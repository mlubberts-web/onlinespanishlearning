"""Logging in and making an account, only for the online version of the app.

On your own computer there are no secrets, so start() does nothing and everything is saved in files.
Online, the app's secrets (typed into Streamlit Community Cloud, see DEPLOY.md) look like this:

    [supabase]
    url = "https://abcdefgh.supabase.co"
    key = "sb_secret_..."

    [signup]
    code = "the invite code"      # leave this part out to switch making accounts off

    [users.menno]
    password = "a long password"
    timezone = "Europe/Amsterdam"
    admin = true                  # may reset passwords and remove accounts

Each [users.<name>] part is one person. Everyone else makes their own account with the invite code;
those accounts are kept in the database (see accounts.py). Results are kept apart by name.
After logging in, the address in the browser gets a ?login=... part: bookmark that address and the
app logs you in by itself next time.
"""
import hashlib, hmac, time
from zoneinfo import available_timezones

import streamlit as st

import accounts
import storage
from storage import StorageError

DEFAULT_TIME_ZONE = "Europe/Amsterdam"
DATABASE_DOWN = "The online database can't be reached right now. Try again in a minute."


def secrets_part(name):
    """A part of the secrets, such as 'users', or None when it is missing (always on your own computer)."""
    try:
        return st.secrets[name]
    except Exception:  # no secrets file at all, or no such part in it
        return None


def token(name, secret, key):
    """The code in a bookmarked login address. It changes when the password changes, and nobody
    can make one without knowing the database key, which only the server has."""
    return hmac.new(key.encode(), f"{name}:{secret}".encode(), hashlib.sha256).hexdigest()[:32]


def find(name, database):
    """The account with this name, from the secrets or else from the database, or None.
    'secret' is what the bookmark code is made from: the password for accounts in the secrets
    (as before), the password hash for accounts in the database."""
    users = secrets_part("users") or {}
    if name in users:
        person = users[name]
        return {"name": name, "password": person["password"], "secret": person["password"],
                "timezone": person.get("timezone", DEFAULT_TIME_ZONE),
                "admin": bool(person.get("admin", False))}
    row = accounts.get(database, name)  # may raise StorageError
    if row is None:
        return None
    return {"name": name, "hash": row["password_hash"], "secret": row["password_hash"],
            "timezone": row["timezone"], "admin": False}


def password_right(account, password):
    if "password" in account:
        return hmac.compare_digest(password, account["password"])
    return accounts.password_matches(password, account["hash"])


def remember(account):
    """Keeps who is logged in in the session, so button actions (which Streamlit runs before
    start()) know it too."""
    st.session_state.user = account["name"]
    st.session_state.time_zone = account["timezone"]
    st.session_state.is_admin = account["admin"]


def log_in(account, key):
    """Logs in after the form, and puts the bookmark code in the address."""
    remember(account)
    st.query_params["login"] = f"{account['name']}.{token(account['name'], account['secret'], key)}"
    st.rerun()


def start():
    """Runs at the top of every page load. Returns the name of who is logged in, or None on your own
    computer. Online, without a login it shows the login screen and stops the page there."""
    settings = secrets_part("supabase")
    if settings is None:
        return None  # nothing in the session: storage.py uses files and clock.py the computer's clock
    database = {"url": settings["url"], "key": settings["key"]}
    if "user" not in st.session_state or "time_zone" not in st.session_state:
        account = None
        try:
            account = from_bookmark(database)
        except StorageError:
            st.error(DATABASE_DOWN)
        if account is None:
            login_screen(database)
            st.stop()  # nothing else of the page is shown until you log in
        remember(account)
    name = st.session_state.user
    st.session_state.database = storage.database_session(settings["url"], settings["key"], name)
    return name


def from_bookmark(database):
    """The account in a bookmarked address (?login=name.code), when its code is right."""
    name, _, code = st.query_params.get("login", "").partition(".")  # 'menno.ab12' -> 'menno', '.', 'ab12'
    if not name:
        return None
    account = find(name, database)
    if account and hmac.compare_digest(code, token(name, account["secret"], database["key"])):
        return account
    return None


def login_screen(database):
    st.title("📘 Spanish Learning Program")
    if secrets_part("signup") is None:
        login_form(database)
        return
    log_in_tab, new_tab = st.tabs(["Log in", "Create an account"])
    with log_in_tab:
        login_form(database)
    with new_tab:
        signup_form(database)


def login_form(database):
    with st.form("login"):
        name = st.text_input("Name").strip().lower()
        password = st.text_input("Password", type="password")
        sent = st.form_submit_button("Log in", type="primary")
    if sent:
        try:
            account = find(name, database)
        except StorageError:
            st.error(DATABASE_DOWN)
            return
        if account and password_right(account, password):
            log_in(account, database["key"])
        time.sleep(1)  # makes guessing passwords slow
        st.error("That name and password don't match.")


