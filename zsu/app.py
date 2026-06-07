import streamlit as st
import re
from datetime import datetime
from core.database import load_metrics_db
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

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
    background: var(--sidebar) !important;
    border-right: 1px solid #2A1E2A !important;
    min-width: 240px !important;
    max-width: 256px !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 0 !important; }
[data-testid="stSidebarContent"] {
    padding: 0 !important;
    display: flex;
    flex-direction: column;
    height: 100vh;
}
.cs-logo {
    padding: 20px 18px 16px;
    border-bottom: 1px solid #2A1E2A;
}
.cs-logo-mark {
    font-family: var(--sans);
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--s-text);
    letter-spacing: 0.02em;
    display: flex;
    align-items: center;
    gap: 8px;
}
.cs-diamond { color: var(--accent); font-size: 1rem; }
.cs-logo-sub {
    font-family: var(--mono);
    font-size: 0.55rem;
    color: var(--s-text3);
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-top: 4px;
}
.cs-nav-section {
    font-family: var(--mono);
    font-size: 0.52rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--s-text3);
    padding: 14px 18px 4px;
}
/* Remove ALL Streamlit button styling in sidebar */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    color: #857870 !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.76rem !important;
    font-weight: 400 !important;
    padding: 8px 18px !important;
    width: 100% !important;
    text-align: left !important;
    transition: color 0.15s !important;
    border-left: 3px solid transparent !important;
    letter-spacing: 0.01em !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: transparent !important;
    color: #F0EAE4 !important;
    border-left-color: #5A3030 !important;
    transform: none !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton > button:active {
    transform: none !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton { margin: 0 !important; }
[data-testid="stSidebar"] .stButton > button:focus {
    box-shadow: none !important;
    outline: none !important;
}
/* Active nav item */
.cs-nav-active {
    display: block;
    padding: 8px 18px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.76rem;
    font-weight: 500;
    color: #F0EAE4;
    border-left: 3px solid #B42318;
    background: transparent;
    letter-spacing: 0.01em;
}
.cs-recent-label {
    font-family: var(--mono);
    font-size: 0.52rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--s-text3);
    padding: 12px 18px 6px;
}
.recent-item {
    display: block;
    padding: 6px 14px;
    margin: 1px 8px;
    border-radius: 5px;
    font-family: var(--mono);
    font-size: 0.68rem;
    color: var(--s-text3);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: all 0.12s;
}
.recent-item:hover { background: #261820; color: var(--s-text2); }
.cs-sidebar-bottom {
    margin-top: auto;
    padding: 10px 14px 12px;
    border-top: 1px solid #2A1E2A;
}
.cs-powered { font-family: var(--mono); font-size: 0.57rem; color: var(--s-text3); letter-spacing: 0.08em; }
.cs-powered span { color: #E87060; }

/* ── MAIN ── */
section[data-testid="stMain"] { background: var(--bg) !important; }
section[data-testid="stMain"] > div { padding: 0 !important; }

.cs-page-header {
    padding: 16px 32px 12px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--bg2);
    position: sticky;
    top: 0;
    z-index: 10;
    box-shadow: var(--shadow);
}
.cs-page-title {
    font-family: var(--sans);
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.01em;
}
.cs-page-sub {
    font-family: var(--mono);
    font-size: 0.58rem;
    color: var(--text3);
    letter-spacing: 0.1em;
    margin-left: 12px;
}
.cs-page-content { padding: 24px 32px; }

/* ── TOOLBAR ── */
.cs-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 32px;
    background: var(--bg2);
    border-bottom: 1px solid var(--border);
}
.cs-mode-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: 20px;
    font-family: var(--mono);
    font-size: 0.68rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.12s;
}
.cs-mode-active { background: var(--accentbg); color: var(--accent); border: 1px solid var(--accentbd); }
.cs-mode-inactive { background: var(--bg3); color: var(--text3); border: 1px solid var(--border); }
.cs-repo-connected {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: 20px;
    background: var(--greenbg);
    color: var(--green);
    border: 1px solid #BBF7D0;
    font-family: var(--mono);
    font-size: 0.65rem;
    font-weight: 500;
}

