import os
import sys
import pathlib
import requests
import traceback
from fastapi import FastAPI, Request
from datetime import date, datetime, timezone, timedelta

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


def send(message: str):
    token, chat_id = get_telegram_creds()
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    )


# ── HANDLERS ───────────────────────────────────────────────────────────────

def handle_status():
    streak    = get_config("current_streak")
    target    = get_config("daily_task_target")
    topic     = get_config("weekly_topic")
    placement = get_config("placement_date")
    days_left = (date.fromisoformat(placement) - date.today()).days

    supa  = get_supabase()
    today = date.today().isoformat()
    outcomes_today = (supa.table("outcomes")
                      .select("result")
                      .gte("logged_at", today)
                      .execute()).data or []
    done = sum(1 for o in outcomes_today if o.get("result") == "completed")

    remaining = int(target) - done
    remaining_txt = (f"{remaining} left to hit target" if remaining > 0
                     else "Target hit for today, sir")

    send(f"""📋 *Here's where you stand, sir*

✅ Done today: *{done}* of *{target}*
🔥 Streak: *{streak} days*
📅 Placement: *{days_left} days away*
📚 Focus: *{topic}*

_{remaining_txt}_""")


def handle_done(amount: int):
    supa  = get_supabase()
    now   = datetime.now(timezone.utc)
    today = date.today()

    for _ in range(amount):
        supa.table("outcomes").insert({
            "result"      : "completed",
            "hour_of_day" : now.hour,
            "day_of_week" : now.strftime("%A"),
            "logged_at"   : now.isoformat()
        }).execute()

    # ── streak logic: advance at most once per calendar day ────────────
    try:
        last_date_str = get_config("streak_last_date")
    except Exception:
        last_date_str = ""

    streak  = int(get_config("current_streak"))
    longest = int(get_config("longest_streak"))

    if last_date_str == today.isoformat():
        # already counted today — don't touch the streak, just log the task
        pass
    else:
        last_date = date.fromisoformat(last_date_str) if last_date_str else None
        if last_date == today - timedelta(days=1):
            streak += 1                 # consecutive day — extend the streak
        else:
            streak = 1                  # gap in days (or first ever) — reset to 1

        set_config("current_streak", str(streak))
        set_config("streak_last_date", today.isoformat())

        if streak > longest:
            set_config("longest_streak", str(streak))

    remarks = {
        1: "One down. Onwards.",
        2: "Two done. The momentum is yours.",
        3: "Three. That's a full day's work, sir.",
    }
    remark = remarks.get(amount, f"All {amount} logged.")

    send(f"✅ {remark}\n🔥 Streak now at *{streak} days*.")


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

    reason_line = f"Noted: _{reason}_" if reason else "No reason given — that's fine."
    send(f"📝 Logged.\n{reason_line}\n\nEven the best days have misses, sir.")


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

    send("⏭️ Session logged as skipped.\n_Tomorrow is already waiting, sir._")


