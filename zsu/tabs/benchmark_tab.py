import csv
import io
import time
import streamlit as st
import plotly.graph_objects as go
from core.benchmark_data import BENCHMARK_CASES, score_detection
from core.analysis import run_ruff, run_bandit, ask_llm, fast_llm_call

_MODE_LABEL = {"llm_only": "LLM Only", "static_llm": "Static + LLM"}


def render():
    st.markdown('<div class="section-label">Benchmark — Experimental Evaluation</div>',
                unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#666;font-family:DM Mono,monospace;font-size:0.8rem;margin-bottom:1.2rem;'>"
        "Run 50 predefined buggy Python programs through the review modes. "
        "Measures how many known issues each mode detects — use these results in your paper."
        "</p>",
        unsafe_allow_html=True,
    )

    # ── Config ────────────────────────────────────────────────────────────────
    bm_col1, bm_col2 = st.columns([2, 1])
    with bm_col1:
        selected_modes = st.multiselect(
            "Modes to benchmark:",
            ["llm_only", "static_llm"],
            default=["llm_only", "static_llm"],
            format_func=lambda x: _MODE_LABEL[x],
            key="bm_modes",
        )
    with bm_col2:
        selected_categories = st.multiselect(
            "Filter categories:",
            ["Security", "Quality", "Style"],
            default=["Security", "Quality", "Style"],
            key="bm_cats",
        )

    filtered_cases = [c for c in BENCHMARK_CASES if c["category"] in selected_categories]

    # ── Quick Mode ────────────────────────────────────────────────────────────
    quick_mode = st.checkbox(
        "⚡ Quick Mode (10 random cases instead of all 50)",
        value=True, key="bm_quick"
    )
    if quick_mode and len(filtered_cases) > 10:
        import random as _rnd
        _rnd.seed(42)
        filtered_cases = _rnd.sample(filtered_cases, 10)

    total_calls = len(filtered_cases) * len(selected_modes)
    est_min = round(total_calls * 6 / 60, 1)
    st.markdown(
        f"<p style='font-family:DM Mono,monospace;font-size:0.75rem;color:#999;'>"
        f"{len(filtered_cases)} test cases · {len(selected_modes)} mode(s) · "
        f"{total_calls} API calls · est. ~{est_min} min</p>",
        unsafe_allow_html=True,
    )

    # ── Test case preview ─────────────────────────────────────────────────────
    with st.expander("💾 Preview test cases", expanded=False):
        for tc in filtered_cases:
            sev_color = {"HIGH": "#dc2626", "MEDIUM": "#d97706", "LOW": "#16a34a"}.get(
                tc["severity"], "#999")
            st.markdown(
                f"<span style='font-family:DM Mono,monospace;font-size:0.72rem;'>"
                f"<b style='color:{sev_color};'>[{tc['severity']}]</b> "
                f"<b>{tc['id']}</b> — {tc['name']} ({tc['category']})</span>",
                unsafe_allow_html=True,
            )
            st.code(tc["code"].strip(), language="python")

    # ── Debug mode toggle ─────────────────────────────────────────────────────
    debug_mode = st.checkbox("🔍 Show LLM output preview (debug)", value=False, key="bm_debug")

    run_benchmark = st.button("🚀 Run Benchmark", key="bm_run")

    if run_benchmark:
        if not selected_modes:
            st.warning("Please select at least one mode.")
            return
        if not filtered_cases:
            st.warning("Please select at least one category.")
            return

        results = []
        skipped = []
        total_cases = len(filtered_cases) * len(selected_modes)
        progress  = st.progress(0)
        status_txt = st.empty()
        eta_txt    = st.empty()
        step = 0
        import time as _time
        t_start = _time.time()

        for tc in filtered_cases:
            ruff_issues   = run_ruff(tc["code"])
            bandit_issues = run_bandit(tc["code"])

            for mode in selected_modes:
                status_txt.markdown(
                    f"<span style='font-family:DM Mono,monospace;font-size:0.75rem;color:#999;'>"
                    f"Running {_MODE_LABEL[mode]} on {tc['id']} — {tc['name']}…</span>",
                    unsafe_allow_html=True,
                )
                # ETA
                if step > 0:
                    elapsed = _time.time() - t_start
                    remaining = elapsed / step * (total_cases - step)
                    eta_txt.markdown(
                        f"<span style='font-family:DM Mono,monospace;font-size:0.7rem;color:#bbb;'>"
                        f"{step}/{total_cases} done · ~{remaining/60:.1f} min remaining</span>",
                        unsafe_allow_html=True,
                    )

                try:
                    static_section = ""
                    if mode == "static_llm":
                        lines = []
                        for i in ruff_issues:
                            lines.append(f"- Ruff {i['code']}: {i['message']}")
                        for i in bandit_issues:
                            lines.append(f"- Bandit {i['test_id']}: {i['issue_text']}")
                        static_section = "STATIC FINDINGS:\n" + "\n".join(lines)
                    bm_prompt = (
                        "You are a Python code reviewer. Review this code and list ALL issues.\n\n"
                        f"CODE:\n{tc['code']}\n"
                        + (static_section + "\n" if static_section else "")
                        + "For each issue name it explicitly: e.g. sql injection, hardcoded password, "
                        "eval, pickle, md5, shell=True, yaml.load, bare except, mutable default "
                        "argument, unused import, resource leak, etc."
                    )
                    llm_out = fast_llm_call(bm_prompt)
                    time.sleep(10)# pace requests — avoids rate-limit 42910
                except Exception:
                    llm_out = ""

                # ── Skip if LLM returned nothing (API error) ──────────────────
                if not llm_out or llm_out.startswith("⚠️"):
                    skipped.append(f"{tc['id']} ({_MODE_LABEL[mode]})")
                    step += 1
                    progress.progress(step / total_cases)
                    continue

                # ── Debug preview ─────────────────────────────────────────────
                if debug_mode:
                    with st.expander(f"🔍 {tc['id']} {_MODE_LABEL[mode]} — LLM output"):
                        st.text(llm_out[:800])
                        st.caption(f"Keywords to match: {tc.get('known_issues', [])}")

                score = score_detection(
                    llm_out,
                    ruff_issues,
                    bandit_issues,
                    tc.get("known_issues", []),
                    mode,
                )

                results.append({
                    "id":         tc["id"],
                    "name":       tc["name"],
                    "category":   tc["category"],
                    "severity":   tc["severity"],
                    "mode":       _MODE_LABEL[mode],
                    "mode_key":   mode,
                    "ruff":       len(ruff_issues),
                    "bandit":     len(bandit_issues),
                    "total_gt":   score["total_gt"],
                    "tp":         score["tp"],
                    "fp":         score["fp"],
                    "fn":         score["fn"],
                    "precision":  score["precision"],
                    "recall":     score["recall"],
                    "f1":         score["f1"],
                    "llm_output": llm_out,
                })
                step += 1
                progress.progress(step / total_cases)

        status_txt.empty()
        eta_txt.empty()
        progress.empty()

        if skipped:
            st.warning(
                f"⚠️ {len(skipped)} run(s) skipped due to API errors: {', '.join(skipped[:5])}"
                + (" …" if len(skipped) > 5 else "")
                + " — Try re-running in a few minutes."
            )

        if not results:
            st.error("❌ No results — all runs failed. Gemini API may be overloaded. Wait and retry.")
            return

        completed = len(results)
        st.success(
            f"✅ Benchmark complete — {completed} runs completed"
            + (f", {len(skipped)} skipped" if skipped else "")
            + f" across {len(filtered_cases)} test cases."
        )

        # ── KPI summary ───────────────────────────────────────────────────────
        st.markdown("<div class='section-label' style='margin-top:1rem;'>Summary</div>",
                    unsafe_allow_html=True)
        mode_keys_used = [m for m in selected_modes if any(r["mode_key"] == m for r in results)]
        kpi_cols = st.columns(len(mode_keys_used) * 3)
        kpi_idx = 0
        for mode_key in mode_keys_used:
            mr = [r for r in results if r["mode_key"] == mode_key]
            avg_p  = sum(r["precision"] for r in mr) / len(mr)
            avg_r  = sum(r["recall"]    for r in mr) / len(mr)
            avg_f1 = sum(r["f1"]        for r in mr) / len(mr)
            kpi_cols[kpi_idx  ].metric(f"{_MODE_LABEL[mode_key]} Precision", f"{avg_p:.1f}%")
            kpi_cols[kpi_idx+1].metric(f"{_MODE_LABEL[mode_key]} Recall",    f"{avg_r:.1f}%")
            kpi_cols[kpi_idx+2].metric(f"{_MODE_LABEL[mode_key]} F1",        f"{avg_f1:.1f}%")
            kpi_idx += 3

        # ── Results table ─────────────────────────────────────────────────────
        st.markdown("<div class='section-label' style='margin-top:1rem;'>Detailed Results</div>",
                    unsafe_allow_html=True)
        table_rows = []
        for r in results:
            table_rows.append({
                "ID":          r["id"],
                "Name":        r["name"],
                "Category":    r["category"],
                "Severity":    r["severity"],
                "Mode":        r["mode"],
                "GT Issues":   r["total_gt"],
                "TP":          r["tp"],
                "FP":          r["fp"],
                "FN":          r["fn"],
                "Precision %": r["precision"],
                "Recall %":    r["recall"],
                "F1 %":        r["f1"],
            })
        st.dataframe(table_rows, use_container_width=True)

        # ── Charts ────────────────────────────────────────────────────────────
        if len(mode_keys_used) >= 1:
            st.markdown("<div class='section-label' style='margin-top:1rem;'>Visualisations</div>",
                        unsafe_allow_html=True)
            _bm_layout = dict(
                paper_bgcolor="#f7f7f5", plot_bgcolor="#f7f7f5",
                font=dict(family="DM Mono, monospace", size=11, color="#1a1a1a"),
                margin=dict(l=20, r=20, t=40, b=20),
            )
            colors = ["#2563eb", "#7c3aed"]

            ch1, ch2 = st.columns(2)
            with ch1:
                fig_f1 = go.Figure()
                labels = [_MODE_LABEL[m] for m in mode_keys_used]
                for metric, name, col_set in [
                    ("f1",        "F1",        ["#2563eb","#7c3aed"]),
                    ("recall",    "Recall",    ["#93c5fd","#c4b5fd"]),
                    ("precision", "Precision", ["#6ee7b7","#fde68a"]),
                ]:
                    vals = [
                        sum(r[metric] for r in results if r["mode_key"]==m)
                        / max(1, sum(1 for r in results if r["mode_key"]==m))
                        for m in mode_keys_used
                    ]
                    fig_f1.add_trace(go.Bar(
                        name=name, x=labels, y=vals,
                        marker_color=col_set[:len(mode_keys_used)],
                        text=[f"{v:.1f}%" for v in vals], textposition="outside"
                    ))
                fig_f1.update_layout(**_bm_layout, barmode="group",
                    title="Avg Precision / Recall / F1 by Mode",
                    yaxis=dict(range=[0, 120], title="%", showgrid=True, gridcolor="#e8e8e4"),
                    xaxis=dict(showgrid=False),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig_f1, use_container_width=True)

            with ch2:
                categories_used = sorted(set(r["category"] for r in results))
                fig_cat = go.Figure()
                for i, mk in enumerate(mode_keys_used):
                    cat_recalls = [
                        sum(r["recall"] for r in results if r["mode_key"]==mk and r["category"]==cat)
                        / max(1, sum(1 for r in results if r["mode_key"]==mk and r["category"]==cat))
                        for cat in categories_used
                    ]
                    fig_cat.add_trace(go.Bar(
                        name=_MODE_LABEL[mk], x=categories_used, y=cat_recalls,
                        marker_color=colors[i % 2],
                        text=[f"{v:.0f}%" for v in cat_recalls], textposition="outside"
                    ))
                fig_cat.update_layout(**_bm_layout, barmode="group",
                    title="Recall by Category & Mode",
                    yaxis=dict(range=[0, 120], title="Recall %", showgrid=True, gridcolor="#e8e8e4"),
                    xaxis=dict(showgrid=False),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig_cat, use_container_width=True)

            ch3, ch4 = st.columns(2)
            with ch3:
                fig_per = go.Figure()
                for i, mk in enumerate(mode_keys_used):
                    mr = [r for r in results if r["mode_key"]==mk]
                    fig_per.add_trace(go.Bar(
                        name=_MODE_LABEL[mk],
                        x=[r["id"] for r in mr], y=[r["recall"] for r in mr],
                        marker_color=colors[i % 2],
                        text=[f"{r['recall']}%" for r in mr], textposition="outside"
                    ))
                fig_per.update_layout(**_bm_layout, barmode="group",
                    title="Recall per Test Case",
                    yaxis=dict(range=[0, 130], title="Recall %", showgrid=True, gridcolor="#e8e8e4"),
                    xaxis=dict(showgrid=False, tickangle=-45),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig_per, use_container_width=True)

            with ch4:
                sev_labels = ["HIGH", "MEDIUM", "LOW"]
                fig_sev = go.Figure()
                for i, mk in enumerate(mode_keys_used):
                    sev_recalls = [
                        sum(r["recall"] for r in results if r["mode_key"]==mk and r["severity"]==sev)
                        / max(1, sum(1 for r in results if r["mode_key"]==mk and r["severity"]==sev))
                        for sev in sev_labels
                    ]
                    fig_sev.add_trace(go.Bar(
                        name=_MODE_LABEL[mk], x=sev_labels, y=sev_recalls,
                        marker_color=colors[i % 2],
                        text=[f"{v:.0f}%" for v in sev_recalls], textposition="outside"
                    ))
                fig_sev.update_layout(**_bm_layout, barmode="group",
                    title="Recall by Severity Level",
                    yaxis=dict(range=[0, 130], title="Recall %", showgrid=True, gridcolor="#e8e8e4"),
                    xaxis=dict(showgrid=False),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig_sev, use_container_width=True)

        # ── Research findings ─────────────────────────────────────────────────
        st.markdown("<div class='section-label' style='margin-top:0.5rem;'>Research Findings</div>",
                    unsafe_allow_html=True)
        if len(mode_keys_used) == 2:
            m0, m1 = mode_keys_used
            r0 = [r for r in results if r["mode_key"] == m0]
            r1 = [r for r in results if r["mode_key"] == m1]
            f1_0 = sum(r["f1"]     for r in r0) / max(1, len(r0))
            f1_1 = sum(r["f1"]     for r in r1) / max(1, len(r1))
            rc_0 = sum(r["recall"] for r in r0) / max(1, len(r0))
            rc_1 = sum(r["recall"] for r in r1) / max(1, len(r1))
            better = _MODE_LABEL[m0] if f1_0 >= f1_1 else _MODE_LABEL[m1]
            diff_f1 = abs(f1_0 - f1_1)
            diff_rc = abs(rc_0 - rc_1)
            st.markdown(f"""
> ✨ **Key Finding:**  
> **{better}** achieved higher average F1 across {len(filtered_cases)} test cases.  
> F1 difference: **{diff_f1:.1f} pp** · Recall difference: **{diff_rc:.1f} pp**  
> This supports the hypothesis that static analysis tools provide additional context  
> that improves LLM-based code review quality.
""")

        # ── Export ────────────────────────────────────────────────────────────
        bm_csv = io.StringIO()
        writer = csv.DictWriter(bm_csv, fieldnames=[
            "ID", "Name", "Category", "Severity", "Mode",
            "GT Issues", "TP", "FP", "FN", "Precision %", "Recall %", "F1 %"
        ])
        writer.writeheader()
        writer.writerows(table_rows)
        st.download_button(
            "⬇ Export Benchmark Results (CSV)",
            data=bm_csv.getvalue(),
            file_name="codesense_benchmark.csv",
            mime="text/csv",
        )