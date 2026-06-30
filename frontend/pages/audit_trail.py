import streamlit as st
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

def gate_pill(status):
    status = (status or "—").upper()
    color = {"PASSED": "var(--low)", "REVIEW": "var(--medium)", "FAILED": "var(--critical)"}.get(status, "var(--text3)")
    bg = {"PASSED": "var(--low-bg)", "REVIEW": "var(--medium-bg)", "FAILED": "var(--critical-bg)"}.get(status, "rgba(255,255,255,0.04)")
    return f'<span style="background:{bg};color:{color};padding:0.2rem 0.6rem;border-radius:4px;font-family:var(--font-mono);font-size:0.7rem;font-weight:600">{status}</span>'

@st.cache_data(ttl=20)
def fetch_audit():
    try:
        r = requests.get(f"{API}/audit", timeout=8)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            return data.get("audit", data.get("certificates", data.get("records", []))), None
        return data, None
    except Exception as e:
        return [], str(e)

# ── PAGE HEADER ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="im-page-header">
  <div class="im-page-title">Canara Bank Compliance Certificates</div>
  <div class="im-page-sub">CRYPTOGRAPHICALLY SEALED AUDIT RECORDS · CLOSED MAPs</div>
</div>
""", unsafe_allow_html=True)

records, err = fetch_audit()
records = [r for r in records if isinstance(r, dict)]

if err:
    st.markdown(f"""
    <div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.2);
    border-radius:10px;padding:0.85rem 1.25rem;margin-bottom:1.5rem;font-family:var(--font-mono);
    font-size:0.78rem;color:var(--critical)">
      ⚠ Backend unreachable — {err}
    </div>""", unsafe_allow_html=True)

# Sort by closed_at descending
def closed_at_key(r):
    return r.get("closed_at") or r.get("created_at") or ""

records = sorted(records, key=closed_at_key, reverse=True)

# ── SUMMARY ───────────────────────────────────────────────────────────────────
total_closed = len(records)
scores = [float(r.get("semantic_score", 0)) for r in records if r.get("semantic_score") is not None]
avg_score = sum(scores) / len(scores) if scores else 0
total_resolved = sum(float(r.get("penalty_exposure", 0)) for r in records)

wing_counts = {}
for r in records:
    w = r.get("wing_verified_by") or r.get("wing") or "—"
    wing_counts[w] = wing_counts.get(w, 0) + 1
top_wing = max(wing_counts, key=wing_counts.get) if wing_counts else "—"

col1, col2, col3, col4 = st.columns(4)
col1.markdown(f"""
<div class="im-metric-card c-low">
  <span class="im-metric-icon">✓</span>
  <div class="im-metric-value" style="color:var(--low)">{total_closed}</div>
  <div class="im-metric-label">Total Closed MAPs</div>
</div>""", unsafe_allow_html=True)
col2.markdown(f"""
<div class="im-metric-card c-accent">
  <span class="im-metric-icon">◎</span>
  <div class="im-metric-value">{avg_score:.2f}</div>
  <div class="im-metric-label">Avg Semantic Score</div>
</div>""", unsafe_allow_html=True)
col3.markdown(f"""
<div class="im-metric-card c-high">
  <span class="im-metric-icon">₹</span>
  <div class="im-metric-value">{format_inr(total_resolved)}</div>
  <div class="im-metric-label">Exposure Resolved</div>
</div>""", unsafe_allow_html=True)
col4.markdown(f"""
<div class="im-metric-card c-critical">
  <span class="im-metric-icon">🏛</span>
  <div class="im-metric-value" style="font-size:1.1rem;line-height:1.3">{top_wing}</div>
  <div class="im-metric-label">Most Closures</div>
