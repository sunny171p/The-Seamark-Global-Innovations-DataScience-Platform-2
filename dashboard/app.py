# ==
# app.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# Streamlit dashboard
# ==
#
# WHY THIS EXISTS:
# Everything analytics/ computes today lives in CSVs (batch reports) or
# behind the Flask API (one lookup at a time). Neither is a place to just
# look at the store's health at a glance. This is that place — one screen,
# the real numbers the pipeline already produced, each one labelled with
# exactly what it is and isn't (same honesty rule as api/main.py: the
# forecast is store-wide, not per-product, and it says so on-screen, not
# just in a code comment).
#
# DATA SOURCE:
# Reads from Supabase if SUPABASE_URL / SUPABASE_ANON_KEY are configured
# (see dashboard/README.md), otherwise reads the local CSVs in
# cleaned_data/ and outputs/ directly — see data_loader.py. Either way this
# is a snapshot of the last pipeline run, not a live feed; the sidebar
# says which source is active.
#
# HOW TO RUN:
#   pip install -r dashboard/requirements.txt
#   streamlit run dashboard/app.py
# ==

import pandas as pd
import plotly.express as px
import plotly.io as pio
import plotly.graph_objects as go
import streamlit as st

from data_loader import (
    get_data_source,
    load_affiliate_by_status,
    load_affiliates,
    load_catalog_vs_sales_mix,
    load_external_category_benchmark,
    load_category_by_country,
    load_cluster_terms,
    load_pipeline_health_checks,
    load_products,
    load_snapshot,
    load_stock_check,
)

st.set_page_config(
    page_title="Seamark Analytics",
    page_icon="📦",
    layout="wide",
)

# --- External conversion-rate benchmark (NOT this store's own data) ---------------
# A real, cited, published reference point — not a simulated/generated dataset.
# Littledata's analysis of Shopify stores puts the average Shopify store
# conversion rate at ~1.4%; corroborated independently by a second source
# (Nudgify) citing the same Littledata figure. Checked 2026-09-16. Clearly
# labelled as external throughout the UI so it's never mistaken for a number
# this project computed from Seamark's own data.
EXTERNAL_SHOPIFY_CONVERSION_BENCHMARK_PCT = 1.4
EXTERNAL_SHOPIFY_CONVERSION_BENCHMARK_SOURCE = (
    "Littledata analysis of Shopify stores, ~1.4% average — via "
    "redstagfulfillment.com and nudgify.com (accessed 2026-09-16)"
)

# --- Seamark brand theme (matches the deep green/near-black + gold + teal ---------
# logo, set alongside .streamlit/config.toml, which handles the page's own
# background/text/accent colors). Plotly charts don't pick up Streamlit's
# theme automatically — they default to a white background regardless of the
# page around them — so this registers one shared dark template with the
# brand's actual accent colors and points every px.* chart at it, instead of
# repeating the same colors in each chart's own update_layout() call.
_seamark_template = go.layout.Template()
_seamark_template.layout.paper_bgcolor = "#0f1117"
_seamark_template.layout.plot_bgcolor = "#0f1117"
_seamark_template.layout.font = dict(color="#FAFAFA")
_seamark_template.layout.colorway = ["#00d4aa", "#D4AF37", "#4fe3c1", "#b8952e", "#7fe8ce", "#8c6d1f"]
_seamark_template.layout.xaxis = dict(gridcolor="#2a2f33", zerolinecolor="#2a2f33", linecolor="#2a2f33")
_seamark_template.layout.yaxis = dict(gridcolor="#2a2f33", zerolinecolor="#2a2f33", linecolor="#2a2f33")
_seamark_template.layout.legend = dict(bgcolor="rgba(0,0,0,0)")
pio.templates["seamark_dark"] = _seamark_template
px.defaults.template = "seamark_dark"

