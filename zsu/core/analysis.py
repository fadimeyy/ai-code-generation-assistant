import os
import subprocess
import json
import shutil
import tempfile
import time
import itertools
import streamlit as st
from dotenv import load_dotenv
from google import genai
from core.database import save_metric_db, load_metrics_db

load_dotenv()

# ── Multi-key rotation ────────────────────────────────────────────────────────
_API_KEYS = [
    v for k, v in os.environ.items()
    if k.startswith("GEMINI_API_KEY") and v and v.strip()
]
if not _API_KEYS:
    fallback = os.getenv("GEMINI_API_KEY")
    if fallback:
        _API_KEYS = [fallback]

_key_iter = itertools.cycle(_API_KEYS)

def _new_client():
    """Return a new Gemini client with the next API key in rotation."""
    return genai.Client(api_key=next(_key_iter))

MODEL = "gemini-2.5-flash"

# ── Robust LLM call with retry ────────────────────────────────────────────────
def llm_call(prompt: str, retries: int = 2) -> str:
    keys = _API_KEYS.copy()
    for key in keys:
        for attempt in range(retries):
            try:
                c = genai.Client(api_key=key)
                response = c.models.generate_content(model=MODEL, contents=prompt)
                return getattr(response, "text", None) or ""
            except Exception as e:
                err = str(e)
                if any(k in err for k in ["429", "quota", "exhausted", "RESOURCE_EXHAUSTED"]):
                    break  # sonraki key
                if any(k in err for k in ["503", "UNAVAILABLE"]) and attempt < retries - 1:
                    time.sleep(2)
                    continue
                return ""
    return ""

def fast_llm_call(prompt: str) -> str:
    """Benchmark LLM call — tries each key in order, moves to next on quota error."""
    keys = _API_KEYS.copy()
    for key in keys:
        for attempt in range(2):
            try:
                c = genai.Client(api_key=key)
                response = c.models.generate_content(model=MODEL, contents=prompt)
                return getattr(response, "text", None) or ""
            except Exception as e:
                err = str(e)
                is_quota = any(k in err for k in ["429", "quota", "exhausted", "RESOURCE_EXHAUSTED"])
                is_transient = any(k in err for k in ["503", "UNAVAILABLE"])
                if is_quota:
                    break  # bu key dolmuş, bir sonraki key'e geç
                if is_transient and attempt == 0:
                    time.sleep(3)
                    continue
                return ""
    return ""  # tüm keyler dolmuş

# ── Static analysis helpers ───────────────────────────────────────────────────
def _write_temp(code: str) -> str:
    """Write code string to a temp .py file, return path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w")
    tmp.write(code)
    tmp.close()
    return tmp.name


def run_ruff(code_or_path: str) -> list:
    """Run ruff on code string or file path. Returns list of issue dicts."""
    is_file = os.path.isfile(code_or_path)
    path = code_or_path if is_file else _write_temp(code_or_path)
    try:
        result = subprocess.run(
            ["ruff", "check", path, "--output-format=json"],
            capture_output=True, text=True
        )
        issues = json.loads(result.stdout) if result.stdout.strip() else []
        return issues
    except Exception:
        return []
    finally:
        if not is_file:
            try: os.unlink(path)
            except: pass


def run_bandit(code_or_path: str) -> list:
    """Run bandit on code string or file path. Returns list of issue dicts."""
    is_file = os.path.isfile(code_or_path)
    path = code_or_path if is_file else _write_temp(code_or_path)
    try:
        result = subprocess.run(
            ["bandit", "-r", path, "-f", "json", "-q"],
            capture_output=True, text=True
        )
        data = json.loads(result.stdout) if result.stdout.strip() else {}
        return data.get("results", [])
    except Exception:
        return []
    finally:
        if not is_file:
            try: os.unlink(path)
            except: pass


# ── ask_llm ───────────────────────────────────────────────────────────────────
def ask_llm(code: str, ruff_issues: list, bandit_issues: list,
            mode: str = "llm_only", repo_context: str = "") -> str:
    """
    Build prompt based on mode and call LLM.
    Returns LLM text or "" on failure.
    """
    findings = ""
    if mode != "llm_only":
        for i in ruff_issues:
            findings += f"- Ruff {i['code']}: {i['message']} (line {i['location']['row']})\n"
        for i in bandit_issues:
            findings += (
                f"- Bandit {i['test_id']}: {i['issue_text']} "
                f"(line {i['line_number']}, severity: {i['issue_severity']})\n"
            )

    static_section = (
        f"\nSTATIC ANALYSIS FINDINGS:\n{findings}\n"
        if findings else "\nSTATIC ANALYSIS FINDINGS: None\n"
    )

    repo_section = (
        f"\nREPO CONTEXT (related files):\n{repo_context[:3000]}\n"
        if repo_context else ""
    )

    prompt = f"""You are an expert Python code reviewer. Review the following code carefully.

