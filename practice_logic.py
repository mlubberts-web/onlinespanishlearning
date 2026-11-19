"""The rules of practising: checking an answer, the rounds, and choosing the questions.
No screens in this file, which is what makes it possible to test it automatically."""
import random, re

from practice_items import MODES, clean_text, differences

ARTICLES = ("el ", "la ", "los ", "las ", "un ", "una ")
# Spanish usually leaves out the subject pronoun (hablo instead of yo hablo). Adding it or leaving
# it out never counts as a mistake in these exercise types. Not in listening, where you type what
# you hear, and not in "Fix the mistake", where the pronoun can be the mistake itself.
PRONOUN_MODES = ("verbs", "fill", "translate")
PRONOUNS = {"yo", "tú", "él", "ella", "usted", "nosotros", "nosotras", "vosotros", "vosotras",
            "ellos", "ellas", "ustedes"}
TYPED_PRONOUNS = PRONOUNS | {"tu", "el"}  # in what you type, also tú and él without the accent
MOCK_MODES = ("fill", "verbs", "words", "translate", "fix", "listen")
CHAIN = [mode for mode, _, _ in MODES]  # the order in which the exercise types follow each other

# How each small difference is described in the yellow warning. Capital letters are not in
# here, so they never give a warning. Only "Fix the mistake" checks them, through must_match,
# when the capital is the mistake itself.
WARNINGS = {"accent": "the accent", "ñ": "the ñ", "question mark": "the ¿ ? ¡ !"}


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


def answer_key(item):
    """The name under which your accepted answers to a question are saved. The PDF is left out on
    purpose, so the same question in another PDF or a themed list accepts your answer as well."""
    if item["speak"]:
        question = item["speak"]  # all listening questions have the same prompt text
    elif item["mode"] == "build":
        question = " ".join(item["tiles"])
    else:
        question = item["prompt"]
    return f"{item['mode']}|{question}|{item['hint']}"


def drop_pronoun(text, pronouns):
    """Returns the text without the subject pronoun at the start, or None when it has none.
    A ¿ or ¡ in front stays: '¿Tú hablas inglés?' becomes '¿hablas inglés?'."""
    match = re.match(r"([¿¡]*)\s*(\w+)\s+(.+)", text)  # \w+ is one word; the ( ) parts are kept
    if match and match.group(2).lower() in pronouns:
        return match.group(1) + match.group(3)
    return None


def compare_without_pronoun(item, typed, answer):
    """Compares once more with the pronoun left out, when exactly one of the two has a pronoun.
    When both have one, they must be the same, so 'él come' stays wrong for 'ella come'."""
    typed_short = drop_pronoun(typed, TYPED_PRONOUNS)
    answer_short = drop_pronoun(answer, PRONOUNS)
    if (typed_short is None) == (answer_short is None):  # both or neither have a pronoun
        return None
    return compare(item, typed_short or typed, answer_short or answer)


def check_answer(item, typed, accepted=()):
    """Returns (result, note). The result is 'right', 'near' or 'wrong'.
    'near' means yellow: it counts as correct, but something small was off.
    'accepted' are extra answers you said were right with the 'I was actually right' button."""
    typed = " ".join(typed.split())
    answers = item["answers"] + list(accepted)  # + joins two lists, like [a, b] in MATLAB

    if item["mode"] == "build":  # the tiles have no capitals or punctuation, so only the order counts
        words = clean_text(typed)
        return ("right", "") if any(words == clean_text(a) for a in answers) else ("wrong", "")

    best = None
    for answer in answers:
        warnings = compare(item, typed, answer)
        if warnings == []:  # the list is empty: nothing to warn about
            return "right", ""
        if warnings and best is None:
            best = warnings
    if best:
        return "near", warning_text(best)

    if item["mode"] == "words":  # vocabulary: the word is right, but el / la was left out
        for answer in answers:
            lower = answer.lower()
            if lower.startswith(ARTICLES):
                article, word = answer.split(" ", 1)
                warnings = compare(item, typed, word)
                if warnings is not None:
                    note = f"Correct, but learn the word with its article: {article.lower()} {word}."
                    return "near", note

    if item["mode"] in PRONOUN_MODES:  # yo, tú, ella ... added or left out
        for answer in answers:
            warnings = compare_without_pronoun(item, typed, answer)
            if warnings == []:
                return "right", ""
            if warnings:
                return "near", warning_text(warnings)

    return "wrong", ""


def done_key(item):
    """The name under which 'Mark as done' is saved for the exercise this question belongs to.
    For a PDF that is the PDF and exercise type, like 'A1_09|words'. For a themed list it is the
    list, like 'THEME_food|list:Fruit', because a list's card marks all its types at once."""
    source = item["id"].split("|")[0]  # the id starts with the PDF id or THEME_name
    if source.startswith("THEME_"):
        return f"{source}|list:{item['group']}"
    return f"{source}|{item['mode']}"


# ---------- choosing the questions ----------
KNOWN_FACTOR = 10  # a question you got right on the first try last time is chosen 10x less often
MIN_PRACTISED = 10  # a subject is only judged once you have practised this many of its questions
WEAK_BELOW = 0.70   # a subject is weak when less than 70% was right on the first try


def weight(stats):
    """How likely a question is to be chosen. Often wrong means high, often right means low,
    and right on the first try last time divides it by 10."""
    if stats is None:
        return 3  # never practised
    usual = max(1, 3 + 3 * stats["wrong"] - stats["right"])
    return usual / KNOWN_FACTOR if stats["last_ok"] else usual


def first_try_score(items, stats_by_id):
    """Returns (share right on the first try last time, number practised) for a group of questions.
    The share is None while fewer than MIN_PRACTISED of them were practised."""
    practised = [item for item in items if item["id"] in stats_by_id]
    if len(practised) < MIN_PRACTISED:
        return None, len(practised)
    right = sum(stats_by_id[item["id"]]["last_ok"] for item in practised)  # True counts as 1
    return right / len(practised), len(practised)


def weak_subjects(subjects, stats_by_id):
    """'subjects' is a list of (name, items). Returns the weak ones as (score, practised, name, items),
    the weakest first."""
    weak = []
    for name, items in subjects:
        score, practised = first_try_score(items, stats_by_id)
        if score is not None and score < WEAK_BELOW:
            weak.append((score, practised, name, items))
    return sorted(weak, key=lambda subject: subject[0])  # sorted by the score, lowest first


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


def next_step(modes, current, has_weak):
    """What comes after a finished session of type 'current'. 'modes' are the exercise types this
    PDF or list has. Returns the next type, 'weak' for your weak questions at the end, or None
    when this PDF is done. The mixed test and the weak questions are never followed by a type."""
    if current not in CHAIN:
        return None
    later = [mode for mode in CHAIN[CHAIN.index(current) + 1:] if mode in modes]
    if later:
        return later[0]
    return "weak" if has_weak else None


def score_percent(drill):
    total = len(drill["items"])
    return round(100 * (total - len(drill["first_wrong"])) / total)
