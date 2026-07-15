import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
import sys, pathlib

sys.path.append(str(pathlib.Path(__file__).parent.parent))
from scripts.supabase_client import get_supabase, get_config

st.set_page_config(page_title="PersonalOS", page_icon="⬡", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

*, html, body, [class*="css"] {
  font-family: 'Outfit', sans-serif !important;
  box-sizing: border-box;
}

/* ── PAGE BG ── */
.stApp { background: #0C0C10; }
.main .block-container { padding: 2rem 2.5rem; max-width: 100%; }

/* ── SIDEBAR ── */
div[data-testid="stSidebar"] {
  background: #111116 !important;
  border-right: 1px solid #1E1E26 !important;
}
div[data-testid="stSidebar"] > div { padding: 0; }

/* ── METRIC CARD ── */
.m-card {
  background: #14141A;
  border: 1px solid #1E1E28;
  border-radius: 12px;
  padding: 20px 22px;
  margin: 0 0 10px 0;
  position: relative;
  overflow: hidden;
  transition: border-color 0.2s, transform 0.2s;
}
.m-card:hover { border-color: #3B3BF9; transform: translateY(-2px); }
.m-card::before {
  content: '';
  position: absolute; top: 0; left: 0;
  width: 3px; height: 100%;
  background: #3B3BF9;
}
.m-label {
  font-size: 10px; font-weight: 600; letter-spacing: 0.1em;
  text-transform: uppercase; color: #4A4A6A; margin-bottom: 8px;
}
.m-value {
  font-family: 'DM Mono', monospace !important;
  font-size: 28px; font-weight: 500; color: #E8E8F0; line-height: 1;
}
.m-sub { font-size: 11px; color: #3A3A58; margin-top: 5px; }

/* ── STAT CARD ── */
.s-card {
  background: #14141A;
  border: 1px solid #1E1E28;
  border-radius: 12px;
  padding: 22px 24px;
  transition: border-color 0.2s;
}
.s-card:hover { border-color: #2A2A3F; }
.s-label { font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
  text-transform: uppercase; color: #3A3A58; margin-bottom: 6px; }
.s-value { font-family: 'DM Mono', monospace !important;
  font-size: 32px; font-weight: 500; color: #E8E8F0; line-height: 1; }
.s-sub { font-size: 12px; color: #3A3A58; margin-top: 5px; }
.s-accent { color: #3B3BF9; }
.s-green  { color: #22C997; }
.s-red    { color: #F75555; }

/* ── SECTION HEADER ── */
.sec-head {
  font-size: 11px; font-weight: 600; letter-spacing: 0.12em;
  text-transform: uppercase; color: #3A3A58;
  padding: 24px 0 10px 0;
  border-bottom: 1px solid #1A1A22;
  margin-bottom: 16px;
}

/* ── INSIGHT ROW ── */
.i-row {
  background: #14141A;
  border: 1px solid #1E1E28;
  border-radius: 10px;
  padding: 14px 18px;
  margin: 6px 0;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.i-date { font-size: 10px; font-family: 'DM Mono', monospace !important;
  color: #3A3A58; margin-bottom: 4px; }
.i-text { font-size: 13px; color: #9090B0; line-height: 1.5; }
.i-mood {
  font-size: 10px; font-family: 'DM Mono', monospace !important;
  background: #1E1E2A; border-radius: 4px;
  padding: 2px 6px; color: #5050A0; white-space: nowrap;
}

/* ── NAV ITEM ── */
.nav-logo {
  padding: 24px 20px 16px;
  border-bottom: 1px solid #1A1A22;
  margin-bottom: 8px;
}
.nav-title { font-size: 15px; font-weight: 600; color: #E8E8F0; }
.nav-sub { font-size: 10px; color: #3A3A58; letter-spacing: 0.08em;
  text-transform: uppercase; margin-top: 2px; }
.nav-section { font-size: 9px; font-weight: 700; letter-spacing: 0.14em;
  text-transform: uppercase; color: #2A2A42; padding: 16px 20px 6px; }

/* ── TAG ── */
.tag {
  display: inline-block; font-size: 10px; font-family: 'DM Mono', monospace !important;
  padding: 2px 8px; border-radius: 4px; font-weight: 500;
}
.tag-blue { background: rgba(59,59,249,0.12); color: #6060FF; }
.tag-green { background: rgba(34,201,151,0.12); color: #22C997; }
.tag-red { background: rgba(247,85,85,0.12); color: #F75555; }

/* ── HIDE STREAMLIT UI ── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
</style>
""", unsafe_allow_html=True)

# ── THEME ──────────────────────────────────────────────────────────────────
BG       = "rgba(0,0,0,0)"
GRID     = "#1A1A22"
BLUE     = "#3B3BF9"
GREEN    = "#22C997"
RED      = "#F75555"
AMBER    = "#F7A455"
TEXT     = "#9090B0"
FONT     = {"color": TEXT, "family": "DM Mono, monospace"}


def chart_layout(title="", height=300, extra=None):
    l = dict(
        paper_bgcolor=BG, plot_bgcolor=BG, font=FONT,
        title=dict(text=title, font=dict(color="#5050A0", size=11,
                   family="Outfit"), x=0),
        height=height, margin=dict(l=0, r=0, t=32, b=0),
        hoverlabel=dict(bgcolor="#14141A", bordercolor="#2A2A3F",
                        font=dict(color="#E8E8F0", size=12, family="Outfit"))
    )
    if extra:
        l.update(extra)
    return l


@st.cache_resource
def get_db():
    return get_supabase()


@st.cache_data(ttl=60)
def load_all():
    supa     = get_db()
    outcomes = pd.DataFrame(supa.table("outcomes").select("*").execute().data or [])
    journal  = pd.DataFrame(supa.table("journal").select("*").execute().data or [])
    reviews  = pd.DataFrame(supa.table("weekly_reviews").select("*").execute().data or [])
    profile  = pd.DataFrame(supa.table("behavioral_profile").select("*").execute().data or [])
    return outcomes, journal, reviews, profile


outcomes_df, journal_df, reviews_df, profile_df = load_all()

placement_str = get_config("placement_date")
placement     = date.fromisoformat(placement_str)
days_left     = (placement - date.today()).days
streak        = get_config("current_streak")
longest       = get_config("longest_streak")
topic         = get_config("weekly_topic")
target        = get_config("daily_task_target")

total_done   = len(outcomes_df[outcomes_df["result"] == "completed"]) if not outcomes_df.empty else 0
total_failed = len(outcomes_df[outcomes_df["result"] == "failed"])    if not outcomes_df.empty else 0
total        = total_done + total_failed
comp_rate    = round(total_done / max(total, 1) * 100, 1)
latest_score = float(reviews_df["readiness_score"].iloc[-1]) if not reviews_df.empty else 0.0

# ── SIDEBAR ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div class="nav-logo">
      <div class="nav-title">⬡ PersonalOS</div>
      <div class="nav-sub">Learning OS · Placement Prep</div>
    </div>
    <div class="nav-section">Overview</div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="m-card">
      <div class="m-label">Placement In</div>
      <div class="m-value">{days_left}</div>
      <div class="m-sub">days · {placement_str}</div>
    </div>
    <div class="m-card">
      <div class="m-label">Active Streak</div>
      <div class="m-value">{streak}</div>
      <div class="m-sub">days · best {longest} days</div>
    </div>
    <div class="m-card">
      <div class="m-label">This Week</div>
      <div class="m-value" style="font-size:16px;padding-top:4px">{topic}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="nav-section">Commands</div>', unsafe_allow_html=True)
    for cmd, desc in [
        ("/done 2", "log tasks complete"),
        ("/failed reason", "log a failure"),
        ("/journal text | 4", "log journal"),
        ("/status", "today's progress"),
        ("/score", "readiness score"),
    ]:
        st.markdown(f"""
        <div style="padding:6px 20px;display:flex;gap:10px;align-items:center">
          <span class="tag tag-blue">{cmd}</span>
          <span style="font-size:11px;color:#3A3A58">{desc}</span>
        </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="padding:20px;margin-top:auto;border-top:1px solid #1A1A22;margin-top:24px">
      <div style="font-size:10px;color:#2A2A42;font-family:'DM Mono',monospace">
        updates every 60s
      </div>
    </div>""", unsafe_allow_html=True)

# ── HEADER ─────────────────────────────────────────────────────────────────
today_str = date.today().strftime("%A, %d %B %Y")
st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:28px">
  <div>
    <div style="font-size:22px;font-weight:600;color:#E8E8F0;letter-spacing:-0.02em">
      Dashboard
    </div>
    <div style="font-size:12px;color:#3A3A58;margin-top:3px;font-family:'DM Mono',monospace">
      {today_str}
    </div>
  </div>
  <div style="display:flex;gap:8px;align-items:center;margin-top:4px">
    <span class="tag tag-{'green' if int(streak) > 0 else 'red'}">
      {'🔥' if int(streak) > 0 else '○'} streak {streak}d
    </span>
    <span class="tag tag-blue">{days_left} days left</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── TOP STATS ──────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
stats = [
    (c1, "Tasks Done",       str(total_done),       f"target {target}/day", "green"),
    (c2, "Tasks Failed",     str(total_failed),      "all time logged",      "red"),
    (c3, "Completion Rate",  f"{comp_rate}%",        f"{total} total logged","blue"),
    (c4, "Readiness Score",  f"{latest_score:.0f}",  "out of 100",           "blue"),
]
for col, label, val, sub, accent in stats:
    with col:
        st.markdown(f"""
        <div class="s-card">
          <div class="s-label">{label}</div>
          <div class="s-value s-{accent}">{val}</div>
          <div class="s-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

# ── ACTIVITY BAR ───────────────────────────────────────────────────────────
st.markdown('<div class="sec-head">Activity · Last 30 Days</div>', unsafe_allow_html=True)

last_30  = [date.today() - timedelta(days=i) for i in range(29, -1, -1)]
activity = {}

if not outcomes_df.empty and "logged_at" in outcomes_df.columns:
    outcomes_df["log_date"] = pd.to_datetime(outcomes_df["logged_at"]).dt.date
    for d, grp in outcomes_df.groupby("log_date"):
        done   = len(grp[grp["result"] == "completed"])
        failed = len(grp[grp["result"] == "failed"])
        activity[d] = {"done": done, "failed": failed}

dates, vals, cols, hov = [], [], [], []
for d in last_30:
    dates.append(d.strftime("%d %b"))
    if d in activity:
        done   = activity[d]["done"]
        failed = activity[d]["failed"]
        if done > 0:
            vals.append(done); cols.append(GREEN)
            hov.append(f"{d} · {done} completed")
        else:
            vals.append(max(failed, 0.3)); cols.append(RED)
            hov.append(f"{d} · {failed} failed")
    else:
        vals.append(0.1); cols.append("#1A1A22")
        hov.append(f"{d} · no data")

fig_act = go.Figure(go.Bar(
    x=dates, y=vals, marker_color=cols,
    hovertemplate="%{customdata}<extra></extra>",
    customdata=hov
))
fig_act.update_layout(**chart_layout(height=160, extra=dict(
    xaxis=dict(gridcolor=GRID, tickfont=dict(size=9), showgrid=False),
    yaxis=dict(gridcolor=GRID, showgrid=False, showticklabels=False),
    bargap=0.25, showlegend=False
)))
st.plotly_chart(fig_act, use_container_width=True)

# ── CHARTS ROW ─────────────────────────────────────────────────────────────
st.markdown('<div class="sec-head">Performance Analysis</div>', unsafe_allow_html=True)
col_a, col_b, col_c = st.columns([1, 1, 1])

with col_a:
    if not outcomes_df.empty:
        rc = outcomes_df["result"].value_counts()
        fig_donut = go.Figure(go.Pie(
            labels=rc.index.tolist(),
            values=rc.values.tolist(),
            hole=0.65,
            marker=dict(
                colors=[GREEN, RED, AMBER],
                line=dict(color="#0C0C10", width=3)
            ),
            hovertemplate="<b>%{label}</b><br>%{value}<extra></extra>",
            textinfo="none"
        ))
        fig_donut.add_annotation(
            text=f"{comp_rate}%", x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color="#E8E8F0", family="DM Mono")
        )
        fig_donut.update_layout(**chart_layout("TASK OUTCOMES", height=260, extra=dict(
            showlegend=True,
            legend=dict(font=dict(size=10, color=TEXT), bgcolor="rgba(0,0,0,0)")
        )))
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.markdown('<div class="s-card" style="height:260px;display:flex;align-items:center;justify-content:center"><span style="color:#2A2A42;font-size:12px">No data yet</span></div>', unsafe_allow_html=True)

with col_b:
    if not outcomes_df.empty and "failure_reason" in outcomes_df.columns:
        fail_df = outcomes_df[outcomes_df["result"] == "failed"]["failure_reason"].dropna()
        if not fail_df.empty:
            fc = fail_df.value_counts().head(6)
            fig_fail = go.Figure(go.Bar(
                x=fc.values,
                y=fc.index.tolist(),
                orientation="h",
                marker=dict(color=RED, opacity=0.7),
                hovertemplate="<b>%{y}</b><br>%{x} times<extra></extra>"
            ))
            fig_fail.update_layout(**chart_layout("FAILURE REASONS", height=260, extra=dict(
                xaxis=dict(gridcolor=GRID, tickfont=dict(size=9)),
                yaxis=dict(gridcolor=GRID, categoryorder="total ascending",
                           tickfont=dict(size=10)),
                bargap=0.4
            )))
            st.plotly_chart(fig_fail, use_container_width=True)
        else:
            st.markdown('<div class="s-card" style="height:260px;display:flex;align-items:center;justify-content:center"><span style="color:#2A2A42;font-size:12px">No failures logged</span></div>', unsafe_allow_html=True)

with col_c:
    if not reviews_df.empty:
        fig_score = go.Figure()
        fig_score.add_trace(go.Scatter(
            x=reviews_df["week_label"].tolist(),
            y=reviews_df["readiness_score"].tolist(),
            mode="lines+markers",
            line=dict(color=BLUE, width=2),
            marker=dict(color=BLUE, size=6,
                        line=dict(color="#0C0C10", width=2)),
            fill="tozeroy",
            fillcolor="rgba(59,59,249,0.06)",
            hovertemplate="<b>%{x}</b><br>%{y}/100<extra></extra>"
        ))
        fig_score.add_hline(y=80, line_dash="dot", line_color=GREEN,
                            line_width=1, opacity=0.4)
        fig_score.update_layout(**chart_layout("READINESS TREND", height=260, extra=dict(
            xaxis=dict(gridcolor=GRID, tickfont=dict(size=9)),
            yaxis=dict(gridcolor=GRID, range=[0, 100], tickfont=dict(size=9))
        )))
        st.plotly_chart(fig_score, use_container_width=True)
    else:
        st.markdown('<div class="s-card" style="height:260px;display:flex;align-items:center;justify-content:center"><span style="color:#2A2A42;font-size:12px">No weekly data yet</span></div>', unsafe_allow_html=True)

# ── BOTTOM ROW ─────────────────────────────────────────────────────────────
st.markdown('<div class="sec-head">Readiness & Journal</div>', unsafe_allow_html=True)
col_g, col_j = st.columns([1, 2])

with col_g:
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=latest_score,
        number={"suffix": "", "font": {"color": "#E8E8F0", "size": 40,
                                        "family": "DM Mono"}},
        gauge=dict(
            axis=dict(range=[0, 100], tickcolor=GRID,
                      tickfont=dict(color="#3A3A58", size=9)),
            bar=dict(color=BLUE, thickness=0.2),
            bgcolor="#14141A",
            bordercolor=GRID, borderwidth=1,
            steps=[
                dict(range=[0,  40],  color="#14141A"),
                dict(range=[40, 70],  color="#161620"),
                dict(range=[70, 100], color="#18182A"),
            ],
            threshold=dict(line=dict(color=GREEN, width=2), value=80)
        ),
        title={"text": "READINESS SCORE",
               "font": {"color": "#3A3A58", "size": 10, "family": "Outfit"}}
    ))
    fig_gauge.update_layout(**chart_layout(height=260,
                            extra=dict(margin=dict(l=20, r=20, t=40, b=10))))
    st.plotly_chart(fig_gauge, use_container_width=True)

with col_j:
    if not journal_df.empty:
        recent = journal_df.sort_values("entry_date", ascending=False).head(5)
        for _, row in recent.iterrows():
            mood_val = row.get("mood", None)
            mood_tag = f'<span class="i-mood">mood {mood_val}/5</span>' if mood_val else ""
            entry    = row.get("entry", "—") or "—"
            st.markdown(f"""
            <div class="i-row">
              <div style="flex:1">
                <div class="i-date">{row['entry_date']} {mood_tag}</div>
                <div class="i-text">{entry}</div>
              </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="i-row">
          <div class="i-text" style="color:#2A2A42">
            No journal entries yet.<br>
            Use <span class="tag tag-blue">/journal your text | 4</span> in Telegram.
          </div>
        </div>""", unsafe_allow_html=True)

# ── BEHAVIORAL PROFILE ─────────────────────────────────────────────────────
if not profile_df.empty and len(profile_df) > 0:
    st.markdown('<div class="sec-head">Behavioral Profile · Best Slots</div>', unsafe_allow_html=True)
    top = profile_df.sort_values("completion_rate", ascending=False).head(5)
    st.dataframe(
        top[["profile_key","attempts","completions","completion_rate","avg_mood"]]
        .rename(columns={
            "profile_key"    : "Slot (Day_Hour)",
            "attempts"       : "Attempts",
            "completions"    : "Completed",
            "completion_rate": "Rate",
            "avg_mood"       : "Avg Mood"
        }),
        use_container_width=True, height=180
    )

# ── DANGER ZONE — RESET ALL PROGRESS ─────────────────────────────────────
st.divider()
st.subheader("⚠️ Danger Zone")
 
TABLES_TO_RESET = ["outcomes", "journal", "weekly_reviews", "behavioral_profile"]
 
def reset_all_progress():
    supa = get_db()
    results = {}
    for table in TABLES_TO_RESET:
        try:
            supa.table(table).delete().neq("id", 0).execute()
            results[table] = "cleared"
        except Exception as e:
            results[table] = f"error: {e}"
    # also reset streak counters back to zero
    try:
        from scripts.supabase_client import set_config
        set_config("current_streak", "0")
        set_config("longest_streak", "0")
        results["streak_config"] = "reset"
    except Exception as e:
        results["streak_config"] = f"error: {e}"
    return results
 
with st.expander("Reset all progress"):
    st.warning(
        "This permanently deletes ALL data: tasks/outcomes, journal entries, "
        "weekly reviews, behavioral profile, and resets your streak to 0. "
        "This cannot be undone."
    )
    confirm_check = st.checkbox("I understand this is permanent")
    confirm_text = st.text_input('Type "RESET" to confirm')
 
    if st.button("Reset All Progress", type="primary", disabled=not confirm_check):
        if confirm_text == "RESET":
            outcome = reset_all_progress()
            st.success("Reset complete:")
            st.json(outcome)
            st.cache_data.clear()
        else:
            st.error('You must type "RESET" exactly to confirm.')

# ── FOOTER ─────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="margin-top:40px;padding-top:16px;border-top:1px solid #1A1A22;
     display:flex;justify-content:space-between;align-items:center">
  <div style="font-size:11px;color:#2A2A42;font-family:'DM Mono',monospace">
    PersonalOS · Soham Alhat · {date.today().year}
  </div>
  <div style="font-size:11px;color:#2A2A42;font-family:'DM Mono',monospace">
    data refreshes every 60s
  </div>
</div>
""", unsafe_allow_html=True)