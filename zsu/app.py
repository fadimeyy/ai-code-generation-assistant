import os
import subprocess
import json
import streamlit as st
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def run_ruff(code):
    with open("temp_review.py", "w") as f:
        f.write(code)
    result = subprocess.run(
        ["ruff", "check", "temp_review.py", "--output-format=json"],
        capture_output=True, text=True
    )
    try:
        return json.loads(result.stdout)
    except:
        return []

def run_bandit(code):
    with open("temp_review.py", "w") as f:
        f.write(code)
    result = subprocess.run(
        ["bandit", "-r", "temp_review.py", "-f", "json", "-q"],
        capture_output=True, text=True
    )
    try:
        return json.loads(result.stdout).get("results", [])
    except:
        return []

def ask_llm(code, ruff_issues, bandit_issues, mode="static_llm"):
    findings = ""
    if mode == "static_llm":
        for i in ruff_issues:
            findings += f"- Ruff {i['code']}: {i['message']} (line {i['location']['row']})\n"
        for i in bandit_issues:
            findings += f"- Bandit {i['test_id']}: {i['issue_text']} (line {i['line_number']}, severity: {i['issue_severity']})\n"

    if mode == "llm_only":
        prompt = f"""You are an expert code reviewer. Review this Python code.

CODE:
{code}

For each issue provide:
- Line number
- Issue description
- Severity (HIGH/MEDIUM/LOW)
- Suggested fix with corrected code
"""
    else:
        prompt = f"""You are an expert code reviewer. Review this Python code using the static analysis findings.

CODE:
{code}

STATIC ANALYSIS FINDINGS:
{findings}

For each issue provide:
- Line number
- Issue description
- Severity (HIGH/MEDIUM/LOW)
- Suggested fix with corrected code
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

def generate_fixed_code(code, ruff_issues, bandit_issues):
    findings = ""
    for i in ruff_issues:
        findings += f"- Ruff {i['code']}: {i['message']} (line {i['location']['row']})\n"
    for i in bandit_issues:
        findings += f"- Bandit {i['test_id']}: {i['issue_text']} (line {i['line_number']}, severity: {i['issue_severity']})\n"

    prompt = f"""You are an expert Python developer.
Fix ALL the issues in the code below based on the static analysis findings.
Return ONLY the fixed Python code, no explanations, no markdown, just clean code.

ORIGINAL CODE:
{code}

ISSUES TO FIX:
{findings}

FIXED CODE:
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

def generate_code_from_description(description):
    prompt = f"""You are an expert Python developer.
Write clean, production-ready Python code based on this description.
Return ONLY the Python code, no explanations, no markdown.

DESCRIPTION:
{description}

CODE:
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

# UI
st.set_page_config(page_title="AI Code Review Bot", layout="wide")
st.title("AI Code Review Assistant")

tab1, tab2 = st.tabs(["Review Code", "Generate & Review"])

with tab1:
    st.markdown("Paste your Python code below and get an AI-powered code review.")
    mode = st.selectbox(
        "Select Review Mode",
        ["llm_only", "static_llm"],
        format_func=lambda x: "LLM Only" if x == "llm_only" else "Static Analysis + LLM"
    )
    code_input = st.text_area("Paste your Python code here:", height=300)

    if st.button("Review Code"):
        if not code_input.strip():
            st.warning("Please paste some code first.")
        else:
            ruff_issues = run_ruff(code_input)
            bandit_issues = run_bandit(code_input)

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Static Analysis Results")
                if ruff_issues:
                    st.markdown("**Ruff Findings:**")
                    for i in ruff_issues:
                        st.error(f"Line {i['location']['row']}: {i['code']} - {i['message']}")
                else:
                    st.success("No Ruff issues found.")
                if bandit_issues:
                    st.markdown("**Bandit Findings:**")
                    for i in bandit_issues:
                        color = st.error if i['issue_severity'] == "HIGH" else st.warning
                        color(f"Line {i['line_number']}: {i['test_id']} - {i['issue_text']} [{i['issue_severity']}]")
                else:
                    st.success("No Bandit issues found.")

            with col2:
                st.subheader("LLM Review")
                with st.spinner("Reviewing..."):
                    llm_output = ask_llm(code_input, ruff_issues, bandit_issues, mode)
                st.markdown(llm_output)

            st.subheader("Generated Fixed Code")
            with st.spinner("Generating fix..."):
                fixed_code = generate_fixed_code(code_input, ruff_issues, bandit_issues)
            st.code(fixed_code, language="python")
            st.download_button(
                label="Download Fixed Code",
                data=fixed_code,
                file_name="fixed_code.py",
                mime="text/plain"
            )

with tab2:
    st.markdown("Describe what you want to build and get generated + reviewed code.")
    description = st.text_area(
        "Describe your code:",
        placeholder="e.g. A login function that checks username and password from a database",
        height=150
    )

    if st.button("Generate & Review"):
        if not description.strip():
            st.warning("Please describe what you want to build.")
        else:
            with st.spinner("Generating code..."):
                generated = generate_code_from_description(description)

            st.subheader("Generated Code")
            st.code(generated, language="python")

            ruff_issues = run_ruff(generated)
            bandit_issues = run_bandit(generated)

            st.subheader("Auto Review Results")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Static Analysis:**")
                if ruff_issues:
                    for i in ruff_issues:
                        st.error(f"Line {i['location']['row']}: {i['code']} - {i['message']}")
                if bandit_issues:
                    for i in bandit_issues:
                        color = st.error if i['issue_severity'] == "HIGH" else st.warning
                        color(f"Line {i['line_number']}: {i['test_id']} - {i['issue_text']} [{i['issue_severity']}]")
                if not ruff_issues and not bandit_issues:
                    st.success("No issues found!")

            with col2:
                st.markdown("**LLM Review:**")
                with st.spinner("Reviewing..."):
                    review = ask_llm(generated, ruff_issues, bandit_issues, "static_llm")
                st.markdown(review)