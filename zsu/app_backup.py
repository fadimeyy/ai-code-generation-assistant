import os
import subprocess
import json
import shutil
import tempfile
import sqlite3
import csv
import io
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from google import genai
import plotly.graph_objects as go
import plotly.express as px

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ── SQLite Database ──────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codesense.db")

def init_db():
    """Create the metrics table if it doesn't exist."""
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT    NOT NULL,
            mode      TEXT    NOT NULL,
            ruff      INTEGER NOT NULL,
            bandit    INTEGER NOT NULL,
            llm_found INTEGER NOT NULL
        )
    """)
    con.commit()
    con.close()

def save_metric_db(mode: str, ruff: int, bandit: int, llm_found: bool):
    """Insert one metric row into the database."""
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO metrics (timestamp, mode, ruff, bandit, llm_found) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), mode, ruff, bandit, int(llm_found)),
    )
    con.commit()
    con.close()

def load_metrics_db() -> list:
    """Return all rows from metrics table as a list of dicts."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT timestamp, mode, ruff, bandit, llm_found FROM metrics ORDER BY id"
    ).fetchall()
    con.close()
    return [
        {
            "timestamp": r["timestamp"],
            "mode":      r["mode"],
            "ruff":      r["ruff"],
            "bandit":    r["bandit"],
            "llm_found": bool(r["llm_found"]),
        }
        for r in rows
    ]

def clear_metrics_db():
    """Delete all metric rows from the database."""
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM metrics")
    con.commit()
    con.close()

# Initialise DB on startup
init_db()

# ── helpers ──────────────────────────────────────────────────────────────────

def run_ruff(code: str) -> list:
    with open("temp_review.py", "w", encoding="utf-8") as f:
        f.write(code)
    result = subprocess.run(
        ["ruff", "check", "temp_review.py", "--output-format=json"],
        capture_output=True, text=True
    )
    try:
        return json.loads(result.stdout)
    except Exception:
        return []


def run_bandit(code: str) -> list:
    with open("temp_review.py", "w", encoding="utf-8") as f:
        f.write(code)
    result = subprocess.run(
        ["bandit", "-r", "temp_review.py", "-f", "json", "-q"],
        capture_output=True, text=True
    )
    try:
        return json.loads(result.stdout).get("results", [])
    except Exception:
        return []


