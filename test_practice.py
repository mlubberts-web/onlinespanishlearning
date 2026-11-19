"""Checks the practice questions of all 59 PDFs and the rules of the rounds.
Run with:  .venv\\Scripts\\python.exe test_practice.py
Use this after changing the practice files or the content. It does not touch your progress."""
import collections, json, tempfile
from pathlib import Path

import practice_logic as logic
import practice_store as store
from practice_items import MODES, build_items, clean_text, without_accents

HERE = Path(__file__).parent
problems = []


def expect(condition, message):
    if not condition:
        problems.append(message)


# ---------- every question of every PDF ----------
catalog = json.loads((HERE / "data" / "catalog.json").read_text(encoding="utf-8"))
totals = collections.Counter()
all_items = []
for pdf in catalog:
    document = json.loads((HERE / "data" / "content" / pdf["content"]).read_text(encoding="utf-8"))
    items = build_items(pdf["id"], document)
    all_items += items
    ids = [i["id"] for i in items]
    expect(len(ids) == len(set(ids)), f"{pdf['id']}: two questions with the same id")
    expect(any(i["mode"] == "fill" for i in items), f"{pdf['id']}: no grammar exercises")
    for item in items:
        totals[item["mode"]] += 1
        name = f"{pdf['id']} {item['mode']} {item['prompt']!r}"
        expect(item["prompt"].strip() and item["answers"], f"{name}: empty question")
        expect("*" not in "".join(item["answers"]), f"{name}: star left in answer")
        for answer in item["answers"]:
            expect(answer.strip(), f"{name}: empty answer")
            result = logic.check_answer(item, answer)[0]
            expect(result == "right", f"{name}: its own answer {answer!r} gives {result}")
            # Dots must not matter at all, for any exercise type.
            no_dots = answer.replace(".", "")
            if no_dots.strip():
                result = logic.check_answer(item, no_dots)[0]
                expect(result == "right", f"{name}: {no_dots!r} without dots gives {result}")
            # Without accents: wrong only where the accent has to be right, otherwise yellow.
            loose = without_accents(answer)
            if loose != answer and item["mode"] != "build":
                result = logic.check_answer(item, loose)[0]
                wanted = "wrong" if "accent" in item["must_match"] else "near"
                if len(item["answers"]) == 1:  # with more answers another one could match exactly
                    expect(result == wanted, f"{name}: {loose!r} gives {result}, wanted {wanted}")
        if item["mode"] == "verbs":
            expect("accent" in item["must_match"], f"{name}: accents must matter in verbs")
        if item["mode"] == "fix":  # a wrong sentence retyped without changes may never pass
            result = logic.check_answer(item, item["prompt"])[0]
            expect(result == "wrong", f"{name}: unchanged mistake gives {result}")
        expect(logic.check_answer(item, "xyzzy")[0] == "wrong", f"{name}: accepts nonsense")
        expect(logic.check_answer(item, "")[0] == "wrong", f"{name}: accepts an empty answer")
        if item["mode"] == "build":
            built = " ".join(item["tiles"])
            expect(len(item["tiles"]) >= 3, f"{name}: too few tiles")
            expect(logic.check_answer(item, built)[0] == "right", f"{name}: tiles give {built!r}")

# ---------- the themed word lists ----------
LATIN_AMERICAN = {"carro", "computadora", "celular", "jugo", "manejar", "boleto", "papa", "frijol", "frijoles",
                  "durazno", "chamaco", "ómnibus", "tiquete", "refrigeradora", "mesero", "mesera",
                  "elote", "ejote", "chícharo", "betabel"}
for path in sorted((HERE / "data" / "themes").glob("*.json")):
    theme = json.loads(path.read_text(encoding="utf-8"))
    pairs = theme["items"]
    spanish_words = [pair[0] for pair in pairs]
    expect(100 <= len(pairs) <= 200, f"{path.stem}: {len(pairs)} words, wanted 100 to 200")
    expect(len(spanish_words) == len(set(spanish_words)), f"{path.stem}: a word appears twice: "
           + str([w for w, n in collections.Counter(spanish_words).items() if n > 1]))
    for spanish, english in pairs:
        expect(not (set(clean_text(spanish).split()) & LATIN_AMERICAN), f"{path.stem}: not Spain Spanish? {spanish}")
    items = build_items(f"THEME_{path.stem}", {"blocks": [{"type": "verbpairs", "title": theme["title"], "items": pairs}]})
    all_items += items
    for item in items:
        totals[item["mode"]] += 1
        for answer in item["answers"]:
            expect(logic.check_answer(item, answer)[0] == "right", f"{path.stem} {item['prompt']!r}: own answer {answer!r}")

