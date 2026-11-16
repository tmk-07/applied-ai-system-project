# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Implementation Summary

PawPal+ models pet care scheduling with four cooperating classes in `pawpal_system.py`:

- **`Task`** holds a single care item (name, category, duration, priority, optional preferred time/recurrence) and tracks its own completion via `mark_done()`.
- **`Pet`** owns a list of `Task` objects and exposes `add_task()`/`remove_task()` to manage them.
- **`Owner`** owns a list of `Pet` objects and can `add_pet()` or roll up every task across all pets with `get_all_tasks()`.
- **`Schedule`** takes a `Pet` and a list of tasks and turns them into a concrete daily plan: `generate_plan()` sorts pending tasks by priority (high → low) and then by preferred time, lays them out sequentially starting at a fixed day-start time, and skips any task that would exceed the available minutes budget. Each placed task becomes a `ScheduleEntry` (start/end time plus a plain-language reason it was placed there). `total_scheduled_minutes()` and `explain_plan()` summarize the result.

`main.py` ties these together end-to-end: it creates an `Owner`, two `Pet`s, assigns three `Task`s with different preferred times, builds a `Schedule` per pet, and prints each pet's schedule for the current date. `app.py` wires the same classes into a Streamlit UI for interactive use.

The UML class diagram in [`diagrams/uml_final.mmd`](diagrams/uml_final.mmd) reflects the final implementation above, including methods added after the initial draft (`Task.create_next_occurrence()`, `Pet.complete_task()`, `Pet.filter_tasks()`, `Owner.filter_tasks()`/`get_tasks_by_pet()`/`detect_conflicts()`, and `Schedule.sort_by_time()`).

## Features

- **Owner & pet management** — create an owner, add any number of pets, and switch between them in the UI (`Owner.add_pet()`, `Pet` dataclass).
- **Task creation** — add tasks with a name, duration, priority, optional preferred time, and optional daily/weekly recurrence.
- **Sorting by time** — `Schedule.sort_by_time()` returns a pet's tasks in chronological order (untimed tasks last); the Streamlit task table always displays in this order.
- **Priority-aware daily scheduling** — `Schedule.generate_plan()` builds a concrete day plan: high-priority tasks are placed first, pending tasks are laid out starting at a fixed day-start time, and anything that would blow the available-minutes budget is skipped. `explain_plan()` prints a plain-language reason for each placement.
- **Filtering** — `Pet.filter_tasks()` / `Owner.filter_tasks()` return just the done or pending tasks for a pet or across an owner's whole household; `Owner.get_tasks_by_pet()` pulls one pet's tasks by name.
- **Daily recurrence** — `Pet.complete_task()` marks a task done and, if it recurs, automatically creates the next occurrence via `Task.create_next_occurrence()` (due one day later for `"daily"`, one week later for `"weekly"`).
- **Conflict warnings** — `Owner.detect_conflicts()` scans every pet's tasks for ones sharing the exact same preferred time and returns warning strings (instead of raising), which the UI renders as `st.warning` banners so a pet owner immediately sees a double-booking.

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

```
Schedule for Luna on 2026-10-24:
- 18:00-18:20 Evening Grooming: Scheduled at its preferred time (Low priority).
Total scheduled: 20/480 minutes.
```

## 🧪 Testing PawPal+

```bash
python -m pytest
```

`tests/test_pawpal.py` covers both happy paths and edge cases for the core scheduling behaviors:

- **Completion**: marking a task done flips `is_done`; adding a task increases a pet's task count.
- **Sorting** (`Schedule.sort_by_time()`): tasks come back in chronological order; untimed tasks sort last; an empty list returns an empty list.
- **Recurrence** (`Pet.complete_task()`, `Task.create_next_occurrence()`): completing a `"daily"` task auto-creates the next occurrence one day later, a `"weekly"` task one week later, and completing a non-recurring task creates nothing.
- **Conflict detection** (`Owner.detect_conflicts()`): two tasks (same pet or different pets) at the same `preferred_time` are flagged, non-overlapping times are not, and a pet with no tasks produces no conflicts.
- **Filtering** (`Pet.filter_tasks()`): tasks can be filtered by completion status or returned unfiltered.

