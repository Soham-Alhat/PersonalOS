import os
import pathlib
from supabase import create_client


def get_supabase():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")

    if not url or not key:
        try:
            import toml
            p = pathlib.Path(__file__).parent.parent / "dashboard" / ".streamlit" / "secrets.toml"
            s = toml.load(p)
            url = s.get("SUPABASE_URL", "")
            key = s.get("SUPABASE_KEY", "")
        except Exception:
            pass

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY not found.")

    return create_client(url, key)


def get_config(key: str) -> str:
    supa = get_supabase()
    resp = supa.table("config").select("value").eq("key", key).maybesingle().execute()
    return resp.data["value"] if resp.data else ""


def set_config(key: str, value: str):
    supa = get_supabase()
    supa.table("config").upsert(
        {"key": key, "value": value},
        on_conflict="key"
    ).execute()