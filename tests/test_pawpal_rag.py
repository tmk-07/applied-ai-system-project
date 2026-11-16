from pawpal_rag import NO_EVIDENCE_MESSAGE, ask, build_prompt, retrieve_notes
from pawpal_system import Pet, Priority, Task, TaskCategory


class FakeGeminiClient:
    """Stands in for GeminiClient so tests never touch the network or need an API key.

    Also records how many times generate() was called, so tests can assert that a
    no-evidence question never reaches "Gemini".
    """

    def __init__(self, response="Fake answer [walk-dog-1]"):
        self.response = response
        self.last_prompt = None
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        return self.response


def _make_dog():
    pet = Pet(name="Rex", species="dog", breed="Labrador", age=3)
    pet.add_task(
        Task(task_id="t1", name="Walk", category=TaskCategory.WALK,
             duration_minutes=30, priority=Priority.HIGH)
    )
    return pet


def _make_cat():
    return Pet(name="Luna", species="cat", breed="Tabby", age=2)


def test_retrieve_notes_matches_species_and_task_category():
    notes = retrieve_notes(_make_dog(), "How many minutes a day should my adult dog walk?")

    assert notes
    assert all(note.species in ("dog", "any") for note in notes)
    assert any(note.note_id == "walk-dog-1" for note in notes)


def test_retrieve_notes_category_bonus_cannot_surface_an_unrelated_note():
    # Rex has a "walk" task, so walk-dog-1 gets a category bonus — but a bicycle
    # question shares no real content words with any care note, including walk-dog-1,
    # so the bonus must not be enough to pull it (or anything else) in.
    notes = retrieve_notes(_make_dog(), "How do I change a bicycle tire?")

    assert notes == []


def test_retrieve_notes_excludes_other_species():
    notes = retrieve_notes(_make_cat(), "how often should I feed my cat")

    assert all(note.species != "dog" for note in notes)


def test_retrieve_notes_on_unmatched_question_returns_empty_list():
    # A pet with no tasks gets no category-match bonus, so an unrelated question scores zero.
    assert retrieve_notes(_make_cat(), "xyzzy quux") == []


def test_build_prompt_includes_question_and_pet_name():
    pet = _make_dog()
    question = "How many minutes a day should my adult dog walk?"
    notes = retrieve_notes(pet, question)

    prompt = build_prompt(pet, question, notes)

    assert "Rex" in prompt
    assert question in prompt
    assert "walk-dog-1" in prompt


def test_build_prompt_with_no_notes_says_so():
    pet = _make_dog()

    prompt = build_prompt(pet, "xyzzy quux", [])

    assert "no specific local care notes" in prompt


def test_ask_uses_injected_client_without_network():
    pet = _make_dog()
    client = FakeGeminiClient(response="Walk Rex for 30-60 minutes a day.")

    answer = ask(pet, "How many minutes a day should my adult dog walk?", client)

    assert answer == "Walk Rex for 30-60 minutes a day."
    assert "Rex" in client.last_prompt
    assert client.call_count == 1


def test_ask_on_bicycle_question_returns_no_evidence_and_never_calls_gemini():
    # Regression test for the bug: Mochi/Rex has a "walk" task (so walk-dog-1 gets a
    # category bonus), but a bicycle-repair question has no real overlap with any care
    # note. ask() must recognize there's no evidence and must not call the model at all.
    pet = _make_dog()
    client = FakeGeminiClient(response="Step 1: remove the wheel...")

    answer = ask(pet, "How do I change a bicycle tire?", client)

    assert answer == NO_EVIDENCE_MESSAGE
    assert client.call_count == 0
    assert client.last_prompt is None
