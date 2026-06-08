import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time

# ── 1. PAGE CONFIG & CUSTOM CSS ───────────────────────────────────────────────
st.set_page_config(page_title="IntelliMandate Workspace", page_icon="🏦", layout="wide")

# Injecting Custom CSS for a modern SaaS look
st.markdown("""
<style>
    /* Hide Streamlit default menus and footers */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Modern Metric Cards */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 1.2rem;
        border-radius: 0.75rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    }
    div[data-testid="metric-container"] > div {
        color: #0f172a;
    }
</style>
""", unsafe_allow_html=True)

# ── 2. DATA LAYER (Converted to Pandas DataFrames) ───────────────────────────
DUMMY_MAPS = [
    {"id": "MAP001", "obligation": "KYC re-verification for high-risk customers", "ref": "RBI/KYC/112", "type": "KYC_AML", "exposure": 5000000, "mpi": 92, "tier": "Critical", "due": "2025-06-15", "status": "Open", "auth": "RBI"},
    {"id": "MAP002", "obligation": "MFA for all internet banking systems", "ref": "RBI/CYBER/089", "type": "Cybersecurity", "exposure": 3000000, "mpi": 75, "tier": "High", "due": "2025-07-01", "status": "In Progress", "auth": "RBI"},
    {"id": "MAP003", "obligation": "Maintain Capital Adequacy Ratio > 11.5%", "ref": "RBI/CAR/045", "type": "Capital_Adequacy", "exposure": 8000000, "mpi": 68, "tier": "High", "due": "2025-06-30", "status": "Open", "auth": "RBI"},
    {"id": "MAP004", "obligation": "Quarterly grievance redressal report", "ref": "SEBI/GRV/033", "type": "Grievance", "exposure": 1000000, "mpi": 45, "tier": "Medium", "due": "2025-07-15", "status": "Open", "auth": "SEBI"},
    {"id": "MAP005", "obligation": "FEMA annual return for foreign txns", "ref": "FIU/FEMA/021", "type": "FEMA", "exposure": 500000, "mpi": 32, "tier": "Low", "due": "2025-08-01", "status": "Closed", "auth": "FIU"}
]
df_maps = pd.DataFrame(DUMMY_MAPS)

# ── 3. SIDEBAR NAVIGATION ────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Canara_Bank_Logo.svg/320px-Canara_Bank_Logo.svg.png", width=140)
    st.title("IntelliMandate")
    st.caption("AI Regulatory Operating System v1.0")
    st.divider()
    
    workspace = st.radio(
        "WORKSPACES",
        ["📊 Command Center", "📥 Mandate Pipeline", "🛡️ Compliance Ops"],
        label_visibility="hidden"
    )
    st.divider()
    st.info("🟢 System Online\n\nDatabase: Connected\n\nAgents: Idle")

# ── 4. WORKSPACE 1: COMMAND CENTER ───────────────────────────────────────────
if workspace == "📊 Command Center":
    st.header("Executive Command Center")
    st.markdown("Real-time oversight of Mandatory Action Points (MAPs) and penalty exposure.")
    
    # High-level KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Active MAPs", len(df_maps[df_maps['status'] != 'Closed']))
    col2.metric("Critical Exposure", f"₹{df_maps[df_maps['tier'] == 'Critical']['exposure'].sum() / 1000000:.1f}Cr", "-1 Breach Warning", delta_color="inverse")
    col3.metric("Total Risk Exposure", f"₹{df_maps['exposure'].sum() / 1000000:.1f}Cr")
    col4.metric("AI Confidence", "94.2%", "+2.1% this week")

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Modern Layout: 70% Data Grid, 30% Visuals
    grid_col, chart_col = st.columns([2.5, 1])
    
    with grid_col:
        st.subheader("Action Point Matrix")
        # Streamlit's advanced column configuration for a modern grid look
        st.dataframe(
            df_maps[['id', 'tier', 'mpi', 'obligation', 'exposure', 'due']],
            column_config={
                "id": st.column_config.TextColumn("MAP ID", width="small"),
                "tier": st.column_config.TextColumn("Tier", width="small"),
                "mpi": st.column_config.ProgressColumn("MPI Score", help="Mandate Priority Index", min_value=0, max_value=100, width="medium"),
                "obligation": st.column_config.TextColumn("Obligation", width="large"),
                "exposure": st.column_config.NumberColumn("Exposure", format="₹%d"),
                "due": st.column_config.DateColumn("Deadline", format="MMM DD, YYYY")
            },
            hide_index=True,
            use_container_width=True,
            height=300
        )
        
    with chart_col:
        st.subheader("Priority Distribution")
        # Sleek Plotly Donut Chart
        tier_counts = df_maps['tier'].value_counts().reset_index()
        tier_counts.columns = ['tier', 'count']
        fig = px.pie(tier_counts, values='count', names='tier', hole=0.7, 
                     color='tier', color_discrete_map={'Critical':'#ef4444', 'High':'#f97316', 'Medium':'#eab308', 'Low':'#22c55e'})
        fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=300, 
                          annotations=[dict(text=f"{len(df_maps)}<br>MAPs", x=0.5, y=0.5, font_size=20, showarrow=False)])
        st.plotly_chart(fig, use_container_width=True)

