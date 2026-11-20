"""Accounts that people make themselves in the online version (with the invite code).

They live in the 'accounts' table of the online database, one row per person:

    name    password_hash                       timezone          created
    ana     pbkdf2_sha256$200000$<salt>$<hash>   Europe/Madrid     2026-11-20

The password itself is never stored, only a scrambled version of it (a "hash"): checking a password
means scrambling it again in the same way and comparing. Accounts written in the app's secrets
(see login.py) keep working next to these. No screens here; login.py has the forms.
"""
import hashlib, hmac, os, re

import storage

TABLE = "accounts"
ROUNDS = 200_000  # how often the password is scrambled: makes guessing slow
NAME_RULE = re.compile(r"[a-z0-9_-]{2,20}")  # small letters, digits, - and _; 2 to 20 of them
MIN_PASSWORD = 8


def hash_password(password):
    salt = os.urandom(16)  # random, so two people with the same password get different hashes
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ROUNDS)
    return f"pbkdf2_sha256${ROUNDS}${salt.hex()}${digest.hex()}"


def password_matches(password, stored):
    """True when password scrambles to the stored hash."""
    try:
        _, rounds, salt, digest = stored.split("$")
        again = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
    except ValueError:  # a damaged row: never let anyone in with it
        return False
    return hmac.compare_digest(again.hex(), digest)


def valid_name(name):
    return bool(NAME_RULE.fullmatch(name))


def get(database, name):
    """The row of this account, or None when there is no such account."""
    if not valid_name(name):
        return None
    rows = storage.request(database, "GET", TABLE, params={"select": "*", "name": f"eq.{name}"}).json()
    return rows[0] if rows else None


def create(database, name, password, timezone):
    """Makes the account. False when the name is already taken."""
    row = {"name": name, "password_hash": hash_password(password), "timezone": timezone}
    reply = storage.request(database, "POST", TABLE, body=[row], prefer="return=minimal")
    return reply.status_code != 409


def every(database):
    """All accounts, by name, without their password hashes."""
    return storage.request(database, "GET", TABLE,
                           params={"select": "name,timezone,created", "order": "name"}).json()


def set_password(database, name, password):
    storage.request(database, "PATCH", TABLE, params={"name": f"eq.{name}"},
                    body={"password_hash": hash_password(password)}, prefer="return=minimal")


def remove(database, name):
    """Removes the account and all of its results."""
    storage.request(database, "DELETE", storage.TABLE, params={"owner": f"eq.{name}"})
    storage.request(database, "DELETE", TABLE, params={"name": f"eq.{name}"})
    storage.forget(name)  # so a new account with the same name starts clean
