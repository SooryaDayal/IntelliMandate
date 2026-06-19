import streamlit as st
import plotly.graph_objects as go
import requests
import os
from datetime import date
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

def badge_html(tier):
    t = (tier or "LOW").upper()
    return f'<span class="im-badge {t.lower()}"><span class="im-badge-dot"></span>{t}</span>'

def days_remaining(deadline_str):
    if not deadline_str: return None
    try:
        dl = date.fromisoformat(str(deadline_str)[:10])
        return (dl - date.today()).days
    except: return None

def mpi_gauge(score):
    score = float(score or 0)
    if score >= 80:   color, label = "#f43f5e", "CRITICAL"
    elif score >= 60: color, label = "#f97316", "HIGH"
    elif score >= 40: color, label = "#eab308", "MEDIUM"
    else:             color, label = "#22c55e", "LOW"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        gauge=dict(
            axis=dict(range=[0, 100], tickfont=dict(color="#4a5568", family="JetBrains Mono", size=10)),
            bar=dict(color=color, thickness=0.25),
            bgcolor="#0f1218", borderwidth=0,
            steps=[dict(range=[i*20,(i+1)*20], color="#0f1218") for i in range(5)],
            threshold=dict(line=dict(color=color, width=3), thickness=0.8, value=score)
        ),
        number=dict(font=dict(family="Syne", size=36, color=color)),
        title=dict(text=f"MPI · {label}", font=dict(family="JetBrains Mono", size=11, color="#4a5568"))
    ))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=20,r=20,t=30,b=10), height=200)
    return fig

# ── FETCH ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def fetch_maps_list():
    try:
        r = requests.get(f"{API}/maps", timeout=8)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            return data.get("maps", []), None
        return data, None
    except Exception as e:
        return [], str(e)

def fetch_map_detail(map_id):
    try:
        r = requests.get(f"{API}/maps/{map_id}", timeout=8)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return {}, str(e)

def fetch_assignments(map_id):
    try:
        r = requests.get(f"{API}/maps/{map_id}/assignments", timeout=8)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return [], str(e)

def fetch_graph_impact(mandate_id):
    try:
        r = requests.get(f"{API}/graph/impact/{mandate_id}", timeout=8)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return [], str(e)

# ── PAGE ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="im-page-header">
  <div class="im-page-title">MAP Detail</div>
  <div class="im-page-sub">CANARA BANK · MANDATORY ACTION POINT · FULL VIEW</div>
