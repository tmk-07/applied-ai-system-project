# Model Card: Ask PawPal (RAG + Gemini)

This covers the "Ask PawPal" feature only (`pawpal_rag.py`, the Ask PawPal section of `app.py`, `eval_pawpal_rag.py`). It is a small retrieval-augmented generation (RAG) layer: local keyword retrieval over a static, hand-written corpus (`CARE_NOTES`), followed by a single call to Gemini (`gemini-3.5-flash-lite` by default) that is only given the retrieved notes as evidence.

## What it does

Given a pet and a free-text question, `retrieve_notes()` tokenizes the question and each of the 9 entries in `CARE_NOTES`, strips common stopwords, filters notes to the pet's species, and keeps a note only if it shares a real content word with the question. If nothing is retrieved, `ask()` returns a fixed no-evidence message and makes zero calls to Gemini. If something is retrieved, `build_prompt()` assembles a prompt instructing the model to answer using only those notes, cite note ids, and output the same no-evidence message if the notes don't actually support an answer.

## Limitations

- **Keyword retrieval, not semantic search.** Matching is exact-token overlap after stopword removal — no stemming, no embeddings. "feed" and "feeding", or "dog" and "dogs", don't match each other. This means some genuinely relevant notes can be missed (false negatives) if the owner's wording doesn't share a literal token with the note text.
- **Tiny, static corpus.** `CARE_NOTES` has 9 hand-written entries covering walk/feeding/medication/grooming/enrichment/general topics for dogs and cats only. Any question outside those topics, or about a species other than dog/cat, will correctly get the no-evidence response rather than an answer — this is a coverage gap, not a bug.
- **Noisy but harmless over-retrieval.** Common words like "day" appear in nearly every note, so a supported question often retrieves 2-3 notes instead of exactly 1. Observed directly in both the offline and live evals (see "Testing observations" below): the dog-walking question retrieved `['walk-dog-1', 'feeding-dog-1', 'medication-any-1']`, and the cat-feeding question retrieved `['feeding-cat-1', 'walk-cat-1', 'medication-any-1']`. In both live runs Gemini correctly cited only the truly relevant note and ignored the other two, but this relies on the model's judgment at generation time, not on retrieval precision — a smaller/less capable model given the same prompt could cite an irrelevant note instead.
- **No conversation memory.** Each question is answered independently; there's no multi-turn context from earlier questions about the same pet.
- **Generic model-level limitations apply**: Gemini can still misread a correctly-retrieved note, answer with hedged/vague language, or (rarely) ignore the "use only the notes" instruction, since that constraint is enforced by prompt instructions, not by output filtering.

## Misuse considerations

- **Not veterinary advice.** The notes are generic, non-personalized guidance (e.g., typical walk durations, typical feeding schedules). The prompt and one of the care notes (`general-any-1`) explicitly steer health-specific questions toward a vet rather than trying to answer them, but this is a prompt-level mitigation, not a hard block — a determined user could still get the model to speculate on a health question if it happens to share keywords with a stored note.
- **No PII or account-linked data** flows into the corpus or the prompt — only the pet's name, species, and breed (already user-entered in the Streamlit session) and the static care notes.
- **API key handling**: `GeminiClient` reads `GEMINI_API_KEY` from the environment and never logs or returns it; `eval_pawpal_rag.py` is deliberately structured so the no-evidence case needs no key at all, and the live-mode output only ever prints the model's answer text, never the key.
- **Not a general-purpose chatbot.** The system prompt explicitly instructs the model not to answer unrelated topics using outside knowledge. Before the fix below, this instruction was not reliably followed and the app answered an off-topic question directly.

## Testing observations

