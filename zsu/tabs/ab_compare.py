import re
import streamlit as st
import plotly.graph_objects as go
from core.analysis import run_ruff, run_bandit, ask_llm, record_metric


def render():
    st.markdown('<div class="section-label">A/B Mode Comparison</div>', unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#666;font-family:DM Mono,monospace;font-size:0.8rem;margin-bottom:1.2rem;'>"
        "Run the same code through two different review modes side-by-side — "
        "compare what each mode finds and how they differ."
        "</p>",
        unsafe_allow_html=True,
    )

    _MODE_LABELS = {
        "llm_only":   "🧠 LLM Only",
        "static_llm": "🔬 Static + LLM",
        "repo_llm":   "🗂 Repo + Static + LLM",
    }

    # ── Code input
    ab_code = st.text_area(
        "Paste your Python code:",
        height=200,
        placeholder="# Paste the code you want to compare across modes...",
        key="ab_code_input",
    )

    # ── Mode selectors
    col_ma, col_mb = st.columns(2)
    with col_ma:
        mode_a = st.selectbox(
            "Mode A",
            list(_MODE_LABELS.keys()),
            format_func=lambda x: _MODE_LABELS[x],
            index=0,
            key="ab_mode_a",
        )
    with col_mb:
        mode_b = st.selectbox(
            "Mode B",
            list(_MODE_LABELS.keys()),
            format_func=lambda x: _MODE_LABELS[x],
            index=1,
            key="ab_mode_b",
        )

    run_ab = st.button("⚡ Run A/B Comparison", key="ab_run_btn")

    if run_ab:
        if not ab_code.strip():
            st.warning("Please paste some code first.")
        elif mode_a == mode_b:
            st.warning("Please select two different modes to compare.")
        else:
            # ── Static analysis (shared)
            with st.spinner("Running static analysis..."):
                ab_ruff   = run_ruff(ab_code)
                ab_bandit = run_bandit(ab_code)

            # ── LLM reviews
            with st.spinner(f"Running {_MODE_LABELS[mode_a]}..."):
                result_a = ask_llm(ab_code, ab_ruff, ab_bandit, mode_a)
            with st.spinner(f"Running {_MODE_LABELS[mode_b]}..."):
                result_b = ask_llm(ab_code, ab_ruff, ab_bandit, mode_b)

            # ── Static summary (shared)
            st.markdown(
                "<div class='section-label' style='margin-top:1.5rem;'>Static Analysis (shared input)</div>",
                unsafe_allow_html=True,
            )
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("Ruff Issues",   len(ab_ruff))
            sc2.metric("Bandit Issues", len(ab_bandit))
            sc3.metric("Total",         len(ab_ruff) + len(ab_bandit))

            # ── Side-by-side LLM reviews
            st.markdown(
                "<div class='section-label' style='margin-top:1rem;'>LLM Review Outputs</div>",
                unsafe_allow_html=True,
            )
            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown(
                    f"<div style='font-family:DM Mono,monospace;font-size:0.72rem;letter-spacing:0.1em;"
                    f"text-transform:uppercase;color:#2563eb;border-bottom:2px solid #2563eb;"
                    f"padding-bottom:4px;margin-bottom:12px;'>Mode A — {_MODE_LABELS[mode_a]}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(result_a)

            with col_b:
                st.markdown(
                    f"<div style='font-family:DM Mono,monospace;font-size:0.72rem;letter-spacing:0.1em;"
                    f"text-transform:uppercase;color:#7c3aed;border-bottom:2px solid #7c3aed;"
                    f"padding-bottom:4px;margin-bottom:12px;'>Mode B — {_MODE_LABELS[mode_b]}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(result_b)

            # ── Visual Comparison Charts
            st.markdown(
                "<div class='section-label' style='margin-top:1rem;'>Visual Comparison</div>",
                unsafe_allow_html=True,
            )

            def count_lines_mentioned(text: str) -> int:
                line_refs = re.findall(r'[Ll]ine(?:\s+[Nn]umber)?:?\s*\d+', text)
                issue_refs = re.findall(r'Severity:', text)
                return max(len(line_refs), len(issue_refs))

            lines_a = count_lines_mentioned(result_a)
            lines_b = count_lines_mentioned(result_b)

            ruff_a   = len(ab_ruff)   if mode_a != "llm_only" else 0
            bandit_a = len(ab_bandit) if mode_a != "llm_only" else 0
            ruff_b   = len(ab_ruff)   if mode_b != "llm_only" else 0
            bandit_b = len(ab_bandit) if mode_b != "llm_only" else 0

            _ab_layout = dict(
                paper_bgcolor="#f7f7f5", plot_bgcolor="#f7f7f5",
                font=dict(family="DM Mono, monospace", size=12, color="#1a1a1a"),
                margin=dict(l=20, r=20, t=40, b=20),
            )

            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                fig_ab = go.Figure()
                fig_ab.add_trace(go.Bar(
                    name="Ruff Visible",
                    x=[_MODE_LABELS[mode_a], _MODE_LABELS[mode_b]],
                    y=[ruff_a, ruff_b],
                    marker_color="#2563eb",
                    text=[ruff_a, ruff_b], textposition="outside",
                ))
                fig_ab.add_trace(go.Bar(
                    name="Bandit Visible",
                    x=[_MODE_LABELS[mode_a], _MODE_LABELS[mode_b]],
                    y=[bandit_a, bandit_b],
                    marker_color="#dc2626",
                    text=[bandit_a, bandit_b], textposition="outside",
                ))
                fig_ab.update_layout(
                    **_ab_layout, barmode="group", showlegend=True,
                    title="Static Findings Visible to Each Mode",
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor="#e8e8e4", title="Issues"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_ab, use_container_width=True)

            with chart_col2:
                fig_lines = go.Figure(go.Bar(
                    x=[_MODE_LABELS[mode_a], _MODE_LABELS[mode_b]],
                    y=[lines_a, lines_b],
                    marker_color=["#2563eb", "#7c3aed"],
                    text=[lines_a, lines_b], textposition="outside",
                ))
                fig_lines.update_layout(
                    **_ab_layout, showlegend=False,
                    title="Line References in LLM Output",
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor="#e8e8e4", title="Count"),
                )
                st.plotly_chart(fig_lines, use_container_width=True)

            # ── Verdict summary table
            st.markdown(
                "<div class='section-label' style='margin-top:0.5rem;'>Comparison Summary</div>",
                unsafe_allow_html=True,
            )
            total_a = ruff_a + bandit_a
            total_b = ruff_b + bandit_b

            if total_a > total_b:
                verdict = f"🏆 **Mode A ({_MODE_LABELS[mode_a]})** had more static context ({total_a} vs {total_b} issues visible)"
            elif total_b > total_a:
                verdict = f"🏆 **Mode B ({_MODE_LABELS[mode_b]})** had more static context ({total_b} vs {total_a} issues visible)"
            else:
                verdict = "⚖️ Both modes had the same static context available."

            st.markdown(f"""
| | Mode A | Mode B |
|---|---|---|
| **Name** | {_MODE_LABELS[mode_a]} | {_MODE_LABELS[mode_b]} |
| **Ruff issues visible** | {ruff_a} | {ruff_b} |
| **Bandit issues visible** | {bandit_a} | {bandit_b} |
| **Line refs in review** | {lines_a} | {lines_b} |
""")
            st.info(verdict)

            # Save both runs to metrics DB
            record_metric(mode_a, ruff_a, bandit_a, bool(ruff_a or bandit_a))
            record_metric(mode_b, ruff_b, bandit_b, bool(ruff_b or bandit_b))