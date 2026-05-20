import os
import sys
import pathlib
import requests
from fastapi import FastAPI, Request
from datetime import date, datetime, timezone

sys.path.append(str(pathlib.Path(__file__).parent.parent))
from scripts.supabase_client import get_supabase, get_config, set_config

app = FastAPI()


def get_telegram_creds():
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        try:
            import toml
            p = pathlib.Path(__file__).parent.parent / "dashboard" / ".streamlit" / "secrets.toml"
            s = toml.load(p)
            token   = s.get("TELEGRAM_BOT_TOKEN", "")
            chat_id = s.get("TELEGRAM_CHAT_ID", "")
        except Exception:
            pass
    return token, chat_id


def send_telegram(message: str):
    token, chat_id = get_telegram_creds()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={
        "chat_id"   : chat_id,
        "text"      : message,
        "parse_mode": "Markdown"
    })


def handle_status():
    streak      = get_config("current_streak")
    target      = get_config("daily_task_target")
    topic       = get_config("weekly_topic")
    placement   = get_config("placement_date")
    days_left   = (date.fromisoformat(placement) - date.today()).days

    supa  = get_supabase()
    today = date.today().isoformat()
    outcomes_today = (supa.table("outcomes")
                      .select("result")
                      .gte("logged_at", today)
                      .execute()).data or []

    completed_today = sum(1 for o in outcomes_today if o.get("result") == "completed")

    send_telegram(f"""📊 *Status — {date.today().strftime('%A')}*

✅ Done today: *{completed_today}/{target}*
🔥 Streak: *{streak} days*
📅 Days to placement: *{days_left}*
📚 Focus: *{topic}*""")


def handle_done(amount: int):
    supa = get_supabase()
    now  = datetime.now(timezone.utc)

    for _ in range(amount):
        supa.table("outcomes").insert({
            "result"      : "completed",
            "hour_of_day" : now.hour,
            "day_of_week" : now.strftime("%A"),
            "logged_at"   : now.isoformat()
        }).execute()

    streak = int(get_config("current_streak")) + 1
    longest = int(get_config("longest_streak"))
    if streak > longest:
        set_config("longest_streak", str(streak))
    set_config("current_streak", str(streak))

    send_telegram(f"✅ Logged *{amount}* task(s) completed. Streak: *{streak} days*. Keep going.")


def handle_failed(reason: str = ""):
    supa = get_supabase()
    now  = datetime.now(timezone.utc)

    supa.table("outcomes").insert({
        "result"        : "failed",
        "failure_reason": reason if reason else "unspecified",
        "hour_of_day"   : now.hour,
        "day_of_week"   : now.strftime("%A"),
        "logged_at"     : now.isoformat()
    }).execute()

    send_telegram(f"❌ Task logged as failed. Reason: _{reason if reason else 'not specified'}_\nUse /skip to reschedule your session.")

def handle_skip():
    supa = get_supabase()
    now  = datetime.now(timezone.utc)

    supa.table("outcomes").insert({
        "result"        : "failed",
        "failure_reason": "skipped",
        "hour_of_day"   : now.hour,
        "day_of_week"   : now.strftime("%A"),
        "logged_at"     : now.isoformat()
    }).execute()

    send_telegram("⏭️ Session skipped and logged.\nFocus on tomorrow — streak protection active.")

def handle_weak():
    supa = get_supabase()
    resp = (supa.table("outcomes")
            .select("failure_reason")
            .eq("result", "failed")
            .execute())
    data = resp.data or []

    reasons = [r["failure_reason"] for r in data if r.get("failure_reason")]
    if not reasons:
        send_telegram("No failure data yet. Start logging tasks with /done and /failed.")
        return

    from collections import Counter
    counts  = Counter(reasons).most_common(3)
    lines   = "\n".join([f"• {r}: {c} times" for r, c in counts])
    send_telegram(f"🔍 *Your top failure reasons:*\n{lines}")


def handle_journal(text: str):
    supa  = get_supabase()
    today = date.today().isoformat()

    parts = [p.strip() for p in text.split("|")]
    mood  = None
    if len(parts) >= 2:
        try:
            mood = int(parts[-1])
            text = "|".join(parts[:-1])
        except ValueError:
            pass

    supa.table("journal").upsert({
        "entry_date"        : today,
        "entry"             : text,
        "mood"              : mood,
        "logged_via"        : "telegram",
        "logged_at"         : datetime.now(timezone.utc).isoformat()
    }, on_conflict="entry_date").execute()

    send_telegram(f"📓 Journal logged for today. Mood: *{mood}/5*" if mood else "📓 Journal entry saved.")


def handle_streak():
    streak  = get_config("current_streak")
    longest = get_config("longest_streak")
    send_telegram(f"🔥 Current streak: *{streak} days*\n🏆 Longest streak: *{longest} days*")


def handle_score():
    supa = get_supabase()
    resp = (supa.table("weekly_reviews")
            .select("week_label, readiness_score")
            .order("created_at", desc=True)
            .limit(1)
            .execute())

    if resp.data:
        row = resp.data[0]
        send_telegram(f"🧠 *Readiness score — {row['week_label']}*\n*{row['readiness_score']}/100*")
    else:
        send_telegram("No weekly score yet. Run /weekly after logging some tasks.")


@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        body    = await request.json()
        message = body.get("message", {})
        text    = message.get("text", "").strip()

        if not text:
            return {"ok": True}

        print(f"Received: {text}")

        if text == "/status":
            handle_status()
        elif text.startswith("/done"):
            parts  = text.split()
            amount = int(parts[1]) if len(parts) > 1 else 1
            handle_done(amount)
        elif text.startswith("/failed"):
            parts  = text.split(maxsplit=1)
            reason = parts[1] if len(parts) > 1 else ""
            handle_failed(reason)
        elif text == "/skip":
            handle_skip()
        elif text == "/weak":
            handle_weak()
        elif text == "/streak":
            handle_streak()
        elif text == "/score":
            handle_score()
        elif text.startswith("/journal"):
            parts   = text.split(maxsplit=1)
            content = parts[1] if len(parts) > 1 else ""
            handle_journal(content)
        else:
            send_telegram(
                "Commands:\n"
                "/status — today's progress\n"
                "/done 2 — log 2 tasks complete\n"
                "/failed low energy — log a failure\n"
                "/skip — skip today's session\n"
                "/journal your entry | mood — log journal\n"
                "/weak — your top failure reasons\n"
                "/streak — streak history\n"
                "/score — latest readiness score"
            )

    except Exception as e:
        print(f"Webhook error: {e}")

    return {"ok": True}


@app.get("/")
def health():
    return {"status": "PersonalOS webhook running"}