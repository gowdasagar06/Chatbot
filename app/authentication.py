import boto3
import os
import streamlit as st
from dotenv import load_dotenv
from botocore.exceptions import ClientError
import re

load_dotenv()


class CognitoAuthManager:
    def __init__(self):
        self.client_id = "7vjm7dikbn1srnc82l0o1u4pfd"
        self.client = boto3.client("cognito-idp", region_name="ap-south-1")

    @staticmethod
    def is_valid_email(email):
        return re.match(r"[^@]+@[^@]+\.[^@]+", email)

    def sign_up_user(self, username, password):
        try:
            self.client.sign_up(
                ClientId=self.client_id,
                Username=username,
                Password=password
            )
            return "✅ Sign-up successful! Please check your email to confirm your account."
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "UsernameExistsException":
                return "⚠️ This email is already registered. Please log in instead."
            elif error_code == "InvalidPasswordException":
                return "❌ Password does not meet policy requirements."
            elif error_code == "InvalidParameterException":
                return "❌ Invalid input. Please check your email format or password."
            else:
                return f"❌ Sign-up failed: {e.response['Error']['Message']}"

    def confirm_user_signup(self, username, confirmation_code):
        try:
            self.client.confirm_sign_up(
                ClientId=self.client_id,
                Username=username,
                ConfirmationCode=confirmation_code
            )
            return "✅ Email confirmed successfully! You can now log in."
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "CodeMismatchException":
                return "❌ Incorrect confirmation code."
            elif error_code == "ExpiredCodeException":
                return "❌ Confirmation code expired. Please request a new one."
            elif error_code == "UserNotFoundException":
                return "❌ No such user found."
            elif error_code == "NotAuthorizedException":
                return "❌ User is already confirmed."
            else:
                return f"❌ Confirmation failed: {e.response['Error']['Message']}"

    def authenticate_user(self, username, password):
        try:
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": username, "PASSWORD": password}
            )
            return response['AuthenticationResult'].get('AccessToken') if 'AuthenticationResult' in response else None
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "UserNotConfirmedException":
                return "❌ Your account is not confirmed. Please check your email."
            elif error_code == "NotAuthorizedException":
                return "❌ Incorrect email or password."
            elif error_code == "UserNotFoundException":
                return "❌ No account found with this email. Please sign up."
            else:
                return f"❌ Login failed: {e.response['Error']['Message']}"

    def initiate_forgot_password(self, username):
        try:
            self.client.forgot_password(
                ClientId=self.client_id,
                Username=username
            )
            return "📨 A password reset code has been sent to your email."
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "UserNotFoundException":
                return "❌ No such user found."
            elif error_code == "LimitExceededException":
                return "❌ Too many attempts. Please try again later."
            else:
                return f"❌ Failed to initiate reset: {e.response['Error']['Message']}"

    def confirm_forgot_password(self, username, code, new_password):
        try:
            self.client.confirm_forgot_password(
                ClientId=self.client_id,
                Username=username,
                ConfirmationCode=code,
                Password=new_password
            )
            return "✅ Password reset successful! You can now log in."
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "CodeMismatchException":
                return "❌ Incorrect confirmation code."
            elif error_code == "ExpiredCodeException":
                return "❌ Code expired. Please request a new one."
            elif error_code == "InvalidPasswordException":
                return "❌ New password doesn't meet requirements."
            else:
                return f"❌ Reset failed: {e.response['Error']['Message']}"


