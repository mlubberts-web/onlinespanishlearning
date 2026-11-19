"""Checks the study plan, the dates you finished things and the study time counting. Run with:
    .venv\\Scripts\\python.exe test_schedule.py
It only reads the PDFs and data files and never changes your own results."""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pymupdf

import practice_store as store
import study_log
import study_plan as plans
from practice_items import build_items, build_theme_items

HERE = Path(__file__).parent
problems = []


def expect(condition, message):
    if not condition:
        problems.append(message)


# ---------- the real PDFs and themes, as the Schedule screen gets them ----------
catalog = json.loads((HERE / "data" / "catalog.json").read_text(encoding="utf-8"))
pdfs = []
for pdf in catalog:
    with pymupdf.open(HERE / "static" / "pdfs" / pdf["file"]) as doc:
        pages = doc.page_count
    document = json.loads((HERE / "data" / "content" / pdf["content"]).read_text(encoding="utf-8"))
    pdfs.append({"id": pdf["id"], "level": pdf["level"], "number": pdf["number"], "title": pdf["title"],
                 "pages": pages, "items": build_items(pdf["id"], document)})
themes = []
for path in sorted((HERE / "data" / "themes").glob("*.json")):
    theme = json.loads(path.read_text(encoding="utf-8"))
    themes.append({"name": path.stem, "title": theme["title"],
                   "lists": [{"name": part["name"], "level": part["level"]} for part in theme["lists"]],
                   "items": build_theme_items(path.stem, theme)})

# ---------- the units ----------
units = plans.all_units(pdfs, themes)
ids = [u["id"] for u in units]
expect(len(set(ids)) == len(ids), "two units with the same id")
expect(sum(u["kind"] == "read" for u in units) == len(pdfs), "every PDF needs a reading unit")
expect(sum(u["kind"] == "mock" for u in units) == 12, "there must be 12 mock exams")
pdf_exercises = sum(len({i["mode"] for i in pdf["items"]}) for pdf in pdfs)
theme_exercises = sum(len({(i["group"], i["mode"]) for i in theme["items"]}) for theme in themes)
expect(sum(u["kind"] == "exercise" for u in units) == pdf_exercises + theme_exercises,
       "every exercise type of every PDF and themed list needs a unit")
for level in ["A1", "A2", "B1", "B2", "C1", "C2"]:
    expect(ids.index(f"mock:{level}:1") < ids.index(f"mock:{level}:2"), f"{level}: mock 1 should come first")
expect(ids.index("mock:B2:2") < ids.index("read:" + next(p["id"] for p in pdfs if p["level"] == "C1")),
       "all B2 mocks belong before C1")
for pdf in pdfs:
    own = [n for n, u in enumerate(units) if u.get("pdf_id") == pdf["id"] and u["kind"] == "exercise"]
    expect(own and ids.index(f"read:{pdf['id']}") < min(own), f"{pdf['id']}: reading should come before its exercises")
example = next(u for u in units if u["kind"] == "exercise" and u.get("pdf_id"))
expect(example["id"] == f"exercise:{example['pdf_id']}|{example['mode']}", "the exercise id must match done_key + type")


def check_plan(plan, today, finished, label):
    """Things that must hold for every plan: each unfinished unit once, nothing in the past,
    and each phase before its deadline."""
    placed = [u["id"] for row in plan["days"] for u in row["units"]]
    expect(len(placed) == len(set(placed)), f"{label}: a unit is planned twice")
    wanted = {u["id"] for u in units if u["id"] not in finished}
    expect(set(placed) >= wanted, f"{label}: {len(wanted - set(placed))} units are not planned")
    expect(not [row for row in plan["days"] if row["date"] < today and row["units"]], f"{label}: units in the past")
    for row in plan["days"]:
        phase = next(p for p in plans.PHASES if p["name"] == row["phase"])
        expect(all(u["phase"] == phase["name"] for u in row["units"]) or plan["late"] or row["date"] > plans.PHASES[0]["end"],
               f"{label}: {row['date']} has a unit of another phase")
    for phase in plans.PHASES:
        last = plans.finish_day(plan, lambda unit: unit["phase"] == phase["name"])
        expect(last is None or last <= phase["end"] or phase is not plans.PHASES[-1] and today > phase["end"],
               f"{label}: {phase['name']} ends {last}, after its deadline")


# ---------- from the very first day, nothing done ----------
start = plans.FIRST_DAY
plan = plans.build_plan(units, start, set())
check_plan(plan, start, set(), "first day")
rows = {row["date"]: row for row in plan["days"]}
expect(rows[date(2026, 11, 9)]["budget"] == 240 and rows[date(2026, 11, 7)]["budget"] == 120,
       "a Monday should have 4 hours and a Saturday 2")
expect(len(plan["days"]) == (plans.LAST_DAY - plans.FIRST_DAY).days + 1, "the plan should cover every day once")
weekday = sum(u["minutes"] for u in rows[date(2026, 11, 10)]["units"])
weekend = sum(u["minutes"] for u in rows[date(2026, 11, 14)]["units"])
expect(weekday > weekend, f"a weekday should get more work than a Saturday ({weekday} / {weekend} minutes)")
expect(not [u for row in plan["days"] if row["date"] > plans.PHASES[0]["end"] for u in row["units"]
            if u["phase"] == "B2"], "B2 work after 4 December")

