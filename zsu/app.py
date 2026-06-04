import streamlit as st
import re
from datetime import datetime
from core.database import load_metrics_db
from core.analysis import (
    ask_llm, run_ruff, run_bandit,
    generate_code_from_description, complete_code,
    chat_with_code, get_repo_context
)

st.set_page_config(page_title="CodeSense", layout="wide", page_icon="◈",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=JetBrains+Mono:wght@300;400;500;600&family=Crimson+Pro:ital,wght@0,300;0,400;0,600;1,400&display=swap');

:root {
    --bg:        #ffffff;
    --bg2:       #fafaf8;
    --bg3:       #f4f1ee;
    --sidebar:   #1a0a0a;
    --border:    #e8e4e0;
    --border2:   #d4cdc8;
    --text:      #1a1210;
    --text2:     #6b5e58;
    --text3:     #a09088;
    --accent:    #8b1a1a;
    --accent2:   #6b1414;
    --accent3:   #c0392b;
    --gold:      #8b6914;
    --s-text:    #f0ede8;
    --s-text2:   #a09080;
    --s-text3:   #5a4840;
    --mono:      'JetBrains Mono', monospace;
    --serif:     'Playfair Display', serif;
    --body:      'Crimson Pro', serif;
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

/* ── SIDEBAR (dark) ── */
[data-testid="stSidebar"] {
    background: var(--sidebar) !important;
    border-right: 1px solid #2a1a1a !important;
    min-width: 230px !important;
    max-width: 248px !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 0 !important; }
[data-testid="stSidebarContent"] {
    padding: 0 !important;
    display: flex;
    flex-direction: column;
    height: 100vh;
}

.cs-logo {
    padding: 22px 18px 14px;
    border-bottom: 1px solid #2a1a1a;
}
.cs-logo-mark {
    font-family: var(--serif);
    font-size: 1.2rem;
    font-weight: 900;
    color: var(--s-text);
    letter-spacing: -0.02em;
    display: flex;
    align-items: center;
    gap: 8px;
}
.cs-logo-mark .diamond { color: var(--accent3); }
.cs-logo-sub {
    font-family: var(--mono);
    font-size: 0.58rem;
    color: var(--s-text3);
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-top: 3px;
}

/* Sidebar nav */
[data-testid="stSidebar"] .stRadio > div { gap: 1px !important; }
[data-testid="stSidebar"] .stRadio label {
    display: flex !important;
    align-items: center !important;
    padding: 9px 14px !important;
    border-radius: 4px !important;
    cursor: pointer !important;
    font-family: var(--mono) !important;
    font-size: 0.78rem !important;
    font-weight: 400 !important;
    color: var(--s-text2) !important;
    transition: all 0.12s !important;
    margin: 1px 8px !important;
    width: calc(100% - 16px) !important;
    border-left: 2px solid transparent !important;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: #2a1212 !important;
    color: var(--s-text) !important;
}
[data-testid="stSidebar"] .stRadio [aria-checked="true"] + label,
[data-testid="stSidebar"] .stRadio label[data-checked="true"] {
    background: #2a1212 !important;
    color: var(--s-text) !important;
    border-left-color: var(--accent3) !important;
    font-weight: 500 !important;
}
[data-testid="stSidebar"] .stRadio input[type="radio"] { display: none !important; }
[data-testid="stSidebar"] .stRadio [data-baseweb="radio"] > div:first-child { display: none !important; }
[data-testid="stSidebar"] .stRadio > label { display: none !important; }

[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    color: var(--s-text2) !important;
    border: 1px solid #3a2020 !important;
    border-radius: 4px !important;
    font-family: var(--mono) !important;
    font-size: 0.75rem !important;
    padding: 7px 14px !important;
    width: 100% !important;
    text-align: left !important;
    transition: all 0.12s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #2a1212 !important;
    color: var(--s-text) !important;
}

.cs-recent {
    font-family: var(--mono);
    font-size: 0.56rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--s-text3);
    padding: 14px 18px 6px;
}
.recent-item {
    display: block;
    padding: 6px 14px;
    margin: 1px 8px;
    border-radius: 4px;
    font-family: var(--mono);
    font-size: 0.7rem;
    color: var(--s-text3);
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: all 0.12s;
}
.recent-item:hover { background: #2a1212; color: var(--s-text2); }

.cs-sidebar-bottom {
    margin-top: auto;
    padding: 10px 14px;
    border-top: 1px solid #2a1a1a;
}
.cs-powered { font-family: var(--mono); font-size: 0.58rem; color: var(--s-text3); }
.cs-powered span { color: var(--accent3); }

/* ── MAIN (white) ── */
section[data-testid="stMain"] { background: var(--bg) !important; }
section[data-testid="stMain"] > div { padding: 0 !important; }

.cs-page-header {
    padding: 18px 32px 14px;
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
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text);
}
.cs-page-sub {
    font-family: var(--mono);
    font-size: 0.6rem;
    color: var(--text3);
    letter-spacing: 0.1em;
}
.cs-page-content { padding: 24px 32px; }

/* ── INPUTS ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
    font-size: 0.82rem !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
}
.stTextInput label, .stTextArea label, .stSelectbox label, .stMultiSelect label {
    font-family: var(--mono) !important;
    font-size: 0.62rem !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    color: var(--text3) !important;
}

/* ── MAIN BUTTONS ── */
section[data-testid="stMain"] .stButton > button {
    background: var(--accent) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 4px !important;
    font-family: var(--mono) !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    padding: 9px 22px !important;
    letter-spacing: 0.04em !important;
    transition: background 0.15s !important;
}
section[data-testid="stMain"] .stButton > button:hover {
    background: var(--accent3) !important;
}

/* ── SELECTBOX ── */
.stSelectbox > div > div {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
    font-size: 0.82rem !important;
}

/* ── MULTISELECT ── */
.stMultiSelect > div > div {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    font-family: var(--mono) !important;
}
[data-baseweb="tag"] {
    background: var(--accent) !important;
    border-radius: 3px !important;
    font-family: var(--mono) !important;
    font-size: 0.7rem !important;
}

/* ── METRICS ── */
[data-testid="stMetric"] {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    padding: 16px !important;
}
[data-testid="stMetricValue"] {
    font-family: var(--serif) !important;
    color: var(--accent) !important;
    font-size: 1.9rem !important;
    font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
    font-family: var(--mono) !important;
    font-size: 0.6rem !important;
    letter-spacing: 0.12em !important;
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
    font-size: 0.78rem !important;
    padding: 10px 18px !important;
}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom-color: var(--accent) !important;
    font-weight: 500 !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 1.2rem !important; }