Sample test output:

```
============================= test session starts ==============================
platform darwin -- Python 3.13.5, pytest-8.3.4, pluggy-1.5.0
rootdir: /Users/timmy/ai110-module2show-pawpal-starter
plugins: anyio-4.7.0
collected 12 items

tests/test_pawpal.py::test_mark_done_changes_task_status PASSED          [  8%]
tests/test_pawpal.py::test_adding_task_increases_pet_task_count PASSED   [ 16%]
tests/test_pawpal.py::test_sort_by_time_returns_chronological_order PASSED [ 25%]
tests/test_pawpal.py::test_sort_by_time_places_untimed_tasks_last PASSED [ 33%]
tests/test_pawpal.py::test_sort_by_time_on_empty_list_returns_empty_list PASSED [ 41%]
tests/test_pawpal.py::test_completing_daily_task_creates_next_day_occurrence PASSED [ 50%]
tests/test_pawpal.py::test_completing_weekly_task_creates_occurrence_one_week_later PASSED [ 58%]
tests/test_pawpal.py::test_completing_non_recurring_task_does_not_create_new_task PASSED [ 66%]
tests/test_pawpal.py::test_detect_conflicts_flags_two_tasks_at_the_same_time PASSED [ 75%]
tests/test_pawpal.py::test_detect_conflicts_returns_empty_list_when_no_overlap PASSED [ 83%]
tests/test_pawpal.py::test_detect_conflicts_on_pet_with_no_tasks_returns_empty_list PASSED [ 91%]
tests/test_pawpal.py::test_filter_tasks_by_completion_status PASSED      [100%]

============================== 12 passed in 0.01s ==============================
```

