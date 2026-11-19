"""The practice screens: choosing an exercise type for a PDF, answering, and the result.

How Streamlit works, coming from MATLAB: the whole script runs again from top to bottom after
every click. Normal variables are forgotten each time, so everything that must be remembered
lives in st.session_state, which works like a struct that survives the reruns.
The on_click functions ("callbacks") run first, and then the screen is drawn with the new state.
"""
import html, json, random
from pathlib import Path

import streamlit as st

import practice_logic as logic
import practice_store as store
from practice_items import MODES, build_items, build_theme_items
from ui import go_home, go_level, go_view, hero, log_activity, log_overrule

HERE = Path(__file__).parent
PRACTICE_FILE = HERE / "practice.json"
SIZES = {"10": 10, "20": 20, "All": None}
DEFAULT_SIZE = "All"
EXTRA_TITLES = {"test": "🎯 Mixed test", "weak": "💪 Weak questions"}
# app.py puts its function for opening the reader in here, for the "Next PDF" button.
ACTIONS = {}


def mode_title(mode):
    """'words' gives '🔤 Words, English to Spanish'."""
    return next((title for m, title, _ in MODES if m == mode), EXTRA_TITLES.get(mode, mode))


def size_buttons(key):
    """The row of buttons for the number of questions. Returns 10, 20 or None for all of them.
    required=True means one button is always chosen: clicking the chosen one does nothing."""
    choice = st.segmented_control("Questions per session", list(SIZES), default=DEFAULT_SIZE,
                                  required=True, key=key)
    if choice != DEFAULT_SIZE:
        st.caption("The questions you often get wrong are chosen more often, and the ones you got "
                   "right on the first try last time 10 times less often.")
    return SIZES[choice]


# ---------- the 'Skip what I know' switch ----------
def skip_known():
    """The switch is saved in practice.json, so it stays as you left it after a restart."""
    return practice_data().get("settings", {}).get("skip_known", False)


def save_skip(widget_key):
    practice_data().setdefault("settings", {})["skip_known"] = st.session_state[widget_key]
    store.save(PRACTICE_FILE, practice_data())


def skip_switch(widget_key):
    st.session_state[widget_key] = skip_known()  # the same switch on every screen
    st.toggle("Skip what I know", key=widget_key, on_change=save_skip, args=(widget_key,),
              help="Leaves out the questions you got right on the first try last time, and exercises "
                   "you marked as done. The daily review still brings them back after 1, 3, 7 and 30 days.")


def is_known(item):
    return store.is_mastered(practice_data(), item["id"]) or is_marked(item)


def leave_out_known(items):
    """Returns (the questions to ask, how many known ones were left out)."""
    if not skip_known():
        return items, 0
    unknown = [item for item in items if not is_known(item)]
    return unknown, len(items) - len(unknown)


def show_notice():
    """A message left by a button for the next screen, like 'you know all of these'."""
    if "notice" in st.session_state:
        st.info(st.session_state.pop("notice"))  # pop takes it out, so it shows only once
ACCENT_KEYS = ["á", "é", "í", "ó", "ú", "ü", "ñ", "¿", "¡"]

STYLE = """
<style>
  .prompt-card { background: #fff; border: 1px solid #e3ddd1; border-radius: 12px; padding: 22px 26px; }
  .prompt-kind { color: #8a8f9c; font-size: .8rem; font-weight: 700; letter-spacing: .06em;
                 text-transform: uppercase; }
  .prompt-text { color: #1f2a44; font-size: 1.6rem; font-weight: 600; line-height: 1.35; margin-top: 4px; }
  .prompt-hint { color: #5c6475; font-size: 1.05rem; margin-top: 6px; }
  .accent-key { background: #fff; border: 1px solid #d5cfc2; border-radius: 6px; color: #1f2a44;
                cursor: pointer; font-size: 1rem; margin: 0 4px 4px 0; min-width: 34px; padding: 4px 8px; }
  .accent-key:hover { border-color: #c0392b; color: #c0392b; }
  .speak-button { background: #1f2a44; border: 0; border-radius: 8px; color: #fff; cursor: pointer;
                  font-size: 1rem; margin: 0 8px 8px 0; padding: 8px 16px; }
  .speak-button:hover { background: #33415f; }
  .voice-warning { background: #fbf3d0; border-radius: 8px; color: #6b5300; display: none;
                   margin-top: 6px; padding: 10px 14px; }
</style>
"""

