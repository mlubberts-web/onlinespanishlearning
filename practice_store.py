"""Remembers your practice results in practice.json. No screens in this file.

The file holds three parts:
    items:  for each question: {"right": 3, "wrong": 1, "last_ok": true, "box": 2, "due": "2026-11-10",
                                "last": "2026-11-07"}  (last: the date of your last answer)
    scores: for each PDF and exercise type: {"last": 80, "best": 90, "date": "2026-11-03"}
    mocks:  a list with the result of each mock exam
    accepted: answers you said were right: {"words|doctor|": ["el galeno"]}
    done:     exercises you marked as done: ["A1_09|words", "THEME_food|list:Fruit"]
"""
from datetime import date, timedelta

import clock
import storage

# Daily review: each correct answer moves a question to the next box, which waits longer.
# A wrong answer sends it back to the first box, so it returns tomorrow.
REVIEW_DAYS = [1, 3, 7, 30]


def load(path):
    # storage.py reads the file, or the online database when the app runs on the internet.
    return storage.load(path, {"items": {}, "scores": {}})


def save(path, data):
    storage.save(path, data)


def schedule(stats, correct, today):
    """Sets the box and the date this question comes back."""
    if correct:
        box = stats["box"]
        stats["due"] = (today + timedelta(days=REVIEW_DAYS[box])).isoformat()
        stats["box"] = min(box + 1, len(REVIEW_DAYS) - 1)
    else:
        stats["box"] = 0
        stats["due"] = (today + timedelta(days=REVIEW_DAYS[0])).isoformat()


def record(data, item_id, correct, today=None):
    today = today or clock.today()  # 'or' takes the second value when the first one is empty
    stats = data["items"].setdefault(item_id, {"right": 0, "wrong": 0, "last_ok": False})
    stats.setdefault("box", 0)  # results saved before the daily review existed have no box
    stats["box_before"] = stats["box"]
    stats["right" if correct else "wrong"] += 1
    stats["last_ok"] = correct
    stats["last"] = today.isoformat()  # the date of this answer, for the Schedule's dashboard
    schedule(stats, correct, today)


def last_answer_date(stats):
    """The date of your last first-try answer to a question, as text. Older results don't have
    'last', so it is worked out backwards from the review date: a right answer set the review
    REVIEW_DAYS[box_before] days ahead, a wrong one 1 day ahead."""
    if "last" in stats:
        return stats["last"]
    if "due" not in stats:
        return None
    wait = REVIEW_DAYS[stats.get("box_before", 0)] if stats["last_ok"] else REVIEW_DAYS[0]
    return (date.fromisoformat(stats["due"]) - timedelta(days=wait)).isoformat()


def change_to_correct(data, item_id, today=None):
    """For the 'I was actually right' button: replaces the wrong just recorded by a right."""
    stats = data["items"][item_id]
    stats["wrong"] -= 1
    stats["right"] += 1
    stats["last_ok"] = True
    stats["box"] = stats.get("box_before", 0)
    schedule(stats, True, today or clock.today())


def accepted_answers(data, key):
    """The answers you accepted for a question, see answer_key in practice_logic.py."""
    return data.get("accepted", {}).get(key, [])  # an older file has no "accepted" part yet


def accept(data, key, typed):
    """Remembers an answer as correct, so next time it is right straight away."""
    typed = " ".join(typed.split())
    if not typed:
        return
    answers = data.setdefault("accepted", {}).setdefault(key, [])
    if typed not in answers:
        answers.append(typed)


def unaccept(data, key, typed):
    """For a click on 'I was actually right' that was a mistake."""
    answers = data.get("accepted", {}).get(key, [])
    if typed in answers:
        answers.remove(typed)
    if not answers:
        data.get("accepted", {}).pop(key, None)  # pop removes a key from a dict


def is_marked_done(data, key):
    """True when you marked this exercise as done, see done_key in practice_logic.py."""
    return key in data.get("done", [])  # an older file has no "done" part yet


def mark_done(data, key, done):
    """Marks an exercise as done (done=True) or takes the mark away (done=False)."""
    marks = data.setdefault("done", [])
    if done and key not in marks:
        marks.append(key)
    elif not done and key in marks:
        marks.remove(key)


def save_score(data, pdf_id, mode, percent):
    pdf_scores = data["scores"].setdefault(pdf_id, {})
    old = pdf_scores.get(mode, {"best": 0})
    pdf_scores[mode] = {"last": percent, "best": max(old["best"], percent),
                        "date": clock.today().isoformat()}


def save_mock(data, result):
    data.setdefault("mocks", []).append(result)  # setdefault: an older file has no "mocks" yet


def is_mastered(data, item_id):
    """Mastered means: your most recent answer to this question was correct."""
    stats = data["items"].get(item_id)
    return bool(stats and stats["last_ok"])


def is_weak(data, item_id):
    """Weak means: wrong last time, or wrong more often than right."""
    stats = data["items"].get(item_id)
    return bool(stats and stats["wrong"] > 0
                and (not stats["last_ok"] or stats["wrong"] > stats["right"]))


def is_due(data, item_id, today=None):
    """Due means: practised before and its waiting time is over. Dates in the format 2026-11-03
    can be compared as text, because they sort the same way as the real dates."""
    stats = data["items"].get(item_id)
    if not stats:
        return False
    return stats.get("due", "") <= (today or clock.today()).isoformat()