/* ── INPUTS ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
    font-size: 0.82rem !important;
    box-shadow: var(--shadow) !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(180,35,24,0.08) !important;
}
.stTextInput label, .stTextArea label, .stSelectbox label {
    font-family: var(--mono) !important;
    font-size: 0.6rem !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    color: var(--text3) !important;
}

/* ── MAIN BUTTONS ── */
section[data-testid="stMain"] .stButton > button {
    background: var(--accent) !important;
    color: #fff !important;
    border: none !important;
    border-radius: var(--radius) !important;
    font-family: var(--mono) !important;
    font-size: 0.76rem !important;
    font-weight: 500 !important;
    padding: 9px 20px !important;
    letter-spacing: 0.04em !important;
    transition: background 0.15s, transform 0.1s !important;
    box-shadow: 0 1px 2px rgba(180,35,24,0.2) !important;
}
section[data-testid="stMain"] .stButton > button:hover {
    background: var(--accent2) !important;
    transform: translateY(-1px) !important;
}
section[data-testid="stMain"] .stButton > button:active {
    transform: translateY(0) !important;
}

/* ── SELECTBOX ── */
.stSelectbox > div > div {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
    font-size: 0.8rem !important;
    box-shadow: var(--shadow) !important;
}

/* ── METRICS ── */
[data-testid="stMetric"] {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: 16px 18px !important;
    box-shadow: var(--shadow) !important;
}
[data-testid="stMetricValue"] {
    font-family: var(--sans) !important;
    color: var(--accent) !important;
    font-size: 1.8rem !important;
    font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
    font-family: var(--mono) !important;
    font-size: 0.58rem !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    color: var(--text3) !important;
}

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text3) !important;
    border-bottom: 2px solid transparent !important;
    font-family: var(--mono) !important;
    font-size: 0.75rem !important;
    padding: 9px 16px !important;
}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom-color: var(--accent) !important;
    font-weight: 500 !important;
}

/* ── ALERTS ── */
.stAlert {
    border-radius: var(--radius) !important;
    border-left-width: 3px !important;
    font-family: var(--mono) !important;
    font-size: 0.76rem !important;
}

/* ── CODE ── */
.stCode, pre, code {
    background: #F8F6F2 !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    font-family: var(--mono) !important;
    font-size: 0.79rem !important;
    color: var(--text) !important;
}

/* ── PROGRESS ── */
.stProgress > div > div > div { background: var(--accent) !important; }
.stProgress > div > div { background: var(--bg3) !important; border-radius: 2px !important; }

/* ── DOWNLOAD ── */
.stDownloadButton > button {
    background: transparent !important;
    color: var(--accent) !important;
    border: 1px solid var(--accentbd) !important;
    border-radius: var(--radius) !important;
    font-family: var(--mono) !important;
    font-size: 0.74rem !important;
    transition: all 0.15s !important;
}
.stDownloadButton > button:hover {
    background: var(--accent) !important;
    color: #fff !important;
}

/* ── CHAT BUBBLES ── */
.chat-user {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    padding: 12px 16px;
    margin: 8px 0;
    border-radius: 0 var(--radius) var(--radius) 0;
    font-family: var(--mono);
    font-size: 0.82rem;
    color: var(--text);
    box-shadow: var(--shadow);
}
.chat-assistant {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-left: 3px solid var(--border2);
    padding: 14px 18px;
    margin: 8px 0;
    border-radius: 0 var(--radius) var(--radius) 0;
    font-family: var(--mono);
    font-size: 0.81rem;
    color: var(--text2);
    line-height: 1.65;
    box-shadow: var(--shadow);
}

/* ── EXPANDER ── */
.stExpander {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    background: var(--bg2) !important;
    box-shadow: var(--shadow) !important;
}

/* ── CHECKBOX ── */
.stCheckbox label {
    color: var(--text2) !important;
    font-family: var(--mono) !important;
    font-size: 0.78rem !important;
}

/* ── SECTION LABELS ── */
.section-label {
    font-family: var(--mono);
    font-size: 0.58rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--text3);
    border-bottom: 1px solid var(--border);
    padding-bottom: 6px;
    margin-bottom: 14px;
}

