import csv
import io
import streamlit as st
import plotly.graph_objects as go
from core.database import load_metrics_db, clear_metrics_db


def render():
    st.markdown('<div class="section-label">Metrics Dashboard</div>', unsafe_allow_html=True)
    st.markdown("<p style='color:#666;font-family:DM Mono,monospace;font-size:0.75rem;margin-bottom:1.2rem;'>Session tracking — review and generation statistics</p>", unsafe_allow_html=True)

    metrics = st.session_state.metrics

    _PLOTLY_LAYOUT = dict(
        paper_bgcolor="#f7f7f5",
        plot_bgcolor="#f7f7f5",
        font=dict(family="DM Mono, monospace", size=12, color="#1a1a1a"),
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=True,
    )

    if not metrics:
        st.info("No data yet — run some reviews or code generation to see metrics here.")
    else:
        total = len(metrics)
        total_ruff = sum(m["ruff"] for m in metrics)
        total_bandit = sum(m["bandit"] for m in metrics)
        issues_found = sum(1 for m in metrics if m["llm_found"])
        detection_rate = int(issues_found / total * 100) if total else 0

        # ── KPI Cards ──────────────────────────────────────────────────────────
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Analyses", total)
        c2.metric("Ruff Issues", total_ruff)
        c3.metric("Bandit Issues", total_bandit)
        c4.metric("Detection Rate", f"{detection_rate}%")
        c5.metric("Clean Sessions", f"{total - issues_found}/{total}")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Row 1: Mode Breakdown + Issue Distribution ─────────────────────────
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown('<div class="section-label">Analyses by Review Mode</div>', unsafe_allow_html=True)
            mode_labels_map = {
                "llm_only": "LLM Only",
                "static_llm": "Static + LLM",
                "repo_llm": "Repo + Static + LLM",
            }
            mode_counts = {}
            mode_ruff   = {}
            mode_bandit = {}
            mode_found  = {}
            for m in metrics:
                md = m["mode"]
                mode_counts[md] = mode_counts.get(md, 0) + 1
                mode_ruff[md]   = mode_ruff.get(md, 0) + m["ruff"]
                mode_bandit[md] = mode_bandit.get(md, 0) + m["bandit"]
                mode_found[md]  = mode_found.get(md, 0) + (1 if m["llm_found"] else 0)

            modes_used  = list(mode_counts.keys())
            mode_labels = [mode_labels_map.get(m, m) for m in modes_used]
            counts      = [mode_counts[m] for m in modes_used]

            fig_mode = go.Figure(go.Bar(
                x=mode_labels,
                y=counts,
                marker_color=["#2563eb", "#7c3aed", "#0d9488"][:len(modes_used)],
                text=counts,
                textposition="outside",
            ))
            fig_mode.update_layout(
                **_PLOTLY_LAYOUT,
                title="",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#e8e8e4", title="Sessions"),
                showlegend=False,
            )
            st.plotly_chart(fig_mode, use_container_width=True)

        with col_right:
            st.markdown('<div class="section-label">Issue Type Distribution</div>', unsafe_allow_html=True)
            if total_ruff + total_bandit > 0:
                fig_pie = go.Figure(go.Pie(
                    labels=["Ruff (Style/Quality)", "Bandit (Security)"],
                    values=[total_ruff, total_bandit],
                    hole=0.5,
                    marker=dict(colors=["#2563eb", "#dc2626"]),
                    textfont=dict(family="DM Mono, monospace", size=12),
                ))
                fig_pie.update_layout(
                    **_PLOTLY_LAYOUT,
                    title="",
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.success("✓ No issues detected across all sessions!")

        # ── Row 2: Mode Comparison Bar (Ruff + Bandit per mode) ────────────────
        if len(mode_counts) > 1:
            st.markdown('<div class="section-label" style="margin-top:0.5rem;">Average Issues Found per Mode</div>', unsafe_allow_html=True)

            avg_ruff   = [mode_ruff.get(m, 0) / mode_counts[m] for m in modes_used]
            avg_bandit = [mode_bandit.get(m, 0) / mode_counts[m] for m in modes_used]

            fig_compare = go.Figure()
            fig_compare.add_trace(go.Bar(
                name="Ruff (Style)",
                x=mode_labels,
                y=avg_ruff,
                marker_color="#2563eb",
                text=[f"{v:.1f}" for v in avg_ruff],
                textposition="outside",
            ))
            fig_compare.add_trace(go.Bar(
                name="Bandit (Security)",
                x=mode_labels,
                y=avg_bandit,
                marker_color="#dc2626",
                text=[f"{v:.1f}" for v in avg_bandit],
                textposition="outside",
            ))
            fig_compare.update_layout(
                **_PLOTLY_LAYOUT,
                barmode="group",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#e8e8e4", title="Avg Issues"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_compare, use_container_width=True)

        # ── Row 3: Detection Rate per Mode ─────────────────────────────────────
        if len(mode_counts) >= 1:
            st.markdown('<div class="section-label" style="margin-top:0.5rem;">Detection Rate per Mode (%)</div>', unsafe_allow_html=True)
            det_rates = [
                round(mode_found.get(m, 0) / mode_counts[m] * 100)
                for m in modes_used
            ]
            fig_det = go.Figure(go.Bar(
                x=mode_labels,
                y=det_rates,
                marker_color=["#16a34a" if r >= 50 else "#d97706" for r in det_rates],
                text=[f"{r}%" for r in det_rates],
                textposition="outside",
            ))
            fig_det.update_layout(
                **_PLOTLY_LAYOUT,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#e8e8e4", title="Detection Rate (%)", range=[0, 110]),
                showlegend=False,
            )
            st.plotly_chart(fig_det, use_container_width=True)

        # ── Row 4: Session Trend (cumulative issues over time) ─────────────────
        if total >= 3:
            st.markdown('<div class="section-label" style="margin-top:0.5rem;">Cumulative Issues Over Sessions</div>', unsafe_allow_html=True)
            cum_ruff   = []
            cum_bandit = []
            cr = cb = 0
            for m in metrics:
                cr += m["ruff"]
                cb += m["bandit"]
                cum_ruff.append(cr)
                cum_bandit.append(cb)

            session_ids = list(range(1, total + 1))
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(
                x=session_ids, y=cum_ruff,
                mode="lines+markers",
                name="Ruff (cumulative)",
                line=dict(color="#2563eb", width=2),
                marker=dict(size=6),
            ))
            fig_trend.add_trace(go.Scatter(
                x=session_ids, y=cum_bandit,
                mode="lines+markers",
                name="Bandit (cumulative)",
                line=dict(color="#dc2626", width=2, dash="dash"),
                marker=dict(size=6),
            ))
            fig_trend.update_layout(
                **_PLOTLY_LAYOUT,
                xaxis=dict(showgrid=True, gridcolor="#e8e8e4", title="Session #"),
                yaxis=dict(showgrid=True, gridcolor="#e8e8e4", title="Cumulative Issues"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        # ── Session Log Table ──────────────────────────────────────────────────
        st.markdown('<div class="section-label" style="margin-top:0.5rem;">Session Log</div>', unsafe_allow_html=True)
        rows = []
        for idx, m in enumerate(metrics):
            rows.append({
                "#": idx + 1,
                "Timestamp": m.get("timestamp", "—"),
                "Mode": mode_labels_map.get(m["mode"], m["mode"]),
                "Ruff Issues": m["ruff"],
                "Bandit Issues": m["bandit"],
                "Total Issues": m["ruff"] + m["bandit"],
                "Issues Detected": "✅ Yes" if m["llm_found"] else "❌ No",
            })
        st.dataframe(rows, use_container_width=True)

        # ── Export ─────────────────────────────────────────────────────────────
        col_exp1, col_exp2 = st.columns([1, 5])
        with col_exp1:
            if st.button("🗑 Clear Metrics"):
                clear_metrics_db()
                st.session_state.metrics = []
                st.rerun()
        with col_exp2:
            csv_buf = io.StringIO()
            writer = csv.DictWriter(csv_buf, fieldnames=["#", "Timestamp", "Mode", "Ruff Issues", "Bandit Issues", "Total Issues", "Issues Detected"])
            writer.writeheader()
            writer.writerows(rows)
            st.download_button(
                "⬇ Export CSV",
                data=csv_buf.getvalue(),
                file_name="codesense_metrics.csv",
                mime="text/csv",
            )
