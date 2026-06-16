import streamlit as st
import plotly.graph_objects as go
import requests
import os
from dotenv import load_dotenv

load_dotenv()
API = os.getenv("BACKEND_URL", "http://localhost:8000")

# ── HELPERS ──────────────────────────────────────────────────────────────────
def format_inr(amount):
    if not amount: return "₹0"
    amount = float(amount)
    if amount >= 1_00_00_000: return f"₹{amount/1_00_00_000:.1f}Cr"
    elif amount >= 1_00_000:  return f"₹{amount/1_00_000:.1f}L"
    return f"₹{amount:,.0f}"

def tier_class(tier):
    return (tier or "low").lower()

def badge_html(tier):
    t = (tier or "LOW").upper()
    c = t.lower()
    return f'<span class="im-badge {c}"><span class="im-badge-dot"></span>{t}</span>'

def days_remaining(deadline_str):
    if not deadline_str: return None
    from datetime import date
    try:
        dl = date.fromisoformat(str(deadline_str)[:10])
        return (dl - date.today()).days
    except: return None

def deadline_label(deadline_str):
    d = days_remaining(deadline_str)
    if d is None: return "—"
    if d < 0:   return f'<span style="color:var(--critical)">⚠ {abs(d)}d overdue</span>'
    if d == 0:  return f'<span style="color:var(--critical)">⚠ Due today</span>'
    if d <= 7:  return f'<span style="color:var(--high)">{d}d left</span>'
    if d <= 30: return f'<span style="color:var(--medium)">{d}d left</span>'
    return f'<span style="color:var(--text3)">{d}d left</span>'

# ── FETCH ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def fetch_maps():
    try:
        r = requests.get(f"{API}/maps", timeout=8)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            return data.get("maps", []), None
        return data, None
    except Exception as e:
        return [], str(e)

@st.cache_data(ttl=30)
def fetch_stats():
    try:
        r = requests.get(f"{API}/stats", timeout=8)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return {}, str(e)

# ── PAGE ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="im-page-header">
  <div class="im-page-title">MAP Priority Dashboard</div>
  <div class="im-page-sub">CANARA BANK · MANDATORY ACTION POINTS · SORTED BY MPI SCORE</div>
</div>
""", unsafe_allow_html=True)

maps, maps_err = fetch_maps()
stats, stats_err = fetch_stats()

# ── API ERROR BANNER ──────────────────────────────────────────────────────────
if maps_err:
    st.markdown(f"""
    <div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.2);
    border-radius:10px;padding:0.85rem 1.25rem;margin-bottom:1.5rem;
    font-family:var(--font-mono);font-size:0.78rem;color:var(--critical)">
      ⚠ Backend unreachable — {maps_err}
    </div>
    """, unsafe_allow_html=True)

# ── STATS ─────────────────────────────────────────────────────────────────────
total_maps      = stats.get("total_maps", len(maps))
critical_maps   = stats.get("critical_maps", sum(1 for m in maps if isinstance(m, dict) and m.get("priority_tier","").upper() == "CRITICAL"))
total_exposure  = stats.get("total_penalty_exposure", sum(float(m.get("penalty_exposure", 0)) for m in maps if isinstance(m, dict)))
closed_maps     = stats.get("closed_maps", sum(1 for m in maps if isinstance(m, dict) and m.get("status","").upper() == "CLOSED"))

col1, col2, col3, col4 = st.columns(4)
col1.markdown(f"""
<div class="im-metric-card c-accent">
  <span class="im-metric-icon">▦</span>
  <div class="im-metric-value">{total_maps}</div>
  <div class="im-metric-label">Total MAPs</div>
  <div class="im-metric-sub" style="color:var(--text3)">Across all authorities</div>
</div>""", unsafe_allow_html=True)
col2.markdown(f"""
<div class="im-metric-card c-critical">
  <span class="im-metric-icon">⚠</span>
  <div class="im-metric-value" style="color:var(--critical)">{critical_maps}</div>
  <div class="im-metric-label">Critical</div>
  <div class="im-metric-sub" style="color:var(--critical)">Immediate action required</div>
</div>""", unsafe_allow_html=True)
col3.markdown(f"""
<div class="im-metric-card c-high">
  <span class="im-metric-icon">₹</span>
  <div class="im-metric-value">{format_inr(total_exposure)}</div>
  <div class="im-metric-label">Total Exposure</div>
  <div class="im-metric-sub" style="color:var(--text3)">Aggregate penalty risk</div>
</div>""", unsafe_allow_html=True)
col4.markdown(f"""
<div class="im-metric-card c-low">
  <span class="im-metric-icon">✓</span>
  <div class="im-metric-value" style="color:var(--low)">{closed_maps}</div>
  <div class="im-metric-label">Closed</div>
  <div class="im-metric-sub" style="color:var(--low)">Compliance achieved</div>
