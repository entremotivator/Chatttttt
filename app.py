import streamlit as st
import requests
from datetime import datetime

# 👇 Use your actual working n8n webhook URL
N8N_WEBHOOK_URL = "https://agentonline-u29564.vm.elestio.app/webhook/f4927f0d-167b-4ab0-94d2-87d4c373f9e9"

st.set_page_config(page_title="n8n ChatBot", layout="centered")
st.title("🤖 Chat with AI Agent")
st.caption("Using n8n Webhook + LLM")

st.markdown("""
    <style>
    .chat-bubble {
        padding: 10px 15px;
        border-radius: 15px;
        margin-bottom: 10px;
        max-width: 80%;
        line-height: 1.5;
        font-size: 16px;
        word-wrap: break-word;
    }
    .user-msg {
        background-color: #DCF8C6;
        margin-left: auto;
        text-align: right;
    }
    .bot-msg {
        background-color: #F1F0F0;
        margin-right: auto;
        text-align: left;
    }
    .chat-box {
        max-height: 500px;
        overflow-y: auto;
        padding: 10px;
        border: 1px solid #ccc;
        border-radius: 15px;
        background-color: #fff;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# 📤 Call webhook and safely parse response
def ask_n8n_agent(prompt):
    try:
        res = requests.post(N8N_WEBHOOK_URL, json={"message": prompt}, timeout=10)
        res.raise_for_status()
        try:
            return res.json().get("response", res.text.strip())
        except Exception:
            return f"⚠️ Non-JSON reply:\n\n{res.text.strip()}"
    except Exception as e:
        return f"❌ Error: {e}"

# 🧾 Chat UI
with st.form("chat_input", clear_on_submit=True):
    user_input = st.text_input("💬 Your message:")
    submitted = st.form_submit_button("Send")

if submitted and user_input:
    time_now = datetime.now().strftime("%H:%M")
    st.session_state.chat_history.append(("🧑 You", user_input, time_now))
    reply = ask_n8n_agent(user_input)
    st.session_state.chat_history.append(("🤖 AI", reply, datetime.now().strftime("%H:%M")))

# 🗨️ Chat History UI
st.markdown('<div class="chat-box">', unsafe_allow_html=True)
for sender, message, time in st.session_state.chat_history:
    cls = "chat-bubble user-msg" if "You" in sender else "chat-bubble bot-msg"
    st.markdown(f"""
        <div class="{cls}">
        <b>{sender} • {time}</b><br>{message}
        </div>
    """, unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

if st.button("🗑️ Clear Chat"):
    st.session_state.chat_history = []
    st.rerun()
