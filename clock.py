"""Today's date and the time, in the time zone of the person using the app. No screens in this file.

On your own computer this is simply your computer's clock. Online, the server runs on UTC time
and serves several people at once, maybe in different countries, so login.py writes each person's
time zone in their session (st.session_state, which every visitor has their own copy of).
"""
from datetime import datetime
from zoneinfo import ZoneInfo


def session_value(key):
    """A value from the current visitor's session, or None outside the app (as in the tests).
    Read on every call, because Streamlit runs button actions before the page itself."""
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except ImportError:
        return None
    if get_script_run_ctx(suppress_warning=True) is None:  # not inside a running page
        return None
    return st.session_state.get(key)


def now():
    """The local time without a time zone attached, like datetime.now() on your own computer."""
    zone = session_value("time_zone")
    if not zone:
        return datetime.now()
    return datetime.now(ZoneInfo(zone)).replace(tzinfo=None)


def today():
    return now().date()
