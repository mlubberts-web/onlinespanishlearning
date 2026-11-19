"""Builds your study plan: which PDFs to read and which exercises to finish on each day, until
your last deadline. No screens in this file.

How it works:
1. Make a list of 'units' in the order you do them: read a PDF, then each of its exercise types
   (one unit each), the official mock exams, and the themed word lists (one unit per list and
   exercise type).
2. Estimate the minutes of each unit from its pages and questions. Only used to spread the work
   fairly, because a goal is a number of PDFs and exercises, not a number of hours.
3. Every day the plan starts again from where you are: what is left before a deadline is spread
   over the days left until it, weekdays getting more than weekend days (your hours in Settings
   set that balance). Work ahead and the coming days get lighter; fall behind and they get heavier.
4. Today's list is fixed the first time you look at it (see study_log.py), so it doesn't shrink
   while you work through it.

Like a MATLAB struct array, the plan is a list of dicts: one dict per day.
"""
from datetime import date, timedelta

from practice_items import MODES

# Estimated seconds for one question of each exercise type, the first time you answer it.
SECONDS = {"gender": 5, "words": 12, "reverse": 12, "verbs": 12, "fill": 20, "build": 25,
           "listen": 25, "translate": 40, "fix": 40}
# Extra time for the questions you have to repeat in the rounds: harder levels need more.
RETRY = {"A1": 1.05, "A2": 1.1, "B1": 1.15, "B2": 1.25, "C1": 1.4, "C2": 1.5, "themes": 1.2}
READ_MINUTES = {"A1": 2, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 5}  # per page
# An official mock exam including checking it; the higher levels have longer exams.
MOCK_MINUTES = {"A1": 150, "A2": 150, "B1": 240, "B2": 240, "C1": 300, "C2": 300}
REVIEW_MINUTES = 20
DEFAULT_HOURS = {"weekday": 240, "weekend": 120}  # minutes per day
MODE_ORDER = [mode for mode, _, _ in MODES]  # the exercise types in the order of the practice screen

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
WRITING_MINUTES = 60  # writing practice per weekday while you work on C1 or C2 (half at the weekend)

# Your deadlines: finish everything up to a level by a date. Each person sets their own on the
# Schedule screen (saved in study_log 'deadlines'); these are used until they do.
DEFAULT_GOALS = [{"level": "B2", "date": "2026-12-04"}, {"level": "C2", "date": "2027-01-20"}]
DEFAULT_START = date(2026, 11, 7)


def level_names(levels, from_start):
    """The short name of a phase: 'B2' for A1 to B2 (you reach B2), 'C1/C2', or 'B1–C1'."""
    if from_start or len(levels) == 1:
        return levels[-1]
    return "/".join(levels) if len(levels) == 2 else f"{levels[0]}–{levels[-1]}"


def make_phases(goals, start):
    """Turns the deadlines into phases: the levels to finish before each deadline, from start on.
    goals: [{"level": "B2", "date": "2026-12-04"}, ...], from low to high level, dates in the same order.
    The themed word lists go into the last phase, only the lists up to its level; writing practice
    into the phases with C1 or C2."""
    phases, first = [], 0
    for n, goal in enumerate(goals):
        last = LEVELS.index(goal["level"])
        levels = LEVELS[first:last + 1]
        end = date.fromisoformat(goal["date"])
        name = level_names(levels, first == 0)
        phases.append({"name": name, "goal": f"{name.replace('/', ' and ')} by {end.day} {end:%B}",
                       "start": start, "end": end, "levels": levels,
                       "themes": n == len(goals) - 1, "themes_up_to": goal["level"],
                       "writing": WRITING_MINUTES if {"C1", "C2"} & set(levels) else 0})
        start, first = end + timedelta(days=1), last + 1
    return phases


def deadline_problem(goals):
    """None when the deadlines can be planned, else what is wrong, in words."""
    if not goals:
        return "Keep at least one deadline."
    goals = sorted(goals, key=lambda goal: LEVELS.index(goal["level"]))  # from low to high level
    levels = [LEVELS.index(goal["level"]) for goal in goals]
    dates = [goal["date"] for goal in goals]
    if len(set(levels)) < len(levels):
        return "Each level can have only one deadline."
    if sorted(dates) != dates or len(set(dates)) < len(dates):
        return "A higher level needs a later date."
    return None


# B2 has to be finished by the end of 4 December, so you are at B2 level on 5 December.
PHASES = make_phases(DEFAULT_GOALS, DEFAULT_START)
FIRST_DAY, LAST_DAY = PHASES[0]["start"], PHASES[-1]["end"]  # of these example deadlines


