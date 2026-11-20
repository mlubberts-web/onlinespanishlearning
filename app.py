"""Spanish Learning Program - reader and progress tracker.
Run with:  streamlit run app.py   (or double-click start.bat on Windows).

Screens: home (all levels) -> level (the PDFs in one level) -> reader (one PDF).
The practice screens are in practice_screen.py.
To add a screen, write a function for it and add it to SCREENS at the bottom."""
import base64, json, os
from pathlib import Path

import pymupdf
import streamlit as st

import clock
import extra_screens as extra
import login
import practice_screen as practice
import practice_store as store
import progress_screen as progress
import schedule_screen as schedule
import storage
from ui import go_home, go_level, go_view, hero, log_activity, log_data, save_log

HERE = Path(__file__).parent
PDF_DIR = HERE / "static" / "pdfs"
CATALOG = HERE / "data" / "catalog.json"
PROGRESS = HERE / "progress.json"
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
LEVEL_NAMES = {"A1": "Beginner", "A2": "Elementary", "B1": "Intermediate",
               "B2": "Upper intermediate", "C1": "Advanced", "C2": "Mastery"}
PAGE_WIDTHS = {"Small": 760, "Medium": 1000, "Large": 1300}  # maximum width on screen, in pixels
STATUS_LABEL = {"done": "✅ Done", "reading": "📖 In progress", "new": "○ Not started"}

STYLE = """
<style>
  h1, h2, h3, h4 { color: #1f2a44; }
  .hero { background: #1f2a44; color: #fff; border-radius: 14px; padding: 26px 30px; }
  .hero-eyebrow { color: #f0b9b2; font-size: .8rem; font-weight: 700; letter-spacing: .08em;
                  text-transform: uppercase; }
  .hero-title { font-size: 2.1rem; font-weight: 700; line-height: 1.2; margin: 4px 0 6px; }
  .hero-text { color: #d9deea; }
  .hero-track { background: rgba(255, 255, 255, .2); border-radius: 99px; height: 10px; margin-top: 16px; }
  .hero-fill { background: #e4685c; border-radius: 99px; height: 100%; }
  .pdf-page { width: 100%; background: #fff; box-shadow: 0 1px 8px rgba(31, 42, 68, .22); }
  [class*="st-key-card_"], [class*="st-key-row_"] { background: #fff; }
  [data-testid="stSidebar"] button { justify-content: flex-start; text-align: left; }
  [data-testid="stSidebar"] button > div { justify-content: flex-start; }
</style>
"""

st.set_page_config(page_title="Spanish Learning Program", page_icon="📘", layout="wide")
st.html(STYLE)
# Online, this asks who you are first; on your own computer it does nothing and USER is None.
USER = login.start()


# ---------- data ----------
@st.cache_data
def load_catalog():
    with open(CATALOG, encoding="utf-8") as fh:
        return json.load(fh)


@st.cache_data
def page_count(file):
    with pymupdf.open(PDF_DIR / file) as doc:
        return doc.page_count


@st.cache_data(show_spinner=False)
def render_page(file, index):
    """Return a page as a vector SVG data URI, so it stays sharp at any size or browser zoom."""
    with pymupdf.open(PDF_DIR / file) as doc:
        svg = doc[index].get_svg_image(text_as_path=True)
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


catalog = load_catalog()
by_id = {i["id"]: i for i in catalog}


# ---------- progress ----------
def load_progress():
    # storage.py reads the file, or the online database when the app runs on the internet.
    return storage.load(PROGRESS, {})


def save_progress():
    storage.save(PROGRESS, st.session_state.progress)


def entry(pid):
    return st.session_state.progress.setdefault(
        pid, {"seen": [], "last_page": 0, "done": False, "updated": None})


def touch(pid):
    entry(pid)["updated"] = clock.now().isoformat(timespec="seconds")


def seen_count(item):
    return len(entry(item["id"])["seen"]) if item["id"] in st.session_state.progress else 0


def status(item):
    e = st.session_state.progress.get(item["id"])
    total = page_count(item["file"])
    if e and (e["done"] or len(e["seen"]) >= total):
        return "done"
    if e and e["seen"]:
        return "reading"
    return "new"


def fraction(item):
    if status(item) == "done":
        return 1.0
    return min(1.0, seen_count(item) / page_count(item["file"]))