CODE:
{code}
{static_section if mode != "llm_only" else ""}
{repo_section}
For EACH issue found, provide:
- Line number
- Issue type (e.g. SQL Injection, Hardcoded Password, Bare Exception)
- Severity: HIGH / MEDIUM / LOW
- Brief explanation
- Suggested fix

Be specific and mention the exact issue names (e.g. "sql injection", "hardcoded password",
"eval", "pickle", "md5", "shell=True", "yaml.load", "bare except", "mutable default argument",
"magic number", "unused import", "wildcard import", "resource leak", "race condition", etc.)
"""
    return llm_call(prompt)


# ── Code generation ───────────────────────────────────────────────────────────
def generate_code_from_description(description: str) -> str:
    prompt = f"""You are an expert Python developer.
Write clean, production-ready Python code based on this description.
Return ONLY the Python code, no explanations, no markdown.

DESCRIPTION:
{description}

CODE:"""
    return llm_call(prompt)


def complete_code(partial_code: str) -> str:
    prompt = f"""You are an expert Python developer.
Complete the following partial Python code. Return ONLY the complete Python code.

PARTIAL CODE:
{partial_code}

COMPLETED CODE:"""
    return llm_call(prompt)


def generate_fixed_code(code: str, ruff_issues: list, bandit_issues: list) -> str:
    findings = ""
    for i in ruff_issues:
        findings += f"- Ruff {i['code']}: {i['message']} (line {i['location']['row']})\n"
    for i in bandit_issues:
        findings += (
            f"- Bandit {i['test_id']}: {i['issue_text']} "
            f"(line {i['line_number']}, severity: {i['issue_severity']})\n"
        )
    prompt = f"""You are an expert Python developer.
Fix ALL the issues in the code below. Return ONLY the fixed Python code, no markdown.

ORIGINAL CODE:
{code}

ISSUES TO FIX:
{findings or "Apply general best practices."}

FIXED CODE:"""
    return llm_call(prompt)


# ── Chat ──────────────────────────────────────────────────────────────────────
def chat_with_code(user_message: str, code_context: str, history: list) -> str:
    history_text = ""
    for msg in history[-6:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{role}: {msg['content'][:300]}\n"

    prompt = f"""You are a helpful Python coding assistant.

CONVERSATION HISTORY:
{history_text}

{"CODE CONTEXT:" + chr(10) + code_context[:2000] if code_context.strip() else ""}

User: {user_message}
Answer:"""
    return llm_call(prompt)


# ── Repo context ──────────────────────────────────────────────────────────────
def get_repo_context(repo_url: str, changed_file: str = "") -> str:
    """Clone repo and read relevant files. Returns context string."""
    if not repo_url.startswith("https://github.com/"):
        return ""
    tmpdir = tempfile.mkdtemp()
    try:
        subprocess.run(
            ["git", "clone", "--depth=1", repo_url, tmpdir],
            capture_output=True, timeout=30
        )
        context = ""
        for root, _, files in os.walk(tmpdir):
            if ".git" in root:
                continue
            for fn in files:
                if fn.endswith(".py") and len(context) < 4000:
                    try:
                        with open(os.path.join(root, fn)) as f:
                            context += f"\n# {fn}\n" + f.read()[:800]
                    except:
                        pass
        return context[:4000]
    except:
        return ""
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── Metrics ───────────────────────────────────────────────────────────────────
def record_metric(mode: str, ruff: int, bandit: int, llm_found: bool):
    save_metric_db(mode, ruff, bandit, llm_found)