# --- Styling for KPI cards, tinted to the brand's teal + gold ---------------------
st.markdown(
    """
    <style>
    div[data-testid="stMetric"] {
        background-color: rgba(0, 212, 170, 0.08);
        border: 1px solid rgba(212, 175, 55, 0.28);
        border-radius: 10px;
        padding: 14px 16px 10px 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Company name banner, centered, matching the brand's gold serif logo type ----
st.markdown(
    """
    <h1 style='text-align: center; color: #D4AF37; font-family: Georgia, "Times New Roman", serif;
               letter-spacing: 2px; margin-bottom: 0; font-size: 2.1rem;'>
        THE SEAMARK GLOBAL INNOVATIONS LIMITED
    </h1>
    <p style='text-align: center; color: #7fe8ce; margin-top: 4px; letter-spacing: 3px;
              font-size: 0.85rem; text-transform: uppercase;'>
        Seamark Global Innovations Analytics Project
    </p>
    """,
    unsafe_allow_html=True,
)

# --- Load data --------------------------------------------------------------------
products = load_products()
funnel = load_snapshot("funnel_summary", "funnel_summary.csv")
forecast = load_snapshot("forecast_summary", "forecast_vs_actual_summary.csv")
omnichannel = load_snapshot("omnichannel_summary", "omnichannel_visibility_summary.csv")
pricing_summary = load_snapshot("pricing_integrity_summary", "pricing_integrity_summary.csv")
affiliate_summary = load_snapshot("affiliate_summary", "affiliate_summary.csv")
affiliate_by_status = load_affiliate_by_status()
affiliates = load_affiliates()
pipeline_health = load_snapshot("pipeline_health_summary", "pipeline_health_summary.csv")
pipeline_health_checks = load_pipeline_health_checks()
cluster_terms = load_cluster_terms()
category_by_country = load_category_by_country()
catalog_vs_sales_mix = load_catalog_vs_sales_mix()
external_category_benchmark = load_external_category_benchmark()
stock_check = load_stock_check()

# --- Sidebar ------------------------------------------------------------------
with st.sidebar:
    st.title("📦 Seamark — Project 2")
    st.caption("Post-launch analytics, real data only.")
    source = get_data_source()
    if source == "supabase":
        st.success("Data source: Supabase")
    else:
        st.info("Data source: local CSVs (cleaned_data/ + outputs/)")
    st.caption(
        "Snapshot of the last `python pipeline.py` run. "
        "To refresh with live Shopify data first, run "
        "`shopify_sync/refresh_raw_data.py`, then re-run the pipeline "
        "(and `supabase/sync_to_supabase.py` if using Supabase) — "
        "nothing here auto-updates."
    )
    st.divider()
    if pipeline_health:
        status = pipeline_health.get("overall_status")
        checks_line = f"{int(pipeline_health.get('checks_passed', 0))}/{int(pipeline_health.get('checks_total', 0))} checks passed"
        if status == "HEALTHY":
            st.success(f"Pipeline health: {status}\n\n{checks_line}")
        else:
            st.error(f"Pipeline health: {status}\n\n{checks_line} — see Pipeline Health section")
    else:
        st.warning("Pipeline health: unknown — run 08_pipeline_health.py")
    st.divider()
    section = st.radio(
        "Section",
        ["Overview", "Products & Pricing", "Funnel & Checkout", "Omnichannel", "Affiliates", "AI Forecast", "Pipeline Health", "Stock Alerts"],
    )

# --- Header KPI row (shown on every section, like the reference dashboard) -------
misleading_count = int(pricing_summary.get("misleading_discount_count", 0) or 0)
anomaly_count = int(pricing_summary.get("margin_anomaly_count", 0) or 0)
pricing_issues = misleading_count + anomaly_count

checkout_rate = funnel.get("adjusted_conversion_rate_pct")
active_affiliate_count = int(affiliate_summary.get("active_count", 0) or 0)
total_affiliate_count = int(affiliate_summary.get("total_signups", len(affiliates) if not affiliates.empty else 0) or 0)
forecast_error_pct = forecast.get("error_pct")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Products tracked", f"{len(products):,}" if not products.empty else "—")
k2.metric("Pricing / margin issues", f"{pricing_issues}", help="Misleading discounts + margin anomalies, from 05_pricing_integrity.py")
k3.metric(
    "Checkout rate (bot-adjusted)",
    f"{checkout_rate:.2f}%" if checkout_rate is not None else "—",
    help="Orders ÷ sessions after removing likely-bot sessions (03_funnel_analysis.py)",
)
k4.metric(
    "Active affiliates (UpPromote)",
    f"{active_affiliate_count}",
    help=f"{total_affiliate_count} total signups — see the Affiliates tab. Programme status only, not sales attribution.",
)
k5.metric(
    "AI forecast error (store-wide)",
    f"{forecast_error_pct:.0f}%" if forecast_error_pct is not None else "—",
    help="Store-wide Prophet forecast vs actual revenue, NOT a per-product prediction — see the AI Forecast tab.",
)

st.divider()

# ==================================================================================
# OVERVIEW
# ==================================================================================
if section == "Overview":
    st.subheader("Overview")

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("**Products by category**")
        if not products.empty and "auto_category" in products.columns:
            counts = products["auto_category"].value_counts().reset_index()
            counts.columns = ["Category", "Products"]
            fig = px.bar(counts, x="Products", y="Category", orientation="h")
            fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(categoryorder="total ascending"))
            st.plotly_chart(fig, width='stretch')
            # One-line pointer to the external benchmark, not a duplicate chart —
            # Overview stays a glance page, and the Olist comparison stays clearly
            # a reference point rather than looking like one of Seamark's own KPIs.
            # Numbers are read live from the real output file, never hardcoded.
            if not external_category_benchmark.empty:
                _top = external_category_benchmark.loc[external_category_benchmark["seamark_real_sales_pct"].idxmax()]
                st.caption(
                    f"External reference: **{_top['auto_category']}** is {_top['seamark_real_sales_pct']:.1f}% of "
                    f"Seamark Global Innovations' real sales but only {_top['external_olist_revenue_pct']:.1f}% of "
                    f"the real order mix in the external Olist marketplace dataset (99,441 real orders, "
                    f"2016–2018) — a reminder of how concentrated a 7-order store's mix naturally looks next to a "
                    f"much larger, unrelated business. Full comparison under Products & Pricing."
                )
        else:
            st.info("No product data available.")

    with col2:
        st.markdown("**Pricing integrity**")
        if pricing_summary:
            breakdown = pd.DataFrame({
                "Status": ["Verified real discount", "Misleading discount", "No discount"],
                "Count": [
                    pricing_summary.get("verified_real_discount_count", 0),
                    pricing_summary.get("misleading_discount_count", 0),
                    pricing_summary.get("no_discount_count", 0),
                ],
            })
            fig = px.pie(breakdown, names="Status", values="Count", hole=0.55)
            fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width='stretch')
            st.caption(
                f"Integrity score: **{pricing_summary.get('integrity_score_pct', 0):.1f}%** · "
                f"{int(pricing_summary.get('margin_anomaly_count', 0))} margin anomalies "
                f"(IQR method, {pricing_summary.get('margin_anomaly_threshold_pct', 0):.1f}% threshold)."
            )
        else:
            st.info("No pricing integrity summary available — run 05_pricing_integrity.py.")

    st.markdown("**Funnel snapshot**")
    if funnel:
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Visitors", f"{int(funnel.get('total_visitors', 0)):,}")
        f2.metric("Sessions", f"{int(funnel.get('total_sessions', 0)):,}")
        f3.metric("Real orders", f"{int(funnel.get('total_orders', 0)):,}")
        f4.metric("AOV", f"£{funnel.get('aov_gbp', 0):.2f}")
        st.caption(
            f"{funnel.get('likely_bot_pct', 0):.1f}% of sessions flagged as likely bot traffic and excluded from "
            f"the adjusted conversion rate above ({int(funnel.get('likely_bot_sessions', 0))} of "
            f"{int(funnel.get('total_sessions', 0))} sessions)."
        )
    else:
        st.info("No funnel summary available — run 03_funnel_analysis.py.")

# ==================================================================================
# PRODUCTS & PRICING
# ==================================================================================
elif section == "Products & Pricing":
    st.subheader("Products & Pricing Integrity")

    if products.empty:
        st.info("No product data available — run pipeline.py to generate cleaned_data/products_clean.csv.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            categories = ["All"] + sorted(products["auto_category"].dropna().unique().tolist())
            pick_cat = st.selectbox("Category", categories)
        with c2:
            statuses = ["All"] + sorted(products["pricing_status"].dropna().unique().tolist()) if "pricing_status" in products else ["All"]
            pick_status = st.selectbox("Pricing status", statuses)
        with c3:
            anomaly_only = st.checkbox("Margin anomalies only")

        filtered = products.copy()
        if pick_cat != "All":
            filtered = filtered[filtered["auto_category"] == pick_cat]
        if pick_status != "All" and "pricing_status" in filtered:
            filtered = filtered[filtered["pricing_status"] == pick_status]
        if anomaly_only and "margin_anomaly" in filtered:
            filtered = filtered[filtered["margin_anomaly"] == True]  # noqa: E712

        st.caption(f"Showing {len(filtered):,} of {len(products):,} products")
        st.dataframe(
            filtered[[c for c in [
                "handle", "title", "auto_category", "shipping_destination",
                "variant_price", "margin_pct", "pricing_status", "margin_anomaly",
            ] if c in filtered.columns]],
            width='stretch',
            height=420,
        )

        st.markdown("**Text clusters (TF-IDF / K-Means over Title + Type + Tags)**")
        if not cluster_terms.empty:
            st.dataframe(cluster_terms, width='stretch', hide_index=True)
        else:
            st.info("No cluster data available — run 02_product_classification.py.")

        st.markdown("**Category by shipping destination**")
        if not category_by_country.empty:
            fig = px.bar(
                category_by_country, x="auto_category", y="product_count", color="country", barmode="stack"
            )
            fig.update_layout(height=420, xaxis_title="", yaxis_title="Products", legend_title="Destination")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No category-by-country breakdown available.")

        st.markdown("**Margin % distribution**")
        if "margin_pct" in filtered.columns and filtered["margin_pct"].notna().any():
            fig = px.histogram(filtered, x="margin_pct", nbins=20)
            fig.update_layout(
                height=360, xaxis_title="Margin %", yaxis_title="Products",
                bargap=0.05, showlegend=False,
            )
            _anomaly_threshold = pricing_summary.get("margin_anomaly_threshold_pct")
            if _anomaly_threshold is not None and not pd.isna(_anomaly_threshold):
                fig.add_vline(
                    x=_anomaly_threshold, line_dash="dash", line_color="#e05a5a",
                    annotation_text=f"Anomaly threshold ({_anomaly_threshold:.1f}%)",
                    annotation_position="top right", annotation_font_color="#e05a5a",
                )
            st.plotly_chart(fig, width='stretch')
            st.caption(
                "Dashed line = the IQR-based low-margin anomaly threshold from 05_pricing_integrity.py "
                "(same figure as the margin anomaly count above). This reflects the current category/status "
                "filters above."
            )
        else:
            st.info("No margin data available for the current filter.")

        st.markdown("**Catalogue mix vs real sales mix**")
        if not catalog_vs_sales_mix.empty:
            _mix = catalog_vs_sales_mix.rename(columns={
                "auto_category": "Category", "catalog_pct": "Catalogue (% of products)",
                "real_sales_pct": "Real sales (% of revenue)",
            })
            _mix_long = _mix.melt(
                id_vars="Category",
                value_vars=["Catalogue (% of products)", "Real sales (% of revenue)"],
                var_name="Mix", value_name="Percent",
            )
            fig = px.bar(_mix_long, x="Category", y="Percent", color="Mix", barmode="group")
            fig.update_layout(height=420, xaxis_title="", yaxis_title="% of total", legend_title="")
            st.plotly_chart(fig, width='stretch')
            _biggest = (_mix["Real sales (% of revenue)"] - _mix["Catalogue (% of products)"]).abs().idxmax()
            _row = _mix.loc[_biggest]
            st.caption(
                f"Both sides are real data — no simulated orders used. Catalogue mix = share of this store's "
                f"275 real products per category; sales mix = share of real order revenue per category, from "
                f"all 11 real line items across the 7 real orders (matched to a real product by SKU or exact "
                f"title — see analytics/09_catalog_vs_sales_mix.py). Biggest gap right now: "
                f"**{_row['Category']}** is {_row['Catalogue (% of products)']:.1f}% of the catalogue but "
                f"{_row['Real sales (% of revenue)']:.1f}% of real sales revenue. With only 11 line items total, "
                "this is a real pattern worth watching, not yet a stable trend."
            )
        else:
            st.info("No catalogue-vs-sales comparison available — run 09_catalog_vs_sales_mix.py.")

        st.markdown("**Real sales mix vs an external real dataset (Olist, 2016–2018 Brazil)**")
        if not external_category_benchmark.empty:
            _ext = external_category_benchmark.rename(columns={
                "auto_category": "Category", "seamark_real_sales_pct": "Seamark (% of real sales)",
                "external_olist_revenue_pct": "External — Olist (% of real orders)",
            })
            _ext_long = _ext.melt(
                id_vars="Category",
                value_vars=["Seamark (% of real sales)", "External — Olist (% of real orders)"],
                var_name="Mix", value_name="Percent",
            )
            fig = px.bar(_ext_long, x="Category", y="Percent", color="Mix", barmode="group")
            fig.update_layout(height=420, xaxis_title="", yaxis_title="% of total", legend_title="")
            st.plotly_chart(fig, width='stretch')
            st.caption(
                "Both sides are real, unrelated businesses — this is an external reference point, not a "
                "prediction or a target. Olist is a real Brazilian e-commerce marketplace: 99,441 real orders "
                "(96,478 delivered), Sep 2016–Oct 2018, mapped conservatively onto Seamark's 14 categories "
                "(see analytics/10_external_category_benchmark.py for the full mapping and why it's "
                "deliberately conservative — an unmatched Olist category falls into 'Other' rather than being "
                "force-fit). Seamark's own real sales mix is the same 11-line-item figure shown above, so "
                "read this as directional on both sides, not conclusive."
            )
        else:
            st.info("No external category benchmark available — run 10_external_category_benchmark.py.")

# ==================================================================================
# FUNNEL & CHECKOUT
# ==================================================================================
elif section == "Funnel & Checkout":
    st.subheader("Funnel & Checkout")

    if not funnel:
        st.info("No funnel summary available — run 03_funnel_analysis.py.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Raw conversion rate", f"{funnel.get('conversion_rate_pct', 0):.3f}%")
            st.metric("Adjusted conversion rate (bots removed)", f"{funnel.get('adjusted_conversion_rate_pct', 0):.3f}%")
            st.metric("Likely-bot sessions", f"{int(funnel.get('likely_bot_sessions', 0))} ({funnel.get('likely_bot_pct', 0):.1f}%)")
        with c2:
            st.metric("Average order value", f"£{funnel.get('aov_gbp', 0):.2f}")
            st.metric("Payment gateway variance found", "Yes" if funnel.get("gateway_variance_found") else "No")
            st.metric("Channel variance found", "Yes" if funnel.get("channel_variance_found") else "No")

        # Two charts built from the same real funnel numbers already shown
        # above as tiles — no new figures introduced, just a visual view of
        # the same data.
        d1, d2 = st.columns(2)
        with d1:
            st.markdown("**Sessions: bot vs genuine**")
            _total_sessions = int(funnel.get("total_sessions", 0))
            _bot_sessions = int(funnel.get("likely_bot_sessions", 0))
            _genuine_sessions = max(_total_sessions - _bot_sessions, 0)
            session_split = pd.DataFrame({
                "Type": ["Genuine sessions", "Likely-bot sessions"],
                "Sessions": [_genuine_sessions, _bot_sessions],
            })
            fig = px.pie(session_split, names="Type", values="Sessions", hole=0.55)
            fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width='stretch')

        with d2:
            st.markdown("**Conversion rate: raw vs bot-adjusted**")
            conv_compare = pd.DataFrame({
                "Metric": ["Raw", "Adjusted (bots removed)"],
                "Conversion rate (%)": [
                    funnel.get("conversion_rate_pct", 0),
                    funnel.get("adjusted_conversion_rate_pct", 0),
                ],
            })
            fig = px.bar(conv_compare, x="Metric", y="Conversion rate (%)", text="Conversion rate (%)")
            fig.update_traces(texttemplate="%{text:.3f}%", textposition="outside")
            fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="")
            st.plotly_chart(fig, width='stretch')

        st.markdown("**Conversion benchmarking**")
        _adjusted_rate = funnel.get("adjusted_conversion_rate_pct")
        if _adjusted_rate is not None and not pd.isna(_adjusted_rate):
            _gap_pp = round(_adjusted_rate - EXTERNAL_SHOPIFY_CONVERSION_BENCHMARK_PCT, 2)
            _status = "above" if _gap_pp > 0 else ("below" if _gap_pp < 0 else "in line with")
            b1, b2, b3 = st.columns(3)
            b1.metric("This store (bot-adjusted)", f"{_adjusted_rate:.2f}%")
            b2.metric(
                "External benchmark",
                f"{EXTERNAL_SHOPIFY_CONVERSION_BENCHMARK_PCT:.1f}%",
                help=EXTERNAL_SHOPIFY_CONVERSION_BENCHMARK_SOURCE,
            )
            b3.metric("Gap", f"{_gap_pp:+.2f}pp", help=f"This store is {_status} the external benchmark.")
            st.caption(
                f"Benchmark source: {EXTERNAL_SHOPIFY_CONVERSION_BENCHMARK_SOURCE} — an external reference "
                "point, not this store's own data. This store's own figure is based on 7 real orders, a very "
                "small sample, so treat the comparison as context, not a statistically robust claim."
            )
        else:
            st.info("Not enough data yet to benchmark the conversion rate.")

        st.markdown("**+5% conversion, what-if scenario**")
        st.caption(
            "A labelled hypothetical built on this store's own real AOV and adjusted conversion "
            "rate — not a prediction, and not based on any observed friction point (all 7 real "
            "orders used the same payment gateway and channel, so no gateway/channel variance "
            "exists in this data)."
        )
        s1, s2, s3 = st.columns(3)
        s1.metric("Scenario lift", f"{funnel.get('scenario_lift_pct', 0):.1f}%")
        s2.metric("Additional orders", f"{funnel.get('scenario_additional_orders', 0):.2f}")
        s3.metric("Additional revenue", f"£{funnel.get('scenario_additional_revenue_gbp', 0):.2f}")

# ==================================================================================
# OMNICHANNEL
# ==================================================================================
elif section == "Omnichannel":
    st.subheader("Omnichannel Visibility — Website vs Google Shopping")

    if not omnichannel:
        st.info("No omnichannel summary available — run 06_omnichannel_visibility.py.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Website** ({omnichannel.get('website_window', 'n/a')})")
            st.metric("Sessions", f"{int(omnichannel.get('website_sessions', 0)):,}")
            st.metric("Orders", f"{int(omnichannel.get('website_orders', 0)):,}")
            st.metric("Conversion rate", f"{omnichannel.get('website_conversion_rate_pct', 0):.3f}%")
        with c2:
            st.markdown(f"**Google Shopping** ({omnichannel.get('google_shopping_window', 'n/a')})")
            st.metric("Clicks", f"{int(omnichannel.get('google_shopping_clicks', 0)):,}")
            st.metric("Purchases", f"{int(omnichannel.get('google_shopping_purchases', 0)):,}")
        st.caption(f"Source note: {omnichannel.get('data_source_note', '')}")

        # Same numbers as the tiles above, just visualized — this is the
        # section's own headline comparison (website vs Google Shopping),
        # split into two charts because traffic and sales sit on very
        # different scales (695 sessions vs 7 orders) — cramming both onto
        # one linear-scale chart would make the sales bars invisible next to
        # the traffic bars.
        d1, d2 = st.columns(2)
        with d1:
            st.markdown("**Traffic by channel**")
            traffic_compare = pd.DataFrame({
                "Channel": ["Website", "Google Shopping"],
                "Sessions / Clicks": [
                    int(omnichannel.get("website_sessions", 0)),
                    int(omnichannel.get("google_shopping_clicks", 0)),
                ],
            })
            fig = px.bar(traffic_compare, x="Channel", y="Sessions / Clicks", text="Sessions / Clicks")
            fig.update_traces(textposition="outside")
            fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width='stretch')

        with d2:
            st.markdown("**Sales by channel**")
            sales_compare = pd.DataFrame({
                "Channel": ["Website", "Google Shopping"],
                "Orders / Purchases": [
                    int(omnichannel.get("website_orders", 0)),
                    int(omnichannel.get("google_shopping_purchases", 0)),
                ],
            })
            fig = px.bar(sales_compare, x="Channel", y="Orders / Purchases", text="Orders / Purchases")
            fig.update_traces(textposition="outside")
            fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width='stretch')

        # Actual money made per channel, not just order counts. There's no
        # separately-tracked "revenue by channel" field in this summary, so
        # this is derived from numbers already shown elsewhere on this page
        # and the Overview: website revenue = real orders × this store's own
        # verified average order value (funnel_summary.csv's aov_gbp — the
        # same AOV already shown in the Funnel & Checkout tab, not a new
        # figure). Google Shopping's revenue isn't estimated at all — with
        # 0 purchases recorded, £0 follows directly, no assumption needed.
        st.markdown("**Revenue by channel**")
        _website_revenue = omnichannel.get("website_orders", 0) * funnel.get("aov_gbp", 0)
        _gs_purchases = omnichannel.get("google_shopping_purchases", 0)
        _gs_revenue = _gs_purchases * funnel.get("aov_gbp", 0) if _gs_purchases else 0
        revenue_compare = pd.DataFrame({
            "Channel": ["Website", "Google Shopping"],
            "Revenue (£)": [round(_website_revenue, 2), round(_gs_revenue, 2)],
        })
        fig = px.bar(revenue_compare, x="Channel", y="Revenue (£)", text="Revenue (£)")
        fig.update_traces(texttemplate="£%{text:.2f}", textposition="outside")
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width='stretch')
        st.caption(
            f"Website revenue = {int(omnichannel.get('website_orders', 0))} real orders × this store's own "
            f"average order value (£{funnel.get('aov_gbp', 0):.2f}, from the Funnel & Checkout tab) — not a "
            "separately-tracked figure. Google Shopping shows £0 because Merchant Center recorded 0 purchases "
            "for it, not because of an assumption."
        )

# ==================================================================================
# AFFILIATES
# ==================================================================================
elif section == "Affiliates":
    st.subheader("Affiliate Programme (UpPromote)")

    if not affiliate_summary:
        st.info("No affiliate summary available — run 07_affiliate_analysis.py.")
    else:
        st.warning(
            "Known gap (see DATA_PROVENANCE.md): UpPromote lists who has signed up as an "
            "affiliate, not which — if any — of the store's real orders were attributed to one. "
            "This section shows programme signups and engagement, not attributed sales.\n\n"
            f"{affiliate_summary.get('attribution_gap_note', '')}"
        )
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Total signups", f"{int(affiliate_summary.get('total_signups', 0))}")
        a2.metric("Active", f"{int(affiliate_summary.get('active_count', 0))}")
        a3.metric("Verified", f"{int(affiliate_summary.get('verified_count', 0))}")
        a4.metric(
            "Never logged in since signup",
            f"{int(affiliate_summary.get('never_logged_in_count', 0))}",
            help="A real engagement gap, independent of any sales question this data can't answer.",
        )

        if not affiliate_by_status.empty:
            status_col = "status" if "status" in affiliate_by_status.columns else affiliate_by_status.columns[0]
            count_col = "count" if "count" in affiliate_by_status.columns else affiliate_by_status.columns[1]
            fig = px.bar(affiliate_by_status, x=status_col, y=count_col)
            fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="", yaxis_title="Signups")
            st.plotly_chart(fig, width='stretch')

        if not affiliates.empty:
            d1, d2 = st.columns(2)
            with d1:
                st.markdown("**Verified**")
                if "verified" in affiliates.columns:
                    v_counts = affiliates["verified"].fillna("Unknown").astype(str).str.title().value_counts().reset_index()
                    v_counts.columns = ["Verified", "Count"]
                    fig = px.pie(v_counts, names="Verified", values="Count", hole=0.55)
                    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
                    st.plotly_chart(fig, width='stretch')
                else:
                    st.info("No verification data available.")
            with d2:
                st.markdown("**Engagement since signup**")
                if "login_count" in affiliates.columns:
                    engagement = affiliates["login_count"].fillna(0).apply(
                        lambda n: "Never logged in" if n == 0 else "Logged in at least once"
                    ).value_counts().reset_index()
                    engagement.columns = ["Engagement", "Count"]
                    fig = px.pie(
                        engagement, names="Engagement", values="Count", hole=0.55,
                        color="Engagement",
                        color_discrete_map={"Never logged in": "#e05a5a", "Logged in at least once": "#00d4aa"},
                    )
                    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
                    st.plotly_chart(fig, width='stretch')
                else:
                    st.info("No login data available.")
            st.caption(
                "Programme engagement only — same known gap as above, this isn't a sales metric."
            )

        st.markdown("**Signup detail**")
        if affiliates.empty:
            st.info("No per-affiliate detail available — check raw_data/uppromote_affiliates.xlsx.")
        else:
            st.dataframe(
                affiliates[[c for c in ["email", "first_name", "last_name", "country", "program", "status", "verified", "login_count", "signup_source"] if c in affiliates.columns]],
                width='stretch',
                height=360,
            )

# ==================================================================================
# AI FORECAST
# ==================================================================================
elif section == "AI Forecast":
    st.subheader("AI Forecast vs Actual")

    if not forecast:
        st.info("No forecast summary available — run 04_forecast_vs_actual.py.")
    else:
        # One clean stat line instead of a paragraph — still direction-aware
        # (not hardcoded to "overpredicted", same reason 04_forecast_vs_actual.py's
        # own printed interpretation is), just without spending the space
        # explaining/justifying which way the error went.
        _predicted = forecast.get("predicted_total_gbp", 0)
        _actual = forecast.get("actual_total_gbp", 0)
        _error_pct = forecast.get("error_pct")
        _overlap_days = int(forecast.get("overlap_days", 0))

        if _error_pct is not None and not pd.isna(_error_pct):
            st.info(
                f"**Forecast accuracy:** £{_predicted:,.2f} predicted vs £{_actual:,.2f} actual "
                f"over {_overlap_days} days — {_error_pct:+.1f}% variance."
            )
        else:
            st.info("**Forecast accuracy:** not enough overlapping data yet to compare predicted vs actual revenue.")

        st.caption(
            "Store-wide daily revenue forecast (Prophet), not a per-product prediction — this store has 7 real "
            "orders across 275 products, not enough history yet for a per-product demand model."
        )

        f1, f2, f3 = st.columns(3)
        f1.metric("Predicted revenue", f"£{forecast.get('predicted_total_gbp', 0):.2f}")
        f2.metric("Actual revenue", f"£{forecast.get('actual_total_gbp', 0):.2f}")
        # Direction-neutral label + value: this used to be hardcoded as
        # "Overprediction multiple", which read backwards on a run where the
        # forecast actually underpredicted (a ratio below 1x on a tile
        # labelled "overprediction" is confusing, not just wrong).
        _ratio = forecast.get("overprediction_multiple")
        f3.metric(
            "Predicted ÷ actual",
            f"{_ratio:.1f}×" if _ratio is not None and not pd.isna(_ratio) else "—",
            help="Below 1× means the forecast underpredicted actual revenue; above 1× means it overpredicted.",
        )

        g1, g2, g3 = st.columns(3)
        g1.metric("Forecast error", f"£{forecast.get('error_gbp', 0):.2f} ({forecast.get('error_pct', 0):.0f}%)")
        g2.metric("Overlap window", f"{int(forecast.get('overlap_days', 0))} days")
        # capital_at_risk_gbp is only ever computed for an OVERprediction
        # (04_forecast_vs_actual.py leaves it blank/None when the forecast
        # underpredicted, since "dead capital from unsold stock" doesn't
        # apply to that case). forecast.get(..., 0) used to be the fallback
        # here, but .get() only uses its default for a MISSING key — a
        # present-but-None/NaN value (exactly what an underprediction run
        # produces, especially once synced through Supabase, which stores it
        # as a real NULL) skipped the default and crashed the £{:.2f} format.
        _capital_at_risk = forecast.get("capital_at_risk_gbp")
        _capital_is_real = _capital_at_risk is not None and not pd.isna(_capital_at_risk)
        g3.metric(
            "Capital at risk",
            f"£{_capital_at_risk:.2f}" if _capital_is_real else "N/A",
            help=(
                f"Uses this catalogue's own verified average margin ({forecast.get('avg_margin_pct_used', 0):.1f}%) "
                "applied to the revenue gap — no inventory-quantity export exists, so no dead-stock unit count is "
                "claimed either way."
                if _capital_is_real
                else "Not applicable this run — the forecast underpredicted actual revenue, so there's no unsold-stock "
                "gap to cost out. (This tile only has a value when the forecast overpredicted.)"
            ),
        )

        bounds = pd.DataFrame({
            "Metric": ["Predicted (lower)", "Predicted", "Predicted (upper)", "Actual"],
            "GBP": [
                forecast.get("predicted_lower_gbp", 0),
                forecast.get("predicted_total_gbp", 0),
                forecast.get("predicted_upper_gbp", 0),
                forecast.get("actual_total_gbp", 0),
            ],
        })
        fig = px.bar(bounds, x="Metric", y="GBP")
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width='stretch')

# ==================================================================================
# PIPELINE HEALTH
# ==================================================================================
elif section == "Pipeline Health":
    st.subheader("Pipeline Health — Launch Readiness")
    st.caption(
        "From analytics/08_pipeline_health.py — re-checks the same structural "
        "invariants the test suite checks (no duplicate handles, every output "
        "file present, headline totals agreeing with each other), on every "
        "pipeline run. This is a lighter, always-on version of the real "
        "correctness check in tests/ — run `pytest` before an actual release, "
        "don't rely on this panel alone."
    )

    if not pipeline_health:
        st.info("No pipeline health summary available — run 08_pipeline_health.py.")
    else:
        status = pipeline_health.get("overall_status")
        if status == "HEALTHY":
            st.success(f"Status: {status}")
        else:
            st.error(f"Status: {status} — do not treat this run's outputs as launch-ready until fixed.")

        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Checks passed", f"{int(pipeline_health.get('checks_passed', 0))} / {int(pipeline_health.get('checks_total', 0))}")
        h2.metric("Products", f"{int(pipeline_health.get('products_row_count', 0)):,}")
        h3.metric("Orders", f"{int(pipeline_health.get('orders_row_count', 0)):,}")
        h4.metric("Pricing integrity score", f"{pipeline_health.get('pricing_integrity_score_pct', 0):.1f}%")
        st.caption(f"Last run: {pipeline_health.get('run_at', 'unknown')}")

        # Same pass/fail count as the "Checks passed" tile above, as a chart —
        # will show a red slice the moment a real check starts failing.
        st.markdown("**Checks passed vs failed**")
        _checks_passed = int(pipeline_health.get("checks_passed", 0))
        _checks_total = int(pipeline_health.get("checks_total", 0))
        _checks_failed = max(_checks_total - _checks_passed, 0)
        checks_split = pd.DataFrame({
            "Result": ["Passed", "Failed"],
            "Count": [_checks_passed, _checks_failed],
        })
        fig = px.pie(
            checks_split, names="Result", values="Count", hole=0.55,
            color="Result", color_discrete_map={"Passed": "#00d4aa", "Failed": "#e05a5a"},
        )
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width='stretch')

        st.markdown("**Individual checks**")
        if not pipeline_health_checks.empty:
            display_df = pipeline_health_checks.copy()
            if "passed" in display_df.columns:
                display_df["passed"] = display_df["passed"].map({True: "✅", False: "❌", "True": "✅", "False": "❌"}).fillna(display_df["passed"])
            st.dataframe(
                display_df[[c for c in ["check_name", "passed", "detail"] if c in display_df.columns]],
                width='stretch',
                height=420,
            )
        else:
            st.info("No individual check detail available.")

# ==================================================================================
# STOCK ALERTS
# ==================================================================================
elif section == "Stock Alerts":
    st.subheader("Stock Alerts")
    st.caption(
        "From stock_alerts/check_stock.py — real, live inventory pulled straight "
        "from Shopify's Admin API, not a dated CSV export like the rest of this "
        "dashboard. It's an optional, opt-in add-on: it only shows real data here "
        "once you've set it up with your own Shopify credentials and run it at "
        "least once — see stock_alerts/README.md. A product with '0' stock at "
        "Shopify but sold with tracking off shows as 'not tracked' rather than "
        "guessed at, the same rule the rest of this project follows."
    )

    if stock_check.empty:
        st.info(
            "No stock check has been run yet. This is optional — see "
            "stock_alerts/README.md to connect your live Shopify inventory and "
            "get weekly email + desktop alerts when something hits 0 stock."
        )
    else:
        checked_at = stock_check["checked_at_utc"].iloc[0] if "checked_at_utc" in stock_check.columns else "unknown"
        st.caption(f"Last live check: {checked_at} (UTC)")

        counts = stock_check["stock_status"].value_counts()
        s1, s2, s3 = st.columns(3)
        s1.metric("In stock", int(counts.get("in stock", 0)))
        s2.metric("Out of stock", int(counts.get("out of stock", 0)))
        s3.metric("Not tracked", int(counts.get("not tracked", 0)))

        out_of_stock = stock_check[stock_check["stock_status"] == "out of stock"]
        if not out_of_stock.empty:
            st.error(f"{len(out_of_stock)} product(s) at 0 stock as of the last check:")
            st.dataframe(
                out_of_stock[["Title", "Auto_Category", "live_inventory_qty"]],
                width='stretch',
            )
        else:
            st.success("No tracked products were at 0 stock as of the last check.")

        status_counts = counts.rename_axis("Status").reset_index(name="Products")
        fig = px.bar(
            status_counts, x="Status", y="Products", color="Status",
            color_discrete_map={"in stock": "#00d4aa", "out of stock": "#e05a5a", "not tracked": "#D4AF37"},
        )
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
        st.plotly_chart(fig, width='stretch')

# ==================================================================================
# SYSTEM ARCHITECTURE FOOTER (shown on every page)
# ==================================================================================
# What this project's stack actually is — deliberately not "what would
# look most impressive". Data source is Shopify's own batch CSV/XLSX
# exports (Analytics + Admin), not a live REST connection; the database
# badge reflects whichever source this run is actually reading from
# (Supabase, or local CSV files as the fallback) via the same `source`
# variable the sidebar already shows.
_db_label = "Supabase (PostgreSQL)" if source == "supabase" else "Local CSV / Excel files"
st.divider()
st.markdown(
    f"""
    <div style='text-align: center; padding: 6px 0 4px 0;'>
        <span style='background: rgba(0,212,170,0.12); border: 1px solid rgba(0,212,170,0.35);
                     color: #7fe8ce; border-radius: 14px; padding: 4px 12px; margin: 0 4px;
                     font-size: 0.78rem; display: inline-block;'>
            📥 Data source: Shopify CSV/XLSX exports + Google Merchant Center + UpPromote
        </span>
        <span style='background: rgba(212,175,55,0.12); border: 1px solid rgba(212,175,55,0.35);
                     color: #D4AF37; border-radius: 14px; padding: 4px 12px; margin: 0 4px;
                     font-size: 0.78rem; display: inline-block;'>
            🗄️ Database: {_db_label}
        </span>
        <span style='background: rgba(0,212,170,0.12); border: 1px solid rgba(0,212,170,0.35);
                     color: #7fe8ce; border-radius: 14px; padding: 4px 12px; margin: 0 4px;
                     font-size: 0.78rem; display: inline-block;'>
            🐍 Pipeline: Python (pandas, scikit-learn, Prophet) via pipeline.py
        </span>
        <span style='background: rgba(212,175,55,0.12); border: 1px solid rgba(212,175,55,0.35);
                     color: #D4AF37; border-radius: 14px; padding: 4px 12px; margin: 0 4px;
                     font-size: 0.78rem; display: inline-block;'>
            📊 Dashboard: Streamlit + Plotly
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)
