import os
import sys
import pathlib
import requests
from datetime import date

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
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    )


def already_journaled_today() -> bool:
    supa  = get_supabase()
    today = date.today().isoformat()
    resp  = (supa.table("journal")
             .select("id")
             .eq("entry_date", today)
             .execute())
    return len(resp.data) > 0


def run():
    if already_journaled_today():
        print("Already journaled today. Skipping prompt.")
        return

    supa    = get_supabase()
    target  = get_config("daily_task_target")
    today   = date.today().isoformat()

    outcomes = (supa.table("outcomes")
                .select("result")
                .gte("logged_at", today)
                .execute()).data or []

    completed = sum(1 for o in outcomes if o.get("result") == "completed")

    send_telegram(f"""🌙 *Evening Check-in*

You completed *{completed}/{target}* tasks today.

Reply with `/journal your entry | mood(1-5)` to log your day.

Example:
`/journal Solved sliding window problems, struggled with edge cases | 3`

_Takes 30 seconds. Worth every day._""")

    print("Evening journal prompt sent.")


if __name__ == "__main__":
    run()