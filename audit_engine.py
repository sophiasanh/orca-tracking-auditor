import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Issue:
    category: str
    severity: str  # Critical / High / Medium / Low
    issue: str
    recommendation: str
    owner: str
    points_deducted: int


def normalize_df(df: pd.DataFrame, expected_cols: List[str]) -> pd.DataFrame:
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = np.nan
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def load_shopify(file) -> pd.DataFrame:
    expected = ["date", "order_id", "revenue", "source", "utm_source",
                "utm_medium", "utm_campaign", "landing_page"]
    df = pd.read_csv(file)
    return normalize_df(df, expected)


def load_meta(file) -> pd.DataFrame:
    expected = ["date", "campaign_name", "spend", "clicks",
                "purchases", "purchase_value", "final_url"]
    df = pd.read_csv(file)
    return normalize_df(df, expected)


def load_google(file) -> pd.DataFrame:
    expected = ["date", "campaign_name", "spend", "clicks",
                "conversions", "conversion_value", "final_url"]
    df = pd.read_csv(file)
    return normalize_df(df, expected)


def run_audit(shopify: pd.DataFrame, meta: pd.DataFrame, google: pd.DataFrame) -> Dict[str, Any]:
    issues: List[Issue] = []

    # ── 1. Purchase count mismatch: Shopify vs Meta ──────────────────────────
    shopify_fb = shopify[shopify["utm_source"].str.lower().isin(
        ["facebook", "meta", "fb"]) if shopify["utm_source"].notna().any() else [False]*len(shopify)]
    shopify_fb_count = len(shopify_fb)
    meta_purchases = int(meta["purchases"].sum()) if "purchases" in meta.columns else 0

    if meta_purchases > 0 or shopify_fb_count > 0:
        delta = abs(shopify_fb_count - meta_purchases)
        pct = delta / max(meta_purchases, 1) * 100
        if pct > 20:
            issues.append(Issue(
                category="Attribution",
                severity="Critical" if pct > 40 else "High",
                issue=f"Meta reports {meta_purchases} purchases; Shopify attributes {shopify_fb_count} orders to Facebook — a {pct:.0f}% discrepancy.",
                recommendation="Verify Meta pixel is firing on all order confirmation pages. Check deduplication logic between pixel and Conversions API.",
                owner="Marketing / Dev",
                points_deducted=15 if pct > 40 else 10,
            ))

    # ── 2. Conversion mismatch: Shopify vs Google ────────────────────────────
    shopify_google = shopify[shopify["utm_source"].str.lower().isin(
        ["google", "google ads", "adwords"]) if shopify["utm_source"].notna().any() else [False]*len(shopify)]
    shopify_google_count = len(shopify_google)
    google_conversions = int(google["conversions"].sum()) if "conversions" in google.columns else 0

    if google_conversions > 0 or shopify_google_count > 0:
        delta_g = abs(shopify_google_count - google_conversions)
        pct_g = delta_g / max(google_conversions, 1) * 100
        if pct_g > 20:
            issues.append(Issue(
                category="Attribution",
                severity="Critical" if pct_g > 40 else "High",
                issue=f"Google Ads reports {google_conversions} conversions; Shopify attributes {shopify_google_count} orders to Google — a {pct_g:.0f}% gap.",
                recommendation="Audit Google Ads conversion action setup. Ensure the purchase tag fires only once per transaction and uses the correct revenue variable.",
                owner="Marketing / Dev",
                points_deducted=15 if pct_g > 40 else 10,
            ))

    # ── 3. Revenue discrepancy: Meta ─────────────────────────────────────────
    meta_reported_rev = meta["purchase_value"].sum() if "purchase_value" in meta.columns else 0
    shopify_fb_rev = shopify_fb["revenue"].sum() if "revenue" in shopify_fb.columns else 0
    if meta_reported_rev > 0 and shopify_fb_rev > 0:
        rev_pct = abs(meta_reported_rev - shopify_fb_rev) / max(shopify_fb_rev, 1) * 100
        if rev_pct > 15:
            issues.append(Issue(
                category="Revenue Accuracy",
                severity="High",
                issue=f"Meta reports ${meta_reported_rev:,.2f} in purchase value vs ${shopify_fb_rev:,.2f} in Shopify Facebook-attributed revenue ({rev_pct:.0f}% off).",
                recommendation="Confirm the pixel is passing the correct `value` parameter matching Shopify's net revenue. Check for discounts/tax inclusion differences.",
                owner="Marketing / Analytics",
                points_deducted=10,
            ))

    # ── 4. Revenue discrepancy: Google ───────────────────────────────────────
    google_reported_rev = google["conversion_value"].sum() if "conversion_value" in google.columns else 0
    shopify_google_rev = shopify_google["revenue"].sum() if "revenue" in shopify_google.columns else 0
    if google_reported_rev > 0 and shopify_google_rev > 0:
        g_rev_pct = abs(google_reported_rev - shopify_google_rev) / max(shopify_google_rev, 1) * 100
        if g_rev_pct > 15:
            issues.append(Issue(
                category="Revenue Accuracy",
                severity="High",
                issue=f"Google Ads reports ${google_reported_rev:,.2f} in conversion value vs ${shopify_google_rev:,.2f} in Shopify Google-attributed revenue ({g_rev_pct:.0f}% off).",
                recommendation="Review Google Ads conversion value rules. Ensure the tag uses dynamic revenue pulled from order confirmation page.",
                owner="Marketing / Analytics",
                points_deducted=10,
            ))

    # ── 5. Missing UTM parameters ────────────────────────────────────────────
    total_orders = len(shopify)
    missing_utm = shopify[
        shopify["utm_source"].isna() | (shopify["utm_source"].astype(str).str.strip() == "")
    ]
    missing_pct = len(missing_utm) / max(total_orders, 1) * 100
    if missing_pct > 10:
        issues.append(Issue(
            category="UTM Hygiene",
            severity="High" if missing_pct > 25 else "Medium",
            issue=f"{len(missing_utm)} of {total_orders} orders ({missing_pct:.0f}%) have no UTM source — traffic is unattributable.",
            recommendation="Audit all ad platform links and email campaigns to ensure UTM parameters are appended. Use a UTM builder and naming convention doc.",
            owner="Marketing",
            points_deducted=10 if missing_pct > 25 else 5,
        ))

    # ── 6. UTM casing inconsistency ──────────────────────────────────────────
    utm_cols = ["utm_source", "utm_medium", "utm_campaign"]
    casing_issues = []
    for col in utm_cols:
        if col in shopify.columns:
            vals = shopify[col].dropna().astype(str)
            if vals.str.lower().nunique() < vals.nunique():
                casing_issues.append(col)
    if casing_issues:
        issues.append(Issue(
            category="UTM Hygiene",
            severity="Medium",
            issue=f"Mixed casing detected in UTM fields: {', '.join(casing_issues)}. E.g., 'Facebook' and 'facebook' appear as separate sources.",
            recommendation="Standardize all UTM values to lowercase. Update ad platform URL templates and enforce casing rules in a UTM naming convention doc.",
            owner="Marketing",
            points_deducted=5,
        ))

    # ── 7. Campaign naming inconsistency across platforms ───────────────────
    meta_campaigns = set(meta["campaign_name"].dropna().str.lower().str.strip()) if "campaign_name" in meta.columns else set()
    google_campaigns = set(google["campaign_name"].dropna().str.lower().str.strip()) if "campaign_name" in google.columns else set()
    shopify_campaigns = set(shopify["utm_campaign"].dropna().str.lower().str.strip()) if "utm_campaign" in shopify.columns else set()

    all_platform_campaigns = meta_campaigns | google_campaigns
    unmatched = all_platform_campaigns - shopify_campaigns
    if len(unmatched) > 0 and len(all_platform_campaigns) > 0:
        match_pct = (len(all_platform_campaigns) - len(unmatched)) / len(all_platform_campaigns) * 100
        if match_pct < 80:
            issues.append(Issue(
                category="Campaign Naming",
                severity="Medium",
                issue=f"{len(unmatched)} campaign names in Meta/Google don't match Shopify UTM campaigns: {', '.join(list(unmatched)[:3])}{'…' if len(unmatched) > 3 else ''}.",
                recommendation="Align campaign names across all ad platforms and UTM parameters. Create a master campaign naming convention and audit quarterly.",
                owner="Marketing",
                points_deducted=5,
            ))

    # ── 8. High spend, zero conversions (Meta) ───────────────────────────────
    meta_dead = meta[(meta["spend"] > 200) & (meta["purchases"].fillna(0) == 0)]
    if len(meta_dead) > 0:
        wasted = meta_dead["spend"].sum()
        issues.append(Issue(
            category="Spend Efficiency",
            severity="High",
            issue=f"{len(meta_dead)} Meta campaign(s) spent over $200 with zero recorded purchases (total: ${wasted:,.2f}).",
            recommendation="Pause or investigate these campaigns immediately. Verify pixel purchase events are firing. Check audience targeting and landing page conversion rate.",
            owner="Paid Social",
            points_deducted=10,
        ))

    google_dead = google[(google["spend"] > 200) & (google["conversions"].fillna(0) == 0)]
    if len(google_dead) > 0:
        wasted_g = google_dead["spend"].sum()
        issues.append(Issue(
            category="Spend Efficiency",
            severity="High",
            issue=f"{len(google_dead)} Google campaign(s) spent over $200 with zero conversions (total: ${wasted_g:,.2f}).",
            recommendation="Review conversion action status in Google Ads. Confirm tag is active and tracking the correct event. Assess Quality Score and landing page experience.",
            owner="Paid Search",
            points_deducted=10,
        ))

    # ── 9. High click / low conversion anomaly ───────────────────────────────
    meta_anomaly = meta[(meta["clicks"] > 500) & (meta["purchases"].fillna(0) == 0)]
    if len(meta_anomaly) > 0:
        issues.append(Issue(
            category="Conversion Anomaly",
            severity="Medium",
            issue=f"{len(meta_anomaly)} Meta campaign(s) have 500+ clicks with zero purchases — possible tracking failure or severe landing page issue.",
            recommendation="Audit the pixel's purchase event on high-traffic landing pages using Meta Pixel Helper. A/B test landing page copy and CTA.",
            owner="Paid Social / CRO",
            points_deducted=5,
        ))

    google_anomaly = google[(google["clicks"] > 500) & (google["conversions"].fillna(0) == 0)]
    if len(google_anomaly) > 0:
        issues.append(Issue(
            category="Conversion Anomaly",
            severity="Medium",
            issue=f"{len(google_anomaly)} Google campaign(s) have 500+ clicks with zero conversions — potential tag breakage or funnel drop-off.",
            recommendation="Use Google Tag Assistant to verify conversion tag fires on the thank-you page. Review Search Terms report for irrelevant traffic.",
            owner="Paid Search / CRO",
            points_deducted=5,
        ))

    # ── Score calculation ────────────────────────────────────────────────────
    total_deducted = sum(i.points_deducted for i in issues)
    score = max(0, 100 - total_deducted)

    # ── Summary metrics ──────────────────────────────────────────────────────
    summary = {
        "total_shopify_orders": total_orders,
        "total_shopify_revenue": shopify["revenue"].sum() if "revenue" in shopify.columns else 0,
        "total_meta_spend": meta["spend"].sum() if "spend" in meta.columns else 0,
        "total_google_spend": google["spend"].sum() if "spend" in google.columns else 0,
        "total_meta_purchases": meta_purchases,
        "total_google_conversions": google_conversions,
        "missing_utm_pct": missing_pct,
        "meta_roas": (meta["purchase_value"].sum() / max(meta["spend"].sum(), 1)) if "purchase_value" in meta.columns else 0,
        "google_roas": (google["conversion_value"].sum() / max(google["spend"].sum(), 1)) if "conversion_value" in google.columns else 0,
    }

    return {
        "score": score,
        "issues": issues,
        "summary": summary,
        "shopify": shopify,
        "meta": meta,
        "google": google,
    }
