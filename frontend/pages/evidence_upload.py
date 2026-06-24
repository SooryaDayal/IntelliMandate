import streamlit as st
import requests
import os
import time
import hashlib
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

def gate_row(gate_no, gate_name, status, reason):
    if status == "PASSED":
        icon, cls = "✓", "gs-passed"
    elif status == "REVIEW":
        icon, cls = "⚠", "gs-pending"
    elif status == "FAILED":
        icon, cls = "✕", "gs-failed"
    else:
        icon, cls = "⟳", "gs-pending"
    return f"""
    <div class="im-gate">
      <span style="font-family:var(--font-mono);font-size:0.7rem;color:var(--text3);width:3rem">Gate {gate_no}</span>
      <div style="flex:1">
        <div class="im-gate-name">{gate_name}</div>
        <div style="font-size:0.7rem;color:var(--text3);font-family:var(--font-mono);margin-top:2px">{reason}</div>
      </div>
      <span class="im-gate-status {cls}">{icon} {status}</span>
    </div>
    """

# ── PAGE HEADER ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="im-page-header">
  <div class="im-page-title">Evidence Upload</div>
  <div class="im-page-sub">CANARA BANK · SUBMIT COMPLIANCE EVIDENCE · GATE VALIDATION</div>
</div>
""", unsafe_allow_html=True)

maps_list, list_err = fetch_maps_list()
maps_list = [m for m in maps_list if isinstance(m, dict)]
open_maps = [m for m in maps_list if m.get("status", "").upper() != "CLOSED"]
map_ids = [m.get("id") or m.get("map_id", "") for m in open_maps if m.get("id") or m.get("map_id")]

if list_err:
    st.markdown(f"""
    <div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.2);
    border-radius:10px;padding:0.85rem 1.25rem;font-family:var(--font-mono);
    font-size:0.78rem;color:var(--critical)">
      ⚠ Backend unreachable — {list_err}
    </div>""", unsafe_allow_html=True)

if not map_ids:
    st.markdown("""
    <div class="im-empty">
      <span class="im-empty-icon">↑</span>
      <div class="im-empty-text">No open MAPs to submit evidence for</div>
      <div class="im-empty-sub">All MAPs are closed, or none have been created yet</div>
    </div>""", unsafe_allow_html=True)
    st.stop()

# ── MAP SELECTOR ──────────────────────────────────────────────────────────────
preselect = st.session_state.get("selected_map")
default_idx = map_ids.index(preselect) if preselect in map_ids else 0
sel = st.selectbox("Select MAP to submit evidence for", map_ids, index=default_idx)

m, detail_err = fetch_map_detail(sel)
if not m or not isinstance(m, dict):
    m = next((x for x in open_maps if (x.get("id") or x.get("map_id")) == sel), {})

# ── MAP CONTEXT CARD ──────────────────────────────────────────────────────────
wing = m.get("wing_responsible") or m.get("wing", "—")
st.markdown(f"""
<div class="im-card {m.get('priority_tier','low').lower()}" style="margin-top:0.5rem">
  <div class="im-card-left">
    <div class="im-card-id">{sel} · {m.get('regulatory_reference','—')}</div>
    <div class="im-card-title">{m.get('obligation_text','—')}</div>
    <div class="im-card-meta">
      <span>🏛 Wing: {wing}</span>
      <span>⏱ Deadline: {m.get('deadline','—')}</span>
    </div>
  </div>
  <div class="im-card-right">{badge_html(m.get('priority_tier','LOW'))}</div>
