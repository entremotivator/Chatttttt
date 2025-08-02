import streamlit as st
import requests
from datetime import datetime

# 🌐 Set your live n8n webhook here
N8N_WEBHOOK_URL = "https://agentonline-u29564.vm.elestio.app/webhook/f4927f0d-167b-4ab0-94d2-87d4c373f9e9"

# 🎨 Page config
st.set_page_config(page_title="n8n ChatBot", layout="centered")
st.markdown("""
    <style>
    .chat-bubble {
        padding: 10px 15px;
        border-radius: 15px;
        margin-bottom: 8px;
        max-width: 80%;
        word-wrap: break-word;
        line-height: 1.5;
        font-size: 16px;
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
        max-height: 550px;
        overflow-y: auto;
        padding: 10px;
        border: 1px solid #ccc;
        border-radius: 15px;
        background-color: #f9f9f9;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# 📌 Title and description
st.title("🤖 n8n AI ChatBot")
st.caption("Talk to your custom AI agent powered by [n8n](https://n8n.io) + LLMs (OpenAI, Ollama, etc.)")

# 📜 Initialize session
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# 🚀 Function to call the n8n agent
def ask_n8n_agent(prompt):
    try:
        res = requests.post(N8N_WEBHOOK_URL, json={"message": prompt}, timeout=10)
        res.raise_for_status()
        return res.json().get("response", "⚠️ No response from agent.")
    except Exception as e:
        return f"❌ Error: {e}"

# 📥 Chat input form
with st.form("chat_input", clear_on_submit=True):
    user_input = st.text_input("💬 Type your message here", "")
    submitted = st.form_submit_button("Send")

# 💬 Process message
if submitted and user_input.strip():
    # Add user message
    timestamp = datetime.now().strftime("%H:%M")
    st.session_state.chat_history.append({
        "sender": "user",
        "message": user_input,
        "time": timestamp
    })

    # Get agent reply
    reply = ask_n8n_agent(user_input)
    st.session_state.chat_history.append({
        "sender": "bot",
        "message": reply,
        "time": datetime.now().strftime("%H:%M")
    })

# 🪟 Chat window display
st.markdown('<div class="chat-box">', unsafe_allow_html=True)
for entry in st.session_state.chat_history:
    sender = entry["sender"]
    msg = entry["message"]
    time = entry["time"]

    bubble_class = "chat-bubble user-msg" if sender == "user" else "chat-bubble bot-msg"
    avatar = "🧑" if sender == "user" else "🤖"

    st.markdown(f"""
        <div class="{bubble_class}">
            <b>{avatar} {'You' if sender == 'user' else 'AI'} • {time}</b><br>
            {msg}
        </div>
    """, unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# 🧹 Clear button
if st.button("🗑️ Clear Chat"):
    st.session_state.chat_history = []
    st.experimental_rerun()
