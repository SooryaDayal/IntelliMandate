import streamlit as st
import requests
import os
import time

API = os.getenv("BACKEND_URL", "https://larhonda-unlaurelled-bristol.ngrok-free.dev")

# ── HELPERS ──────────────────────────────────────────────────────────────────
def signal_html(signal_type):
    s = (signal_type or "").upper()
    map_ = {
        "MANDATORY_IMMEDIATE": ("sig-mandatory-immediate", "MANDATORY · IMMEDIATE"),
        "MANDATORY_FUTURE":    ("sig-mandatory-future",    "MANDATORY · FUTURE"),
        "CIRCULAR_AMENDMENT":  ("sig-amendment",           "AMENDMENT"),
        "ADVISORY":            ("sig-advisory",            "ADVISORY"),
        "CONSULTATION_PAPER":  ("sig-consultation",        "CONSULTATION"),
    }
    cls, label = map_.get(s, ("sig-advisory", s or "UNKNOWN"))
    return f'<span class="im-signal {cls}">{label}</span>'

def source_badge(source):
    colors = {"RBI":"#3b82f6","SEBI":"#f97316","FIU":"#a78bfa","FIU_IND":"#a78bfa","IRDAI":"#22c55e","MCA":"#eab308"}
    c = colors.get((source or "").upper(), "#8a96a8")
    return f'<span style="background:rgba(255,255,255,0.06);border:1px solid {c}33;color:{c};padding:0.2rem 0.55rem;border-radius:4px;font-family:var(--font-mono);font-size:0.68rem;font-weight:600">{source or "—"}</span>'

# ── FETCH ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=20)
def fetch_history():
    try:
        r = requests.get(f"{API}/scrape/history", timeout=8)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            return data.get("mandates", []), None
        return data, None
    except Exception as e:
        return [], str(e)

def fetch_scrape_status():
    try:
        r = requests.get(f"{API}/scrape/status", timeout=5)
        r.raise_for_status()
        return r.json()
    except:
        return None

# ── PAGE ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="im-page-header">
  <div class="im-page-title">Regulatory Mandates</div>
  <div class="im-page-sub">CANARA BANK · INCOMING CIRCULARS · RBI · SEBI · FIU · IRDAI</div>
</div>
""", unsafe_allow_html=True)

# ── SCRAPE CONTROLS ───────────────────────────────────────────────────────────
st.markdown('<div class="im-section-title">Scrape Controls</div>', unsafe_allow_html=True)

sc1, sc2, sc3 = st.columns([1, 1, 3])

scrape_triggered = False
demo_triggered   = False

if sc1.button("⟳  Trigger Online Scrape", use_container_width=True):
    scrape_triggered = True
if sc2.button("📂  Load Demo Data", use_container_width=True):
    demo_triggered = True

if scrape_triggered:
    try:
        r = requests.post(f"{API}/scrape/rbi?max_circulars=10", timeout=10)
        r.raise_for_status()
        st.markdown("""
        <div style="background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.2);
        border-radius:10px;padding:0.85rem 1.25rem;font-family:var(--font-mono);
        font-size:0.78rem;color:var(--accent)">
          ⟳ Online scrape triggered — polling status below
        </div>""", unsafe_allow_html=True)
        st.session_state["polling"] = True
    except Exception as e:
        st.markdown(f"""
        <div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.2);
        border-radius:10px;padding:0.85rem 1.25rem;font-family:var(--font-mono);
        font-size:0.78rem;color:var(--critical)">
          ⚠ Scrape failed — {e}
        </div>""", unsafe_allow_html=True)

if demo_triggered:
    try:
        r = requests.post(f"{API}/scrape/offline", timeout=10)
        r.raise_for_status()
        st.markdown("""
        <div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);
        border-radius:10px;padding:0.85rem 1.25rem;font-family:var(--font-mono);
        font-size:0.78rem;color:var(--low)">
          ✓ Demo data load triggered — 10 Canara Bank relevant circulars ingesting
        </div>""", unsafe_allow_html=True)
        st.session_state["polling"] = True
    except Exception as e:
        st.markdown(f"""
        <div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.2);
        border-radius:10px;padding:0.85rem 1.25rem;font-family:var(--font-mono);
        font-size:0.78rem;color:var(--critical)">
          ⚠ Demo load failed — {e}
        </div>""", unsafe_allow_html=True)

# ── LIVE STATUS POLLING ───────────────────────────────────────────────────────
if st.session_state.get("polling"):
    st.markdown('<div class="im-section-title">Scrape Status</div>', unsafe_allow_html=True)

    status_placeholder = st.empty()
    poll_count = 0

    while poll_count < 12:
        status = fetch_scrape_status()
        if status:
            found   = status.get("circulars_found", "—")
            stored  = status.get("circulars_stored", "—")
            skipped = status.get("circulars_skipped", "—")
            done    = status.get("status", "") in ("COMPLETE", "DONE", "complete", "done")

            status_placeholder.markdown(f"""
            <div style="background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:1.25rem 1.5rem">
              <div style="display:flex;gap:2.5rem;align-items:center">
                <div>
                  <div class="im-stat-label">Found</div>
                  <div class="im-stat-value">{found}</div>
                </div>
                <div>
                  <div class="im-stat-label">Stored</div>
                  <div class="im-stat-value" style="color:var(--low)">{stored}</div>
                </div>
                <div>
                  <div class="im-stat-label">Skipped</div>
                  <div class="im-stat-value" style="color:var(--text3)">{skipped}</div>
                </div>
                <div style="margin-left:auto;font-family:var(--font-mono);font-size:0.75rem;
                color:{'var(--low)' if done else 'var(--accent)'}">
                  {"✓ COMPLETE" if done else "⟳ PROCESSING..."}
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            if done:
                st.session_state["polling"] = False
                st.cache_data.clear()
                break
        else:
            status_placeholder.markdown("""
            <div style="font-family:var(--font-mono);font-size:0.75rem;color:var(--text3);padding:0.5rem">
              Waiting for status endpoint...
            </div>""", unsafe_allow_html=True)

        time.sleep(5)
        poll_count += 1

