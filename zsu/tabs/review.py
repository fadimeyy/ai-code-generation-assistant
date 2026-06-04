import streamlit as st
from core.analysis import run_ruff, run_bandit, ask_llm, generate_fixed_code, get_repo_context, record_metric


def render():
    st.markdown('<div class="section-label">Code Review</div>', unsafe_allow_html=True)

    mode = st.selectbox(
        "Review Mode",
        ["llm_only", "static_llm", "repo_llm"],
        format_func=lambda x: {
            "llm_only": "🧠 LLM Only",
            "static_llm": "🔬 Static Analysis + LLM",
            "repo_llm": "🗂 Repo Context + Static Analysis + LLM",
        }[x]
    )

    if mode == "repo_llm":
        c1, c2 = st.columns(2)
        with c1:
            repo_url = st.text_input("GitHub Repo URL:", placeholder="https://github.com/username/repo")
        with c2:
            changed_file = st.text_input("Changed file path:", placeholder="src/auth.py")
    else:
        repo_url, changed_file = "", ""

    code_input = st.text_area("Paste your Python code:", height=280,
                               placeholder="# Paste code to review...")

    if st.button("🔍 Review Code", key="review_btn"):
        if not code_input.strip():
            st.warning("Please paste some code first.")
        else:
            ruff_issues = run_ruff(code_input)
            bandit_issues = run_bandit(code_input)

            repo_context = ""
            if mode == "repo_llm" and repo_url:
                with st.spinner("Fetching repo context..."):
                    repo_context = get_repo_context(repo_url, changed_file)
                st.info(f"Repo context: {len(repo_context)} chars fetched")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown('<div class="section-label">Static Analysis</div>', unsafe_allow_html=True)
                if ruff_issues:
                    st.markdown('<span style="font-family:DM Mono,monospace;font-size:0.7rem;color:#666;letter-spacing:0.1em;">RUFF</span>', unsafe_allow_html=True)
                    for i in ruff_issues:
                        st.error(f"Line {i['location']['row']}: `{i['code']}` — {i['message']}")
                else:
                    st.success("✓ No Ruff issues")

                if bandit_issues:
                    st.markdown('<span style="font-family:DM Mono,monospace;font-size:0.7rem;color:#666;letter-spacing:0.1em;">BANDIT</span>', unsafe_allow_html=True)
                    for i in bandit_issues:
                        sev = i['issue_severity']
                        fn = st.error if sev == "HIGH" else st.warning
                        fn(f"Line {i['line_number']}: `{i['test_id']}` — {i['issue_text']} [{sev}]")
                else:
                    st.success("✓ No Bandit issues")

            with col2:
                st.markdown('<div class="section-label">LLM Review</div>', unsafe_allow_html=True)
                with st.spinner("Analyzing..."):
                    llm_out = ask_llm(code_input, ruff_issues, bandit_issues, mode, repo_context)
                st.markdown(llm_out)

            st.markdown('<div class="section-label" style="margin-top:1.5rem;">Generated Fix</div>', unsafe_allow_html=True)
            with st.spinner("Generating fix..."):
                fixed = generate_fixed_code(code_input, ruff_issues, bandit_issues)
            st.code(fixed, language="python")
            st.download_button("⬇ Download Fixed Code", data=fixed,
                               file_name="fixed_code.py", mime="text/plain")

            # record metric
            record_metric(mode, len(ruff_issues), len(bandit_issues),
                          bool(ruff_issues or bandit_issues))