# Clicking a key puts the letter in the answer box. The box stays selected, so you keep typing.
ACCENT_SCRIPT = """
<script>
if (!window.accentKeysReady) {
  window.accentKeysReady = true;
  document.addEventListener('mousedown', (event) => {
    const key = event.target.closest && event.target.closest('.accent-key');
    if (!key) return;
    event.preventDefault();
    const box = document.querySelector('[data-testid="stMain"] [data-testid="stTextInput"] input');
    if (!box) return;
    const start = box.selectionStart, end = box.selectionEnd, letter = key.dataset.letter;
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setValue.call(box, box.value.slice(0, start) + letter + box.value.slice(end));
    box.dispatchEvent(new Event('input', { bubbles: true }));
    box.setSelectionRange(start + letter.length, start + letter.length);
    box.focus();
  });
}
</script>
"""


# The browser reads the sentence aloud, always asking for the Spanish of Spain (es-ES).
# Ctrl+Space plays it again, so your hands can stay on the keyboard.
SPEECH_SCRIPT = """
<script>
if (!window.speechReady) {
  window.speechReady = true;
  window.spainVoice = () => speechSynthesis.getVoices().find(v => v.lang.replace('_', '-') === 'es-ES');
  window.speakSpanish = (text, rate) => {
    window.lastSpanish = text;
    speechSynthesis.cancel();
    const sentence = new SpeechSynthesisUtterance(text);
    sentence.lang = 'es-ES';
    sentence.rate = rate;
    const voice = window.spainVoice();
    if (voice) sentence.voice = voice;
    speechSynthesis.speak(sentence);
    setTimeout(() => {
      const warning = document.querySelector('.voice-warning');
      if (warning) warning.style.display = window.spainVoice() ? 'none' : 'block';
    }, 1500);
  };
  document.addEventListener('mousedown', (event) => {
    const button = event.target.closest && event.target.closest('.speak-button');
    if (!button) return;
    event.preventDefault();
    window.speakSpanish(window.lastSpanish, Number(button.dataset.rate));
  });
  document.addEventListener('keydown', (event) => {
    if (event.ctrlKey && event.code === 'Space' && window.lastSpanish) {
      event.preventDefault();
      window.speakSpanish(window.lastSpanish, 1);
    }
  });
}
</script>
"""

VOICE_HELP = ("No Spanish (Spain) voice was found, so you may hear nothing or a different accent. "
              "Use Microsoft Edge or Chrome, or add one in Windows: Settings, Time &amp; language, "
              "Speech, Manage voices, Add voices, Spanish (Spain). Then restart your browser.")


# ---------- data ----------
@st.cache_data(show_spinner=False)
def load_all_items():
    """Returns a dict: for each PDF id, the list of its questions. Stored after the first time."""
    catalog = json.loads((HERE / "data" / "catalog.json").read_text(encoding="utf-8"))
    result = {}
    for pdf in catalog:
        path = HERE / "data" / "content" / pdf["content"]
        result[pdf["id"]] = build_items(pdf["id"], json.loads(path.read_text(encoding="utf-8")))
    return result