**Confidence Level:** ⭐⭐⭐⭐☆ (4/5) — all core sorting, recurrence, filtering, and conflict-detection behaviors are covered and passing. One star withheld because conflict detection only checks exact time matches rather than overlapping durations (see `reflection.md`, section 2b), and `generate_plan()`'s interaction with the day-end/available-minutes boundary isn't yet covered by a dedicated test.

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Schedule.sort_by_time()` | Sorts a list of `Task` objects by `preferred_time` (formatted as `"HH:MM"` for the sort key); untimed tasks sort last. Separate from `Schedule.generate_plan()`, which sorts by priority first and then by time while building the actual plan. |
| Filtering | `Pet.filter_tasks()`, `Owner.filter_tasks()`, `Owner.get_tasks_by_pet()` | Filter tasks by completion status (`is_done=True`/`False`/`None`) at the pet level or across every pet an owner has, or pull all tasks for one named pet. |
| Conflict handling | `Owner.detect_conflicts()` | Groups pending tasks across all of an owner's pets by exact `preferred_time` and returns a list of warning strings for any time with more than one task — same pet or different pets. Lightweight exact-match check, not full interval overlap (see `reflection.md`, section 2b). |
| Recurring tasks | `Task.create_next_occurrence()`, `Pet.complete_task()` | `Pet.complete_task(task_id)` marks a task done and, if it's recurring (`recurrence="daily"` or `"weekly"`), automatically creates and adds the next occurrence with its `due_date` advanced by `timedelta(days=1)` or `timedelta(weeks=1)`. |

## 🐾 Ask PawPal (RAG + Gemini)

Ask PawPal is a stretch feature built on top of the **Module 2 PawPal+ baseline** described above (the `Owner`/`Pet`/`Task`/`Schedule` classes in `pawpal_system.py`, unchanged by this feature). It answers a pet-care question about the selected pet by retrieving from a small, local, static corpus of care notes (`CARE_NOTES` in `pawpal_rag.py`) and passing only the matched notes to Gemini as evidence. If retrieval finds nothing relevant, the app shows a fixed no-evidence message and **never calls Gemini** — this is enforced in code, not just in the prompt (see the diagram below).

### Setup

```bash
pip install -r requirements.txt          # includes google-genai
export GEMINI_API_KEY=your-key-here      # only needed for live Gemini calls
```

`GEMINI_MODEL` is an optional env var to override the default model (`gemini-3.5-flash-lite`).

### Run commands

```bash
streamlit run app.py                         # interactive UI, "Ask PawPal" section
python3 -m pytest                            # unit tests (never needs an API key)
python3 eval_pawpal_rag.py                   # offline eval, fake client, no network/key needed
GEMINI_API_KEY=your-key-here python3 eval_pawpal_rag.py --live   # live eval, real Gemini calls
```

### How retrieval works

`retrieve_notes()` tokenizes the question and each care note, strips common stopwords ("a", "to", "my", "how", ...), and only keeps a note if it shares at least one real content word with the question. A pet's task categories (e.g. a dog with a "walk" task) can add a small bonus that **reorders** already-relevant notes, but a category match alone can never pull in an unrelated note — this was a real bug, fixed on 2026-11-15 (see `model_card.md` and the "bicycle tire" example below).

### Three real examples

Each example shows the pet, the exact question, which local notes were retrieved, and the outcome. The two supported cases were run twice: once offline against `eval_pawpal_rag.py`'s fake client (labeled **offline/fake**), and once with `--live` against real Gemini (labeled **live/Gemini**) so the actual citation could be checked.

**1. Dog, supported — offline/fake** (`python3 eval_pawpal_rag.py`)
```
species:        dog
question:       How many minutes a day should my adult dog walk?
retrieved notes: ['walk-dog-1', 'feeding-dog-1', 'medication-any-1']
outcome:        sent 3 note(s) to client, got fake reply
```

**1. Dog, supported — live/Gemini** (`GEMINI_API_KEY=... python3 eval_pawpal_rag.py --live`)
```
species:        dog
question:       How many minutes a day should my adult dog walk?
retrieved notes: ['walk-dog-1', 'feeding-dog-1', 'medication-any-1']
outcome:        Adult dogs generally need 20-60 minutes of walking a day, split across
                 1-3 walks, though high-energy breeds may need more [walk-dog-1].
```
Note that `feeding-dog-1` and `medication-any-1` were retrieved alongside the correct note (they share the content word "day" with the question) but Gemini correctly cited only the relevant one, `walk-dog-1`.

**2. Cat, supported — offline/fake**
```
species:        cat
question:       How many meals a day should I feed my cat?
retrieved notes: ['feeding-cat-1', 'walk-cat-1', 'medication-any-1']
outcome:        sent 3 note(s) to client, got fake reply
```

**2. Cat, supported — live/Gemini**
```
species:        cat
question:       How many meals a day should I feed my cat?
retrieved notes: ['feeding-cat-1', 'walk-cat-1', 'medication-any-1']
outcome:        Cats often prefer small, frequent meals, with a common approach being
                 free-feeding dry food combined with 1-2 scheduled wet meals a day
                 [feeding-cat-1].
