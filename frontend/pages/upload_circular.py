import streamlit as st
import requests
import os
import time
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

# ── PAGE HEADER ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="im-page-header">
  <div class="im-page-title">Upload RBI Circular Manually</div>
  <div class="im-page-sub">CANARA BANK · FEED ANY CIRCULAR DIRECTLY INTO INTELLIMANDATE · PDF / DOCX / ZIP</div>
</div>
""", unsafe_allow_html=True)

if "upload_result" not in st.session_state:
    st.session_state.upload_result = None
if "upload_log" not in st.session_state:
    st.session_state.upload_log = []

# ── UPLOAD FORM ────────────────────────────────────────────────────────────────
st.markdown('<div class="im-section-title">Manual Circular Upload</div>', unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])

with col1:
    uploaded_file = st.file_uploader(
        "Drop a circular here — PDF, DOCX, or ZIP of multiple PDFs",
        type=["pdf", "docx", "zip"],
        key="circular_uploader"
    )
    circular_title = st.text_input("Circular Title (optional)", placeholder="e.g. Master Direction on KYC — Amendment 2026")

with col2:
    source_regulator = st.selectbox("Source Regulator", ["RBI", "SEBI", "IRDAI", "FIU_IND", "MCA"])
    st.markdown("<div style='margin-top:1.6rem'></div>", unsafe_allow_html=True)
    process_clicked = st.button("⬆  Upload and Process", use_container_width=True, type="primary")

# ── PROCESSING FLOW ───────────────────────────────────────────────────────────
if process_clicked:
    if not uploaded_file:
        st.markdown("""
        <div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.2);
        border-radius:10px;padding:0.85rem 1.25rem;font-family:var(--font-mono);
        font-size:0.78rem;color:var(--critical)">
          ⚠ Please select a file before processing
        </div>""", unsafe_allow_html=True)
    else:
        st.session_state.upload_log = []
        st.markdown('<div class="im-section-title">Processing</div>', unsafe_allow_html=True)
        step_placeholder = st.empty()
        log_placeholder = st.empty()

        def render_steps(active_step, completed_steps):
            steps = [
                "Extracting text from file",
                "Classifying regulatory signal",
                "Running Agentic Orchestrator",
                "MAPs created and routed to Canara Bank Wings",
            ]
            html = '<div style="display:flex;flex-direction:column;gap:0.5rem;margin-bottom:1rem">'
            for i, s in enumerate(steps, start=1):
                if i in completed_steps:
                    icon, color = "✓", "var(--low)"
                elif i == active_step:
                    icon, color = "⟳", "var(--accent)"
                else:
                    icon, color = "○", "var(--text3)"
                html += f"""
                <div style="display:flex;align-items:center;gap:0.75rem;font-family:var(--font-mono);
                font-size:0.8rem;color:{color}">
                  <span style="width:1.2rem">{icon}</span>
                  <span>Step {i}/4 — {s}</span>
                </div>"""
            html += '</div>'
            step_placeholder.markdown(html, unsafe_allow_html=True)

        def render_log():
            if not st.session_state.upload_log:
                return
            html = '<div style="background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:1rem 1.25rem;font-family:var(--font-mono);font-size:0.78rem;color:var(--text2);line-height:1.8">'
            for line in st.session_state.upload_log:
                html += f"<div>▸ {line}</div>"
            html += '</div>'
            log_placeholder.markdown(html, unsafe_allow_html=True)

        completed = []

        # Step 1
        render_steps(1, completed)
        st.session_state.upload_log.append("Reading file bytes and extracting text via PyMuPDF...")
        render_log()
        time.sleep(0.6)

        try:
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            data = {"title": circular_title or "", "source": source_regulator}

            resp = requests.post(f"{API}/scrape/upload", files=files, data=data, timeout=30)
            resp.raise_for_status()
            result = resp.json()

            completed.append(1)
            st.session_state.upload_log.append(f"Text extracted — {len(uploaded_file.getvalue())} bytes processed")
            render_steps(2, completed)
            render_log()
            time.sleep(0.5)

            signal_type = result.get("signal_type", "UNKNOWN")
            st.session_state.upload_log.append(f"classify_signal_type → {signal_type}")
            completed.append(2)
            render_steps(3, completed)
            render_log()
            time.sleep(0.5)

            mandate_id = result.get("mandate_id") or result.get("id")

            # Trigger orchestrator if not already run server-side
            if mandate_id:
                try:
                    orch_resp = requests.post(f"{API}/agents/orchestrate/{mandate_id}", timeout=30)
                    orch_resp.raise_for_status()
                    orch_result = orch_resp.json()
                except Exception:
                    orch_result = result  # backend may already run orchestrator on upload

                reasoning_log = orch_result.get("reasoning_log", [])
                for entry in reasoning_log:
                    st.session_state.upload_log.append(str(entry))
                    render_log()
                    time.sleep(0.15)

                if not reasoning_log:
                    st.session_state.upload_log.append("Orchestrator run complete — no detailed log returned")
                    render_log()

                completed.append(3)
                render_steps(4, completed)
                time.sleep(0.4)
                completed.append(4)
                render_steps(4, completed)

                st.session_state.upload_result = orch_result
            else:
                completed.append(3)
                completed.append(4)
                render_steps(4, completed)
                st.session_state.upload_result = result

        except requests.exceptions.RequestException as e:
            st.markdown(f"""
            <div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.2);
            border-radius:10px;padding:0.85rem 1.25rem;margin-top:1rem;font-family:var(--font-mono);
            font-size:0.78rem;color:var(--critical)">
              ⚠ Upload failed — {e}
            </div>""", unsafe_allow_html=True)
            st.session_state.upload_result = None

# ── SUMMARY CARD ──────────────────────────────────────────────────────────────
if st.session_state.upload_result:
    r = st.session_state.upload_result
    maps_created   = r.get("maps_created", 0)
    critical_maps  = r.get("critical_maps", 0)
    total_exposure = r.get("total_penalty_exposure", 0)
    wings_assigned = r.get("wings_assigned", [])

    highest_tier = "CRITICAL" if critical_maps else ("HIGH" if maps_created else "—")

    st.markdown('<div class="im-section-title">Summary</div>', unsafe_allow_html=True)

    wings_html = " · ".join(wings_assigned) if wings_assigned else "—"

    st.markdown(f"""
    <div style="background:rgba(34,197,94,0.06);border:1px solid rgba(34,197,94,0.2);
    border-radius:var(--radius-lg);padding:1.5rem;margin-bottom:1rem">
      <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:1rem">
        <span style="font-size:1.3rem">✓</span>
        <span style="font-family:var(--font-display);font-weight:700;color:var(--low);font-size:1rem">
          Processing Complete
        </span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-bottom:1rem">
        <div>
          <div class="im-stat-label">MAPs Created</div>
          <div style="font-family:var(--font-display);font-size:1.6rem;font-weight:800;color:var(--text)">{maps_created}</div>
        </div>
        <div>
          <div class="im-stat-label">Highest Priority</div>
          <div style="margin-top:0.3rem">{badge_html(highest_tier)}</div>
        </div>
        <div>
          <div class="im-stat-label">Total Exposure</div>
          <div style="font-family:var(--font-display);font-size:1.6rem;font-weight:800;color:var(--critical)">{format_inr(total_exposure)}</div>
        </div>
      </div>
      <div style="font-size:0.78rem;color:var(--text3);font-family:var(--font-mono)">
        Wings assigned: {wings_html}
      </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("View MAPs on Dashboard →", key="goto_dashboard", use_container_width=True):
        st.session_state.page = "Dashboard"
        st.session_state.upload_result = None
        st.rerun()