/* ── INTENT BADGES ── */
.intent-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-family: var(--mono);
    font-size: 0.62rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 6px;
    font-weight: 500;
}
.intent-review   { background: var(--accentbg); color: var(--accent); border: 1px solid var(--accentbd); }
.intent-generate { background: var(--bluebg);   color: var(--blue);   border: 1px solid #BFDBFE; }
.intent-repo     { background: var(--greenbg);  color: var(--green);  border: 1px solid #BBF7D0; }
.intent-chat     { background: var(--bg3);      color: var(--text3);  border: 1px solid var(--border); }
.intent-bench    { background: var(--goldbg);   color: var(--gold);   border: 1px solid #FDE68A; }

/* ── PROMPT CARDS ── */
.prompt-card {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 10px 16px;
    font-family: var(--mono);
    font-size: 0.7rem;
    cursor: pointer;
    transition: all 0.15s;
    box-shadow: var(--shadow);
}
.prompt-card:hover { border-color: var(--border2); box-shadow: var(--shadow2); }
.prompt-review   { border-left: 3px solid var(--accent); color: var(--accent); }
.prompt-generate { border-left: 3px solid var(--blue);   color: var(--blue);   }
.prompt-repo     { border-left: 3px solid var(--green);  color: var(--green);  }

/* ── DATAFRAME ── */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    overflow: hidden !important;
    box-shadow: var(--shadow) !important;
}

/* ── MULTISELECT ── */
.stMultiSelect > div > div {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
}
[data-baseweb="tag"] {
    background: var(--accent) !important;
    border-radius: 4px !important;
    font-family: var(--mono) !important;
    font-size: 0.68rem !important;
}

::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg3); }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }
hr { border-color: var(--border) !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "history"      not in st.session_state: st.session_state.history      = []
if "metrics"      not in st.session_state: st.session_state.metrics      = load_metrics_db()
if "page"         not in st.session_state: st.session_state.page         = "chat"
if "repo_context" not in st.session_state: st.session_state.repo_context = ""
if "repo_url_connected" not in st.session_state: st.session_state.repo_url_connected = ""

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

    if st.button("＋  New Session", key="new_session"):  # styled via sidebar CSS
        st.session_state.history = []
        st.session_state.repo_context = ""
        st.session_state.repo_url_connected = ""
        st.session_state.page = "chat"
        st.rerun()

    st.markdown("<div class='cs-nav-section'>Main</div>", unsafe_allow_html=True)

    pages = {
        "chat":      "💬  Chat",
        "benchmark": "🎯  Benchmark",
        "metrics":   "📊  Metrics",
    }
    for key, label in pages.items():
        active = st.session_state.page == key
        if active:
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

    st.markdown("<div class='cs-recent-label'>Recent</div>", unsafe_allow_html=True)
    recent = st.session_state.metrics[-8:][::-1]
    _MS = {"llm_only": "LLM", "static_llm": "Static+LLM", "repo_llm": "Repo+LLM"}
    if recent:
        for m in recent:
            ts   = m.get("timestamp", "")[:16]
            mode = _MS.get(m.get("mode", ""), m.get("mode", ""))
            iss  = m.get("ruff", 0) + m.get("bandit", 0)
            st.markdown(f"<div class='recent-item'>{ts} · {mode} · {iss}i</div>",
                        unsafe_allow_html=True)
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

# ── MAIN ──────────────────────────────────────────────────────────────────────
pg = st.session_state.page

# ── NON-CHAT PAGES ────────────────────────────────────────────────────────────
if pg != "chat":
    _TITLES = {
        "benchmark": ("Benchmark",  "50 test cases · precision / recall / F1"),
        "metrics":   ("Metrics",    "session statistics · usage tracking"),
        "docs":      ("Docs",       "architecture · how it works"),
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
    elif pg == "metrics":
        from tabs import metrics as metrics_tab
        metrics_tab.render()
    elif pg == "docs":
        from tabs import docs as docs_tab
        docs_tab.render()

    st.markdown("</div>", unsafe_allow_html=True)

# ── UNIFIED CHAT PAGE ─────────────────────────────────────────────────────────
else:
    # ── Header ────────────────────────────────────────────────────────────────
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
      <div style="display:flex;gap:8px;align-items:center;">
        {repo_badge}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Repo connect (collapsible) ─────────────────────────────────────────
    with st.expander("🔗 Connect GitHub Repository" + (" ✓" if repo_connected else ""), expanded=False):
        col_r1, col_r2, col_r3 = st.columns([3, 1, 1])
        with col_r1:
            repo_url = st.text_input("Repository URL",
                placeholder="https://github.com/username/repo",
                value=repo_connected,
                key="repo_url_input")
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
                        st.session_state.history.append({
                            "role": "assistant",
                            "content": f"✓ Repository connected: `{repo_url}`\n\n{summary}",
                            "intent": "repo"
                        })
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
                st.markdown(f"<div class='chat-user'>👤 {content}</div>",
                            unsafe_allow_html=True)
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
                st.markdown(f"<span class='intent-badge {bc}'>{bl}</span>",
                            unsafe_allow_html=True)
                st.markdown(msg["content"])

    # ── Input area ────────────────────────────────────────────────────────────
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    col_in, col_mode = st.columns([4, 1])
    with col_in:
        user_input = st.text_area(
            "Message",
            placeholder="Review code, write a function, explain an error... (Shift+Enter = new line)",
            height=120,
            label_visibility="collapsed",
            key="user_msg"
        )
    with col_mode:
        st.markdown("""
        <div style='font-family:JetBrains Mono,monospace;font-size:0.58rem;
                    letter-spacing:0.14em;text-transform:uppercase;color:#A09890;
                    margin-bottom:4px;'>Review Mode</div>
        """, unsafe_allow_html=True)
        review_mode = st.selectbox(
            "Review Mode",
            ["llm_only", "static_llm"],
            format_func=lambda x: "LLM Only" if x == "llm_only" else "Static + LLM",
            key="rev_mode",
            label_visibility="collapsed"
        )
        mode_desc = {
            "llm_only": "Fast — code only",
            "static_llm": "Ruff + Bandit + LLM",
        }
        st.markdown(f"""
        <div style='font-family:JetBrains Mono,monospace;font-size:0.62rem;
                    color:#A09890;margin-top:4px;'>{mode_desc[review_mode]}</div>
        """, unsafe_allow_html=True)

    col_send, col_clear, col_spacer = st.columns([1, 1, 6])
    with col_send:
        send = st.button("▶ Send", key="send_btn")
    with col_clear:
        if st.button("✕ Clear", key="clear_btn"):
            st.session_state.history = []
            st.rerun()

    # ── Process message ───────────────────────────────────────────────────────
    if send and user_input.strip():
        msg = user_input.strip()
        st.session_state.history.append({"role": "user", "content": msg})

        intent   = detect_intent(msg)
        code     = extract_code(msg)
        repo_ctx = st.session_state.repo_context

        with st.spinner("Processing..."):
            response = ""

            # ── REVIEW ───────────────────────────────────────────────────────
            if intent == "review" and code:
                ruff   = run_ruff(code)
                bandit = run_bandit(code)
                mode   = "repo_llm" if repo_ctx else review_mode
                response = ask_llm(code, ruff, bandit, mode, repo_ctx)
                if not response:
                    response = "⚠️ No response from API. Please wait a moment and try again."
                else:
                    record_metric(mode, len(ruff), len(bandit), bool(ruff or bandit))
                    st.session_state.metrics = load_metrics_db()

            elif intent == "review" and not code:
                response = ("To review code, please include it in your message.\n\n"
                            "Example:\n```python\ndef login(user, pw):\n    ...\n```")

            # ── GENERATE ─────────────────────────────────────────────────────
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

            # ── REPO ─────────────────────────────────────────────────────────
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
                    # Already connected, answer about the repo
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

            # ── BENCHMARK redirect ────────────────────────────────────────────
            elif intent == "benchmark":
                response = ("Use the 🎯 Benchmark tab in the left menu to run the 50-case evaluation.")

            # ── CHAT (default) ───────────────────────────────────────────────
            else:
                history_for_llm = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.history[:-1]
                ]
                response = chat_with_code(msg, repo_ctx or "", history_for_llm)
                if not response:
                    response = "⚠️ No response from API. Please try again."

        st.session_state.history.append({
            "role": "assistant",
            "content": response,
            "intent": intent
        })
        st.rerun()