/* ── ALERTS ── */
.stAlert {
    border-radius: 4px !important;
    border-left-width: 3px !important;
    font-family: var(--mono) !important;
    font-size: 0.78rem !important;
}

/* ── CODE ── */
.stCode, pre, code {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    font-family: var(--mono) !important;
    font-size: 0.8rem !important;
    color: var(--text) !important;
}

/* ── PROGRESS ── */
.stProgress > div > div > div { background: var(--accent) !important; }
.stProgress > div > div { background: var(--bg3) !important; border-radius: 2px !important; }

/* ── DOWNLOAD ── */
.stDownloadButton > button {
    background: transparent !important;
    color: var(--accent) !important;
    border: 1px solid var(--accent) !important;
    border-radius: 4px !important;
    font-family: var(--mono) !important;
    font-size: 0.75rem !important;
}
.stDownloadButton > button:hover {
    background: var(--accent) !important;
    color: #fff !important;
}

/* ── CHAT BUBBLES ── */
.chat-user {
    background: #fdf4f4;
    border-left: 3px solid var(--accent3);
    padding: 12px 16px;
    margin: 8px 0;
    border-radius: 0 4px 4px 0;
    font-family: var(--body);
    font-size: 1rem;
    color: var(--text);
}
.chat-assistant {
    background: var(--bg2);
    border-left: 3px solid var(--border2);
    padding: 12px 16px;
    margin: 8px 0;
    border-radius: 0 4px 4px 0;
    font-family: var(--body);
    font-size: 1rem;
    color: var(--text2);
}

/* ── EXPANDER ── */
.stExpander {
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    background: var(--bg2) !important;
}

/* ── CHECKBOX ── */
.stCheckbox label {
    color: var(--text2) !important;
    font-family: var(--mono) !important;
    font-size: 0.8rem !important;
}

