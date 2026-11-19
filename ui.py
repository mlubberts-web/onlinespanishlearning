"""Small pieces shared by app.py and practice_screen.py."""
import streamlit as st


def go_home():
    st.session_state.view = "home"
    st.session_state.level = None


def go_level(level):
    st.session_state.view = "level"
    st.session_state.level = level


def go_view(view):
    st.session_state.view = view
    st.session_state.level = None


def hero(eyebrow, title, text, share):
    """The dark banner at the top of a screen. 'share' is the filled part of the bar, 0 to 1."""
    st.html(f'<div class="hero"><div class="hero-eyebrow">{eyebrow}</div>'
            f'<div class="hero-title">{title}</div><div class="hero-text">{text}</div>'
            f'<div class="hero-track"><div class="hero-fill" style="width:{share:.1%}"></div></div></div>')
