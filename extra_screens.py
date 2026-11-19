"""The themed word lists and the mock exam. The drills themselves are in practice_screen.py."""
import html, time
from datetime import date

import streamlit as st

import practice_logic as logic
import practice_screen as practice
import practice_store as store
from practice_items import MODES
from ui import go_view, hero

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2", "All levels"]
# Number of questions and the minutes you get for them: (questions, minutes).
LENGTHS = {"20 questions, 15 minutes": (20, 15), "40 questions, 30 minutes": (40, 30),
           "60 questions, 45 minutes": (60, 45)}
THEME_MODES = [("words", "🔤 To Spanish"), ("reverse", "🔄 To English"), ("gender", "⚖️ el or la?")]


# ---------- themed word lists ----------
def themes_screen():
    themes = practice.load_themes()
    done, total = practice.mastery(practice.theme_items())
    hero("Word lists", "Themed vocabulary", f"{done} of {total} questions mastered",
         done / total if total else 0)
    st.write("")
    choice = st.radio("Questions per session (the difficult ones are chosen more often)",
                      list(practice.SIZES), index=1, horizontal=True, key="themes_size")
    size = practice.SIZES[choice]

    columns = st.columns(2)
    for n, (name, theme) in enumerate(themes.items()):
        with columns[n % 2].container(border=True, key=f"theme_{name}"):
            st.markdown(f"#### {theme['title']}")
            theme_done, theme_total = practice.mastery(theme["items"])
            st.progress(theme_done / theme_total, text=f"{theme_done} of {theme_total} questions mastered")
            buttons = st.columns(3)
            for column, (mode, label) in zip(buttons, THEME_MODES):
                items = [i for i in theme["items"] if i["mode"] == mode]
                column.button(label, key=f"theme_{name}_{mode}", width="stretch", on_click=practice.start_drill,
                              args=(items, f"{theme['title']} · {label}", ("view", "themes"),
                                    f"THEME_{name}", mode, size))


# ---------- mock exam: setting it up ----------
def start_mock(level, length):
    questions, minutes = LENGTHS[length]
    pool = practice.every_item() if level == "All levels" else practice.items_of_level(level)
    st.session_state.mock = {"level": level, "items": logic.choose_mock_items(pool, questions),
                             "position": 0, "answers": [], "minutes": minutes,
                             "deadline": time.time() + minutes * 60, "saved": False}
    st.session_state.view = "mock_run"


def mock_screen():
    hero("Mock exam", "Test yourself under time pressure",
         "A mix of all exercise types, one attempt each, with no feedback until the end.", 0)
    st.write("")
    level = st.radio("Level", LEVELS, index=5, horizontal=True, key="mock_level")
    length = st.radio("Length", list(LENGTHS), index=1, horizontal=True, key="mock_length")
    st.button("Start the mock exam", key="mock_start", type="primary", on_click=start_mock, args=(level, length))
    st.caption("This trains exam conditions with the questions of this program. "
               "It does not follow the format of the official DELE exam.")

    earlier = practice.practice_data().get("mocks", [])
    if earlier:
        st.subheader("Earlier results")
        for mock in reversed(earlier[-10:]):  # the last ten, newest first
            st.markdown(f"- {mock['date']} · {mock['level']} · **{mock['percent']}%** "
                        f"({mock['right']} of {mock['total']})")


# ---------- mock exam: answering ----------
def finish_mock():
    mock = st.session_state.mock
    if not mock["saved"]:
        mock["saved"] = True
        data = practice.practice_data()
        store.save_mock(data, mock_result(mock))
        store.save(practice.PRACTICE_FILE, data)
    st.session_state.view = "mock_result"


def mock_result(mock):
    right = sum(answer["result"] != "wrong" for answer in mock["answers"])
    total = len(mock["items"])
    return {"date": date.today().isoformat(), "level": mock["level"], "right": right, "total": total,
            "percent": round(100 * right / total)}


def submit_mock(key):
    mock = st.session_state.mock
    item = mock["items"][mock["position"]]
    typed = st.session_state.get(key, "")
    result, _ = logic.check_answer(item, typed)
    store.record(practice.practice_data(), item["id"], result != "wrong")
    store.save(practice.PRACTICE_FILE, practice.practice_data())
    mock["answers"].append({"item": item, "typed": typed, "result": result})
    mock["position"] += 1
    if mock["position"] >= len(mock["items"]):
        finish_mock()


@st.fragment(run_every=1)
def mock_clock():
    """A fragment is a part of the screen that redraws by itself, here every second, while the
    rest stays untouched. So the clock runs without disturbing what you are typing."""
    mock = st.session_state.mock
    left = int(mock["deadline"] - time.time())
    if left <= 0:
        finish_mock()
        st.rerun()  # redraws the whole screen, now with the result
    st.markdown(f"### ⏱️ {left // 60:02d}:{left % 60:02d}")  # // divides without decimals, % is the remainder


def mock_run_screen():
    st.html(practice.STYLE)
    mock = st.session_state.mock
    total = len(mock["items"])
    item = mock["items"][mock["position"]]
    top = st.columns([1.2, 5, 1.2], vertical_alignment="center")
    top[0].button("Finish now", key="mock_finish", on_click=finish_mock, width="stretch")
    top[1].progress(mock["position"] / total, text=f"Question {mock['position'] + 1} of {total}")
    with top[2]:
        mock_clock()
    practice.show_prompt(None, item)
    st.write("")
    if item["speak"]:
        practice.listening_controls(f"mock{mock['position']}", item["speak"])
    practice.answer_box(f"mock{mock['position']}", submit_mock)


# ---------- mock exam: the result ----------
def overrule_mock(index):
    """For the 'I was actually right' button on the result screen."""
    mock = st.session_state.mock
    answer = mock["answers"][index]
    answer["result"] = "overruled"
    data = practice.practice_data()
    store.change_to_correct(data, answer["item"]["id"])
    data["mocks"][-1] = mock_result(mock)  # the mock just finished is the last in the list
    store.save(practice.PRACTICE_FILE, data)


def mock_result_screen():
    mock = st.session_state.mock
    result = mock_result(mock)
    unanswered = result["total"] - len(mock["answers"])
    text = f"{result['right']} of {result['total']} correct · {mock['level']}"
    if unanswered:
        text += f" · {unanswered} not answered"
    hero("Mock exam result", f"{result['percent']}%", text, result["percent"] / 100)
    st.write("")
    with st.container(horizontal=True):
        st.button("New mock exam", key="mock_again", type="primary", on_click=go_view, args=("mock",))

    st.subheader("Per exercise type")
    for mode, title, _ in MODES:
        asked = [a for a in mock["answers"] if a["item"]["mode"] == mode]
        if asked:
            right = sum(a["result"] != "wrong" for a in asked)
            st.markdown(f"- {title}: **{right} of {len(asked)}**")

    wrong = [(n, a) for n, a in enumerate(mock["answers"]) if a["result"] == "wrong"]
    if wrong:
        st.subheader("What you got wrong")
    for n, answer in wrong:
        item = answer["item"]
        with st.container(border=True, key=f"mock_wrong_{n}"):
            c = st.columns([5, 1.4], vertical_alignment="center")
            question = item["speak"] or item["prompt"]
            c[0].markdown(f"{practice.plain_markdown(question)}  \n"
                          f"Your answer: {practice.plain_markdown(answer['typed']) or '(no answer)'}  \n"
                          f"Correct: **{practice.plain_markdown(item['show'])}**")
            c[1].button("I was right", key=f"overrule_{n}", on_click=overrule_mock, args=(n,), width="stretch")
