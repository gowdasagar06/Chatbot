import streamlit as st
import asyncio
from app.services.model_streamer import ModelStreamer
from app.chat_history_db import ChatSessionManagerDynamoDB
import os

def render_chat_interface():
    streamer = ModelStreamer()
    session_handler = ChatSessionManagerDynamoDB()
    # Main chat interface
    model_map = streamer.load_model_config("/home/ec2-user/Chatbot/config/model_config.json")
    
    if not st.session_state.messages:
        st.markdown("""
        <div class="welcome-message">
            <h3>Welcome to Chatbot Arena</h3>
            <p>Start a conversation by typing your message below</p>
        </div>
        """, unsafe_allow_html=True)

    # Display chat messages
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(
                f"<div class='user-message'><strong>You:</strong><br>{message['content']}</div>",
                unsafe_allow_html=True
            )
        elif message["role"] == "assistant":
            if isinstance(message.get("responses"), dict) and message["responses"]:
                keys = list(message["responses"].keys())

                # Ensure keys are non-empty before rendering columns
                if keys:
                    cols = st.columns(len(keys))
                    for i, key in enumerate(keys):
                        with cols[i]:
                            pretty_name = key.replace("-", " ").title()
                            st.markdown(
                                f"<div class='arena-column'><div class='model-label'>{pretty_name}</div><div>{message['responses'][key]}</div></div>",
                                unsafe_allow_html=True
                            )
            elif "content" in message:
                st.markdown(
                    f"<div class='assistant-message'><strong>Assistant:</strong><br>{message['content']}</div>",
                    unsafe_allow_html=True
                )

    # Chat input
    if user_query := st.chat_input("Type your message..."):
        if not st.session_state.selected_models:
            st.error("Please select at least one model")
            return

        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_query})
        
        # Set session name from first user message
        if len(st.session_state.messages) == 1 and not st.session_state.session_name:
            st.session_state.session_name = user_query[:60]

        with st.spinner("Generating response..."):
            # Create placeholders for streaming responses
            placeholders = {}
            cols = st.columns(len(st.session_state.selected_models))
            for i, model_name in enumerate(st.session_state.selected_models):
                with cols[i]:
                    st.markdown(f"<div class='arena-column'><div class='model-label'>{model_name}</div></div>", unsafe_allow_html=True)
                    placeholders[model_name] = st.empty()

            try:
                # Get responses from selected models
                responses = asyncio.run(
                    streamer.stream_models(
                        st.session_state.selected_models,
                        st.session_state.prev_system_prompt,
                        st.session_state.messages,
                        st.session_state.temperature,
                        placeholders
                    )
                )
                
                # Add assistant responses
                st.session_state.messages.append({
                    "role": "assistant",
                    "responses": {
                        model_map[name]["key"]: responses[name] for name in st.session_state.selected_models
                    }
                })
                
                # Auto-save session only if saving is enabled
                if st.session_state.save_data_enabled:
                    session_handler.save_session()
                
            except Exception as e:
                st.error(f"Error generating response: {e}")
        
        st.rerun()
