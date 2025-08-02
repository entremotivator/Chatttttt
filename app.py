import streamlit as st
import requests
from datetime import datetime
import time

# Configuration
N8N_WEBHOOK_URL = "https://agentonline-u29564.vm.elestio.app/webhook/f4927f0d-167b-4ab0-94d2-87d4c373f9e9"
REQUEST_TIMEOUT = 30  # Increased timeout for better reliability

# Page configuration
st.set_page_config(
    page_title="n8n ChatBot", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        border-bottom: 2px solid #f0f0f0;
        margin-bottom: 2rem;
    }
    
    .chat-container {
        max-height: 600px;
        overflow-y: auto;
        padding: 1rem;
        border: 2px solid #e0e0e0;
        border-radius: 20px;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .chat-bubble {
        padding: 12px 18px;
        border-radius: 18px;
        margin-bottom: 12px;
        max-width: 85%;
        line-height: 1.6;
        font-size: 15px;
        word-wrap: break-word;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        animation: fadeIn 0.3s ease-in;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .user-msg {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin-left: auto;
        text-align: right;
        border-bottom-right-radius: 5px;
    }
    
    .bot-msg {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        margin-right: auto;
        text-align: left;
        border-bottom-left-radius: 5px;
    }
    
    .error-msg {
        background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
        color: #721c24;
        margin-right: auto;
        text-align: left;
        border-left: 4px solid #dc3545;
    }
    
    .timestamp {
        font-size: 11px;
        opacity: 0.8;
        margin-top: 4px;
    }
    
    .input-container {
        background: white;
        padding: 1rem;
        border-radius: 15px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        margin-top: 1rem;
    }
    
    .status-indicator {
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: bold;
        margin-bottom: 1rem;
        text-align: center;
    }
    
    .status-online {
        background-color: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
    }
    
    .status-loading {
        background-color: #fff3cd;
        color: #856404;
        border: 1px solid #ffeaa7;
    }
    
    .status-error {
        background-color: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">', unsafe_allow_html=True)
st.title("🤖 AI Chat Assistant")
st.caption("Powered by n8n Webhook + LLM")
st.markdown('</div>', unsafe_allow_html=True)

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "is_loading" not in st.session_state:
    st.session_state.is_loading = False

if "connection_status" not in st.session_state:
    st.session_state.connection_status = "online"

def validate_input(text):
    """Validate user input"""
    if not text or not text.strip():
        return False, "Please enter a message"
    
    if len(text.strip()) > 1000:
        return False, "Message too long (max 1000 characters)"
    
    return True, ""

def ask_n8n_agent(prompt):
    """Enhanced function to call n8n webhook with better error handling"""
    try:
        st.session_state.connection_status = "loading"
        
        # Prepare the request
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Streamlit-ChatBot/1.0'
        }
        
        payload = {
            "message": prompt.strip(),
            "timestamp": datetime.now().isoformat(),
            "session_id": st.session_state.get("session_id", "default")
        }
        
        # Make the request
        response = requests.post(
            N8N_WEBHOOK_URL, 
            json=payload, 
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        
        # Check response status
        response.raise_for_status()
        
        # Parse response
        try:
            json_response = response.json()
            if isinstance(json_response, dict):
                # Try different possible response keys
                for key in ['response', 'message', 'reply', 'answer', 'text']:
                    if key in json_response:
                        st.session_state.connection_status = "online"
                        return json_response[key]
                
                # If no standard key found, return the whole response
                st.session_state.connection_status = "online"
                return str(json_response)
            else:
                st.session_state.connection_status = "online"
                return str(json_response)
                
        except ValueError:
            # Not JSON, return as text
            response_text = response.text.strip()
            if response_text:
                st.session_state.connection_status = "online"
                return response_text
            else:
                st.session_state.connection_status = "error"
                return "⚠️ Received empty response from server"
                
    except requests.exceptions.Timeout:
        st.session_state.connection_status = "error"
        return "⏱️ Request timed out. The server might be busy. Please try again."
        
    except requests.exceptions.ConnectionError:
        st.session_state.connection_status = "error"
        return "🔌 Connection failed. Please check your internet connection and try again."
        
    except requests.exceptions.HTTPError as e:
        st.session_state.connection_status = "error"
        if e.response.status_code == 404:
            return "🔍 Webhook endpoint not found. Please check the URL configuration."
        elif e.response.status_code == 500:
            return "🔧 Server error. The n8n workflow might have an issue."
        else:
            return f"📡 HTTP Error {e.response.status_code}: {e.response.reason}"
            
    except Exception as e:
        st.session_state.connection_status = "error"
        return f"❌ Unexpected error: {str(e)}"

def display_status():
    """Display connection status"""
    if st.session_state.connection_status == "online":
        st.markdown('<div class="status-indicator status-online">🟢 Connected</div>', unsafe_allow_html=True)
    elif st.session_state.connection_status == "loading":
        st.markdown('<div class="status-indicator status-loading">🟡 Processing...</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-indicator status-error">🔴 Connection Issues</div>', unsafe_allow_html=True)

def add_message(sender, message, timestamp, is_error=False):
    """Add a message to chat history"""
    st.session_state.chat_history.append({
        "sender": sender,
        "message": message,
        "timestamp": timestamp,
        "is_error": is_error
    })

# Display status
display_status()

# Chat input form
st.markdown('<div class="input-container">', unsafe_allow_html=True)

with st.form("chat_input", clear_on_submit=True):
    col1, col2 = st.columns([4, 1])
    
    with col1:
        user_input = st.text_input(
            "💬 Your message:",
            placeholder="Type your message here...",
            disabled=st.session_state.is_loading,
            label_visibility="collapsed"
        )
    
    with col2:
        submitted = st.form_submit_button(
            "Send",
            disabled=st.session_state.is_loading or not user_input,
            use_container_width=True
        )

st.markdown('</div>', unsafe_allow_html=True)

# Process form submission
if submitted and user_input:
    # Validate input
    is_valid, error_msg = validate_input(user_input)
    
    if not is_valid:
        st.error(error_msg)
    else:
        # Set loading state
        st.session_state.is_loading = True
        
        # Add user message
        timestamp = datetime.now().strftime("%H:%M:%S")
        add_message("🧑 You", user_input, timestamp)
        
        # Get AI response
        with st.spinner("AI is thinking..."):
            reply = ask_n8n_agent(user_input)
        
        # Add AI response
        ai_timestamp = datetime.now().strftime("%H:%M:%S")
        is_error = reply.startswith(("❌", "⚠️", "🔌", "⏱️", "🔍", "🔧", "📡"))
        add_message("🤖 AI Assistant", reply, ai_timestamp, is_error)
        
        # Reset loading state
        st.session_state.is_loading = False
        
        # Rerun to update the display
        st.rerun()

# Display chat history
if st.session_state.chat_history:
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    
    for msg in st.session_state.chat_history:
        sender = msg["sender"]
        message = msg["message"]
        timestamp = msg["timestamp"]
        is_error = msg.get("is_error", False)
        
        if "You" in sender:
            css_class = "chat-bubble user-msg"
        elif is_error:
            css_class = "chat-bubble error-msg"
        else:
            css_class = "chat-bubble bot-msg"
        
        # Escape HTML in message content
        escaped_message = message.replace("<", "&lt;").replace(">", "&gt;")
        
        st.markdown(f"""
            <div class="{css_class}">
                <div><strong>{sender}</strong></div>
                <div>{escaped_message}</div>
                <div class="timestamp">{timestamp}</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("👋 Welcome! Start a conversation by typing a message above.")

# Control buttons
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.connection_status = "online"
        st.rerun()

with col2:
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

with col3:
    if st.button("📊 Stats", use_container_width=True):
        total_messages = len(st.session_state.chat_history)
        user_messages = len([msg for msg in st.session_state.chat_history if "You" in msg["sender"]])
        st.info(f"Total messages: {total_messages} | Your messages: {user_messages}")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 12px;'>"
    "💡 Tip: Keep your messages clear and concise for better responses"
    "</div>", 
    unsafe_allow_html=True
)

