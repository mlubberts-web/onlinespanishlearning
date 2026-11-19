# Spanish Learning Program

A local study app for learning Spanish from Spain, from beginner level up to DELE C2. It combines
59 study PDFs with a reader, progress tracking and about 11,000 practice questions.

Built with Python and [Streamlit](https://streamlit.io) as my first GitHub project, while learning
Python. The study material was written by me together with Claude.

![Home screen with progress for each level](docs/screenshots/home.png)

## What it does

**Read:** 59 PDFs (373 pages) across levels A1 to C2, sharp at any zoom, with the arrow keys to turn
pages. The app remembers where you stopped.

**Practise:** every PDF has its own practice session, with these exercise types where the PDF has
the material for them. After each session a short summary follows, and Enter starts the next type
in this order, from recognising words to producing whole sentences. After the last type, Enter
opens the next PDF.

| Exercise | What you do |
|---|---|
| 🔄 Words, Spanish to English | See the Spanish, type the English |
| ⚖️ el or la? | Choose the article of a noun, with the E and L keys |
| 🔤 Words, English to Spanish | See the English, type the Spanish |
| 🔁 Verb forms | Type the form for a given verb, person and tense |
| 📝 Grammar exercises | Type the missing part of a sentence; in the 25 PDFs about verbs also about 20 sentences in which the context tells you which form you need |
| 🧩 Build the sentence | Click the words in the right order |
| 🎧 Listening | Hear a sentence, type what you hear |
| 🔍 Fix the mistake | Correct a wrong sentence and see why it was wrong |
| 💬 Translate sentences | Type the whole sentence in Spanish |
| 🎯 Mixed test | All of the above mixed together, started by hand |

A session has all questions of a type, or 10 or 20 if you are short of time.

Each exercise card has a "Mark as done" checkbox, and each themed list one as well, for exercises
you have finished elsewhere or don't need. A marked exercise counts as mastered in your progress
and as finished in the Schedule, and the automatic next step skips it.

**Remember it:**

- **Rounds:** you see everything once, then only what you got wrong until all of it is correct, and
  then the same again for what you missed the first time.
- **Daily review:** questions come back after 1, 3, 7 and 30 days, and a wrong answer brings a
  question back the next day.
- **Mastered:** a question counts as mastered when your last first try at it was right: the first
  time it came up in a session, not after the repeats. Wrong on Monday and right straight away on
  Tuesday counts.
- **Weak questions:** what you often get wrong is chosen more often and can be practised separately.
  Mastered questions are chosen 10 times less often.
- **Skip what I know:** a switch above the exercises that leaves out your mastered questions
  altogether. The daily review still brings them back.
- **Weak subjects:** the home and level screens list the PDFs and themed lists where less than 70%
  of what you practised was right on the first try (once you practised 10 of its questions), with
  a button to practise their weak questions. A line above them gives the same score per exercise
  type, so you can see which skill needs work.

**Plan it:** the 🗓️ Schedule screen turns everything above into a daily goal up to your own
deadlines, such as all of A1 to B2 by 4 December and C1 and C2 by 20 January. You choose the levels
and dates in its Settings; a plan can also stop at a lower level, for example B1. The goal
is a list of PDFs to read and exercises to finish, where an exercise is one exercise type of a PDF
or a themed list. Every morning the plan starts again from where you are and spreads what is left
over the days to the deadline, so working ahead makes the coming days lighter. It shows:

- **Today:** your list with a button for each PDF and exercise, the daily review, and your streak.
- **Coming days:** the forecast of the lists for the days ahead.
- **Total:** what is left for each deadline, your expected finish date at your current pace,
  progress per level, and a calendar coloured by how much of each day's list you finished.
- **Mock exams:** 12 official DELE model exams, two per level, with your score for each part.
- **Settings:** your deadlines, your hours per day (which only set the balance between weekdays and
  the weekend) and your days off.

The app times your study from your answers and page turns, and you can add time you studied
elsewhere.

**Look back:** the 📊 Progress tab shows your totals, where you are in the program, and:

- **Week by week:** any week back to your first day, with the hours per day, exercises and PDFs
  finished, questions answered, the share right on the first try, the change against the week
  before, where you were at the start and end of the week, and a list of what you finished.
- **Trends:** hours, exercises, questions and first-try accuracy per week, questions mastered over
  time, and a table of all weeks.
- **Levels:** PDFs read, exercises finished and questions mastered per level.
- **Mock exams** and **weak subjects**.

**Word lists:** 32 themed files with about 2,400 words and phrases, split into lists of 12 to 30
with a level each:

- **Topics:** 22 subjects people talk about, from food and travel to politics, law, science and
  paperwork in Spain.
- **Useful language:** 10 files of the words that hold a text together, such as connectors, phrases
  for speaking and writing, verbs with a preposition, verb phrases, collocations, idioms, false
  friends, ser or estar, and colloquial Spain. Most of these come with an example sentence to
  complete.

**Mock exam:** a timed mix of exercises. It trains exam pressure, but it does not follow the format
of the official DELE exam.

| | |
|---|---|
| ![Choosing el or la](docs/screenshots/gender.png) | ![Themed word lists](docs/screenshots/themes.png) |

### How answers are graded

| What differs from the correct answer | Result |
|---|---|
| Capital letters | 🟢 Ignored |
| ñ written as n, ¿ ? ¡ ! | 🟡 Warning, still counts as correct |
| Missing el / la in vocabulary | 🟡 Warning that names the article |
| Missing accent, outside verb forms | 🟡 Warning, still counts as correct |
| Dots and similar punctuation | 🟢 Ignored |
| Subject pronoun added or left out (yo hablo, hablo) in verb forms, grammar and translation | 🟢 Ignored |
| Grammar markers such as + inf. or + gerundio (tener que, estar) | 🟢 Not needed, shown in the answer |
| Missing accent in a verb form (hablo, habló) | 🔴 Wrong |

Two exceptions: in "Fix the mistake", the exact thing that is the mistake has to be corrected (which
can be a capital), and in the two PDFs about accents, accents have to be right. A wrong pronoun
still counts as wrong: él come is not ella come.

Spanish often allows several correct sentences, so a wrong answer has an "I was actually right"
button. The app then remembers your answer, and it counts as correct from then on, also where the
same question comes back in another PDF or list. The accepted answers are listed under each PDF's
exercises, with a button to remove one you accepted by mistake.

## Run it

Windows only. You need [Python 3.11 or newer](https://www.python.org/downloads/); tick "Add python.exe
to PATH" while installing.

1. Download this project and open its folder.
2. Double-click `start.bat`. The first run installs the packages, which takes about a minute.
3. Your browser opens at http://localhost:8501.

Everything runs on your own computer. Listening needs a Spanish (Spain) voice in your browser, which
Edge and Chrome normally have. If the app warns that it is missing, go to Windows Settings, Time &
language, Speech, Manage voices, Add voices, Spanish (Spain), and restart your browser.

Your results are saved in `progress.json`, `practice.json` and `study_log.json`. Git leaves these
files out on purpose, so copy them somewhere safe to back them up, or use **💾 Your data** in the
sidebar to download a backup.

### Online

The app can also run as a website, so people without Python can use it on any computer, Mac
included. Each person logs in and has their own results, saved in a free online database.
[DEPLOY.md](DEPLOY.md) explains how to set it up.

## How the code is organised

| File | What it does |
|---|---|
| `app.py` | Home screen, level screens and the PDF reader |
| `practice_items.py` | Turns the PDF source data into questions |
| `practice_logic.py` | Checks answers, runs the rounds, chooses the questions |
| `practice_store.py` | Saves results and schedules the daily review |
| `practice_screen.py` | The practice screens |
| `extra_screens.py` | The themed word lists and the mock exam |
| `schedule_screen.py` | The Schedule screen |
| `progress_screen.py` | The Progress tab: your history, trends and levels |
| `study_plan.py` | Makes the daily lists of PDFs and exercises from where you are |
| `study_log.py` | Counts your study time per day, the dates you finished things, the daily lists and your mock exam scores |
| `ui.py` | Small pieces shared between the screens |
| `storage.py` | Saves your results: in files on your own computer, or in the online database |
| `login.py` | The login of the online version |
| `clock.py` | Today's date in each person's own time zone |
| `build_catalog.py` | Rebuilds `data/catalog.json`, only needed after adding PDFs |
| `test_practice.py` | Checks all questions and rules |
| `test_schedule.py` | Checks the plan and the time counting |
| `data/content/` | The source data of each PDF, including the exercises |
| `data/verbs_in_context/` | Sentences per PDF for practising verb forms in context (the format is explained in `practice_items.py`) |
| `data/themes/` | The themed word lists; add a file here to add a theme (the format is explained in `practice_items.py`) |
| `static/pdfs/` | The 59 PDFs |
| `DEPLOY.md` | How to put the app online |

To check that everything still works after a change:

```
.venv\Scripts\python.exe test_practice.py
.venv\Scripts\python.exe test_schedule.py
```
