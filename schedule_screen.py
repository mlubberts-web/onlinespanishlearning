"""The Schedule screen: your daily goals in PDFs and exercises until 20 January, a dashboard of
what you studied, and how far you are. The plan is made in study_plan.py, the study time and the
dates you finished things are kept in study_log.py."""
import html
from datetime import date, timedelta
import clock
from pathlib import Path

import pymupdf
import streamlit as st

import practice_screen as practice
import practice_store as store
import study_log
import study_plan as plans
from ui import go_view, hero, log_data, save_log

HERE = Path(__file__).parent
SECTIONS = ["📅 Today", "🗓️ Coming days", "📈 Total", "⏱️ Mock exams", "⚙️ Settings"]
ICONS = {"read": "📖", "exercise": "✍️", "mock": "⏱️", "theme": "📚"}
PARTS = ["Reading", "Listening", "Writing", "Speaking"]
TARGET = 70  # aim for at least this percentage on every part of a mock exam
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
MOCK_SLOTS = [(level, number) for level in LEVELS for number in (1, 2)]
OFFICIAL_SITE = "https://cervantes.org/es/examenes/dele"

# app.py fills these in with connect(), because the reader and its progress live in app.py.
ACTIONS = {}


def connect(open_reader, reading_share, read_date):
    ACTIONS["open_reader"] = open_reader
    ACTIONS["reading_share"] = reading_share  # PDF id -> share of its pages read, 0 to 1
    ACTIONS["read_date"] = read_date          # PDF id -> when you last read in it, as text, or None


