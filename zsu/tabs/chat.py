import streamlit as st
from core.analysis import chat_with_code, run_ruff, run_bandit, ask_llm


def render():
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