```
Again, `walk-cat-1` and `medication-any-1` were retrieved (sharing "day") but correctly left uncited.

**3. Bicycle tire, no evidence — offline/fake and live/Gemini give the identical result**, because the no-evidence path never calls the model in either mode:
```
species:        dog
question:       How do I change a bicycle tire?
retrieved notes: []
outcome:        no-evidence message, 0 model calls
```
This is the regression case: a dog with a "walk" task used to get `walk-dog-1` retrieved anyway (via stopword overlap on "a"/"to", not the category bonus), and Gemini would then answer the literal bicycle question using its own general knowledge instead of refusing. See `model_card.md` for the root cause and fix.

### Offline evaluation results (observed)

```
3/3 cases passed.
```

### Test results (observed)

```
============================== 20 passed in 0.02s ==============================
```

### Architecture diagram

[`diagrams/ask_pawpal_flow.mmd`](diagrams/ask_pawpal_flow.mmd) shows the retrieval → no-evidence branch → generation flow, including that the no-evidence branch happens *before* any Gemini call, not as a prompt-only instruction. It also shows where `eval_pawpal_rag.py`'s automated checks validate each branch (offline fake-client assertions and the live-mode call-count assertion), and where human review fits: a person reads the Streamlit answer or the `--live` output, checks that `[note-id]` citations are correct and that irrelevant retrieved notes weren't cited, and records the resulting accept/revise/reject decision in `model_card.md`.

*(The test-harness documentation above — three real examples, offline evaluation results, test results — covers `eval_pawpal_rag.py` as a bonus deliverable in its own right. The section below is a separate, follow-on improvement to the retriever itself.)*

## ⚖️ RAG Enhancement: IDF-weighted ranking

The supported-case examples above show a real, pre-existing limitation: `retrieve_notes()` previously scored a note by raw keyword-overlap count (`2 points per shared content word` + a flat `+1` task-category bonus), so a note sharing only a common word like "day" — which appears in 5 of the 9 care notes — scored the same per word as a note sharing a word that's actually specific to one topic. This let generic notes crowd into the result set and rank closer to the true match than they should.

**The fix (`pawpal_rag.py`):** matched words are now weighted by inverse document frequency (IDF), computed once at import time from `CARE_NOTES` itself — no external library, no dependency beyond the standard-library `math` module. A word's weight is `ln(N / df)`, where `N` is the corpus size (9) and `df` is how many notes contain that word. A word in every note would weight to 0; a word specific to one note weights highest (`ln(9/1) ≈ 2.2`). The task-category bonus (`+0.2`) was kept but shrunk so it stays below the weakest realistic single-word match — it can still only reorder notes that already have real overlap, never admit one with none (unchanged from the earlier fix; still enforced by the `score <= 0: continue` gate before the bonus is applied).

**Before/after, computed directly (not simulated) from the two supported demo questions:**

| Case | Note | Shared words | Old score (flat) | New score (IDF) |
|---|---|---|---|---|
| Dog | `walk-dog-1` (correct) | adult, day, minutes | 7 | **3.80** |
| Dog | `feeding-dog-1` (noise) | adult, day | 4 | 2.09 |
| Dog | `medication-any-1` (noise) | day | 2 | 0.59 |
| Cat | `feeding-cat-1` (correct) | day, meals | 5 | **2.29** |
| Cat | `walk-cat-1` (noise) | day | 2 | 0.59 |
| Cat | `medication-any-1` (noise) | day | 2 | 0.59 |

The separation between the correct note and the weakest noise note grew from **3.5x → 6.5x** (dog) and **2.5x → 3.9x** (cat) — the ranking is meaningfully better at pushing the true match to the top and the generic matches toward the bottom.

**What did *not* change:** the exact set of note IDs returned for the dog and cat cases is identical before and after (`['walk-dog-1', 'feeding-dog-1', 'medication-any-1']` and `['feeding-cat-1', 'walk-cat-1', 'medication-any-1']`) — all three species-eligible notes genuinely share at least one content word with the question, so with `limit=3` all three are still returned either way. The improvement here is in ranking/score separation, not in raw selection count for these two cases; an honest comparison needs to say so rather than imply fewer notes came back.

**Generalization check (new, not the demo wording):** to confirm the IDF weighting isn't just tuned to the two exact demo sentences, a differently-worded dog question was added — *"My adult dog is high energy -- how many minutes of walking does he need each day?"* — sharing almost no phrasing with the original ("minutes a day should my adult dog walk"). It still retrieves `walk-dog-1` as a top result:

```
[PASS] dog paraphrase (generalization check)
species:        dog
question:       My adult dog is high energy -- how many minutes of walking does he need each day?
retrieved notes: ['walk-dog-1', 'medication-any-1', 'feeding-dog-1']
expected note retained: True ('walk-dog-1')
irrelevant notes returned: 2
```

**Bicycle case still makes zero model calls**, unchanged by this enhancement (observed directly):

```
[PASS] bicycle (no evidence)
species:        dog
question:       How do I change a bicycle tire?
retrieved notes: []
outcome:        no-evidence message, 0 model calls
```

**Observed results after the enhancement, 2026-11-15:**

```
4/4 cases passed.     # python3 eval_pawpal_rag.py
```
```
20 passed in 0.01s    # python3 -m pytest
```

## 📸 Demo Walkthrough

### Streamlit app (`app.py`)

The UI lets a user:

- Enter an **owner name**, which is kept in `st.session_state` so it survives Streamlit's rerun-on-every-click behavior.
- **Add a pet** (name, species, breed) and switch between pets with a selector once more than one exists.
- **Add a task** for the selected pet, with a title, duration, priority, an optional preferred time, and an optional recurrence (`none`/`daily`/`weekly`).
- See that pet's tasks in a table that is always **sorted by time** (via `Schedule.sort_by_time()`), with status (`✅ done` / `⏳ pending`) and recurrence shown per row.
- **Mark a pending task complete**; if it's recurring, the app confirms the next occurrence was added and shows its new due date.
- **Generate the day's schedule** for the selected pet, which calls `Schedule.generate_plan()` and prints the resulting plan with `explain_plan()`.
- See **conflict warnings** as soon as two tasks (for the same pet, or across different pets) share a preferred time — rendered as `st.warning` banners above the task table, so the owner notices a double-booking before they even generate a schedule, rather than discovering it buried in a schedule printout.

Example workflow: add pet "Mochi" → add a 7:30 AM "Morning walk" task → add a second pet "Milo" → add a 7:30 AM task for Milo too → a conflict warning appears immediately ("Conflict at 07:30: Mochi's Morning walk, Milo's ... are all scheduled at the same time") → generate the schedule for either pet to see it placed and explained.

### CLI demo (`main.py`)

`main.py` builds an owner with two pets, adds tasks out of chronological order (including one recurring daily task and two tasks that intentionally collide at 13:00), then exercises every algorithmic feature end-to-end. Sample output from `python3 main.py`:

```
=== Sorting demo: Rex's tasks sorted by time ===
- 07:30:00: Morning Walk
- 13:00:00: Afternoon Feeding
- 18:00:00: Evening Grooming

=== Recurring task demo ===
Before completing: Morning Walk is_done=False
After completing: Morning Walk is_done=True
Next occurrence auto-created: T1-next-2026-10-27, due 2026-10-27

=== Filtering demo ===
Rex's completed tasks: ['Morning Walk']
Rex's pending tasks: ['Evening Grooming', 'Afternoon Feeding', 'Morning Walk']
All of Luna's tasks: ['Litter Box Cleaning']

=== Conflict detection demo ===
WARNING: Conflict at 13:00: Rex's Afternoon Feeding, Luna's Litter Box Cleaning are all scheduled at the same time.

=== Daily schedule ===
Schedule for Rex on 2026-10-26:
- 07:30-08:00 Morning Walk: Scheduled at its preferred time (High priority).
- 13:00-13:15 Afternoon Feeding: Scheduled at its preferred time (Medium priority).
- 18:00-18:20 Evening Grooming: Scheduled at its preferred time (Low priority).
Total scheduled: 65/480 minutes.

Schedule for Luna on 2026-10-26:
- 13:00-13:10 Litter Box Cleaning: Scheduled at its preferred time (Medium priority).
Total scheduled: 10/480 minutes.
```

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
