"""Logging in, only for the online version of the app.

On your own computer there are no secrets, so start() does nothing and everything is saved in files.
Online, the app's secrets (typed into Streamlit Community Cloud, see DEPLOY.md) look like this:

    [supabase]
    url = "https://abcdefgh.supabase.co"
    key = "sb_secret_..."

    [users.menno]
    password = "a long password"
    timezone = "Europe/Amsterdam"

Each [users.<name>] part is one person; their results are kept apart in the database by that name.
After logging in, the address in the browser gets a ?login=... part: bookmark that address and the
app logs you in by itself next time.
"""
import hashlib, hmac, time

import streamlit as st

import storage

DEFAULT_TIME_ZONE = "Europe/Amsterdam"


def secrets_part(name):
    """A part of the secrets, such as 'users', or None when it is missing (always on your own computer)."""
    try:
        return st.secrets[name]
    except Exception:  # no secrets file at all, or no such part in it
        return None


def token(name, password, key):
    """The code in a bookmarked login address. It changes when the password changes, and nobody
    can make one without knowing the database key, which only the server has."""
    return hmac.new(key.encode(), f"{name}:{password}".encode(), hashlib.sha256).hexdigest()[:32]


def start():
    """Runs at the top of every page load. Returns the name of who is logged in, or None on your own
    computer. Online, without a login it shows the login form and stops the page there."""
    database = secrets_part("supabase")
    if database is None:
        return None  # nothing in the session: storage.py uses files and clock.py the computer's clock
    users = secrets_part("users") or {}
    name = st.session_state.get("user")
    if name is None:
        name = from_bookmark(users, database["key"])
    if name is None or name not in users:
        login_form(users, database["key"])
        st.stop()  # nothing else of the page is shown until you log in
    # Kept in the session, so button actions (which Streamlit runs before this) know them too.
    st.session_state.user = name
    st.session_state.database = storage.database_session(database["url"], database["key"], name)
    st.session_state.time_zone = users[name].get("timezone", DEFAULT_TIME_ZONE)
    return name


def from_bookmark(users, key):
    """The name in a bookmarked address (?login=name.code), when its code is right."""
    name, _, code = st.query_params.get("login", "").partition(".")  # 'menno.ab12' -> 'menno', '.', 'ab12'
    if name in users and hmac.compare_digest(code, token(name, users[name]["password"], key)):
        return name
    return None


def login_form(users, key):
    st.title("📘 Spanish Learning Program")
    with st.form("login"):
        name = st.text_input("Name").strip().lower()
        password = st.text_input("Password", type="password")
        sent = st.form_submit_button("Log in", type="primary")
    if sent:
        right = name in users and hmac.compare_digest(password, users[name]["password"])
        if right:
            st.session_state.user = name
            st.query_params["login"] = f"{name}.{token(name, password, key)}"
            st.rerun()
        time.sleep(1)  # makes guessing passwords slow
        st.error("That name and password don't match.")


def log_out():
    st.query_params.clear()
    for widget_key in list(st.session_state):  # list() first: the loop changes what it walks over
        del st.session_state[widget_key]


def sidebar_part(name):
    """Who is logged in, with a button to log out. Only online."""
    st.caption(f"Logged in as **{name.capitalize()}**. Bookmark this page to log in by itself next time.")
    st.button("Log out", key="log_out", on_click=log_out, width="stretch")
