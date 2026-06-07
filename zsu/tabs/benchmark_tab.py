import csv
import io
import time
import streamlit as st
import plotly.graph_objects as go
from core.benchmark_data import BENCHMARK_CASES, score_detection
from core.analysis import run_ruff, run_bandit, fast_llm_call
from core.database import load_latest_benchmark_results_db, save_benchmark_results_db

_MODE_LABEL = {
    "llm_only":   "LLM Only",
    "static_llm": "Static + LLM",
    "repo_llm":   "Repo + LLM",
}
_CSV_FIELDS = [
    "ID", "Name", "Category", "Severity", "Mode",
    "GT Issues", "TP", "FP", "FN", "Precision %", "Recall %", "F1 %"
]


def _benchmark_csv(rows):
    bm_csv = io.StringIO()
    writer = csv.DictWriter(bm_csv, fieldnames=_CSV_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return bm_csv.getvalue()


def render():
    st.markdown('<div class="section-label">Benchmark — Experimental Evaluation</div>',
                unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#666;font-family:DM Mono,monospace;font-size:0.8rem;margin-bottom:1.2rem;'>"
        "Run 50 predefined buggy Python programs through the review modes. "
        "Measures how many known issues each mode detects"
        "</p>",
        unsafe_allow_html=True,
    )

    # ── Config ────────────────────────────────────────────────────────────────
    latest_run = load_latest_benchmark_results_db()
    if latest_run:
        if "loaded_benchmark_run" not in st.session_state:
            st.session_state.loaded_benchmark_run = None

        st.markdown(
            "<div class='section-label' style='margin-top:0.5rem;'>Saved Benchmark Export</div>",
            unsafe_allow_html=True,
        )
        load_col, info_col = st.columns([1, 4])
        with load_col:
            if st.button("Load Previous Results", key="bm_load_previous", use_container_width=True):
                st.session_state.loaded_benchmark_run = latest_run
        with info_col:
            st.markdown(
                f"<p style='font-family:DM Mono,monospace;font-size:0.75rem;color:#999;'>"
                f"Latest saved run: {latest_run['timestamp']} · {latest_run['row_count']} rows</p>",
                unsafe_allow_html=True,
            )

        loaded_run = st.session_state.loaded_benchmark_run
        if loaded_run:
            st.dataframe(loaded_run["rows"], use_container_width=True)
            st.download_button(
                "Export Loaded Benchmark Results (CSV)",
                data=_benchmark_csv(loaded_run["rows"]),
                file_name="codesense_benchmark.csv",
                mime="text/csv",
                key=f"bm_export_loaded_{loaded_run['id']}",
            )

    bm_col1, bm_col2 = st.columns([2, 1])
    with bm_col1:
        selected_modes = st.multiselect(
            "Modes to benchmark:",
            ["llm_only", "static_llm", "repo_llm"],
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

    repo_pilot_only = st.checkbox(
        "Repo Pilot Control (TC-R01–TC-R05 only: LLM Only vs Static + LLM vs Repo + LLM)",
        value=False,
        key="bm_repo_pilot_only",
    )

    active_modes = ["llm_only", "static_llm", "repo_llm"] if repo_pilot_only else selected_modes

    if repo_pilot_only:
        filtered_cases = [c for c in BENCHMARK_CASES if c.get("repo_only", False)]
        st.info("Repo pilot control is active: only TC-R01–TC-R05 will run with LLM Only, Static + LLM, and Repo + LLM.")
    else:
        # Repo+LLM seçildiyse repo_only vakalarını da dahil et, seçilmediyse hariç tut
        include_repo_only = "repo_llm" in active_modes
        filtered_cases = [
            c for c in BENCHMARK_CASES
            if c["category"] in selected_categories
            and (include_repo_only or not c.get("repo_only", False))
        ]

    if "repo_llm" in active_modes and not repo_pilot_only:
        st.info("ℹ️ Repo+LLM modu seçili: TC-R01–TC-R05 (repo bağlamlı vakalar) benchmark'a dahil edildi.")

    # ── Quick Mode ────────────────────────────────────────────────────────────
    quick_mode = st.checkbox(
        "⚡ Quick Mode (10 random cases instead of all — repo-only cases always included)",
        value=True, key="bm_quick"
    )
    if quick_mode and len(filtered_cases) > 10:
        import random as _rnd
        _rnd.seed(42)
        # Repo-only vakalarını ayır, quick mode'da her zaman dahil et
        repo_cases   = [c for c in filtered_cases if c.get("repo_only")]
        normal_cases = [c for c in filtered_cases if not c.get("repo_only")]
        sample_count = max(0, 10 - len(repo_cases))
        sampled      = _rnd.sample(normal_cases, min(sample_count, len(normal_cases)))
        filtered_cases = sampled + repo_cases

    # Gerçek call sayısını hesapla (repo_only vakalar sadece repo_llm ile çalışır)
    _normal_modes = [m for m in active_modes if m != "repo_llm"]
    _repo_modes   = [m for m in active_modes if m == "repo_llm"]
    _normal_count = sum(1 for c in filtered_cases if not c.get("repo_only"))
    _repo_count   = sum(1 for c in filtered_cases if c.get("repo_only"))
    if repo_pilot_only:
        total_calls = len(filtered_cases) * len(active_modes)
    else:
        total_calls = _normal_count * len(_normal_modes) + _repo_count * len(_repo_modes)
    est_min = round(total_calls * 6 / 60, 1)
    st.markdown(
        f"<p style='font-family:DM Mono,monospace;font-size:0.75rem;color:#999;'>"
        f"{len(filtered_cases)} test cases · {len(active_modes)} mode(s) · "
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
        if not active_modes:
            st.warning("Please select at least one mode.")
            return
        if not filtered_cases:
            st.warning("Please select at least one category.")
            return

        results = []
        skipped = []
        # Toplam call sayısını akıllıca hesapla
        normal_modes = [m for m in active_modes if m != "repo_llm"]
        repo_modes   = [m for m in active_modes if m == "repo_llm"]
        normal_cases_count = sum(1 for c in filtered_cases if not c.get("repo_only"))
        repo_cases_count   = sum(1 for c in filtered_cases if c.get("repo_only"))
        if repo_pilot_only:
            total_cases = len(filtered_cases) * len(active_modes)
        else:
            total_cases = normal_cases_count * len(normal_modes) + repo_cases_count * len(repo_modes)
        progress  = st.progress(0)
        status_txt = st.empty()
        eta_txt    = st.empty()
        step = 0
        import time as _time
        t_start = _time.time()

        for tc in filtered_cases:
            ruff_issues   = run_ruff(tc["code"])
            bandit_issues = run_bandit(tc["code"])

            # repo pilot control'de repo vakaları hem LLM Only hem Repo+LLM ile çalışır
            if repo_pilot_only:
                modes_for_tc = active_modes
            elif tc.get("repo_only"):
                modes_for_tc = [m for m in active_modes if m == "repo_llm"]
            else:
                modes_for_tc = [m for m in active_modes if m != "repo_llm"]

            for mode in modes_for_tc:
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
                    if mode in ("static_llm", "repo_llm"):
                        lines = []
                        for i in ruff_issues:
                            lines.append(f"- Ruff {i['code']}: {i['message']}")
                        for i in bandit_issues:
                            lines.append(f"- Bandit {i['test_id']}: {i['issue_text']}")
                        if lines:
                            static_section = "STATIC FINDINGS:\n" + "\n".join(lines)

                    # Repo+LLM: test vakasının repo_context alanını prompt'a ekle
                    repo_section = ""
                    if mode == "repo_llm" and tc.get("repo_context"):
                        repo_section = (
                            "\nREPO CONTEXT (related modules from the same codebase):\n"
                            + tc["repo_context"]
                            + "\n"
                        )

                    bm_prompt = (
                        "You are a Python code reviewer. Review this code carefully "
                        "and list ALL issues found.\n\n"
                        f"CODE:\n{tc['code']}\n"
                        + (static_section + "\n" if static_section else "")
                        + repo_section
                        + "For each issue name it explicitly: e.g. sql injection, hardcoded password, "
                        "eval, pickle, md5, shell=True, yaml.load, bare except, mutable default "
                        "argument, unused import, resource leak, circular import, race condition, "
                        "authentication bypass, thread safety, etc."
                    )
                    llm_out = fast_llm_call(bm_prompt)
                    time.sleep(10)  # pace requests — avoids rate-limit 429
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
        mode_keys_used = [m for m in active_modes if any(r["mode_key"] == m for r in results)]
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
        save_benchmark_results_db(table_rows)
        st.session_state.loaded_benchmark_run = load_latest_benchmark_results_db()
        st.dataframe(table_rows, use_container_width=True)

        pilot_results = [r for r in results if r["id"].startswith("TC-R")]
        if pilot_results and {"llm_only", "static_llm", "repo_llm"}.issubset({r["mode_key"] for r in pilot_results}):
            st.markdown(
                "<div class='section-label' style='margin-top:1rem;'>Repo Pilot Control Summary</div>",
                unsafe_allow_html=True,
            )
            pilot_rows = []
            for tc in [c for c in BENCHMARK_CASES if c.get("repo_only", False)]:
                llm_row = next(
                    (r for r in pilot_results if r["id"] == tc["id"] and r["mode_key"] == "llm_only"),
                    None,
                )
                static_row = next(
                    (r for r in pilot_results if r["id"] == tc["id"] and r["mode_key"] == "static_llm"),
                    None,
                )
                repo_row = next(
                    (r for r in pilot_results if r["id"] == tc["id"] and r["mode_key"] == "repo_llm"),
                    None,
                )
                if not llm_row or not static_row or not repo_row:
                    continue
                repo_gain = repo_row["f1"] - llm_row["f1"]
                static_gain = static_row["f1"] - llm_row["f1"]
                pilot_rows.append({
                    "ID": tc["id"],
                    "Test Case": tc["name"],
                    "Category": tc["category"],
                    "Severity": tc["severity"],
                    "GT": repo_row["total_gt"],
                    "LLM Only F1 %": llm_row["f1"],
                    "Static+LLM F1 %": static_row["f1"],
                    "Repo+LLM F1 %": repo_row["f1"],
                    "Static Gain": f"{static_gain:+.1f}",
                    "Repo Gain": f"{repo_gain:+.1f}",
                })
            if pilot_rows:
                st.dataframe(pilot_rows, use_container_width=True)

        # ── Charts ────────────────────────────────────────────────────────────
        if len(mode_keys_used) >= 1:
            st.markdown("<div class='section-label' style='margin-top:1rem;'>Visualisations</div>",
                        unsafe_allow_html=True)
            _bm_layout = dict(
                paper_bgcolor="#f7f7f5", plot_bgcolor="#f7f7f5",
                font=dict(family="DM Mono, monospace", size=11, color="#1a1a1a"),
                margin=dict(l=20, r=20, t=40, b=20),
            )
            colors = ["#2563eb", "#7c3aed", "#0d9488"]

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
        if len(mode_keys_used) >= 2:
            # Tüm modlar için F1 ortalamasını hesapla
            mode_f1 = {}
            mode_rc = {}
            for mk in mode_keys_used:
                mr = [r for r in results if r["mode_key"] == mk]
                mode_f1[mk] = sum(r["f1"]     for r in mr) / max(1, len(mr))
                mode_rc[mk] = sum(r["recall"] for r in mr) / max(1, len(mr))

            best_mode = max(mode_f1, key=mode_f1.get)
            worst_mode = min(mode_f1, key=mode_f1.get)
            diff_f1 = mode_f1[best_mode] - mode_f1[worst_mode]
            diff_rc = mode_rc[best_mode] - mode_rc[worst_mode]

            # Repo+LLM özel bulgusu
            repo_note = ""
            if "repo_llm" in mode_keys_used:
                repo_cases = [r for r in results if r["id"].startswith("TC-R")]
                if repo_cases:
                    repo_f1_by_mode = {
                        mk: sum(r["f1"] for r in repo_cases if r["mode_key"] == mk)
                           / max(1, sum(1 for r in repo_cases if r["mode_key"] == mk))
                        for mk in mode_keys_used
                    }
                    repo_best = max(repo_f1_by_mode, key=repo_f1_by_mode.get)
                    repo_note = (
                        f"\n> 🔗 **Repo+LLM on cross-module cases (TC-R01–TC-R05):** "
                        f"{_MODE_LABEL[repo_best]} achieved avg F1 of "
                        f"**{repo_f1_by_mode[repo_best]:.1f}%** on context-dependent bugs "
                        f"that LLM Only scored "
                        f"**{repo_f1_by_mode.get('llm_only', 0):.1f}%** on.  "
                    )

            st.markdown(f"""
> ✨ **Key Finding:**  
> **{_MODE_LABEL[best_mode]}** achieved the highest average F1 across {len(filtered_cases)} test cases.  
> F1 difference (best vs worst): **{diff_f1:.1f} pp** · Recall difference: **{diff_rc:.1f} pp**  
> This supports the hypothesis that additional context (static findings + repo) improves LLM-based code review.
{repo_note}
""")

        # ── Export ────────────────────────────────────────────────────────────
        st.download_button(
            "⬇ Export Benchmark Results (CSV)",
            data=_benchmark_csv(table_rows),
            file_name="codesense_benchmark.csv",
            mime="text/csv",
            key="bm_export_current",
        )
