"""Few-shot vs. zero-shot prompt experiment for Ask PawPal's Gemini call.

This does NOT change production behavior: `pawpal_rag.build_prompt()` (used by `ask()`
and the Streamlit app) is untouched. This script only adds a second, alternate prompt
builder (`build_prompt_few_shot`) for comparison, and is never imported by the app.

Both prompt variants are built from the SAME retrieved notes (retrieval itself,
`retrieve_notes()`, is unchanged) and sent through the SAME `GeminiClient` (same model,
same settings) for each held-out question, so the prompt wording is the only variable.

The two few-shot examples use `grooming-dog-1` / `grooming-cat-1` and their own made-up
questions, which do not appear anywhere in the held-out test questions below (disjoint
notes, disjoint questions) — the held-out set tests generalization, not memorized
exemplars.

This experiment always makes real Gemini calls (a fake client would answer identically
regardless of prompt wording, which would make the comparison meaningless), so it always
needs GEMINI_API_KEY. It never prints the key.

Run:

    GEMINI_API_KEY=your-key-here python3 fewshot_experiment.py
"""

from __future__ import annotations

import sys

from pawpal_rag import NO_EVIDENCE_MESSAGE, CareNote, GeminiClient, build_prompt, retrieve_notes
from pawpal_system import Pet, Priority, Task, TaskCategory

FEW_SHOT_EXAMPLES = f"""Here are two worked examples of how to answer, in the same format used below.

Example 1 — question answered using a supplied note:
Relevant care notes:
- [grooming-dog-1] Short-haired dogs typically need brushing weekly; long-haired breeds often need it every 1-2 days to prevent matting.
Question: How often does a short-haired dog need brushing?
Answer: Short-haired dogs typically need brushing about once a week [grooming-dog-1].

Example 2 — notes were retrieved, but they don't answer the question:
Relevant care notes:
- [grooming-cat-1] Most cats self-groom well, but weekly brushing reduces shedding and hairballs, more often for long-haired cats.
Question: What shampoo brand is safest for bathing my long-haired cat?
Answer: {NO_EVIDENCE_MESSAGE}

Now answer the real question below, following the same pattern.

"""


def build_prompt_few_shot(pet: Pet, question: str, notes: list[CareNote]) -> str:
    """Same prompt as build_prompt(), with two worked examples inserted before the
    real notes/question. Everything else (instructions, notes_block, question,
    closing instruction) is identical to build_prompt() so the examples are the
    only variable being tested."""
    if notes:
        notes_block = "\n".join(f"- [{note.note_id}] {note.text}" for note in notes)
    else:
        notes_block = "- (no specific local care notes matched this question)"

    return (
        f"You are PawPal, a pet care assistant. Answer the owner's question about their "
        f"{pet.species} named {pet.name} ({pet.breed}), using ONLY the care notes below as your "
        "evidence. Do not use outside knowledge, and do not answer questions unrelated to pet "
        "care (e.g. general how-to topics), even if you know the answer.\n\n"
        f"{FEW_SHOT_EXAMPLES}"
        f"Relevant care notes:\n{notes_block}\n\n"
        f"Question: {question}\n\n"
        "Answer concisely, and cite note ids in brackets, like [note-id], when you rely on one. "
        "If the care notes above do not contain enough information to answer the question, "
        f"reply with exactly this sentence and nothing else: \"{NO_EVIDENCE_MESSAGE}\""
    )


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


# Held-out questions: none of these notes (walk-dog-1, feeding-dog-1, feeding-cat-1,
# medication-any-1) or question wordings appear in FEW_SHOT_EXAMPLES above.
HELD_OUT_CASES = [
    # (label, pet, question, kind)  kind: "supported" or "insufficient"
    ("dog supported", _make_dog(),
     "Is 45 minutes of daily walking reasonable for my adult dog?", "supported"),
    ("cat supported", _make_cat(),
     "How many meals should I plan for my cat's daily feeding schedule?", "supported"),
    ("dog insufficient (notes retrieved, don't answer)", _make_dog(),
     "What brand of dog food should I buy for my adult dog?", "insufficient"),
    ("cat insufficient (notes retrieved, don't answer)", _make_cat(),
     "Is it safe to give my cat human ibuprofen for pain relief?", "insufficient"),
]


def score_supported(answer: str, notes: list[CareNote]) -> bool:
    """True if the answer cites at least one of the notes actually supplied to it."""
    return any(f"[{note.note_id}]" in answer for note in notes)


def score_insufficient(answer: str) -> bool:
    """True if the answer abstains with exactly the no-evidence message, as instructed."""
    return answer.strip() == NO_EVIDENCE_MESSAGE


def main() -> int:
    try:
        client = GeminiClient()
    except RuntimeError as error:
        print(f"Cannot run: {error}")
        return 1

    zero_shot_score = 0
    few_shot_score = 0
    total = len(HELD_OUT_CASES)

    for label, pet, question, kind in HELD_OUT_CASES:
        notes = retrieve_notes(pet, question)
        zero_shot_prompt = build_prompt(pet, question, notes)
        few_shot_prompt = build_prompt_few_shot(pet, question, notes)

        zero_shot_answer = client.generate(zero_shot_prompt)
        few_shot_answer = client.generate(few_shot_prompt)

        if kind == "supported":
            zero_ok = score_supported(zero_shot_answer, notes)
            few_ok = score_supported(few_shot_answer, notes)
        else:
            zero_ok = score_insufficient(zero_shot_answer)
            few_ok = score_insufficient(few_shot_answer)

        zero_shot_score += zero_ok
        few_shot_score += few_ok

        print(f"=== {label} ({kind}) ===")
        print(f"  species:         {pet.species}")
        print(f"  question:        {question}")
        print(f"  retrieved notes: {[n.note_id for n in notes]}")
        print(f"  [zero-shot] {'PASS' if zero_ok else 'FAIL'}: {zero_shot_answer}")
        print(f"  [few-shot]  {'PASS' if few_ok else 'FAIL'}: {few_shot_answer}")
        print()

    print(f"Zero-shot score: {zero_shot_score}/{total}")
    print(f"Few-shot score:  {few_shot_score}/{total}")

    if few_shot_score > zero_shot_score:
        print("Result: few-shot measurably improved scores on this held-out set.")
    elif few_shot_score < zero_shot_score:
        print("Result: few-shot regressed scores on this held-out set.")
    else:
        print("Result: tie — few-shot did not measurably improve scores on this held-out set.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
