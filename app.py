import streamlit as st
import requests
from datetime import datetime, timedelta
import re
import json
import hashlib
import pickle
import os
from typing import List, Dict, Optional
import time
import io
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from google.auth.transport.requests import Request
import tempfile

# ----------------------------
# Configuration
# ----------------------------
CHAT_HISTORY_FILE = "chat_sessions.pkl"
CHAT_HISTORY_JSON = "chat_sessions.json"
MAX_CHAT_HISTORY = 100
DEFAULT_N8N_WEBHOOK = "https://agentonline-u29564.vm.elestio.app/webhook/f4927f0d-167b-4ab0-94d2-87d4c373f9e9"

# Google Drive Configuration
SCOPES = ['https://www.googleapis.com/auth/drive.file']
DRIVE_FOLDER_NAME = "Lil J's AI Chat Sessions"

# ----------------------------
# Google Drive Integration
# ----------------------------
class GoogleDriveManager:
    def __init__(self):
        self.service = None
        self.folder_id = None
    
    def authenticate_service_account(self, service_account_json: str) -> bool:
        """Authenticate with Google Drive using service account"""
        try:
            credentials_info = json.loads(service_account_json)
            
            # Validate service account format
            required_keys = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
            if not all(key in credentials_info for key in required_keys):
                st.error("❌ Invalid service account format")
                return False
            
            if credentials_info.get('type') != 'service_account':
                st.error("❌ File is not a service account credential")
                return False
            
            # Create credentials from service account info
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info, scopes=SCOPES
            )
            
            # Build Drive service
            self.service = build('drive', 'v3', credentials=credentials)
            
            # Test the connection
            self.service.about().get(fields="user").execute()
            
            # Store credentials in session state
            st.session_state.drive_credentials = credentials_info
            
            # Create or find folder
            self.folder_id = self._get_or_create_folder()
            st.session_state.drive_folder_id = self.folder_id
            
            # Update last sync time
            st.session_state.last_drive_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            return True
            
        except json.JSONDecodeError:
            st.error("❌ Invalid JSON format")
            return False
        except Exception as e:
            st.error(f"❌ Authentication error: {str(e)}")
            return False
    
    def initialize_from_session(self) -> bool:
        """Initialize Drive service from stored session credentials"""
        try:
            credentials_info = st.session_state.get('drive_credentials')
            if not credentials_info:
                return False
            
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info, scopes=SCOPES
            )
            
            self.service = build('drive', 'v3', credentials=credentials)
            self.folder_id = st.session_state.get('drive_folder_id')
            
            if not self.folder_id:
                self.folder_id = self._get_or_create_folder()
                st.session_state.drive_folder_id = self.folder_id
            
            return True
            
        except Exception as e:
            st.error(f"Drive initialization error: {str(e)}")
            return False
    
    def _get_or_create_folder(self) -> str:
        """Get or create the chat sessions folder in Drive"""
        try:
            # Search for existing folder - properly escape the apostrophe in folder name
            query = f"name = \"{DRIVE_FOLDER_NAME}\" and mimeType = 'application/vnd.google-apps.folder'"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                return folders[0]['id']
            
            # Create new folder
            folder_metadata = {
                'name': DRIVE_FOLDER_NAME,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = self.service.files().create(body=folder_metadata, fields='id').execute()
            return folder.get('id')
            
        except Exception as e:
            st.error(f"Folder creation error: {str(e)}")
            return None
    
    def upload_sessions(self, sessions_data: Dict, filename: str = None) -> bool:
        """Upload chat sessions to Google Drive"""
        try:
            if not self.service or not self.folder_id:
                return False
            
            if not filename:
                filename = f"chat_sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            # Convert sessions to JSON format
            json_data = json.dumps(sessions_data, indent=2, default=str)
            
            # Create file metadata
            file_metadata = {
                'name': filename,
                'parents': [self.folder_id]
            }
            
            # Upload file
            media = MediaIoBaseUpload(
                io.BytesIO(json_data.encode()),
                mimetype='application/json'
            )
            
            # Check if file already exists and update it - properly escape filename
            query = f"name = \"{filename}\" and parents in \"{self.folder_id}\""
            existing_files = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            if existing_files.get('files'):
                # Update existing file
                file_id = existing_files['files'][0]['id']
                self.service.files().update(
                    fileId=file_id,
                    media_body=media,
                    fields='id'
                ).execute()
            else:
                # Create new file
                self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
            
            return True
            
        except Exception as e:
            st.error(f"Upload error: {str(e)}")
            return False
    
    def list_session_files(self) -> List[Dict]:
        """List all session files in Drive folder"""
        try:
            if not self.service or not self.folder_id:
                return []
            
            # Properly construct query with double quotes for folder ID and contains operator
            query = f"parents in \"{self.folder_id}\" and name contains \"chat_sessions\""
            results = self.service.files().list(
                q=query,
                orderBy='modifiedTime desc',
                spaces='drive',
                fields="files(id, name, modifiedTime, size)"
            ).execute()
            
            return results.get('files', [])
            
        except Exception as e:
            st.error(f"List files error: {str(e)}")
            return []
    
    def download_sessions(self, file_id: str) -> Optional[Dict]:
        """Download and parse session file from Drive"""
        try:
            if not self.service:
                return None
            
            request = self.service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            # Parse JSON content
            file_content.seek(0)
            sessions_data = json.loads(file_content.read().decode())
            
            return sessions_data
            
        except Exception as e:
            st.error(f"Download error: {str(e)}")
            return None

# Initialize Google Drive manager
@st.cache_resource
def get_drive_manager():
    return GoogleDriveManager()

# ----------------------------
# Utility Functions
# ----------------------------
def strip_html_tags(text):
    """Remove HTML tags from text"""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def extract_plain_text(response_text):
    """Extract plain text message from AI response"""
    try:
        data = json.loads(response_text)
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and "messages" in entry:
                    msg_dict = entry["messages"]
                    for key in ("ai", "assistant", "response", "message", "content", "text"):
                        if key in msg_dict:
                            return strip_html_tags(str(msg_dict[key]))
        elif isinstance(data, dict):
            for key in ("response", "message", "text", "content", "answer", "reply", "output"):
                if key in data:
                    content = data[key]
                    if isinstance(content, str):
                        return strip_html_tags(content)
                    elif isinstance(content, dict):
                        for nested_key in ("text", "content", "message"):
                            if nested_key in content:
                                return strip_html_tags(str(content[nested_key]))
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    
    return strip_html_tags(str(response_text))

def generate_session_id(user_info: Dict) -> str:
    """Generate a unique session ID based on user info and timestamp"""
    base_string = f"{user_info['name']}_{user_info['role']}_{user_info['team']}"
    return hashlib.md5(base_string.encode()).hexdigest()[:12]

def save_chat_sessions(sessions: Dict, auto_upload: bool = True):
    """Save chat sessions to file and optionally upload to Drive"""
    try:
        # Save locally
        with open(CHAT_HISTORY_FILE, 'wb') as f:
            pickle.dump(sessions, f)
        
        # Save as JSON for Drive compatibility
        with open(CHAT_HISTORY_JSON, 'w') as f:
            json.dump(sessions, f, indent=2, default=str)
        
        # Auto-upload to Drive if enabled and authenticated
        if auto_upload and st.session_state.get('drive_enabled', False):
            drive_manager = get_drive_manager()
            if drive_manager.initialize_from_session():
                drive_manager.upload_sessions(sessions, "chat_sessions_latest.json")
                
    except Exception as e:
        st.error(f"Error saving chat sessions: {e}")

def load_chat_sessions() -> Dict:
    """Load chat sessions from file"""
    try:
        if os.path.exists(CHAT_HISTORY_FILE):
            with open(CHAT_HISTORY_FILE, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        st.error(f"Error loading chat sessions: {e}")
    return {}

def format_timestamp(timestamp: str) -> str:
    """Format timestamp for display"""
    try:
        if isinstance(timestamp, str):
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            dt = timestamp
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(timestamp)

def truncate_message(message: str, max_length: int = 100) -> str:
    """Truncate message for preview"""
    if len(message) <= max_length:
        return message
    return message[:max_length] + "..."

# ----------------------------
# Session State Initialization
# ----------------------------
def initialize_session_state():
    """Initialize all session state variables"""
    
    # User information
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

    # Chat-related state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = generate_session_id(st.session_state.user_info)
    
    if "chat_sessions" not in st.session_state:
        st.session_state.chat_sessions = load_chat_sessions()
    
    if "selected_session" not in st.session_state:
        st.session_state.selected_session = None
    
    if "auto_save" not in st.session_state:
        st.session_state.auto_save = True
    
    if "message_count" not in st.session_state:
        st.session_state.message_count = 0
    
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = datetime.now().isoformat()
    
    # Google Drive related state
    if "drive_enabled" not in st.session_state:
        st.session_state.drive_enabled = False
    
    if "drive_auto_sync" not in st.session_state:
        st.session_state.drive_auto_sync = True

# ----------------------------
# Chat Session Management
# ----------------------------
def save_current_session():
    """Save the current chat session"""
    if not st.session_state.messages:
        return
    
    session_data = {
        "messages": st.session_state.messages.copy(),
        "user_info": st.session_state.user_info.copy(),
        "created_at": st.session_state.get("session_created_at", datetime.now().isoformat()),
        "last_activity": datetime.now().isoformat(),
        "message_count": len(st.session_state.messages),
        "session_name": f"Chat with {st.session_state.user_info['name']} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    }
    
    st.session_state.chat_sessions[st.session_state.current_session_id] = session_data
    save_chat_sessions(st.session_state.chat_sessions, st.session_state.get('drive_auto_sync', True))

def load_session(session_id: str):
    """Load a specific chat session"""
    if session_id in st.session_state.chat_sessions:
        session_data = st.session_state.chat_sessions[session_id]
        st.session_state.messages = session_data["messages"].copy()
        st.session_state.user_info = session_data["user_info"].copy()
        st.session_state.current_session_id = session_id
        st.session_state.selected_session = session_id
        st.rerun()

def create_new_session():
    """Create a new chat session"""
    if st.session_state.auto_save and st.session_state.messages:
        save_current_session()
    
    st.session_state.messages = []
    st.session_state.current_session_id = generate_session_id(st.session_state.user_info) + f"_{int(time.time())}"
    st.session_state.session_created_at = datetime.now().isoformat()
    st.session_state.selected_session = None
    st.rerun()

def delete_session(session_id: str):
    """Delete a chat session"""
    if session_id in st.session_state.chat_sessions:
        del st.session_state.chat_sessions[session_id]
        save_chat_sessions(st.session_state.chat_sessions, st.session_state.get('drive_auto_sync', True))
        if st.session_state.current_session_id == session_id:
            create_new_session()
        st.rerun()

# ----------------------------
# AI Communication
# ----------------------------
def send_message_to_ai(prompt: str, webhook_url: str) -> str:
    """Send message to AI and return response"""
    try:
        with st.spinner("🤖 Lil J is thinking..."):
            recent_context = []
            if len(st.session_state.messages) > 0:
                recent_messages = st.session_state.messages[-5:]
                for msg in recent_messages:
                    recent_context.append({
                        "role": msg["role"],
                        "content": msg["content"][:200]
                    })
            
            payload = {
                "message": prompt,
                "user_id": st.session_state.username,
                "user_name": st.session_state.user_info['name'],
                "user_role": st.session_state.user_info['role'],
                "user_team": st.session_state.user_info['team'],
                "timestamp": datetime.now().isoformat(),
                "customer_count": len(st.session_state.customers_df),
                "system": "laundry_crm",
                "session_id": st.session_state.current_session_id,
                "message_count": len(st.session_state.messages),
                "context": recent_context
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=45,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                bot_response = extract_plain_text(response.text)
                if not bot_response or bot_response.strip() == "":
                    bot_response = "🤔 I received your message but couldn't generate a proper response. Could you try rephrasing?"
                return bot_response
            else:
                return f"❌ AI service returned status {response.status_code}. Please try again later."

    except requests.exceptions.Timeout:
        return "⏱️ Request timed out. The AI might be processing a complex query. Please try again."
    except requests.exceptions.ConnectionError:
        return "🔌 Connection error. Please check your internet connection and try again."
    except Exception as e:
        return f"⚠️ Unexpected error: {str(e)}"

# ----------------------------
# Google Drive UI Components
# ----------------------------
def render_google_drive_section():
    """Render Google Drive integration section in sidebar"""
    st.sidebar.subheader("🔐 Authentication")
    
    drive_manager = get_drive_manager()
    
    # Check if already authenticated
    if st.session_state.get('drive_enabled', False):
        st.sidebar.success("✅ Connected to Google Drive")
        
        # Auto-sync toggle
        st.session_state.drive_auto_sync = st.sidebar.checkbox(
            "Auto-sync to Drive", 
            value=st.session_state.get('drive_auto_sync', True)
        )
        
        # Manual sync button
        if st.sidebar.button("🔄 Sync Now"):
            if drive_manager.initialize_from_session():
                if drive_manager.upload_sessions(st.session_state.chat_sessions):
                    st.sidebar.success("Synced to Drive!")
                else:
                    st.sidebar.error("Sync failed")
        
        # View Drive files
        with st.sidebar.expander("📁 Drive Files", expanded=False):
            if drive_manager.initialize_from_session():
                files = drive_manager.list_session_files()
                
                if files:
                    st.write("**Available session files:**")
                    for file_info in files[:10]:  # Show last 10 files
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            file_name = truncate_message(file_info['name'], 25)
                            if st.button(f"📥 {file_name}", 
                                       key=f"download_{file_info['id']}",
                                       help=f"Modified: {format_timestamp(file_info['modifiedTime'])}"):
                                downloaded_sessions = drive_manager.download_sessions(file_info['id'])
                                if downloaded_sessions:
                                    st.session_state.chat_sessions.update(downloaded_sessions)
                                    save_chat_sessions(st.session_state.chat_sessions, False)  # Don't auto-upload
                                    st.success(f"Loaded {len(downloaded_sessions)} sessions!")
                                    st.rerun()
                        with col2:
                            size_kb = round(int(file_info.get('size', 0)) / 1024, 1)
                            st.caption(f"{size_kb}KB")
                else:
                    st.info("No session files found in Drive")
        
        # Disconnect option
        if st.sidebar.button("🔌 Disconnect Drive"):
            st.session_state.drive_enabled = False
            st.session_state.drive_credentials = None
            st.session_state.drive_folder_id = None
            st.rerun()
    
    else:
        # Simple service account upload
        st.sidebar.info("Upload service_account.json")
        
        uploaded_file = st.sidebar.file_uploader(
            "Drag and drop file here",
            type=['json'],
            help="Limit 200MB per file • JSON For google drive"
        )
        
        if uploaded_file is not None:
            try:
                service_account_content = uploaded_file.read().decode()
                
                # Use st.spinner() instead of st.sidebar.spinner()
                with st.spinner("🔄 Authenticating with Google Drive..."):
                    if drive_manager.authenticate_service_account(service_account_content):
                        st.session_state.drive_enabled = True
                        st.sidebar.success("✅ Google Drive connected successfully!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.sidebar.error("❌ Authentication failed")
                        
            except Exception as e:
                st.sidebar.error(f"❌ Error reading file: {str(e)}")

# ----------------------------
# Enhanced UI Components
# ----------------------------
def render_sidebar():
    """Render the enhanced sidebar with Google Drive integration"""
    st.sidebar.subheader("🔗 AI Webhook Settings")
    webhook_url = st.sidebar.text_input("Enter N8N Webhook URL:", value=DEFAULT_N8N_WEBHOOK)
    
    # Google Drive Integration
    render_google_drive_section()
    
    st.sidebar.subheader("👤 User Settings")
    with st.sidebar.expander("Edit User Info", expanded=False):
        new_name = st.text_input("Name:", value=st.session_state.user_info['name'])
        new_role = st.selectbox("Role:", 
                               ["Visitor", "Customer", "Manager", "Technician", "Admin"],
                               index=["Visitor", "Customer", "Manager", "Technician", "Admin"].index(st.session_state.user_info['role']) if st.session_state.user_info['role'] in ["Visitor", "Customer", "Manager", "Technician", "Admin"] else 0)
        new_team = st.text_input("Team:", value=st.session_state.user_info['team'])
        
        if st.button("Update User Info"):
            st.session_state.user_info.update({
                "name": new_name,
                "role": new_role,
                "team": new_team
            })
            st.success("User info updated!")
            st.rerun()
    
    st.sidebar.subheader("💬 Chat Sessions")
    
    # Auto-save toggle
    st.session_state.auto_save = st.sidebar.checkbox("Auto-save sessions", value=st.session_state.auto_save)
    
    # Session management buttons
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("🆕 New Chat", use_container_width=True):
            create_new_session()
    with col2:
        if st.button("💾 Save Current", use_container_width=True):
            save_current_session()
            st.success("Session saved!")
    
    # Display chat sessions
    if st.session_state.chat_sessions:
        st.sidebar.write("**Previous Sessions:**")
        
        sorted_sessions = sorted(
            st.session_state.chat_sessions.items(),
            key=lambda x: x[1].get("last_activity", ""),
            reverse=True
        )
        
        for session_id, session_data in sorted_sessions[:10]:
            session_name = session_data.get("session_name", f"Session {session_id[:8]}")
            message_count = session_data.get("message_count", 0)
            last_activity = session_data.get("last_activity", "")
            
            with st.sidebar.container():
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    if st.button(f"📝 {truncate_message(session_name, 20)}", 
                               key=f"load_{session_id}",
                               help=f"Messages: {message_count}\nLast activity: {format_timestamp(last_activity)}",
                               use_container_width=True):
                        load_session(session_id)
                
                with col2:
                    st.write(f"{message_count}")
                
                with col3:
                    if st.button("🗑️", key=f"delete_{session_id}", help="Delete session"):
                        delete_session(session_id)
    
    return webhook_url

def render_chat_stats():
    """Render enhanced chat statistics with Drive status"""
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Current Messages", len(st.session_state.messages))
    
    with col2:
        st.metric("Total Sessions", len(st.session_state.chat_sessions))
    
    with col3:
        total_messages = sum(session.get("message_count", 0) for session in st.session_state.chat_sessions.values())
        st.metric("Total Messages", total_messages)
    
    with col4:
        st.metric("Customers", len(st.session_state.customers_df))
    
    with col5:
        drive_status = "✅ Connected" if st.session_state.get('drive_enabled', False) else "❌ Offline"
        st.metric("Drive Status", drive_status)

# ----------------------------
# Main Application
# ----------------------------
def main():
    """Main application function with Google Drive integration"""
    st.set_page_config(
        page_title="Lil J's AI Auto Laundry Chat",
        page_icon="🧺",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    initialize_session_state()
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .chat-container {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .user-message {
        background-color: #e3f2fd;
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
    }
    .assistant-message {
        background-color: #f1f8e9;
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
    }
    .stButton > button {
        width: 100%;
    }
    .drive-status {
        background-color: #e8f5e8;
        padding: 10px;
        border-radius: 5px;
        border-left: 4px solid #4caf50;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Render sidebar and get webhook URL
    webhook_url = render_sidebar()
    
    # Main content area
    st.title("💬 Lil J's AI Auto Laundry Super Chat")
    
    # Enhanced user info with Drive status
    drive_indicator = "☁️ Synced" if st.session_state.get('drive_enabled', False) else "💻 Local Only"
    
    st.markdown(f"""
    <div class="chat-container">
        <h3>🤖 AI Assistant for {st.session_state.user_info['name']} {drive_indicator}</h3>
        <p>Chat with our AI assistant powered by Lil J's AI Auto Laundry automation</p>
        <p><strong>User Context:</strong> {st.session_state.user_info['role']} in {st.session_state.user_info['team']}</p>
        <p><strong>Current Session:</strong> {st.session_state.current_session_id}</p>
        {f'<p><strong>Google Drive:</strong> <span class="drive-status">Auto-sync enabled</span></p>' if st.session_state.get('drive_enabled', False) and st.session_state.get('drive_auto_sync', False) else ''}
    </div>
    """, unsafe_allow_html=True)
    
    # Enhanced chat statistics
    render_chat_stats()
    
    # Chat messages container
    chat_container = st.container()
    
    with chat_container:
        # Display chat messages
        for i, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"]):
                if message["role"] == "assistant":
                    # Display assistant message with better formatting
                    st.markdown(f'<div class="assistant-message">{message["content"]}</div>', 
                              unsafe_allow_html=True)
                else:
                    # Display user message
                    st.markdown(f'<div class="user-message">{message["content"]}</div>', 
                              unsafe_allow_html=True)
                
                # Add timestamp if available
                if "timestamp" in message:
                    st.caption(f"⏰ {format_timestamp(message['timestamp'])}")
    
    # Chat input
    if prompt := st.chat_input("Type your message here... 💬"):
        # Add user message with timestamp
        user_message = {
            "role": "user", 
            "content": prompt,
            "timestamp": datetime.now().isoformat()
        }
        st.session_state.messages.append(user_message)
        
        # Display user message immediately
        with st.chat_message("user"):
            st.markdown(f'<div class="user-message">{prompt}</div>', unsafe_allow_html=True)
            st.caption(f"⏰ {format_timestamp(user_message['timestamp'])}")
        
        # Get AI response
        if webhook_url:
            bot_response = send_message_to_ai(prompt, webhook_url)
            
            # Add assistant message with timestamp
            assistant_message = {
                "role": "assistant", 
                "content": bot_response,
                "timestamp": datetime.now().isoformat()
            }
            st.session_state.messages.append(assistant_message)
            
            # Display assistant response
            with st.chat_message("assistant"):
                st.markdown(f'<div class="assistant-message">{bot_response}</div>', 
                          unsafe_allow_html=True)
                st.caption(f"⏰ {format_timestamp(assistant_message['timestamp'])}")
            
            # Auto-save if enabled
            if st.session_state.auto_save:
                save_current_session()
            
            # Update last activity
            st.session_state.last_activity = datetime.now().isoformat()
            
        else:
            st.error("⚙️ Webhook URL not set. Please enter it in the sidebar.")
    
    # Footer with Drive sync status
    st.markdown("---")
    
    # Enhanced footer with sync information
    footer_col1, footer_col2, footer_col3 = st.columns([2, 1, 1])
    
    with footer_col1:
        st.markdown("🧺 **Lil J's AI Auto Laundry** - Making laundry management smarter, one conversation at a time!")
    
    with footer_col2:
        if st.session_state.get('drive_enabled', False):
            last_sync = st.session_state.get('last_drive_sync', 'Never')
            st.caption(f"☁️ Last sync: {last_sync}")
        else:
            st.caption("💻 Local storage only")
    
    with footer_col3:
        # Quick export option
        if st.session_state.chat_sessions:
            if st.button("📤 Export All Sessions"):
                # Create downloadable JSON
                export_data = {
                    "export_timestamp": datetime.now().isoformat(),
                    "total_sessions": len(st.session_state.chat_sessions),
                    "user_info": st.session_state.user_info,
                    "sessions": st.session_state.chat_sessions
                }
                
                json_str = json.dumps(export_data, indent=2, default=str)
                st.download_button(
                    label="💾 Download JSON",
                    data=json_str,
                    file_name=f"lil_j_chat_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )

if __name__ == "__main__":
    main()
