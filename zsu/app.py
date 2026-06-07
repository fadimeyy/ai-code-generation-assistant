import streamlit as st
import re
import uuid
from datetime import datetime
from core.database import (
    load_metrics_db, save_chat_db,
    load_chat_sessions_db, load_chat_history_db
)
from core.analysis import (
    ask_llm, run_ruff, run_bandit,
    generate_code_from_description, complete_code,
    chat_with_code, get_repo_context, record_metric
)

st.set_page_config(page_title="CodeSense", layout="wide", page_icon="◈",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=JetBrains+Mono:wght@300;400;500&family=Fraunces:ital,wght@0,300;0,400;0,600;1,300&display=swap');

:root {
    --bg:       #F7F6F3;
    --bg2:      #FFFFFF;
    --bg3:      #F0EDE8;
    --sidebar:  #171217;
    --border:   #E4E0DA;
    --border2:  #CEC8C0;
    --text:     #1C1917;
    --text2:    #6B6560;
    --text3:    #A09890;
    --accent:   #B42318;
    --accent2:  #912018;
    --accentbg: #FFF1EF;
    --accentbd: #FECDCA;
    --blue:     #1D4ED8;
    --bluebg:   #EFF6FF;
    --green:    #15803D;
    --greenbg:  #F0FDF4;
    --gold:     #92400E;
    --goldbg:   #FFFBEB;
    --purple:   #7C3AED;
    --purplebg: #F5F3FF;
    --s-text:   #F5F0EB;
    --s-text2:  #A09080;
    --s-text3:  #5A4840;
    --mono:     'JetBrains Mono', monospace;
    --sans:     'Syne', sans-serif;
    --serif:    'Fraunces', serif;
    --radius:   8px;
    --shadow:   0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    --shadow2:  0 4px 12px rgba(0,0,0,0.08);
}

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] {
    font-family: var(--mono) !important;
    background: var(--bg) !important;
    color: var(--text) !important;
}
.stApp { background: var(--bg) !important; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 !important; max-width: 100% !important; }


