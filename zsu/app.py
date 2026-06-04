import streamlit as st
from datetime import datetime
from core.database import load_metrics_db
from tabs import chat, review, generate, metrics, ab_compare, benchmark_tab, docs

st.set_page_config(page_title="CodeSense", layout="wide", page_icon="◈",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=JetBrains+Mono:wght@300;400;500;600&family=Crimson+Pro:wght@300;400;600&display=swap');

:root {
    --bg:         #0a0a0a;
    --bg2:        #111111;
    --bg3:        #1a1a1a;
    --sidebar:    #0d0d0d;
    --border:     #2a2a2a;
    --border2:    #3a3a3a;
    --text:       #f0ede8;
    --text2:      #a09890;
    --text3:      #5a5250;
    --accent:     #8b1a1a;
    --accent2:    #6b1414;
    --accent3:    #c0392b;
    --gold:       #c9a96e;
    --gold2:      #a07840;
    --mono:       'JetBrains Mono', monospace;
    --serif:      'Playfair Display', serif;
    --body:       'Crimson Pro', serif;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, [class*="css"] {
    font-family: var(--mono) !important;
    background: var(--bg) !important;
    color: var(--text) !important;
}
.stApp { background: var(--bg) !important; }

#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding: 0 !important;
    max-width: 100% !important;
}

/* ═══════════════════════════════════════════
   SIDEBAR
═══════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: var(--sidebar) !important;
    border-right: 1px solid var(--border) !important;
    min-width: 240px !important;
    max-width: 252px !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 0 !important; }
[data-testid="stSidebarContent"] {
    padding: 0 !important;
    display: flex;
    flex-direction: column;
    height: 100vh;
}

/* Logo area */
.cs-logo {
    padding: 24px 20px 16px;
    border-bottom: 1px solid var(--border);
}
.cs-logo-mark {
    font-family: var(--serif);
    font-size: 1.25rem;
    font-weight: 900;
    color: var(--text);
    letter-spacing: -0.02em;
    display: flex;
    align-items: center;
    gap: 8px;
}
.cs-logo-mark span.diamond {
    color: var(--accent3);
    font-size: 1.1rem;
}
.cs-logo-sub {
    font-family: var(--mono);
    font-size: 0.6rem;
    color: var(--text3);
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-top: 3px;
}

/* Nav items */
[data-testid="stSidebar"] .stRadio > div { gap: 2px !important; }
[data-testid="stSidebar"] .stRadio label {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    padding: 9px 14px !important;
    border-radius: 4px !important;
    cursor: pointer !important;
    font-family: var(--mono) !important;
    font-size: 0.8rem !important;
    font-weight: 400 !important;
    color: var(--text2) !important;
    transition: all 0.15s !important;
    margin: 1px 8px !important;
    width: calc(100% - 16px) !important;
    border-left: 2px solid transparent !important;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: var(--bg3) !important;
    color: var(--text) !important;
    border-left-color: var(--border2) !important;
}
[data-testid="stSidebar"] .stRadio [aria-checked="true"] + label,
[data-testid="stSidebar"] .stRadio label[data-checked="true"] {
    background: #1a0a0a !important;
    color: var(--text) !important;
    border-left-color: var(--accent3) !important;
    font-weight: 500 !important;
}
[data-testid="stSidebar"] .stRadio input[type="radio"] { display: none !important; }
[data-testid="stSidebar"] .stRadio [data-baseweb="radio"] > div:first-child { display: none !important; }
[data-testid="stSidebar"] .stRadio > label { display: none !important; }

/* New session button */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    color: var(--text2) !important;
    border: 1px solid var(--border2) !important;
    border-radius: 4px !important;
    font-family: var(--mono) !important;
    font-size: 0.78rem !important;
    font-weight: 400 !important;
    padding: 7px 14px !important;
    width: 100% !important;
    text-align: left !important;
    transition: all 0.15s !important;
    letter-spacing: 0.02em !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--bg3) !important;
    color: var(--text) !important;
    border-color: var(--text3) !important;
}

