"""Loads and saves your results: as files on your own computer, or in an online database.

On your own computer nothing changes: progress.json, practice.json and study_log.json are files in
the app folder. Online (Streamlit Community Cloud) the server forgets its files whenever it
restarts, so there the results go to a free Supabase database, one row per person and file:

    owner   name        data
    menno   practice    {"items": {...}, "scores": {...}, ...}

After you log in, login.py writes the database and your name in your session (each visitor has
their own), so two people using the app at the same time each get their own rows. The database
address and key come from the app's secrets (see DEPLOY.md), never from the code. No screens here.
"""
import json, os, threading

import requests

from clock import session_value

TABLE = "saves"
TIMEOUT = 20  # seconds to wait for the database

_last_saved = {}  # (owner, name) -> the text saved last, so an unchanged file isn't sent again
_lock = threading.Lock()  # two pages saving at the same moment take turns on _last_saved


class StorageError(Exception):
    """The online database could not be reached."""


def database_session(url, key, owner):
    """What login.py keeps in the session under 'database'."""
    return {"url": url.rstrip("/"), "key": key, "owner": owner}


def _database():
    return session_value("database")  # None on your own computer and in the tests: files


def _address(database):
    return f"{database['url']}/rest/v1/{TABLE}"


def _headers(database):
    return {"apikey": database["key"]}


def load(path, empty):
    """The saved data of path (for example .../practice.json), or empty when there is none yet."""
    database = _database()
    if database is None:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return empty
    try:
        reply = requests.get(_address(database), headers=_headers(database), timeout=TIMEOUT,
                             params={"select": "data", "owner": f"eq.{database['owner']}",
                                     "name": f"eq.{path.stem}"})
        reply.raise_for_status()
    except requests.RequestException as error:
        # Never carry on with empty results here: the next save would overwrite the real ones.
        raise StorageError(str(error)) from error
    rows = reply.json()
    if not rows:
        return empty  # this person hasn't saved anything in this file yet
    _remember(database["owner"], path.stem, _text(rows[0]["data"]))
    return rows[0]["data"]


def _text(data):
    return json.dumps(data, ensure_ascii=False, indent=1)


def save(path, data):
    """Saves data. Online, a failed save shows a warning; the next save sends everything again."""
    text = _text(data)
    database = _database()
    if database is None:
        # Write to a temporary file first, so a crash can never leave half a file.
        tmp = path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
        return
    owner, name = database["owner"], path.stem
    with _lock:
        if _last_saved.get((owner, name)) == text:
            return  # nothing changed since the last save
    row = {"owner": owner, "name": name, "data": data}
    try:
        reply = requests.post(_address(database), json=[row], timeout=TIMEOUT,
                              params={"on_conflict": "owner,name"},
                              headers={**_headers(database),  # ** copies the headers into this dict
                                       "Prefer": "resolution=merge-duplicates,return=minimal"})
        reply.raise_for_status()
    except requests.RequestException:
        import streamlit as st  # only here, so this file works without Streamlit in the tests
        st.toast("⚠️ Your results couldn't be saved online just now. They are kept, and saved "
                 "with your next answer.")
        return
    _remember(owner, name, text)


def _remember(owner, name, text):
    with _lock:
        _last_saved[(owner, name)] = text
