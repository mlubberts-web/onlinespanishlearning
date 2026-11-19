"""Turns the source data of one PDF into practice questions. No screens in this file.

Every question, of every type, is one dict with the same keys:
    id             unique name, used to remember your results in practice.json
    mode           which exercise type it belongs to, see MODES
    prompt         what you see, for example "to eat"
    hint           small extra clue, can be empty
    answers        list of all answers that count as correct
    show           the correct answer as it is shown to you afterwards
    why            short explanation, can be empty
    group          topic within the PDF, for example "Travel" (words only)
    tiles          the words to click (build the sentence only)
    must_match     small differences that make the answer wrong here, see differences() below.
                   Everywhere else they only give a yellow warning.
    speak          the sentence the browser reads aloud (listening only)
    choices        the buttons to choose from (el or la only)

MATLAB note: a dict is like a struct, except that you write item["prompt"] instead of
item.prompt. A list is like a cell array, and its first element is number 0, not 1.
"""
import re, unicodedata

# The exercise types, in the order they appear on the screen: (mode, title, description).
MODES = [
    ("fill", "📝 Grammar exercises", "The exercises from the PDF. Type the missing part."),
    ("words", "🔤 Words", "See the English, type the Spanish."),
    ("reverse", "🔄 Words, Spanish to English", "See the Spanish, type the English."),
    ("gender", "⚖️ el or la?", "See a noun, choose its article."),
    ("verbs", "🔁 Verb forms", "Type the right form for the tense and person."),
    ("listen", "🎧 Listening", "Hear a sentence, type what you hear."),
    ("build", "🧩 Build the sentence", "Click the words in the right order."),
    ("translate", "💬 Translate sentences", "Type the whole sentence in Spanish."),
    ("fix", "🔍 Fix the mistake", "Type the sentence the way it should be."),
]

PERSONS = ["yo", "tú", "él / ella / usted", "nosotros", "vosotros", "ellos / ellas / ustedes"]

# In these PDFs the accents are the subject itself, so a missing accent is simply wrong.
ACCENT_PDFS = ("A1_01", "C1_08")

ARTICLE_WORDS = ("el ", "la ", "los ", "las ", "un ", "una ")

ACCENT_LETTERS = str.maketrans("áéíóúü", "aeiouu")  # ñ is handled separately
QUESTION_MARKS = "¿?¡!"
COMMA_MARKS = ",;:"
OTHER_PUNCTUATION = ".\"'«»…—()"  # never matters: not wrong, and no yellow warning either


def words_only(text):
    """The words without any punctuation. Capitals and accents stay."""
    for mark in QUESTION_MARKS + COMMA_MARKS + OTHER_PUNCTUATION:
        text = text.replace(mark, " ")
    return " ".join(unicodedata.normalize("NFC", text).split())


def clean_text(text):
    return words_only(text).lower()


def without_accents(text):
    return text.translate(ACCENT_LETTERS)


def plain_letters(text):
    """The text reduced as far as possible: no capitals, accents, ñ or punctuation."""
    return without_accents(clean_text(text)).replace("ñ", "n")


def marks_in(text, marks):
    return [character for character in text if character in marks]


def differences(typed, answer):
    """Compares two texts. Returns None when they are different words, and otherwise the list
    of small differences, empty when there are none. Dots never appear in this list."""
    a, b = words_only(typed), words_only(answer)
    if plain_letters(a) != plain_letters(b):
        return None
    found = []
    if a.lower().replace("ñ", "n") != b.lower().replace("ñ", "n"):
        found.append("accent")
    if without_accents(a.lower()) != without_accents(b.lower()):
        found.append("ñ")
    capitals_a, capitals_b = [c.isupper() for c in a], [c.isupper() for c in b]
    if capitals_a[1:] != capitals_b[1:]:  # [1:] means everything except the first element
        found.append("capital")
    elif capitals_a != capitals_b:
        found.append("first capital")
    if marks_in(typed, QUESTION_MARKS) != marks_in(answer, QUESTION_MARKS):
        found.append("question mark")
    if marks_in(typed, COMMA_MARKS) != marks_in(answer, COMMA_MARKS):
        found.append("comma")  # only counts in the few questions that are about commas
    return found


def what_the_mistake_is(wrong, answers):
    """A 'fix the mistake' question like 'Hablo Español.' is about the capital letter, so that
    has to be right, or retyping the wrong sentence unchanged would count as correct."""
    for answer in answers:
        found = differences(wrong, answer)
        if found is not None:
            return found
    return []