print("Questions per exercise type:")
for mode, title, _ in MODES:
    print(f"  {title}: {totals[mode]}")
print(f"  Total: {sum(totals.values())}")

# ---------- grading rules, with real cases from the audit ----------
by_prompt = {(i["id"].split("|")[0][:5], i["mode"], i["prompt"]): i for i in all_items}


def grade(key, typed):
    return logic.check_answer(by_prompt[key], typed)[0]


cases = [
    # the accent is the exercise: a missing accent is wrong
    (("A1_01", "fill", "telefono"), "telefono", "wrong"),
    (("A1_01", "fill", "telefono"), "teléfono", "right"),
    # the capital is the mistake: wrong if it stays, only the first letter is a yellow warning
    (("A1_01", "fix", "Hablo Español."), "Hablo Español.", "wrong"),
    (("A1_01", "fix", "Hablo Español."), "Hablo español.", "right"),
    (("A1_01", "fix", "Hablo Español."), "hablo español", "near"),
    # the comma is the mistake in this one, and the only place where a comma counts
    (("C1_08", "fix", "Mi hermano, vive en Madrid."), "Mi hermano, vive en Madrid.", "wrong"),
    (("C1_08", "fix", "Mi hermano, vive en Madrid."), "Mi hermano vive en Madrid", "right"),
    # capitals are yellow, a missing dot is nothing at all
    (("A2_01", "words", "to dance"), "bailar", "right"),
    (("A1_09", "words", "Monday"), "LUNES", "near"),
    (("A1_09", "words", "Monday"), "Lunes", "near"),
    (("A1_09", "words", "mother"), "la madre", "right"),
    (("A2_01", "translate", "Yesterday I ate paella in a bar."), "Ayer comí paella en un bar", "right"),
    (("A2_01", "translate", "Yesterday I ate paella in a bar."), "ayer comí paella en un bar.", "near"),
    # question and exclamation marks are yellow
    (("A1_09", "fill", "Where is the station?"), "¿Dónde está la estación?", "right"),
    (("A1_09", "fill", "Where is the station?"), "Dónde está la estación", "near"),
    (("A1_09", "fill", "Good morning!"), "Buenos días", "near"),
    # article: left out is yellow, the wrong article is wrong
    (("A1_09", "words", "mother"), "madre", "near"),
    (("A1_09", "words", "mother"), "el madre", "wrong"),
    # ñ written as n is yellow
    (("A1_09", "words", "Spain"), "Espana", "near"),
    (("A1_09", "words", "Spain"), "España", "right"),
    # accents matter in verbs, but the ñ is still only yellow there
    (("A2_01", "verbs", "hablar · preterite · él / ella / usted"), "habló", "right"),
    (("A2_01", "verbs", "hablar · preterite · él / ella / usted"), "hablo", "wrong"),
    # accents are yellow outside verbs
    (("A1_09", "words", "Wednesday"), "miercoles", "near"),
    # one of several correct forms
    (("A1_05", "words", "Spanish"), "española", "right"),
    (("A1_05", "words", "Spanish"), "español", "right"),
    # stem-change reminder and an optional word
    (("A2_10", "words", "to hurt"), "doler", "right"),
    (("A1_09", "words", "(very) well"), "muy bien", "right"),
    (("A1_09", "words", "(very) well"), "bien", "right"),
    # a choice of one word inside a sentence
    (("B2_08", "fix", "¡Qué día muy bonito!"), "¡Qué día tan bonito!", "right"),
    (("B2_08", "fix", "¡Qué día muy bonito!"), "¡Qué día más bonito!", "right"),
]
for key, typed, wanted in cases:
    expect(grade(key, typed) == wanted, f"{key} typed {typed!r}: wanted {wanted}, got {grade(key, typed)}")