def time_zones():
    """The time zones to choose from, such as Europe/Madrid, and the one the browser uses."""
    zones = sorted(z for z in available_timezones() if "/" in z and not z.startswith(("Etc/", "SystemV/")))
    try:
        guess = st.context.timezone  # the visitor's own time zone, as their browser reports it
    except Exception:
        guess = None
    return zones, guess if guess in zones else DEFAULT_TIME_ZONE


def signup_form(database):
    zones, guess = time_zones()
    with st.form("signup"):
        code = st.text_input("Invite code", type="password",
                             help="You get this from the person who sent you the link.")
        name = st.text_input("Name", help="You log in with it. Small letters and digits, 2 to 20.")
        password = st.text_input("Password", type="password",
                                 help=f"At least {accounts.MIN_PASSWORD} characters.")
        again = st.text_input("Password again", type="password")
        zone = st.selectbox("Your time zone", zones, index=zones.index(guess),
                            help="Decides when a new day starts in your study plan.")
        sent = st.form_submit_button("Create my account", type="primary")
    if not sent:
        return
    name = name.strip().lower()
    if not hmac.compare_digest(code.strip(), str(secrets_part("signup")["code"])):
        time.sleep(1)  # makes guessing the code slow
        st.error("That invite code isn't right.")
    elif not accounts.valid_name(name):
        st.error("Choose a name of 2 to 20 small letters or digits (- and _ are allowed too), without spaces.")
    elif len(password) < accounts.MIN_PASSWORD:
        st.error(f"Choose a password of at least {accounts.MIN_PASSWORD} characters.")
    elif password != again:
        st.error("The two passwords are not the same.")
    else:
        try:
            made = name not in (secrets_part("users") or {}) and accounts.create(database, name, password, zone)
            account = find(name, database) if made else None
        except StorageError:
            st.error(DATABASE_DOWN)
            return
        if not made:
            st.error("That name is already taken. Choose another one.")
            return
        log_in(account, database["key"])


def log_out():
    st.query_params.clear()
    for widget_key in list(st.session_state):  # list() first: the loop changes what it walks over
        del st.session_state[widget_key]


def sidebar_part(name):
    """Who is logged in, with a button to log out. Only online."""
    st.caption(f"Logged in as **{name.capitalize()}**. Bookmark this page to log in by itself next time.")
    st.button("Log out", key="log_out", on_click=log_out, width="stretch")


# ---------- for admins: the accounts people made ----------
# The buttons use on_click: Streamlit runs those before the page is drawn, so the list and the
# message below already show the result of the click.

def admin_did(problem=None, done=None):
    """What the last admin click did, shown at the top of the Accounts part."""
    st.session_state.admin_message = ("error", problem) if problem else ("success", done)


def admin_set_password(database):
    who, new = st.session_state.admin_password_who, st.session_state.admin_new_password
    if len(new) < accounts.MIN_PASSWORD:
        return admin_did(f"Choose a password of at least {accounts.MIN_PASSWORD} characters.")
    try:
        accounts.set_password(database, who, new)
    except StorageError:
        return admin_did(DATABASE_DOWN)
    admin_did(done=f"{who} has a new password. Their old bookmark stops working.")


def admin_remove(database):
    who = st.session_state.admin_remove_who
    if not st.session_state.admin_remove_sure:
        return admin_did("Tick the box first.")
    try:
        accounts.remove(database, who)
    except StorageError:
        return admin_did(DATABASE_DOWN)
    admin_did(done=f"{who} and all their results were removed.")


def admin_part():
    """For admins only: the accounts people made, with a new password or removing one."""
    if not st.session_state.get("is_admin"):
        return
    database = st.session_state.database
    message = st.session_state.pop("admin_message", None)  # (kind, text) of the last click
    with st.expander("👥 Accounts", expanded=message is not None):  # open to show the message
        if message:
            kind, text = message
            (st.error if kind == "error" else st.success)(text)
        if secrets_part("signup") is None:
            st.caption("Making accounts is switched off. Add a [signup] part with a code to the "
                       "secrets to switch it on (see DEPLOY.md).")
        else:
            st.caption("New people make their own account with the app's address and the invite "
                       "code from the secrets. Accounts written in the secrets are changed there.")
        try:
            people = accounts.every(database)
        except StorageError:
            st.error(DATABASE_DOWN)
            return
        if not people:
            st.caption("Nobody has made an account yet.")
            return
        for person in people:
            st.markdown(f"**{person['name']}** · {person['timezone']} · since {person['created']}")
        names = [person["name"] for person in people]
        with st.form("admin_password", clear_on_submit=True):
            st.selectbox("Account", names, key="admin_password_who")
            st.text_input("New password", type="password", key="admin_new_password")
            st.form_submit_button("Set new password", width="stretch",
                                  on_click=admin_set_password, args=(database,))
        with st.form("admin_remove", clear_on_submit=True):
            st.selectbox("Account", names, key="admin_remove_who")
            st.checkbox("Yes, remove this account and all its results", key="admin_remove_sure")
            st.form_submit_button("Remove account", width="stretch",
                                  on_click=admin_remove, args=(database,))