def practise_minutes(questions, level):
    """Estimated minutes for a list of exercise types, one per question: ['words', 'words', 'fill']."""
    return sum(SECONDS[mode] for mode in questions) * RETRY[level] / 60


def new_unit(kind, key, title, minutes, level, **extra):
    """One unit. '**extra' takes any other named values, such as pdf_id=..."""
    return {"id": f"{kind}:{key}", "kind": kind, "title": title, "minutes": max(1, round(minutes)),
            "level": level, **extra}


def mock_unit(level, number):
    return new_unit("mock", f"{level}:{number}", f"Official DELE {level} mock exam no. {number}",
                    MOCK_MINUTES[level], level, number=number)


def exercise_units(source, name, items, level, **extra):
    """One unit per exercise type that has questions, in the order of the practice screen.
    The id ends in the same text as done_key in practice_logic.py, plus the type."""
    units = []
    for mode in MODE_ORDER:
        questions = [item["mode"] for item in items if item["mode"] == mode]
        if questions:
            units.append(new_unit("exercise", f"{source}|{mode}", name, practise_minutes(questions, level),
                                  level, mode=mode, questions=len(questions), **extra))
    return units


def make_units(phase, pdfs, themes):
    """The units of one phase, in the order you do them.
    pdfs:   list of {"id", "level", "number", "title", "pages", "items"}, in catalog order
    themes: list of {"name", "title", "lists": [{"name", "level"}], "items"}
    Mock exam 1 of a level comes after its last PDF and no. 2 halfway through the next level,
    so there is time to work on what went wrong. The last level of a phase has its first mock
    after PDF 7 and its second at the very end."""
    levels = phase["levels"]
    by_level = {level: [p for p in pdfs if p["level"] == level] for level in levels}
    after = {}  # PDF id -> the units that follow that PDF

    def put(pdf_id, unit):
        after.setdefault(pdf_id, []).append(unit)

    end = []
    for n, level in enumerate(levels):
        own = by_level[level]
        if n + 1 < len(levels):
            following = by_level[levels[n + 1]]
            put(own[-1]["id"], mock_unit(level, 1))
            put(following[min(4, len(following) - 1)]["id"], mock_unit(level, 2))
        else:
            put(own[min(6, len(own) - 1)]["id"], mock_unit(level, 1))
            end.append(mock_unit(level, 2))

    phase_pdfs = [p for level in levels for p in by_level[level]]
    top = LEVELS.index(phase.get("themes_up_to", "C2"))

    def wanted(part):
        """Only the lists up to the level of the last deadline; a list without a level always counts."""
        return part.get("level") not in LEVELS or LEVELS.index(part["level"]) <= top

    # {**theme, ...} is a copy of the theme with other lists; the theme itself stays as it was.
    themes = [{**theme, "lists": [part for part in theme["lists"] if wanted(part)]} for theme in themes]
    themes = [theme for theme in themes if theme["lists"]]
    if phase["themes"] and themes:
        # Spread the themed files evenly over the PDFs of this phase, each with all its lists.
        for k, theme in enumerate(themes):
            spot = max(0, int((k + 1) * len(phase_pdfs) / len(themes)) - 1)
            units = []
            for part in theme["lists"]:
                items = [i for i in theme["items"] if i["group"] == part["name"]]
                units += exercise_units(f"THEME_{theme['name']}|list:{part['name']}",
                                        f"{theme['title']} · {part['name']}", items, "themes",
                                        theme=theme["name"], group=part["name"])
            after[phase_pdfs[spot]["id"]] = units + after.get(phase_pdfs[spot]["id"], [])

    result = []
    for pdf in phase_pdfs:
        name = f"{pdf['level']} · {pdf['number']:02d} {pdf['title']}"
        result.append(new_unit("read", pdf["id"], name, pdf["pages"] * READ_MINUTES[pdf["level"]], pdf["level"],
                               pdf_id=pdf["id"], number=pdf["number"], pages=pdf["pages"]))
        result += exercise_units(pdf["id"], name, pdf["items"], pdf["level"], pdf_id=pdf["id"], number=pdf["number"])
        result += after.get(pdf["id"], [])
    return result + end


def all_units(pdfs, themes, phases=PHASES):
    """The units of every phase, each marked with its phase."""
    units = []
    for phase in phases:
        for unit in make_units(phase, pdfs, themes):
            unit["phase"] = phase["name"]
            units.append(unit)
    return units