</div>
""", unsafe_allow_html=True)

maps_list, list_err = fetch_maps_list()
maps_list = [m for m in maps_list if isinstance(m, dict)]
map_ids = [m.get("id") or m.get("map_id","") for m in maps_list if m.get("id") or m.get("map_id")]

if not map_ids:
    st.markdown("""
    <div class="im-empty">
      <span class="im-empty-icon">◎</span>
      <div class="im-empty-text">No MAPs available</div>
      <div class="im-empty-sub">Go to Mandates page and load demo data first</div>
    </div>""", unsafe_allow_html=True)
    st.stop()

current = st.session_state.get("selected_map", map_ids[0])
if current not in map_ids:
    current = map_ids[0]

sel = st.selectbox("Select MAP", map_ids, index=map_ids.index(current))
st.session_state.selected_map = sel

m, detail_err = fetch_map_detail(sel)
if not m or not isinstance(m, dict):
    m = next((x for x in maps_list if (x.get("id") or x.get("map_id")) == sel), {})

assignments, assign_err = fetch_assignments(sel)

if detail_err:
    st.markdown(f"""
    <div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.2);
    border-radius:10px;padding:0.85rem 1.25rem;font-family:var(--font-mono);
    font-size:0.78rem;color:var(--critical);margin-bottom:1rem">
      ⚠ {detail_err} — showing available data
    </div>""", unsafe_allow_html=True)

mpi      = m.get("mpi_score", 0)
tier     = m.get("priority_tier","LOW")
exposure = m.get("penalty_exposure", 0)
deadline = m.get("deadline","")
status   = m.get("status","—")
d_remain = days_remaining(deadline)

left_col, right_col = st.columns([3, 2])

with left_col:
    st.markdown('<div class="im-section-title">Obligation</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="im-obligation">{m.get("obligation_text","—")}</div>', unsafe_allow_html=True)

    if m.get("measurable_condition"):
        st.markdown('<div class="im-section-title" style="margin-top:1rem">Measurable Condition</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background:var(--bg2);border:1px solid var(--border);
        border-left:3px solid var(--medium);border-radius:0 10px 10px 0;
        padding:1rem 1.25rem;font-size:0.875rem;color:var(--text2);line-height:1.6">
          {m.get("measurable_condition")}
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="im-section-title" style="margin-top:1rem">Details</div>', unsafe_allow_html=True)
    d1, d2, d3 = st.columns(3)
    d1.markdown(f'<div class="im-detail-field"><div class="im-detail-field-label">Reference</div><div class="im-detail-field-value" style="font-family:var(--font-mono);font-size:0.78rem">{m.get("regulatory_reference","—")}</div></div>', unsafe_allow_html=True)
    d2.markdown(f'<div class="im-detail-field"><div class="im-detail-field-label">MAP Type</div><div class="im-detail-field-value">{m.get("map_type","—")}</div></div>', unsafe_allow_html=True)
    d3.markdown(f'<div class="im-detail-field"><div class="im-detail-field-label">Authority</div><div class="im-detail-field-value">{m.get("authority") or m.get("source","—")}</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='margin-top:0.75rem'></div>", unsafe_allow_html=True)
    e1, e2, e3 = st.columns(3)
    e1.markdown(f'<div class="im-detail-field"><div class="im-detail-field-label">Deadline</div><div class="im-detail-field-value">{deadline or "—"}</div></div>', unsafe_allow_html=True)
    e2.markdown(f'<div class="im-detail-field"><div class="im-detail-field-label">Days Remaining</div><div class="im-detail-field-value" style="color:{("var(--critical)" if d_remain is not None and d_remain<=7 else "var(--text)")}">{f"{d_remain}d" if d_remain is not None else "—"}</div></div>', unsafe_allow_html=True)
    e3.markdown(f'<div class="im-detail-field"><div class="im-detail-field-label">Status</div><div class="im-detail-field-value">{status}</div></div>', unsafe_allow_html=True)

    if m.get("evidence_required"):
        st.markdown('<div class="im-section-title" style="margin-top:1rem">Evidence Required</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="im-detail-field"><div class="im-detail-field-label">What to submit</div><div class="im-detail-field-value">{m.get("evidence_required")}</div></div>', unsafe_allow_html=True)

with right_col:
    st.markdown('<div class="im-section-title">Priority Index</div>', unsafe_allow_html=True)
    st.plotly_chart(mpi_gauge(mpi), use_container_width=True)

    st.markdown(f"""
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem;margin-top:0.5rem">
      <div class="im-detail-field" style="text-align:center">
        <div class="im-detail-field-label">Penalty Exposure</div>
        <div style="font-family:var(--font-display);font-size:1.4rem;font-weight:800;
        color:var(--critical);margin-top:0.3rem">{format_inr(exposure)}</div>
      </div>
      <div class="im-detail-field" style="text-align:center">
        <div class="im-detail-field-label">Priority</div>
        <div style="margin-top:0.4rem">{badge_html(tier)}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1.25rem'></div>", unsafe_allow_html=True)
    if st.button("↑  Upload Evidence", use_container_width=True, key="go_evidence"):
        st.session_state.page = "Evidence Upload"
        st.rerun()

    mandate_id = m.get("mandate_id") or m.get("source_mandate_id")
    if mandate_id:
        if st.button("◈  View Regulatory Impact", use_container_width=True, key="go_impact"):
            st.session_state["show_impact"] = True
            st.session_state["impact_mandate_id"] = mandate_id
            st.rerun()

st.markdown('<div class="im-section-title">Canara Bank Wing Assignments — Three Lines of Defence</div>', unsafe_allow_html=True)

if assign_err or not assignments or not isinstance(assignments, list):
    wing = m.get("wing_responsible") or m.get("wing","—")
    st.markdown(f"""
    <div class="im-lod-grid">
      <div class="im-lod-card" style="border-top:2px solid var(--accent)">
        <div class="im-lod-label">1st Line of Defence · Business Wing</div>
        <div class="im-lod-dept">{wing}</div>
        <div style="font-size:0.75rem;color:var(--text3);margin-top:0.5rem;font-family:var(--font-mono);line-height:1.5">
          Action required — {(m.get("obligation_text") or "")[:80]}...
        </div>
      </div>
      <div class="im-lod-card" style="border-top:2px solid var(--medium)">
        <div class="im-lod-label">2nd Line of Defence · Control Wing</div>
        <div class="im-lod-dept">Compliance Wing</div>
        <div style="font-size:0.75rem;color:var(--text3);margin-top:0.5rem;font-family:var(--font-mono);line-height:1.5">
          Monitor MAP. MPI: {mpi} ({tier}). Exposure: {format_inr(exposure)}.
        </div>
      </div>
      <div class="im-lod-card" style="border-top:2px solid var(--critical)">
        <div class="im-lod-label">3rd Line of Defence · Audit Wing</div>
        <div class="im-lod-dept">Internal Audit Wing</div>
        <div style="font-size:0.75rem;color:var(--text3);margin-top:0.5rem;font-family:var(--font-mono);line-height:1.5">
          Audit queue entry. Schedule evidence verification post-completion.
        </div>
      </div>
    </div>""", unsafe_allow_html=True)
