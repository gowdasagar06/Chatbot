from app.services.model_streamer import ModelStreamer
from app.authentication import CognitoAuthManager, render_auth_ui
from app.ui.chat_interface import render_chat_interface
from app.ui.sidebar import SidebarManager
from app.chat_history_db import ChatSessionManagerDynamoDB
import streamlit as st


def main():
    session_handler = ChatSessionManagerDynamoDB()
    auth_manager = CognitoAuthManager()
    sidebar = SidebarManager(session_handler)
    st.set_page_config(page_title="Chatbot Arena", page_icon="🤖", layout="wide")
    session_handler.load_custom_css()

    # Initialize session state
    session_handler.initialize_session_state()
    session_handler.session_initialized()

    render_auth_ui(
            auth_manager.sign_up_user,
            auth_manager.confirm_user_signup,
            auth_manager.authenticate_user,
            auth_manager.initiate_forgot_password,
            auth_manager.confirm_forgot_password,
        )


    sidebar.render_sidebar()
    # Main chat interface
    render_chat_interface()

if __name__ == "__main__":
    main()
