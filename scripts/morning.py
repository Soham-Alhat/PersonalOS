import os
import sys
import json
import requests
import pathlib
from datetime import datetime, date, timezone

sys.path.append(str(pathlib.Path(__file__).parent.parent))
from scripts.supabase_client import get_supabase, get_config


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
    resp = requests.post(url, json={
        "chat_id"    : chat_id,
        "text"       : message,
        "parse_mode" : "Markdown"
    })
    if resp.status_code == 200:
        print("Telegram message sent.")
    else:
        print(f"Telegram failed: {resp.text}")


def get_days_left() -> int:
    placement_str = get_config("placement_date")
    placement     = date.fromisoformat(placement_str)
    today         = date.today()
    return (placement - today).days


def get_daily_target() -> int:
    return int(get_config("daily_task_target"))


def get_streak() -> int:
    return int(get_config("current_streak"))


def get_weekly_topic() -> str:
    return get_config("weekly_topic")


def get_yesterday_blocker() -> str:
    supa      = get_supabase()
    yesterday = (date.today().toordinal() - 1)
    yesterday = date.fromordinal(yesterday).isoformat()

    resp = (supa.table("journal")
            .select("win_of_day, tomorrow_intention")
            .eq("entry_date", yesterday)
            .execute())

    if resp.data:
        entry     = resp.data[0]
        intention = entry.get("tomorrow_intention", "")
        return intention if intention else "Nothing logged yesterday."
    return "No journal entry yesterday."


def get_mood_last_3_days() -> list:
    supa = get_supabase()
    resp = (supa.table("journal")
            .select("mood, entry_date")
            .order("entry_date", desc=True)
            .limit(3)
            .execute())
    return [r["mood"] for r in resp.data if r.get("mood")] if resp.data else []


def calculate_adjusted_target(base_target: int, moods: list) -> tuple:
    if len(moods) >= 3 and all(m <= 2 for m in moods):
        adjusted = max(1, round(base_target * 0.7))
        return adjusted, True
    return base_target, False


def build_message(days_left, target, adjusted, streak, topic, blocker) -> str:
    today     = datetime.now().strftime("%A, %d %B %Y")
    streak_emoji = "🔥" if streak >= 3 else "✨"

    mood_note = ""
    if adjusted:
        mood_note = "\n⚠️ _Low mood detected for 3 days. Target reduced — protect the streak._"

    message = f"""📡 *PersonalOS — Morning Briefing*
_{today}_

📅 *{days_left} days* to placement
{streak_emoji} Streak: *{streak} days*
🎯 Today's target: *{target} tasks*{mood_note}

📚 Focus topic: *{topic}*

🗒️ Yesterday's intention:
_{blocker}_

---
_Stay consistent. One task at a time._"""

    return message


def run():
    print("Running morning briefing...")

    days_left   = get_days_left()
    base_target = get_daily_target()
    streak      = get_streak()
    topic       = get_weekly_topic()
    blocker     = get_yesterday_blocker()
    moods       = get_mood_last_3_days()

    target, adjusted = calculate_adjusted_target(base_target, moods)

    message = build_message(days_left, target, adjusted, streak, topic, blocker)

    print("\n--- Message Preview ---")
    print(message)
    print("----------------------\n")

    send_telegram(message)


if __name__ == "__main__":
    run()