/* Recent items */
.cs-recent {
    font-family: var(--mono);
    font-size: 0.58rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text3);
    padding: 14px 20px 6px;
}
.recent-item {
    display: block;
    padding: 7px 14px;
    margin: 1px 8px;
    border-radius: 4px;
    font-family: var(--mono);
    font-size: 0.73rem;
    color: var(--text3);
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: all 0.12s;
    border-left: 2px solid transparent;
}
.recent-item:hover {
    background: var(--bg3);
    color: var(--text2);
    border-left-color: var(--border2);
}

/* Sidebar bottom */
.cs-sidebar-bottom {
    margin-top: auto;
    padding: 12px 16px;
    border-top: 1px solid var(--border);
}
.cs-powered {
    font-family: var(--mono);
    font-size: 0.6rem;
    color: var(--text3);
    letter-spacing: 0.08em;
}
.cs-powered span { color: var(--accent3); }

/* ═══════════════════════════════════════════
   MAIN CONTENT
═══════════════════════════════════════════ */
section[data-testid="stMain"] {
    background: var(--bg) !important;
    padding: 0 !important;
}
section[data-testid="stMain"] > div {
    padding: 0 !important;
}

/* Page header */
.cs-page-header {
    padding: 20px 32px 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: baseline;
    gap: 16px;
    background: var(--bg);
    position: sticky;
    top: 0;
    z-index: 10;
}
.cs-page-title {
    font-family: var(--serif);
    font-size: 1.35rem;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.01em;
}
.cs-page-sub {
    font-family: var(--mono);
    font-size: 0.63rem;
    color: var(--text3);
    letter-spacing: 0.1em;
}
.cs-page-content {
    padding: 28px 32px;
}

/* ═══════════════════════════════════════════
   INPUTS & FORMS
═══════════════════════════════════════════ */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
    font-size: 0.82rem !important;
    caret-color: var(--accent3) !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
    outline: none !important;
}
.stTextInput label, .stTextArea label, .stSelectbox label {
    font-family: var(--mono) !important;
    font-size: 0.65rem !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    color: var(--text3) !important;
}

/* ═══════════════════════════════════════════
   BUTTONS (main area)
═══════════════════════════════════════════ */
section[data-testid="stMain"] .stButton > button {
    background: var(--accent) !important;
    color: var(--text) !important;
    border: 1px solid var(--accent) !important;
    border-radius: 4px !important;
    font-family: var(--mono) !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    padding: 9px 22px !important;
    letter-spacing: 0.05em !important;
    transition: all 0.15s !important;
}
section[data-testid="stMain"] .stButton > button:hover {
    background: var(--accent3) !important;
    border-color: var(--accent3) !important;
}

/* ═══════════════════════════════════════════
   SELECTBOX
═══════════════════════════════════════════ */
.stSelectbox > div > div {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
    font-size: 0.82rem !important;
}
[data-baseweb="popover"] {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
}
[data-baseweb="option"] {
    background: var(--bg2) !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
    font-size: 0.82rem !important;
}
[data-baseweb="option"]:hover {
    background: var(--bg3) !important;
}

/* ═══════════════════════════════════════════
   MULTISELECT
═══════════════════════════════════════════ */
.stMultiSelect > div > div {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
    font-size: 0.82rem !important;
}
[data-baseweb="tag"] {
    background: var(--accent) !important;
    border-radius: 3px !important;
    font-family: var(--mono) !important;
    font-size: 0.72rem !important;
}

/* ═══════════════════════════════════════════
   METRICS
═══════════════════════════════════════════ */
[data-testid="stMetric"] {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    padding: 16px !important;
}
[data-testid="stMetricValue"] {
    font-family: var(--serif) !important;
    color: var(--gold) !important;
    font-size: 1.9rem !important;
    font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
    font-family: var(--mono) !important;
    font-size: 0.62rem !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    color: var(--text3) !important;
}

/* ═══════════════════════════════════════════
   TABS
═══════════════════════════════════════════ */
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
    font-size: 0.78rem !important;
    font-weight: 400 !important;
    padding: 10px 18px !important;
    letter-spacing: 0.04em !important;
    transition: all 0.15s !important;
}
.stTabs [aria-selected="true"] {
    color: var(--gold) !important;
    border-bottom-color: var(--gold) !important;
    font-weight: 500 !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 1.2rem !important; }