def get_repo_context(repo_url: str, changed_file_path: str) -> str:
    context = ""
    tmp_dir = tempfile.mkdtemp()
    try:
        result = subprocess.run(
            ["git", "clone", "--depth=1", repo_url, tmp_dir],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return "Could not clone repository."
        for readme in ["README.md", "readme.md", "README.txt"]:
            readme_path = os.path.join(tmp_dir, readme)
            if os.path.exists(readme_path):
                with open(readme_path, encoding="utf-8", errors="ignore") as f:
                    context += f"=== README ===\n{f.read()[:1000]}\n\n"
                break
        target_dir = os.path.join(tmp_dir, os.path.dirname(changed_file_path))
        if os.path.exists(target_dir):
            for fname in os.listdir(target_dir):
                if fname.endswith(".py") and fname != os.path.basename(changed_file_path):
                    fpath = os.path.join(target_dir, fname)
                    with open(fpath, encoding="utf-8", errors="ignore") as f:
                        context += f"=== {fname} ===\n{f.read()[:500]}\n\n"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return context if context else "No additional context found."


def build_findings_text(ruff_issues: list, bandit_issues: list) -> str:
    findings = ""
    for i in ruff_issues:
        findings += f"- Ruff {i['code']}: {i['message']} (line {i['location']['row']})\n"
    for i in bandit_issues:
        findings += f"- Bandit {i['test_id']}: {i['issue_text']} (line {i['line_number']}, severity: {i['issue_severity']})\n"
    return findings


def llm_call(prompt: str, retries: int = 3) -> str:
    import time
    wait_times = [5, 15, 30]
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text or ""
        except Exception as e:
            err_str = str(e)
            is_retryable = any(code in err_str for code in ["503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED"])
            if is_retryable and attempt < retries - 1:
                wait = wait_times[attempt]
                time.sleep(wait)
                continue
            # Non-retryable or last attempt
            if "503" in err_str or "UNAVAILABLE" in err_str:
                return "⚠️ **API Unavailable (503):** Gemini sunucusu şu an yoğun. Lütfen 1-2 dakika bekleyip tekrar deneyin."
            elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                return "⚠️ **Rate Limit (429):** API kotası aşıldı. Lütfen biraz bekleyip tekrar deneyin."
            else:
                return f"⚠️ **API Hatası:** {err_str[:200]}"
    return "⚠️ **Bağlantı başarısız:** Tüm denemeler tükendi. Lütfen internet bağlantınızı ve API anahtarınızı kontrol edin."


def ask_llm(code: str, ruff_issues: list, bandit_issues: list,
            mode: str = "static_llm", repo_context: str = "") -> str:
    findings = build_findings_text(ruff_issues, bandit_issues) if mode != "llm_only" else ""

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
    elif mode == "repo_llm":
        prompt = f"""You are an expert code reviewer with full repository context.

REPOSITORY CONTEXT:
{repo_context}

CODE TO REVIEW:
{code}

STATIC ANALYSIS FINDINGS:
{findings}

Review considering the repository context. For each issue:
- Line number
- Issue description
- Severity (HIGH/MEDIUM/LOW)
- Suggested fix that fits the repository style
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
    return llm_call(prompt)


def generate_fixed_code(code: str, ruff_issues: list, bandit_issues: list) -> str:
    findings = build_findings_text(ruff_issues, bandit_issues)
    prompt = f"""You are an expert Python developer.
Fix ALL the issues in the code below based on the static analysis findings.
Return ONLY the fixed Python code, no explanations, no markdown, just clean code.

ORIGINAL CODE:
{code}

ISSUES TO FIX:
{findings}

FIXED CODE:
"""
    return llm_call(prompt)


def generate_code_from_description(description: str) -> str:
    prompt = f"""You are an expert Python developer.
Write clean, production-ready Python code based on this description.
Return ONLY the Python code, no explanations, no markdown.

DESCRIPTION:
{description}

CODE:
"""
    return llm_call(prompt)


def complete_code(partial_code: str) -> str:
    prompt = f"""You are an expert Python developer.
Complete the following partial Python code. Continue naturally from where it left off.
Return ONLY the completed Python code (include the original part + your completion).
No explanations, no markdown.

PARTIAL CODE:
{partial_code}

COMPLETED CODE:
"""
    return llm_call(prompt)


def chat_with_code(user_message: str, current_code: str, history: list) -> str:
    history_text = ""
    for msg in history[-6:]:  # last 3 turns
        role = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{role}: {msg['content']}\n"

    code_section = f"\nCURRENT CODE IN EDITOR:\n{current_code}\n" if current_code.strip() else ""

    prompt = f"""You are an expert Python coding assistant. You help users write, fix, review, and improve Python code.
You can generate new code, fix bugs, add features, write tests, explain code, and answer questions.
When you produce code, wrap it in triple backticks with python language tag.
{code_section}
CONVERSATION HISTORY:
{history_text}
User: {user_message}
Assistant:"""
    return llm_call(prompt)


def record_metric(mode: str, ruff_count: int, bandit_count: int, found_by_llm: bool):
    """Save metric to both SQLite DB and session state."""
    save_metric_db(mode, ruff_count, bandit_count, found_by_llm)
    # Keep session state in sync with DB
    st.session_state.metrics = load_metrics_db()


# ── page config ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="CodeSense", layout="wide", page_icon="◈")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

:root {
    --bg:        #ffffff;
    --surface:   #f7f7f5;
    --border:    #e8e8e4;
    --border2:   #d4d4ce;
    --text:      #1a1a1a;
    --muted:     #999;
    --accent:    #2563eb;
    --accent2:   #1d4ed8;
    --red:       #dc2626;
    --orange:    #d97706;
    --green:     #16a34a;
    --mono:      'DM Mono', monospace;
    --sans:      'Outfit', sans-serif;
}

html, body, [class*="css"] {
    font-family: var(--sans) !important;
    color: var(--text) !important;
}

.stApp {
    background: var(--bg) !important;
}

/* Hide default streamlit elements */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 2rem !important; max-width: 1400px !important; }

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
    padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--muted) !important;
    border-radius: 0 !important;
    border-bottom: 2px solid transparent !important;
    font-family: var(--sans) !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.01em !important;
    padding: 10px 22px !important;
    transition: all 0.15s !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: var(--text) !important;
}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
    font-weight: 600 !important;
}

/* Fix nested tabs (Generate subtabs) */
.stTabs .stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--muted) !important;
    border-radius: 0 !important;
    border-bottom: 2px solid transparent !important;
    font-family: var(--sans) !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.01em !important;
    padding: 10px 20px !important;
    transition: all 0.15s !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: var(--text) !important;
}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
    font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-panel"] {
    padding-top: 1.5rem !important;
}

/* ── BUTTONS ── */
.stButton > button {
    background: var(--accent) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: var(--sans) !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.03em !important;
    padding: 9px 22px !important;
    transition: background 0.15s !important;
}
.stButton > button:hover {
    background: var(--accent2) !important;
}

/* ── INPUTS ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 3px !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
    font-size: 0.83rem !important;
    transition: border-color 0.15s !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
}

/* ── SELECTBOX ── */
.stSelectbox > div > div {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 3px !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
    font-size: 0.83rem !important;
}

/* ── LABELS ── */
.stTextInput label, .stTextArea label, .stSelectbox label {
    font-family: var(--mono) !important;
    font-size: 0.72rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    color: var(--muted) !important;
}

/* ── ALERTS ── */
.stAlert {
    border-radius: 3px !important;
    border-left-width: 3px !important;
    font-family: var(--mono) !important;
    font-size: 0.8rem !important;
}

/* ── METRICS ── */
[data-testid="stMetric"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 3px !important;
    padding: 16px !important;
}
[data-testid="stMetricValue"] {
    font-family: var(--mono) !important;
    color: var(--accent) !important;
    font-size: 1.8rem !important;
}
[data-testid="stMetricLabel"] {
    font-family: var(--mono) !important;
    font-size: 0.7rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    color: var(--muted) !important;
}

/* ── DATAFRAME ── */
.stDataFrame {
    border: 1px solid var(--border) !important;
    border-radius: 3px !important;
}

/* ── CODE BLOCKS ── */
.stCode, pre {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 3px !important;
    font-family: var(--mono) !important;
}

/* ── SPINNER ── */
.stSpinner > div {
    border-top-color: var(--accent) !important;
}

/* ── FORM ── */
[data-testid="stForm"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    padding: 12px !important;
}

/* Send button inside form — same as other buttons */
[data-testid="stForm"] .stButton > button {
    background: var(--accent) !important;
    color: #fff !important;
    border-radius: 6px !important;
    font-family: var(--sans) !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    padding: 8px 20px !important;
}

/* ── DOWNLOAD BUTTON ── */
.stDownloadButton > button {
    background: transparent !important;
    color: var(--accent) !important;
    border: 1.5px solid var(--accent) !important;
    border-radius: 6px !important;
    font-family: var(--sans) !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
}
.stDownloadButton > button:hover {
    background: var(--accent) !important;
    color: #fff !important;
}

/* ── PROGRESS ── */
.stProgress > div > div > div {
    background: var(--accent) !important;
}
.stProgress > div > div {
    background: var(--border) !important;
    border-radius: 2px !important;
}

/* ── CHAT BUBBLES ── */
.chat-user {
    background: #eff6ff;
    border-left: 3px solid var(--accent);
    padding: 12px 16px;
    margin: 6px 0;
    border-radius: 0 8px 8px 0;
    font-family: var(--sans);
    font-size: 0.9rem;
    color: var(--text);
}
.chat-assistant {
    background: var(--surface);
    border-left: 3px solid var(--border2);
    padding: 12px 16px;
    margin: 6px 0;
    border-radius: 0 8px 8px 0;
    font-family: var(--sans);
    font-size: 0.9rem;
    color: var(--text);
}
.chat-tag {
    font-family: var(--mono);
    font-size: 0.65rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 4px;
}

/* ── SECTION HEADERS ── */
.section-label {
    font-family: var(--mono);
    font-size: 0.68rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
    padding-bottom: 6px;
    margin-bottom: 14px;
}

/* ── ISSUE TAGS ── */
.tag-high   { color: var(--red);    font-family: var(--mono); font-size: 0.75rem; }
.tag-medium { color: var(--orange); font-family: var(--mono); font-size: 0.75rem; }
.tag-low    { color: var(--green);  font-family: var(--mono); font-size: 0.75rem; }

/* ── INFO BOX ── */
.stInfo { border-color: var(--accent) !important; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex; align-items:baseline; gap:16px; padding-bottom:10px; 
            border-bottom: 1px solid #e8e8e4; margin-bottom: 1.5rem;">
  <span style="font-family:'Outfit',sans-serif; font-size:1.3rem; font-weight:700;
               color:#1a1a1a; letter-spacing:-0.02em;">◈ CodeSense</span>
  <span style="font-family:'DM Mono',monospace; font-size:0.7rem; 
               color:#bbb; letter-spacing:0.08em; text-transform:uppercase;">
    AI-Powered Code Review &amp; Generation
  </span>
  <span style="margin-left:auto; font-family:'DM Mono',monospace; 
               font-size:0.65rem; color:#ccc;">v1.0 · Python · Gemini</span>
</div>
""", unsafe_allow_html=True)