# ── MANDATE LIST ──────────────────────────────────────────────────────────────
st.markdown('<div class="im-section-title">Mandate History</div>', unsafe_allow_html=True)

mandates, err = fetch_history()

if err:
    st.markdown(f"""
    <div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.2);
    border-radius:10px;padding:0.85rem 1.25rem;font-family:var(--font-mono);
    font-size:0.78rem;color:var(--critical)">
      ⚠ Could not reach backend — {err}
    </div>""", unsafe_allow_html=True)
elif not mandates:
    st.markdown("""
    <div class="im-empty">
      <span class="im-empty-icon">≡</span>
      <div class="im-empty-text">No mandates yet</div>
      <div class="im-empty-sub">Click "Trigger Online Scrape" or "Load Demo Data" above</div>
    </div>""", unsafe_allow_html=True)
else:
    for m in mandates:
        m_id     = m.get("id") or m.get("mandate_id","—")
        title    = m.get("title","Untitled")
        date_iss = m.get("date_issued") or m.get("created_at","—")
        source   = m.get("source","—")
        sig      = m.get("signal_type","—")
        maps_ext = m.get("maps_extracted") or m.get("map_count", 0)
        processed = m.get("processed", False)

        proc_badge = f'<span style="color:var(--low);font-family:var(--font-mono);font-size:0.68rem">✓ Processed</span>' if processed else f'<span style="color:var(--medium);font-family:var(--font-mono);font-size:0.68rem">⏳ Pending</span>'

        st.markdown(f"""
        <div class="im-mandate-card">
          <div style="flex:1;min-width:0">
            <div class="im-mandate-title">{title}</div>
            <div class="im-mandate-meta">
              <span>📅 {str(date_iss)[:10]}</span>
              <span>{source_badge(source)}</span>
              <span>🆔 {m_id}</span>
              <span>{proc_badge}</span>
            </div>
            <div style="display:flex;gap:0.75rem;align-items:center;margin-top:0.35rem">
              {signal_html(sig)}
            </div>
          </div>
          <div class="im-mandate-right">
            <div class="im-mandate-count">{maps_ext}</div>
            <div class="im-mandate-count-label">MAPs<br>Extracted</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Process button for unprocessed mandates
        if not processed:
            mid_val = m.get("id") or m.get("mandate_id")
            if mid_val:
                btn_cols = st.columns([5, 1])
                if btn_cols[1].button("Process →", key=f"process_{mid_val}"):
                    try:
                        r = requests.post(f"{API}/agents/orchestrate/{mid_val}", timeout=10)
                        r.raise_for_status()
                        st.success(f"Orchestrator triggered for {mid_val}")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

if st.button("↻  Refresh", key="mandates_refresh"):
    st.cache_data.clear()
    st.rerun()
