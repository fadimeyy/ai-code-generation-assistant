import streamlit as st


def render():
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
