"""
인증 모듈 — streamlit-authenticator 래퍼
"""
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "auth_config.yaml")


def _load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.load(f, Loader=SafeLoader)


def _save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


def require_auth() -> tuple[stauth.Authenticate, str | None, bool]:
    """
    로그인 게이트. 미로그인 시 로그인/회원가입 UI 표시 후 st.stop().
    Returns (authenticator, username, is_logged_in)
    """
    config = _load_config()
    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )

    name, auth_status, username = authenticator.login(
        location="main",
        fields={
            "Form name": "🔐 로그인",
            "Username": "아이디",
            "Password": "비밀번호",
            "Login": "로그인",
        },
    )

    if auth_status is False:
        st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
        _show_register(authenticator, config)
        st.stop()

    if auth_status is None:
        st.info("아이디와 비밀번호를 입력해주세요.")
        _show_register(authenticator, config)
        st.stop()

    return authenticator, username, True


def _show_register(authenticator: stauth.Authenticate, config: dict) -> None:
    with st.expander("처음 방문하셨나요? 회원가입"):
        try:
            email, username, name = authenticator.register_user(
                location="main",
                fields={
                    "Form name": "회원가입",
                    "Email": "이메일",
                    "Username": "아이디",
                    "Password": "비밀번호",
                    "Repeat password": "비밀번호 확인",
                    "Register": "가입하기",
                },
            )
            if email:
                _save_config(config)
                st.success("가입 완료! 로그인해주세요.")
        except Exception as e:
            st.error(str(e))


def logout_button(authenticator: stauth.Authenticate) -> None:
    authenticator.logout(button_name="로그아웃", location="sidebar")