def handle_add(text: str):
    supa   = get_supabase()
    parts  = [p.strip() for p in text.split("|")]
    name   = parts[0]
    priority = parts[1].lower() if len(parts) > 1 else "medium"
    deadline = parts[2] if len(parts) > 2 else None

    if not name:
        send("Tell me what to add, sir. Format:\n`/add task name | priority | deadline`")
        return

    valid_priorities = ["urgent", "high", "medium", "low"]
    if priority not in valid_priorities:
        priority = "medium"

    supa.table("tasks").insert({
        "name"      : name,
        "priority"  : priority,
        "deadline"  : deadline,
        "status"    : "pending",
        "category"  : "manual",
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()

    priority_icons = {"urgent": "🚨", "high": "🔴", "medium": "🟡", "low": "🟢"}
    icon = priority_icons.get(priority, "🟡")

    msg = f"📌 Added to your list, sir.\n\n{icon} *{name}*\nPriority: {priority}"
    if deadline:
        msg += f"\nDeadline: {deadline}"
    send(msg)


def handle_done_task(name_fragment: str):
    supa  = get_supabase()
    tasks = (supa.table("tasks")
             .select("*")
             .eq("status", "pending")
             .execute()).data or []

    matches = [t for t in tasks
               if name_fragment.lower() in t.get("name", "").lower()]

    if not matches:
        send(f"No task matching *{name_fragment}* on the list, sir.")
        return

    t = matches[0]
    supa.table("tasks").update({"status": "done"}).eq("id", t["id"]).execute()
    send(f"✅ *{t['name']}* — marked done.\n_Well done, sir._")


def handle_delete(arg: str = ""):
    """
    /delete            -> list all pending tasks
    /delete 2          -> remove pending task #2 (1-indexed, as shown by the list)
    /delete some name  -> remove first pending task whose name contains the fragment
    """
    supa  = get_supabase()
    tasks = (supa.table("tasks")
             .select("*")
             .eq("status", "pending")
             .order("created_at", desc=False)
             .execute()).data or []

    if not tasks:
        send("Your list is clear, sir. Nothing pending.")
        return

    priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    tasks = sorted(tasks, key=lambda x: priority_order.get(x.get("priority", "low"), 3))
    icons = {"urgent": "🚨", "high": "🔴", "medium": "🟡", "low": "🟢"}

    # no argument — just list tasks
    if not arg:
        lines = []
        for i, t in enumerate(tasks, 1):
            icon     = icons.get(t.get("priority", "medium"), "🟡")
            deadline = f" · _{t['deadline']}_" if t.get("deadline") else ""
            lines.append(f"{i}. {icon} {t.get('name','')}{deadline}")
        send(f"📋 *Your tasks, sir:*\n\n"
             + "\n".join(lines)
             + "\n\n_Reply /delete 2 to remove task 2_")
        return

    # number given — delete by index
    if arg.isdigit():
        index = int(arg) - 1
        if index < 0 or index >= len(tasks):
            send(f"No task at position {arg}, sir.")
            return
        t = tasks[index]
        supa.table("tasks").update({"status": "removed"}).eq("id", t["id"]).execute()
        send(f"🗑️ Removed: *{t['name']}*\n_Done, sir._")
        return

    # text given — delete by name fragment
    matches = [t for t in tasks if arg.lower() in t.get("name", "").lower()]
    if not matches:
        send(f"Nothing matching *{arg}* on the list, sir.")
        return
    t = matches[0]
    supa.table("tasks").update({"status": "removed"}).eq("id", t["id"]).execute()
    send(f"🗑️ Removed: *{t['name']}*\n_Done, sir._")


def handle_weak():
    supa = get_supabase()
    resp = (supa.table("outcomes")
            .select("failure_reason")
            .eq("result", "failed")
            .execute())
    data = resp.data or []

    reasons = [r["failure_reason"] for r in data
               if r.get("failure_reason") and r["failure_reason"] != "unspecified"]

    if not reasons:
        send("No failure patterns yet, sir. Keep logging with /failed.")
        return

    from collections import Counter
    counts = Counter(reasons).most_common(3)
    lines  = [f"• *{r}* — {c} {'time' if c == 1 else 'times'}" for r, c in counts]

    send("🔍 *Your top failure reasons, sir:*\n\n" + "\n".join(lines)
         + "\n\n_Awareness is the first step._")


def handle_streak():
    streak  = get_config("current_streak")
    longest = get_config("longest_streak")

    if int(streak) == 0:
        msg = "No active streak yet, sir. Today is a good day to start."
    elif int(streak) >= int(longest):
        msg = f"🔥 *{streak} days* — and that's your best ever. Keep going."
    else:
        msg = f"🔥 *{streak} days* active · Best ever: *{longest} days*"

    send(msg)


def handle_score():
    supa = get_supabase()
    resp = (supa.table("weekly_reviews")
            .select("week_label, readiness_score")
            .order("created_at", desc=True)
            .limit(1)
            .execute())

    if resp.data:
        row   = resp.data[0]
        score = row['readiness_score']
        week  = row['week_label']

        if score >= 80:
            verdict = "Excellent. You're on track, sir."
        elif score >= 60:
            verdict = "Solid. A few adjustments and you'll be there."
        elif score >= 40:
            verdict = "Room to grow. Let's pick up the pace, sir."
        else:
            verdict = "Early days. Consistency is all that matters right now."

        send(f"🧠 *Readiness — {week}*\n\n*{score}/100*\n\n_{verdict}_")
    else:
        send("No score yet, sir. Run the week out and check back Sunday.")


def handle_journal(text: str):
    supa  = get_supabase()
    today = date.today().isoformat()
    parts = [p.strip() for p in text.split("|")]
    mood  = None

    if len(parts) >= 2:
        try:
            mood = int(parts[-1])
            text = "|".join(parts[:-1]).strip()
        except ValueError:
            pass

    supa.table("journal").upsert({
        "entry_date": today,
        "entry"     : text,
        "mood"      : mood,
        "logged_via": "telegram",
        "logged_at" : datetime.now(timezone.utc).isoformat()
    }, on_conflict="entry_date").execute()

    mood_line = f"\nMood logged: *{mood}/5*" if mood else ""
    send(f"📓 Journal saved, sir.{mood_line}\n_Every entry counts._")


def handle_help():
    send("""🤵 *At your service, sir.*

*Logging*
`/done 2` — log 2 tasks complete
`/failed low energy` — log a failure
`/skip` — skip today's session
`/journal your entry | mood` — log your day

*Tasks*
`/add name | priority | deadline` — add a task
`/delete` — see all pending tasks
`/delete 2` — remove task number 2
`/finish name` — mark a task done

*Intel*
`/status` — today's overview
`/streak` — current streak
`/score` — readiness score
`/weak` — your failure patterns

_Priority options: urgent · high · medium · low_""")


# ── ROUTER ─────────────────────────────────────────────────────────────────

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        body    = await request.json()
        message = body.get("message", {})
        text    = message.get("text", "").strip()

        print(f"Received: {repr(text)}")

        if not text:
            return {"ok": True}

        # Robust command parsing:
        # - split off the first whitespace-separated token as the command
        # - strip a "@BotUsername" suffix Telegram appends in group chats
        # - lowercase the command for matching, keep the remainder as-is
        parts       = text.split(maxsplit=1)
        command_raw = parts[0]
        command     = command_raw.split("@")[0].lower()
        arg_text    = parts[1].strip() if len(parts) > 1 else ""

        print(f"Parsed command={command!r} arg={arg_text!r}")

        if command == "/status":
            handle_status()
        elif command == "/done":
            amount = int(arg_text) if arg_text.isdigit() else 1
            handle_done(amount)
        elif command == "/failed":
            handle_failed(arg_text)
        elif command == "/skip":
            handle_skip()
        elif command == "/add":
            handle_add(arg_text)
        elif command == "/finish":
            handle_done_task(arg_text)
        elif command in ("/delete", "/list"):
            handle_delete(arg_text)
        elif command == "/weak":
            handle_weak()
        elif command == "/streak":
            handle_streak()
        elif command == "/score":
            handle_score()
        elif command == "/journal":
            handle_journal(arg_text)
        elif command in ["/help", "/start"]:
            handle_help()
        else:
            handle_help()

    except Exception as e:
        print(f"Webhook error: {e}")
        traceback.print_exc()
        try:
            send(f"⚠️ Something went wrong processing that command, sir.\n_{e}_")
        except Exception:
            pass

    return {"ok": True}


@app.get("/")
def health():
    return {"status": "PersonalOS — online, sir."}