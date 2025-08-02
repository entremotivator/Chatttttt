import streamlit as st
import requests
from datetime import datetime

# ----------------------------
# Sidebar: Webhook input
# ----------------------------
st.sidebar.subheader("🔗 AI Webhook Settings")
DEFAULT_N8N_WEBHOOK = "https://agentonline-u29564.vm.elestio.app/webhook/f4927f0d-167b-4ab0-94d2-87d4c373f9e9"
N8N_WEBHOOK_URL = st.sidebar.text_input("Enter N8N Webhook URL:", value=DEFAULT_N8N_WEBHOOK)

# ----------------------------
# Lil J’s Ai Auto Laundry Super Chat
# ----------------------------
st.subheader("💬 Lil J’s Ai Auto Laundry Super Chat")

# Header & context display
st.markdown(f"""
<div class="chat-container">
    <h3>🤖 AI Assistant for {st.session_state.user_info['name']}</h3>
    <p>Chat with our AI assistant powered by Lil J’s Ai Auto Laundry automation</p>
    <p><strong>User Context:</strong> {st.session_state.user_info['role']} in {st.session_state.user_info['team']}</p>
</div>
""", unsafe_allow_html=True)

# Initialize messages in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input field
if prompt := st.chat_input("Type your message here..."):
    # Store user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Prepare bot response
    if N8N_WEBHOOK_URL:
        try:
            with st.spinner("🤖 Lil J is thinking..."):
                response = requests.post(
                    N8N_WEBHOOK_URL,
                    json={
                        "message": prompt,
                        "user_id": st.session_state.get("username", "guest"),
                        "user_name": st.session_state.user_info['name'],
                        "user_role": st.session_state.user_info['role'],
                        "user_team": st.session_state.user_info['team'],
                        "timestamp": datetime.now().isoformat(),
                        "customer_count": len(st.session_state.get("customers_df", [])),
                        "system": "laundry_crm"
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        bot_response = response_data.get("response") or response_data.get("message", "I'm processing your request...")
                    except:
                        bot_response = response.text or "I'm processing your request..."
                else:
                    bot_response = "❌ Unable to connect to AI service. Please try again."

        except Exception as e:
            bot_response = f"⚠️ Connection error: {str(e)}"
    else:
        bot_response = "⚙️ Webhook not set. Please input one in the sidebar."

    # Display bot reply
    st.session_state.messages.append({"role": "assistant", "content": bot_response})
    with st.chat_message("assistant"):
        st.markdown(bot_response)