- **Regression bug (fixed 2026-11-15):** asking "How to change a bicycle tire?" with a dog selected returned full bicycle-repair instructions instead of a no-evidence response. Root cause: `retrieve_notes()` scored on raw whitespace-split tokens with no stopword filtering, so the question's filler words ("a", "to") overlapped with filler words in several notes (`walk-dog-1`, `feeding-dog-1`, `medication-any-1`, `grooming-dog-1`) and scored above the inclusion threshold on their own — independent of the pet's task-category bonus. The category bonus (the dog had a "walk" task) only decided which of those already-bogus notes ranked first; it was not, by itself, the thing letting a note through.
- **Fix:** keyword matching now strips stopwords before scoring, a note is only a candidate once it has real content-word overlap with the question, and the category bonus is applied only after that gate (it reorders, it cannot admit). `ask()` was also changed to check retrieval first and return the no-evidence message without calling the model at all — so the fix is enforced in code, not only in the prompt wording. `app.py` was restructured to run retrieval before constructing `GeminiClient()`, so the no-evidence path needs no `GEMINI_API_KEY`.
- **Irrelevant notes ranked below the correct match:** confirmed directly in both the offline eval and the live Gemini run. For "How many minutes a day should my adult dog walk?", `feeding-dog-1` and `medication-any-1` were retrieved alongside the correct `walk-dog-1` (all three share the content word "day"), but ranked below it, and Gemini's live answer cited only `walk-dog-1`. Same pattern for the cat-feeding question (`walk-cat-1` and `medication-any-1` retrieved below `feeding-cat-1`, only `feeding-cat-1` cited).
- **Observed results, 2026-11-15:**
  - Offline evaluation (`eval_pawpal_rag.py`, fake client): 3/3 cases passed.
  - Full test suite (`python3 -m pytest`): 20/20 passed, run with no `GEMINI_API_KEY` set.
  - Live evaluation (`eval_pawpal_rag.py --live`, real Gemini): 3/3 cases passed; both supported cases returned a correctly-cited, on-topic answer, and the bicycle case made 0 model calls exactly as in offline mode.

## Few-Shot Specialization Experiment

A separate script, `fewshot_experiment.py`, compares the production zero-shot prompt (`pawpal_rag.build_prompt()`, unchanged — the app and `ask()` still use it) against a few-shot variant (`build_prompt_few_shot()`, defined only in that script) that adds two worked examples before the real notes/question: one supported answer that cites a note (`grooming-dog-1`), and one insufficient-evidence answer where a retrieved note is topically related but doesn't answer the question (`grooming-cat-1`). Both variants are otherwise byte-identical (same instructions, same notes block, same question, same closing instruction), and both are sent through the same `GeminiClient` (same model, same settings) for each held-out question, so the examples are the only variable.

**Held-out test set** (4 questions, using only `walk-dog-1`, `feeding-dog-1`, `feeding-cat-1`, `medication-any-1` — disjoint from the two notes used in the few-shot examples above):

| Case | Question | Retrieved notes | Kind |
|---|---|---|---|
| dog supported | "Is 45 minutes of daily walking reasonable for my adult dog?" | `walk-dog-1`, `feeding-dog-1` | supported |
| cat supported | "How many meals should I plan for my cat's daily feeding schedule?" | `feeding-cat-1` | supported |
| dog insufficient | "What brand of dog food should I buy for my adult dog?" | `walk-dog-1`, `feeding-dog-1` | insufficient — neither note names a brand |
| cat insufficient | "Is it safe to give my cat human ibuprofen for pain relief?" | `medication-any-1` | insufficient — note doesn't cover this |

Scoring: a "supported" case passes if the answer cites any of the notes actually supplied to it (`[note-id]` substring match); an "insufficient" case passes if the answer abstains with exactly `NO_EVIDENCE_MESSAGE`, as both prompts instruct.

**Actual output, 2026-11-15 (`GEMINI_API_KEY=... python3 fewshot_experiment.py`, `gemini-3.5-flash-lite`):**