</div>
""", unsafe_allow_html=True)

if m.get("measurable_condition"):
    st.markdown('<div class="im-section-title">Measurable Condition — What Proof Must Show</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="im-obligation">{m.get("measurable_condition")}</div>', unsafe_allow_html=True)

if m.get("evidence_required"):
    st.markdown(f"""
    <div class="im-detail-field" style="margin-top:0.75rem">
      <div class="im-detail-field-label">Evidence Required</div>
      <div class="im-detail-field-value">{m.get('evidence_required')}</div>
    </div>""", unsafe_allow_html=True)

# ── UPLOAD ────────────────────────────────────────────────────────────────────
st.markdown('<div class="im-section-title">Submit Evidence</div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Upload proof — PDF, DOCX, TXT, PNG, or JPG",
    type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
    key="evidence_uploader"
)

submit_clicked = st.button("⬆  Submit Evidence", use_container_width=True, type="primary", disabled=not uploaded_file)

if submit_clicked and uploaded_file:
    file_bytes = uploaded_file.getvalue()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Gate 2 — immediate, hash computed at upload
    st.markdown('<div class="im-section-title">Validation Gates</div>', unsafe_allow_html=True)
    gates_placeholder = st.empty()

    rendered_gates = {}

    def render_all():
        html = ""
        for i in [1, 2, 3, 4]:
            if i in rendered_gates:
                html += rendered_gates[i]
            else:
                html += f"""
                <div class="im-gate">
                  <span style="font-family:var(--font-mono);font-size:0.7rem;color:var(--text3);width:3rem">Gate {i}</span>
                  <span class="im-gate-name" style="color:var(--text3)">Pending...</span>
                  <span class="im-gate-status gs-pending">⟳ WAITING</span>
                </div>"""
        gates_placeholder.markdown(html, unsafe_allow_html=True)

    render_all()

    # Show Gate 2 immediately since hash is computed client-side at upload
    rendered_gates[2] = gate_row(2, "Integrity Hash", "PASSED", f"SHA-256: {file_hash[:24]}...")
    render_all()
    time.sleep(0.4)

    evidence_id = None
    try:
        files = {"file": (uploaded_file.name, file_bytes, uploaded_file.type)}
        data = {"file_hash": file_hash}
        resp = requests.post(f"{API}/maps/{sel}/evidence", files=files, data=data, timeout=30)
        resp.raise_for_status()
        evidence_result = resp.json()
        evidence_id = evidence_result.get("evidence_id") or evidence_result.get("id")
    except Exception as e:
        st.markdown(f"""
        <div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.2);
        border-radius:10px;padding:0.85rem 1.25rem;margin-top:1rem;font-family:var(--font-mono);
        font-size:0.78rem;color:var(--critical)">
          ⚠ Evidence upload failed — {e}
        </div>""", unsafe_allow_html=True)
        st.stop()

    # Poll /agents/validate/{evidence_id} every 3 seconds
    final_cert = None
    if evidence_id:
        max_polls = 15
        for poll_i in range(max_polls):
            try:
                vresp = requests.post(f"{API}/agents/validate/{evidence_id}", timeout=15)
                vresp.raise_for_status()
                vdata = vresp.json()
            except Exception:
                try:
                    vresp = requests.get(f"{API}/agents/validate/{evidence_id}", timeout=15)
                    vresp.raise_for_status()
                    vdata = vresp.json()
                except Exception as e:
                    time.sleep(3)
                    continue

            gate_results = vdata.get("gate_results", {})

            g1 = gate_results.get("gate_1_deadline", {})
            if g1:
                rendered_gates[1] = gate_row(1, "Deadline Check", g1.get("status", "PENDING"), g1.get("reason", ""))
                render_all()

            g2 = gate_results.get("gate_2_integrity", {})
            if g2:
                rendered_gates[2] = gate_row(2, "Integrity Hash", g2.get("status", "PASSED"), g2.get("reason", f"SHA-256: {file_hash[:24]}..."))
                render_all()

            g3 = gate_results.get("gate_3_temporal", {})
            if g3:
                rendered_gates[3] = gate_row(3, "Temporal Check", g3.get("status", "PENDING"), g3.get("reason", ""))
                render_all()

            g4 = gate_results.get("gate_4_semantic", {})
            if g4:
                score = g4.get("score")
                score_str = f" (score: {score})" if score is not None else ""
                rendered_gates[4] = gate_row(4, "Semantic Match", g4.get("status", "PENDING"), g4.get("reason", "") + score_str)
                render_all()

            status = vdata.get("status") or vdata.get("map_status")
            if all(k in rendered_gates for k in [1, 2, 3, 4]) or status in ("CLOSED", "REVIEW", "FAILED", "RESUBMIT"):
                final_cert = vdata
                break

            time.sleep(3)

    # ── FINAL RESULT BANNER ───────────────────────────────────────────────────
    if final_cert:
        outcome = (final_cert.get("status") or final_cert.get("map_status") or "").upper()
        g4 = final_cert.get("gate_results", {}).get("gate_4_semantic", {})
        score = g4.get("score")

        if outcome == "CLOSED":
            st.markdown(f"""
            <div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.25);
            border-radius:var(--radius-lg);padding:1.5rem;margin-top:1rem;text-align:center">
              <div style="font-size:1.6rem;margin-bottom:0.5rem">✓</div>
              <div style="font-family:var(--font-display);font-weight:800;color:var(--low);font-size:1.05rem">
                CANARA BANK MAP CLOSED
              </div>
              <div style="font-size:0.8rem;color:var(--text2);margin-top:0.5rem">
                Compliance obligation fulfilled. Certificate generated.
              </div>
            </div>""", unsafe_allow_html=True)
            st.cache_data.clear()
        elif outcome == "REVIEW":
            st.markdown(f"""
            <div style="background:rgba(234,179,8,0.08);border:1px solid rgba(234,179,8,0.25);
            border-radius:var(--radius-lg);padding:1.5rem;margin-top:1rem;text-align:center">
              <div style="font-size:1.6rem;margin-bottom:0.5rem">⚠</div>
              <div style="font-family:var(--font-display);font-weight:800;color:var(--medium);font-size:1.05rem">
                COMPLIANCE WING REVIEW REQUIRED
              </div>
              <div style="font-size:0.8rem;color:var(--text2);margin-top:0.5rem">
                Semantic score {score if score is not None else "—"}. Manual review needed.<br>
                Wing: Compliance Wing to verify evidence.
              </div>
            </div>""", unsafe_allow_html=True)
        else:
            failure_reason = g4.get("reason", "Evidence does not address the compliance requirement.")
            st.markdown(f"""
            <div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.25);
            border-radius:var(--radius-lg);padding:1.5rem;margin-top:1rem;text-align:center">
              <div style="font-size:1.6rem;margin-bottom:0.5rem">✕</div>
              <div style="font-family:var(--font-display);font-weight:800;color:var(--critical);font-size:1.05rem">
                RESUBMISSION REQUIRED
              </div>
              <div style="font-size:0.8rem;color:var(--text2);margin-top:0.5rem">
                Evidence does not prove: {m.get("measurable_condition","the required condition")}<br>
                Guidance: {failure_reason}
              </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:var(--bg2);border:1px solid var(--border);border-radius:10px;
        padding:0.85rem 1.25rem;margin-top:1rem;font-family:var(--font-mono);font-size:0.78rem;color:var(--text3)">
          ⟳ Validation still in progress on the server. Refresh this page in a moment to see the final result.
        </div>""", unsafe_allow_html=True)
        