# ---------- small helpers ----------
def fmt(minutes):
    """75 -> '1 h 15', 40 -> '40 min'."""
    minutes = round(minutes)
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d}" if minutes % 60 else f"{minutes // 60} h"


def long_date(day):
    return f"{day:%A} {day.day} {day:%B}"


def monday_of(day):
    return day - timedelta(days=day.weekday())


def safe(text):
    return "".join(ch if ch.isalnum() else "_" for ch in text)


def plural(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


# ---------- the units of the plan and how far you are ----------
@st.cache_resource(show_spinner=False)
def pdf_info():
    """cache_resource keeps one copy for the whole session; these lists are only read, never changed."""
    all_items = practice.load_all_items()
    result = []
    for pdf in practice.load_catalog():
        with pymupdf.open(HERE / "static" / "pdfs" / pdf["file"]) as doc:
            pages = doc.page_count
        result.append({"id": pdf["id"], "level": pdf["level"], "number": pdf["number"],
                       "title": pdf["title"], "pages": pages, "items": all_items[pdf["id"]]})
    return result


@st.cache_resource(show_spinner=False)
def theme_info():
    return [{"name": name, "title": theme["title"], "lists": theme["lists"], "items": theme["items"]}
            for name, theme in practice.load_themes().items()]


def goals():
    """Your deadlines, from low to high level. Until you set your own, the example ones."""
    saved = log_data().get("deadlines") or plans.DEFAULT_GOALS
    return sorted(saved, key=lambda goal: plans.LEVELS.index(goal["level"]))


def phases():
    """Your deadlines as phases (see study_plan.make_phases), starting on your first day."""
    return plans.make_phases(goals(), first_day(clock.today()))


@st.cache_resource(show_spinner=False)
def units_for(phase_list):
    """The units for these phases. cache_resource keeps one list for each set of deadlines, shared
    by everyone with the same deadlines; the lists are only read, never changed."""
    return plans.all_units(pdf_info(), theme_info(), phase_list)


def plan_units():
    # The units only depend on the levels of each phase, not on the dates, so the dates are left out:
    # then moving a deadline doesn't make a new list.
    return units_for([{key: value for key, value in phase.items() if key not in ("start", "end", "goal")}
                      for phase in phases()])


@st.cache_resource(show_spinner=False)
def unit_items():
    """For each exercise unit: its questions. The unit id is 'exercise:' + source + '|' + type."""
    groups = {}
    for pdf in pdf_info():
        for item in pdf["items"]:
            groups.setdefault(f"exercise:{pdf['id']}|{item['mode']}", []).append(item)
    for theme in theme_info():
        for item in theme["items"]:
            groups.setdefault(f"exercise:THEME_{theme['name']}|list:{item['group']}|{item['mode']}", []).append(item)
    return groups


def unit_shares(units):
    """For each unit: the share finished, 0 to 1. Reading counts the pages you opened, an exercise
    the questions answered at least once (or marked as done), a mock exam the result you logged."""
    groups = unit_items()
    mocks = {(m["level"], m["number"]) for m in log_data().get("mocks", [])}
    shares = {}
    for unit in units:
        if unit["kind"] == "read":
            shares[unit["id"]] = ACTIONS["reading_share"](unit["pdf_id"])
        elif unit["kind"] == "exercise":
            items = groups.get(unit["id"], [])
            shares[unit["id"]] = sum(practice.is_answered(i) for i in items) / len(items) if items else 1.0
        else:
            shares[unit["id"]] = 1.0 if (unit["level"], unit["number"]) in mocks else 0.0
    return shares


def estimated_dates(units):
    """For what you finished before the dates were kept: the date it was most likely finished."""
    stats = practice.practice_data()["items"]
    groups = unit_items()
    mocks = {(m["level"], m["number"]): m["date"] for m in log_data().get("mocks", [])}
    guesses = {}
    for unit in units:
        if unit["kind"] == "read":
            guess = ACTIONS["read_date"](unit["pdf_id"])
            guesses[unit["id"]] = guess[:10] if guess else None  # [:10] keeps only the date of the time
        elif unit["kind"] == "exercise":
            dates = [store.last_answer_date(stats[i["id"]]) for i in groups.get(unit["id"], []) if i["id"] in stats]
            dates = [d for d in dates if d]
            guesses[unit["id"]] = max(dates) if dates else None
        else:
            guesses[unit["id"]] = mocks.get((unit["level"], unit["number"]))
    return guesses


def hours():
    return log_data().get("hours", plans.DEFAULT_HOURS)


def current_state(today):
    """Returns (plan, shares, finished ids). Also writes down newly finished units and fixes
    today's list the first time you look at it."""
    log = log_data()
    units = plan_units()
    shares = unit_shares(units)
    finished = {unit_id for unit_id, share in shares.items() if share >= 0.999}
    estimates = estimated_dates(units) if "finished" not in log else None  # only the very first time
    changed = study_log.update_finished(log, finished, today.isoformat(), estimates)
    frozen = log.get("goals", {}).get(today.isoformat())
    plan = plans.build_plan(units, today, finished, hours(), set(log.get("days_off", [])), frozen, phases())
    row = day_rows(plan).get(today)
    if frozen is None and row is not None:
        log.setdefault("goals", {})[today.isoformat()] = [unit["id"] for unit in row["units"]]
        changed = True
    if changed:
        save_log()
    return plan, shares, finished


def day_rows(plan):
    return {row["date"]: row for row in plan["days"]}


def day_entry(day):
    """The log of one day without creating it, so just looking doesn't change the file."""
    return log_data().get("days", {}).get(day.isoformat(), {})


def units_by_id():
    return {unit["id"]: unit for unit in plan_units()}


def goal_units(day):
    """The units on a day's list (fixed when you first looked at it), or [] when it had none."""
    lookup = units_by_id()
    return [lookup[i] for i in log_data().get("goals", {}).get(day.isoformat(), []) if i in lookup]


def count(units, kind):
    return sum(1 for unit in units if unit["kind"] == kind)


def finished_on(day, kind):
    """How many units of a kind (read / exercise / mock) you finished on this day."""
    text = day.isoformat()
    lookup = units_by_id()
    return sum(1 for unit_id, d in log_data().get("finished", {}).items()
               if d == text and unit_id in lookup and lookup[unit_id]["kind"] == kind)


def first_day(today):
    """Your first day of studying: the earliest date in the log, or today."""
    log = log_data()
    dates = list(log.get("days", {})) + list(log.get("finished", {}).values()) + list(log.get("goals", {}))
    return min([date.fromisoformat(d) for d in dates] + [today])


def current_phase(today):
    every = phases()
    return next((p for p in every if p["end"] >= today), every[-1])


def pace_text(plan, finished, today):
    """('success'/'warning'/'info', text): what you need per day for the next deadline against
    what you did per day over the last 7 days."""
    phase = current_phase(today)
    units = plan["units"]
    need_read = plans.needed_per_day(plan, units, finished, phase["name"], today, "read", phases())
    need_ex = plans.needed_per_day(plan, units, finished, phase["name"], today, "exercise", phases())
    week = [today - timedelta(days=n) for n in range(7)]
    did_read = sum(finished_on(d, "read") for d in week) / 7
    did_ex = sum(finished_on(d, "exercise") for d in week) / 7
    text = (f"For **{phase['goal']}** you need on average **{need_read:.1f} PDFs** and **{need_ex:.1f} exercises** "
            f"per study day. Over the last 7 days you did {did_read:.1f} and {did_ex:.1f} a day.")
    if need_read == 0 and need_ex == 0:
        return "success", f"Everything for {phase['goal']} is finished. 🎉"
    if did_ex >= need_ex and did_read >= need_read:
        return "success", text + " 🎉"
    return "info", text + (" The lists are shared out by the time things take, so while you are in the "
                           "lower levels, whose exercises go quickly, a day's list is longer than this average.")


# ---------- callbacks ----------
def tick(day_text, block, minutes):
    study_log.tick_block(log_data(), day_text, block, minutes)
    save_log()


def set_extra(day_text, key):
    study_log.day(log_data(), day_text)["extra"] = st.session_state[key]
    save_log()


def go_mock_log(level, number):
    st.session_state.schedule_section = "⏱️ Mock exams"
    st.session_state.mock_slot = f"{level} · no. {number}"


def move_week(key, step):
    st.session_state[key] = st.session_state.get(key, 0) + step if step else 0


def remake_today():
    """After a change in Settings: today's list is made again with the new settings."""
    log_data().get("goals", {}).pop(clock.today().isoformat(), None)


# ---------- the screen ----------
def schedule_screen():
    today = clock.today()
    plan, shares, finished = current_state(today)
    goal = goal_units(today)
    done = study_log.finished_by(log_data(), [u["id"] for u in goal], today.isoformat())
    studied = study_log.studied_minutes(log_data(), today.isoformat())
    countdown = " · ".join(f"{(phase['end'] - today).days} days to {phase['name']}"
                           for phase in phases() if phase["end"] >= today)
    reads, exercises = [u["id"] for u in goal if u["kind"] == "read"], [u["id"] for u in goal if u["kind"] == "exercise"]
    log = log_data()
    hero("Schedule", long_date(today),
         f"{study_log.finished_by(log, exercises, today.isoformat())} of {len(exercises)} exercises · "
         f"{study_log.finished_by(log, reads, today.isoformat())} of {len(reads)} PDFs read today · "
         f"{fmt(studied)} studied · {countdown}", done / len(goal) if goal else 0)
    st.write("")
    st.session_state.setdefault("schedule_section", SECTIONS[0])
    if st.session_state.schedule_section not in SECTIONS:  # a name from an older version
        st.session_state.schedule_section = SECTIONS[0]
    # A row of buttons; required=True keeps one chosen. Its value comes from session_state above.
    section = st.segmented_control("Show", SECTIONS, required=True, key="schedule_section",
                                   label_visibility="collapsed")
    if "deadlines" not in log_data():
        c = st.columns([4, 1.5], vertical_alignment="center")
        c[0].info("These deadlines are examples: " + ", ".join(p["goal"] for p in phases()) +
                  ". Set your own in ⚙️ Settings, or keep these.")
        c[1].button("Keep these deadlines", key="deadlines_keep", on_click=save_goals, args=(goals(),),
                    width="stretch")
    if plan["late"]:
        st.error(f"{plural(len(plan['late']), 'part')} of the plan no longer fit before "
                 f"{long_date(phases()[-1]['end'])}.")
    {"📅 Today": today_section, "🗓️ Coming days": coming_section,
     "📈 Total": total_section, "⏱️ Mock exams": mock_section, "⚙️ Settings": settings_section}[section](
        plan, shares, finished, today)


# ---------- today ----------
def today_section(plan, shares, finished, today):
    row = day_rows(plan).get(today)
    if row is None:
        first, last = phases()[0]["start"], phases()[-1]["end"]
        st.info(f"Your plan runs from {long_date(first)} {first.year} to {long_date(last)} {last.year}. "
                "Set new deadlines in ⚙️ Settings.")
        return
    log = log_data()
    goal = goal_units(today)
    text = today.isoformat()
    c = st.columns(4)
    for column, kind, label in [(c[0], "exercise", "Exercises finished"), (c[1], "read", "PDFs read")]:
        ids = [u["id"] for u in goal if u["kind"] == kind]
        column.metric(label, f"{study_log.finished_by(log, ids, text)} of {len(ids)}",
                      help="Finished from today's list. Work you do beyond it counts too: it makes the coming days lighter.")
    c[2].metric("Studied today", fmt(study_log.studied_minutes(log, text)),
                help="Time in the app is counted from your answers and the pages you turn. A break of "
                     "more than 3 minutes (10 while reading) isn't counted.")
    c[3].metric("Streak", f"{study_log.streak(log, text)} days",
                help="Days in a row on which you finished your whole list. Days off don't break it.")
    kind, message = pace_text(plan, finished, today)
    getattr(st, kind)(message)  # st.success or st.info

    if row["budget"] == 0 and not goal:
        st.info("🌴 Day off. Enjoy it, the plan has moved its work to the other days.")
        return
    estimate = row["review"] + row["writing"] + sum(u["minutes"] for u in goal)
    st.subheader("Today's goal")
    st.caption(f"Estimated time: about {fmt(estimate)}. Your goal is the list, not the time: finish it "
               "faster or slower, both are fine.")
    review_row(today)
    for title, kind_units in group_units(goal):
        unit_row(title, kind_units, shares, "today")
    if goal and all(shares.get(u["id"], 0) >= 0.999 for u in goal):
        st.success("Today's list is done. ✅ If you want to do more, these come next:")
        upcoming = next((r["units"] for r in plan["days"] if r["date"] > today and r["units"]), [])
        for title, kind_units in group_units(upcoming)[:3]:
            unit_row(title, kind_units, shares, "next")
    if row["writing"]:
        writing_row(today, row)
    key = f"extra_{text}"
    st.number_input("Minutes you studied outside the app today (a class, a book, a podcast...)", 0, 600,
                    value=int(day_entry(today).get("extra", 0)), step=15, key=key,
                    on_change=set_extra, args=(text, key))


def group_units(units):
    """Puts the exercises of one PDF or themed list together: [(title, [units])], in plan order."""
    groups = {}
    for unit in units:
        if unit["kind"] == "exercise":
            key = unit.get("pdf_id") or f"{unit['theme']}|{unit['group']}"
            groups.setdefault(("exercise", key), (f"Practise {unit['title']}", []))[1].append(unit)
        elif unit["kind"] == "read":
            groups[("read", unit["id"])] = (f"Read {unit['title']}", [unit])
        else:
            groups[("mock", unit["id"])] = (unit["title"], [unit])
    return list(groups.values())


def block_row(key, icon, title, caption, ticked):
    """A row with an icon, a title and room on the right for buttons. Returns the button columns."""
    with st.container(border=True, key=f"plan_{key}"):
        c = st.columns([0.5, 4, 2, 1.4], vertical_alignment="center")
        c[0].markdown(f"### {'✅' if ticked else icon}")
        c[1].markdown(f"**{title}**")
        c[1].caption(caption)
        return c[2], c[3]


def review_row(today):
    due = practice.due_items()
    ticked = "review" in day_entry(today).get("blocks", {})
    left, right = block_row("review", "📅", f"Daily review · {plural(len(due), 'question')} due",
                            "The oldest come first. Not part of the goal: do what you can.", ticked)
    if due:
        left.button(f"Review {min(30, len(due))}", key="plan_review_start", type="primary", width="stretch",
                    on_click=practice.start_drill, args=(due[:30], "📅 Daily review", ("view", "schedule")))
    right.button("Undo" if ticked else "Done", key="plan_review_tick", width="stretch",
                 on_click=tick, args=(today.isoformat(), "review", 0))


def unit_row(title, units, shares, place):
    """One row for a PDF to read, the exercises of one PDF or list, or a mock exam."""
    first = units[0]
    done = [u for u in units if shares.get(u["id"], 0) >= 0.999]
    finished = len(done) == len(units)
    if first["kind"] == "exercise":
        caption = f"{len(done)} of {plural(len(units), 'exercise')} finished: " + " · ".join(
            f"{'✅' if u in done else '⬜'} {practice.mode_title(u['mode'])}" for u in units)
        share = sum(min(1.0, shares.get(u["id"], 0)) for u in units) / len(units)
        icon = ICONS["theme"] if first.get("theme") else ICONS["exercise"]
    elif first["kind"] == "read":
        share = shares.get(first["id"], 0)
        caption = f"{first['pages']} pages · {share:.0%} read"
        icon = ICONS["read"]
    else:
        share = shares.get(first["id"], 0)
        caption = ("Use an official model exam, on paper and timed. You may split it over two days, "
                   "then log your scores.")
        icon = ICONS["mock"]
    key = f"{place}_{safe(first['id'])}"
    left, right = block_row(key, icon, title, caption, finished)
    left.progress(min(1.0, share), text=f"{share:.0%}")
    kind = "secondary" if finished else "primary"
    if first["kind"] == "read":
        # A PDF you finished opens at page 1, otherwise where you stopped (None).
        right.button("Read", key=f"{key}_go", type=kind, width="stretch", on_click=ACTIONS["open_reader"],
                     args=(first["pdf_id"], 0 if share >= 0.999 else None))
    elif first["kind"] == "exercise" and first.get("pdf_id"):
        right.button("Practise", key=f"{key}_go", type=kind, width="stretch", on_click=practice.go_practice,
                     args=(first["pdf_id"],))
    elif first["kind"] == "exercise":
        right.button("Open", key=f"{key}_go", type=kind, width="stretch", on_click=go_view, args=("themes",))
    else:
        right.button("Log result", key=f"{key}_go", type=kind, width="stretch", on_click=go_mock_log,
                     args=(first["level"], first["number"]))


def writing_row(today, row):
    # Writing and speaking take turns, one day each.
    if today.toordinal() % 2:
        title, caption = "Writing", "Write one task from an official model exam, then check it or have it checked."
    else:
        title, caption = "Speaking", "Record a 3-minute monologue on a topic from a model exam and listen back."
    ticked = "writing" in day_entry(today).get("blocks", {})
    _, right = block_row("writing", "🖋️" if title == "Writing" else "🎙️", f"{title} · {fmt(row['writing'])}",
                         caption + " Ticking it adds its time to today.", ticked)
    right.button("Undo" if ticked else "Done", key="plan_writing_tick", width="stretch",
                 on_click=tick, args=(today.isoformat(), "writing", row["writing"]))


# ---------- coming days ----------
def coming_section(plan, shares, finished, today):
    monday = monday_of(today) + timedelta(weeks=st.session_state.get("plan_week", 0))
    days = [monday + timedelta(days=n) for n in range(7)]
    rows = day_rows(plan)
    with st.container(horizontal=True, vertical_alignment="center"):
        st.button("◀ Previous week", key="week_back", on_click=move_week, args=("plan_week", -1),
                  disabled=monday <= monday_of(today))
        st.button("This week", key="week_now", on_click=move_week, args=("plan_week", 0))
        st.button("Next week ▶", key="week_next", on_click=move_week, args=("plan_week", 1),
                  disabled=days[-1] >= phases()[-1]["end"])
        st.markdown(f"**{days[0].day} {days[0]:%B} – {days[6].day} {days[6]:%B}**")
    st.caption("The coming days are a forecast: each morning the plan starts again from where you are, "
               "so finishing more today makes the following days lighter.")
    columns = st.columns(7)
    for column, day in zip(columns, days):
        with column.container(border=True, key=f"week_{day.isoformat()}"):
            st.markdown(f"**{day:%a} {day.day}**" + (" · :red[today]" if day == today else ""))
            row = rows.get(day)
            if day < today:
                st.caption("Past: see the 📊 Progress tab")
                continue
            if row is None:
                st.caption("Outside the plan")
                continue
            units = goal_units(day) if day == today else row["units"]
            if not units:
                st.caption("🌴 Day off" if row["budget"] == 0 else "Nothing planned")
                continue
            lines = []
            for title, group in group_units(units):
                first = group[0]
                mark = "✅" if all(shares.get(u["id"], 0) >= 0.999 for u in group) else \
                    ICONS["theme"] if first.get("theme") else ICONS[first["kind"]]
                if first["kind"] == "exercise":
                    name = f"{first['level']} {first['number']:02d}" if first.get("pdf_id") else first["group"]
                    lines.append(f"{mark} {name}: {plural(len(group), 'exercise')}")
                elif first["kind"] == "read":
                    lines.append(f"{mark} Read {first['level']} {first['number']:02d}")
                else:
                    lines.append(f"{mark} Mock {first['level']} no. {first['number']}")
            if row["writing"]:
                lines.append(f"🖋️ Writing {row['writing']} min")
            st.caption(f"{count(units, 'read')} PDFs · {count(units, 'exercise')} exercises  \n" + "  \n".join(lines))


# ---------- total ----------
def total_section(plan, shares, finished, today):
    log = log_data()
    units = plan["units"]
    c = st.columns(5)
    c[0].metric("PDFs read", f"{sum(1 for u in units if u['kind'] == 'read' and u['id'] in finished)} of "
                             f"{count(units, 'read')}")
    c[1].metric("Exercises finished", f"{sum(1 for u in units if u['kind'] == 'exercise' and u['id'] in finished)} of "
                                      f"{count(units, 'exercise')}")
    c[2].metric("Studied in total", fmt(sum(study_log.studied_minutes(log, d) for d in log.get("days", {}))))
    c[3].metric("Mock exams", f"{len(log.get('mocks', []))} of {len(MOCK_SLOTS)}")
    c[4].metric("Streak", f"{study_log.streak(log, today.isoformat())} days")

    st.subheader("Deadlines")
    every = phases()
    columns = st.columns(len(every))
    week = [today - timedelta(days=n) for n in range(7)]
    pace = sum(finished_on(d, "read") + finished_on(d, "exercise") + finished_on(d, "mock") for d in week) / 7
    for n, (column, phase) in enumerate(zip(columns, every)):
        names = [p["name"] for p in every[:n + 1]]  # this phase and the ones before it
        left = [u for u in units if u["phase"] in names and u["id"] not in finished]
        with column.container(border=True, key=f"deadline_{safe(phase['name'])}"):
            st.markdown(f"#### 🏁 {phase['goal']}")
            st.markdown(f"Deadline: **{long_date(phase['end'])}** · {max(0, (phase['end'] - today).days)} days left  \n"
                        f"Left{', earlier levels included' if n else ''}: **{count(left, 'read')} PDFs** to read, **{count(left, 'exercise')} exercises**, "
                        f"**{count(left, 'mock')} mock exams**")
            if not left:
                st.success("All done! 🎉")
            elif pace <= 0:
                st.caption("Your expected finish date appears here once you finish PDFs and exercises.")
            else:
                projected = today + timedelta(days=-(-len(left) // pace))  # -(-a // b) rounds up
                if projected <= phase["end"]:
                    st.success(f"At your pace of the last 7 days you finish on **{long_date(projected)}**.")
                else:
                    st.warning(f"At your pace of the last 7 days you finish on **{long_date(projected)}**, "
                               f"{(projected - phase['end']).days} days late. The daily lists will grow to make up for it.")

    st.subheader("Levels")
    level_rows(plan, finished)
    st.subheader("Calendar")
    st.html(calendar_html(plan, today))


def level_rows(plan, finished):
    mocks = {(m["level"], m["number"]) for m in log_data().get("mocks", [])}
    for level in LEVELS:
        units = [u for u in plan["units"] if u["level"] == level]
        if not units:
            continue  # a level above your last deadline isn't in your plan
        reads = [u for u in units if u["kind"] == "read"]
        exercises = [u for u in units if u["kind"] == "exercise"]
        read = sum(u["id"] in finished for u in reads) / len(reads)
        practised = sum(u["id"] in finished for u in exercises) / len(exercises)
        level_mocks = sum((level, n) in mocks for n in (1, 2))
        end = plans.finish_day(plan, lambda unit: unit["level"] == level)
        with st.container(border=True, key=f"total_{level}"):
            c = st.columns([0.8, 2, 2, 1.2, 1.6], vertical_alignment="center")
            c[0].markdown(f"### {level}")
            c[1].progress(read, text=f"PDFs read {read:.0%}")
            c[2].progress(practised, text=f"Exercises finished {practised:.0%}")
            c[3].markdown(f"⏱️ Mocks **{level_mocks}/2**")
            c[4].caption(f"Planned to finish: {long_date(end)}" if end else "")


def calendar_html(plan, today):
    """A calendar like the one on a GitHub profile: one column per week, darker means more of
    that day's list finished. Days before the lists existed are coloured by the hours you studied."""
    rows = day_rows(plan)
    log = log_data()
    mock_days = {}
    for row in plan["days"]:
        for unit in row["units"]:
            if unit["kind"] == "mock":
                mock_days.setdefault(row["date"], f"Mock {unit['level']} no. {unit['number']}")
    every = phases()
    deadlines = {phase["end"]: phase["goal"] for phase in every}
    start, last_day = every[0]["start"], every[-1]["end"]
    first = monday_of(start)
    weeks = max(1, (last_day - first).days // 7 + 1)
    cells, months = [], []
    for w in range(weeks):
        monday = first + timedelta(weeks=w)
        # The month name goes above the first week, and above each week in which a month starts.
        month_start = next((monday + timedelta(days=n) for n in range(7)
                            if (monday + timedelta(days=n)).day == 1), monday if w == 0 else None)
        months.append(f'<div class="cal-month">{f"{month_start:%b}" if month_start else ""}</div>')
        for n in range(7):
            day = monday + timedelta(days=n)
            row = rows.get(day)
            text = day.isoformat()
            classes, tip = ["cal-day"], [long_date(day)]
            goal = log.get("goals", {}).get(text)
            studied = study_log.studied_minutes(log, text)
            if day < start or day > last_day:
                classes.append("cal-out")
            elif day <= today and goal:
                share = study_log.finished_by(log, goal, text) / len(goal)
                classes.append("cal-4" if share >= 1 else "cal-3" if share >= 0.66 else
                               "cal-2" if share >= 0.33 else "cal-1" if share > 0 else "cal-0")
                tip.append(f"{study_log.finished_by(log, goal, text)} of {len(goal)} of the list · {fmt(studied)}")
            elif day <= today:
                classes.append("cal-2" if studied >= 60 else "cal-1" if studied > 0 else "cal-0")
                tip.append(f"{fmt(studied)} studied" + (" · no list yet" if day < today else ""))
            elif row is not None and row["budget"] == 0:
                classes.append("cal-off")
                tip.append("day off")
            else:
                classes.append("cal-future")
                if row is not None:
                    tip.append(f"{count(row['units'], 'read')} PDFs · {count(row['units'], 'exercise')} exercises")
            if day in mock_days:  # a small dot in the corner
                classes.append("cal-mock")
                tip.append(mock_days[day])
            if day in deadlines:  # a thick border
                classes.append("cal-deadline")
                tip.append(deadlines[day])
            if day == today:
                classes.append("cal-today")
            cells.append(f'<div class="{" ".join(classes)}" style="grid-column:{w + 2};grid-row:{n + 2}" '
                         f'title="{html.escape(" · ".join(tip))}">{day.day}</div>')
    labels = "".join(f'<div class="cal-label" style="grid-row:{n + 2}">{name}</div>'
                     for n, name in enumerate(["Mon", "", "Wed", "", "Fri", "", "Sun"]))
    month_row = "".join(m.replace('class="cal-month"', f'class="cal-month" style="grid-column:{w + 2};grid-row:1"')
                        for w, m in enumerate(months))
    return f"""
<style>
  .cal {{ display: grid; grid-template-columns: 34px repeat({weeks}, 30px); grid-auto-rows: 30px;
          gap: 4px; font: 12px sans-serif; color: #2b3345; overflow-x: auto; padding-bottom: 4px; }}
  .cal-label, .cal-month {{ color: #6b7385; display: flex; align-items: center; }}
  .cal-day {{ border-radius: 6px; display: flex; align-items: center; justify-content: center; cursor: default;
              position: relative; }}
  .cal-mock::after {{ content: ""; position: absolute; top: 3px; right: 3px; width: 7px; height: 7px;
                      border-radius: 50%; background: #1f2a44; border: 1px solid #fff; }}
  .cal-out {{ visibility: hidden; }}
  .cal-0 {{ background: #e6e1d6; }}  .cal-1 {{ background: #f6d0ca; }}  .cal-2 {{ background: #ec9a90; }}
  .cal-3 {{ background: #e4685c; color: #fff; }}  .cal-4 {{ background: #c0392b; color: #fff; }}
  .cal-future {{ background: #fff; border: 1px solid #e0d9cc; }}
  .cal-off {{ background: repeating-linear-gradient(45deg, #eee9df, #eee9df 4px, #f7f4ee 4px, #f7f4ee 8px); }}
  .cal-deadline {{ border: 2px solid #1f2a44; }}
  .cal-today {{ outline: 3px solid #1f2a44; outline-offset: 1px; }}
  .cal-legend {{ display: flex; gap: 14px; flex-wrap: wrap; margin-top: 10px; font: 12px sans-serif; color: #6b7385; }}
  .cal-legend span {{ display: inline-flex; align-items: center; gap: 5px; }}
  .cal-legend i {{ width: 14px; height: 14px; border-radius: 4px; display: inline-block; }}
</style>
<div class="cal">{month_row}{labels}{"".join(cells)}</div>
<div class="cal-legend">
  <span><i class="cal-0"></i>nothing</span><span><i class="cal-1"></i>under a third of the list</span>
  <span><i class="cal-2"></i>a third</span><span><i class="cal-3"></i>two thirds</span>
  <span><i class="cal-4"></i>list finished</span><span><i class="cal-off"></i>day off</span>
  <span><i class="cal-future cal-mock" style="position:relative"></i>mock exam planned</span>
  <span><i class="cal-future cal-deadline"></i>deadline</span><span>hover over a day for details</span>
</div>"""


# ---------- mock exams ----------
def remove_mock(level, number):
    study_log.remove_mock(log_data(), level, number)
    save_log()


def save_mock_form(slot):
    # The fields have the exam in their key, so each exam keeps its own fields.
    s = st.session_state
    level, number = slot.split(" · no. ")
    parts = {part: s[f"mock_part_{part}_{slot}"] for part in PARTS}
    study_log.save_mock(log_data(), level, int(number), s[f"mock_date_{slot}"].isoformat(),
                        s[f"mock_minutes_{slot}"], parts, s[f"mock_note_{slot}"])
    save_log()
    st.toast(f"Saved: DELE {level} mock exam no. {number}")


def mock_section(plan, shares, finished, today):
    st.markdown(f"Take these on paper with the official model exams of the Instituto Cervantes, timed and "
                f"with the audio, then log your scores here. My suggestion: aim for at least **{TARGET}%** on "
                "every part. That is a target for practice, not the official pass mark.")
    st.link_button("Official DELE page of the Instituto Cervantes", OFFICIAL_SITE)
    logged = {(m["level"], m["number"]): m for m in log_data().get("mocks", [])}
    starts = {}
    for row in plan["days"]:
        for unit in row["units"]:
            if unit["kind"] == "mock":
                starts.setdefault((unit["level"], unit["number"]), row["date"])
    for n, (level, number) in enumerate(MOCK_SLOTS):
        if n % 4 == 0:  # a new row of four cards, so they read from left to right
            columns = st.columns(4)
        mock = logged.get((level, number))
        with columns[n % 4].container(border=True, key=f"mock_{level}_{number}"):
            st.markdown(f"#### {level} · no. {number}")
            if mock:
                scores = mock["parts"]
                average = sum(scores.values()) / len(scores)
                st.markdown(f"{'✅' if min(scores.values()) >= TARGET else '🔸'} **{average:.0f}%** on average · "
                            f"{long_date(date.fromisoformat(mock['date']))}")
                st.markdown("  \n".join(f"{':green' if score >= TARGET else ':red'}[{part}: {score}%]"
                                        for part, score in scores.items()))
                if mock.get("note"):
                    st.caption(mock["note"])
                c = st.columns(2)
                c[0].button("Edit", key=f"mock_edit_{level}_{number}", on_click=go_mock_log, args=(level, number),
                            width="stretch")
                c[1].button("Remove", key=f"mock_remove_{level}_{number}", on_click=remove_mock,
                            args=(level, number), width="stretch")
            else:
                start = starts.get((level, number))
                st.caption(f"Planned for {long_date(start)}" if start else "Not in the plan")
                st.button("Log result", key=f"mock_log_{level}_{number}", on_click=go_mock_log, args=(level, number),
                          width="stretch")

    st.subheader("Log a result")
    st.session_state.setdefault("mock_slot", f"{MOCK_SLOTS[0][0]} · no. 1")
    # The choice of exam is outside the form, so the fields below change straight away when you pick another.
    slot = st.selectbox("Mock exam", [f"{level} · no. {number}" for level, number in MOCK_SLOTS], key="mock_slot")
    level, number = slot.split(" · no. ")
    old = logged.get((level, int(number)))
    with st.form(f"mock_form_{slot}"):
        c = st.columns(2)
        c[0].date_input("Date", value=date.fromisoformat(old["date"]) if old else today, key=f"mock_date_{slot}")
        c[1].number_input("Minutes it took you", 10, 600, value=old["minutes"] if old else plans.MOCK_MINUTES[level],
                          step=10, key=f"mock_minutes_{slot}")
        c = st.columns(4)
        for column, part in zip(c, PARTS):
            column.number_input(f"{part} (%)", 0, 100, value=old["parts"][part] if old else 0, step=1,
                                key=f"mock_part_{part}_{slot}")
        st.text_input("Note (what went wrong, what to practise)", value=old.get("note", "") if old else "",
                      key=f"mock_note_{slot}")
        st.form_submit_button("Save result", type="primary", on_click=save_mock_form, args=(slot,))
    st.caption("The minutes count towards your study time on that date.")


# ---------- settings ----------
def save_hours():
    log_data()["hours"] = {"weekday": round(st.session_state.hours_weekday * 60),
                           "weekend": round(st.session_state.hours_weekend * 60)}
    remake_today()
    save_log()


def add_day_off():
    days_off = set(log_data().get("days_off", []))
    days_off.add(st.session_state.day_off_pick.isoformat())
    log_data()["days_off"] = sorted(days_off)
    remake_today()
    save_log()


def remove_day_off(day_text):
    log_data()["days_off"] = [d for d in log_data().get("days_off", []) if d != day_text]
    remake_today()
    save_log()


def save_goals(new_goals):
    """Saves your deadlines when they can be planned; otherwise keeps the old ones and says why."""
    problem = plans.deadline_problem(new_goals)
    if problem:
        st.session_state.deadline_problem = problem
        return
    log_data()["deadlines"] = sorted(new_goals, key=lambda goal: plans.LEVELS.index(goal["level"]))
    remake_today()
    save_log()


def change_deadline(n):
    changed = [dict(goal) for goal in goals()]  # dict(goal) copies, so a refused change leaves no trace
    changed[n]["date"] = st.session_state[f"deadline_date_{n}"].isoformat()
    save_goals(changed)


def remove_deadline(n):
    save_goals([goal for k, goal in enumerate(goals()) if k != n])


def add_deadline():
    save_goals(goals() + [{"level": st.session_state.deadline_new_level,
                           "date": st.session_state.deadline_new_date.isoformat()}])


def deadlines_settings(today):
    st.subheader("Deadlines")
    st.caption("Finish everything up to a level by a date: its PDFs, exercises and mock exams. The themed "
               "word lists go with your last deadline. Changing a deadline makes today's list again.")
    if st.session_state.get("deadline_problem"):
        st.error(st.session_state.pop("deadline_problem"))
    every = phases()
    for n, (goal, phase) in enumerate(zip(goals(), every)):
        widget_key = f"deadline_date_{n}"
        st.session_state[widget_key] = phase["end"]  # always show what is saved
        c = st.columns([2.2, 1.6, 1], vertical_alignment="bottom")
        c[0].markdown(f"🏁 **{phase['goal']}**  \n{' · '.join(phase['levels'])}")
        c[1].date_input("Date", key=widget_key, on_change=change_deadline, args=(n,), format="DD/MM/YYYY")
        c[2].button("Remove", key=f"deadline_remove_{n}", on_click=remove_deadline, args=(n,),
                    disabled=len(every) == 1)
    free = [level for level in plans.LEVELS if level not in {goal["level"] for goal in goals()}]
    if free:
        c = st.columns([2.2, 1.6, 1], vertical_alignment="bottom")
        c[0].selectbox("Add a deadline for", free, index=len(free) - 1, key="deadline_new_level")
        c[1].date_input("Date", value=every[-1]["end"] + timedelta(days=30), min_value=today,
                        key="deadline_new_date", format="DD/MM/YYYY")
        c[2].button("Add", key="deadline_add", on_click=add_deadline)


def settings_section(plan, shares, finished, today):
    deadlines_settings(today)

    st.subheader("Study time per day")
    c = st.columns(2)
    c[0].number_input("Monday to Friday (hours)", 0.0, 12.0, value=hours()["weekday"] / 60, step=0.5,
                      key="hours_weekday", on_change=save_hours)
    c[1].number_input("Saturday and Sunday (hours)", 0.0, 12.0, value=hours()["weekend"] / 60, step=0.5,
                      key="hours_weekend", on_change=save_hours)
    st.caption("Your goals are PDFs and exercises, not hours. These hours set how the work is shared between "
               "weekdays and the weekend, and give the time estimate on the Today page. Changing them makes "
               "today's list again.")
    phase = current_phase(today)
    load = plan["load"].get(phase["name"])
    if load and load > 1.05:
        st.warning(f"What is left for {phase['goal']} takes about {load:.0%} of these hours, by my estimate. "
                   "The lists still fit the deadline, but the days will feel longer than this.")

    st.subheader("Days off")
    with st.container(horizontal=True, vertical_alignment="bottom"):
        last = max(today, phases()[-1]["end"])  # max(): also when your last deadline has passed
        st.date_input("Day", value=today, min_value=min(today, phases()[0]["start"]), max_value=last,
                      key="day_off_pick")
        st.button("Add day off", key="day_off_add", on_click=add_day_off)
    days_off = log_data().get("days_off", [])
    if days_off:
        for day_text in days_off:
            c = st.columns([3, 1], vertical_alignment="center")
            c[0].markdown(f"🌴 {long_date(date.fromisoformat(day_text))} {day_text[:4]}")
            c[1].button("Remove", key=f"day_off_remove_{day_text}", on_click=remove_day_off, args=(day_text,))
    else:
        st.caption("None yet. Christmas Day and New Year's Day might be good ones.")

    with st.expander("How the plan is made"):
        st.markdown(
            "- **Goals:** each day has a list of PDFs to read and exercises to finish. An exercise is one "
            "exercise type of a PDF (like *Words, Spanish to English*) or of a themed list, finished when "
            "every question was answered once, or when you marked it as done.\n"
            "- **Order:** for each PDF, first read it, then its exercises. Mock exam 1 of a level comes after "
            "its last PDF, no. 2 halfway through the next level. The last level before each deadline has "
            "them after PDF 7 and at the end. The themed lists are spread over the part before your last "
            "deadline, up to its level.\n"
            "- **Deadlines:** " + "; ".join(p["goal"] for p in phases()) + ". From C1 on, the plan also "
            "has an hour of writing practice on weekdays.\n"
            "- **Every morning:** the plan starts from where you are and spreads what is left over the days "
            "to the deadline, weekdays getting more than the weekend. Today's list is fixed the first time "
            "you open it, so it doesn't change while you work through it.\n"
            "- **Estimates:** 2 to 5 minutes per page, 5 to 40 seconds per question depending on the type, plus "
            "extra for the repeats in the rounds. A mock exam counts as 2.5 to 5 hours including checking it.\n"
            "- **Study time:** counted from your answers and page turns. A pause of more than 3 minutes "
            "(10 while reading) counts as a break.")


# ---------- the row on the home screen ----------
def home_row():
    today = clock.today()
    plan, shares, finished = current_state(today)
    if day_rows(plan).get(today) is None:
        return
    log = log_data()
    goal = goal_units(today)
    reads = [u["id"] for u in goal if u["kind"] == "read"]
    exercises = [u["id"] for u in goal if u["kind"] == "exercise"]
    studied = study_log.studied_minutes(log, today.isoformat())
    c = st.columns([4, 1.5], vertical_alignment="center")
    if not goal:
        c[0].markdown(f"**🗓️ Today:** nothing on your list · {fmt(studied)} studied")
    else:
        c[0].markdown(f"**🗓️ Today:** {study_log.finished_by(log, exercises, today.isoformat())} of "
                      f"{len(exercises)} exercises · {study_log.finished_by(log, reads, today.isoformat())} of "
                      f"{len(reads)} PDFs read · {fmt(studied)} studied")
    c[1].button("Open schedule", key="home_schedule", on_click=go_view, args=("schedule",), width="stretch")