```
=== dog supported (supported) ===
  retrieved notes: ['walk-dog-1', 'feeding-dog-1']
  [zero-shot] PASS: Yes, 45 minutes of daily walking is reasonable, as adult dogs generally
    need 20-60 minutes of walking a day, split across 1-3 walks, though high-energy breeds
    may need more [walk-dog-1].
  [few-shot]  PASS: Answer: Yes, 45 minutes of daily walking is reasonable, as adult dogs
    generally need 20 to 60 minutes of walking a day, which can be split across 1 to 3
    walks [walk-dog-1].

=== cat supported (supported) ===
  retrieved notes: ['feeding-cat-1']
  [zero-shot] PASS: For Luna's daily feeding schedule, you can plan for small, frequent
    meals, with a common approach being free-feeding dry food plus 1-2 scheduled wet
    meals a day [feeding-cat-1].
  [few-shot]  PASS: Answer: A common daily feeding schedule for cats includes small,
    frequent meals, such as free-feeding dry food combined with 1 to 2 scheduled wet
    meals a day [feeding-cat-1].

=== dog insufficient (notes retrieved, don't answer) (insufficient) ===
  retrieved notes: ['walk-dog-1', 'feeding-dog-1']
  [zero-shot] PASS: I don't have local pet-care notes that cover this question, so I
    can't answer it from PawPal's notes. Please ask a vet or pet-care professional, or
    rephrase with a pet-care topic.
  [few-shot]  PASS: (identical message)

=== cat insufficient (notes retrieved, don't answer) (insufficient) ===
  retrieved notes: ['medication-any-1']
  [zero-shot] PASS: (no-evidence message)
  [few-shot]  PASS: (identical message)

Zero-shot score: 4/4
Few-shot score:  4/4
Result: tie — few-shot did not measurably improve scores on this held-out set.
```

(Full exact answer text for all 4 cases, both variants, is in the raw run output; the two insufficient-evidence cases are abbreviated above only because zero-shot and few-shot produced the identical, exact `NO_EVIDENCE_MESSAGE` string.)

**Manual citation check:** for both supported cases, the cited note (`walk-dog-1`, `feeding-cat-1`) genuinely supports the claim made — the dog answer's "20-60 minutes... split across 1-3 walks" and the cat answer's "free-feeding dry food plus 1-2 scheduled wet meals a day" are both taken directly from the cited note's text, not fabricated or drawn from the uncited `feeding-dog-1` note that was also retrieved alongside `walk-dog-1`.

**Result: tie, 4/4 vs. 4/4.** The zero-shot prompt was already fully correct on this held-out set — both the citation behavior and the insufficient-evidence abstention. The few-shot examples changed surface wording slightly (an added "Answer:" prefix, minor phrasing differences) but did not change correctness on any case, and the two insufficient-evidence cases were byte-identical between variants. **Recommendation: do not adopt the few-shot variant.** It adds prompt length and latency/token cost for a model (`gemini-3.5-flash-lite`) that is already behaving correctly zero-shot on this test set; there's no measured benefit to justify the cost. This result is specific to this model, this prompt, and this small held-out set — a smaller or different model might benefit from the same examples, but that would need its own test, not an assumption.

## AI collaboration reflection

Claude Code was used throughout this feature: designing the retrieval/prompt/client split in `pawpal_rag.py`, diagnosing the bicycle-tire regression, writing the fix, and building `eval_pawpal_rag.py`.

**Accepted as-is:** the stopword filter and the rule that a task-category match can only reorder already-relevant notes, never make an unrelated note eligible on its own. I accepted this because the diagnosis traced the actual failure correctly — filler-word overlap (e.g. "a", "to") scoring above the inclusion threshold on its own, not the category bonus in isolation — before any fix was proposed, and the resulting fix (strip stopwords, require real content-word overlap before a note is even a candidate, apply the category bonus only afterward to reorder) matched that diagnosis exactly. No changes were needed.

**Revised:** the original no-evidence behavior relied only on a prompt instruction telling Gemini to reply with a fixed no-evidence sentence when the retrieved notes didn't cover the question. When I tested the bicycle-tire case, Gemini's response acknowledged that the notes didn't cover bicycle repair and then went ahead and answered the question anyway — the prompt-only instruction wasn't reliably followed. I asked for a Python-level guardrail instead: a hard check in `ask()` that returns the no-evidence fallback and skips calling Gemini entirely whenever retrieval comes back empty, so the behavior doesn't depend on the model choosing to comply. I revised the design this way because a prompt is a request the model can ignore, while a code branch that never calls `client.generate()` cannot. I verified this in two ways: a manual Streamlit rerun of the bicycle question showed only the fallback message (no model output at all), and the regression test (`test_ask_on_bicycle_question_returns_no_evidence_and_never_calls_gemini`) asserts `client.call_count == 0` to confirm this holds automatically, not just in the one manual check.
