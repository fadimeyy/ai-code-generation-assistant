import streamlit as st
from datetime import datetime
from core.database import load_metrics_db
from tabs import chat, review, generate, metrics, ab_compare, benchmark_tab, docs

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="CodeSense", layout="wide", page_icon="◈",
                   initial_sidebar_state="expanded")

# ── CSS — Claude-style sidebar + clean layout ─────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

:root {
    --bg:        #ffffff;
    --surface:   #f7f7f5;
    --sidebar:   #f3f3ef;
    --border:    #e8e8e4;
    --border2:   #d4d4ce;
    --text:      #1a1a1a;
    --muted:     #999;
    --accent:    #d97706;
    --accent2:   #b45309;
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
.stApp { background: var(--bg) !important; }

/* ── Hide default chrome ── */
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding-top: 1.5rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 100% !important;
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
    background: var(--sidebar) !important;
    border-right: 1px solid var(--border) !important;
    min-width: 240px !important;
    max-width: 260px !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding: 0 !important;
}
[data-testid="stSidebarContent"] {
    padding: 0 !important;
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
}

/* Sidebar collapse button */
[data-testid="collapsedControl"] {
    color: var(--muted) !important;
}

/* ── NAV RADIO BUTTONS → nav items ── */
[data-testid="stSidebar"] .stRadio > div {
    gap: 1px !important;
}
[data-testid="stSidebar"] .stRadio label {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    padding: 9px 14px !important;
    border-radius: 8px !important;
    cursor: pointer !important;
    font-family: var(--sans) !important;
    font-size: 0.9rem !important;
    font-weight: 400 !important;
    color: #3d3d3a !important;
    transition: background 0.12s !important;
    margin: 0 8px !important;
    width: calc(100% - 16px) !important;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: #e8e8e2 !important;
    color: var(--text) !important;
}
[data-testid="stSidebar"] .stRadio [aria-checked="true"] + label,
[data-testid="stSidebar"] .stRadio label[data-checked="true"] {
    background: #e2e2dc !important;
    font-weight: 600 !important;
    color: var(--text) !important;
}
/* Hide radio circles */
[data-testid="stSidebar"] .stRadio input[type="radio"] {
    display: none !important;
}
[data-testid="stSidebar"] .stRadio [data-baseweb="radio"] > div:first-child {
    display: none !important;
}
[data-testid="stSidebar"] .stRadio > label { display: none !important; }

/* ── RECENT ITEMS ── */
.recent-item {
    display: block;
    padding: 8px 14px;
    margin: 1px 8px;
    border-radius: 8px;
    font-family: var(--sans);
    font-size: 0.82rem;
    color: #555;
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: background 0.12s;
}
.recent-item:hover { background: #e8e8e2; color: var(--text); }

.sidebar-section {
    font-family: var(--mono);
    font-size: 0.65rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #aaa;
    padding: 12px 22px 4px;
    margin-top: 4px;
}
.sidebar-logo {
    padding: 20px 20px 12px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 4px;
}
.sidebar-bottom {
    margin-top: auto;
    padding: 12px;
    border-top: 1px solid var(--border);
}

/* ── NEW SESSION BUTTON ── */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    color: #3d3d3a !important;
    border: 1px solid var(--border2) !important;
    border-radius: 8px !important;
    font-family: var(--sans) !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    padding: 8px 14px !important;
    width: 100% !important;
    text-align: left !important;
    transition: background 0.12s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #e8e8e2 !important;
}

/* ── MAIN AREA BUTTONS ── */
.main-area .stButton > button,
section[data-testid="stMain"] .stButton > button {
    background: var(--accent) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 7px !important;
    font-family: var(--sans) !important;
    font-size: 0.83rem !important;
    font-weight: 600 !important;
    padding: 9px 22px !important;
    transition: background 0.15s !important;
}
section[data-testid="stMain"] .stButton > button:hover {
    background: var(--accent2) !important;
}

/* ── INPUTS ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
    font-size: 0.83rem !important;
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
    border-radius: 6px !important;
    font-family: var(--mono) !important;
    font-size: 0.83rem !important;
}

/* ── LABELS ── */
.stTextInput label, .stTextArea label, .stSelectbox label {
    font-family: var(--mono) !important;
    font-size: 0.7rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    color: var(--muted) !important;
}

/* ── TABS (inner) ── */
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
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    padding: 10px 20px !important;
    transition: all 0.15s !important;
}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
    font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 1.5rem !important; }

