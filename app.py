import streamlit as st
import requests
from datetime import datetime
import re

# ----------------------------
# Utility: Strip HTML tags
# ----------------------------
def strip_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

# ----------------------------
# Default Session State Setup
# ----------------------------
if "user_info" not in st.session_state:
    st.session_state.user_info = {
        "name": "Guest",
        "role": "Visitor",
        "team": "Unknown"
    }

if "username" not in st.session_state:
    st.session_state.username = "guest_user"

if "customers_df" not in st.session_state:
    st.session_state.customers_df = []

if "messages" not in st.session_state:
    st.session_state.messages = []

# ----------------------------
# Sidebar: Webhook input
# ----------------------------
st.sidebar.subheader("🔗 AI Webhook Settings")
DEFAULT_N8N_WEBHOOK = "https://agentonline-u29564.vm.elestio.app/webhook/f4927f0d-167b-4ab0-94d2-87d4c373f9e9"
N8N_WEBHOOK_URL = st.sidebar.text_input("Enter N8N Webhook URL:", value=DEFAULT_N8N_WEBHOOK)

# ----------------------------
# Main Interface
# ----------------------------
st.set_page_config(page_title="Lil J’s AI Auto Laundry Chat", layout="centered")
st.title("💬 Lil J’s Ai Auto Laundry Super Chat")

# User Info Display
st.markdown(f"""
<div class="chat-container">
    <h3>🤖 AI Assistant for {st.session_state.user_info['name']}</h3>
    <p>Chat with our AI assistant powered by Lil J’s Ai Auto Laundry automation</p>
    <p><strong>User Context:</strong> {st.session_state.user_info['role']} in {st.session_state.user_info['team']}</p>
</div>
""", unsafe_allow_html=True)

# Display Chat Messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            # Display assistant message as plain text (no AI or JSON formatting)
            st.text(message["content"])
        else:
            st.markdown(message["content"])

# Chat Input
if prompt := st.chat_input("Type your message here..."):
    # Store user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Send to N8N Webhook
    if N8N_WEBHOOK_URL:
        try:
            with st.spinner("🤖 Lil J is thinking..."):
                response = requests.post(
                    N8N_WEBHOOK_URL,
                    json={
                        "message": prompt,
                        "user_id": st.session_state.username,
                        "user_name": st.session_state.user_info['name'],
                        "user_role": st.session_state.user_info['role'],
                        "user_team": st.session_state.user_info['team'],
                        "timestamp": datetime.now().isoformat(),
                        "customer_count": len(st.session_state.customers_df),
                        "system": "laundry_crm"
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        # Only get raw string response, no AI markup or JSON objects
                        bot_response = response_data.get("response") or response_data.get("message") or "🧠 Processing..."
                        # Strip any HTML tags if present
                        bot_response = strip_html_tags(bot_response)
                    except Exception:
                        # Fallback: treat as raw text and strip HTML
                        bot_response = strip_html_tags(response.text) or "🧠 Processing..."
                else:
                    bot_response = "❌ Could not reach the AI service. Please try again later."

        except Exception as e:
            bot_response = f"⚠️ Connection error: {str(e)}"
    else:
        bot_response = "⚙️ Webhook URL not set. Please enter it in the sidebar."

    # Display Bot Response as plain text only
    st.session_state.messages.append({"role": "assistant", "content": bot_response})
    with st.chat_message("assistant"):
        st.text(bot_response)