def stats(items):
    """Return (PDFs done, pages read, pages in total) for a list of PDFs."""
    done = sum(status(i) == "done" for i in items)
    pages_total = sum(page_count(i["file"]) for i in items)
    pages_read = sum(page_count(i["file"]) if status(i) == "done" else seen_count(i) for i in items)
    return done, pages_read, pages_total


def level_items(level):
    return [i for i in catalog if i["level"] == level]


def browser_url(item, page_index=0):
    return f"/app/static/pdfs/{item['file']}#page={page_index + 1}"


def open_in_pdf_app(item):
    path = str(PDF_DIR / item["file"])
    if hasattr(os, "startfile"):
        os.startfile(path)  # Windows only
        st.toast("Opened in your default PDF app.")
    else:
        st.toast("This button only works when the app runs on Windows.")


# ---------- state ----------
# Your results are read once per visit and then kept in the session. Online they come from the
# database; when it can't be reached the page stops here, so it never starts with empty results
# that would overwrite your real ones at the next save.
try:
    if "progress" not in st.session_state:
        st.session_state.progress = load_progress()
    practice.practice_data()
    log_data()
except storage.StorageError as problem:
    st.error("The online database can't be reached right now, so your results can't be loaded. "
             f"Reload the page in a minute.\n\nWhat the database said: {problem}")
    st.stop()
st.session_state.setdefault("view", "home")
st.session_state.setdefault("level", None)
st.session_state.setdefault("current", None)
st.session_state.setdefault("page", 0)
st.session_state.setdefault("page_jump", 1)


# ---------- navigation ----------
def open_reader(pid, page=None):
    st.session_state.current = pid
    st.session_state.level = by_id[pid]["level"]
    st.session_state.view = "reader"
    p = entry(pid)["last_page"] if page is None else page
    st.session_state.page = p
    st.session_state.page_jump = p + 1


def go_to_page(new_page):
    total = page_count(by_id[st.session_state.current]["file"])
    st.session_state.page = max(0, min(total - 1, new_page))
    st.session_state.page_jump = st.session_state.page + 1


def turn_page(step):
    go_to_page(st.session_state.page + step)


def jump_changed():
    go_to_page(st.session_state.page_jump - 1)


def toggle_done(pid):
    e = entry(pid)
    e["done"] = not (status(by_id[pid]) == "done")
    if not e["done"]:
        e["seen"] = []
        e["last_page"] = 0
    touch(pid)
    save_progress()


def reset_pdf(pid):
    st.session_state.progress.pop(pid, None)
    save_progress()
    st.session_state.page = 0
    st.session_state.page_jump = 1


def scroll_to_top_after_moving():
    """Start each new screen or PDF page at the top instead of keeping the old scroll position."""
    s = st.session_state
    spot = f"{s.view}/{s.level}"
    if s.view == "reader":
        spot += f"/{s.current}/{s.page}"
    elif s.view == "drill":
        spot += f"/{s.drill['stage']}/{s.drill['round']}/{s.drill['position']}/{s.drill['finished']}"
    elif s.view == "mock_run":
        spot += f"/{s.mock['position']}"
    # Streamlit only runs the script again when the HTML changes, hence the comment holding the spot.
    st.html(f'<script>/* {spot} */ document.querySelector(\'[data-testid="stMain"]\')?.scrollTo(0, 0);'
            "</script>", unsafe_allow_javascript=True)


# ---------- shared pieces ----------
def sidebar():
    with st.sidebar:
        st.title("📘 Spanish")
        st.button("🏠 Home", key="nav_home", on_click=go_home, width="stretch",
                  type="primary" if st.session_state.view == "home" else "secondary")
        st.button("🗓️ Schedule", key="nav_schedule", on_click=go_view, args=("schedule",), width="stretch",
                  type="primary" if st.session_state.view == "schedule" else "secondary")
        st.button("📊 Progress", key="nav_progress", on_click=go_view, args=("progress",), width="stretch",
                  type="primary" if st.session_state.view == "progress" else "secondary")
        st.button("📚 Themed words", key="nav_themes", on_click=go_view, args=("themes",), width="stretch",
                  type="primary" if st.session_state.view == "themes" else "secondary")
        st.button("⏱️ Mock exam", key="nav_mock", on_click=go_view, args=("mock",), width="stretch",
                  type="primary" if st.session_state.view == "mock" else "secondary")
        st.divider()
        st.caption("LEVELS")
        for level in LEVELS:
            items = level_items(level)
            done = sum(status(i) == "done" for i in items)
            st.button(f"{level} · {LEVEL_NAMES[level]}  ({done}/{len(items)})", key=f"nav_{level}",
                      on_click=go_level, args=(level,), width="stretch",
                      type="primary" if st.session_state.level == level else "secondary")
        st.divider()
        if USER:
            login.sidebar_part(USER)
        else:
            st.caption("Progress is saved in progress.json, practice.json and study_log.json next to app.py.")
        your_data()
        login.admin_part()  # only for admins: the accounts people made