</div>""", unsafe_allow_html=True)

st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)

# ── LIST ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="im-section-title">Closed MAPs</div>', unsafe_allow_html=True)

if not records:
    st.markdown("""
    <div class="im-empty">
      <span class="im-empty-icon">✓</span>
      <div class="im-empty-text">No closed MAPs yet</div>
      <div class="im-empty-sub">Closed MAPs and their certificates will appear here once evidence is validated</div>
    </div>""", unsafe_allow_html=True)
else:
    for r in records:
        map_id   = r.get("map_id", "—")
        oblig    = r.get("obligation_text", "—")
        wing     = r.get("wing_verified_by") or r.get("wing", "—")
        closed_at = (r.get("closed_at") or "—")[:19].replace("T", " ")
        score    = r.get("semantic_score")
        ref      = r.get("regulatory_reference", "—")
        file_hash = r.get("evidence", {}).get("file_hash", "—") if isinstance(r.get("evidence"), dict) else r.get("file_hash", "—")

        st.markdown(f"""
        <div class="im-audit-header">
          <div class="im-audit-check">✓</div>
          <div style="flex:1">
            <div class="im-audit-title">{oblig[:70]}{"..." if len(oblig) > 70 else ""}</div>
            <div class="im-audit-ref">{map_id} · {ref} · 🏛 {wing} · Closed {closed_at}</div>
          </div>
          <div style="text-align:right">
            <div class="im-stat-label">Semantic Score</div>
            <div style="font-family:var(--font-display);font-weight:700;color:var(--low)">{f"{float(score):.2f}" if score is not None else "—"}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("View Compliance Certificate"):
            gate_results = r.get("gate_results", {})
            g1 = gate_results.get("gate_1_deadline", {})
            g2 = gate_results.get("gate_2_integrity", {})
            g3 = gate_results.get("gate_3_temporal", {})
            g4 = gate_results.get("gate_4_semantic", {})

            st.markdown(f"""
            <div class="im-cert">
              <div class="im-cert-row"><span class="im-cert-key">map_id</span><span class="im-cert-val">{map_id}</span></div>
              <div class="im-cert-row"><span class="im-cert-key">regulation_reference</span><span class="im-cert-val">{ref}</span></div>
              <div class="im-cert-row"><span class="im-cert-key">closed_at</span><span class="im-cert-val">{r.get("closed_at","—")}</span></div>
              <div class="im-cert-row"><span class="im-cert-key">evidence_file_hash</span><span class="im-cert-val" style="color:var(--accent)">{file_hash}</span></div>
              <div class="im-cert-row"><span class="im-cert-key">semantic_score</span><span class="im-cert-val" style="color:var(--low)">{score if score is not None else "—"}</span></div>
              <div class="im-cert-row"><span class="im-cert-key">gate_1_deadline</span><span class="im-cert-val">{gate_pill(g1.get("status"))}</span></div>
              <div class="im-cert-row"><span class="im-cert-key">gate_2_integrity</span><span class="im-cert-val">{gate_pill(g2.get("status"))}</span></div>
              <div class="im-cert-row"><span class="im-cert-key">gate_3_temporal</span><span class="im-cert-val">{gate_pill(g3.get("status"))}</span></div>
              <div class="im-cert-row"><span class="im-cert-key">gate_4_semantic</span><span class="im-cert-val">{gate_pill(g4.get("status"))}</span></div>
              <div class="im-cert-row"><span class="im-cert-key">wing_verified_by</span><span class="im-cert-val">{wing}</span></div>
              <div class="im-cert-row"><span class="im-cert-key">validator</span><span class="im-cert-val">{r.get("validator","IntelliMandate v1.0")}</span></div>
              <div class="im-cert-row"><span class="im-cert-key">bank</span><span class="im-cert-val">Canara Bank</span></div>
            </div>
            """, unsafe_allow_html=True)

            for gname, g in [("Gate 1 — Deadline", g1), ("Gate 2 — Integrity", g2), ("Gate 3 — Temporal", g3), ("Gate 4 — Semantic", g4)]:
                if g.get("reason"):
                    st.markdown(f"""
                    <div style="font-size:0.75rem;color:var(--text3);font-family:var(--font-mono);
                    margin-top:0.5rem;padding-left:0.5rem;border-left:2px solid var(--border)">
                      <strong style="color:var(--text2)">{gname}:</strong> {g.get("reason")}
                    </div>""", unsafe_allow_html=True)

if st.button("↻  Refresh", key="audit_refresh"):
    st.cache_data.clear()
    st.rerun()
    