def render_auth_ui(
    sign_up_user,
    confirm_user_signup,
    authenticate_user,
    initiate_forgot_password,
    confirm_forgot_password
):
    # --- CUSTOM CSS ---
    st.markdown("""
    <style>
        .auth-container {
            max-width: 500px;
            margin: auto;
        }
        .auth-buttons {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 20px;
        }
        .auth-button {
            background-color: #f0f2f6;
            border: 2px solid #ccc;
            padding: 10px 24px;
            font-weight: bold;
            border-radius: 8px;
            cursor: pointer;
        }
        .auth-button.selected {
            border: 2px solid #4CAF50;
            background-color: #e6ffe6;
        }
    </style>
    """, unsafe_allow_html=True)

    # --- SESSION DEFAULTS ---
    st.session_state.setdefault("auth_mode", "Login")
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("email_confirm_pending", False)
    st.session_state.setdefault("forgot_password_stage", None)
    st.session_state.setdefault("forgot_email", "")

    # --- STOP RENDERING MAIN APP IF NOT AUTHENTICATED ---
    if not st.session_state["authenticated"]:

        # --- FORGOT PASSWORD STEP 1: EMAIL ENTRY ---
        if st.session_state.forgot_password_stage == "enter_email":
            st.title("🔐 Reset Password")
            st.session_state.forgot_email = st.text_input("Enter your registered email", value=st.session_state.forgot_email)

            if st.button("Send Reset Code"):
                if st.session_state.forgot_email:
                    result = initiate_forgot_password(st.session_state.forgot_email)
                    st.info(result)
                    if "📨" in result:
                        st.session_state.forgot_password_stage = "code_sent"
                        st.rerun()
                else:
                    st.warning("Please enter a valid email.")

            if st.button("⬅️ Back to Login"):
                st.session_state.forgot_password_stage = None
                st.rerun()

        # --- FORGOT PASSWORD STEP 2: CODE + NEW PASSWORD ---
        elif st.session_state.forgot_password_stage == "code_sent":
            st.title("📨 Confirm Code & Reset Password")
            code = st.text_input("Confirmation Code")
            new_password = st.text_input("New Password", type="password")

            if st.button("Reset Password"):
                result = confirm_forgot_password(
                    st.session_state.forgot_email,
                    code,
                    new_password
                )
                st.info(result)
                if "✅" in result:
                    st.session_state.forgot_password_stage = None
                    st.session_state.auth_mode = "Login"
                    st.rerun()

            if st.button("Resend Code"):
                result = initiate_forgot_password(st.session_state.forgot_email)
                st.info(result)

            if st.button("⬅️ Back to Login"):
                st.session_state.forgot_password_stage = None
                st.rerun()

        # --- LOGIN / SIGNUP MAIN PAGE ---
        else:
            st.markdown('<div class="auth-container">', unsafe_allow_html=True)
            st.title("🔐 Welcome to Chatbot Arena")
            st.subheader("Please log in or create an account")

            # --- AUTH MODE BUTTONS ---
            col1, col2 = st.columns(2)
            with col1:
                login_class = "auth-button selected" if st.session_state.auth_mode == "Login" else "auth-button"
                if st.button("🔑 Login", key="login_btn", use_container_width=True):
                    st.session_state.auth_mode = "Login"
                    st.session_state.forgot_password_stage = None

            with col2:
                signup_class = "auth-button selected" if st.session_state.auth_mode == "Sign Up" else "auth-button"
                if st.button("🆕 Sign Up", key="signup_btn", use_container_width=True):
                    st.session_state.auth_mode = "Sign Up"
                    st.session_state.email_confirm_pending = False

            # --- SHARED FIELDS ---
            email = st.text_input("Email", key="auth_email")
            password = st.text_input("Password", type="password", key="auth_password")

            # --- SIGNUP FLOW ---
            if st.session_state.auth_mode == "Sign Up":
                if not st.session_state.email_confirm_pending:
                    if st.button("Create Account"):
                        result = sign_up_user(email, password)
                        st.info(result)
                        if "✅" in result:
                            st.session_state.email_confirm_pending = True
                            st.rerun()
                else:
                    code = st.text_input("Enter confirmation code sent to your email")
                    if st.button("Confirm Account"):
                        result = confirm_user_signup(email, code)
                        st.info(result)
                        if "✅" in result:
                            st.session_state.email_confirm_pending = False
                            st.session_state.auth_mode = "Login"
                            st.rerun()

            # --- LOGIN FLOW ---
            elif st.session_state.auth_mode == "Login":
                if st.button("Login"):
                    result = authenticate_user(email, password)
                    if result and "❌" not in result:
                        st.success("Login successful! 🎉")
                        st.session_state.authenticated = True
                        st.session_state.user_id = email
                        st.session_state.access_token = result
                        st.rerun()
                    else:
                        st.error(result)

                if st.button("Forgot Password?"):
                    st.session_state.forgot_password_stage = "enter_email"
                    st.session_state.forgot_email = email
                    st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

        st.stop()

