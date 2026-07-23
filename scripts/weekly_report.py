import os
import sys
import pathlib
import requests
from datetime import date, timedelta

sys.path.append(str(pathlib.Path(__file__).parent.parent))
from scripts.supabase_client import get_supabase, get_config, set_config


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
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={
        "chat_id"   : chat_id,
        "text"      : message,
        "parse_mode": "Markdown"
    })


def calculate_readiness_score(completed, target, streak, avg_mood, days_active) -> float:
    # tasks vs target: 30 pts
    task_score = min(30, (completed / max(target, 1)) * 30)
    # streak consistency: 25 pts
    streak_score = min(25, (streak / 7) * 25)
    # mood stability: 20 pts
    mood_score = min(20, (avg_mood / 5) * 20)
    # days active out of 7: 25 pts
    activity_score = min(25, (days_active / 7) * 25)

    return round(task_score + streak_score + mood_score + activity_score, 1)


def detect_anomaly(current_rate: float, avg_rate: float) -> bool:
    if avg_rate == 0:
        return False
    drop = (avg_rate - current_rate) / avg_rate
    return drop >= 0.30


def run():
    supa      = get_supabase()
    today     = date.today()
    week_ago  = today - timedelta(days=7)
    week_label = f"{today.year}-W{today.isocalendar()[1]}"

    print(f"Generating weekly report for {week_label}...")

    # ── fetch outcomes from last 7 days ────────────────────────────────────
    outcomes_resp = (supa.table("outcomes")
                     .select("result, mood, failure_reason")
                     .gte("logged_at", week_ago.isoformat())
                     .execute())
    outcomes = outcomes_resp.data or []

    completed   = sum(1 for o in outcomes if o.get("result") == "completed")
    failed      = sum(1 for o in outcomes if o.get("result") == "failed")
    total       = completed + failed
    comp_rate   = round(completed / max(total, 1) * 100, 1)

    failure_reasons = [o["failure_reason"] for o in outcomes if o.get("failure_reason")]
    top_failure = max(set(failure_reasons), key=failure_reasons.count) if failure_reasons else "None"

    # ── fetch journal entries from last 7 days ─────────────────────────────
    journal_resp = (supa.table("journal")
                    .select("entry_date, mood")
                    .gte("entry_date", week_ago.isoformat())
                    .execute())
    journal_entries = journal_resp.data or []
    days_active     = len(journal_entries)

    moods = [j["mood"] for j in journal_entries if j.get("mood")]
    avg_mood = round(sum(moods) / len(moods), 1) if moods else 0

    # ── streak ─────────────────────────────────────────────────────────────
    streak      = int(get_config("current_streak"))
    daily_target = int(get_config("daily_task_target"))

    # ── readiness score ────────────────────────────────────────────────────
    weekly_target  = daily_target * 7
    readiness      = calculate_readiness_score(completed, weekly_target, streak, avg_mood, days_active)

    # ── anomaly detection ──────────────────────────────────────────────────
    prev_reviews = (supa.table("weekly_reviews")
                    .select("tasks_completed, tasks_failed")
                    .order("created_at", desc=True)
                    .limit(4)
                    .execute())
    prev_data   = prev_reviews.data or []
    if prev_data:
        prev_rates  = [r["tasks_completed"] / max(r["tasks_completed"] + r["tasks_failed"], 1)
                       for r in prev_data]
        avg_prev    = sum(prev_rates) / len(prev_rates)
        current_r   = completed / max(total, 1)
        anomaly     = detect_anomaly(current_r, avg_prev)
    else:
        anomaly = False

    # ── save to weekly_reviews ─────────────────────────────────────────────
    supa.table("weekly_reviews").upsert({
        "week_label"        : week_label,
        "tasks_completed"   : completed,
        "tasks_failed"      : failed,
        "avg_mood"          : avg_mood,
        "streak"            : streak,
        "readiness_score"   : readiness,
        "top_failure_reason": top_failure
    }, on_conflict="week_label").execute()

    # ── build and send Telegram message ────────────────────────────────────
    anomaly_note = ""
    if anomaly:
        anomaly_note = "\n⚠️ *Anomaly detected* — output dropped 30%+ vs your recent average.\n"

    message = f"""📊 *PersonalOS — Week {today.isocalendar()[1]} Report*

✅ Completed: *{completed}* tasks
❌ Failed: *{failed}* tasks
📈 Completion rate: *{comp_rate}%*
😐 Avg mood: *{avg_mood}/5*
🔥 Streak: *{streak} days*
📅 Active days: *{days_active}/7*
{anomaly_note}
🧠 *Readiness score: {readiness}/100*

🚫 Top failure reason: _{top_failure}_

---
_Keep the streak. Small consistent wins beat everything._"""

    print(message)
    send_telegram(message)
    print("Weekly report sent.")


if __name__ == "__main__":
    run()