/* ── SECTION LABELS ── */
.section-label {
    font-family: var(--mono);
    font-size: 0.6rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--text3);
    border-bottom: 1px solid var(--border);
    padding-bottom: 6px;
    margin-bottom: 14px;
}
.tag-high   { color: #dc2626; font-family: var(--mono); font-size: 0.72rem; }
.tag-medium { color: #b45309; font-family: var(--mono); font-size: 0.72rem; }
.tag-low    { color: #16a34a; font-family: var(--mono); font-size: 0.72rem; }

/* ── INTENT BADGE ── */
.intent-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 2px;
    font-family: var(--mono);
    font-size: 0.65rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 8px;
}
.intent-review   { background: #fdf4f4; color: var(--accent); border: 1px solid #f5c6c6; }
.intent-generate { background: #f4f8fd; color: #1d4ed8; border: 1px solid #bfdbfe; }
.intent-repo     { background: #f4fdf6; color: #15803d; border: 1px solid #bbf7d0; }
.intent-chat     { background: var(--bg3); color: var(--text3); border: 1px solid var(--border); }
.intent-bench    { background: #fffbf4; color: var(--gold); border: 1px solid #fde68a; }

::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg2); }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }

[data-testid="stForm"] {
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
}
hr { border-color: var(--border) !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "history"      not in st.session_state: st.session_state.history      = []
if "metrics_data" not in st.session_state: st.session_state.metrics_data = load_metrics_db()
if "page"         not in st.session_state: st.session_state.page         = "chat"

# ── Intent detection ──────────────────────────────────────────────────────────
def detect_intent(msg: str) -> str:
    msg = msg.lower()
    if re.search(r"github\.com|repo|depo|klon", msg):
        return "repo"
    if re.search(r"benchmark|test case|precision|recall|f1|karşılaştır.*mod", msg):
        return "benchmark"
    if re.search(r"yaz|oluştur|generate|write.*function|write.*class|fonksiyon yaz|kod yaz|tamamla|complete", msg):
        return "generate"
    if re.search(r"incele|review|analiz|hata bul|bug|güvenlik|security|kontrol et|check", msg):
        return "review"
    return "chat"

def extract_code(msg: str) -> str:
    """Extract code block from message if present."""
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
      <div class="cs-logo-mark"><span class="diamond">◈</span> CodeSense</div>
      <div class="cs-logo-sub">AI Code Review · v1.0</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if st.button("＋  New Session", key="new_session"):
        st.session_state.history = []
        st.session_state.page    = "chat"
        st.rerun()

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    pages = {
        "chat":      "💬  Chat",
        "benchmark": "🎯  Benchmark",
        "metrics":   "📊  Metrics",
        "docs":      "📖  Docs",
    }
    for key, label in pages.items():
        active = st.session_state.page == key
        if active:
            st.markdown(
                f"<div style='padding:9px 14px;margin:1px 8px;border-radius:4px;"
                f"background:#2a1212;color:#f0ede8;font-family:JetBrains Mono,monospace;"
                f"font-size:0.78rem;font-weight:500;border-left:2px solid #c0392b;'>{label}</div>",
                unsafe_allow_html=True
            )
        else:
            if st.button(label, key=f"nav_{key}"):
                st.session_state.page = key
                st.rerun()

    st.markdown("<div class='cs-recent'>Recent</div>", unsafe_allow_html=True)
    recent = st.session_state.metrics_data[-8:][::-1]
    _MS = {"llm_only": "LLM", "static_llm": "Static+LLM", "repo_llm": "Repo+LLM"}
    if recent:
        for m in recent:
            ts    = m.get("timestamp", "")[:16]
            mode  = _MS.get(m.get("mode", ""), m.get("mode", ""))
            iss   = m.get("ruff", 0) + m.get("bandit", 0)
            label = f"{ts} · {mode} · {iss}i"
            st.markdown(f"<div class='recent-item'>{label}</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            "<div style='padding:6px 18px;font-size:0.7rem;color:#3a2a2a;"
            "font-family:JetBrains Mono,monospace;'>No sessions yet</div>",
            unsafe_allow_html=True
        )

    st.markdown("""
    <div class="cs-sidebar-bottom">
      <div class="cs-powered">Powered by <span>Gemini</span> · Python 3.9</div>
    </div>
    """, unsafe_allow_html=True)

# ── MAIN ──────────────────────────────────────────────────────────────────────
pg = st.session_state.page

# ── NON-CHAT PAGES ────────────────────────────────────────────────────────────
if pg != "chat":
    _TITLES = {
        "benchmark": ("Benchmark", "50 test cases · precision / recall / F1"),
        "metrics":   ("Metrics",   "session statistics · usage tracking"),
        "docs":      ("Docs",      "architecture · how it works"),
    }
    t, s = _TITLES.get(pg, (pg, ""))
    st.markdown(f"""
    <div class="cs-page-header">
      <span class="cs-page-title">{t}</span>
      <span class="cs-page-sub">{s}</span>
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
    st.markdown("""
    <div class="cs-page-header">
      <span class="cs-page-title">CodeSense</span>
      <span class="cs-page-sub">chat · review · generate · repo analysis</span>
    </div>
    """, unsafe_allow_html=True)

    # Repo context input (collapsible, at top)
    with st.expander("🔗 GitHub Repo bağla (opsiyonel)", expanded=False):
        col_r1, col_r2 = st.columns([3, 1])
        with col_r1:
            repo_url = st.text_input("Repo URL", placeholder="https://github.com/kullanici/repo",
                                     label_visibility="collapsed", key="repo_url")
        with col_r2:
            repo_file = st.text_input("Dosya yolu", placeholder="src/main.py",
                                      label_visibility="collapsed", key="repo_file")
        if st.button("Bağla", key="connect_repo"):
            if repo_url:
                with st.spinner("Repo klonlanıyor..."):
                    ctx = get_repo_context(repo_url, repo_file)
                st.session_state["repo_context"] = ctx
                st.success(f"✓ Repo bağlandı — {len(ctx)} karakter bağlam yüklendi.")
            else:
                st.warning("Repo URL girin.")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Chat history display
    chat_container = st.container()
    with chat_container:
        if not st.session_state.history:
            st.markdown("""
            <div style="padding:40px 0 20px;text-align:center;">
              <div style="font-family:'Playfair Display',serif;font-size:2rem;font-weight:700;
                          color:#e8e4e0;letter-spacing:-0.02em;margin-bottom:8px;">◈ CodeSense</div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:0.72rem;
                          color:#c0b8b0;letter-spacing:0.08em;margin-bottom:32px;">
                AI-powered Python code review & generation
              </div>
              <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:8px;">
                <div style="background:#fdf4f4;border:1px solid #f5c6c6;border-radius:6px;
                            padding:10px 16px;font-family:'JetBrains Mono',monospace;
                            font-size:0.72rem;color:#8b1a1a;cursor:pointer;">
                  🔍 "Bu kodu incele: [kodu yapıştır]"
                </div>
                <div style="background:#f4f8fd;border:1px solid #bfdbfe;border-radius:6px;
                            padding:10px 16px;font-family:'JetBrains Mono',monospace;
                            font-size:0.72rem;color:#1d4ed8;cursor:pointer;">
                  ✨ "Login fonksiyonu yaz"
                </div>
                <div style="background:#f4fdf6;border:1px solid #bbf7d0;border-radius:6px;
                            padding:10px 16px;font-family:'JetBrains Mono',monospace;
                            font-size:0.72rem;color:#15803d;cursor:pointer;">
                  🔗 "GitHub repomu analiz et"
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            for msg in st.session_state.history:
                if msg["role"] == "user":
                    st.markdown(f"<div class='chat-user'>👤 {msg['content']}</div>",
                                unsafe_allow_html=True)
                else:
                    intent_class = msg.get("intent", "chat")
                    badge_map = {
                        "review":   ("intent-review",   "Code Review"),
                        "generate": ("intent-generate", "Generate"),
                        "repo":     ("intent-repo",     "Repo Analysis"),
                        "chat":     ("intent-chat",     "Chat"),
                        "benchmark":("intent-bench",    "Benchmark"),
                    }
                    bc, bl = badge_map.get(intent_class, ("intent-chat", "Chat"))
                    st.markdown(
                        f"<span class='intent-badge {bc}'>{bl}</span>"
                        f"<div class='chat-assistant'>◈ {msg['content']}</div>",
                        unsafe_allow_html=True
                    )

    # ── Input area ────────────────────────────────────────────────────────────
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    col_in, col_mode = st.columns([4, 1])
    with col_in:
        user_input = st.text_area(
            "Mesajınız",
            placeholder="Kodu incele, fonksiyon yaz, hata açıkla... (Shift+Enter = yeni satır)",
            height=90,
            label_visibility="collapsed",
            key="user_msg"
        )
    with col_mode:
        review_mode = st.selectbox(
            "Review Modu",
            ["llm_only", "static_llm"],
            format_func=lambda x: "LLM Only" if x == "llm_only" else "Static + LLM",
            key="rev_mode",
            label_visibility="visible"
        )

    col_send, col_clear = st.columns([1, 5])
    with col_send:
        send = st.button("▶ Gönder", key="send_btn")
    with col_clear:
        if st.button("✕ Temizle", key="clear_btn"):
            st.session_state.history = []
            st.rerun()

    # ── Process message ───────────────────────────────────────────────────────
    if send and user_input.strip():
        msg = user_input.strip()
        st.session_state.history.append({"role": "user", "content": msg})

        intent = detect_intent(msg)
        code   = extract_code(msg)
        repo_ctx = st.session_state.get("repo_context", "")

        with st.spinner("İşleniyor..."):
            response = ""

            # ── REVIEW ───────────────────────────────────────────────────────
            if intent == "review" and code:
                ruff    = run_ruff(code)
                bandit  = run_bandit(code)
                mode    = review_mode
                if repo_ctx:
                    mode = "repo_llm"
                response = ask_llm(code, ruff, bandit, mode, repo_ctx)
                if not response:
                    response = "⚠️ API yanıt vermedi. Lütfen biraz bekleyip tekrar deneyin."

            elif intent == "review" and not code:
                response = "Kodu inceleyebilmem için lütfen kodu mesajınıza ekleyin.\n\nÖrnek:\n```python\ndef login(user, pw):\n    ...\n```"

            # ── GENERATE ─────────────────────────────────────────────────────
            elif intent == "generate":
                # Check if it's a completion request
                if re.search(r"tamamla|complete|devam et", msg.lower()) and code:
                    response = complete_code(code)
                else:
                    # Extract description (remove code blocks)
                    desc = re.sub(r"```.*?```", "", msg, flags=re.DOTALL).strip()
                    desc = re.sub(r"(yaz|oluştur|generate|write|create)\s*:?\s*", "", desc,
                                  flags=re.IGNORECASE).strip()
                    response = generate_code_from_description(desc)
                if not response:
                    response = "⚠️ Kod üretilemedi. API kotası dolmuş olabilir."

            # ── REPO ─────────────────────────────────────────────────────────
            elif intent == "repo":
                urls = re.findall(r"https://github\.com/\S+", msg)
                if urls:
                    with st.spinner("Repo klonlanıyor..."):
                        ctx = get_repo_context(urls[0])
                    st.session_state["repo_context"] = ctx
                    response = f"✓ Repo bağlandı: `{urls[0]}`\n{len(ctx)} karakter bağlam yüklendi.\n\nArtık 'Bu kodu incele' dediğinizde repo bağlamı otomatik kullanılır."
                else:
                    response = "GitHub repo URL'si bulunamadı. Örnek: `https://github.com/kullanici/repo`"

            # ── BENCHMARK (redirect) ─────────────────────────────────────────
            elif intent == "benchmark":
                response = "Benchmark için sol menüden 🎯 Benchmark sekmesine geçin — 50 test vakasını oradan çalıştırabilirsiniz."

            # ── CHAT (default) ───────────────────────────────────────────────
            else:
                history_for_llm = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.history[:-1]
                ]
                response = chat_with_code(msg, repo_ctx or "", history_for_llm)
                if not response:
                    response = "⚠️ Yanıt alınamadı. API kotası dolmuş olabilir."

        st.session_state.history.append({
            "role": "assistant",
            "content": response,
            "intent": intent
        })
        st.rerun()