# ---------- your data: a backup to download, and putting one back ----------
PARTS = {"progress": PROGRESS.name, "practice": practice.PRACTICE_FILE.name, "study_log": "study_log.json"}


def backup_text():
    """All your results in one file: {"progress": {...}, "practice": {...}, "study_log": {...}}."""
    every = {"progress": st.session_state.progress, "practice": practice.practice_data(),
             "study_log": log_data()}
    return json.dumps(every, ensure_ascii=False, indent=1)


def read_uploads(files):
    """The parts in the uploaded files: a backup from the button above, or the separate files
    progress.json, practice.json and study_log.json from the app on your own computer."""
    found = {}
    for file in files:
        try:
            data = json.loads(file.getvalue().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue  # not a JSON file
        part = next((p for p, file_name in PARTS.items() if file.name == file_name), None)
        if part:
            found[part] = data
        elif isinstance(data, dict) and set(data) & set(PARTS):  # & keeps what both sets have
            found.update({p: data[p] for p in PARTS if p in data})
    return found


def put_back(found):
    """Replaces your results with the uploaded ones and saves them."""
    if "progress" in found:
        st.session_state.progress = found["progress"]
        save_progress()
    if "practice" in found:
        st.session_state.practice = found["practice"]
        store.save(practice.PRACTICE_FILE, found["practice"])
    if "study_log" in found:
        st.session_state.study_log = found["study_log"]
        save_log()
    st.session_state.restored = ", ".join(PARTS[p] for p in found)


def your_data():
    with st.expander("💾 Your data"):
        st.download_button("Download a backup", backup_text(), width="stretch",
                           file_name=f"spanish-backup-{clock.today().isoformat()}.json",
                           mime="application/json", key="backup_download")
        if st.session_state.get("restored"):
            st.success(f"Put back: {st.session_state.pop('restored')}.")
        files = st.file_uploader("Put back a backup", type="json", accept_multiple_files=True,
                                 key="backup_upload",
                                 help="A backup from the button above, or progress.json, practice.json "
                                      "and study_log.json from the app on your own computer.")
        found = read_uploads(files or [])
        if files and not found:
            st.warning("These files don't hold any results.")
        if found:
            st.caption("This replaces your current results with the ones in: "
                       + ", ".join(PARTS[p] for p in found) + ".")
            st.button("Replace my results", key="backup_put_back", type="primary", width="stretch",
                      on_click=put_back, args=(found,))


# ---------- home: progress across all levels ----------
def home():
    done, read, total = stats(catalog)
    all_questions = practice.every_item()
    mastered, questions = practice.mastery(all_questions)
    hero("Spanish Learning Program", "Your progress",
         f"{done} of {len(catalog)} PDFs done · {read} of {total} pages read · "
         f"{mastered} of {questions} practice questions mastered",
         done / len(catalog))
    st.write("")
    schedule.home_row()  # today's plan, with a button to the Schedule screen

    due = practice.due_items()
    c = st.columns([4, 1.5], vertical_alignment="center")
    if due:
        c[0].markdown(f"**📅 Daily review:** {len(due)} questions are due today")
        # The list is sorted with the longest overdue first, [:30] takes the first thirty.
        c[1].button("Review 30" if len(due) > 30 else f"Review {len(due)}", key="home_review", type="primary",
                    width="stretch", on_click=practice.start_drill,
                    args=(due[:30], "📅 Daily review", ("home",)))
    else:
        c[0].markdown("**📅 Daily review:** nothing is due today. Questions you practise come back "
                      "after 1, 3, 7 and 30 days.")

    recent = [(e["updated"], pid) for pid, e in st.session_state.progress.items()
              if e.get("updated") and pid in by_id]
    if recent:
        _, pid = max(recent)
        item = by_id[pid]
        c = st.columns([4, 1.5], vertical_alignment="center")
        c[0].markdown(f"**Continue where you left off:** {item['level']} · {item['title']} "
                      f"(page {entry(pid)['last_page'] + 1} of {page_count(item['file'])})")
        c[1].button("Continue ▶", on_click=open_reader, args=(pid,), type="primary", width="stretch")

    weak = practice.weak_items(all_questions)
    if weak:
        c = st.columns([4, 1.5], vertical_alignment="center")
        c[0].markdown(f"**Weak questions:** {len(weak)} across all levels")
        c[1].button("💪 Practise 20", key="home_weak", on_click=practice.start_drill, width="stretch",
                    args=(weak, "All levels · Weak questions", ("home",), None, None, 20))

    practice.weak_subjects_section(None, ("home",), "home_subject")

    st.subheader("Levels")
    cols = st.columns(3)
    for n, level in enumerate(LEVELS):
        items = level_items(level)
        level_done, level_read, level_total = stats(items)
        with cols[n % 3].container(border=True, key=f"card_{level}"):
            st.markdown(f"#### {level} · {LEVEL_NAMES[level]}")
            st.progress(level_done / len(items), text=f"{level_done} of {len(items)} PDFs done")
            level_mastered, level_questions = practice.mastery(practice.items_of_level(level))
            st.caption(f"{level_read} of {level_total} pages read  \n"
                       f"{level_mastered} of {level_questions} practice questions mastered")
            st.button(f"Open {level}", key=f"open_{level}", on_click=go_level, args=(level,),
                      width="stretch")


# ---------- level: progress within one level ----------
def level_screen():
    level = st.session_state.level
    items = level_items(level)
    done, read, total = stats(items)
    st.button("🏠 Home", key="level_home", on_click=go_home)
    level_questions = practice.items_of_level(level)
    mastered, questions = practice.mastery(level_questions)
    hero(f"Level {level}", LEVEL_NAMES[level],
         f"{done} of {len(items)} PDFs done · {read} of {total} pages read · "
         f"{mastered} of {questions} practice questions mastered", done / len(items))
    st.write("")

    # Practising across all the PDFs of this level at once.
    weak = practice.weak_items(level_questions)
    with st.container(horizontal=True):
        st.button(f"🎯 Test all of {level} (30 questions)", key="level_test", on_click=practice.start_drill,
                  args=(level_questions, f"{level} · Mixed test", ("level", level), None, None, 30))
        if weak:
            st.button(f"💪 Weak questions ({len(weak)})", key="level_weak", on_click=practice.start_drill,
                      args=(weak, f"{level} · Weak questions", ("level", level), None, None, 20))
    practice.weak_subjects_section(level, ("level", level), f"level_subject_{level}")

    next_up = next((i["id"] for i in items if status(i) != "done"), None)
    for item in items:
        stt = status(item)
        is_next = item["id"] == next_up
        with st.container(border=True, key=f"row_{item['id']}"):
            c = st.columns([0.45, 3.5, 1.6, 1.2, 1.2, 1.2], vertical_alignment="center")
            c[0].markdown(f"### {item['number']}")
            c[1].markdown(f"**{item['title']}**" + ("  ·  :red[Next up]" if is_next else ""))
            c[1].caption(f"{item['section']} · {page_count(item['file'])} pages · {item['subtitle']}")
            c[2].progress(fraction(item), text=STATUS_LABEL[stt])
            pdf_mastered, pdf_questions = practice.mastery(practice.load_all_items()[item["id"]])
            c[2].caption(f"{pdf_mastered} of {pdf_questions} questions mastered")
            label = {"done": "Read again", "reading": "Continue", "new": "Read"}[stt]
            c[3].button(label, key=f"read_{item['id']}", on_click=open_reader,
                        args=(item["id"], 0 if stt == "done" else None),
                        type="primary" if is_next else "secondary", width="stretch")
            c[4].button("Practise", key=f"practise_{item['id']}", on_click=practice.go_practice,
                        args=(item["id"],), width="stretch")
            with c[5].popover("More", width="stretch"):
                last_page = entry(item["id"])["last_page"] if stt == "reading" else 0
                st.link_button("Open in browser tab", browser_url(item, last_page), width="stretch")
                # Online the PDF app would open on the server, not on your computer, so it's left out.
                if not USER and st.button("Open in PDF app", key=f"app_{item['id']}", width="stretch"):
                    open_in_pdf_app(item)
                st.button("Mark as not done" if stt == "done" else "Mark as done",
                          key=f"done_{item['id']}", on_click=toggle_done, args=(item["id"],),
                          width="stretch")


# ---------- reader ----------
def reader():
    item = by_id[st.session_state.current]
    total = page_count(item["file"])
    page = st.session_state.page
    e = entry(item["id"])
    if page not in e["seen"]:
        e["seen"].append(page)
    e["last_page"] = page
    touch(item["id"])
    save_progress()
    # Count the time you read, but only once per page: the screen also reruns when you change the size.
    if st.session_state.get("logged_page") != (item["id"], page):
        st.session_state.logged_page = (item["id"], page)
        log_activity("page")

    top = st.columns([1, 1.7, 5, 2.2], vertical_alignment="center")
    top[0].button("🏠 Home", key="reader_home", on_click=go_home, width="stretch")
    top[1].button(f"← {item['level']} · {LEVEL_NAMES[item['level']]}", key="reader_level",
                  on_click=go_level, args=(item["level"],), width="stretch")
    top[2].markdown(f"#### {item['level']} · PDF {item['number']} — {item['title']}")
    top[3].progress(fraction(item), text=STATUS_LABEL[status(item)])

    bar = st.columns([1, 1, 1.3, 1.6, 2, 2, 1.8], vertical_alignment="center")
    bar[0].button("◀ Prev", on_click=turn_page, args=(-1,), disabled=page == 0,
                  shortcut="Left", width="stretch")
    bar[1].button("Next ▶", on_click=turn_page, args=(1,), disabled=page >= total - 1,
                  shortcut="Right", width="stretch")
    bar[2].number_input("Page", 1, total, key="page_jump", on_change=jump_changed,
                        label_visibility="collapsed")
    bar[3].markdown(f"**of {total}**  ·  read {len(e['seen'])}/{total}")
    bar[4].link_button("Open in browser tab", browser_url(item, page), width="stretch")
    if not USER and bar[5].button("Open in PDF app", width="stretch"):
        open_in_pdf_app(item)
    size = bar[6].selectbox("Size", list(PAGE_WIDTHS), index=1, label_visibility="collapsed")

    st.html(f'<div style="text-align:center"><img class="pdf-page" src="{render_page(item["file"], page)}" '
            f'alt="Page {page + 1} of {total}" style="max-width:{PAGE_WIDTHS[size]}px"></div>')

    foot = st.columns([1, 1, 2, 2, 2])
    foot[0].button("◀ Prev ", on_click=turn_page, args=(-1,), disabled=page == 0,
                   key="prev2", width="stretch")
    foot[1].button("Next ▶ ", on_click=turn_page, args=(1,), disabled=page >= total - 1,
                   key="next2", width="stretch")
    label = "Mark as not done" if status(item) == "done" else "Mark as done"
    foot[2].button(label, on_click=toggle_done, args=(item["id"],), width="stretch",
                   type="primary" if page == total - 1 and status(item) != "done" else "secondary")
    foot[3].button("Reset progress for this PDF", on_click=reset_pdf, args=(item["id"],),
                   width="stretch")
    foot[4].button("Practise this PDF", key="reader_practise", on_click=practice.go_practice,
                   args=(item["id"],), width="stretch")


# ---------- run ----------
SCREENS = {"home": home, "level": level_screen, "reader": reader,
           "practice": practice.practice_screen, "drill": practice.drill_screen,
           "themes": extra.themes_screen, "mock": extra.mock_screen,
           "mock_run": extra.mock_run_screen, "mock_result": extra.mock_result_screen,
           "schedule": schedule.schedule_screen, "progress": progress.progress_screen}
# The Schedule screen needs to open the reader and know how much of a PDF you read; both live in this file.
schedule.connect(open_reader, lambda pid: fraction(by_id[pid]),
                 lambda pid: st.session_state.progress.get(pid, {}).get("updated"))
practice.ACTIONS["open_reader"] = open_reader  # for the "Next PDF" button after a practice session
SCREENS[st.session_state.view]()
sidebar()  # after the screen, so its counts include the page just opened
scroll_to_top_after_moving()
