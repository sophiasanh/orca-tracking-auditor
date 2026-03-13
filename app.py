import streamlit as st
import pandas as pd
import anthropic
import os

from audit_engine import load_shopify, load_meta, load_google, run_audit
from prompts import build_executive_summary_prompt, SYSTEM_PROMPT

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Orca Tracking Auditor",
    page_icon="🐋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.main { background-color: #0a0e1a; }
[data-testid="stAppViewContainer"] { background-color: #0a0e1a; }
[data-testid="stSidebar"] { background-color: #0d1120; border-right: 1px solid #1e2640; }

h1, h2, h3, h4 { font-family: 'DM Sans', sans-serif; font-weight: 700; color: #e8ecf4; }
p, li, span, label { color: #9ba3b8; }

.score-ring {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 180px;
    height: 180px;
    border-radius: 50%;
    font-family: 'DM Sans', sans-serif;
    font-weight: 700;
    font-size: 48px;
    margin: 0 auto;
    border: 6px solid;
    position: relative;
}

.score-label {
    font-size: 14px;
    font-weight: 500;
    margin-top: 4px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}

.metric-card {
    background: #111827;
    border: 1px solid #1e2d48;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 12px;
}

.metric-card .metric-val {
    font-size: 32px;
    font-weight: 700;
    color: #e8ecf4;
    font-family: 'DM Mono', monospace;
}

.metric-card .metric-label {
    font-size: 12px;
    color: #5a6480;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 4px;
}

.issue-critical { border-left: 4px solid #ef4444; background: #1a0f0f; }
.issue-high     { border-left: 4px solid #f97316; background: #1a1208; }
.issue-medium   { border-left: 4px solid #eab308; background: #17140a; }
.issue-low      { border-left: 4px solid #22c55e; background: #0a1710; }

.issue-card {
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
}

.issue-title { font-size: 14px; font-weight: 600; color: #e8ecf4; margin-bottom: 6px; }
.issue-rec   { font-size: 13px; color: #7d8699; margin-bottom: 4px; }
.issue-meta  { font-size: 11px; color: #4a5470; }

.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

.badge-critical { background: #3d1515; color: #ef4444; }
.badge-high     { background: #3d2010; color: #f97316; }
.badge-medium   { background: #302910; color: #eab308; }
.badge-low      { background: #0f2d18; color: #22c55e; }

.exec-summary {
    background: linear-gradient(135deg, #0f1729 0%, #111d35 100%);
    border: 1px solid #1e3060;
    border-radius: 14px;
    padding: 28px 32px;
    color: #b8c4da;
    font-size: 15px;
    line-height: 1.75;
}

.section-header {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #3d6bff;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid #1e2640;
}

.upload-zone {
    border: 2px dashed #1e2d48;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    background: #0d1120;
    margin-bottom: 12px;
}

.stButton > button {
    background: linear-gradient(135deg, #3d6bff, #6b3dff);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
    font-family: 'DM Sans', sans-serif;
    font-weight: 600;
    font-size: 14px;
    width: 100%;
    cursor: pointer;
    transition: opacity 0.2s;
}

.stButton > button:hover { opacity: 0.9; }

[data-testid="stFileUploader"] {
    background: #0d1120;
    border: 1px dashed #1e2d48;
    border-radius: 10px;
}

.orca-header {
    background: linear-gradient(135deg, #0a0e1a 0%, #0f1729 100%);
    border-bottom: 1px solid #1e2640;
    padding: 24px 0 20px;
    margin-bottom: 32px;
}

</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex; align-items:center; gap:16px; margin-bottom:8px;">
  <span style="font-size:40px;">🐋</span>
  <div>
    <h1 style="margin:0; font-size:32px; background: linear-gradient(135deg, #3d6bff, #9b6bff); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">Orca Tracking Auditor</h1>
    <p style="margin:0; font-size:14px; color:#3d5070;">Ecommerce Attribution & Tracking Quality Analysis</p>
  </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="section-header">📂 Upload Data Sources</div>', unsafe_allow_html=True)

    shopify_file = st.file_uploader("Shopify Orders CSV", type=["csv"], key="shopify")
    meta_file    = st.file_uploader("Meta Ads CSV", type=["csv"], key="meta")
    google_file  = st.file_uploader("Google Ads CSV", type=["csv"], key="google")

    st.divider()
    st.markdown('<div class="section-header">⚡ Sample Data</div>', unsafe_allow_html=True)

    use_sample = st.button("Load Sample Data")

    st.divider()
    st.markdown('<div class="section-header">🤖 AI Summary</div>', unsafe_allow_html=True)
    api_key = st.text_input("Anthropic API Key (optional)", type="password",
                             placeholder="sk-ant-...")
    st.caption("Leave blank to skip AI executive summary.")

    run_audit_btn = st.button("🔍 Run Audit", type="primary")

    st.divider()
    st.markdown("""
    <div style="font-size:11px; color:#3d5070; line-height:1.6;">
    <b style="color:#5a6490;">Expected columns:</b><br>
    <b>Shopify:</b> date, order_id, revenue, source, utm_source, utm_medium, utm_campaign, landing_page<br><br>
    <b>Meta:</b> date, campaign_name, spend, clicks, purchases, purchase_value, final_url<br><br>
    <b>Google:</b> date, campaign_name, spend, clicks, conversions, conversion_value, final_url
    </div>
    """, unsafe_allow_html=True)


# ── Load sample data ──────────────────────────────────────────────────────────
SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_data")

if use_sample:
    st.session_state["use_sample"] = True

# ── Main Logic ────────────────────────────────────────────────────────────────
def load_files(shopify_f, meta_f, google_f):
    shopify = load_shopify(shopify_f)
    meta    = load_meta(meta_f)
    google  = load_google(google_f)
    return shopify, meta, google


if run_audit_btn or st.session_state.get("use_sample"):
    try:
        if st.session_state.get("use_sample") and not shopify_file:
            shopify_df = load_shopify(os.path.join(SAMPLE_DIR, "shopify_orders.csv"))
            meta_df    = load_meta(os.path.join(SAMPLE_DIR, "meta_ads.csv"))
            google_df  = load_google(os.path.join(SAMPLE_DIR, "google_ads.csv"))
            st.info("📊 Running on sample data. Upload your own CSVs via the sidebar.")
        elif shopify_file and meta_file and google_file:
            shopify_df, meta_df, google_df = load_files(shopify_file, meta_file, google_file)
        else:
            st.warning("⚠️ Please upload all three CSV files or click **Load Sample Data**.")
            st.stop()

        results = run_audit(shopify_df, meta_df, google_df)
        score   = results["score"]
        issues  = results["issues"]
        summary = results["summary"]

        # ── Score color ───────────────────────────────────────────────────────
        if score >= 80:
            score_color = "#22c55e"
            score_label = "Healthy"
        elif score >= 60:
            score_color = "#eab308"
            score_label = "Needs Work"
        else:
            score_color = "#ef4444"
            score_label = "At Risk"

        # ── Layout ────────────────────────────────────────────────────────────
        col_score, col_metrics = st.columns([1, 3])

        with col_score:
            st.markdown(f"""
            <div style="text-align:center; padding:20px 0;">
              <div class="score-ring" style="color:{score_color}; border-color:{score_color}; box-shadow: 0 0 40px {score_color}33;">
                {score}
                <div class="score-label" style="color:{score_color}; font-size:13px;">{score_label}</div>
              </div>
              <p style="margin-top:14px; font-size:12px; color:#3d5070; text-transform:uppercase; letter-spacing:0.1em;">Tracking Health Score</p>
            </div>
            """, unsafe_allow_html=True)

        with col_metrics:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"""<div class="metric-card">
                  <div class="metric-val">{summary['total_shopify_orders']}</div>
                  <div class="metric-label">Shopify Orders</div>
                </div>""", unsafe_allow_html=True)
            with m2:
                st.markdown(f"""<div class="metric-card">
                  <div class="metric-val">${summary['total_shopify_revenue']:,.0f}</div>
                  <div class="metric-label">Total Revenue</div>
                </div>""", unsafe_allow_html=True)
            with m3:
                st.markdown(f"""<div class="metric-card">
                  <div class="metric-val">{summary['meta_roas']:.1f}x</div>
                  <div class="metric-label">Meta ROAS</div>
                </div>""", unsafe_allow_html=True)
            with m4:
                st.markdown(f"""<div class="metric-card">
                  <div class="metric-val">{summary['google_roas']:.1f}x</div>
                  <div class="metric-label">Google ROAS</div>
                </div>""", unsafe_allow_html=True)

            m5, m6, m7, m8 = st.columns(4)
            with m5:
                st.markdown(f"""<div class="metric-card">
                  <div class="metric-val">${summary['total_meta_spend']:,.0f}</div>
                  <div class="metric-label">Meta Spend</div>
                </div>""", unsafe_allow_html=True)
            with m6:
                st.markdown(f"""<div class="metric-card">
                  <div class="metric-val">${summary['total_google_spend']:,.0f}</div>
                  <div class="metric-label">Google Spend</div>
                </div>""", unsafe_allow_html=True)
            with m7:
                st.markdown(f"""<div class="metric-card">
                  <div class="metric-val">{summary['missing_utm_pct']:.0f}%</div>
                  <div class="metric-label">Missing UTMs</div>
                </div>""", unsafe_allow_html=True)
            with m8:
                st.markdown(f"""<div class="metric-card">
                  <div class="metric-val">{len(issues)}</div>
                  <div class="metric-label">Issues Found</div>
                </div>""", unsafe_allow_html=True)

        st.divider()

        # ── Issues ────────────────────────────────────────────────────────────
        col_issues, col_table = st.columns([1, 1])

        with col_issues:
            st.markdown('<div class="section-header">🚨 Issues Detected</div>', unsafe_allow_html=True)

            severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
            sorted_issues  = sorted(issues, key=lambda x: severity_order.get(x.severity, 9))

            if not sorted_issues:
                st.success("✅ No significant tracking issues detected!")
            else:
                for issue in sorted_issues:
                    sev = issue.severity.lower()
                    st.markdown(f"""
                    <div class="issue-card issue-{sev}">
                      <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
                        <span class="badge badge-{sev}">{issue.severity}</span>
                        <span style="font-size:11px; color:#4a5470; font-family:'DM Mono',monospace;">{issue.category}</span>
                        <span style="font-size:11px; color:#ef6b00; margin-left:auto;">−{issue.points_deducted}pts</span>
                      </div>
                      <div class="issue-title">{issue.issue}</div>
                      <div class="issue-rec">💡 {issue.recommendation}</div>
                      <div class="issue-meta">Owner: {issue.owner}</div>
                    </div>
                    """, unsafe_allow_html=True)

        with col_table:
            st.markdown('<div class="section-header">📋 Issue Summary Table</div>', unsafe_allow_html=True)
            if issues:
                table_data = [{
                    "Category":   i.category,
                    "Severity":   i.severity,
                    "Issue":      i.issue[:80] + "…" if len(i.issue) > 80 else i.issue,
                    "Owner":      i.owner,
                    "Pts Deducted": i.points_deducted,
                } for i in sorted_issues]
                df_issues = pd.DataFrame(table_data)
                st.dataframe(df_issues, use_container_width=True, hide_index=True)

                st.markdown(f"""
                <div style="background:#111827; border:1px solid #1e2d48; border-radius:10px; padding:16px 20px; margin-top:12px;">
                  <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:#5a6490; font-size:13px;">Total Points Deducted</span>
                    <span style="color:#ef4444; font-size:24px; font-weight:700; font-family:'DM Mono',monospace;">−{100 - score}</span>
                  </div>
                  <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
                    <span style="color:#5a6490; font-size:13px;">Final Score</span>
                    <span style="color:{score_color}; font-size:24px; font-weight:700; font-family:'DM Mono',monospace;">{score}/100</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.success("No issues — perfect score!")

        st.divider()

        # ── AI Executive Summary ──────────────────────────────────────────────
        st.markdown('<div class="section-header">🤖 AI Executive Summary</div>', unsafe_allow_html=True)

        key_to_use = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

        if key_to_use:
            with st.spinner("Generating executive summary…"):
                try:
                    client = anthropic.Anthropic(api_key=key_to_use)
                    prompt = build_executive_summary_prompt(score, sorted_issues, summary)
                    message = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=800,
                        system=SYSTEM_PROMPT,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    exec_text = message.content[0].text
                    st.markdown(f'<div class="exec-summary">{exec_text.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"AI summary failed: {e}")
        else:
            st.markdown("""
            <div class="exec-summary" style="opacity:0.5; text-align:center; padding:40px;">
              <span style="font-size:32px;">🔑</span><br>
              <span style="color:#3d5070;">Add your Anthropic API key in the sidebar to generate an AI executive summary.</span>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # ── Raw Data Preview ──────────────────────────────────────────────────
        st.markdown('<div class="section-header">🔎 Raw Data Preview</div>', unsafe_allow_html=True)
        tab1, tab2, tab3 = st.tabs(["🛒 Shopify Orders", "📘 Meta Ads", "🔵 Google Ads"])
        with tab1:
            st.dataframe(shopify_df, use_container_width=True, hide_index=True)
        with tab2:
            st.dataframe(meta_df, use_container_width=True, hide_index=True)
        with tab3:
            st.dataframe(google_df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"❌ Audit failed: {e}")
        st.exception(e)

else:
    # ── Welcome screen ────────────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center; padding:60px 20px;">
      <div style="font-size:64px; margin-bottom:20px;">🐋</div>
      <h2 style="color:#e8ecf4; margin-bottom:12px;">Audit your ecommerce tracking in seconds</h2>
      <p style="color:#5a6490; font-size:16px; max-width:500px; margin:0 auto 32px;">
        Upload your Shopify, Meta, and Google Ads exports to detect attribution gaps, UTM issues, spend waste, and conversion discrepancies.
      </p>
      <div style="display:flex; justify-content:center; gap:32px; flex-wrap:wrap; margin-top:32px;">
        <div style="background:#111827; border:1px solid #1e2d48; border-radius:12px; padding:20px 28px; min-width:160px;">
          <div style="font-size:28px; margin-bottom:8px;">📊</div>
          <div style="color:#e8ecf4; font-weight:600; font-size:14px;">Attribution Analysis</div>
          <div style="color:#3d5070; font-size:12px; margin-top:4px;">Cross-platform comparison</div>
        </div>
        <div style="background:#111827; border:1px solid #1e2d48; border-radius:12px; padding:20px 28px; min-width:160px;">
          <div style="font-size:28px; margin-bottom:8px;">🏷️</div>
          <div style="color:#e8ecf4; font-weight:600; font-size:14px;">UTM Hygiene</div>
          <div style="color:#3d5070; font-size:12px; margin-top:4px;">Casing & naming checks</div>
        </div>
        <div style="background:#111827; border:1px solid #1e2d48; border-radius:12px; padding:20px 28px; min-width:160px;">
          <div style="font-size:28px; margin-bottom:8px;">💸</div>
          <div style="color:#e8ecf4; font-weight:600; font-size:14px;">Spend Efficiency</div>
          <div style="color:#3d5070; font-size:12px; margin-top:4px;">Zero-conversion waste alerts</div>
        </div>
        <div style="background:#111827; border:1px solid #1e2d48; border-radius:12px; padding:20px 28px; min-width:160px;">
          <div style="font-size:28px; margin-bottom:8px;">🤖</div>
          <div style="color:#e8ecf4; font-weight:600; font-size:14px;">AI Summary</div>
          <div style="color:#3d5070; font-size:12px; margin-top:4px;">Executive-ready insights</div>
        </div>
      </div>
      <p style="color:#3d5070; font-size:13px; margin-top:48px;">← Upload CSVs in the sidebar or click <b style="color:#3d6bff;">Load Sample Data</b> to see a demo</p>
    </div>
    """, unsafe_allow_html=True)