# ---------- later on, with A1 finished: the plan starts from where you are ----------
today = date(2026, 11, 20)
a1 = {u["id"] for u in units if u["level"] == "A1"}
plan = plans.build_plan(units, today, a1)
check_plan(plan, today, a1, "20 November")
expect(not [u for row in plan["days"] for u in row["units"] if u["id"] in a1], "finished units must not be planned")
today_ids = [u["id"] for u in {r["date"]: r for r in plan["days"]}[today]["units"]]
expect(today_ids, "today should have a list")
frozen_plan = plans.build_plan(units, today, a1, frozen=today_ids)
frozen_rows = {r["date"]: r for r in frozen_plan["days"]}
expect([u["id"] for u in frozen_rows[today]["units"]] == today_ids, "a fixed list must stay as it was")
later = [u["id"] for r in frozen_plan["days"] if r["date"] > today for u in r["units"]]
expect(not set(later) & set(today_ids), "the units of today's list must not come back on later days")
ahead = plans.build_plan(units, today, a1 | set(today_ids))
expect(len({r["date"]: r for r in ahead["days"]}[today + timedelta(days=3)]["units"]) <=
       len(rows.get(today + timedelta(days=3), {"units": []})["units"]) + 50, "working ahead can't make days heavier")

# ---------- days off, too few hours, a deadline that has passed ----------
days_off = {"2026-12-24", "2026-12-25", "2026-12-31", "2027-01-01"}
plan_off = plans.build_plan(units, start, set(), days_off=days_off)
check_plan(plan_off, start, set(), "days off")
expect(all(not row["units"] for row in plan_off["days"] if row["date"].isoformat() in days_off), "a day off should be empty")
little = plans.build_plan(units, start, set(), hours={"weekday": 60, "weekend": 30})
check_plan(little, start, set(), "one hour a day")
expect(little["load"]["B2"] > 1, "one hour a day can't be enough, so the load should be over 100%")
december = date(2026, 12, 10)
late_plan = plans.build_plan(units, december, set())
b2_left = [u for r in late_plan["days"] for u in r["units"] if u["phase"] == "B2"]
expect(b2_left and min(r["date"] for r in late_plan["days"] if any(u["phase"] == "B2" for u in r["units"])) >= december,
       "B2 work left after its deadline should move to the coming days")

# ---------- where you are ----------
first_read = next(u for u in units if u["kind"] == "read")
expect(plans.position(units, {}, start) == f"{first_read['level']} · {first_read['number']:02d}", "nothing done: the first PDF")
a1_dates = {unit_id: "2026-11-10" for unit_id in a1}
expect(plans.position(units, a1_dates, date(2026, 11, 9)).startswith("A1"), "before finishing A1 you were in A1")
expect(plans.position(units, a1_dates, date(2026, 11, 10)) == "A2 · 01", "after finishing A1 you are at A2 · 01")

# ---------- the dates you finished things, and the daily lists ----------
log = {}
study_log.update_finished(log, {"read:x", "exercise:x|words"}, "2026-11-12", {"read:x": "2026-11-08"})
expect(log["finished"] == {"read:x": "2026-11-08", "exercise:x|words": "2026-11-12"}, f"first time: estimates, {log}")
study_log.update_finished(log, {"read:x", "exercise:x|words", "read:y"}, "2026-11-13", {"read:y": "2026-11-01"})
expect(log["finished"]["read:y"] == "2026-11-13", "after the first time, a newly finished unit gets today's date")
study_log.update_finished(log, {"read:x", "read:y"}, "2026-11-13")
expect("exercise:x|words" not in log["finished"], "a unit that isn't finished any more is forgotten")
log["goals"] = {"2026-11-12": ["read:x"], "2026-11-13": ["read:y", "read:z"], "2026-11-14": []}
expect(study_log.goal_reached(log, "2026-11-12") and not study_log.goal_reached(log, "2026-11-13"), "goal reached wrongly")
expect(study_log.goal_reached(log, "2026-11-14") is None, "an empty list is no goal")
expect(study_log.streak(log, "2026-11-14") == 0, "an unfinished list ends the streak")
log["finished"]["read:z"] = "2026-11-13"
expect(study_log.streak(log, "2026-11-14") == 2, "two finished lists in a row, a day without a list doesn't count")
expect(store.last_answer_date({"last_ok": True, "box_before": 1, "due": "2026-11-10"}) == "2026-11-07",
       "a right answer in box 1 came back after 3 days")
expect(store.last_answer_date({"last_ok": False, "due": "2026-11-10"}) == "2026-11-09", "a wrong answer comes back after 1 day")