# ---------- spreading the work over the days ----------
def budget(day, hours, days_off):
    """Minutes you can study on a day: 0 on a day off, otherwise depends on the weekday.
    weekday() gives 0 for Monday up to 6 for Sunday."""
    if day.isoformat() in days_off:
        return 0
    return hours["weekday"] if day.weekday() < 5 else hours["weekend"]


def days_between(first, last):
    return [first + timedelta(days=n) for n in range((last - first).days + 1)]


def day_row(day, phase, hours, days_off):
    total = budget(day, hours, days_off)
    review = min(total, REVIEW_MINUTES)
    writing = phase["writing"] if day.weekday() < 5 else phase["writing"] // 2
    writing = min(total - review, writing)
    # 'room' is the time left for the units; it decides each day's share of the work. At least a
    # quarter of a study day goes to the list, also when review and writing would fill it.
    return {"date": day, "phase": phase["name"], "budget": total, "review": review, "writing": writing,
            "room": max(total - review - writing, total / 4), "units": []}


def spread(units, rows):
    """Puts each unit on one day, so that every day gets a share of the work in proportion to
    its room. A unit goes to the day on which its middle falls, like cutting a long strip of work
    into pieces of the right lengths."""
    rows = [row for row in rows if row["room"] > 0]
    work = sum(unit["minutes"] for unit in units)
    room = sum(row["room"] for row in rows)
    if not rows or not work:
        return
    stretch = room / work  # >1: there is time to spare, <1: the days will be heavier than your hours
    done, index, edge = 0.0, 0, rows[0]["room"]
    for unit in units:
        middle = (done + unit["minutes"] / 2) * stretch
        while middle > edge and index + 1 < len(rows):
            index += 1
            edge += rows[index]["room"]
        rows[index]["units"].append(unit)
        done += unit["minutes"]


def build_plan(units, today, finished, hours=DEFAULT_HOURS, days_off=(), frozen=None, phases=PHASES):
    """Returns {"days": [...], "units": units, "load": {phase: share of your hours needed}, "late": [...]}.
    finished: the ids of the units you finished.
    frozen:   the unit ids of today's list when it was fixed already, else None.
    phases:   from make_phases, with the units' phases.
    Days before today get no units; they are history (see study_log.py)."""
    frozen_ids = set(frozen or [])
    days, load, carry = [], {}, []
    for phase in phases:
        rows = [day_row(day, phase, hours, days_off) for day in days_between(phase["start"], phase["end"])]
        start = today + timedelta(days=1) if frozen is not None else today
        open_rows = [row for row in rows if row["date"] >= start]
        for row in rows:
            if row["date"] == today and frozen is not None:
                row["units"] = [unit for unit in units if unit["id"] in frozen_ids]
        work = carry + [unit for unit in units if unit["phase"] == phase["name"]
                        and unit["id"] not in finished and unit["id"] not in frozen_ids]
        if any(row["room"] > 0 for row in open_rows):
            spread(work, open_rows)
            room = sum(row["room"] for row in open_rows)
            load[phase["name"]] = sum(unit["minutes"] for unit in work) / room
            carry = []
        else:
            carry = work  # the deadline has passed: this work moves to the next phase
        days += rows
    return {"days": days, "units": units, "load": load, "late": carry}


# ---------- where you are ----------
def position(units, finished_dates, day):
    """How far you were at the end of 'day': the first PDF that wasn't finished yet (read and all
    its exercise types). Returns a text like 'A2 · 03', or 'All PDFs done'.
    finished_dates: unit id -> the date text it was finished."""
    last = day.isoformat()
    for unit in units:
        if unit.get("pdf_id") and unit["kind"] in ("read", "exercise"):
            if finished_dates.get(unit["id"], "9999") > last:  # not finished by then
                return f"{unit['level']} · {unit['number']:02d}"
    return "All PDFs done"


def needed_per_day(plan, units, finished, phase_name, today, kind, phases=PHASES):
    """How many units of a kind (read / exercise) you need to finish per study day to make the
    deadline of a phase, counting from today."""
    phase = next(p for p in phases if p["name"] == phase_name)
    names = [p["name"] for p in phases[:phases.index(phase) + 1]]  # this phase and the earlier ones
    left = sum(1 for u in units if u["phase"] in names and u["kind"] == kind and u["id"] not in finished)
    study_days = sum(1 for row in plan["days"] if today <= row["date"] <= phase["end"] and row["room"] > 0)
    return left / study_days if study_days else float(left)


def finish_day(plan, select):
    """The last day with a unit for which select(unit) is True."""
    found = [row["date"] for row in plan["days"] if any(select(unit) for unit in row["units"])]
    return max(found) if found else None
