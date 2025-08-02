import streamlit as st
import requests
from datetime import datetime
import json

# Configuration
N8N_WEBHOOK_URL = "https://agentonline-u29564.vm.elestio.app/webhook/f4927f0d-167b-4ab0-94d2-87d4c373f9e9"

# Page configuration
st.set_page_config(
    page_title="Simple n8n ChatBot", 
    layout="centered"
)

# Simple CSS
st.markdown("""
<style>
.chat-message {
    padding: 10px;
    margin: 10px 0;
    border-radius: 10px;
}
.user-message {
    background-color: #007bff;
    color: white;
    text-align: right;
}
.bot-message {
    background-color: #f8f9fa;
    color: black;
    border: 1px solid #dee2e6;
}
.error-message {
    background-color: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
}
</style>
""", unsafe_allow_html=True)

# Title
st.title("🤖 Simple n8n Chatbot")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

def send_to_n8n(message):
    """Simple function to send message to n8n and get response"""
    try:
        # Simple payload - just send the message
        payload = {"message": message}
        
        # Make request with simple timeout
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            timeout=30
        )
        
        # Check if request was successful
        if response.status_code == 200:
            # Try to get response as JSON first
            try:
                result = response.json()
                # Handle different response formats
                if isinstance(result, dict):
                    # Try common response keys
                    for key in ['response', 'message', 'reply', 'answer', 'output']:
                        if key in result:
                            return result[key]
                    # If no standard key, return first non-empty value
                    for value in result.values():
                        if value and isinstance(value, str):
                            return value
                    return str(result)
                else:
                    return str(result)
            except:
                # If not JSON, return as text
                return response.text if response.text else "Empty response"
        else:
            return f"Error: Server returned status {response.status_code}"
            
    except requests.exceptions.Timeout:
        return "Error: Request timed out"
    except requests.exceptions.ConnectionError:
        return "Error: Could not connect to server"
    except Exception as e:
        return f"Error: {str(e)}"

# Chat input
user_input = st.text_input("Type your message:", key="user_input")

# Send button
if st.button("Send") or (user_input and st.session_state.get("enter_pressed", False)):
    if user_input.strip():
        # Add user message
        st.session_state.messages.append({
            "type": "user",
            "content": user_input,
            "time": datetime.now().strftime("%H:%M:%S")
        })
        
        # Show loading
        with st.spinner("Getting response..."):
            # Get bot response
            bot_response = send_to_n8n(user_input)
        
        # Add bot response
        st.session_state.messages.append({
            "type": "bot",
            "content": bot_response,
            "time": datetime.now().strftime("%H:%M:%S")
        })
        
        # Clear input
        st.session_state.user_input = ""
        st.rerun()

# Display messages
if st.session_state.messages:
    st.subheader("Chat History")
    
    for msg in st.session_state.messages:
        if msg["type"] == "user":
            st.markdown(f"""
            <div class="chat-message user-message">
                <strong>You ({msg['time']}):</strong><br>
                {msg['content']}
            </div>
            """, unsafe_allow_html=True)
        else:
            # Check if it's an error message
            css_class = "error-message" if msg['content'].startswith("Error:") else "bot-message"
            st.markdown(f"""
            <div class="chat-message {css_class}">
                <strong>Bot ({msg['time']}):</strong><br>
                {msg['content']}
            </div>
            """, unsafe_allow_html=True)

# Clear chat button
if st.button("Clear Chat"):
    st.session_state.messages = []
    st.rerun()

# Debug section (optional - can be removed)
with st.expander("Debug Info"):
    st.write("Webhook URL:", N8N_WEBHOOK_URL)
    st.write("Total messages:", len(st.session_state.messages))
    
    # Test connection button
    if st.button("Test Connection"):
        with st.spinner("Testing..."):
            test_response = send_to_n8n("test")
        st.write("Test response:", test_response)
