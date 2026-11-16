"""Ask PawPal: local retrieval over a small care-notes corpus, then Gemini generation.

Retrieval never touches the network. Only `GeminiClient.generate()` calls out to
Gemini, so tests can inject a fake client and stay API-key-free.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass

from pawpal_system import Pet

DEFAULT_MODEL = "gemini-3.5-flash-lite"

NO_EVIDENCE_MESSAGE = (
    "I don't have local pet-care notes that cover this question, so I can't answer it from "
    "PawPal's notes. Please ask a vet or pet-care professional, or rephrase with a pet-care topic."
)

# Common words that carry no topical meaning on their own (e.g. "a", "how", "my"). Excluding
# them from keyword matching keeps a note's relevance tied to real overlap, not filler words
# two unrelated sentences happen to share.
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being", "to", "of", "in", "on",
    "at", "for", "with", "and", "or", "but", "if", "than", "then", "so", "do", "does", "did",
    "how", "what", "when", "where", "why", "who", "i", "you", "he", "she", "it", "we", "they",
    "my", "your", "his", "her", "its", "our", "their", "this", "that", "these", "those",
    "should", "would", "could", "can", "will", "shall", "may", "might", "must", "not", "no",
})
_WORD_RE = re.compile(r"[a-z0-9]+")


def _content_words(text: str) -> set[str]:
    """Tokenize text into lowercased words, dropping punctuation and stopwords."""
    return {word for word in _WORD_RE.findall(text.lower()) if word not in _STOPWORDS}


@dataclass(frozen=True)
class CareNote:
    note_id: str
    species: str  # "dog", "cat", or "any"
    category: str  # TaskCategory name, lowercase, or "general"
    text: str


CARE_NOTES: list[CareNote] = [
    CareNote("walk-dog-1", "dog", "walk",
              "Adult dogs generally need 20-60 minutes of walking a day, split across 1-3 walks; "
              "high-energy breeds may need more."),
    CareNote("walk-cat-1", "cat", "enrichment",
              "Cats don't need walks, but 10-15 minutes of active play (wand toys, chasing) once or "
              "twice a day covers similar exercise needs."),
    CareNote("feeding-dog-1", "dog", "feeding",
              "Most adult dogs do well on two meals a day, spaced roughly 8-12 hours apart, with "
              "portions based on their size and activity level."),
    CareNote("feeding-cat-1", "cat", "feeding",
              "Cats often prefer small, frequent meals; free-feeding dry food plus 1-2 scheduled wet "
              "meals a day is common."),
    CareNote("medication-any-1", "any", "medication",
              "Give medications at consistent times each day, and never double up on a missed dose "
              "without checking with a vet first."),
    CareNote("grooming-dog-1", "dog", "grooming",
              "Short-haired dogs typically need brushing weekly; long-haired breeds often need it "
              "every 1-2 days to prevent matting."),
    CareNote("grooming-cat-1", "cat", "grooming",
              "Most cats self-groom well, but weekly brushing reduces shedding and hairballs, more "
              "often for long-haired cats."),
    CareNote("conflict-any-1", "any", "general",
              "If two tasks are scheduled at the same time, consider spacing them out or lowering the "
              "priority of the less time-sensitive one."),
    CareNote("general-any-1", "any", "general",
              "When in doubt about a health concern, treat it as a question for a veterinarian rather "
              "than a scheduling question."),
]

# Document frequency of each content word across the whole corpus, computed once at import
# time. A word that shows up in most/all notes (e.g. "day") is a weak relevance signal; a
# word specific to one or two notes is a strong one. This drives the IDF weighting below.
_DOCUMENT_FREQUENCY: dict[str, int] = {}
for _note in CARE_NOTES:
    for _word in _content_words(_note.text):
        _DOCUMENT_FREQUENCY[_word] = _DOCUMENT_FREQUENCY.get(_word, 0) + 1
del _note, _word

# Smaller than the weakest real single-word match (the most common content word, "day",
# scores ln(9/5) ≈ 0.59), so this can only reorder notes that already cleared the relevance
# gate on keyword weight alone — never admit a note by itself.
_CATEGORY_BONUS = 0.2


def _idf(word: str) -> float:
    """Inverse document frequency: down-weights words that occur across many notes."""
    df = _DOCUMENT_FREQUENCY.get(word, 0)
    if df == 0:
        return 0.0
    return math.log(len(CARE_NOTES) / df)


def retrieve_notes(pet: Pet, question: str, limit: int = 3) -> list[CareNote]:
    """Return the most relevant local care notes for this pet and question.

    A note is only a candidate if it shares real content words with the question
    (stopwords like "a"/"to"/"my" don't count, so two unrelated sentences sharing
    filler words can't match). Matched words are weighted by inverse document
    frequency, so a word that appears in most notes (e.g. "day") contributes far
    less than one specific to a note or two, which keeps a handful of notes
    sharing only common words from outranking (or crowding out) the true match.
    The pet's task-category bonus only reorders notes that already cleared that
    bar — it cannot make an unrelated note relevant.
    """
    question_words = _content_words(question)
    task_categories = {task.category.name.lower() for task in pet.tasks}

    scored: list[tuple[float, CareNote]] = []
    for note in CARE_NOTES:
        if note.species not in ("any", pet.species.lower()):
            continue
        note_words = _content_words(note.text)
        overlap = question_words & note_words
        score = sum(_idf(word) for word in overlap)
        if score <= 0:
            continue
        if note.category in task_categories:
            score += _CATEGORY_BONUS
        scored.append((score, note))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [note for _, note in scored[:limit]]


def build_prompt(pet: Pet, question: str, notes: list[CareNote]) -> str:
    """Assemble the Gemini prompt from the pet, the owner's question, and retrieved notes."""
    if notes:
        notes_block = "\n".join(f"- [{note.note_id}] {note.text}" for note in notes)
    else:
        notes_block = "- (no specific local care notes matched this question)"

    return (
        f"You are PawPal, a pet care assistant. Answer the owner's question about their "
        f"{pet.species} named {pet.name} ({pet.breed}), using ONLY the care notes below as your "
        "evidence. Do not use outside knowledge, and do not answer questions unrelated to pet "
        "care (e.g. general how-to topics), even if you know the answer.\n\n"
        f"Relevant care notes:\n{notes_block}\n\n"
        f"Question: {question}\n\n"
        "Answer concisely, and cite note ids in brackets, like [note-id], when you rely on one. "
        "If the care notes above do not contain enough information to answer the question, "
        f"reply with exactly this sentence and nothing else: \"{NO_EVIDENCE_MESSAGE}\""
    )


class GeminiClient:
    """Thin wrapper around the google-genai SDK so callers only depend on `.generate()`."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        from google import genai  # imported lazily: never required to run the test suite

        resolved_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not resolved_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")

        self.model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self._client = genai.Client(api_key=resolved_key)

    def generate(self, prompt: str) -> str:
        response = self._client.models.generate_content(model=self.model, contents=prompt)
        return response.text


def ask(pet: Pet, question: str, client) -> str:
    """Retrieve locally, build the prompt, and generate an answer via `client.generate(prompt)`.

    `client` only needs a `.generate(prompt: str) -> str` method, so tests can pass a fake.
    When local retrieval finds no relevant care notes, this returns NO_EVIDENCE_MESSAGE
    directly and never calls `client.generate()` — no Gemini call, no API key required.
    """
    notes = retrieve_notes(pet, question)
    if not notes:
        return NO_EVIDENCE_MESSAGE
    prompt = build_prompt(pet, question, notes)
    return client.generate(prompt)


if __name__ == "__main__":
    # Live smoke test: `python3 -m pawpal_rag` (requires GEMINI_API_KEY in the environment).
    smoke_client = GeminiClient()
    reply = smoke_client.generate("Reply with a short confirmation that you received this test message.")
    print(f"Model: {smoke_client.model}")
    print(f"Response: {reply}")