/* ═══════════════════════════════════════════
   ALERTS
═══════════════════════════════════════════ */
.stAlert {
    background: var(--bg2) !important;
    border-radius: 4px !important;
    border-left-width: 3px !important;
    font-family: var(--mono) !important;
    font-size: 0.78rem !important;
    color: var(--text2) !important;
}
div[data-testid="stAlertContainer"] {
    background: var(--bg2) !important;
}

/* ═══════════════════════════════════════════
   DATAFRAME
═══════════════════════════════════════════ */
.stDataFrame {
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
}
.stDataFrame [data-testid="stDataFrameResizable"] {
    background: var(--bg2) !important;
}

/* ═══════════════════════════════════════════
   CODE BLOCKS
═══════════════════════════════════════════ */
.stCode, pre, code {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    font-family: var(--mono) !important;
    font-size: 0.8rem !important;
    color: var(--text) !important;
}

/* ═══════════════════════════════════════════
   PROGRESS
═══════════════════════════════════════════ */
.stProgress > div > div > div {
    background: linear-gradient(90deg, var(--accent), var(--accent3)) !important;
}
.stProgress > div > div {
    background: var(--bg3) !important;
    border-radius: 2px !important;
}

/* ═══════════════════════════════════════════
   DOWNLOAD BUTTON
═══════════════════════════════════════════ */
.stDownloadButton > button {
    background: transparent !important;
    color: var(--gold) !important;
    border: 1px solid var(--gold2) !important;
    border-radius: 4px !important;
    font-family: var(--mono) !important;
    font-size: 0.75rem !important;
    font-weight: 400 !important;
    letter-spacing: 0.04em !important;
}
.stDownloadButton > button:hover {
    background: var(--gold2) !important;
    color: var(--bg) !important;
}

/* ═══════════════════════════════════════════
   CHAT BUBBLES
═══════════════════════════════════════════ */
.chat-user {
    background: #150808;
    border-left: 2px solid var(--accent3);
    padding: 12px 16px;
    margin: 8px 0;
    border-radius: 0 4px 4px 0;
    font-family: var(--body);
    font-size: 0.95rem;
    color: var(--text);
}
.chat-assistant {
    background: var(--bg2);
    border-left: 2px solid var(--border2);
    padding: 12px 16px;
    margin: 8px 0;
    border-radius: 0 4px 4px 0;
    font-family: var(--body);
    font-size: 0.95rem;
    color: var(--text2);
}

/* ═══════════════════════════════════════════
   CHECKBOX & RADIO (content area)
═══════════════════════════════════════════ */
.stCheckbox label {
    color: var(--text2) !important;
    font-family: var(--mono) !important;
    font-size: 0.8rem !important;
}
[data-baseweb="checkbox"] > div {
    border-color: var(--border2) !important;
    background: var(--bg2) !important;
}
[data-baseweb="checkbox"][aria-checked="true"] > div {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
}

/* ═══════════════════════════════════════════
   EXPANDER
═══════════════════════════════════════════ */
.stExpander {
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    background: var(--bg2) !important;
}
.stExpander summary {
    font-family: var(--mono) !important;
    font-size: 0.8rem !important;
    color: var(--text2) !important;
    background: var(--bg2) !important;
}

/* ═══════════════════════════════════════════
   SECTION LABELS & TAGS
═══════════════════════════════════════════ */
.section-label {
    font-family: var(--mono);
    font-size: 0.62rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--text3);
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
    margin-bottom: 16px;
}
.tag-high   { color: #ef4444; font-family: var(--mono); font-size: 0.72rem; }
.tag-medium { color: var(--gold); font-family: var(--mono); font-size: 0.72rem; }
.tag-low    { color: #4ade80; font-family: var(--mono); font-size: 0.72rem; }

/* ═══════════════════════════════════════════
   PLOTLY CHARTS — dark bg fix
═══════════════════════════════════════════ */
.js-plotly-plot .plotly .bg { fill: var(--bg2) !important; }

/* ═══════════════════════════════════════════
   SCROLLBAR
═══════════════════════════════════════════ */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--text3); }

/* ═══════════════════════════════════════════
   SPINNER
═══════════════════════════════════════════ */
.stSpinner > div { border-top-color: var(--accent3) !important; }

/* Form container */
[data-testid="stForm"] {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
}

/* Divider */
hr {
    border-color: var(--border) !important;
    margin: 1rem 0 !important;
}

