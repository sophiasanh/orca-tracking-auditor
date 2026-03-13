def build_executive_summary_prompt(score: int, issues: list, summary: dict) -> str:
    issue_lines = "\n".join(
        f"- [{i.severity}] {i.category}: {i.issue}" for i in issues
    )

    return f"""You are a senior ecommerce analytics consultant reviewing a tracking audit report for a Shopify store running Meta Ads and Google Ads campaigns.

AUDIT DATA:
- Tracking Health Score: {score}/100
- Total Shopify Orders: {summary['total_shopify_orders']}
- Total Revenue (Shopify): ${summary['total_shopify_revenue']:,.2f}
- Meta Spend: ${summary['total_meta_spend']:,.2f} | Meta ROAS: {summary['meta_roas']:.2f}x
- Google Spend: ${summary['total_google_spend']:,.2f} | Google ROAS: {summary['google_roas']:.2f}x
- Missing UTM Coverage: {summary['missing_utm_pct']:.0f}% of orders

ISSUES DETECTED:
{issue_lines if issue_lines else "No significant issues detected."}

Write a concise executive summary (3–4 short paragraphs) for a marketing director audience. Cover:
1. Overall tracking health and what the score means in plain language
2. The 2–3 most urgent issues and their business impact
3. Recommended immediate actions (prioritized)
4. Forward-looking note on how fixing these will improve ROAS visibility

Keep the tone professional but direct. No bullet points — use flowing paragraphs. Do not use markdown headers."""


SYSTEM_PROMPT = """You are an expert ecommerce tracking and analytics consultant. 
You specialize in diagnosing attribution problems, pixel implementation issues, and campaign tracking gaps for DTC brands. 
Your summaries are trusted by CMOs and marketing directors. Be precise, confident, and actionable."""
