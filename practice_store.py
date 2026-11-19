"""Remembers your practice results in practice.json. No screens in this file.

The file holds three parts:
    items:  for each question: {"right": 3, "wrong": 1, "last_ok": true, "box": 2, "due": "2026-11-10"}
    scores: for each PDF and exercise type: {"last": 80, "best": 90, "date": "2026-11-03"}
    mocks:  a list with the result of each mock exam
"""
import json, os
from datetime import date, timedelta

# Daily review: each correct answer moves a question to the next box, which waits longer.
# A wrong answer sends it back to the first box, so it returns tomorrow.
REVIEW_DAYS = [1, 3, 7, 30]


def load(path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"items": {}, "scores": {}}


def save(path, data):
    # Write to a temporary file first, so a crash can never leave half a progress file.
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


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
    today = today or date.today()  # 'or' takes the second value when the first one is empty
    stats = data["items"].setdefault(item_id, {"right": 0, "wrong": 0, "last_ok": False})
    stats.setdefault("box", 0)  # results saved before the daily review existed have no box
    stats["box_before"] = stats["box"]
    stats["right" if correct else "wrong"] += 1
    stats["last_ok"] = correct
    schedule(stats, correct, today)


def change_to_correct(data, item_id, today=None):
    """For the 'I was actually right' button: replaces the wrong just recorded by a right."""
    stats = data["items"][item_id]
    stats["wrong"] -= 1
    stats["right"] += 1
    stats["last_ok"] = True
    stats["box"] = stats.get("box_before", 0)
    schedule(stats, True, today or date.today())


def save_score(data, pdf_id, mode, percent):
    pdf_scores = data["scores"].setdefault(pdf_id, {})
    old = pdf_scores.get(mode, {"best": 0})
    pdf_scores[mode] = {"last": percent, "best": max(old["best"], percent),
                        "date": date.today().isoformat()}


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
    return stats.get("due", "") <= (today or date.today()).isoformat()
