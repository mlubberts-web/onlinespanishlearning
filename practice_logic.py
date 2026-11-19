"""The rules of practising: checking an answer, the rounds, and choosing the questions.
No screens in this file, which is what makes it possible to test it automatically."""
import random

from practice_items import clean_text, differences

ARTICLES = ("el ", "la ", "los ", "las ", "un ", "una ")
MOCK_MODES = ("fill", "verbs", "words", "translate", "fix", "listen")

# How each small difference is described in the yellow warning.
WARNINGS = {"accent": "the accent", "ñ": "the ñ", "capital": "capital letters",
            "first capital": "the capital letter", "question mark": "the ¿ ? ¡ !"}


# ---------- checking one answer ----------
def compare(item, typed, answer):
    """Compares with one correct answer. Returns the small differences to warn about,
    or None when this answer does not match."""
    found = differences(typed, answer)
    if found is None or any(kind in item["must_match"] for kind in found):
        return None
    return [kind for kind in found if kind in WARNINGS]  # this drops the commas


def warning_text(warnings):
    return "Correct, but mind " + " and ".join(WARNINGS[kind] for kind in warnings) + "."


def check_answer(item, typed):
    """Returns (result, note). The result is 'right', 'near' or 'wrong'.
    'near' means yellow: it counts as correct, but something small was off."""
    typed = " ".join(typed.split())

    if item["mode"] == "build":  # the tiles have no capitals or punctuation, so only the order counts
        words = clean_text(typed)
        return ("right", "") if any(words == clean_text(a) for a in item["answers"]) else ("wrong", "")

    best = None
    for answer in item["answers"]:
        warnings = compare(item, typed, answer)
        if warnings == []:  # the list is empty: nothing to warn about
            return "right", ""
        if warnings and best is None:
            best = warnings
    if best:
        return "near", warning_text(best)

    if item["mode"] == "words":  # vocabulary: the word is right, but el / la was left out
        for answer in item["answers"]:
            lower = answer.lower()
            if lower.startswith(ARTICLES):
                article, word = answer.split(" ", 1)
                warnings = compare(item, typed, word)
                if warnings is not None:
                    note = f"Correct, but learn the word with its article: {article.lower()} {word}."
                    return "near", note

    return "wrong", ""


# ---------- choosing the questions ----------
def weight(stats):
    """How likely a question is to be chosen. Often wrong means high, often right means low."""
    if stats is None:
        return 3  # never practised
    return max(1, 3 + 3 * stats["wrong"] - stats["right"])


def choose_items(items, stats_by_id, size):
    """Chooses 'size' different questions, with more chance for the difficult ones.
    Each item gets a random number; a high weight pushes that number up, then the highest win."""
    if size is None or size >= len(items):
        return list(items)
    score = lambda item: random.random() ** (1 / weight(stats_by_id.get(item["id"])))
    return sorted(items, key=score, reverse=True)[:size]


def choose_mock_items(items, count):
    """Chooses questions for a mock exam, spread evenly over the exercise types. Only types you
    type an answer for: clicking words or choosing el/la would not be exam-like."""
    by_mode = {mode: [i for i in items if i["mode"] == mode] for mode in MOCK_MODES}
    piles = [random.sample(pile, len(pile)) for pile in by_mode.values() if pile]
    chosen = []
    while len(chosen) < count and any(piles):
        for pile in piles:  # take one from each pile in turn, like dealing cards
            if pile and len(chosen) < count:
                chosen.append(pile.pop())
    random.shuffle(chosen)
    return chosen


# ---------- the rounds ----------
# Round 1 shows everything once. Later rounds show what was wrong in the round before, until
# all are correct once. After that the same procedure runs on what was wrong in round 1.
def new_drill(items):
    ids = [item["id"] for item in items]
    random.shuffle(ids)
    return {"items": {item["id"]: item for item in items},
            "stage": 1,            # 1 = everything, 2 = the repeat of round 1's wrong answers
            "round": 1,
            "queue": ids,          # the questions of this round, in order
            "position": 0,         # the current question in the queue (0 is the first)
            "wrong_now": [],       # wrong in this round
            "first_wrong": [],     # wrong in the very first round
            "asked": 0,            # how many answers you gave, also used to clear the input box
            "finished": False,
            "feedback": None}      # the result on screen, None while you are answering


def current_item(drill):
    return drill["items"][drill["queue"][drill["position"]]]


def is_first_attempt(drill):
    """Only the first round says what you really knew, so only that one counts for your score."""
    return drill["stage"] == 1 and drill["round"] == 1


def give_result(drill, item_id, correct):
    drill["asked"] += 1
    if not correct:
        drill["wrong_now"].append(item_id)
        if is_first_attempt(drill):
            drill["first_wrong"].append(item_id)


def change_to_correct(drill, item_id):
    """For the 'I was actually right' button."""
    drill["wrong_now"].remove(item_id)
    if is_first_attempt(drill):
        drill["first_wrong"].remove(item_id)


def go_to_next(drill):
    drill["feedback"] = None
    drill["position"] += 1
    if drill["position"] < len(drill["queue"]):
        return
    if drill["wrong_now"]:  # next round: only what was wrong
        drill["queue"] = random.sample(drill["wrong_now"], len(drill["wrong_now"]))
        drill["round"] += 1
    elif drill["stage"] == 1 and drill["first_wrong"]:  # all correct: repeat round 1's wrong ones
        drill["queue"] = random.sample(drill["first_wrong"], len(drill["first_wrong"]))
        drill["stage"], drill["round"] = 2, 1
    else:
        drill["finished"] = True
        return
    drill["position"] = 0
    drill["wrong_now"] = []


def score_percent(drill):
    total = len(drill["items"])
    return round(100 * (total - len(drill["first_wrong"])) / total)