def optional_versions(text):
    """'(muy) bien' gives both 'muy bien' and 'bien'."""
    if "(" not in text:
        return [text]
    kept = " ".join(text.replace("(", "").replace(")", "").split())
    left_out = " ".join(re.sub(r"\([^)]*\)", " ", text).split())
    return [kept, left_out]


def word_answers(text):
    """'el primo / la prima' gives both forms. '(ue)' only reminds you of the stem change."""
    text = re.sub(r"\s*\((?:ie|ue|i|u|zc)\)", "", text)
    answers = []
    for part in text.split(" / "):
        answers += optional_versions(part)  # += adds a list to a list, like [a, b] in MATLAB
    return answers


def sentence_answers(text):
    """Splits the different ways of writing a correct sentence.
    'Se enfadó. / Se puso furioso.' is two sentences; '¡Qué día tan / más bonito!' is one
    sentence with a choice of one word in the middle."""
    parts = text.split(" / ")
    if len(parts) == 1 or all(part.rstrip()[-1] in ".!?" for part in parts):
        versions = parts
    else:
        before, after = parts[0].split(), parts[1].split()
        versions = [" ".join(before + after[1:]), " ".join(before[:-1] + after)]
    answers = []
    for version in versions:
        answers += optional_versions(version)
    return answers


def add_item(items, pdf_id, mode, prompt, answers, hint="", show=None, why="", group="", must_match=(),
             unique=None, tiles=(), speak="", choices=()):
    """Adds one question to the dict 'items'. The same prompt twice means one question with
    more correct answers: 'doctor' can be el médico and also el doctor.
    'unique' is for questions that share a prompt but are different, like listening."""
    # An f-string fills in the {values}, like sprintf in MATLAB.
    item_id = f"{pdf_id}|{mode}|{unique}" if unique else f"{pdf_id}|{mode}|{prompt}|{hint}"
    if item_id in items:
        old = items[item_id]
        new_answers = [a for a in answers if a not in old["answers"]]
        if new_answers:
            old["answers"] += new_answers
            old["show"] += f"  or  {show or answers[0]}"
        return
    items[item_id] = {"id": item_id, "mode": mode, "prompt": prompt, "hint": hint,
                      "answers": answers, "show": show or answers[0], "why": why, "group": group,
                      "tiles": list(tiles), "must_match": list(must_match), "speak": speak,
                      "choices": list(choices)}


def english_answers(english, spanish):
    """All the ways to write the English side: 'to tackle, address' accepts 'to tackle', 'tackle',
    'to address' and 'address'. Text in brackets is a remark, unless it comes first: '(very) well'."""
    parts = [part.strip() for part in re.split(r",| / ", english) if part.strip()]
    is_verb = parts[0].startswith("to ")
    is_noun = spanish.lower().startswith(ARTICLE_WORDS)
    answers = []
    for part in parts:
        part = re.sub(r"(?<=\S)\s*\(.*?\)", "", part)  # a remark in brackets after a word
        for version in optional_versions(part):
            bare = version[3:] if version.startswith("to ") else version
            answers.append(version)
            if is_verb:
                answers += [bare, f"to {bare}"]
            if is_noun:
                answers += [f"the {version}", f"a {version}", f"an {version}"]
    return list(dict.fromkeys(answers))  # removes doubles and keeps the order


def add_word(items, pdf_id, english, spanish, group, show=None):
    """One word pair gives three questions: to Spanish, to English, and its article."""
    add_item(items, pdf_id, "words", english, word_answers(spanish), show=show, group=group)
    add_item(items, pdf_id, "reverse", spanish, english_answers(english, spanish), show=english, group=group)
    match = re.fullmatch(r"(el|la) ([^/()]+)", spanish.strip(), flags=re.IGNORECASE)
    if match:  # 'el primo / la prima' can't be asked, since both articles are correct
        article, noun = match.group(1).lower(), match.group(2)
        hint = re.sub(r"\s*\((?:masculine|feminine)\)", "", english)  # or the hint gives it away
        add_item(items, pdf_id, "gender", noun, [article], hint=hint, show=f"{article} {noun}",
                 group=group, choices=["el", "la"])


def add_listening(items, pdf_id, sentence):
    """One dictation question, if the sentence has at least three words."""
    text = sentence_answers(sentence)[0]
    if len(clean_text(text).split()) >= 3:
        add_item(items, pdf_id, "listen", "Listen and type what you hear.", [text],
                 unique=text, speak=text)


