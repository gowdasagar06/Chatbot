import uuid
import streamlit as st
from datetime import datetime


class SidebarManager:
    def __init__(self, session_handler):
        self.session_handler = session_handler

    def render_sidebar(self):
        with st.sidebar:
            st.header("Sidebar Menu")

            # Tabs: Config / Sessions
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⚙️ Config"):
                    st.session_state.sidebar_view = "Configuration"
            with col2:
                if st.button("📜 Sessions"):
                    st.session_state.sidebar_view = "Session History"

            if st.session_state.sidebar_view == "Configuration":
                self._render_model_selection()
                self._render_model_behavior()
                self._render_data_management()
                self._render_session_control()

            elif st.session_state.sidebar_view == "Session History":
                self._render_session_history()

    # def _render_model_selection(self):
    #     with st.expander("🤖 Model Selection", expanded=False):
    #         model_checkboxes = {
    #             "Amazon-Titan-Lite": st.checkbox("Amazon-Titan-Lite", value="Amazon-Titan-Lite" in st.session_state.selected_models),
    #             "Amazon-Titan-Express": st.checkbox("Amazon-Titan-Express", value="Amazon-Titan-Express" in st.session_state.selected_models),
    #             #"Amazon-Nova-Pro": st.checkbox("Amazon-Nova-Pro", value="Amazon-Nova-Pro" in st.session_state.selected_models),
    #             # "Claude-4-Sonnet": st.checkbox("Claude-4-Sonnet", value="Claude-4-Sonnet" in st.session_state.selected_models),
    #             # "DeepSeek-R1": st.checkbox("DeepSeek-R1", value="DeepSeek-R1" in st.session_state.selected_models),
    #             # "Claude-4-Opus": st.checkbox("Claude-4-Opus", value="Claude-4-Opus" in st.session_state.selected_models),
    #             # "Claude-3.5-Haiku": st.checkbox("Claude-3.5-Haiku", value="Claude-3.5-Haiku" in st.session_state.selected_models),
    #         }

    #         st.session_state.selected_models = [model for model, selected in model_checkboxes.items() if selected]
    #         selected_count = len(st.session_state.selected_models)

    #         # Set mode based on model count
    #         st.session_state.arena_mode = selected_count >= 4
    #         st.session_state.three_model_mode = selected_count == 3
    #         st.session_state.two_model_mode = selected_count == 2
    #         st.session_state.single_model_mode = selected_count == 1

    #         if st.session_state.arena_mode:
    #             st.success("Arena Mode Active")
    #         elif selected_count > 0:
    #             st.info(f"Selected Models: {', '.join(st.session_state.selected_models)}")
    #         else:
    #             st.warning("No model selected.")

    def _render_model_selection(self):
        with st.expander("🤖 Model Selection", expanded=False):
            # Amazon model definitions from your dictionary
            amazon_models = {
                "Nova Pro": {
                    "id": "amazon.nova-pro-v1",
                    "key": "nova-pro",
                    "provider": "Amazon",
                    "type": "text",
                    "quality": "high"
                },
                "Nova Premier": {
                    "id": "amazon.nova-premier-v1",
                    "key": "nova-premier",
                    "provider": "Amazon",
                    "type": "text",
                    "quality": "enterprise"
                },
                "Nova Lite": {
                    "id": "amazon.nova-lite-v1",
                    "key": "nova-lite",
                    "provider": "Amazon",
                    "type": "text",
                    "quality": "basic"
                },
                "Titan Text G1 - Premier": {
                    "id": "amazon.titan-text-premier-v1",
                    "key": "titan-premier",
                    "provider": "Amazon",
                    "type": "text",
                    "quality": "high"
                },
                "Titan Text G1 - Lite": {
                    "id": "amazon.titan-text-lite-v1",
                    "key": "titan-lite",
                    "provider": "Amazon",
                    "type": "text",
                    "quality": "low"
                },
                "Titan Text G1 - Express": {
                    "id": "amazon.titan-text-express-v1",
                    "key": "titan-express",
                    "provider": "Amazon",
                    "type": "text",
                    "quality": "medium"
                }
            }

            if "selected_models" not in st.session_state:
                st.session_state.selected_models = []

            model_checkboxes = {}

            for label, config in amazon_models.items():
                key = config["key"]
                model_checkboxes[label] = st.checkbox(
                    label,
                    value=label in st.session_state.selected_models
                )

            st.session_state.selected_models = [
                label for label, selected in model_checkboxes.items() if selected
            ]
            selected_count = len(st.session_state.selected_models)

            # Update mode flags
            st.session_state.arena_mode = selected_count >= 4
            st.session_state.three_model_mode = selected_count == 3
            st.session_state.two_model_mode = selected_count == 2
            st.session_state.single_model_mode = selected_count == 1

            # Mode indicator messages
            if st.session_state.arena_mode:
                st.success("Arena Mode Active")
            elif selected_count > 0:
                st.info(f"Selected Models: {', '.join(st.session_state.selected_models)}")
            else:
                st.warning("No model selected.")

    def _render_model_behavior(self):

        if "temperature" not in st.session_state or not isinstance(st.session_state.temperature, float):
            st.session_state.temperature = 0.7  # Default float value

        if "show_temperature_slider" not in st.session_state:
            st.session_state.show_temperature_slider = True  # default value
        with st.expander("🎛️ Model Behavior", expanded=False):
            if st.session_state.show_temperature_slider:
                st.session_state.temperature = st.slider(
                    "Response Creativity (Temperature)", 0.0, 1.0,
                    value=st.session_state.temperature, step=0.1)
            else:
                st.markdown(f"Temperature: **{st.session_state.temperature}** (Hidden)")

            st.subheader("System Prompt")
            system_prompt = st.text_area("System behavior", value=st.session_state.prev_system_prompt, height=100)

            if system_prompt != st.session_state.prev_system_prompt:
                # Save session if needed
                if st.session_state.messages and st.session_state.save_data_enabled:
                    self.session_handler.save_session()

                if not st.session_state.save_data_enabled:
                    self.session_handler.clear_unsaved_data()

                # Reset session
                st.session_state.messages = []
                st.session_state.session_id = str(uuid.uuid4())
                st.session_state.created_at = datetime.now().isoformat()
                st.session_state.prev_system_prompt = system_prompt
                st.session_state.session_name = ""
                st.success("New session started due to prompt change.")
                st.rerun()

    def _render_data_management(self):
        with st.expander("📁 Data Management", expanded=False):
            if "save_data_enabled" not in st.session_state:
                st.session_state.save_data_enabled = False

            current_value = st.session_state.save_data_enabled
            new_value = st.toggle("Enable Data Saving", value=current_value)

            if new_value != current_value:
                st.session_state.save_data_enabled = new_value
                if new_value:
                    st.success("Data saving enabled.")
                else:
                    st.warning("Data saving disabled. Session data will be cleared on new session.")
                    if st.session_state.get("messages"):
                        self.session_handler.clear_unsaved_data()
                    st.rerun()

            status = "ON" if st.session_state.save_data_enabled else "OFF"
            st.markdown(f'<div class="status-info">Data Saving: **{status}**</div>', unsafe_allow_html=True)

    def _render_session_control(self):
        with st.expander("🧹 Session Control", expanded=False):
            if st.button("New Chat"):
                if st.session_state.messages and st.session_state.save_data_enabled:
                    self.session_handler.save_session()

                st.session_state.messages = []
                st.session_state.session_id = str(uuid.uuid4())
                st.session_state.created_at = datetime.now().isoformat()
                st.session_state.session_name = ""
                st.rerun()

    def _render_session_history(self):
        st.subheader("Past Conversations")

        if not st.session_state.save_data_enabled:
            st.warning("Data saving is disabled. Enable it to view session history.")
            return

        sessions = self.session_handler.load_all_sessions()
        if sessions:
            sorted_sessions = sorted(sessions, key=lambda x: x["created_at"], reverse=True)
            for session in sorted_sessions:
                with st.expander(f"{session['session_name'] or 'Unnamed Session'} — {session['created_at'][:19]}"):
                    for msg in session["messages"][:3]:
                        if msg["role"] == "user":
                            st.markdown(f"**User:** {msg['content'][:100]}{'...' if len(msg['content']) > 100 else ''}")
                        elif msg["role"] == "assistant":
                            if "responses" in msg:
                                for model, response in msg["responses"].items():
                                    st.markdown(f"**{model}:** {response[:100]}{'...' if len(response) > 100 else ''}")
                            elif "content" in msg:
                                st.markdown(f"**Assistant:** {msg['content'][:100]}{'...' if len(msg['content']) > 100 else ''}")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Load", key=f"load_{session['session_id']}"):
                            if st.session_state.messages and st.session_state.save_data_enabled:
                                self.session_handler.save_session()

                            st.session_state.session_id = session['session_id']
                            st.session_state.session_name = session['session_name']
                            st.session_state.created_at = session['created_at']
                            st.session_state.messages = session['messages']
                            st.session_state.prev_system_prompt = session.get('system_prompt', 'You are a helpful assistant')
                            st.session_state.temperature = session.get('temperature', 0.7)
                            st.session_state.selected_models = session.get('selected_models', [])
                            st.success(f"Loaded session: {session['session_name'] or 'Unnamed Session'}")
                            st.rerun()
                    with col2:
                        if st.button("Delete", key=f"delete_{session['session_id']}"):
                            if self.session_handler.delete_session(session['session_id']):
                                st.success("Session deleted successfully")
                                st.rerun()
        else:
            st.info("No past sessions found.")
