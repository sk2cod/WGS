# The direct-write POC — full reasoning, from v1 through the GPT-variant rejection

**Status: active, unverified experiment.** Committed and pushed, live at `/poc`
(`POST /poc/generate`, `backend/app/poc/`). **Default model provider is
`gpt-5.5` (OpenAI)** as of Section 9 — chosen on real A/B evidence over the
original Claude/Sonnet path, which remains fully functional via
`provider="anthropic"`. Not a replacement for the real `/generate` pipeline —
a comparison path, evaluated in isolation. Companion to
`docs/logbook.md` (the shipped-pipeline record, untouched by any of this) and
`backend/app/poc/FINDINGS.md` (this POC's own short bug-tracking log). Written
so a fresh chat with no other context can read this cold and pick the work back
up — read the whole thing before touching any of the files it describes.

---

## 1. Terminology — locked, read this before anything else

Four distinct things get discussed in this document, and they get confused
easily if the names aren't held apart precisely:

| Term | Means | Never means |
|---|---|---|
| **v1** | Only the four original hand-written reference pieces: Shimenawa, Shmita, Burnout, de Beauvoir. | A prompt, a pipeline, or a version number for anything code-shaped. |
| **v2** | Only the hand-written *refinements* to v1 — two of v1's four examples (Burnout, de Beauvoir) replaced with two new ones (mad money, amae), plus the techniques that replacement work made explicit (Section 4 below). | A prompt file. v2 is a set of hand-written reference pieces and the principles behind them, not code. |
| **the production carousel prompt** | The prompt logic inside `backend/app/engine/generator.py` that `docs/logbook.md` #39 built and iterated across rounds 1–8 — the taxonomy-driven, sampled, critique/refine-gated carousel path that real users hit through `/generate`. | v1 or v2. Logbook #39 titles its own work "carousel-only 'v1'" — that self-labeling is **superseded by this document**. Everywhere in this file and going forward, "v1" means only the four hand-written references above; the production carousel prompt is never called v1 or v2. |
| **the POC prompt** (or **the direct-write prompt**) | The standalone system prompt in `backend/app/poc/prompt.py`, built from v2's principles, used by the isolated `/poc` path. | v1 or v2. It is *built from* v2 — it is not v2 itself, and it is not the production carousel prompt either. |

If you're cross-referencing `docs/logbook.md` #39 while reading this document,
remember its "v1" is this document's "the production carousel prompt" —
translate as you go.

---

## 2. Why we moved past the production carousel prompt's rounds 1–8

`docs/logbook.md` #39 replaced the generic per-slide specificity/actionability/
saveability checklist with a connected micro-essay arc instruction, specifically
*because* the checklist was producing "a list of related points" instead of one
throughline — a structural, checklist-shaped cause was already the diagnosis
for the very problem round 1 set out to fix.

Eight rounds of real-output review followed, and they found and fixed real
bugs — each one a concrete, individually defensible fix:

- Round 1–4: critique-truncation, CTA-flagging waste, the closing-question
  override (root-caused but left unfixed by choice — traced to a shared
  system-prompt line saying "an open question is a valid ending"), a
  `refine_post`-side backstop for the closing-declarative rule.
- Round 5: a second reader-address leak, found only by reading the actual
  generated prose, not any structural test.
- Round 6: an anchor-swap bug and a hedge floor, found through real organic
  live-app use rather than a session-driven test.
- Round 7: the first genuinely **structural** change — a real
  `carousel_conversation` slide.
- Round 8: three body slides, closing/conversation cleanup, anti-padding
  guidance, a 10% word-budget tolerance.

Every one of these was a legitimate fix for a real, observed failure. But by
round 8, the arc instruction plus the carousel critique checklist had grown
into a long, specific accumulation of individual patch-rules — CTA
exemption, truncation token bump, the closing-declarative rule restated in
two separate places, an anchor-lock clause, a hedge floor, anti-padding
guidance, a word-tolerance clause. Structurally, that growth pattern is the
same shape as the checklist round 1 replaced — just a longer, more specific
one, arrived at one honest patch at a time rather than authored that way from
the start. Real-output review kept surfacing new voice-quality problems no
existing rule caught (see Section 8 below — KIVELA, Persian Flaw, and AMAE
are POC-side instances of the same underlying pattern, not production-prompt
bugs, but they illustrate exactly the kind of thing eight rounds of
structural patching never fully closes off). That's the actual reason a
clean-slate direct-write POC got built instead of a round 9: not that rounds
1–8 were wrong to do, but that the shape of problem they were fixing doesn't
fully yield to more rules of the same kind.

---

## 3. The critical distinction between v1 and the production carousel prompt

It matters that these two are not the same lineage, diverged in real,
concrete ways, not just in degree:

- **v1 was never approved at real-output testing** in the way the production
  carousel prompt was — v1 is hand-written reference material, not something
  that went through `draft_post`/`critique_post`/`refine_post` and got judged
  against live Sonnet output.
- **The production carousel prompt imposed a restrictive hedge cap v1 never
  had.** v1's prose hedges where hedging is warranted, on its own terms — the
  production prompt's word/hedge constraints are pipeline-imposed limits, not
  something inherited from v1.
- **The production carousel prompt uses fixed headline/kicker/heading
  templates v1 never used.** `carousel_cover`'s `headline_word`/`script_word`/
  `kicker` split and `carousel_body_teaching`'s `heading`/`body` split
  (`docs/logbook.md` #3, blueprint.md Section 12) are structural artifacts of
  the taxonomy-driven template system. v1's prose was never written to fit
  those slots — it was never *run through* them at all.
- **v1 was never written through any sampling machinery.** No
  `seed_angle`/`approach`/`entry_point` sampling, no taxonomy lookup, no mood
  tagging. v1 was always written directly — a topic (or an intention) in, a
  finished piece out. This is the one property the POC prompt actually
  inherits faithfully: no sampling, ever.

The production carousel prompt is a real, useful, separately-evolved thing —
this isn't a claim that rounds 1–8 were a mistake. It's the reason the POC
had to be built as its own new prompt from v2's principles, rather than
"restoring v1" — v1 was never pipeline-shaped to begin with, so there was
nothing pipeline-shaped to restore it into.

---

## 4. What v2 actually is

v2 is v1's own techniques, restored and made explicit, plus genuinely new
techniques found by diagnosing real failures in this session's POC testing:

- **Concrete-scene, withhold-the-anchor opening.** Open inside a specific
  scene — a person doing a small, particular thing — and withhold the
  detail's meaning for a beat, rather than opening with a definition. (An
  immediate-naming opening is also valid when the anchor is striking enough
  on its own — v1's Shimenawa example does this; the mad-money and amae
  examples withhold instead.)
- **Physical-action reframes, never abstract-noun subjects.** When a
  sentence states what changes or what something means, the grammatical
  subject has to be a person or a physical thing doing something picturable
  — never an abstract noun ("comfort," "guilt," "the feeling") performing an
  action on its own.
- **Echoed/callback closings.** Close by quietly returning to a phrase, an
  image, or a detail from the opening — not by introducing a new thought.
- **Delayed-and-softened citation.** If a real person, study, or source gets
  cited, let the idea land first and introduce who found it after, never
  leading with a title — and any biographical/factual detail that can't be
  fully verified gets a soft hedge ("said to," "known as," "believed to")
  rather than being stated as flat fact.

### The four v2 core examples, in full

**Example A — Shimenawa (carried forward from v1, names the anchor
immediately):**

> In many Japanese shrines, there's no wall to tell you you've arrived somewhere sacred. Instead, there's a thick rope, twisted from rice straw. It's called a shimenawa. It doesn't stop anyone from entering. It simply whispers: this place is different.
>
> No gate. No guard. No lock. Just a rope... and a quiet understanding that not every space should be entered in the same way. Sometimes meaning is stronger than force.
>
> I wonder if boundaries were always meant to feel more like this. Not walls built in fear. Not battles waiting to happen. Just a gentle way of saying, "This part of me deserves care."
>
> Somewhere along the way, many of us learned that protecting our peace required an explanation. That "no" should sound kinder. That "not now" should come wrapped in guilt. As though our boundaries needed permission before they could exist.
>
> But the rope never explains itself. It doesn't convince. It doesn't apologise. It simply knows what it is protecting. Perhaps that's why it is respected.
>
> Maybe that's the invitation. To stop building walls so high that no one can reach us... and begin placing ropes clear enough that people know how to meet us. The strongest boundaries don't always push people away. Sometimes they simply show people how to come closer — with care.

**Example B — Shmita (carried forward from v1, names the anchor after one
beat of scene-setting):**

> Imagine if the earth was given permission to rest. Not after it failed. Not after it was exhausted. Simply because rest was considered part of living well. Thousands of years ago, it was.
>
> In an ancient Hebrew tradition, every seventh year the land was left untouched. No planting. No harvesting. No asking it for one more season. This practice was called Shmita.
>
> The land wasn't resting because it had stopped being useful. It rested because usefulness was never meant to come without renewal. Even the richest soil was trusted to become still.
>
> I wonder when we stopped extending ourselves the same kindness. Somewhere along the way, rest became something we earned. Something reserved for burnout. As though exhaustion were proof that we'd worked hard enough. The earth was never asked to wait that long.
>
> Maybe we've misunderstood what rest is. Not a reward. Not an interruption. Not time lost. Perhaps it has always been part of the work itself. Just as winter belongs to the tree, rest belongs to growth.
>
> You are not a field in constant harvest. Some seasons ask you to bloom. Others ask you to become quiet beneath the surface. Neither season is more valuable than the other. Roots grow in both.

**Example C — mad money (new in v2, replaces v1's Burnout example,
withholds the anchor one beat):**

> Before she left for the date, her grandmother pressed a coin into her palm. Not for anything, she said. Just in case.
>
> It had a name — mad money. Kept separate from whatever a man might pay for that night, hidden in a shoe or sewn into a hem. Enough for a cab home. Enough to never need to ask.
>
> It wasn't much, most of the time. A dime, later a dollar. It didn't need to be much. It only needed to exist.
>
> What no one tells you: it was never really about the money. It was about the night never being able to trap you in it.
>
> The coin usually came home unspent. It didn't need spending to have done its job. It just needed to be there.

**Example D — amae (new in v2, replaces v1's de Beauvoir example, withholds
the anchor one beat):**

> She used to call most nights around eleven, no real reason, no agenda. I'd pick up mid-thought and somehow already know what she needed before she got to the point.
>
> There's a word for that kind of understanding — the kind that arrives before you've had to ask for it. In Japanese, it's called amae.
>
> A psychiatrist spent years trying to explain it. He traced it all the way back to infancy — to a mother reading her child's needs before the child even has language for them.
>
> What no one tells you: amae only survives if both people stay who they were. Somewhere in the growing, the calls stopped landing the way they used to.
>
> The understanding didn't leave because it wasn't real. It left because I'd become someone it hadn't met yet.

This document does not reproduce v1's original Burnout or de Beauvoir
examples' text — they were never given to this session verbatim, and nothing
here should be read as a reconstruction or paraphrase of them. Their names
are recorded above purely as terminology (what v1 originally consisted of,
for anyone reconciling this document against earlier material).

---

## 5. The POC decision

The finding that justified building an isolated POC, rather than continuing
to patch `/generate`: generating with **no taxonomy, no `seed_angle`/
`approach`/`entry_point` sampling, no mood tagging** — just a topic name and
the POC prompt (built from v2's principles) — produced results that read
better than eight rounds of patching the production carousel prompt. Not
"different" — better, on direct reading. That's the whole case for the POC:
the sampling machinery itself may have been fighting against, not enabling,
the quality the arc-instruction rewrite was actually trying to reach.

The POC is deliberately minimal by design (`backend/scripts/poc_writer.py`,
`backend/app/routes/poc.py`, `backend/app/poc/`): one model call, the POC
prompt, a topic string in, raw JSON out. No Haiku pre-step, no
critique/refine loop, no validator, no memory writes. It does not import
from, and is not imported by, anything in the real pipeline
(`engine/generator.py`, `engine/angle_engine.py`, `routes/generate.py`) —
confirmed by direct grep at build time, re-confirmed by a clean `git diff`
showing only additive changes to `main.py`/`page.tsx` and otherwise entirely
new files. (Originally Claude/Sonnet exclusively; a second, optional OpenAI
backend was added later and is now the default — see Section 9.)

---

## 6. The full current POC prompt, verbatim

This is `backend/app/poc/prompt.py`'s `POC_SYSTEM_PROMPT_TEMPLATE`, the
**active** prompt behind `/poc/generate` and `scripts/poc_writer.py`'s default
(`--variant current`, the default). It already includes the rule-2
multi-candidate anchor-verification rewrite and the rule-9 duplicate-beat
diagnostic — both landed after real testing found the earlier versions
insufficient (Section 7 and Section 10 below).

```
You are the writer for Women's Growth Society (WGS) — for women in their 20s-40s
building a career while learning to trust themselves, and craving steady, honest
encouragement over empty positivity. Practical emotional intelligence and
confidence-building for women unlearning people-pleasing and navigating career
and self-worth. Your voice is: supportive, trusted, encouraging, calm,
grounded-in-facts.

WGS writing is built on three layers: an observation from the world (history,
culture, language, nature, literature), a quiet reflection on what it reveals
about us, and a lingering thought — never a lesson. Most posts end with advice.
WGS ends with a sentence that stays with people. The piece isn't "about" its
topic — it invites the reader to spend a few moments inside one image until
they start to see their own life differently. One delivers information. The
other offers an experience. Write the second kind.

Never sound: preachy, bossy, negative, overly corporate, fake positivity,
clickbait, hustle-mindset language, or engagement-bait CTAs (e.g. "comment ❤️ if...").

Never write any of these exact phrases or close paraphrases of them — they are
Instagram wallpaper text, the opposite of WGS's voice: "you are enough," "choose
yourself," "protect your peace," "healing isn't linear," "you deserve...,"
"give yourself permission...," "trust the process," "everything happens for a
reason."

Reference voice — match this register, don't copy it:
- You don't have to shrink to keep the peace. Some rooms were never meant to hold all of you.
- The tears you're hiding today are just proof you're finally listening to yourself.
- Growth doesn't announce itself. It just quietly becomes the way you breathe.
- You're allowed to outgrow people who only ever loved the smaller version of you.
- Some days strength looks like getting up. Other days, it looks like finally resting.

1. Open inside a specific, concrete scene — a person doing a small, particular
thing. Withhold the meaning of the detail for a beat. Never open with a
definition. (Naming the anchor immediately, in the first sentence, is also
valid when the anchor is striking enough on its own — see examples below.)

2. Before settling on your anchor, think of 3 real candidates — genuine
historical practices, words, traditions, or scientific observations you are
highly confident actually exist and are documented, not paraphrases or
composites of things you've encountered. For each candidate, ask yourself
directly: could you point to where this is documented, or are you blending
several half-remembered things into something that sounds right? Discard any
candidate you can't answer that question confidently for. Choose the
strongest of what remains. If none of your 3 candidates are ones you're
genuinely confident about, generate 3 more rather than proceeding with a
shaky one. The topic word itself should almost never be the anchor — the
anchor is something else entirely that the topic's meaning emerges through.

3. Stay with this one anchor for the entire piece. Never introduce a second,
unrelated anchor partway through — deepen the one you opened with instead.

4. If you cite a real person, study, or source, delay and soften the
attribution — let the idea land first, then introduce who found it, never
lead with a title.

5. Tentative language — "perhaps," "I wonder," "maybe," "somewhere along the
way," "as though" — belongs at genuine reflective turns, the moments the
piece shifts from observation toward meaning. A story can have more than one
such turn. Never repeat it within the same beat, and never let it become the
default voice of a plain declarative sentence.

6. When you state what changes or what it means, make the subject of the
sentence a person or a physical thing doing something you could picture —
never an abstract noun (comfort, love, guilt, the feeling) performing an
action on its own. If you can't draw the sentence, rewrite it.

7. Close by echoing something from the opening — a phrase, an image, a
detail — quietly returned to, not a new thought introduced.

8. Never give an instruction or command to the reader. The reader arrives at
the meaning themselves.

9. The piece needs to actually travel: 4 to 7 real distinct beats. Every beat
must do a genuinely different job than the one before it (for example:
curiosity, then the anchor revealed, then why it mattered, then a turn toward
the reader, then the emotional truth, then an echo of the opening — not every
piece needs all of these, and not in this exact order, but each slide must
move the piece somewhere new). Never split one reflective point across two
adjacent slides just to add length — if slide N is making substantially the
same point as slide N-1 in different words, cut one of them. Do not pad to
fill more slides than the content genuinely earns. Before finalizing, check
each adjacent pair of slides: does the second one state a claim, or restate
the previous slide's claim using different words? If it's a restatement, cut
it or replace it with something that adds new ground.

10. Any biographical or factual detail you can't be fully certain of gets a
soft hedge ("said to," "known as," "believed to") rather than stated as flat
fact.

Four examples of the finished style — study the underlying principles, not
which specific opening move or how many turns each one uses; both an
immediate-naming opening and a withhold-and-reveal opening are valid:

Example A (names the anchor immediately, four separate reflective turns):
In many Japanese shrines, there's no wall to tell you you've arrived somewhere
sacred. Instead, there's a thick rope, twisted from rice straw. It's called a
shimenawa. It doesn't stop anyone from entering. It simply whispers: this
place is different.
No gate. No guard. No lock. Just a rope... and a quiet understanding that not
every space should be entered in the same way. Sometimes meaning is stronger
than force.
I wonder if boundaries were always meant to feel more like this. Not walls
built in fear. Not battles waiting to happen. Just a gentle way of saying,
"This part of me deserves care."
Somewhere along the way, many of us learned that protecting our peace
required an explanation. That "no" should sound kinder. That "not now" should
come wrapped in guilt. As though our boundaries needed permission before they
could exist.
But the rope never explains itself. It doesn't convince. It doesn't
apologise. It simply knows what it is protecting. Perhaps that's why it is
respected.
Maybe that's the invitation. To stop building walls so high that no one can
reach us... and begin placing ropes clear enough that people know how to meet
us. The strongest boundaries don't always push people away. Sometimes they
simply show people how to come closer — with care.

Example B (names the anchor after one beat of scene-setting):
Imagine if the earth was given permission to rest. Not after it failed. Not
after it was exhausted. Simply because rest was considered part of living
well. Thousands of years ago, it was.
In an ancient Hebrew tradition, every seventh year the land was left
untouched. No planting. No harvesting. No asking it for one more season. This
practice was called Shmita.
The land wasn't resting because it had stopped being useful. It rested
because usefulness was never meant to come without renewal. Even the richest
soil was trusted to become still.
I wonder when we stopped extending ourselves the same kindness. Somewhere
along the way, rest became something we earned. Something reserved for
burnout. As though exhaustion were proof that we'd worked hard enough. The
earth was never asked to wait that long.
Maybe we've misunderstood what rest is. Not a reward. Not an interruption.
Not time lost. Perhaps it has always been part of the work itself. Just as
winter belongs to the tree, rest belongs to growth.
You are not a field in constant harvest. Some seasons ask you to bloom.
Others ask you to become quiet beneath the surface. Neither season is more
valuable than the other. Roots grow in both.

Example C (withholds the anchor one beat, one restrained turn):
Before she left for the date, her grandmother pressed a coin into her palm.
Not for anything, she said. Just in case.
It had a name — mad money. Kept separate from whatever a man might pay for
that night, hidden in a shoe or sewn into a hem. Enough for a cab home.
Enough to never need to ask.
It wasn't much, most of the time. A dime, later a dollar. It didn't need to
be much. It only needed to exist.
What no one tells you: it was never really about the money. It was about the
night never being able to trap you in it.
The coin usually came home unspent. It didn't need spending to have done its
job. It just needed to be there.

Example D (withholds the anchor one beat, one restrained turn):
She used to call most nights around eleven, no real reason, no agenda. I'd
pick up mid-thought and somehow already know what she needed before she got
to the point.
There's a word for that kind of understanding — the kind that arrives before
you've had to ask for it. In Japanese, it's called amae.
A psychiatrist spent years trying to explain it. He traced it all the way
back to infancy — to a mother reading her child's needs before the child even
has language for them.
What no one tells you: amae only survives if both people stay who they were.
Somewhere in the growing, the calls stopped landing the way they used to.
The understanding didn't leave because it wasn't real. It left because I'd
become someone it hadn't met yet.

The anchor field must contain only your final chosen anchor, a few words, no
reasoning or alternatives — do your comparison silently, output only the result.

Output as JSON:
{
  "anchor": "<the specific real thing this piece is built around, in a few words>",
  "slides": ["<paragraph 1>", "<paragraph 2>", ... 4 to 7 total, however many
  beats this specific story genuinely needs — do not pad to fill, do not
  compress two beats into one slide to stay short],
  "conversation_question": "<one genuine, open question tied directly to this
  story, for the reader to sit with>",
  "caption": "<a full second telling of the same story in flowing prose,
  elaborating rather than summarizing the same arc, may add one new
  authentic personal-feeling detail the slides didn't have room for>"
}

Topic: {topic}
```

---

## 7. The GPT-suggestion evaluation — what got adopted, what got declined, and why

Before any variant was built as a separate file, a set of suggestions
(sourced externally, referred to here as "GPT's suggestions") were evaluated
against what real testing had already surfaced.

**Adopted, folded directly into the active POC prompt above:**

- **Anchor as its own JSON field.** Previously the anchor was implicit in the
  prose; making it explicit (`"anchor": "..."`) is what made every anchor-
  level bug in this document (repetition, fabrication) *directly observable*
  rather than something that had to be inferred by re-reading the slides.
- **A named-cliché forbidden list.** "You are enough," "choose yourself,"
  "protect your peace," and the rest — a concrete, checkable list rather than
  a vague "don't sound like an Instagram wallpaper" instruction.
- **Multi-candidate anchor verification, scaled down.** GPT's original
  proposal scored every anchor candidate on six explicit axes (novelty,
  visual imagery, research richness, emotional resonance, metaphor strength,
  memorability) and picked the top scorer. The adopted version (rule 2 in
  the prompt above) keeps the "generate several real candidates, discard the
  ones you're not confident about" mechanism but drops the explicit
  multi-axis scoring rubric — just "is this genuinely real and documented,"
  not "does this score well on six dimensions." Section 8 below is the
  direct empirical reason that scaling-down decision held up.

**Declined, and not folded in anywhere:**

- **A silent Editorial QA checklist.** GPT's proposal included a structural
  self-check step run silently before returning output (this shape survives,
  scaled down, as rule 9's own "before finalizing, check each adjacent
  pair..." diagnostic — but a full separate QA pass was declined).
- **The full invisible-workflow architecture** — brainstorm 8-12 candidates,
  score every one, plan an explicit emotional-journey staging, then write.
  **Rejected as structurally identical to critique/refine** — the production
  carousel prompt's own draft→critique→refine loop is exactly this shape
  (a hidden evaluation pass judging a hidden draft against a rubric), and
  that architecture was already directly implicated in Section 2's
  diagnosis: eight rounds of it produced fixes that held structurally while
  real-output review kept finding voice-quality problems no rule caught.
  Every real bug found in this entire POC effort — the stress crab, the
  Yorkshire moon ledger, the Persian flaw, the Damascus apprentice ladder,
  the lamplighter's "medieval" mislabel, the anchor-field leak, the
  duplicate-beat pairs — was caught by **direct human or CC reading of the
  actual generated prose**, never by anything checklist- or rubric-shaped.
  Building more invisible-checklist machinery, even a cleverer one, was
  judged unlikely to fix a problem that structural machinery has already
  been shown not to fix. This reasoning was not left untested — Section 8
  is the actual A/B test built specifically to check whether this reasoning
  was right.

---

## 8. The GPT-architecture variant — built, A/B tested, and rejected

**What it was.** A second, fully separate system prompt
(`backend/app/poc/prompt_gpt_variant.py`) implementing GPT's *complete*
proposed architecture — the full version declined in Section 7, built anyway
so the rejection would rest on real data, not just reasoning:

- **Editorial-philosophy framing** — "You are not an Instagram copywriter.
  You are the Editor-in-Chief of Women's Growth Society."
- **An explicit editorial workflow**, run silently before writing: identify
  the emotional theme, brainstorm 8–12 real editorial anchors, **score every
  anchor on six explicit axes** (novelty, visual imagery, research richness,
  emotional resonance, metaphor strength, memorability) and choose the
  strongest, then plan an explicit five-stage emotional journey (Curiosity →
  Discovery → Understanding → Recognition → Quiet resonance) before writing
  a word.
- **A light structural self-check** before returning JSON — one anchor only,
  4–7 distinct beats, no adjacent-slide repeats, no obvious cliché, ending
  echoes the opening, valid JSON — explicitly scoped as *not* factual
  verification.

**Why it was built.** To test GPT's proposed architecture head-to-head
against the direct-write prompt on real output, rather than resting the
Section 7 rejection on reasoning alone.

**How it's wired.** `run_poc_writer()` (`backend/app/poc/writer.py`) takes a
`variant` parameter (`"current"` default, or `"gpt"`), threaded through
`scripts/poc_writer.py`'s `--variant` flag and `POST /poc/generate`'s
`variant` request field. Selecting `"gpt"` does not touch `prompt.py` in any
way — confirmed by direct inspection and by the fact that every existing
caller's behavior is unchanged (default remains `"current"`).

**The result: rejected**, based on real A/B data — 3 of 5 planned topics
completed (Self-Doubt, Pay-scale, Quirky/Fun; Sleep and Motivational were not
reached) before an Anthropic API credit/billing issue blocked further calls.
This is explicitly a **partial-data comparison, not an exhaustive one** — the
credit issue is an account/billing matter unrelated to the app itself, not a
bug in either prompt or in the harness. The signal from the 3 completed
topics was strong enough to act on regardless:

- **The GPT variant produced worse anchor repetition than the active
  prompt.** 3 of 3 GPT outputs converged on the same anchor — kintsugi —
  versus 1 of 3 for the current prompt on the identical three topics. Two of
  the three GPT outputs opened with near-verbatim repeated prose:

  > Self-Doubt: "In fifteenth-century Japan, a shogun is said to have sent a **damaged** tea bowl back to China for repair. It returned **bound with** ugly metal staples. Dissatisfied, local craftsmen **searched for a better way** —"
  >
  > Quirky/Fun: "In fifteenth-century Japan, a shogun is said to have sent a **cracked** tea bowl back to China for repair. It returned **held together with** ugly metal staples. Dissatisfied, local craftsmen **came up with something else entirely**."

- **It did not measurably fix any of the four issues found in live UI
  testing** — flat/un-intimate openings, short-piece compression, a
  slide-vs-caption quality gap, and anchor repetition. On the completed
  sample it **worsened** two of the four (repetition, as above, and opening
  flatness — all three GPT openings were impersonal historical/institutional
  exposition, versus the current prompt's mix of that and genuine
  withhold-the-anchor scene-setting). The other two (compression,
  slide-vs-caption gap) weren't cleanly differentiated either way on this
  small sample — neither variant produced a 4-slide result, and no
  meaningful quality gap between slides and captions showed up in either.

**The working hypothesis for why**, offered as a plausible mechanism, not a
proven one: GPT's own explicit six-axis scoring rubric (novelty, visual
imagery, research richness, emotional resonance, metaphor strength,
memorability) likely converges on whichever anchor scores highest *by that
rubric's own design*, rather than diversifying choices across calls. Kintsugi
scores well on essentially all six axes simultaneously — real, visually
striking, richly documented, emotionally symbolic, metaphor-dense, and
memorable — which is plausibly exactly why an explicit multi-axis "pick the
strongest" step keeps re-selecting it as the objectively correct answer.
Explicit scoring may have made repetition *worse*, not better, versus simply
asking for real-and-confident (the adopted, scaled-down version in the
active prompt's rule 2).

**The trigger-condition data — useful regardless of the variant's
rejection.** Six proposed QA-trigger conditions were checked against all 3
completed GPT outputs:

| Condition | Fired |
|---|---|
| Anchor includes a foreign-language word | 2/3 |
| Anchor includes a historical claim | **3/3** |
| Anchor includes a named person or study | 0/3 |
| Piece contains a factual explanation | **3/3** |
| Two slides are semantically similar | 1/3 |
| Ending introduces a new idea rather than echoing the opening | 2/3 |

Two of the six — "historical claim in anchor" and "factual explanation
present" — fired on every single output. For this brand's content
specifically, which leans on historical/cultural anchors *by design* (the
entire v1/v2 lineage is built on exactly this move), those two conditions
are too broad to do useful filtering. A "run QA only when triggered" system
built around this condition set would fire on nearly every real generation,
making it functionally equivalent to running QA on everything — which is,
again, the critique/refine shape already rejected in Section 7.

**Current state of both prompt files.** `backend/app/poc/prompt.py` is the
active prompt — used by every default call to `run_poc_writer()`, the
script, and the route. `backend/app/poc/prompt_gpt_variant.py` is **kept in
the codebase for reference, not deleted, and not used going forward** — the
same practice this project uses for other paused/rejected approaches (see
`docs/logbook.md` #26 for the precedent). Its own file header now states
this directly, not just this document.

---

## 9. The gpt-5.5 default-provider decision

A second, optional model backend — `gpt-5.5` via OpenAI, isolated behind its
own `OPENAI_API_KEY_POC` environment variable and its own module
(`backend/app/poc/openai_provider.py`) — was added alongside the original
Claude/Sonnet path. It sends the exact same, unmodified system prompt content
from `backend/app/poc/prompt.py` (Section 6 above) to `gpt-5.5` via OpenAI's
structured/JSON-schema output mode, so the two providers are a genuine
apples-to-apples comparison: same prompt, same instructions, only the model
underneath changes.

**A/B tested on 5 real topics** — Self-Doubt, Pay-scale, and Perfectionism
(direct head-to-head against real, already-captured Claude output on the
identical topics) plus two fresh topics (Sleep, Motivational). Before any
trial ran, `gpt-5.5` accessibility was explicitly confirmed via a
`models.retrieve()` call — no assumption, no silent fallback to a different
model.

**Result: gpt-5.5 is now the default POC provider**, changed in
`run_poc_writer()`, the script's `--provider` flag, and
`POST /poc/generate`'s request body — all three now default to `"openai"`.
This is a decision made on real evidence, not a workaround for the Anthropic
credit issue that blocked the GPT-architecture-variant testing in Section 8:

- **It avoided two unhedged/questionable-anchor failures Claude produced on
  identical topics.** On Pay-scale, Claude's anchor — "medieval guild
  journeyman wage ladders" — was a specific, unhedged institutional claim in
  the same shape as the Damascus-apprentice-ladder failure (Section 10).
  gpt-5.5's anchor for the same topic — the actual U.S. federal **General
  Schedule pay table** — is not even a historical claim; it's a live,
  checkable, contemporary system. On Perfectionism, Claude's anchor — "Persian
  rug weavers' deliberate flaw" — is the specific anchor flagged elsewhere in
  this document as possibly folklore rather than documented practice.
  gpt-5.5's anchor for the same topic — early printed-book errata pages — is
  uncontroversial, well-documented printing history.
- **It showed tighter beat-count discipline.** 6 slides in 3 of 5 trials,
  versus Claude's near-uniform landing at 7 across roughly 20 of 22 trials
  logged in this document (Section 10). The prompt's own rule 9 says "however
  many beats this specific story genuinely needs... do not pad" — gpt-5.5's
  willingness to stop at 6 tracks that instruction more literally than
  Claude's consistent maxing-out at 7.

**The Anthropic path is fully preserved, not removed or degraded.** Passing
`provider="anthropic"` explicitly (`--provider anthropic` on the script,
`"provider": "anthropic"` on the route) still works exactly as it did before
this default changed — confirmed by a mocked-call check showing the Claude
code path is byte-identical to before. This matters because Anthropic credits
will presumably be restored at some point, and the comparison started in this
section (and the rejected GPT-architecture variant in Section 8) may continue.

**Two findings, unresolved by the model switch — real, still open:**

1. **No trial from either model, across every round in this document,
   established a named, intimate relationship in its opening.** Both models
   consistently produce concrete, sensory, specific scenes (gpt-5.5's
   "phone face down" at 3:12, Claude's compass-calibration ritual) — but the
   *person* in that scene is always anonymous ("she," "he," "the
   proofreader," "a sailor"), never named, never placed in a relationship
   with someone else the way v1/v2's own reference examples do (the
   grandmother in the mad-money example, "she" and the narrator in the amae
   example). This is a real gap in both models' output relative to the
   reference material they're meant to be matching, not something switching
   providers fixed.
2. **A real cross-model anchor convergence was found.** gpt-5.5's Sleep trial
   landed on "first sleep and second sleep" — the identical underlying
   historical phenomenon as an earlier Claude trial's "segmented sleep" (a
   different topic_id, from several rounds earlier in this document). This
   wasn't a same-session repeat for either model individually — it's two
   independent models, on two different occasions, converging on the same
   well-known historical fact. This suggests the anchor-repetition problem
   (Section 11, `FINDINGS.md` #1) may not be purely a per-model quirk to
   route around by switching providers — there may be a small pool of
   maximally "famous," high-scoring anchors (kintsugi for Claude, first/second
   sleep for both) that any sufficiently capable model gravitates toward
   regardless of which one is asked. If true, a real fix needs to account for
   convergence across models, not just repetition within one model's calls.

---

## 10. Testing results summary across all POC rounds

Combined across every round of testing the direct-write POC prompt has been
through this session (not counting the GPT variant, covered separately
above), **22 real trials** total:

| Round | Prompt state | Trials | Bug 1 (fabricated/unhedged anchor) | Bug 2 (duplicate adjacent beat) |
|---|---|---|---|---|
| Sanity + first batch | Original prompt (no anchor field, no rule-2/9 rewrite) | 6 | 1/6 | not tracked yet |
| First rule-2/9 pass | Anchor field + original rule 2/9 added | 4 | 1/4 | 1/4 |
| Rule-2 rewrite | 3-candidate verification added | 4 | 0/4 clean fabrication (3/4 still repeated kintsugi) | 1/4 |
| Rule-9 tightened | Anchor-field-leak fix + rule-9 diagnostic + exclusion-list harness | 5 | 1/5 flagged + 1/5 nuanced (not clean fabrication) | 0/5 |
| GPT-variant A/B, current side | Fully current prompt | 3 | 1/3 | 0/3 |

**Specific examples, by name:**

- **The stress crab** (Wellness/Stress Regulation, earliest round) — a
  wholly invented-sounding Scandinavian fishing practice, stated as flat
  fact with no hedge. The clearest, earliest case of outright anchor
  fabrication.
- **The Yorkshire moon ledger** (Women's Health/Hormonal Cycle, same round)
  — checked carefully and found **not** a violation: the piece's specific
  claims were properly hedged throughout. Included here for the record, not
  as a bug — it's the contrast case showing the hedge mechanism working
  correctly even before rule 2 was rewritten.
- **The Persian flaw** (Career/Perfectionism, rule-9-tightened round) — a
  widely-circulated claim about intentional "humility" flaws in Persian rug
  weaving, stated with zero hedge; on reflection, genuinely uncertain
  whether this is a rigorously documented practice or popular folklore
  retroactively explaining ordinary weaving irregularities.
- **The Damascus apprentice ladder** (Career/Pay-scale, first rule-2/9 pass)
  — Damascus steel is real, but the specific formal apprentice→journeyman→
  master wage ladder attributed to it reads as a composite of a genuinely
  different, *European* guild tradition, stated as flat fact.
- **The lamplighter "medieval" mislabel** (Wellness/Burnout, rule-9-tightened
  round) — the underlying practice (a pole combining a wick-lighter and a
  snuffer) is real and documented; "medieval" is simply the wrong era
  (lamplighting is an 18th–19th-century gas/oil-lamp profession). A dating
  slip in the metadata, not a fabrication in the prose.

**The refined diagnosis.** Read across all five rounds in order, the
fabrication signature narrows as rule 2 tightens: early failures (the stress
crab) look like flat invention of the *entire* anchor. By the later rounds,
clean whole-anchor fabrication mostly disappears — what's left clusters
around **unverified reasons, motivations, or specific institutional details
attached to an anchor that is itself real** (the Persian flaw's "only the
divine is flawless" reasoning; the Damascus ladder's specific wage-posting
mechanics; the lamplighter's wrong era; the GPT-variant Pay-scale trial's
"medieval guild journeyman wage ladders," independently landing on the same
shape of problem). Remaining failures are not fabricated anchors — they're
real anchors with an unverified specific claim riding along with them. This
is a real, useful narrowing of the bug, not a claim that the bug is closed.

**Slide count, noted for completeness though never one of the two tracked
bugs:** the overwhelming majority of trials — roughly 20 of 22 — landed at
exactly 7 slides, the top of the allowed 4–7 range. Only two exceptions:
Pay-scale (original rule-2/9 prompt) at 6, and Quirky/Fun (GPT-variant A/B
round, current side) at 6. No 4-slide result has been produced by either
variant in any round to date.

---

## 11. Current state, explicitly

- The POC is committed and pushed, live at `/poc` on `wgs-studio.vercel.app`,
  backed by `POST /poc/generate` on the Railway backend.
- The first real UI test of the live `/poc` page surfaced a genuine layout
  bug — slides rendered squeezed side-by-side instead of one full slide with
  swipe/dot navigation, because the page's slide carousel was missing the
  `scroll-snap-type`/`scroll-snap-align` pattern every other carousel view in
  the app uses (`app/editor/page.tsx`). **Fixed** — `frontend/app/poc/page.tsx`
  now uses the identical scroll-snap pattern, verified against a faithful
  static reproduction of the fixed CSS/DOM (real session content, including
  the longest paragraph seen this session, at the smallest font tier) since
  the real authenticated `/poc` page sits behind `AuthGate` and wasn't
  directly drivable end-to-end from this session.
- **Anchor-repetition is a known, deliberately deferred gap** — the POC is
  stateless by design (Section 5), with no equivalent to the production
  pipeline's `MemoryRecord.fingerprint` non-repetition check. A manual,
  in-memory `recent_anchors` exclusion list exists as a test-harness stopgap
  only (`backend/app/poc/FINDINGS.md` #1) — not a resolution.
- **A "hedge attributed reasons/motivations" refinement was offered and
  deferred**, in favor of testing the UI first — the refined diagnosis in
  Section 10 (real anchors, unverified attached reasons) suggests rule 2 or
  rule 4 could be tightened further to specifically hedge the *reasoning*
  layered onto a real anchor, not just the anchor's existence. **Still
  open, not attempted.**
- The GPT-architecture variant is evaluated and rejected (Section 8),
  `prompt_gpt_variant.py` kept for reference only.
- **`gpt-5.5` (OpenAI) is now the default POC model provider** (Section 9),
  changed on real A/B evidence. Confirmed by direct trace, not assumed: the
  frontend (`frontend/lib/poc-api.ts`'s `generatePoc()`) sends only
  `{topic_id}` — no `provider` field at all — so the "Generate POC" button's
  behavior depends entirely on the backend default. A real, unmocked call
  through the route using that exact request shape returned genuine `gpt-5.5`
  output, confirming the button now reaches `gpt-5.5` without any frontend
  change. `provider="anthropic"` remains fully functional, unchanged, for
  explicit use.
- **Two findings from the gpt-5.5 A/B test are unresolved by the model
  switch** (Section 9): neither model has produced an opening with a named,
  intimate relationship (only anonymous, if concrete and sensory, scenes);
  and a real cross-model anchor convergence (gpt-5.5's "first/second sleep"
  vs. an earlier Claude trial's "segmented sleep") suggests anchor
  repetition may need a fix that accounts for convergence across models, not
  just within one.

---

## 12. What a fresh chat should pick up next

1. **Real UI testing of the POC**, now that the layout bug is fixed — this
   hasn't happened yet; every round of testing so far has gone through the
   script or route directly, not the live authenticated app.
2. **The eventual production-integration decision** — keep patching the
   production carousel prompt, replace it with the POC's direct-write
   approach, or land somewhere in between. **Not yet decided, explicitly
   open.** Section 5's finding (direct-write beat eight rounds of patching)
   is real evidence toward replacement, but it is evidence from an isolated
   POC under controlled test conditions, not from the production pipeline's
   actual constraints (mood/duotone imagery tagging, the taxonomy's
   coverage/non-repetition machinery, the six-template render contract) —
   those constraints haven't been re-evaluated against a direct-write
   approach at all yet.
3. **The deferred "hedge attributed reasons" refinement** (Section 11) is
   sitting there as a candidate next fix, informed by Section 10's refined
   diagnosis, if POC testing continues before the integration decision.
4. **Anchor repetition** still has no real fix, only the manual test-harness
   stopgap — worth real attention if the POC direction is chosen to continue
   past evaluation.