/* Info box */
.stInfo {
    background: #0d1117 !important;
    border-left-color: var(--accent) !important;
}

/* Success */
.stSuccess {
    background: #0a1a0d !important;
    border-left-color: #22c55e !important;
}

/* Warning */
.stWarning {
    background: #1a1200 !important;
    border-left-color: var(--gold) !important;
}

/* Error */
.stError {
    background: #1a0808 !important;
    border-left-color: var(--accent3) !important;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "chat_history"  not in st.session_state: st.session_state.chat_history  = []
if "chat_code"     not in st.session_state: st.session_state.chat_code     = ""
if "metrics"       not in st.session_state: st.session_state.metrics       = load_metrics_db()
if "current_page"  not in st.session_state: st.session_state.current_page  = "💬 Chat"

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="cs-logo">
      <div class="cs-logo-mark">
        <span class="diamond">◈</span> CodeSense
      </div>
      <div class="cs-logo-sub">AI Code Review · v1.0</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if st.button("＋  New Session", key="new_session"):
        st.session_state.chat_history = []
        st.session_state.chat_code    = ""
        st.session_state.current_page = "💬 Chat"
        st.rerun()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    pages = ["💬 Chat", "🔍 Review", "✨ Generate", "📊 Metrics",
             "⚡ A/B Compare", "🎯 Benchmark", "📖 Docs"]

    selected = st.radio("nav", pages, index=pages.index(st.session_state.current_page),
                        label_visibility="collapsed", key="nav_radio")
    if selected != st.session_state.current_page:
        st.session_state.current_page = selected
        st.rerun()

    st.markdown("<div class='cs-recent'>Recents</div>", unsafe_allow_html=True)

    recent_metrics = st.session_state.metrics[-10:][::-1]
    _MODE_SHORT = {"llm_only": "LLM", "static_llm": "Static+LLM", "repo_llm": "Repo+LLM"}

    if recent_metrics:
        for m in recent_metrics:
            ts     = m.get("timestamp", "")[:16]
            mode   = _MODE_SHORT.get(m.get("mode", ""), m.get("mode", ""))
            issues = m.get("ruff", 0) + m.get("bandit", 0)
            label  = f"{ts} · {mode} · {issues} issues"
            st.markdown(
                f"<div class='recent-item' title='{label}'>{label}</div>",
                unsafe_allow_html=True
            )
    else:
        st.markdown(
            "<div style='padding:6px 22px;font-size:0.72rem;color:#333;"
            "font-family:JetBrains Mono,monospace;'>No sessions yet</div>",
            unsafe_allow_html=True
        )

    st.markdown("""
    <div class="cs-sidebar-bottom">
      <div class="cs-powered">Powered by <span>Gemini</span> · Python 3.9</div>
    </div>
    """, unsafe_allow_html=True)

# ── MAIN CONTENT ──────────────────────────────────────────────────────────────
page = st.session_state.current_page

_TITLES = {
    "💬 Chat":        ("Chat Assistant",       "write code · fix bugs · explain · review"),
    "🔍 Review":      ("Code Review",           "static analysis + AI · three modes"),
    "✨ Generate":    ("Generate & Complete",    "describe → AI writes → auto-reviews"),
    "📊 Metrics":     ("Metrics",               "session statistics · usage tracking"),
    "⚡ A/B Compare": ("A/B Comparison",         "two modes · same code · side by side"),
    "🎯 Benchmark":   ("Benchmark",             "50 test cases · precision / recall / F1"),
    "📖 Docs":        ("Documentation",          "architecture · prompts · data flow"),
}
title, subtitle = _TITLES.get(page, (page, ""))

st.markdown(f"""
<div class="cs-page-header">
  <span class="cs-page-title">{title}</span>
  <span class="cs-page-sub">{subtitle}</span>
</div>
<div class="cs-page-content">
""", unsafe_allow_html=True)

if   page == "💬 Chat":        chat.render()
elif page == "🔍 Review":      review.render()
elif page == "✨ Generate":    generate.render()
elif page == "📊 Metrics":     metrics.render()
elif page == "⚡ A/B Compare": ab_compare.render()
elif page == "🎯 Benchmark":   benchmark_tab.render()
elif page == "📖 Docs":        docs.render()

st.markdown("</div>", unsafe_allow_html=True)