note = logic.check_answer(by_prompt[("A1_09", "words", "mother")], "madre")[1]
expect("la madre" in note, f"the warning must name the article, was {note!r}")
note = logic.check_answer(by_prompt[("A1_09", "words", "Spain")], "Espana")[1]
expect("ñ" in note, f"the warning must name the ñ, was {note!r}")
expect(("A1_05", "words", "big") in by_prompt and ("A1_05", "words", "small") in by_prompt,
       "big / small should be two questions")
expect(by_prompt[("A1_09", "fill", "juice")]["answers"][0] == "el zumo", "Spain Spanish: juice is el zumo")

# ---------- Spanish to English, el or la, listening ----------
reverse_cases = [
    (("A1_09", "reverse", "la madre"), "mother", "right"), (("A1_09", "reverse", "la madre"), "the mother", "right"),
    (("A1_09", "reverse", "lunes"), "monday", "near"), (("A1_09", "reverse", "lunes"), "Monday", "right"),
    (("A1_09", "reverse", "cero"), "0", "right"),
    (("A2_01", "reverse", "bailar"), "to dance", "right"), (("A2_01", "reverse", "bailar"), "dance", "right"),
    (("C1_10", "reverse", "abordar"), "to address", "right"), (("C1_10", "reverse", "abordar"), "tackle", "right"),
    (("A1_03", "reverse", "caer"), "to fall", "right"), (("A1_03", "reverse", "caer"), "to jump", "wrong"),
    (("A1_05", "reverse", "grande"), "big", "right"), (("A1_05", "reverse", "grande"), "small", "wrong"),
]
for key, typed, wanted in reverse_cases:
    expect(key in by_prompt, f"{key} is missing")
    if key in by_prompt:
        expect(grade(key, typed) == wanted, f"{key} typed {typed!r}: wanted {wanted}, got {grade(key, typed)}")

gender = [i for i in all_items if i["mode"] == "gender"]
expect(all(i["choices"] == ["el", "la"] and i["answers"][0] in ("el", "la") for i in gender), "el/la questions are wrong")
expect(not any("masculine" in i["hint"] or "feminine" in i["hint"] for i in gender), "the hint gives the gender away")
expect(not any("/" in i["prompt"] for i in gender), "words with both genders can't be asked")
expect(logic.check_answer(by_prompt[("A1_09", "gender", "madre")], "la")[0] == "right", "madre is la")
expect(logic.check_answer(by_prompt[("A1_09", "gender", "madre")], "el")[0] == "wrong", "madre is not el")

listening = [i for i in all_items if i["mode"] == "listen"]
expect(listening and all(i["speak"] == i["answers"][0] and "______" not in i["speak"] for i in listening), "listening data")
expect(all(i["speak"] not in i["prompt"] for i in listening), "the sentence may not be on the screen while listening")

# ---------- mock exam ----------
pool = [i for i in all_items if i["id"].startswith("B2")]
mock = logic.choose_mock_items(pool, 40)
expect(len(mock) == 40 and len({i["id"] for i in mock}) == 40, "a mock needs 40 different questions")
counts = collections.Counter(i["mode"] for i in mock)
expect(set(counts) <= set(logic.MOCK_MODES), f"only typed exercise types in a mock: {counts}")
expect(len(counts) >= 3 and max(counts.values()) - min(counts.values()) <= 1, f"a mock must be spread evenly: {counts}")
expect(len(logic.choose_mock_items(pool[:5], 40)) <= 5, "a small pool must not fail")

# ---------- daily review: 1, 3, 7 and 30 days ----------
from datetime import date, timedelta
day = date(2026, 1, 1)
data = {"items": {}, "scores": {}}
expect(not store.is_due(data, "q", day), "a new question is not due yet")
for days in (1, 3, 7, 30, 30):
    store.record(data, "q", True, day)
    expect(data["items"]["q"]["due"] == (day + timedelta(days=days)).isoformat(), f"correct must wait {days} days")
    expect(not store.is_due(data, "q", day + timedelta(days=days - 1)), f"not due before {days} days")
    expect(store.is_due(data, "q", day + timedelta(days=days)), f"due after {days} days")
    day += timedelta(days=days)
