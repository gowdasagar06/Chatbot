import boto3
from datetime import datetime
import uuid
import streamlit as st
from botocore.exceptions import ClientError
import json
from decimal import Decimal
import collections.abc

class ChatSessionManagerDynamoDB:
    def __init__(self, table_name='Arena-ChatSessions', region_name='us-east-1'):
        self.table_name = table_name
        self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
        self.table = self.dynamodb.Table(table_name)

    def initialize_session_state(self):
        st.set_page_config(page_title="Chatbot Arena", page_icon="🤖", layout="wide")
        st.session_state.setdefault("authenticated", False)
        st.session_state.setdefault("user_id", "")
        st.session_state.setdefault("access_token", "")
        st.session_state.setdefault("refresh_token", "")
        st.session_state.setdefault("messages", [])
        st.session_state.setdefault("session_id", str(uuid.uuid4()))
        st.session_state.setdefault("created_at", datetime.now().isoformat())
        st.session_state.setdefault("session_name", "")
        st.session_state.setdefault("temperature", 0.7)
        st.session_state.setdefault("selected_models", [])
        st.session_state.setdefault("prev_system_prompt", "You are a helpful assistant")
        st.session_state.setdefault("save_data_enabled", False)
        st.session_state.setdefault("show_temperature_slider", True)
        st.session_state.setdefault("sidebar_visible", True)
        st.session_state.setdefault("sidebar_view", "Configuration")

    def session_initialized(self):
        if "messages" not in st.session_state:
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.created_at = datetime.now().isoformat()
            st.session_state.session_name = ""
            st.session_state.temperature = 0.7
            st.session_state.selected_models = []

        # --- Initialize States ---
        if "show_sidebar" not in st.session_state:
            st.session_state.show_sidebar = True

        if "sidebar_view" not in st.session_state:
            st.session_state.sidebar_view = "Configuration"
            
        # Initialize system prompt if not exists
        if "prev_system_prompt" not in st.session_state:
            st.session_state.prev_system_prompt = "You are a helpful assistant"

        # Initialize data saving toggle (OFF by default)
        if "save_data_enabled" not in st.session_state:
            st.session_state.save_data_enabled = False

        # Initialize slider visibility toggle
        if "show_temperature_slider" not in st.session_state:
            st.session_state.show_temperature_slider = True

        # Initialize sidebar visibility state
        if "sidebar_visible" not in st.session_state:
            st.session_state.sidebar_visible = True

    def load_custom_css(self):
        st.markdown("""
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stDeployButton {display: none;}
        .main { padding-top: 2rem; }
        .sidebar .sidebar-content { background: #f8f9fa; }
        .status-success { background: #d4edda; color: #155724; padding: 0.5rem; border-radius: 4px; border-left: 4px solid #28a745; margin: 0.5rem 0; }
        .status-info { background: #d1ecf1; color: #0c5460; padding: 0.5rem; border-radius: 4px; border-left: 4px solid #17a2b8; margin: 0.5rem 0; }
        .status-warning { background: #fff3cd; color: #856404; padding: 0.5rem; border-radius: 4px; border-left: 4px solid #ffc107; margin: 0.5rem 0; }
        .user-message { background: #e3f2fd; padding: 1rem; border-radius: 8px; margin: 1rem 0; border-left: 4px solid #2196f3; }
        .assistant-message { background: #f5f5f5; padding: 1rem; border-radius: 8px; margin: 1rem 0; border-left: 4px solid #4caf50; }
        .arena-column { background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 1rem; margin: 0.5rem; }
        .model-label { font-weight: 600; color: #666; margin-bottom: 0.5rem; padding-bottom: 0.5rem; border-bottom: 2px solid #e0e0e0; }
        .stButton > button { background: #ffffff; color: #666; border: 1px solid #e0e0e0; border-radius: 4px; padding: 0.5rem 1rem; width: 100%; }
        .stButton > button:hover { background: #f5f5f5; border-color: #ccc; }
        .welcome-message { text-align: center; padding: 2rem; color: #666; background: #fafafa; border-radius: 8px; margin: 2rem 0; }
        </style>
        """, unsafe_allow_html=True)

    
    def convert_floats_to_decimal(self, obj):
        """Recursively convert all float values to Decimal in a nested structure."""
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self.convert_floats_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_floats_to_decimal(i) for i in obj]
        elif isinstance(obj, tuple):
            return tuple(self.convert_floats_to_decimal(i) for i in obj)
        else:
            return obj

    def save_session(self):
        if not st.session_state.get('save_data_enabled', False):
            return
    
        session_data = {
            "user_id": st.session_state.user_id,
            "session_id": st.session_state.session_id,
            "session_name": st.session_state.session_name,
            "created_at": st.session_state.created_at,
            "messages": st.session_state.messages,
            "system_prompt": st.session_state.prev_system_prompt,
            "temperature": st.session_state.temperature,
            "selected_models": st.session_state.selected_models
        }

        session_data_cleaned = self.convert_floats_to_decimal(session_data)


        try:
            self.table.put_item(Item=session_data_cleaned)
        except ClientError as e:
            st.error(f"Error saving session to DynamoDB: {e}")

    def load_all_sessions(self):
        """Load all sessions belonging to the current user."""
        try:
            response = self.table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(st.session_state.user_id)
            )
            return response.get("Items", [])
        except ClientError as e:
            st.error(f"Error fetching sessions: {e}")
            return []

    def load_session_by_id(self, session_id):
        """Load a specific session by ID for the current user."""
        try:
            response = self.table.get_item(
                Key={
                    "user_id": st.session_state.user_id,
                    "session_id": session_id
                }
            )
            return response.get("Item", None)
        except ClientError as e:
            st.error(f"Error loading session {session_id}: {e}")
            return None

    def delete_session(self, session_id):
        """Delete a specific session for the current user."""
        try:
            self.table.delete_item(
                Key={
                    "user_id": st.session_state.user_id,
                    "session_id": session_id
                }
            )
            return True
        except ClientError as e:
            st.error(f"Error deleting session: {e}")
            return False

    def clear_unsaved_data(self):
        if not st.session_state.get('save_data_enabled', False):
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.created_at = datetime.now().isoformat()
            st.session_state.session_name = ""