# ── DEMO DATA SECTION ─────────────────────────────────────────────────────────
st.markdown('<div class="im-section-title">Demo Data</div>', unsafe_allow_html=True)

st.markdown("""
<div class="im-upload-box">
  <span class="im-upload-icon">📂</span>
  <div class="im-upload-text">Load 10 pre-downloaded Canara Bank relevant circulars</div>
  <div class="im-upload-sub">KYC · CKYCR · PSL · AML · CIC · BSBDA · IRAC · Interest Rate · CRR/SLR</div>
</div>
""", unsafe_allow_html=True)

demo_col = st.columns([1, 1, 1])[1]
if demo_col.button("📂  Load Demo Data", use_container_width=True, key="load_demo_upload"):
    try:
        r = requests.post(f"{API}/scrape/offline", timeout=15)
        r.raise_for_status()
        st.markdown("""
        <div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);
        border-radius:10px;padding:0.85rem 1.25rem;margin-top:0.75rem;font-family:var(--font-mono);
        font-size:0.78rem;color:var(--low)">
          ✓ Demo data load triggered — 10 Canara Bank circulars ingesting in background.
          Check the Mandates page to track progress.
        </div>""", unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f"""
        <div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.2);
        border-radius:10px;padding:0.85rem 1.25rem;margin-top:0.75rem;font-family:var(--font-mono);
        font-size:0.78rem;color:var(--critical)">
          ⚠ Demo load failed — {e}
        </div>""", unsafe_allow_html=True)