store.record(data, "q", False, day)
expect(data["items"]["q"]["due"] == (day + timedelta(days=1)).isoformat() and data["items"]["q"]["box"] == 0,
       "a wrong answer must come back tomorrow")
store.change_to_correct(data, "q", day)
expect(data["items"]["q"]["due"] == (day + timedelta(days=30)).isoformat(), "'I was right' must restore the schedule")
old_file = {"items": {"old": {"right": 1, "wrong": 0, "last_ok": True}}, "scores": {}}
expect(store.is_due(old_file, "old", day), "results from before the daily review must be due")
store.record(old_file, "old", True, day)
expect("box" in old_file["items"]["old"], "results from before the daily review must keep working")

# ---------- the rounds, from the design in the brief ----------
items = [{"id": name} for name in "abcd"]
drill = logic.new_drill(items)
seen, round_history = [], []


def answer_round(drill, wrong):
    asked = []
    start = (drill["stage"], drill["round"])
    while not drill["finished"] and (drill["stage"], drill["round"]) == start:
        item_id = logic.current_item(drill)["id"]
        asked.append(item_id)
        logic.give_result(drill, item_id, item_id not in wrong)
        logic.go_to_next(drill)
    return sorted(asked)


expect(answer_round(drill, {"a", "b"}) == list("abcd"), "round 1 must show everything once")
expect(answer_round(drill, {"a"}) == ["a", "b"], "round 2 must show only round 1's wrong ones")
expect(answer_round(drill, set()) == ["a"], "round 3 must show only round 2's wrong ones")
expect(not drill["finished"] and drill["stage"] == 2, "then the repeat must start")
expect(answer_round(drill, {"b"}) == ["a", "b"], "the repeat must use round 1's wrong ones")
expect(answer_round(drill, set()) == ["b"], "the repeat must also go on until all are correct")
expect(drill["finished"], "the drill must end after that")
expect(logic.score_percent(drill) == 50, "score must only count round 1")

drill = logic.new_drill(items)
expect(answer_round(drill, set()) == list("abcd") and drill["finished"], "all correct must end at once")

drill = logic.new_drill(items[:1])
logic.give_result(drill, "a", False)
logic.change_to_correct(drill, "a")
logic.go_to_next(drill)
expect(drill["finished"] and logic.score_percent(drill) == 100, "'I was actually right' must count as right")

# ---------- more wrong means chosen more often ----------
pool = [{"id": str(n)} for n in range(10)]
hard = {"0": {"right": 0, "wrong": 5, "last_ok": False}}
picked = sum(any(i["id"] == "0" for i in logic.choose_items(pool, hard, 2)) for _ in range(3000))
expect(picked > 1200, f"a difficult question must be chosen far more often, was {picked} of 3000")
expect(len(logic.choose_items(pool, {}, None)) == 10, "'all' must keep every question")
expect(len({i["id"] for i in logic.choose_items(pool, {}, 5)}) == 5, "no question twice in one session")

# ---------- saving ----------
with tempfile.TemporaryDirectory() as folder:
    path = Path(folder) / "practice.json"
    data = store.load(path)
    store.record(data, "x¿ñ", False)
    expect(store.is_weak(data, "x¿ñ") and not store.is_mastered(data, "x¿ñ"), "wrong must be weak")
    store.change_to_correct(data, "x¿ñ")
    expect(store.is_mastered(data, "x¿ñ") and not store.is_weak(data, "x¿ñ"), "override must clear weak")
    store.save_score(data, "pdf", "fill", 90)
    store.save_score(data, "pdf", "fill", 70)
    store.save(path, data)
    again = store.load(path)
    expect(again["scores"]["pdf"]["fill"]["best"] == 90 and again["scores"]["pdf"]["fill"]["last"] == 70,
           "best and last score must be kept")
    expect(again["items"]["x¿ñ"]["right"] == 1, "results must survive saving, also with ñ and ¿")

# ---------- result ----------
print()
if problems:
    print(f"{len(problems)} PROBLEMS:")
    for problem in problems[:60]:
        print(" -", problem)
else:
    print("All checks passed.")