@st.cache_data(show_spinner=False)
def load_catalog():
    return json.loads((HERE / "data" / "catalog.json").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_themes():
    """Returns the themed word lists: for each theme file its title, kind, lists and questions.
    path.stem is the file name without .json, for example 'food'."""
    themes = {}
    for path in sorted((HERE / "data" / "themes").glob("*.json")):
        theme = json.loads(path.read_text(encoding="utf-8"))
        lists = [{"name": part["name"], "level": part["level"]} for part in theme["lists"]]
        themes[path.stem] = {"title": theme["title"], "kind": theme.get("kind", "topic"), "lists": lists,
                             "items": build_theme_items(path.stem, theme)}
    return themes


def practice_data():
    if "practice" not in st.session_state:
        st.session_state.practice = store.load(PRACTICE_FILE)
    return st.session_state.practice


def items_of_level(level):
    all_items = load_all_items()
    return [item for pdf in load_catalog() if pdf["level"] == level for item in all_items[pdf["id"]]]


def every_item():
    return [item for items in load_all_items().values() for item in items]


def is_marked(item):
    """True when the exercise of this question was marked as done with its checkbox."""
    return store.is_marked_done(practice_data(), logic.done_key(item))


def is_answered(item):
    """For the Schedule: answered at least once, or part of an exercise you marked as done."""
    return item["id"] in practice_data()["items"] or is_marked(item)


def mastery(items):
    """Returns (questions mastered, questions in total). A question of an exercise you marked as
    done counts as mastered."""
    data = practice_data()
    return sum(store.is_mastered(data, item["id"]) or is_marked(item) for item in items), len(items)


def set_done(keys, widget_key):
    """For the 'Mark as done' checkboxes. The checkbox's new value is in session_state[widget_key]."""
    for key in keys:
        store.mark_done(practice_data(), key, st.session_state[widget_key])
    store.save(PRACTICE_FILE, practice_data())


def done_checkbox(items, label, widget_key):
    """A checkbox that marks the exercises of these questions as done. It is ticked when all of
    them are marked. Returns True when ticked."""
    keys = sorted({logic.done_key(item) for item in items})
    ticked = all(store.is_marked_done(practice_data(), key) for key in keys)
    st.session_state[widget_key] = ticked  # always show what is saved in practice.json
    st.checkbox(label, key=widget_key, on_change=set_done, args=(keys, widget_key),
                help="Counts this exercise as finished in your progress and the Schedule, "
                     "and the automatic next step skips it. Your answers are not changed.")
    return ticked


def weak_items(items):
    data = practice_data()
    return [item for item in items if store.is_weak(data, item["id"])]


def theme_items():
    return [item for theme in load_themes().values() for item in theme["items"]]


def due_items():
    """Everything that is due for review today, from the PDFs and the themed lists,
    with the longest overdue first."""
    data = practice_data()
    due = [item for item in every_item() + theme_items() if store.is_due(data, item["id"])]
    return sorted(due, key=lambda item: data["items"][item["id"]].get("due", ""))


# ---------- moving between screens ----------
def go_practice(pdf_id):
    st.session_state.practice_pdf = pdf_id
    st.session_state.level = next(p["level"] for p in load_catalog() if p["id"] == pdf_id)
    st.session_state.view = "practice"


def start_drill(items, title, back, pdf_id=None, mode=None, size=None, pool=None, source=None, left_out=0):
    """Starts a session. 'back' is the screen to return to: ('pdf', id), ('level', A1) or ('home',).
    'pool' holds all questions of the PDF or list, so the next exercise type can follow, and
    'source' is its name, like 'A1 · Greetings'. Without a pool, nothing follows the session.
    'left_out' is the number of known questions that 'Skip what I know' left out."""
    chosen = logic.choose_items(items, practice_data()["items"], size)
    drill = logic.new_drill(chosen)
    drill.update(title=title, back=back, pdf_id=pdf_id, mode=mode, tiles_for=None, order=[], picked=[],
                 size=size, pool=pool or [], source=source, left_out=left_out)
    st.session_state.drill = drill
    st.session_state.view = "drill"


def start_known_check(items, title, back, pdf_id, mode, size, pool=None, source=None):
    """Starts a session without the known questions when 'Skip what I know' is on. When nothing
    is left, it stays on this screen with a message instead."""
    items, left_out = leave_out_known(items)
    if not items:
        st.session_state.notice = (f"You already know all {left_out} questions of {title}. "
                                   "Switch off 'Skip what I know' to practise them anyway.")
        return
    start_drill(items, title, back, pdf_id, mode, size, pool, source, left_out)


def start_mode(pool, source, back, pdf_id, mode, size):
    """Starts one exercise type of a PDF or list, keeping the pool so the next type can follow."""
    title = f"{source} · {mode_title(mode)}"
    if mode == "weak":  # weak questions are never left out
        start_drill(weak_items(pool), title, back, pdf_id, mode, size, pool, source)
        return
    items = pool if mode == "test" else [i for i in pool if i["mode"] == mode]  # test: everything
    start_known_check(items, title, back, pdf_id, mode, size, pool, source)


def repeat_drill():
    """Run again: the same questions, so nothing is left out this time."""
    old = st.session_state.drill
    start_drill(list(old["items"].values()), old["title"], old["back"], old["pdf_id"], old["mode"],
                old["size"], old["pool"], old["source"])


def continue_drill(mode):
    old = st.session_state.drill
    start_mode(old["pool"], old["source"], old["back"], old["pdf_id"], mode, old["size"])


def following_step(drill):
    """The exercise type after this session, 'weak', or None. See next_step in practice_logic.py."""
    if not drill["pool"]:
        return None
    # {...} makes a set: every type once. A type you marked as done is skipped, and with
    # 'Skip what I know' on, also a type of which you know every question.
    skip = skip_known()
    modes = {item["mode"] for item in drill["pool"] if not (is_known(item) if skip else is_marked(item))}
    return logic.next_step(modes, drill["mode"], bool(weak_items(drill["pool"])))


def next_pdf(pdf_id):
    """The PDF after this one in the catalogue, or None after the last one."""
    ids = [pdf["id"] for pdf in load_catalog()]
    if pdf_id in ids and ids.index(pdf_id) + 1 < len(ids):
        return ids[ids.index(pdf_id) + 1]
    return None


def previous_pdf(pdf_id):
    """The PDF before this one in the catalogue, or None before the first one."""
    ids = [pdf["id"] for pdf in load_catalog()]
    return ids[ids.index(pdf_id) - 1] if pdf_id in ids and ids.index(pdf_id) > 0 else None


def short_label(pdf_id):
    """'A1_04_Ser_Estar...' gives 'A1 · 04'."""
    pdf = next(p for p in load_catalog() if p["id"] == pdf_id)
    return f"{pdf['level']} · {pdf['number']:02d}"


def pdf_title(pdf_id):
    return next(p["title"] for p in load_catalog() if p["id"] == pdf_id)


def open_next_pdf(pdf_id):
    """Opens a PDF in the reader, where you last stopped in it."""
    ACTIONS["open_reader"](pdf_id)


def accepted_for(item):
    return store.accepted_answers(practice_data(), logic.answer_key(item))


def leave_drill():
    back = st.session_state.drill["back"]
    if back[0] == "pdf":
        go_practice(back[1])
    elif back[0] == "level":
        go_level(back[1])
    elif back[0] == "view":
        go_view(back[1])
    else:
        go_home()


# ---------- what happens when you answer ----------
def grade(typed):
    drill = st.session_state.drill
    item = logic.current_item(drill)
    result, note = logic.check_answer(item, typed, accepted_for(item))
    correct = result != "wrong"
    first = logic.is_first_attempt(drill)
    if first:
        store.record(practice_data(), item["id"], correct)
        store.save(PRACTICE_FILE, practice_data())
    # Every answer counts towards today's study time, also in later rounds; only first tries
    # count towards your accuracy on the Progress tab.
    log_activity("answer", correct if first else None)
    logic.give_result(drill, item["id"], correct)
    drill["feedback"] = {"result": result, "note": note, "typed": typed}


def submit_typed(key):
    grade(st.session_state.get(key, ""))


def i_was_right():
    drill = st.session_state.drill
    item = logic.current_item(drill)
    if logic.is_first_attempt(drill):
        store.change_to_correct(practice_data(), item["id"])
        log_overrule()
    # Remember the answer, also in later rounds, so it counts as correct from now on.
    store.accept(practice_data(), logic.answer_key(item), drill["feedback"]["typed"])
    store.save(PRACTICE_FILE, practice_data())
    logic.change_to_correct(drill, item["id"])
    drill["feedback"]["result"] = "overruled"


def next_question():
    drill = st.session_state.drill
    logic.go_to_next(drill)
    if drill["finished"] and drill["pdf_id"]:  # a PDF score is only saved for a finished session
        store.save_score(practice_data(), drill["pdf_id"], drill["mode"], logic.score_percent(drill))
        store.save(PRACTICE_FILE, practice_data())


def click_tile(index):
    st.session_state.drill["picked"].append(index)


def undo_tile():
    st.session_state.drill["picked"].pop()  # pop removes the last element of a list


def clear_tiles():
    st.session_state.drill["picked"] = []


def submit_tiles():
    drill = st.session_state.drill
    grade(" ".join(drill["order"][i] for i in drill["picked"]))


# ---------- pick screen: all exercise types of one PDF ----------
def practice_screen():
    st.html(STYLE)
    pdf = next(p for p in load_catalog() if p["id"] == st.session_state.practice_pdf)
    items = load_all_items()[pdf["id"]]
    done, total = mastery(items)

    # A row of buttons, each as wide as its text; it wraps to a second line on a narrow screen.
    with st.container(horizontal=True):
        st.button("🏠 Home", key="practice_home", on_click=go_home)
        st.button(f"← {pdf['level']} overview", key="practice_level", on_click=go_level, args=(pdf["level"],))
        before, after = previous_pdf(pdf["id"]), next_pdf(pdf["id"])  # also across levels
        if before:
            st.button(f"◀ Practise {short_label(before)}", key="practice_prev_pdf", on_click=go_practice,
                      args=(before,), help=f"Practise the previous PDF: {pdf_title(before)}")
        if after:
            st.button(f"Practise {short_label(after)} ▶", key="practice_next_pdf", on_click=go_practice,
                      args=(after,), help=f"Practise the next PDF: {pdf_title(after)}")
        if before:
            st.button(f"📖 Read {short_label(before)}", key="practice_read_prev", on_click=open_next_pdf,
                      args=(before,), help=f"Read the previous PDF: {pdf_title(before)}")
        if after:
            st.button(f"📖 Read {short_label(after)}", key="practice_read_next", on_click=open_next_pdf,
                      args=(after,), help=f"Read the next PDF: {pdf_title(after)}")
    hero(f"Practise · {pdf['level']} · PDF {pdf['number']}", html.escape(pdf["title"]),
         f"{done} of {total} questions mastered", done / total)
    st.write("")

    size = size_buttons("practice_size")
    skip_switch("practice_skip")
    st.caption("After each session the next exercise type follows, in the order of the cards below.")
    show_notice()
    scores = practice_data()["scores"].get(pdf["id"], {})
    back = ("pdf", pdf["id"])
    source = f"{pdf['level']} · {pdf['title']}"

    # One card per exercise type, with only the types that exist for this PDF.
    cards = [(mode, title, text, [i for i in items if i["mode"] == mode]) for mode, title, text in MODES]
    cards = [card for card in cards if card[3]]
    cards.append(("test", "🎯 Mixed test", "All exercise types mixed together.", items))
    weak = weak_items(items)
    if weak:
        cards.append(("weak", "💪 Weak questions", "What you got wrong recently.", weak))

    columns = st.columns(3)
    for n, (mode, title, text, mode_items) in enumerate(cards):
        with columns[n % 3].container(border=True, key=f"mode_{mode}"):
            st.markdown(f"#### {title}")
            st.caption(text)
            mode_done, mode_total = mastery(mode_items)
            line = f"{mode_done} of {mode_total} mastered"
            if mode in scores:
                line += f" · last {scores[mode]['last']}% · best {scores[mode]['best']}%"
            st.markdown(line)
            if mode not in ("test", "weak"):  # these two mix the other types, so they have no mark
                done_checkbox(mode_items, "Mark as done", f"done_{pdf['id']}_{mode}")
            chosen = mode_items
            groups = sorted({i["group"] for i in mode_items if i["group"]})
            # A list of topics, the {set} removes duplicates.
            if mode in ("words", "reverse", "gender") and len(groups) > 1:
                topic = st.selectbox("Topic", ["All topics"] + groups, key=f"topic_{pdf['id']}_{mode}")
                if topic != "All topics":
                    chosen = [i for i in mode_items if i["group"] == topic]
            if chosen is mode_items:  # 'is' means: the very same list, so no topic was chosen
                st.button("Start", key=f"start_{mode}", type="primary", width="stretch", on_click=start_mode,
                          args=(items, source, back, pdf["id"], mode, size))
            else:  # one topic only: then nothing follows, because the next type has no topics
                st.button("Start", key=f"start_{mode}", type="primary", width="stretch", on_click=start_known_check,
                          args=(chosen, f"{source} · {title} · {topic}", back, pdf["id"], mode, size))
    accepted_section(items, f"accepted_{pdf['id']}")


def remove_accepted(key, typed):
    store.unaccept(practice_data(), key, typed)
    store.save(PRACTICE_FILE, practice_data())


def accepted_section(items, key):
    """The answers you accepted with 'I was actually right', with a button to undo each one."""
    keys = {}
    for item in items:
        keys.setdefault(logic.answer_key(item), item)  # several questions can share one key
    found = [(k, item, typed) for k, item in keys.items() for typed in store.accepted_answers(practice_data(), k)]
    if not found:
        return
    with st.expander(f"✅ Answers you accepted ({len(found)})"):
        st.caption("These count as correct everywhere in the app. Remove one if you clicked by mistake.")
        for n, (k, item, typed) in enumerate(found):
            c = st.columns([5, 1], vertical_alignment="center")
            question = item["speak"] or item["prompt"]
            c[0].markdown(f"{mode_title(item['mode'])} · {plain_markdown(question)}  →  **{plain_markdown(typed)}**  \n"
                          f"Model answer: {plain_markdown(item['show'])}")
            c[1].button("Remove", key=f"{key}_{n}", on_click=remove_accepted, args=(k, typed), width="stretch")


# ---------- weak subjects ----------
def subjects(level=None):
    """Every PDF and every themed list of a level (or of all levels) as (name, questions)."""
    all_items = load_all_items()
    found = [(f"{pdf['level']} · {pdf['title']}", all_items[pdf["id"]])
             for pdf in load_catalog() if level in (None, pdf["level"])]
    for theme in load_themes().values():
        for part in theme["lists"]:
            if level in (None, part["level"]):
                items = [i for i in theme["items"] if i["group"] == part["name"]]
                found.append((f"{theme['title']} · {part['name']}", items))
    return found


def start_weak_subject(name, items, back):
    source = items[0]["id"].split("|")[0]  # the PDF id, or THEME_name for a themed list
    pdf_id = None if source.startswith("THEME_") else source
    start_drill(weak_items(items), f"{name} · Weak questions", back, pdf_id, "weak")


def weak_subjects_section(level, back, key):
    """The weakest subjects with a button each, and the first-try score per exercise type."""
    stats = practice_data()["items"]
    scope = subjects(level)
    weak = logic.weak_subjects(scope, stats)
    # The same score per exercise type, over all questions in scope.
    every = [item for _, items in scope for item in items]
    per_type = []
    for mode, title, _ in MODES:
        score, _ = logic.first_try_score([i for i in every if i["mode"] == mode], stats)
        if score is not None:
            per_type.append((score, title))
    if not weak and not per_type:
        return  # too little practised to say anything yet
    st.subheader("Weak subjects")
    if per_type:
        st.caption("Right on the first try, per exercise type: " +
                   " · ".join(f"{title} {score:.0%}" for score, title in sorted(per_type)))
    if not weak:
        st.caption(f"No weak subjects: everywhere you practised at least {logic.MIN_PRACTISED} "
                   f"questions, {logic.WEAK_BELOW:.0%} or more was right on the first try.")
        return
    st.caption(f"PDFs and themed lists where less than {logic.WEAK_BELOW:.0%} of the questions you "
               f"practised was right on the first try last time (from {logic.MIN_PRACTISED} questions practised).")
    for n, (score, practised, name, items) in enumerate(weak[:5]):  # the five weakest
        c = st.columns([4, 1.5], vertical_alignment="center")
        c[0].markdown(f"**{html.escape(name)}** · {score:.0%} right on the first try ({practised} practised)")
        c[1].button("💪 Practise", key=f"{key}_{n}", width="stretch", on_click=start_weak_subject,
                    args=(name, items, back))


# ---------- a running session ----------
def show_prompt(drill, item):
    kind = next((title for mode, title, _ in MODES if mode == item["mode"]), "")
    hint = f'<div class="prompt-hint">{html.escape(item["hint"])}</div>' if item["hint"] else ""
    st.html(f'<div class="prompt-card"><div class="prompt-kind">{kind}</div>'
            f'<div class="prompt-text">{html.escape(item["prompt"])}</div>{hint}</div>')


def listening_controls(number, text):
    """The play buttons. The sentence plays once by itself; 'number' makes each script new, so
    it plays again for each new question, but not when the screen is only redrawn."""
    st.html('<button type="button" class="speak-button" data-rate="1">🔊 Play again (Ctrl+Space)</button>'
            '<button type="button" class="speak-button" data-rate="0.65">🐢 Slowly</button>'
            f'<div class="voice-warning">{VOICE_HELP}</div>{SPEECH_SCRIPT}'
            f"<script>/* {number} */ window.speakSpanish({json.dumps(text)}, 1);</script>",
            unsafe_allow_javascript=True)


def answer_box(number, on_submit):
    """The input box, its button and the accent keys. Enter also presses the button.
    on_submit is a function that gets the name under which the typed text is stored."""
    key = f"answer_{number}"  # a new name for each question, so the box starts empty
    with st.form(f"form_{number}", border=False):
        st.text_input("Your answer", key=key, autocomplete="off")
        st.form_submit_button("Check (Enter)", type="primary", on_click=on_submit, args=(key,))
    keys = "".join(f'<button type="button" class="accent-key" data-letter="{k}">{k}</button>'
                   for k in ACCENT_KEYS)
    st.html(f"<div>{keys}</div>{ACCENT_SCRIPT}", unsafe_allow_javascript=True)
    # Puts the cursor in the box, so you can type straight away. The number makes each script new.
    st.html(f"<script>/* {number} */ setTimeout(() => document.querySelector("
            "'[data-testid=\"stMain\"] [data-testid=\"stTextInput\"] input')?.focus(), 80);</script>",
            unsafe_allow_javascript=True)


def typed_question(drill, item):
    if item["speak"]:
        listening_controls(drill["asked"], item["speak"])
    answer_box(drill["asked"], submit_typed)


def choice_question(item):
    """Choosing el or la: click a button, or press the E or L key."""
    with st.container(horizontal=True):
        for choice in item["choices"]:
            st.button(choice, key=f"choice_{choice}", on_click=grade, args=(choice,),
                      shortcut=choice[0].upper(), type="primary")


def tile_question(drill, item):
    if drill["tiles_for"] != drill["asked"]:  # first time on this question: shuffle the words
        order = item["tiles"][:]  # [:] makes a copy, in Python b = a would be the same list
        for _ in range(8):
            random.shuffle(order)
            if order != item["tiles"]:
                break
        drill.update(tiles_for=drill["asked"], order=order, picked=[])

    built = " ".join(drill["order"][i] for i in drill["picked"])
    st.markdown(f"#### {built}" if built else "*Click the words in the right order.*")
    with st.container(horizontal=True):
        for i, word in enumerate(drill["order"]):  # enumerate gives the number and the element
            st.button(word, key=f"tile_{drill['asked']}_{i}", on_click=click_tile, args=(i,),
                      disabled=i in drill["picked"])
    st.write("")
    with st.container(horizontal=True):
        everything_used = len(drill["picked"]) == len(drill["order"])
        st.button("Check", key="tiles_check", type="primary", shortcut="Enter", on_click=submit_tiles,
                  disabled=not everything_used)
        st.button("Undo", key="tiles_undo", on_click=undo_tile, disabled=not drill["picked"])
        st.button("Clear", key="tiles_clear", on_click=clear_tiles, disabled=not drill["picked"])


def plain_markdown(text):
    """Stops characters like * and _ from changing the layout of the text."""
    for character in "\\`*_[]$~":
        text = text.replace(character, "\\" + character)
    return text


def show_feedback(item, feedback):
    correct = plain_markdown(item["show"])
    mine = plain_markdown(feedback["typed"]) or "(no answer)"
    if feedback["result"] == "right":
        st.success(f"**Correct!**  {correct}")
    elif feedback["result"] == "near":
        st.warning(f"**{feedback['note']}**  {correct}")
    elif feedback["result"] == "overruled":
        st.success(f"**Counted as correct.**  Your answer: {mine}  ·  Model answer: {correct}")
    else:
        st.error(f"**Your answer:** {mine}  \n**Correct:** {correct}")
    if item["why"]:
        st.info(item["why"])
    with st.container(horizontal=True):
        st.button("Next", key="next_question", type="primary", shortcut="Enter", on_click=next_question)
        if feedback["result"] == "wrong":
            st.button("I was actually right", key="overrule", on_click=i_was_right)


def drill_screen():
    st.html(STYLE)
    drill = st.session_state.drill
    if drill["finished"]:
        return results_screen(drill)

    item = logic.current_item(drill)
    top = st.columns([1.2, 6], vertical_alignment="center")
    top[0].button("✕ Stop session", key="drill_stop", on_click=leave_drill, width="stretch")
    top[1].markdown(f"**{html.escape(drill['title'])}**")
    if drill.get("left_out"):  # .get: a session started before this existed has no 'left_out'
        st.caption(f"{drill['left_out']} questions you already know are left out ('Skip what I know').")
    stage = "Round" if drill["stage"] == 1 else "Repeat of what you missed, round"
    total = len(drill["queue"])
    st.progress(drill["position"] / total,
                text=f"{stage} {drill['round']}  ·  question {drill['position'] + 1} of {total}")

    show_prompt(drill, item)
    st.write("")
    if drill["feedback"]:
        show_feedback(item, drill["feedback"])
    elif item["mode"] == "build":
        tile_question(drill, item)
    elif item["choices"]:
        choice_question(item)
    else:
        typed_question(drill, item)


def results_screen(drill):
    percent = logic.score_percent(drill)
    total = len(drill["items"])
    right = total - len(drill["first_wrong"])
    hero("Session complete", f"{percent}%", f"{right} of {total} correct the first time",  percent / 100)
    st.write("")
    show_notice()
    step = following_step(drill)
    # Only a PDF session can lead to the next PDF; a themed list ends with Back.
    after = next_pdf(drill["pdf_id"]) if drill["pool"] and drill["back"][0] == "pdf" else None
    with st.container(horizontal=True):
        if step:
            st.button(f"Next: {mode_title(step)}", key="drill_next", type="primary", shortcut="Enter",
                      on_click=continue_drill, args=(step,))
        elif after and "open_reader" in ACTIONS:
            title = next(p for p in load_catalog() if p["id"] == after)
            st.button(f"Next PDF: {title['level']} · {title['title']}", key="drill_next_pdf",
                      type="primary", shortcut="Enter", on_click=open_next_pdf, args=(after,))
        st.button("↻ Run again", key="drill_again", on_click=repeat_drill)
        st.button("Back", key="drill_back", on_click=leave_drill)
    if drill["pool"] and not step and not after:
        st.success("That was the last exercise type. 🎉")
    if drill["first_wrong"]:
        st.subheader("Wrong the first time")
        for item_id in drill["first_wrong"]:
            item = drill["items"][item_id]
            st.markdown(f"- {plain_markdown(item['prompt'])}  →  **{plain_markdown(item['show'])}**")
