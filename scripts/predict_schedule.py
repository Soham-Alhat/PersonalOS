import sys
import pathlib
from datetime import date, timedelta
from collections import defaultdict

sys.path.append(str(pathlib.Path(__file__).parent.parent))
from scripts.supabase_client import get_supabase, get_config


DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
HOURS = list(range(6, 23))


def calculate_slot_score(attempts, completions, avg_mood, streak):
    if attempts < 3:
        return None  # not enough data

    completion_rate  = completions / attempts
    mood_score       = (avg_mood / 5) if avg_mood else 0.5
    streak_momentum  = min(streak / 30, 1.0)

    score = (
        completion_rate  * 0.35 +
        mood_score       * 0.25 +
        streak_momentum  * 0.20 +
        completion_rate  * 0.20  # double weight on completion rate
    )
    return round(score, 3)


def update_behavioral_profile():
    supa    = get_supabase()
    streak  = int(get_config("current_streak"))

    outcomes = supa.table("outcomes").select("*").execute().data or []

    profile_data = defaultdict(lambda: {"attempts": 0, "completions": 0, "moods": []})

    for o in outcomes:
        hour    = o.get("hour_of_day")
        dow     = o.get("day_of_week")
        result  = o.get("result")
        mood    = o.get("mood")

        if not hour or not dow:
            continue

        key = f"{dow}_{hour}"
        profile_data[key]["attempts"] += 1
        if result == "completed":
            profile_data[key]["completions"] += 1
        if mood:
            profile_data[key]["moods"].append(mood)

    for key, data in profile_data.items():
        avg_mood = sum(data["moods"]) / len(data["moods"]) if data["moods"] else 0
        score    = calculate_slot_score(
            data["attempts"], data["completions"], avg_mood, streak
        )

        supa.table("behavioral_profile").upsert({
            "profile_key"    : key,
            "attempts"       : data["attempts"],
            "completions"    : data["completions"],
            "completion_rate": round(data["completions"] / max(data["attempts"], 1), 3),
            "avg_mood"       : round(avg_mood, 2),
        }, on_conflict="profile_key").execute()

    print(f"Behavioral profile updated for {len(profile_data)} slots.")


def get_best_slots(top_n=3) -> list:
    supa = get_supabase()
    resp = (supa.table("behavioral_profile")
            .select("*")
            .gte("attempts", 3)
            .order("completion_rate", desc=True)
            .limit(top_n)
            .execute())
    return resp.data or []


def run():
    print("Running prediction engine...")
    update_behavioral_profile()

    best = get_best_slots()
    if best:
        print("\nYour best slots so far:")
        for slot in best:
            print(f"  {slot['profile_key']} — {slot['completion_rate']*100:.0f}% completion rate")
    else:
        print("Not enough data yet. Keep logging with /done and /failed.")


if __name__ == "__main__":
    run()