"""Remembers what you studied on each day, in study_log.json. No screens in this file.

The file holds:
    days:       for each date: {"seconds": 3600, "answers": 120, "pages": 9, "extra": 30,
                                "blocks": {"review": 0, "writing": 60},
                                "first_total": 80, "first_right": 64}  (first tries and how many were right)
    mastered:   for each date, the number of questions you had mastered
    last:       when you last answered a question or turned a page, and which of the two it was
    mocks:      the official DELE mock exams you logged on the Schedule screen
    days_off:   dates on which you don't study; the plan moves that work to the other days
    hours:      your study time per day in minutes: {"weekday": 240, "weekend": 120}
    progress:   for each date, how many minutes of the plan you had finished that day (older versions)
    finished:   for each unit of the plan (a PDF read, an exercise type finished): the date it was finished
    goals:      for each date, the units on that day's list, fixed the first time you looked at it
"""
from datetime import datetime

import clock
import storage

# The time between two actions counts as study time when it is shorter than this, in seconds.
# Reading a page takes longer than answering a question, so a page may take up to 10 minutes.
MAX_GAP = {"page": 600, "answer": 180}
START_SECONDS = 20  # the first action after a break counts for this long


def load(path):
    # storage.py reads the file, or the online database when the app runs on the internet.
    return storage.load(path, {})


def save(path, log):
    storage.save(path, log)


def day(log, day_text):
    """The entry of one date, for example '2026-11-07'. Made empty the first time."""
    entry = log.setdefault("days", {}).setdefault(day_text, {})
    for key in ("seconds", "answers", "pages", "extra"):
        entry.setdefault(key, 0)
    entry.setdefault("blocks", {})
    return entry


def add_activity(log, kind, now=None):
    """Called for every answer (kind 'answer') and every new page you read (kind 'page').
    Adds the time since your previous action, unless that was a break."""
    now = now or clock.now()
    entry = day(log, now.date().isoformat())
    entry["answers" if kind == "answer" else "pages"] += 1
    last = log.get("last")
    gap = (now - datetime.fromisoformat(last["time"])).total_seconds() if last else None
    if gap is not None and 0 <= gap <= MAX_GAP[last["kind"]]:
        entry["seconds"] += round(gap)
    else:
        entry["seconds"] += START_SECONDS
    log["last"] = {"time": now.isoformat(timespec="seconds"), "kind": kind}


def add_result(log, correct, day_text=None):
    """Counts a first-try answer for the day: right or not. For the accuracy on the Progress tab."""
    entry = day(log, day_text or clock.now().date().isoformat())
    entry["first_total"] = entry.get("first_total", 0) + 1
    entry["first_right"] = entry.get("first_right", 0) + (1 if correct else 0)


def overrule_result(log, day_text=None):
    """For 'I was actually right': a wrong first try of today becomes a right one."""
    entry = day(log, day_text or clock.now().date().isoformat())
    if entry.get("first_right", 0) < entry.get("first_total", 0):
        entry["first_right"] += 1


def remember_mastered(log, day_text, count):
    """Keeps the number of questions you had mastered on each day. Returns True when it changed."""
    snapshots = log.setdefault("mastered", {})
    if snapshots.get(day_text) == count:
        return False
    snapshots[day_text] = count
    return True


def studied_minutes(log, day_text):
    """Everything you studied on one date: time in the app, the time you added yourself,
    ticked blocks such as writing, and official mock exams you took that day."""
    entry = log.get("days", {}).get(day_text)
    minutes = 0
    if entry:
        minutes += entry.get("seconds", 0) / 60 + entry.get("extra", 0) + sum(entry.get("blocks", {}).values())
    minutes += sum(m["minutes"] for m in log.get("mocks", []) if m["date"] == day_text)
    return minutes


def tick_block(log, day_text, block, minutes):
    """Ticks a block such as 'writing' as done, or unticks it when it was ticked already.
    'minutes' is added to that day; use 0 for blocks that the app times itself."""
    blocks = day(log, day_text)["blocks"]
    if block in blocks:
        del blocks[block]
    else:
        blocks[block] = minutes


def save_mock(log, level, number, day_text, minutes, parts, note=""):
    """Saves an official mock exam; a second save of the same one replaces the first."""
    mocks = [m for m in log.get("mocks", []) if (m["level"], m["number"]) != (level, number)]
    mocks.append({"level": level, "number": number, "date": day_text, "minutes": minutes,
                  "parts": parts, "note": note})
    log["mocks"] = sorted(mocks, key=lambda m: (m["level"], m["number"]))


def remove_mock(log, level, number):
    log["mocks"] = [m for m in log.get("mocks", []) if (m["level"], m["number"]) != (level, number)]


# ---------- what you finished, and each day's goal ----------
def update_finished(log, done_ids, today_text, estimates=None):
    """Writes down the date of each unit you finished, and forgets units that aren't finished
    any more (for example after unticking 'Mark as done'). Returns True when something changed.
    estimates: unit id -> a date text, used only the very first time, for what you finished before
    the dates were kept."""
    first_time = "finished" not in log
    finished = log.setdefault("finished", {})
    changed = first_time
    for unit_id in done_ids:
        if unit_id not in finished:
            guess = (estimates or {}).get(unit_id) if first_time else None
            finished[unit_id] = min(guess, today_text) if guess else today_text
            changed = True
    for unit_id in [u for u in finished if u not in done_ids]:  # a copy, so we can delete while looping
        del finished[unit_id]
        changed = True
    return changed


def finished_by(log, unit_ids, day_text):
    """How many of these units were finished on or before this date."""
    finished = log.get("finished", {})
    return sum(1 for unit_id in unit_ids if finished.get(unit_id, "9999") <= day_text)


def goal_reached(log, day_text):
    """True when everything on that day's list was finished by the end of that day.
    None when that day had no list (a day off, or before the lists existed)."""
    goal = log.get("goals", {}).get(day_text)
    if not goal:
        return None
    return finished_by(log, goal, day_text) == len(goal)


def streak(log, today_text):
    """The number of days in a row on which you finished your list, counting back from today.
    Today only counts once you have finished it; days without a list don't break the row."""
    count = 0
    for day_text in sorted((d for d in log.get("goals", {}) if d <= today_text), reverse=True):
        reached = goal_reached(log, day_text)
        if reached is None:
            continue
        if reached:
            count += 1
        elif day_text != today_text:  # today isn't over yet, so it doesn't end the row
            break
    return count