</div>""", unsafe_allow_html=True)

st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)

# ── FILTERS ───────────────────────────────────────────────────────────────────
with st.expander("⟁  Filters", expanded=False):
    fc1, fc2, fc3, fc4 = st.columns(4)
    tier_filter   = fc1.multiselect("Priority Tier", ["CRITICAL","HIGH","MEDIUM","LOW"], default=["CRITICAL","HIGH","MEDIUM","LOW"])
    status_filter = fc2.multiselect("Status", ["OPEN","IN_PROGRESS","CLOSED"], default=["OPEN","IN_PROGRESS"])
    types_avail   = list({m.get("map_type","") for m in maps if isinstance(m, dict) and m.get("map_type")}) or ["PROCESS_CHANGE","POLICY_UPDATE","SYSTEM_CHANGE","REPORTING_OBLIGATION"]
    type_filter   = fc3.multiselect("MAP Type", types_avail, default=types_avail)
    search_q      = fc4.text_input("Search obligation", placeholder="e.g. KYC, AML...")

# ── FILTER + SORT ─────────────────────────────────────────────────────────────
filtered = [
    m for m in maps
    if isinstance(m, dict)
    and m.get("priority_tier","").upper() in [t.upper() for t in tier_filter]
    and m.get("status","").upper() in [s.upper() for s in status_filter]
    and m.get("map_type","") in type_filter
    and (search_q.lower() in m.get("obligation_text","").lower() if search_q else True)
]
filtered = sorted(filtered, key=lambda x: float(x.get("mpi_score") or 0), reverse=True)

# ── MAP LIST ──────────────────────────────────────────────────────────────────
st.markdown(f'<div class="im-section-title">MAP List <span style="font-size:0.75rem;color:var(--text3);font-family:var(--font-mono);font-weight:400">({len(filtered)} shown)</span></div>', unsafe_allow_html=True)

if not filtered:
    st.markdown("""
    <div class="im-empty">
      <span class="im-empty-icon">▦</span>
      <div class="im-empty-text">No MAPs yet</div>
      <div class="im-empty-sub">Go to Mandates and load demo data to populate</div>
    </div>""", unsafe_allow_html=True)
else:
    for m in filtered:
        map_id   = m.get("id") or m.get("map_id","—")
        tc       = tier_class(m.get("priority_tier","low"))
        ref      = m.get("regulatory_reference","—")
        deadline = m.get("deadline","")
        wing     = m.get("wing_responsible") or m.get("wing","—")
        status   = m.get("status","—")
        mpi      = m.get("mpi_score","—")
        exposure = m.get("penalty_exposure", 0)
        oblig    = m.get("obligation_text","—")
        status_color = {"OPEN":"var(--critical)","IN_PROGRESS":"var(--medium)","CLOSED":"var(--low)"}.get(status.upper(),"var(--text3)")

        st.markdown(f"""
        <div class="im-card {tc}">
          <div class="im-card-left">
            <div class="im-card-id">{map_id} · {ref}</div>
            <div class="im-card-title">{oblig[:90]}{"..." if len(oblig)>90 else ""}</div>
            <div class="im-card-meta">
              <span>🏛 {wing}</span>
              <span>⏱ {deadline_label(deadline)}</span>
              <span style="color:{status_color}">● {status}</span>
            </div>
          </div>
          <div class="im-card-right">
            <div class="im-stat"><div class="im-stat-label">MPI Score</div><div class="im-stat-value">{mpi}</div></div>
            <div class="im-stat"><div class="im-stat-label">Exposure</div><div class="im-stat-value">{format_inr(exposure)}</div></div>
            {badge_html(m.get("priority_tier","LOW"))}
          </div>
        </div>
        """, unsafe_allow_html=True)

        btn_col = st.columns([6, 1])[1]
        if btn_col.button("View →", key=f"dash_view_{map_id}"):
            st.session_state.selected_map = map_id
            st.session_state.page = "MAP Detail"
            st.rerun()

# ── CHART ─────────────────────────────────────────────────────────────────────
if filtered:
    st.markdown('<div class="im-section-title">Top MAPs by Penalty Exposure</div>', unsafe_allow_html=True)
    top10 = sorted(filtered, key=lambda x: float(x.get("penalty_exposure") or 0), reverse=True)[:10]
    color_map = {"CRITICAL":"#f43f5e","HIGH":"#f97316","MEDIUM":"#eab308","LOW":"#22c55e"}
    fig = go.Figure(go.Bar(
        x=[m.get("id") or m.get("map_id","") for m in top10],
        y=[float(m.get("penalty_exposure") or 0) for m in top10],
        marker=dict(color=[color_map.get(m.get("priority_tier","LOW").upper(),"#3b82f6") for m in top10], opacity=0.85, line=dict(width=0)),
        text=[format_inr(m.get("penalty_exposure",0)) for m in top10],
        textposition="outside",
        textfont=dict(family="JetBrains Mono", size=11, color="#8a96a8")
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Instrument Sans", color="#8a96a8", size=12),
        xaxis=dict(showgrid=False, showline=False, tickfont=dict(family="JetBrains Mono", size=11)),
        yaxis=dict(showgrid=True, gridcolor="#1e2530", showline=False, tickprefix="₹", tickfont=dict(family="JetBrains Mono", size=10)),
        margin=dict(l=0, r=0, t=20, b=0), height=300, bargap=0.35
    )
    st.plotly_chart(fig, use_container_width=True)

if st.button("↻  Refresh", key="dash_refresh"):
    st.cache_data.clear()
    st.rerun()
    