def add_word_pairs(items, pdf_id, block):
    title = block.get("title", "")
    if title == "Letter and name":  # letter names are not translations
        return
    for left, right in block["items"]:
        if block.get("check"):  # lists like: hacer -> hecho (done, made)
            kind = {"participle": "past participle", "gerund": "gerund"}[block["check"]]
            form = re.sub(r"\s*\(.*\)", "", right)
            add_item(items, pdf_id, "verbs", f"{left} · {kind}", [form], must_match=["accent"])
        elif title == "Numbers":
            add_item(items, pdf_id, "words", left, [right], group=title)
            add_item(items, pdf_id, "reverse", right, [left], group=title)
        elif " · " in right:  # queso -> KEH-so · cheese
            add_word(items, pdf_id, right.split(" · ")[-1], left, title, show=left)
        else:
            lefts, rights = left.split(" / "), right.split(" / ")
            if len(lefts) == len(rights) and len(lefts) > 1:  # big / small: two questions
                for spanish, english in zip(lefts, rights):  # zip walks through both lists at once
                    add_word(items, pdf_id, english, spanish, title)
            else:
                add_word(items, pdf_id, right, left, title, show=left)


def add_verb_forms(items, pdf_id, verb, meaning, tense, forms, persons):
    for person, form in zip(persons, forms):
        form = form.replace("*", "")  # the stars only mark the irregular part in the PDF
        # In verbs the accent changes the meaning: hablo is "I speak", habló is "he spoke".
        add_item(items, pdf_id, "verbs", f"{verb} · {tense} · {person}", [form], hint=meaning,
                 must_match=["accent"])


def add_sentence(items, pdf_id, english, spanish):
    answers = sentence_answers(spanish)
    add_item(items, pdf_id, "translate", english, answers, show=spanish)


def add_tiles(items, pdf_id, prompt, spanish):
    """One 'build the sentence' question, if the sentence has at least three words."""
    first_answer = sentence_answers(spanish)[0]
    tiles = clean_text(first_answer).split()
    if len(tiles) < 3:
        return
    if f"{pdf_id}|build|{first_answer}" not in items:
        add_item(items, pdf_id, "build", prompt, sentence_answers(spanish), show=spanish,
                 unique=first_answer, tiles=tiles)
    add_listening(items, pdf_id, spanish)


def build_items(pdf_id, document):
    """Returns the list of all practice questions of one PDF."""
    items = {}
    accent_pdf = pdf_id.startswith(ACCENT_PDFS)
    for block in document["blocks"]:
        kind = block.get("type")

        if kind == "verbpairs":
            add_word_pairs(items, pdf_id, block)

        elif kind == "exercises":
            for e in block["items"]:
                add_item(items, pdf_id, "fill", e["q"],
                         [e["a"], e["full"]] if e["a"] != e["full"] else [e["a"]],
                         hint=e.get("hint", ""), show=e["full"], why=e.get("why", ""),
                         must_match=["accent"] if accent_pdf else [])
                if e.get("hint", "").startswith("translate"):
                    if len(e["a"].split()) > 2:
                        add_sentence(items, pdf_id, e["q"], e["a"])
                        add_tiles(items, pdf_id, e["q"], e["a"])
                    else:
                        add_word(items, pdf_id, e["q"], e["a"], "")
                else:
                    add_tiles(items, pdf_id, "Put the words in the right order.", e["full"])

        elif kind == "translations":
            for t in block["items"]:
                add_sentence(items, pdf_id, t["q"], t["a"])
                add_tiles(items, pdf_id, t["q"], t["a"])

        elif kind == "mistakes":
            for wrong, right, why in block["rows"]:
                if right.startswith("Both are correct") or wrong.startswith("Never say"):
                    continue  # these two rows give advice and contain no sentence to correct
                answers = sentence_answers(right)
                add_item(items, pdf_id, "fix", wrong, answers, show=right, why=why,
                         must_match=what_the_mistake_is(wrong, answers))

        elif kind == "conj":
            forms = block.get("forms") or [block["stem"] + end for end in block["endings"]]
            add_verb_forms(items, pdf_id, block["verb"], block.get("meaning", ""),
                           block.get("tense", "present"), forms, PERSONS)
            for spanish, english in block.get("examples", []):
                add_sentence(items, pdf_id, english, spanish)
                add_tiles(items, pdf_id, english, spanish)

        elif kind == "conjgrid":
            for verb in block["verbs"]:
                add_verb_forms(items, pdf_id, verb["inf"], verb.get("meaning", ""),
                               block.get("tense", "present"), verb["forms"],
                               block.get("persons", PERSONS))
    return list(items.values())
