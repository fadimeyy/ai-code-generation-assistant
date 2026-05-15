import os
import subprocess
import json
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def run_ruff(filepath):
    result = subprocess.run(
        ["ruff", "check", filepath, "--output-format=json"],
        capture_output=True, text=True
    )
    try:
        return json.loads(result.stdout)
    except:
        return []

def run_bandit(filepath):
    result = subprocess.run(
        ["bandit", "-r", filepath, "-f", "json", "-q"],
        capture_output=True, text=True
    )
    try:
        return json.loads(result.stdout).get("results", [])
    except:
        return []

def ask_llm(code, ruff_issues, bandit_issues):
    findings = ""
    for i in ruff_issues:
        findings += f"- Ruff {i['code']}: {i['message']} (satir {i['location']['row']})\n"
    for i in bandit_issues:
        findings += f"- Bandit {i['test_id']}: {i['issue_text']} (satir {i['line_number']}, severity: {i['issue_severity']})\n"

    prompt = f"""You are an expert code reviewer. Review the following Python code.


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
if __name__ == "__main__":
    filepath = "sample.py"

    with open(filepath, "r") as f:
        code = f.read()

    ruff_issues = run_ruff(filepath)
    bandit_issues = run_bandit(filepath)

    print(f"Ruff bulgulari: {len(ruff_issues)}")
    for issue in ruff_issues:
        print(f"  - {issue['code']}: {issue['message']} (satir {issue['location']['row']})")

    print(f"\nBandit bulgulari: {len(bandit_issues)}")
    for issue in bandit_issues:
        print(f"  - {issue['test_id']}: {issue['issue_text']} (satir {issue['line_number']}, severity: {issue['issue_severity']})")

    print("\n--- LLM REVIEW ---")
    llm_output = ask_llm(code, ruff_issues, bandit_issues)
    print(llm_output)

    