[data-testid="stSidebar"] {
    background: var(--sidebar) !important;
    border-right: 1px solid #2A1E2A !important;
    min-width: 240px !important;
    max-width: 256px !important;
    display: flex !important;
    visibility: visible !important;
    transform: none !important;
}
[data-testid="stSidebarCollapseButton"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
[data-testid="stSidebar"] > div:first-child { padding: 0 !important; }
[data-testid="stSidebarContent"] {
    padding: 0 !important;
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow-y: auto;
}
.cs-logo { padding: 20px 18px 16px; border-bottom: 1px solid #2A1E2A; }
.cs-logo-mark {
    font-family: var(--sans); font-size: 1.1rem; font-weight: 700;
    color: var(--s-text); letter-spacing: 0.02em;
    display: flex; align-items: center; gap: 8px;
}
.cs-diamond { color: var(--accent); font-size: 1rem; }
.cs-logo-sub {
    font-family: var(--mono); font-size: 0.55rem; color: var(--s-text3);
    letter-spacing: 0.18em; text-transform: uppercase; margin-top: 4px;
}
.cs-nav-section {
    font-family: var(--mono); font-size: 0.52rem; letter-spacing: 0.2em;
    text-transform: uppercase; color: var(--s-text3); padding: 14px 18px 4px;
}
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important; color: #857870 !important;
    border: none !important; border-radius: 0 !important;
    box-shadow: none !important; font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.76rem !important; font-weight: 400 !important;
    padding: 8px 18px !important; width: 100% !important;
    text-align: left !important; transition: color 0.15s !important;
    border-left: 3px solid transparent !important; letter-spacing: 0.01em !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: transparent !important; color: #F0EAE4 !important;
    border-left-color: #5A3030 !important; transform: none !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton > button:active,
[data-testid="stSidebar"] .stButton > button:focus {
    transform: none !important; box-shadow: none !important; outline: none !important;
}
[data-testid="stSidebar"] .stButton { margin: 0 !important; }
.cs-nav-active {
    display: block; padding: 8px 18px;
    font-family: 'JetBrains Mono', monospace; font-size: 0.76rem; font-weight: 500;
    color: #F0EAE4; border-left: 3px solid #B42318; background: transparent;
    letter-spacing: 0.01em;
}
.cs-recent-label {
    font-family: var(--mono); font-size: 0.52rem; letter-spacing: 0.2em;
    text-transform: uppercase; color: var(--s-text3); padding: 12px 18px 6px;
}
.cs-sidebar-bottom {
    margin-top: auto; padding: 10px 14px 12px; border-top: 1px solid #2A1E2A;
}
.cs-powered { font-family: var(--mono); font-size: 0.57rem; color: var(--s-text3); letter-spacing: 0.08em; }
.cs-powered span { color: #E87060; }

section[data-testid="stMain"] { background: var(--bg) !important; }
section[data-testid="stMain"] > div { padding: 0 !important; }

.cs-page-header {
    padding: 16px 32px 12px; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
    background: var(--bg2); position: sticky; top: 0; z-index: 10;
    box-shadow: var(--shadow);
}
.cs-page-title { font-family: var(--sans); font-size: 1.15rem; font-weight: 700; color: var(--text); letter-spacing: -0.01em; }
.cs-page-sub { font-family: var(--mono); font-size: 0.58rem; color: var(--text3); letter-spacing: 0.1em; margin-left: 12px; }
.cs-page-content { padding: 24px 32px; }

.cs-repo-connected {
    display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px;
    border-radius: 20px; background: var(--greenbg); color: var(--green);
    border: 1px solid #BBF7D0; font-family: var(--mono); font-size: 0.65rem; font-weight: 500;
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: var(--bg2) !important; border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important; color: var(--text) !important;
    font-family: var(--mono) !important; font-size: 0.82rem !important;
    box-shadow: var(--shadow) !important; transition: border-color 0.15s, box-shadow 0.15s !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(180,35,24,0.08) !important;
}
.stTextInput label, .stTextArea label, .stSelectbox label {
    font-family: var(--mono) !important; font-size: 0.6rem !important;
    letter-spacing: 0.14em !important; text-transform: uppercase !important; color: var(--text3) !important;
}

section[data-testid="stMain"] .stButton > button {
    background: var(--accent) !important; color: #fff !important;
    border: none !important; border-radius: var(--radius) !important;
    font-family: var(--mono) !important; font-size: 0.76rem !important;
    font-weight: 500 !important; padding: 9px 20px !important;
    letter-spacing: 0.04em !important; transition: background 0.15s, transform 0.1s !important;
    box-shadow: 0 1px 2px rgba(180,35,24,0.2) !important;
}
section[data-testid="stMain"] .stButton > button:hover { background: var(--accent2) !important; transform: translateY(-1px) !important; }
section[data-testid="stMain"] .stButton > button:active { transform: translateY(0) !important; }

.stSelectbox > div > div {
    background: var(--bg2) !important; border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important; color: var(--text) !important;
    font-family: var(--mono) !important; font-size: 0.8rem !important;
    box-shadow: var(--shadow) !important;
}

[data-testid="stMetric"] {
    background: var(--bg2) !important; border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important; padding: 16px 18px !important; box-shadow: var(--shadow) !important;
}
[data-testid="stMetricValue"] { font-family: var(--sans) !important; color: var(--accent) !important; font-size: 1.8rem !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { font-family: var(--mono) !important; font-size: 0.58rem !important; letter-spacing: 0.14em !important; text-transform: uppercase !important; color: var(--text3) !important; }

.stTabs [data-baseweb="tab-list"] { background: transparent !important; border-bottom: 1px solid var(--border) !important; gap: 0 !important; }
.stTabs [data-baseweb="tab"] { background: transparent !important; color: var(--text3) !important; border-bottom: 2px solid transparent !important; font-family: var(--mono) !important; font-size: 0.75rem !important; padding: 9px 16px !important; }
.stTabs [aria-selected="true"] { color: var(--accent) !important; border-bottom-color: var(--accent) !important; font-weight: 500 !important; }

.stAlert { border-radius: var(--radius) !important; border-left-width: 3px !important; font-family: var(--mono) !important; font-size: 0.76rem !important; }

.stCode, pre, code { background: #F8F6F2 !important; border: 1px solid var(--border) !important; border-radius: var(--radius) !important; font-family: var(--mono) !important; font-size: 0.79rem !important; color: var(--text) !important; }

.stProgress > div > div > div { background: var(--accent) !important; }
.stProgress > div > div { background: var(--bg3) !important; border-radius: 2px !important; }

.stDownloadButton > button { background: transparent !important; color: var(--accent) !important; border: 1px solid var(--accentbd) !important; border-radius: var(--radius) !important; font-family: var(--mono) !important; font-size: 0.74rem !important; transition: all 0.15s !important; }
.stDownloadButton > button:hover { background: var(--accent) !important; color: #fff !important; }

.chat-user {
    background: var(--bg2); border: 1px solid var(--border);
    border-left: 3px solid var(--accent); padding: 12px 16px; margin: 8px 0;
    border-radius: 0 var(--radius) var(--radius) 0;
    font-family: var(--mono); font-size: 0.82rem; color: var(--text); box-shadow: var(--shadow);
}
.chat-assistant {
    background: var(--bg2); border: 1px solid var(--border);
    border-left: 3px solid var(--border2); padding: 14px 18px; margin: 8px 0;
    border-radius: 0 var(--radius) var(--radius) 0;
    font-family: var(--mono); font-size: 0.81rem; color: var(--text2);
    line-height: 1.65; box-shadow: var(--shadow);
}

.stExpander { border: 1px solid var(--border) !important; border-radius: var(--radius) !important; background: var(--bg2) !important; box-shadow: var(--shadow) !important; }
.stCheckbox label { color: var(--text2) !important; font-family: var(--mono) !important; font-size: 0.78rem !important; }

/* Button row: all three elements same height and aligned */
section[data-testid="stMain"] [data-testid="stHorizontalBlock"] {
    padding: 0 32px !important;
    gap: 8px !important;
    align-items: flex-end !important;
}
section[data-testid="stMain"] [data-testid="stHorizontalBlock"] .stButton {
    margin-bottom: 0 !important;
}
section[data-testid="stMain"] [data-testid="stHorizontalBlock"] .stButton > button {
    height: 42px !important;
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}
section[data-testid="stMain"] [data-testid="stHorizontalBlock"] .stSelectbox {
    margin-bottom: 0 !important;
}
section[data-testid="stMain"] [data-testid="stHorizontalBlock"] .stSelectbox label {
    display: none !important;
}
section[data-testid="stMain"] [data-testid="stHorizontalBlock"] .stSelectbox > div > div {
    height: 42px !important;
    min-height: 42px !important;
    margin-top: 0 !important;
}

.section-label { font-family: var(--mono); font-size: 0.58rem; letter-spacing: 0.2em; text-transform: uppercase; color: var(--text3); border-bottom: 1px solid var(--border); padding-bottom: 6px; margin-bottom: 14px; }

.intent-badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-family: var(--mono); font-size: 0.62rem; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 6px; font-weight: 500; }
.intent-review   { background: var(--accentbg); color: var(--accent); border: 1px solid var(--accentbd); }
.intent-generate { background: var(--bluebg);   color: var(--blue);   border: 1px solid #BFDBFE; }
.intent-repo     { background: var(--greenbg);  color: var(--green);  border: 1px solid #BBF7D0; }
.intent-chat     { background: var(--bg3);      color: var(--text3);  border: 1px solid var(--border); }
.intent-bench    { background: var(--goldbg);   color: var(--gold);   border: 1px solid #FDE68A; }

.prompt-card { background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); padding: 10px 16px; font-family: var(--mono); font-size: 0.7rem; cursor: pointer; transition: all 0.15s; box-shadow: var(--shadow); }
.prompt-card:hover { border-color: var(--border2); box-shadow: var(--shadow2); }
.prompt-review   { border-left: 3px solid var(--accent); color: var(--accent); }
.prompt-generate { border-left: 3px solid var(--blue);   color: var(--blue);   }
.prompt-repo     { border-left: 3px solid var(--green);  color: var(--green);  }

[data-testid="stDataFrame"] { border: 1px solid var(--border) !important; border-radius: var(--radius) !important; overflow: hidden !important; box-shadow: var(--shadow) !important; }

.stMultiSelect > div > div { background: var(--bg2) !important; border: 1px solid var(--border) !important; border-radius: var(--radius) !important; }
[data-baseweb="tag"] { background: var(--accent) !important; border-radius: 4px !important; font-family: var(--mono) !important; font-size: 0.68rem !important; }

::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg3); }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }
hr { border-color: var(--border) !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "history"            not in st.session_state: st.session_state.history            = []
if "metrics"            not in st.session_state: st.session_state.metrics            = load_metrics_db()
if "page"               not in st.session_state: st.session_state.page               = "chat"
if "repo_context"       not in st.session_state: st.session_state.repo_context       = ""
if "repo_url_connected" not in st.session_state: st.session_state.repo_url_connected = ""
if "session_id"         not in st.session_state: st.session_state.session_id         = str(uuid.uuid4())[:8]

# ── Intent detection ──────────────────────────────────────────────────────────
def detect_intent(msg: str) -> str:
    m = msg.lower()
    if re.search(r"github\.com|repo|depo|klon|repository", m):
        return "repo"
    if re.search(r"benchmark|test case|precision|recall|f1", m):
        return "benchmark"
    if re.search(r"yaz|oluştur|generate|write.*function|write.*class|fonksiyon yaz|kod yaz|tamamla|complete|create", m):
        return "generate"
    if re.search(r"incele|review|analiz|hata bul|bug|güvenlik|security|kontrol et|check|denetle", m):
        return "review"
    return "chat"

def extract_code(msg: str) -> str:
    match = re.search(r"```(?:python)?\n?(.*?)```", msg, re.DOTALL)
    if match:
        return match.group(1).strip()
    lines = msg.split("\n")
    code_lines = [l for l in lines if l.startswith("    ") or "def " in l or "import " in l]
    if len(code_lines) > 2:
        return "\n".join(code_lines)
    return ""

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="cs-logo">
      <div class="cs-logo-mark"><span class="cs-diamond">◈</span> CodeSense</div>
      <div class="cs-logo-sub">AI Code Review · v1.0</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    if st.button("＋  New Session", key="new_session"):
        st.session_state.history = []
        st.session_state.repo_context = ""
        st.session_state.repo_url_connected = ""
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.page = "chat"
        st.rerun()

    st.markdown("<div class='cs-nav-section'>Main</div>", unsafe_allow_html=True)

    pages = {
        "chat":      "💬  Chat",
        "benchmark": "🎯  Benchmark",
        "ab":        "⚡  A/B Compare",
        "metrics":   "📊  Metrics",
    }
    for key, label in pages.items():
        if st.session_state.page == key:
            st.markdown(f"<div class='cs-nav-active'>{label}</div>", unsafe_allow_html=True)
        else:
            if st.button(label, key=f"nav_{key}"):
                st.session_state.page = key
                st.rerun()

    st.markdown("<div class='cs-nav-section'>Learn</div>", unsafe_allow_html=True)
    if st.session_state.page == "docs":
        st.markdown("<div class='cs-nav-active'>📖  Docs</div>", unsafe_allow_html=True)
    else:
        if st.button("📖  Docs", key="nav_docs"):
            st.session_state.page = "docs"
            st.rerun()

    # ── Recent Sessions ───────────────────────────────────────────────────────
    st.markdown("<div class='cs-recent-label'>Recent Sessions</div>", unsafe_allow_html=True)
    sessions = load_chat_sessions_db()
    if sessions:
        for s in sessions:
            ts  = s["started"][:16] if s["started"] else ""
            n   = s["msg_count"]
            sid = s["session_id"]
            if st.button(f"{ts} · {n}msg", key=f"sess_{sid}"):
                st.session_state.history    = load_chat_history_db(sid)
                st.session_state.session_id = sid
                st.session_state.page       = "chat"
                st.rerun()
    else:
        st.markdown(
            "<div style='padding:5px 18px;font-size:0.68rem;color:#3A2830;"
            "font-family:JetBrains Mono,monospace;'>No sessions yet</div>",
            unsafe_allow_html=True
        )

    st.markdown("""
    <div class="cs-sidebar-bottom">
      <div class="cs-powered">Powered by <span>Groq · Llama 3.3</span> · Python 3.9</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <style>
    div[data-testid="stMainBlockContainer"] > div:first-child > div:first-child > div[data-testid="stVerticalBlock"] > div:first-child {
        position: fixed !important;
        top: 12px !important;
        left: 12px !important;
        z-index: 9999 !important;
        width: auto !important;
    }
    div[data-testid="stMainBlockContainer"] > div:first-child > div:first-child > div[data-testid="stVerticalBlock"] > div:first-child button {
        background: #171217 !important;
        color: #F5F0EB !important;
        border: 1px solid #3A2A3A !important;
        border-radius: 6px !important;
        width: 36px !important;
        height: 36px !important;
        min-height: 36px !important;
        padding: 0 !important;
        font-size: 1rem !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2) !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ── MAIN ──────────────────────────────────────────────────────────────────────
pg = st.session_state.page

# ── NON-CHAT PAGES ────────────────────────────────────────────────────────────
if pg != "chat":
    _TITLES = {
        "benchmark": ("Benchmark",   "50 test cases · precision / recall / F1"),
        "ab":        ("A/B Compare", "side-by-side mode comparison"),
        "metrics":   ("Metrics",     "session statistics · usage tracking"),
        "docs":      ("Docs",        "architecture · how it works"),
    }
    t, s = _TITLES.get(pg, (pg, ""))

    st.markdown(f"""
    <div class="cs-page-header">
      <div><span class="cs-page-title">{t}</span>
      <span class="cs-page-sub">{s}</span></div>
    </div>
    <div class="cs-page-content">
    """, unsafe_allow_html=True)

    if pg == "benchmark":
        from tabs import benchmark_tab
        benchmark_tab.render()
    elif pg == "ab":
        from tabs import ab_compare
        ab_compare.render()
    elif pg == "metrics":
        from tabs import metrics as metrics_tab
        metrics_tab.render()
    elif pg == "docs":
        from tabs import docs as docs_tab
        docs_tab.render()

    st.markdown("</div>", unsafe_allow_html=True)

# ── CHAT PAGE ─────────────────────────────────────────────────────────────────
else:
    repo_connected = st.session_state.repo_url_connected
    repo_badge = ""
    if repo_connected:
        short = repo_connected.replace("https://github.com/", "")
        repo_badge = f"<span class='cs-repo-connected'>🔗 {short}</span>"

    st.markdown(f"""
    <div class="cs-page-header">
      <div>
        <span class="cs-page-title">CodeSense</span>
        <span class="cs-page-sub">chat · review · generate · repo analysis</span>
      </div>
      <div style="display:flex;gap:8px;align-items:center;">{repo_badge}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Repo connect ──────────────────────────────────────────────────────────
    with st.expander("🔗 Connect GitHub Repository" + (" ✓" if repo_connected else ""), expanded=False):
        col_r1, col_r2, col_r3 = st.columns([3, 1, 1])
        with col_r1:
            repo_url = st.text_input("Repository URL",
                placeholder="https://github.com/username/repo",
                value=repo_connected, key="repo_url_input")
        with col_r2:
            repo_file = st.text_input("File path (optional)",
                placeholder="src/main.py", key="repo_file_input")
        with col_r3:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if st.button("Connect", key="connect_repo"):
                if repo_url:
                    with st.spinner("Cloning repo..."):
                        ctx = get_repo_context(repo_url, repo_file)
                    if ctx:
                        st.session_state.repo_context = ctx
                        st.session_state.repo_url_connected = repo_url
                        with st.spinner("Analyzing repo..."):
                            summary = chat_with_code(
                                "Analyze this repository: what files exist, what does it do, "
                                "are there any security vulnerabilities or code quality issues? "
                                "Give a concise summary.",
                                ctx, []
                            )
                        msg_content = f"✓ Repository connected: `{repo_url}`\n\n{summary}"
                        st.session_state.history.append({
                            "role": "assistant", "content": msg_content, "intent": "repo"
                        })
                        save_chat_db(st.session_state.session_id, "assistant", msg_content, "repo")
                        st.rerun()
                    else:
                        st.warning("Could not clone repo. Check the URL.")
                else:
                    st.warning("Please enter a repo URL.")
        if repo_connected:
            if st.button("Disconnect repo", key="disconnect_repo"):
                st.session_state.repo_context = ""
                st.session_state.repo_url_connected = ""
                st.rerun()

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── Chat history ──────────────────────────────────────────────────────────
    if not st.session_state.history:
        st.markdown("""
        <div style="padding:48px 0 28px;text-align:center;">
          <div style="font-family:'Syne',sans-serif;font-size:2.2rem;font-weight:800;
                      color:#E8E0D8;letter-spacing:-0.03em;margin-bottom:6px;">◈ CodeSense</div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;
                      color:#C8C0B8;letter-spacing:0.1em;margin-bottom:36px;">
            AI-powered Python code review & generation
          </div>
          <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
            <div class="prompt-card prompt-review">🔍 Review code: [paste code]</div>
            <div class="prompt-card prompt-generate">✨ Write a login function</div>
            <div class="prompt-card prompt-repo">🔗 Analyze my GitHub repo</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for msg in st.session_state.history:
            if msg["role"] == "user":
                content = msg["content"].replace("<", "&lt;").replace(">", "&gt;")
                st.markdown(f"<div class='chat-user'>👤 {content}</div>", unsafe_allow_html=True)
            else:
                intent_class = msg.get("intent", "chat")
                badge_map = {
                    "review":    ("intent-review",   "Code Review"),
                    "generate":  ("intent-generate", "Generate"),
                    "repo":      ("intent-repo",     "Repo Analysis"),
                    "chat":      ("intent-chat",     "Assistant"),
                    "benchmark": ("intent-bench",    "Benchmark"),
                }
                bc, bl = badge_map.get(intent_class, ("intent-chat", "Assistant"))
                st.markdown(f"<span class='intent-badge {bc}'>{bl}</span>", unsafe_allow_html=True)
                st.markdown(msg["content"])

    # ── Input ─────────────────────────────────────────────────────────────────
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    user_input = st.text_area(
        "Message",
        placeholder="Review code, write a function, explain an error... (Shift+Enter = new line)",
        height=120, label_visibility="collapsed", key="user_msg"
    )

    col_send, col_clear, col_mode = st.columns([1, 1, 3])
    with col_send:
        send = st.button("▶ Send", key="send_btn", use_container_width=True)
    with col_clear:
        if st.button("✕ Clear", key="clear_btn", use_container_width=True):
            st.session_state.history = []
            st.session_state.session_id = str(uuid.uuid4())[:8]
            st.rerun()
    with col_mode:
        st.markdown("""
        <style>
        div[data-testid="stSelectbox"]:has(label[data-testid="stWidgetLabel"] p) {
            position: relative;
        }
        div[data-testid="stSelectbox"] label { display: none !important; }
        div[data-testid="stSelectbox"] > div > div::after {
            content: "review mode";
            position: absolute;
            right: 36px;
            top: 50%;
            transform: translateY(-50%);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.58rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: #A09890;
            pointer-events: none;
        }
        div[data-testid="stSelectbox"] > div > div {
            position: relative;
        }
        </style>
        """, unsafe_allow_html=True)
        _mode_options = ["llm_only", "static_llm"]
        if st.session_state.repo_url_connected:
            _mode_options.append("repo_llm")

        def _fmt_mode(x):
            if x == "llm_only":   return "🧠 LLM Only"
            if x == "static_llm": return "🔬 Static + LLM"
            return "🔗 Repo + LLM"

        _default_mode = "repo_llm" if st.session_state.repo_url_connected else "llm_only"
        _default_idx  = _mode_options.index(_default_mode)

        review_mode = st.selectbox(
            "review mode",
            _mode_options,
            index=_default_idx,
            format_func=_fmt_mode,
            key="rev_mode",
            label_visibility="collapsed",
        )

    # ── Process ───────────────────────────────────────────────────────────────
    if send and user_input.strip():
        msg = user_input.strip()
        st.session_state.history.append({"role": "user", "content": msg})
        save_chat_db(st.session_state.session_id, "user", msg, "user")

        intent   = detect_intent(msg)
        code     = extract_code(msg)
        repo_ctx = st.session_state.repo_context

        with st.spinner("Processing..."):
            response = ""

            if intent == "review" and code:
                ruff   = run_ruff(code)
                bandit = run_bandit(code)
                mode   = review_mode
                if mode == "repo_llm" and not repo_ctx:
                    response = "⚠️ Repo + LLM modu seçili ama bağlı repo yok. Önce bir GitHub deposu bağla."
                else:
                    response = ask_llm(code, ruff, bandit, mode, repo_ctx)
                    if not response:
                        response = "⚠️ No response from API. Please wait a moment and try again."
                    else:
                        record_metric(mode, len(ruff), len(bandit), bool(ruff or bandit))
                        st.session_state.metrics = load_metrics_db()

            elif intent == "review" and not code:
                mode = review_mode
                if mode == "repo_llm" and not repo_ctx:
                    response = "⚠️ Repo + LLM modu seçili ama bağlı repo yok. Önce bir GitHub deposu bağla."
                else:
                    response = ask_llm(msg, [], [], mode, repo_ctx)
                    if not response:
                        response = "⚠️ No response from API. Please try again."
                    else:
                        record_metric(mode, 0, 0, False)
                        st.session_state.metrics = load_metrics_db()

            elif intent == "generate":
                if re.search(r"tamamla|complete|devam et|finish", msg.lower()) and code:
                    response = complete_code(code)
                else:
                    desc = re.sub(r"```.*?```", "", msg, flags=re.DOTALL).strip()
                    desc = re.sub(r"(yaz|oluştur|generate|write|create)\s*:?\s*", "", desc,
                                  flags=re.IGNORECASE).strip()
                    response = generate_code_from_description(desc)
                if not response:
                    response = "⚠️ Code generation failed. API may be rate-limited."
                else:
                    record_metric("llm_only", 0, 0, False)
                    st.session_state.metrics = load_metrics_db()

            elif intent == "repo":
                urls = re.findall(r"https://github\.com/\S+", msg)
                if urls:
                    with st.spinner("Cloning repo..."):
                        ctx = get_repo_context(urls[0])
                    st.session_state.repo_context = ctx
                    st.session_state.repo_url_connected = urls[0]
                    response = (f"✓ Repository connected: `{urls[0]}`\n\n"
                                f"{len(ctx)} characters of context loaded. "
                                f"Ask me anything about it or paste code to review.")
                elif repo_ctx:
                    history_for_llm = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.history[:-1]
                    ]
                    response = chat_with_code(msg, repo_ctx, history_for_llm)
                    if not response:
                        response = "⚠️ No response from API."
                else:
                    response = ("No repository connected. Include a GitHub URL in your message.\n\n"
                                "Example: `https://github.com/username/repo`")

            elif intent == "benchmark":
                response = "Use the 🎯 Benchmark tab in the left menu to run the 50-case evaluation."

            else:
                history_for_llm = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.history[:-1]
                ]
                response = chat_with_code(msg, repo_ctx or "", history_for_llm)
                if not response:
                    response = "⚠️ No response from API. Please try again."

        st.session_state.history.append({
            "role": "assistant", "content": response, "intent": intent
        })
        save_chat_db(st.session_state.session_id, "assistant", response, intent)
        st.rerun()