# ---------- counting study time ----------
log = {}
begin = datetime(2026, 11, 9, 10, 0, 0)
study_log.add_activity(log, "answer", begin)                              # first one: 20 seconds
study_log.add_activity(log, "answer", begin + timedelta(seconds=30))      # +30
study_log.add_activity(log, "page", begin + timedelta(seconds=90))        # +60
study_log.add_activity(log, "answer", begin + timedelta(seconds=490))     # +400, a page may take 10 minutes
study_log.add_activity(log, "answer", begin + timedelta(seconds=1000))    # 510 after an answer: a break, +20
entry = log["days"]["2026-11-09"]
expect(entry["seconds"] == 20 + 30 + 60 + 400 + 20, f"study time counted wrongly: {entry['seconds']}")
expect(entry["answers"] == 4 and entry["pages"] == 1, "answers and pages counted wrongly")
study_log.tick_block(log, "2026-11-09", "writing", 60)
study_log.save_mock(log, "B1", 1, "2026-11-09", 200, {"Reading": 80}, "")
expect(round(study_log.studied_minutes(log, "2026-11-09")) == round(530 / 60 + 60 + 200), "studied minutes are wrong")
study_log.tick_block(log, "2026-11-09", "writing", 60)
expect("writing" not in log["days"]["2026-11-09"]["blocks"], "ticking twice should untick")
study_log.save_mock(log, "B1", 1, "2026-11-10", 180, {"Reading": 90}, "")
expect(len(log["mocks"]) == 1 and log["mocks"][0]["date"] == "2026-11-10", "saving a mock again should replace it")

# ---------- first tries and mastered, for the Progress tab ----------
log = {}
study_log.add_result(log, True, "2026-11-12")
study_log.add_result(log, False, "2026-11-12")
study_log.add_result(log, False, "2026-11-12")
study_log.overrule_result(log, "2026-11-12")
entry = log["days"]["2026-11-12"]
expect((entry["first_right"], entry["first_total"]) == (2, 3), f"first tries counted wrongly: {entry}")
study_log.overrule_result(log, "2026-11-12")
study_log.overrule_result(log, "2026-11-12")
expect(entry["first_right"] == 3, "more right than tries is impossible")
expect(study_log.remember_mastered(log, "2026-11-12", 50) and not study_log.remember_mastered(log, "2026-11-12", 50),
       "the same mastered count twice is no change")

# ---------- your own deadlines ----------
expect([(p["name"], p["goal"], p["levels"], p["writing"], p["themes"]) for p in plans.PHASES] ==
       [("B2", "B2 by 4 December", ["A1", "A2", "B1", "B2"], 0, False),
        ("C1/C2", "C1 and C2 by 20 January", ["C1", "C2"], 60, True)], "the example deadlines changed")
expect(plans.PHASES[1]["start"] == date(2026, 12, 5), "a phase starts the day after the deadline before it")
expect(plans.deadline_problem([]) and plans.deadline_problem([{"level": "B1", "date": "2027-05-01"},
                                                             {"level": "A2", "date": "2027-06-01"}]),
       "a lower level with a later date must be refused")
expect(plans.deadline_problem([{"level": "A2", "date": "2027-05-01"}, {"level": "A2", "date": "2027-06-01"}]),
       "two deadlines for one level must be refused")
expect(plans.deadline_problem([{"level": "B1", "date": "2027-06-01"}, {"level": "A2", "date": "2027-03-01"}]) is None,
       "deadlines in any order are fine when the dates follow the levels")
# Someone who only wants B1, with A2 first: a plan of A1 to B1, themed lists only up to B1.
small = plans.make_phases([{"level": "A2", "date": "2027-03-01"}, {"level": "B1", "date": "2027-06-01"}],
                          date(2027, 1, 10))
expect([p["name"] for p in small] == ["A2", "B1"] and small[1]["levels"] == ["B1"], f"phases wrong: {small}")
small_units = plans.all_units(pdfs, themes, small)
expect({u["level"] for u in small_units if u["kind"] != "exercise" or u.get("pdf_id")} == {"A1", "A2", "B1"},
       "only A1 to B1 belong in this plan")
theme_levels = {(t["name"], part["name"]): part["level"] for t in themes for part in t["lists"]}
expect(all(theme_levels[(u["theme"], u["group"])] in ("A1", "A2", "B1") for u in small_units if u.get("theme")),
       "themed lists above B1 don't belong in this plan")
expect(sum(u["kind"] == "mock" for u in small_units) == 6, "A1, A2 and B1 have 6 mock exams")
small_plan = plans.build_plan(small_units, date(2027, 1, 10), set(), phases=small)
expect(small_plan["days"][-1]["date"] == date(2027, 6, 1) and not small_plan["late"], "the plan should end on 1 June")
expect(all(u["phase"] == "A2" for row in small_plan["days"] if row["date"] <= date(2027, 3, 1) for u in row["units"]),
       "nothing of B1 before the A2 deadline")

if problems:
    print(f"{len(problems)} PROBLEMS:")
    for problem in problems[:40]:
        print(" -", problem)
else:
    per_day = [len(r["units"]) for r in plans.build_plan(units, date.today(), set())["days"] if r["units"]]
    print(f"All good: {len(units)} units ({sum(u['kind'] == 'exercise' for u in units)} exercises), "
          f"on average {sum(per_day) / len(per_day):.1f} a day, nothing over the deadlines.")
