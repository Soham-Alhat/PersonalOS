# 🧠 PersonalOS

**A self-learning personal operating system for placement prep.**

[![Dashboard](https://img.shields.io/badge/Live%20Dashboard-Open-6C63FF?style=for-the-badge)](https://personalos-3nehhfdyshqvahbazrn2lr.streamlit.app/)

Built because I needed a system that adapts to how I actually work —
not just a reminder app that ignores when I fail.

## What it does

- 7 AM Telegram briefing — streak, days to placement, today's focus topic
- Log tasks via Telegram commands — `/done 2`, `/failed low energy`, `/journal`
- Detects failure patterns and adapts daily targets based on mood
- Calculates weekly readiness score (0-100) from real behavioral data
- Streamlit dashboard shows activity, failure reasons, readiness trend
- Everything runs automatically on GitHub Actions — no laptop needed

## Commands

| Command | What it does |
|---|---|
| `/done 2` | Log 2 tasks completed |
| `/failed low energy` | Log a failure with reason |
| `/skip` | Skip today, log it |
| `/journal your text \| 4` | Log journal entry with mood |
| `/status` | Today's progress |
| `/streak` | Current and longest streak |
| `/score` | Latest readiness score |
| `/weak` | Your top failure reasons |

## Stack

- GitHub Actions — daily 7AM briefing, Sunday weekly report, midday nudge
- FastAPI on Render — receives Telegram commands in real time
- Supabase — stores outcomes, journal, behavioral profile, weekly reviews
- Streamlit Cloud — live dashboard

## Intelligence layer

No LLM. Pure behavioral data:
- Mood-based load adaptation — 3 low mood days → target reduced 30%
- Failure pattern detection — top reasons surfaced weekly
- Weighted slot scoring — learns your best hours from outcome history
- Anomaly detection — flags 30%+ drop in completion rate
- Placement readiness forecast — linear projection to placement date

## Run locally

```bash
pip install supabase fastapi uvicorn python-telegram-bot requests toml streamlit plotly pandas
streamlit run dashboard/app.py
```

Built by Soham Alhat · MCA · 2026