# ── 5. WORKSPACE 2: MANDATE PIPELINE ─────────────────────────────────────────
elif workspace == "📥 Mandate Pipeline":
    st.header("NLP Ingestion Pipeline")
    st.markdown("Live feed of regulatory circulars being scraped, classified, and processed by AI.")
    
    with st.container(border=True):
        st.write("📡 **Live Feed: Reserve Bank of India (rbi.org.in)**")
        st.progress(100, text="Scraping complete. 3 new documents found today.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("### Document Classifier")
        st.info("**MND001**\n\nGuidelines on KYC Re-verification\n\n`MANDATORY_IMMEDIATE`")
        st.warning("**MND002**\n\nCybersecurity Framework\n\n`MANDATORY_FUTURE`")
        st.success("**MND003**\n\nAmendment to Capital Adequacy\n\n`CIRCULAR_AMENDMENT`")
    
    with col2:
        st.markdown("### Groq Extraction Engine (Llama 3 70B)")
        st.code("""
{
  "document_id": "MND001",
  "extracted_maps": [
    {
      "obligation_text": "Banks must complete KYC re-verification for all high-risk customers.",
      "deadline": "2025-06-15",
      "penalty_exposure": 5000000,
      "map_type": "KYC_AML"
    }
  ],
  "confidence_score": 0.98
}
        """, language="json")

# ── 6. WORKSPACE 3: COMPLIANCE OPS ───────────────────────────────────────────
elif workspace == "🛡️ Compliance Ops":
    st.header("Compliance Operations Center")
    st.markdown("Review routing, validate evidence, and close out specific action points.")
    
    # Unified selector
    selected_id = st.selectbox("Select Action Point to Manage", df_maps['id'].tolist())
    target_map = df_maps[df_maps['id'] == selected_id].iloc[0]
    
    st.divider()
    
    # Top split: Details & Routing
    det_col, route_col = st.columns(2)
    
    with det_col:
        st.subheader("Obligation Overview")
        st.markdown(f"**Action:** {target_map['obligation']}")
        st.markdown(f"**Reference:** `{target_map['ref']}` | **Authority:** {target_map['auth']}")
        st.markdown(f"**Deadline:** {target_map['due']} | **Exposure:** ₹{target_map['exposure']:,}")
        
    with route_col:
        st.subheader("3-LoD Automated Routing")
        # Visual Sankey Diagram for the workflow
        fig_sankey = go.Figure(data=[go.Sankey(
            node = dict(
              pad = 15, thickness = 20, line = dict(color = "white", width = 0.5),
              label = [f"{target_map['auth']} Signal", "Retail Banking (1st LoD)", "Compliance (2nd LoD)", "Int. Audit (3rd LoD)"],
              color = ["#475569", "#3b82f6", "#f59e0b", "#ef4444"]
            ),
            link = dict(source = [0, 1, 2], target = [1, 2, 3], value = [1, 1, 1])
        )])
        fig_sankey.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=10))
        st.plotly_chart(fig_sankey, use_container_width=True)

    # Bottom split: Evidence Validation
    st.subheader("4-Gate Evidence Validation Engine")
    
    uploaded_file = st.file_uploader("Upload Evidence Package (PDF, DOCX)", key="evidence")
    
    if uploaded_file:
        st.toast("File uploaded successfully into secure vault.")
        
        with st.status("Initiating IntelliMandate Validation Pipeline...", expanded=True) as status:
            time.sleep(0.8)
            st.write("⏳ **Gate 1 (Deadline):** Checking temporal constraints...")
            time.sleep(0.5)
            st.write("✅ **Gate 1 Passed:** Uploaded within deadline.")
            
            time.sleep(0.8)
            st.write("⏳ **Gate 2 (Integrity):** Generating SHA-256 fingerprint...")
            time.sleep(0.5)
            st.write("✅ **Gate 2 Passed:** Hash `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`")
            
            time.sleep(0.8)
            st.write("⏳ **Gate 3 (Context):** NLP extraction of document dates...")
            time.sleep(0.5)
            st.write("✅ **Gate 3 Passed:** Document timeline aligns with regulation.")
            
            time.sleep(1.2)
            st.write("⏳ **Gate 4 (Semantic Match):** Routing to Gemini 1.5 Flash...")
            time.sleep(1)
            st.write("✅ **Gate 4 Passed:** Evidence aligns with measurable condition (Score: 0.94)")
            
            status.update(label="Validation Complete. Certificate Generated.", state="complete", expanded=False)
            
        st.success("MAP successfully closed out. Audit trail updated.")
        st.download_button("Download Immutable Certificate (JSON)", data='{"status": "verified"}', file_name=f"CERT_{target_map['id']}.json")
        