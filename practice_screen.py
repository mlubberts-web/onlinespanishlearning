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
from practice_items import MODES, build_items
from ui import go_home, go_level, go_view, hero

HERE = Path(__file__).parent
PRACTICE_FILE = HERE / "practice.json"
SIZES = {"10": 10, "20": 20, "All": None}
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
    """Returns the themed word lists: for each theme its title and questions."""
    themes = {}
    for path in sorted((HERE / "data" / "themes").glob("*.json")):
        theme = json.loads(path.read_text(encoding="utf-8"))
        # A theme is built like a PDF that holds one list of word pairs.
        document = {"blocks": [{"type": "verbpairs", "title": theme["title"], "items": theme["items"]}]}
        themes[path.stem] = {"title": theme["title"], "items": build_items(f"THEME_{path.stem}", document)}
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


def mastery(items):
    """Returns (questions mastered, questions in total)."""
    data = practice_data()
    return sum(store.is_mastered(data, item["id"]) for item in items), len(items)


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


def start_drill(items, title, back, pdf_id=None, mode=None, size=None):
    """Starts a session. 'back' is the screen to return to: ('pdf', id), ('level', A1) or ('home',)."""
    chosen = logic.choose_items(items, practice_data()["items"], size)
    drill = logic.new_drill(chosen)
    drill.update(title=title, back=back, pdf_id=pdf_id, mode=mode, tiles_for=None, order=[], picked=[])
    st.session_state.drill = drill
    st.session_state.view = "drill"


def repeat_drill():
    old = st.session_state.drill
    start_drill(list(old["items"].values()), old["title"], old["back"], old["pdf_id"], old["mode"])


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
    result, note = logic.check_answer(item, typed)
    correct = result != "wrong"
    if logic.is_first_attempt(drill):
        store.record(practice_data(), item["id"], correct)
        store.save(PRACTICE_FILE, practice_data())
    logic.give_result(drill, item["id"], correct)
    drill["feedback"] = {"result": result, "note": note, "typed": typed}


def submit_typed(key):
    grade(st.session_state.get(key, ""))


def i_was_right():
    drill = st.session_state.drill
    item = logic.current_item(drill)
    if logic.is_first_attempt(drill):
        store.change_to_correct(practice_data(), item["id"])
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

    nav = st.columns([1, 1.7, 7])
    nav[0].button("🏠 Home", key="practice_home", on_click=go_home, width="stretch")
    nav[1].button(f"← {pdf['level']} overview", key="practice_level", on_click=go_level,
                  args=(pdf["level"],), width="stretch")
    hero(f"Practise · {pdf['level']} · PDF {pdf['number']}", html.escape(pdf["title"]),
         f"{done} of {total} questions mastered", done / total)
    st.write("")

    choice = st.radio("Questions per session (the difficult ones are chosen more often)", list(SIZES),
                      index=1, horizontal=True, key="practice_size")
    size = SIZES[choice]
    scores = practice_data()["scores"].get(pdf["id"], {})
    back = ("pdf", pdf["id"])

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
            chosen = mode_items
            groups = sorted({i["group"] for i in mode_items if i["group"]})
            # A list of topics, the {set} removes duplicates.
            if mode in ("words", "reverse", "gender") and len(groups) > 1:
                topic = st.selectbox("Topic", ["All topics"] + groups, key=f"topic_{pdf['id']}_{mode}")
                if topic != "All topics":
                    chosen = [i for i in mode_items if i["group"] == topic]
            st.button("Start", key=f"start_{mode}", type="primary", width="stretch", on_click=start_drill,
                      args=(chosen, f"{pdf['level']} · {pdf['title']} · {title}", back, pdf["id"], mode, size))


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
    with st.container(horizontal=True):
        st.button("↻ Run again", key="drill_again", type="primary", on_click=repeat_drill)
        st.button("Back", key="drill_back", on_click=leave_drill)
    if drill["first_wrong"]:
        st.subheader("Wrong the first time")
        for item_id in drill["first_wrong"]:
            item = drill["items"][item_id]
            st.markdown(f"- {plain_markdown(item['prompt'])}  →  **{plain_markdown(item['show'])}**")