/* ── METRICS ── */
[data-testid="stMetric"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
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

/* ── ALERTS ── */
.stAlert {
    border-radius: 6px !important;
    border-left-width: 3px !important;
    font-family: var(--mono) !important;
    font-size: 0.8rem !important;
}

/* ── DATAFRAME ── */
.stDataFrame {
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
}

/* ── CODE BLOCKS ── */
.stCode, pre {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    font-family: var(--mono) !important;
}

/* ── PROGRESS ── */
.stProgress > div > div > div { background: var(--accent) !important; }
.stProgress > div > div { background: var(--border) !important; border-radius: 2px !important; }

/* ── DOWNLOAD BUTTON ── */
.stDownloadButton > button {
    background: transparent !important;
    color: var(--accent) !important;
    border: 1.5px solid var(--accent) !important;
    border-radius: 7px !important;
    font-family: var(--sans) !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
}
.stDownloadButton > button:hover {
    background: var(--accent) !important;
    color: #fff !important;
}

/* ── CHAT BUBBLES ── */
.chat-user {
    background: #fef3c7;
    border-left: 3px solid var(--accent);
    padding: 12px 16px;
    margin: 6px 0;
    border-radius: 0 8px 8px 0;
    font-family: var(--sans);
    font-size: 0.9rem;
}
.chat-assistant {
    background: var(--surface);
    border-left: 3px solid var(--border2);
    padding: 12px 16px;
    margin: 6px 0;
    border-radius: 0 8px 8px 0;
    font-family: var(--sans);
    font-size: 0.9rem;
}

/* ── FORM ── */
[data-testid="stForm"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    padding: 12px !important;
}

/* ── SECTION LABEL ── */
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
.tag-high   { color: var(--red);    font-family: var(--mono); font-size: 0.75rem; }
.tag-medium { color: var(--orange); font-family: var(--mono); font-size: 0.75rem; }
.tag-low    { color: var(--green);  font-family: var(--mono); font-size: 0.75rem; }
.stInfo { border-color: var(--accent) !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "chat_history"  not in st.session_state: st.session_state.chat_history  = []
if "chat_code"     not in st.session_state: st.session_state.chat_code     = ""
if "metrics"       not in st.session_state: st.session_state.metrics       = load_metrics_db()
if "current_page"  not in st.session_state: st.session_state.current_page  = "💬 Chat"

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo
    st.markdown("""
    <div class="sidebar-logo">
      <div style="font-family:'Outfit',sans-serif;font-size:1.1rem;font-weight:700;
                  color:#1a1a1a;letter-spacing:-0.02em;">◈ CodeSense</div>
      <div style="font-family:'DM Mono',monospace;font-size:0.62rem;color:#bbb;
                  letter-spacing:0.06em;text-transform:uppercase;margin-top:2px;">
        AI Code Review · v1.0
      </div>
    </div>
    """, unsafe_allow_html=True)

    # New Session
    if st.button("＋  New Session", key="new_session"):
        st.session_state.chat_history = []
        st.session_state.chat_code    = ""
        st.session_state.current_page = "💬 Chat"
        st.rerun()

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # Navigation
    pages = ["💬 Chat", "🔍 Review", "✨ Generate", "📊 Metrics",
             "⚡ A/B Compare", "🎯 Benchmark", "📖 Docs"]

    selected = st.radio("nav", pages, index=pages.index(st.session_state.current_page),
                        label_visibility="collapsed", key="nav_radio")
    if selected != st.session_state.current_page:
        st.session_state.current_page = selected
        st.rerun()

    # Recent sessions from DB
    st.markdown("<div class='sidebar-section'>Recents</div>", unsafe_allow_html=True)

    recent_metrics = st.session_state.metrics[-10:][::-1]  # last 10, newest first
    _MODE_SHORT = {"llm_only": "LLM", "static_llm": "Static+LLM", "repo_llm": "Repo+LLM"}

    if recent_metrics:
        for m in recent_metrics:
            ts   = m.get("timestamp", "")[:16]
            mode = _MODE_SHORT.get(m.get("mode", ""), m.get("mode", ""))
            issues = m.get("ruff", 0) + m.get("bandit", 0)
            label = f"{ts}  ·  {mode}  ·  {issues} issues"
            st.markdown(
                f"<div class='recent-item' title='{label}'>{label}</div>",
                unsafe_allow_html=True
            )
    else:
        st.markdown(
            "<div style='padding:8px 22px;font-size:0.8rem;color:#bbb;"
            "font-family:DM Mono,monospace;'>No sessions yet</div>",
            unsafe_allow_html=True
        )

    # Bottom info
    st.markdown("""
    <div class="sidebar-bottom">
      <div style="font-family:'DM Mono',monospace;font-size:0.65rem;color:#ccc;">
        Powered by Gemini · Python 3.9
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── MAIN CONTENT ──────────────────────────────────────────────────────────────
page = st.session_state.current_page

# Page title
_TITLES = {
    "💬 Chat":        ("Chat Assistant",         "Write code · Fix bugs · Add features · Explain · Write tests"),
    "🔍 Review":      ("Code Review",             "Analyze your Python code with static analysis + AI"),
    "✨ Generate":    ("Generate & Complete",      "Describe what you want — AI writes it, then auto-reviews"),
    "📊 Metrics":     ("Metrics Dashboard",        "Session tracking — review and generation statistics"),
    "⚡ A/B Compare": ("A/B Mode Comparison",      "Compare two review modes side-by-side on the same code"),
    "🎯 Benchmark":   ("Benchmark Evaluation",     "50 controlled test cases · Precision / Recall / F1"),
    "📖 Docs":        ("Documentation",            "How CodeSense works"),
}
title, subtitle = _TITLES.get(page, (page, ""))
st.markdown(f"""
<div style="display:flex;align-items:baseline;gap:12px;padding-bottom:10px;
            border-bottom:1px solid #e8e8e4;margin-bottom:1.5rem;">
  <span style="font-family:'Outfit',sans-serif;font-size:1.2rem;font-weight:700;
               color:#1a1a1a;letter-spacing:-0.02em;">{title}</span>
  <span style="font-family:'DM Mono',monospace;font-size:0.68rem;color:#bbb;
               letter-spacing:0.05em;">{subtitle}</span>
</div>
""", unsafe_allow_html=True)

# Route to page
if   page == "💬 Chat":        chat.render()
elif page == "🔍 Review":      review.render()
elif page == "✨ Generate":    generate.render()
elif page == "📊 Metrics":     metrics.render()
elif page == "⚡ A/B Compare": ab_compare.render()
elif page == "🎯 Benchmark":   benchmark_tab.render()
elif page == "📖 Docs":        docs.render()