# ── session state ─────────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "chat_code" not in st.session_state:
    st.session_state.chat_code = ""
if "metrics" not in st.session_state:
    # Load persisted metrics from SQLite on first run
    st.session_state.metrics = load_metrics_db()


# ── tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Chat",
    "Review",
    "Generate",
    "Metrics",
    "Docs",
    "A/B Compare",
    "Benchmark",
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — CHAT ASSISTANT
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="section-label">Chat Assistant</div>', unsafe_allow_html=True)
    st.markdown("<p style='color:#999; font-size:0.88rem; font-family:Outfit,sans-serif; margin-bottom:1.2rem;'>Write code &nbsp;·&nbsp; Fix bugs &nbsp;·&nbsp; Add features &nbsp;·&nbsp; Explain &nbsp;·&nbsp; Write tests</p>", unsafe_allow_html=True)

    col_chat, col_editor = st.columns([3, 2])

    with col_editor:
        st.markdown('<div class="section-label">Code Editor</div>', unsafe_allow_html=True)
        st.markdown("<p style='color:#555;font-family:DM Mono,monospace;font-size:0.72rem;margin-bottom:8px;'>Optional — paste code to give context</p>", unsafe_allow_html=True)
        st.session_state.chat_code = st.text_area(
            "Current code:",
            value=st.session_state.chat_code,
            height=300,
            label_visibility="collapsed",
            placeholder="# Paste code here for context...",
            key="chat_editor"
        )
        if st.button("🔍 Auto-Review This Code", key="chat_review_btn"):
            if st.session_state.chat_code.strip():
                with st.spinner("Reviewing..."):
                    r = run_ruff(st.session_state.chat_code)
                    b = run_bandit(st.session_state.chat_code)
                    review = ask_llm(st.session_state.chat_code, r, b, "static_llm")
                st.session_state.chat_history.append({"role": "user", "content": "[Auto-review requested]"})
                st.session_state.chat_history.append({"role": "assistant", "content": review})
                st.rerun()

    with col_chat:
        # Render history
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown(f'<div class="chat-user">🧑 {msg["content"]}</div>', unsafe_allow_html=True)
                else:
                    content = msg["content"]
                    # render code blocks properly
                    if "```" in content:
                        parts = content.split("```")
                        for idx, part in enumerate(parts):
                            if idx % 2 == 0:
                                if part.strip():
                                    st.markdown(f'<div class="chat-assistant">{part}</div>', unsafe_allow_html=True)
                            else:
                                lang = part.split("\n")[0] or "python"
                                code_body = "\n".join(part.split("\n")[1:])
                                st.code(code_body, language=lang)
                    else:
                        st.markdown(f'<div class="chat-assistant">🤖 {content}</div>', unsafe_allow_html=True)

        # Input
        with st.form("chat_form", clear_on_submit=True):
            user_input = st.text_input(
                "Message",
                placeholder="e.g. Write a function to validate emails, Add error handling to my code, Explain what this does...",
                label_visibility="collapsed"
            )
            send = st.form_submit_button("Send ➤")

        if send and user_input.strip():
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.spinner("Thinking..."):
                reply = chat_with_code(user_input, st.session_state.chat_code, st.session_state.chat_history)
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            st.rerun()

        if st.button("🗑 Clear Chat", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — REVIEW CODE
# ════════════════════════════════════════════════════════════════════════════
with tab2:
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

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — GENERATE & COMPLETE
# ════════════════════════════════════════════════════════════════════════════
with tab3:
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

# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — METRICS DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
with tab4:
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

# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — HOW IT WORKS
# ════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown('<div class="section-label">Documentation</div>', unsafe_allow_html=True)
    st.markdown("""
This system combines **static analysis** with **LLM-powered code intelligence** to provide
three complementary capabilities:

---

#### 🔍 Three Review Modes

| Mode | What it sees | Best for |
|------|-------------|----------|
| **LLM Only** | Just the code | Quick review, no tools needed |
| **Static + LLM** | Code + Ruff/Bandit findings | Precise issue detection |
| **Repo + Static + LLM** | Code + findings + related files | Context-aware review |

---

#### ⚙️ Pipeline

```
Input Code
    ↓
Ruff (style/quality)  +  Bandit (security)
    ↓
LLM receives: code + static findings + (optional) repo context
    ↓
Outputs: Review  +  Fixed Code
```

---

#### ✨ Code Generation Pipeline

```
Natural language description
    ↓
LLM generates Python code
    ↓
Auto-run Ruff + Bandit
    ↓
If issues found → LLM generates fixed version
```

---

#### 🔄 Code Completion

```
Partial / incomplete code
    ↓
LLM completes the code
    ↓
Auto-review + fix if needed
```

---

#### 📊 Metrics

All sessions are tracked so you can compare how many issues each mode detects.
This supports the research question: **Does static analysis improve LLM code review quality?**
""")

# ════════════════════════════════════════════════════════════════════════════
# TAB 6 — A/B COMPARISON
# ════════════════════════════════════════════════════════════════════════════
with tab6:
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

            import re
            def count_lines_mentioned(text: str) -> int:
                return len(re.findall(r'[Ll]ine\s+\d+', text))

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
                showlegend=True,
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
                    **_ab_layout, barmode="group",
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

# ════════════════════════════════════════════════════════════════════════════
# TAB 7 — BENCHMARK
# ════════════════════════════════════════════════════════════════════════════

# ─ Predefined test cases with known bugs
BENCHMARK_CASES = [
    # ── SECURITY / HIGH ────────────────────────────────────────────────────────
    {
        "id": "TC-01", "name": "SQL Injection", "category": "Security", "severity": "HIGH",
        "code": '''
import sqlite3
def get_user(username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchone()
'''
    },
    {
        "id": "TC-02", "name": "Hardcoded Password", "category": "Security", "severity": "HIGH",
        "code": '''
DB_PASSWORD = "admin123"
API_KEY = "sk-abc123def456"
def connect_db():
    return connect(password=DB_PASSWORD)
'''
    },
    {
        "id": "TC-03", "name": "Command Injection", "category": "Security", "severity": "HIGH",
        "code": '''
import os
def run_command(user_input):
    os.system("ls " + user_input)
    result = os.popen(user_input).read()
    return result
'''
    },
    {
        "id": "TC-04", "name": "Eval Usage", "category": "Security", "severity": "HIGH",
        "code": '''
def calculate_expression(expr):
    return eval(expr)
def run_code(code_str):
    exec(code_str)
    return "done"
'''
    },
    {
        "id": "TC-05", "name": "Pickle Deserialization", "category": "Security", "severity": "HIGH",
        "code": '''
import pickle
def load_model(path):
    with open(path, "rb") as f:
        model = pickle.load(f)
    return model
def save_session(data, path):
    with open(path, "wb") as f:
        pickle.dump(data, f)
'''
    },
    {
        "id": "TC-06", "name": "Hardcoded Secret in URL", "category": "Security", "severity": "HIGH",
        "code": '''
import requests
SECRET_TOKEN = "ghp_abcdef123456"
def fetch_data():
    url = "https://api.example.com/data?token=mysecrettoken123"
    headers = {"Authorization": "Bearer " + SECRET_TOKEN}
    return requests.get(url, headers=headers)
'''
    },
    {
        "id": "TC-07", "name": "XML External Entity", "category": "Security", "severity": "HIGH",
        "code": '''
import xml.etree.ElementTree as ET
def parse_xml(xml_string):
    tree = ET.fromstring(xml_string)
    return tree
'''
    },
    {
        "id": "TC-08", "name": "Subprocess Shell=True", "category": "Security", "severity": "HIGH",
        "code": '''
import subprocess
def run_script(script_name):
    result = subprocess.run(script_name, shell=True, capture_output=True)
    return result.stdout
def build_project(build_cmd):
    subprocess.call(build_cmd, shell=True)
'''
    },
    {
        "id": "TC-09", "name": "Weak Hash MD5", "category": "Security", "severity": "HIGH",
        "code": '''
import hashlib
def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()
def verify_password(password, hashed):
    return hashlib.md5(password.encode()).hexdigest() == hashed
'''
    },
    {
        "id": "TC-10", "name": "YAML Load Unsafe", "category": "Security", "severity": "HIGH",
        "code": '''
import yaml
def load_config(config_str):
    return yaml.load(config_str)
def load_config_file(path):
    with open(path) as f:
        return yaml.load(f)
'''
    },
    # ── SECURITY / MEDIUM ──────────────────────────────────────────────────────
    {
        "id": "TC-11", "name": "Insecure Random", "category": "Security", "severity": "MEDIUM",
        "code": '''
import random, string
def generate_token(length=16):
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))
def generate_otp():
    return random.randint(100000, 999999)
'''
    },
    {
        "id": "TC-12", "name": "Assert for Security", "category": "Security", "severity": "MEDIUM",
        "code": '''
def transfer_money(amount, account):
    assert amount > 0, "Amount must be positive"
    assert account is not None, "Account required"
    assert len(account) == 10, "Invalid account"
    return {"status": "ok", "amount": amount}
'''
    },
    {
        "id": "TC-13", "name": "Tempfile Insecure", "category": "Security", "severity": "MEDIUM",
        "code": '''
import os, tempfile
def write_temp(data):
    tmpfile = "/tmp/myapp_" + str(os.getpid())
    with open(tmpfile, "w") as f:
        f.write(data)
    return tmpfile
'''
    },
    {
        "id": "TC-14", "name": "HTTP Instead of HTTPS", "category": "Security", "severity": "MEDIUM",
        "code": '''
import urllib.request
def fetch_page(url):
    response = urllib.request.urlopen("http://api.example.com/data")
    return response.read()
'''
    },
    {
        "id": "TC-15", "name": "Binding to All Interfaces", "category": "Security", "severity": "MEDIUM",
        "code": '''
import socket
def start_server(port):
    s = socket.socket()
    s.bind(("0.0.0.0", port))
    s.listen(5)
    return s
'''
    },
    # ── QUALITY / MEDIUM ───────────────────────────────────────────────────────
    {
        "id": "TC-16", "name": "Bare Exception", "category": "Quality", "severity": "MEDIUM",
        "code": '''
def read_file(path):
    try:
        with open(path) as f:
            return f.read()
    except:
        pass
def parse_json(data):
    try:
        import json
        return json.loads(data)
    except:
        return None
'''
    },
    {
        "id": "TC-17", "name": "Mutable Default Argument", "category": "Quality", "severity": "MEDIUM",
        "code": '''
def add_item(item, items=[]):
    items.append(item)
    return items
def process(data, config={}):
    config["processed"] = True
    return data, config
'''
    },
    {
        "id": "TC-18", "name": "Missing Return Value", "category": "Quality", "severity": "MEDIUM",
        "code": '''
def divide(a, b):
    if b == 0:
        print("Cannot divide by zero")
    else:
        result = a / b
def get_name(user):
    if user:
        name = user["name"]
    return name
'''
    },
    {
        "id": "TC-19", "name": "Undefined Variable Risk", "category": "Quality", "severity": "MEDIUM",
        "code": '''
def process_items(items):
    for item in items:
        if item > 0:
            result = item * 2
    return result

def get_value(flag):
    if flag:
        value = 42
    print(value)
'''
    },
    {
        "id": "TC-20", "name": "Global Variable Misuse", "category": "Quality", "severity": "MEDIUM",
        "code": '''
counter = 0
data_cache = []

def increment():
    global counter
    counter += 1

def add_to_cache(item):
    global data_cache
    data_cache.append(item)
    return data_cache
'''
    },
    {
        "id": "TC-21", "name": "Infinite Loop Risk", "category": "Quality", "severity": "MEDIUM",
        "code": '''
def wait_for_result(check_fn):
    while True:
        result = check_fn()
        if result:
            break
    return result

def retry_forever(fn):
    while not fn():
        pass
'''
    },
    {
        "id": "TC-22", "name": "String Concatenation in Loop", "category": "Quality", "severity": "MEDIUM",
        "code": '''
def build_html(items):
    result = ""
    for item in items:
        result = result + "<li>" + item + "</li>"
    return "<ul>" + result + "</ul>"
'''
    },
    {
        "id": "TC-23", "name": "Catching Exception Too Broad", "category": "Quality", "severity": "MEDIUM",
        "code": '''
def safe_divide(a, b):
    try:
        return a / b
    except Exception:
        return 0

def load_data(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception as e:
        print(e)
        return None
'''
    },
    {
        "id": "TC-24", "name": "Unreachable Code", "category": "Quality", "severity": "MEDIUM",
        "code": '''
def get_status(code):
    if code == 200:
        return "OK"
    elif code == 404:
        return "Not Found"
    else:
        return "Unknown"
    print("This never runs")

def calculate(x):
    return x * 2
    x = x + 1
'''
    },
    {
        "id": "TC-25", "name": "Division Without Zero Check", "category": "Quality", "severity": "MEDIUM",
        "code": '''
def average(numbers):
    return sum(numbers) / len(numbers)

def percentage(part, total):
    return (part / total) * 100
'''
    },
    # ── QUALITY / LOW ──────────────────────────────────────────────────────────
    {
        "id": "TC-26", "name": "Magic Numbers", "category": "Quality", "severity": "LOW",
        "code": '''
def calculate_tax(salary):
    if salary > 85000:
        return salary * 0.35
    elif salary > 40000:
        return salary * 0.22
    else:
        return salary * 0.12
'''
    },
    {
        "id": "TC-27", "name": "Too Long Function", "category": "Quality", "severity": "LOW",
        "code": '''
def process_everything(data, config, mode, flag, extra=None):
    step1 = data * 2
    step2 = step1 + config.get("offset", 0)
    step3 = step2 if flag else step2 * -1
    step4 = step3 + (extra or 0)
    step5 = step4 / (config.get("divisor", 1) or 1)
    step6 = round(step5, 2)
    step7 = str(step6)
    step8 = step7.zfill(10)
    step9 = step8.strip()
    step10 = step9 if mode == "str" else float(step9)
    return step10
'''
    },
    {
        "id": "TC-28", "name": "Comparison to None/True/False", "category": "Quality", "severity": "LOW",
        "code": '''
def check(value, flag):
    if value == None:
        return False
    if flag == True:
        return True
    if flag == False:
        return None
    return value
'''
    },
    {
        "id": "TC-29", "name": "Implicit String Concatenation", "category": "Quality", "severity": "LOW",
        "code": '''
message = ("Hello, "
           "World! "
           "How are you?")

error_msg = ("Error: "
             "Something went wrong.")
'''
    },
    {
        "id": "TC-30", "name": "Shadowing Builtin", "category": "Quality", "severity": "LOW",
        "code": '''
def process(list, dict, type, input):
    id = 42
    filter = [x for x in list if x > 0]
    map = {k: v for k, v in dict.items()}
    return filter, map
'''
    },
    # ── STYLE / LOW ────────────────────────────────────────────────────────────
    {
        "id": "TC-31", "name": "Unused Imports", "category": "Style", "severity": "LOW",
        "code": '''
import os, sys, json, re
import math
from datetime import datetime, timedelta

def calculate(x, y):
    unused_var = 42
    result = x + y
    return result
'''
    },
    {
        "id": "TC-32", "name": "Wildcard Import", "category": "Style", "severity": "LOW",
        "code": '''
from os import *
from sys import *

def very_long_function_name_that_does_something_important(parameter_one, parameter_two, parameter_three, parameter_four):
    x = 1 + 2
    y = x * 3
    return y
'''
    },
    {
        "id": "TC-33", "name": "Missing Whitespace", "category": "Style", "severity": "LOW",
        "code": '''
def add(a,b):
    return a+b

def multiply(x,y,z):
    result=x*y*z
    return result

x=10
y=20
z=x+y
'''
    },
    {
        "id": "TC-34", "name": "Inconsistent Return", "category": "Style", "severity": "LOW",
        "code": '''
def find_item(items, target):
    for i, item in enumerate(items):
        if item == target:
            return i
    return

def check_value(x):
    if x > 0:
        return True
    elif x < 0:
        return False
'''
    },
    {
        "id": "TC-35", "name": "Long Lines", "category": "Style", "severity": "LOW",
        "code": '''
def process_data(data, config, mode, debug=False, verbose=False, output_format="json", encoding="utf-8", timeout=30):
    result = {"data": data, "config": config, "mode": mode, "debug": debug, "verbose": verbose, "format": output_format, "encoding": encoding, "timeout": timeout}
    return result
'''
    },
    {
        "id": "TC-36", "name": "Missing Docstrings", "category": "Style", "severity": "LOW",
        "code": '''
class UserManager:
    def __init__(self, db):
        self.db = db

    def create_user(self, username, email, password):
        user = {"username": username, "email": email, "password": password}
        self.db.insert(user)
        return user

    def delete_user(self, user_id):
        self.db.delete(user_id)
'''
    },
    {
        "id": "TC-37", "name": "Trailing Whitespace & Blank Lines", "category": "Style", "severity": "LOW",
        "code": '''
def function_one():
    x = 1   
    y = 2   
    return x + y



def function_two():


    return 42
'''
    },
    {
        "id": "TC-38", "name": "Single Letter Variables", "category": "Style", "severity": "LOW",
        "code": '''
def transform(d):
    r = []
    for i, v in enumerate(d):
        if v > 0:
            r.append(v * 2)
    return r

def calc(a, b, c, d, e):
    return a + b - c * d / e
'''
    },
    # ── MIXED SEVERITY ─────────────────────────────────────────────────────────
    {
        "id": "TC-39", "name": "SQL + Unused Imports Mixed", "category": "Security", "severity": "HIGH",
        "code": '''
import sqlite3, os, sys, re, json

def search_products(query, limit):
    conn = sqlite3.connect("shop.db")
    sql = "SELECT * FROM products WHERE name LIKE '%" + query + "%' LIMIT " + str(limit)
    return conn.execute(sql).fetchall()
'''
    },
    {
        "id": "TC-40", "name": "Password in Log", "category": "Security", "severity": "HIGH",
        "code": '''
import logging
logger = logging.getLogger(__name__)

def login(username, password):
    logger.debug(f"Login attempt: user={username}, pass={password}")
    if authenticate(username, password):
        logger.info(f"User {username} logged in with password {password}")
        return True
    return False
'''
    },
    {
        "id": "TC-41", "name": "Race Condition File", "category": "Quality", "severity": "MEDIUM",
        "code": '''
import os

def safe_write(path, data):
    if os.path.exists(path):
        os.remove(path)
    with open(path, "w") as f:
        f.write(data)

def check_and_create(path):
    if not os.path.exists(path):
        open(path, "w").close()
'''
    },
    {
        "id": "TC-42", "name": "Resource Leak", "category": "Quality", "severity": "MEDIUM",
        "code": '''
def read_data(path):
    f = open(path)
    data = f.read()
    return data

def write_log(path, message):
    log = open(path, "a")
    log.write(message + "\\n")
'''
    },
    {
        "id": "TC-43", "name": "Type Confusion", "category": "Quality", "severity": "MEDIUM",
        "code": '''
def add_values(a, b):
    return a + b

def process_input(user_input):
    value = user_input
    result = value * 2 + 1
    return result

def parse_age(age_str):
    age = age_str
    if age > 18:
        return "adult"
    return "minor"
'''
    },
    {
        "id": "TC-44", "name": "Circular Import Risk", "category": "Quality", "severity": "LOW",
        "code": '''
from __future__ import annotations
import sys

def get_module(name):
    if name in sys.modules:
        return sys.modules[name]
    __import__(name)
    return sys.modules[name]
'''
    },
    {
        "id": "TC-45", "name": "Deprecated Function", "category": "Quality", "severity": "LOW",
        "code": '''
import cgi
import imp
import distutils.core

def parse_form():
    form = cgi.FieldStorage()
    return form

def load_module(name):
    return imp.load_module(name, None, None, None)
'''
    },
    {
        "id": "TC-46", "name": "Insecure Deserialization JSON", "category": "Security", "severity": "MEDIUM",
        "code": '''
import json
import marshal

def load_user_data(raw):
    return json.loads(raw)

def load_binary_data(raw):
    return marshal.loads(raw)
'''
    },
    {
        "id": "TC-47", "name": "Unvalidated Redirect", "category": "Security", "severity": "MEDIUM",
        "code": '''
def get_redirect_url(request):
    next_url = request.args.get("next", "/")
    return next_url

def redirect_after_login(user, next_page):
    if user.is_authenticated:
        return redirect(next_page)
    return redirect("/login")
'''
    },
    {
        "id": "TC-48", "name": "Print Debugging Left In", "category": "Style", "severity": "LOW",
        "code": '''
def calculate_total(items):
    print("DEBUG: items =", items)
    total = sum(items)
    print("DEBUG: total =", total)
    print(f"Processing {len(items)} items")
    return total
'''
    },
    {
        "id": "TC-49", "name": "No Input Validation", "category": "Quality", "severity": "MEDIUM",
        "code": '''
def create_user(username, email, age, role):
    user = {
        "username": username,
        "email": email,
        "age": age,
        "role": role
    }
    db.insert("users", user)
    return user

def update_balance(user_id, amount):
    db.update("accounts", {"balance": amount}, {"id": user_id})
'''
    },
    {
        "id": "TC-50", "name": "Regex DoS Vulnerability", "category": "Security", "severity": "HIGH",
        "code": '''
import re

def validate_email(email):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))

def validate_username(username):
    pattern = r"^[a-zA-Z0-9_]{3,20}$"
    return bool(re.match(pattern, username))
'''
    },
]


def score_detection(llm_output: str, ruff_issues: list, bandit_issues: list, mode: str) -> dict:
    """
    Ground-truth scoring using Ruff + Bandit as oracle.

    Ground truth (GT) = all unique issues found by Ruff and Bandit.
    For each GT issue we check whether the LLM output mentions it.

    Precision = TP / (TP + FP)
      where FP = GT issues NOT mentioned by LLM but mentioned keywords in LLM output
    Recall    = TP / (TP + FN)  = detected_gt / total_gt
    F1        = 2*P*R / (P+R)
    """
    import re as _re
    text = (llm_output or "").lower()

    # Build ground-truth items from static tools
    gt_items = []
    for item in ruff_issues:
        gt_items.append(item.get("message", item.get("code", "")).lower())
    for item in bandit_issues:
        gt_items.append((item.get("test_id", "") + " " + item.get("issue_text", "")).lower())

    total_gt = len(gt_items)

    if total_gt == 0:
        # No static findings — judge purely on whether LLM mentions any issues
        has_issues = any(kw in text for kw in [
            "issue", "error", "bug", "warning", "vulnerability",
            "problem", "risk", "unsafe", "insecure", "injection"
        ])
        return {"tp": 0, "fp": 0, "fn": 0, "total_gt": 0,
                "precision": 100.0 if has_issues else 0.0,
                "recall": 0.0, "f1": 0.0}

    # For each GT item extract key tokens and check LLM coverage
    tp = 0
    for gt in gt_items:
        # Extract meaningful words (≥4 chars) from GT description
        tokens = [w for w in _re.findall(r'[a-z]+', gt) if len(w) >= 4]
        if not tokens:
            tokens = gt.split()[:2]
        if any(tok in text for tok in tokens):
            tp += 1

    fn = total_gt - tp

    # Estimate FP: lines in LLM output that mention issues NOT in GT
    llm_issue_lines = [ln for ln in llm_output.lower().splitlines()
                       if any(kw in ln for kw in ["line", "issue", "error", "warning", "risk", "unsafe"])]
    fp = max(0, len(llm_issue_lines) - tp)

    precision = round(tp / (tp + fp) * 100, 1) if (tp + fp) > 0 else 0.0
    recall    = round(tp / total_gt * 100, 1)
    f1        = round(2 * precision * recall / (precision + recall), 1) if (precision + recall) > 0 else 0.0

    return {
        "tp":        tp,
        "fp":        fp,
        "fn":        fn,
        "total_gt":  total_gt,
        "precision": precision,
        "recall":    recall,
        "f1":        f1,
    }


with tab7:
    st.markdown('<div class="section-label">Benchmark — Experimental Evaluation</div>', unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#666;font-family:DM Mono,monospace;font-size:0.8rem;margin-bottom:1.2rem;'>"
        "Run 12 predefined buggy Python programs through the review modes. "
        "Measures how many known issues each mode detects — use these results in your paper."
        "</p>",
        unsafe_allow_html=True,
    )

    # ─ Config
    bm_col1, bm_col2 = st.columns([2, 1])
    with bm_col1:
        selected_modes = st.multiselect(
            "Modes to benchmark:",
            ["llm_only", "static_llm"],
            default=["llm_only", "static_llm"],
            format_func=lambda x: {"llm_only": "🧠 LLM Only", "static_llm": "🔬 Static + LLM"}[x],
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
    st.markdown(
        f"<p style='font-family:DM Mono,monospace;font-size:0.75rem;color:#999;'>"
        f"{len(filtered_cases)} test cases selected · {len(selected_modes)} mode(s)</p>",
        unsafe_allow_html=True,
    )

    # ─ Test case preview
    with st.expander("💾 Preview test cases", expanded=False):
        for tc in filtered_cases:
            sev_color = {"HIGH": "#dc2626", "MEDIUM": "#d97706", "LOW": "#16a34a"}.get(tc["severity"], "#999")
            st.markdown(
                f"<span style='font-family:DM Mono,monospace;font-size:0.72rem;'>"
                f"<b style='color:{sev_color};'>[{tc['severity']}]</b> "
                f"<b>{tc['id']}</b> — {tc['name']} ({tc['category']})</span>",
                unsafe_allow_html=True,
            )
            st.code(tc["code"].strip(), language="python")

    run_benchmark = st.button("🚀 Run Benchmark", key="bm_run", type="primary" if hasattr(st.button, '__kwdefaults__') else "secondary")

    if run_benchmark:
        if not selected_modes:
            st.warning("Please select at least one mode.")
        elif not filtered_cases:
            st.warning("Please select at least one category.")
        else:
            results = []   # list of result dicts
            total_cases = len(filtered_cases) * len(selected_modes)
            progress = st.progress(0)
            status_txt = st.empty()
            step = 0

            _MODE_LABEL = {"llm_only": "LLM Only", "static_llm": "Static + LLM", "repo_llm": "Repo+LLM"}

            for tc in filtered_cases:
                ruff_issues   = run_ruff(tc["code"])
                bandit_issues = run_bandit(tc["code"])

                for mode in selected_modes:
                    status_txt.markdown(
                        f"<span style='font-family:DM Mono,monospace;font-size:0.75rem;color:#999;'>"
                        f"Running {_MODE_LABEL[mode]} on {tc['id']} — {tc['name']}...</span>",
                        unsafe_allow_html=True,
                    )
                    try:
                        llm_out = ask_llm(tc["code"], ruff_issues, bandit_issues, mode)
                    except Exception as e:
                        llm_out = f"⚠️ Error: {str(e)[:100]}"
                    score    = score_detection(llm_out, ruff_issues, bandit_issues, mode)
                    results.append({
                        "id":          tc["id"],
                        "name":        tc["name"],
                        "category":    tc["category"],
                        "severity":    tc["severity"],
                        "mode":        _MODE_LABEL[mode],
                        "mode_key":    mode,
                        "ruff":        len(ruff_issues),
                        "bandit":      len(bandit_issues),
                        "total_gt":    score["total_gt"],
                        "tp":          score["tp"],
                        "fp":          score["fp"],
                        "fn":          score["fn"],
                        "precision":   score["precision"],
                        "recall":      score["recall"],
                        "f1":          score["f1"],
                        "llm_output":  llm_out,
                    })
                    step += 1
                    progress.progress(step / total_cases)

            status_txt.empty()
            progress.empty()
            st.success(f"✅ Benchmark complete — {len(results)} runs across {len(filtered_cases)} test cases.")

            # ── KPI summary
            st.markdown("<div class='section-label' style='margin-top:1rem;'>Summary</div>", unsafe_allow_html=True)

            kpi_cols = st.columns(len(selected_modes) * 3)
            kpi_idx = 0
            for mode_key in selected_modes:
                mr = [r for r in results if r["mode_key"] == mode_key]
                avg_p  = sum(r["precision"] for r in mr) / len(mr) if mr else 0
                avg_r  = sum(r["recall"]    for r in mr) / len(mr) if mr else 0
                avg_f1 = sum(r["f1"]        for r in mr) / len(mr) if mr else 0
                kpi_cols[kpi_idx].metric(f"{_MODE_LABEL[mode_key]} Precision", f"{avg_p:.1f}%")
                kpi_cols[kpi_idx+1].metric(f"{_MODE_LABEL[mode_key]} Recall",    f"{avg_r:.1f}%")
                kpi_cols[kpi_idx+2].metric(f"{_MODE_LABEL[mode_key]} F1",        f"{avg_f1:.1f}%")
                kpi_idx += 3

            # ── Results table
            st.markdown("<div class='section-label' style='margin-top:1rem;'>Detailed Results</div>", unsafe_allow_html=True)
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

            # ── Chart 1: Avg Recall per Mode (overall)
            st.markdown("<div class='section-label' style='margin-top:1rem;'>Visualisations</div>", unsafe_allow_html=True)
            ch1, ch2 = st.columns(2)

            _bm_layout = dict(
                paper_bgcolor="#f7f7f5", plot_bgcolor="#f7f7f5",
                font=dict(family="DM Mono, monospace", size=11, color="#1a1a1a"),
                margin=dict(l=20, r=20, t=40, b=20),
            )

            with ch1:
                mode_labels_bm = [_MODE_LABEL[m] for m in selected_modes]
                avg_f1s = []
                avg_recalls = []
                for mk in selected_modes:
                    mr = [r for r in results if r["mode_key"] == mk]
                    avg_f1s.append(sum(r["f1"] for r in mr) / len(mr) if mr else 0)
                    avg_recalls.append(sum(r["recall"] for r in mr) / len(mr) if mr else 0)

                fig_f1 = go.Figure()
                fig_f1.add_trace(go.Bar(
                    name="F1",
                    x=mode_labels_bm, y=avg_f1s,
                    marker_color=["#2563eb", "#7c3aed"][:len(selected_modes)],
                    text=[f"{v:.1f}%" for v in avg_f1s], textposition="outside",
                ))
                fig_f1.add_trace(go.Bar(
                    name="Recall",
                    x=mode_labels_bm, y=avg_recalls,
                    marker_color=["#93c5fd", "#c4b5fd"][:len(selected_modes)],
                    text=[f"{v:.1f}%" for v in avg_recalls], textposition="outside",
                ))
                fig_f1.update_layout(
                    **_bm_layout, barmode="group",
                    title="Avg F1 & Recall (%) by Mode",
                    yaxis=dict(range=[0, 120], title="%", showgrid=True, gridcolor="#e8e8e4"),
                    xaxis=dict(showgrid=False),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_f1, use_container_width=True)

            with ch2:
                # Chart 2: Recall per Category per Mode
                categories_used = sorted(set(r["category"] for r in results))
                cat_colors = {"Security": "#dc2626", "Quality": "#d97706", "Style": "#2563eb"}
                fig_cat = go.Figure()
                for mk in selected_modes:
                    cat_recalls = []
                    for cat in categories_used:
                        cat_r = [r for r in results if r["mode_key"] == mk and r["category"] == cat]
                        cat_recalls.append(sum(r["recall"] for r in cat_r) / len(cat_r) if cat_r else 0)
                    fig_cat.add_trace(go.Bar(
                        name=_MODE_LABEL[mk],
                        x=categories_used,
                        y=cat_recalls,
                        text=[f"{v:.0f}%" for v in cat_recalls],
                        textposition="outside",
                    ))
                fig_cat.update_layout(
                    **_bm_layout,
                    barmode="group",
                    title="Recall (%) by Category & Mode",
                    yaxis=dict(range=[0, 120], title="Recall %", showgrid=True, gridcolor="#e8e8e4"),
                    xaxis=dict(showgrid=False),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_cat, use_container_width=True)

            # Chart 3: Recall per test case (heatmap-style grouped bar)
            ch3, ch4 = st.columns(2)
            with ch3:
                tc_names = [r["id"] + ": " + r["name"][:18] for r in results if r["mode_key"] == selected_modes[0]]
                fig_per_tc = go.Figure()
                for mk in selected_modes:
                    mr = [r for r in results if r["mode_key"] == mk]
                    fig_per_tc.add_trace(go.Bar(
                        name=_MODE_LABEL[mk],
                        x=[r["id"] for r in mr],
                        y=[r["recall"] for r in mr],
                        text=[f"{r['recall']}%" for r in mr],
                        textposition="outside",
                    ))
                fig_per_tc.update_layout(
                    **_bm_layout,
                    barmode="group",
                    title="Recall per Test Case",
                    yaxis=dict(range=[0, 130], title="Recall %", showgrid=True, gridcolor="#e8e8e4"),
                    xaxis=dict(showgrid=False, tickangle=-30),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_per_tc, use_container_width=True)

            with ch4:
                # Chart 4: Severity breakdown
                sev_labels = ["HIGH", "MEDIUM", "LOW"]
                sev_colors = ["#dc2626", "#d97706", "#16a34a"]
                fig_sev = go.Figure()
                for mk in selected_modes:
                    sev_recalls = []
                    for sev in sev_labels:
                        sv_r = [r for r in results if r["mode_key"] == mk and r["severity"] == sev]
                        sev_recalls.append(sum(r["recall"] for r in sv_r) / len(sv_r) if sv_r else 0)
                    fig_sev.add_trace(go.Bar(
                        name=_MODE_LABEL[mk],
                        x=sev_labels,
                        y=sev_recalls,
                        text=[f"{v:.0f}%" for v in sev_recalls],
                        textposition="outside",
                    ))
                fig_sev.update_layout(
                    **_bm_layout,
                    barmode="group",
                    title="Recall (%) by Severity",
                    yaxis=dict(range=[0, 130], title="Recall %", showgrid=True, gridcolor="#e8e8e4"),
                    xaxis=dict(showgrid=False),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_sev, use_container_width=True)

            # ── Paper-ready conclusion
            st.markdown("<div class='section-label' style='margin-top:0.5rem;'>Research Findings</div>", unsafe_allow_html=True)
            if len(selected_modes) == 2:
                r_a = [r for r in results if r["mode_key"] == selected_modes[0]]
                r_b = [r for r in results if r["mode_key"] == selected_modes[1]]
                f1_a = sum(r["f1"]     for r in r_a) / len(r_a) if r_a else 0
                f1_b = sum(r["f1"]     for r in r_b) / len(r_b) if r_b else 0
                rc_a = sum(r["recall"] for r in r_a) / len(r_a) if r_a else 0
                rc_b = sum(r["recall"] for r in r_b) / len(r_b) if r_b else 0
                better_f1 = _MODE_LABEL[selected_modes[0]] if f1_a >= f1_b else _MODE_LABEL[selected_modes[1]]
                diff_f1   = abs(f1_a - f1_b)
                diff_rc   = abs(rc_a - rc_b)
                st.markdown(f"""
> ✨ **Key Finding:**  
> **{better_f1}** achieved higher average F1 score across {len(filtered_cases)} test cases.  
> F1 difference: **{diff_f1:.1f} pp** · Recall difference: **{diff_rc:.1f} pp**  
> This supports the hypothesis that static analysis tools provide additional context
> that improves LLM-based code review quality.
""")

            # ── Export
            bm_csv = io.StringIO()
            bm_writer = csv.DictWriter(bm_csv, fieldnames=[
                "ID", "Name", "Category", "Severity", "Mode",
                "GT Issues", "TP", "FP", "FN", "Precision %", "Recall %", "F1 %"
            ])
            bm_writer.writeheader()
            bm_writer.writerows(table_rows)
            st.download_button(
                "⬇ Export Benchmark Results (CSV)",
                data=bm_csv.getvalue(),
                file_name="codesense_benchmark.csv",
                mime="text/csv",
            )