else:
    lod_colors = ["var(--accent)", "var(--medium)", "var(--critical)"]
    lod_labels = ["1st Line of Defence · Business Wing", "2nd Line of Defence · Control Wing", "3rd Line of Defence · Audit Wing"]
    cols = st.columns(len(assignments))
    for i, (col, asgn) in enumerate(zip(cols, assignments)):
        if not isinstance(asgn, dict): continue
        color     = lod_colors[i] if i < len(lod_colors) else "var(--border2)"
        label     = lod_labels[i] if i < len(lod_labels) else f"Line {i+1}"
        wing_name = asgn.get("wing","—")
        role      = asgn.get("role","—")
        text      = asgn.get("assignment_text","—")
        col.markdown(f"""
        <div class="im-lod-card" style="border-top:2px solid {color};height:100%">
          <div class="im-lod-label">{label}</div>
          <div class="im-lod-dept">{wing_name}</div>
          <div style="font-size:0.7rem;color:var(--text3);margin-top:0.25rem;font-family:var(--font-mono)">{role}</div>
          <div style="font-size:0.75rem;color:var(--text2);margin-top:0.75rem;line-height:1.5;font-family:var(--font-body)">{text[:160]}{"..." if len(text)>160 else ""}</div>
        </div>""", unsafe_allow_html=True)

st.markdown('<div class="im-section-title">MPI Score Breakdown</div>', unsafe_allow_html=True)
if m.get("mpi_breakdown") and isinstance(m["mpi_breakdown"], dict):
    breakdown  = m["mpi_breakdown"]
    components = list(breakdown.keys())
    values     = [float(v) for v in breakdown.values()]
else:
    components = ["Penalty × Likelihood", "Deadline Urgency", "Authority Weight", "Recurrence Risk"]
    score      = float(mpi or 0)
    values     = [score*0.49, score*0.22, score*0.11, score*0.18]

fig2 = go.Figure(go.Bar(
    x=components, y=values,
    marker=dict(color=["#3b82f6","#f97316","#eab308","#a78bfa"], opacity=0.85, line=dict(width=0)),
    text=[f"{v:.1f}" for v in values], textposition="outside",
    textfont=dict(family="JetBrains Mono", size=12, color="#e8edf5")
))
fig2.update_layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Instrument Sans", color="#8a96a8"),
    xaxis=dict(showgrid=False, tickfont=dict(family="JetBrains Mono", size=11)),
    yaxis=dict(showgrid=True, gridcolor="#1e2530", showline=False),
    margin=dict(l=0, r=0, t=20, b=0), height=240, bargap=0.4
)
st.plotly_chart(fig2, use_container_width=True)

if st.session_state.get("show_impact") and st.session_state.get("impact_mandate_id"):
    st.markdown('<div class="im-section-title">Regulatory Impact — Affected MAPs</div>', unsafe_allow_html=True)
    impact, imp_err = fetch_graph_impact(st.session_state["impact_mandate_id"])
    if imp_err:
        st.markdown(f'<div style="font-family:var(--font-mono);font-size:0.78rem;color:var(--text3)">Knowledge graph: {imp_err}</div>', unsafe_allow_html=True)
    elif not impact:
        st.markdown('<div style="font-family:var(--font-mono);font-size:0.78rem;color:var(--text3)">No related MAPs found.</div>', unsafe_allow_html=True)
    else:
        for imp_map in impact:
            if not isinstance(imp_map, dict): continue
            st.markdown(f"""
            <div style="background:var(--bg2);border:1px solid var(--border);border-radius:10px;
            padding:0.85rem 1.25rem;margin-bottom:0.5rem">
              <div style="font-family:var(--font-mono);font-size:0.7rem;color:var(--text3)">{imp_map.get("id","—")} · {imp_map.get("regulatory_reference","—")}</div>
              <div style="font-size:0.875rem;color:var(--text);margin-top:0.3rem">{imp_map.get("obligation_text","—")[:100]}...</div>
            </div>""", unsafe_allow_html=True)
    if st.button("✕ Close", key="close_impact"):
        st.session_state["show_impact"] = False
        st.rerun()
        