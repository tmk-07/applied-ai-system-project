"""Offline/live evaluation for Ask PawPal: exercises the same ask() the Streamlit app calls.

Offline mode (default) uses a fake client and never touches the network:

    python3 eval_pawpal_rag.py

Live mode calls real Gemini for the supported cases only (the no-evidence case never
calls the model, so it needs no API key either way), and prints the actual answers so
citations can be checked manually:

    GEMINI_API_KEY=your-key-here python3 eval_pawpal_rag.py --live

Exits 0 if every case passes its assertions, 1 otherwise. Never prints the API key.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from pawpal_rag import NO_EVIDENCE_MESSAGE, GeminiClient, ask, retrieve_notes
from pawpal_system import Pet, Priority, Task, TaskCategory


class FakeGeminiClient:
    """Deterministic stand-in for GeminiClient: no network, no API key, records calls."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        return self.response


class RecordingClient:
    """Wraps any client to count calls without ever touching or printing its credentials."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        return self.inner.generate(prompt)


def _make_dog() -> Pet:
    pet = Pet(name="Rex", species="dog", breed="Labrador", age=3)
    pet.add_task(
        Task(task_id="t1", name="Walk", category=TaskCategory.WALK,
             duration_minutes=30, priority=Priority.HIGH)
    )
    return pet


def _make_cat() -> Pet:
    pet = Pet(name="Luna", species="cat", breed="Tabby", age=2)
    pet.add_task(
        Task(task_id="t1", name="Feed", category=TaskCategory.FEEDING,
             duration_minutes=10, priority=Priority.HIGH)
    )
    return pet


@dataclass
class Case:
    label: str
    pet: Pet
    question: str
    expect_note_id: str | None  # a note id that must be retrieved, or None for no-evidence


CASES: list[Case] = [
    Case("dog (supported)", _make_dog(),
         "How many minutes a day should my adult dog walk?", "walk-dog-1"),
    Case("cat (supported)", _make_cat(),
         "How many meals a day should I feed my cat?", "feeding-cat-1"),
    Case("bicycle (no evidence)", _make_dog(),
         "How do I change a bicycle tire?", None),
    # Paraphrase of the dog case above, with almost no words in common, to check that the
    # IDF-weighted ranking generalizes rather than being tuned to one exact sentence.
    Case("dog paraphrase (generalization check)", _make_dog(),
         "My adult dog is high energy -- how many minutes of walking does he need each day?",
         "walk-dog-1"),
]


def run_case(case: Case, live: bool) -> bool:
    notes = retrieve_notes(case.pet, case.question)
    note_ids = [note.note_id for note in notes]

    if case.expect_note_id is None:
        client = FakeGeminiClient(response="(should never be called)")
        answer = ask(case.pet, case.question, client)
        passed = (
            notes == []
            and client.call_count == 0
            and answer == NO_EVIDENCE_MESSAGE
        )
        outcome = "no-evidence message, 0 model calls"
    else:
        species_ok = all(note.species in (case.pet.species, "any") for note in notes)
        note_found = case.expect_note_id in note_ids

        if live:
            try:
                inner = GeminiClient()
            except RuntimeError as error:
                print(f"[{case.label}] SKIPPED (live mode): {error}")
                return False
            client = RecordingClient(inner)
        else:
            client = RecordingClient(FakeGeminiClient(response=f"Fake answer [{case.expect_note_id}]"))

        answer = ask(case.pet, case.question, client)
        passed = species_ok and note_found and client.call_count == 1
        outcome = answer if live else f"sent {len(notes)} note(s) to client, got fake reply"

    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {case.label}")
    print(f"  species:        {case.pet.species}")
    print(f"  question:       {case.question}")
    print(f"  retrieved notes: {note_ids}")
    if case.expect_note_id is not None:
        irrelevant_count = len(note_ids) - (1 if note_found else 0)
        print(f"  expected note retained: {note_found} ({case.expect_note_id!r})")
        print(f"  irrelevant notes returned: {irrelevant_count}")
    print(f"  outcome:        {outcome}")
    print()
    return passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true",
                         help="Use real Gemini for supported cases (reads GEMINI_API_KEY from env).")
    args = parser.parse_args()

    results = [run_case(case, args.live) for case in CASES]

    total, passed = len(results), sum(results)
    print(f"{passed}/{total} cases passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
