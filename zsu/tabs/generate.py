import streamlit as st
from core.analysis import generate_code_from_description, complete_code, run_ruff, run_bandit, generate_fixed_code, ask_llm, record_metric


def render():
    st.markdown('<div class="section-label">Generate &amp; Complete</div>', unsafe_allow_html=True)
    gen_tab, complete_tab = st.tabs(["Generate from Description", "Complete Partial Code"])

    with gen_tab:
        st.markdown("<p style='color:#666;font-family:DM Mono,monospace;font-size:0.8rem;'>Describe what you want — AI writes it, then auto-reviews.</p>", unsafe_allow_html=True)
        description = st.text_area(
            "Describe your code:",
            placeholder="e.g. A secure login function with bcrypt hashing and SQL injection prevention\ne.g. REST API client that retries on failure with exponential backoff\ne.g. CSV parser that handles missing values and outputs clean data",
            height=150
        )
        if st.button("✨ Generate & Review", key="gen_btn"):
            if not description.strip():
                st.warning("Please describe what you want to build.")
            else:
                with st.spinner("Generating code..."):
                    generated = generate_code_from_description(description)

                st.markdown('<div class="section-label">Generated Code</div>', unsafe_allow_html=True)
                st.code(generated, language="python")

                with st.spinner("Auto-reviewing..."):
                    r = run_ruff(generated)
                    b = run_bandit(generated)

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown('<div class="section-label">Static Analysis</div>', unsafe_allow_html=True)
                    if r:
                        for i in r:
                            st.error(f"Line {i['location']['row']}: `{i['code']}` — {i['message']}")
                    if b:
                        for i in b:
                            fn = st.error if i['issue_severity'] == "HIGH" else st.warning
                            fn(f"Line {i['line_number']}: `{i['test_id']}` — {i['issue_text']} [{i['issue_severity']}]")
                    if not r and not b:
                        st.success("✓ No issues found")

                with col2:
                    st.markdown('<div class="section-label">LLM Review</div>', unsafe_allow_html=True)
                    with st.spinner("Reviewing..."):
                        review = ask_llm(generated, r, b, "static_llm")
                    st.markdown(review)

                record_metric("static_llm", len(r), len(b), bool(r or b))

                st.download_button("⬇ Download Code", data=generated,
                                   file_name="generated_code.py", mime="text/plain")

    with complete_tab:
        st.markdown("<p style='color:#666;font-family:DM Mono,monospace;font-size:0.8rem;'>Paste partial code — AI completes it, then auto-reviews.</p>", unsafe_allow_html=True)
        partial = st.text_area(
            "Partial code:",
            placeholder="def calculate_fibonacci(n):\n    # complete this...",
            height=220
        )
        if st.button("🔄 Complete & Review", key="complete_btn"):
            if not partial.strip():
                st.warning("Please paste some partial code.")
            else:
                with st.spinner("Completing code..."):
                    completed = complete_code(partial)

                st.markdown('<div class="section-label">Completed Code</div>', unsafe_allow_html=True)
                st.code(completed, language="python")

                with st.spinner("Auto-reviewing..."):
                    r = run_ruff(completed)
                    b = run_bandit(completed)

                if r or b:
                    st.markdown('<div class="section-label">Issues Found</div>', unsafe_allow_html=True)
                    for i in r:
                        st.error(f"Line {i['location']['row']}: `{i['code']}` — {i['message']}")
                    for i in b:
                        fn = st.error if i['issue_severity'] == "HIGH" else st.warning
                        fn(f"Line {i['line_number']}: `{i['test_id']}` — {i['issue_text']} [{i['issue_severity']}]")

                    st.markdown('<div class="section-label">Fixed Version</div>', unsafe_allow_html=True)
                    with st.spinner("Fixing..."):
                        fixed = generate_fixed_code(completed, r, b)
                    st.code(fixed, language="python")
                    st.download_button("⬇ Download Fixed", data=fixed,
                                       file_name="completed_fixed.py", mime="text/plain")
                else:
                    st.success("✅ Completed code is clean — no issues found!")
                    st.download_button("⬇ Download", data=completed,
                                       file_name="completed_code.py", mime="text/plain")

                record_metric("static_llm", len(r), len(b), bool(r or b))
