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
insufficient (Section 7 and Section 12 below).

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
By the caption's second beat at the latest, include at least one clause,
phrase, or beat that gestures toward the reader's own life — a single
wondering, comparison, or echo is enough; you do not need to explain the
connection yet, only signal that one is coming. Before finalizing, check:
does the caption's first or second beat contain that signal? If the caption
stays entirely inside the anchor's own history, mechanics, or terminology
through its third beat with no such signal anywhere yet, add one now rather
than waiting for later. Whichever beat carries this signal will end up as
slide 1 or 2 once the caption is split — that's what makes it count.

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
lead with a title. Prefer a role only ("a psychiatrist," "a marine
biologist," "a historian") over a real name. A named, real researcher turns
the moment into a citation rather than a discovery, even when delayed. Only
name someone when their specific identity is itself part of why the anchor
matters.

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

9. The piece needs to actually travel: 4 to 7 real distinct beats, built into
the caption itself. Every beat must do a genuinely different job than the one
before it (for example: curiosity, then the anchor revealed, then why it
mattered, then a turn toward the reader, then the emotional truth, then an
echo of the opening — not every piece needs all of these, and not in this
exact order, but each beat must move the piece somewhere new). Never spend
two consecutive beats making substantially the same point in different words
— if that happens in the caption, cut one before you ever get to splitting it
into slides. Do not pad the caption with more beats than the content
genuinely earns. Before finalizing, check each adjacent pair of beats in the
caption: does the second one state a claim, or restate the one before it
using different words? If it's a restatement, cut it or replace it with
something that adds new ground. Get this right in the caption and the slide
split inherits it for free — there is no separate distinctness check to do
once you reach the slides.

10. Any biographical or factual detail you can't be fully certain of gets a
soft hedge ("said to," "known as," "believed to") rather than stated as flat
fact.

11. Write like a storyteller pulling the reader into one real scene, never
like an essay addressing an audience. Stay inside one specific person's
experience or one confident, unaddressed observation — never generalize the
reflective turn to a demographic or group ("I wonder how many women feel
this," "so many of us," "many people know this"). The universal feeling
should arrive because the specific detail was true, not because you named
who else might relate to it. Avoid hedged, invitational phrasing that
gestures at an undefined reader ("if you looked closely, you might
notice...," "you may have noticed...") — state what's true directly and
trust the detail to carry its own weight.

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
than force. I wonder if this is closer to what a boundary is supposed to feel
like.
Not walls built in fear. Not battles waiting to happen. Just a gentle way of
saying, "This part of me deserves care."
Somewhere along the way, I learned that protecting my peace required an
explanation. That "no" should sound kinder. That "not now" should
come wrapped in guilt. As though my boundaries needed permission before they
could exist.
But the rope never explains itself. It doesn't convince. It doesn't
apologise. It simply knows what it is protecting. Perhaps that's why it is
respected.
Maybe that's the invitation. To stop building walls so high that no one can
reach me... and begin placing ropes clear enough that people know how to meet
me. The strongest boundaries don't always push people away. Sometimes they
simply show people how to come closer — with care.

Example B (names the anchor after one beat of scene-setting):
Imagine if the earth was given permission to rest. Not after it failed. Not
after it was exhausted. Simply because rest was considered part of living
well. Thousands of years ago, it was.
In an ancient Hebrew tradition, every seventh year the land was left
untouched. No planting. No harvesting. No asking it for one more season. This
practice was called Shmita. A permission the earth received without
asking — the kind I still find hard to give myself.
The land wasn't resting because it had stopped being useful. It rested
because usefulness was never meant to come without renewal. Even the richest
soil was trusted to become still.
I wonder when I stopped extending myself the same kindness. Somewhere
along the way, rest became something I had to earn. Something reserved for
burnout. As though exhaustion were proof that I'd worked hard enough. The
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

Write the caption before the slides. The caption is the real piece — write it
exactly as you would if slides didn't exist, one continuous flowing telling,
start to finish, with the beat structure rule 9 describes built into its own
sentences. Only once that full caption exists do you make the slides, and
making them is a split, not a second draft: group the caption's own
sentences into 4 to 7 slide-sized pieces, breaking at the caption's own
natural pauses — the moments where one beat ends and the next begins. Use
the caption's exact wording. Do not reword, rewrite, summarize, or add new
lines. You may trim a leading connective word or phrase that only made sense
immediately after the sentence before it (an opening "That," "So," or "But"
depending on what came right before), but otherwise the slides are the
caption, split.

Output as JSON:
{
  "anchor": "<the specific real thing this piece is built around, in a few words>",
  "caption": "<the full piece, written first, start to finish, in flowing
  prose — the real first draft, not a summary of anything that comes later>",
  "slides": ["<paragraph 1>", "<paragraph 2>", ... 4 to 7 total — the caption
  above split at its own natural pauses, using its exact wording, not
  reworded or rewritten],
  "conversation_question": "<one genuine, open question tied directly to this
  story, for the reader to sit with>"
}

Topic: {topic}
```

**A technical note on how `caption`-before-`slides` is actually enforced, not
just suggested:** `POST /poc/generate`'s default provider (`gpt-5.5`, Section
9) uses OpenAI's structured/JSON-schema output mode, and that mode generates
fields in the order they're declared in the schema's `properties` object —
so the field order above isn't just prose the model is free to ignore, it's
mechanically enforced by `backend/app/poc/openai_provider.py`'s
`POC_RESPONSE_JSON_SCHEMA`, whose `properties` dict is kept in sync with this
template (`anchor`, `caption`, `slides`, `conversation_question`, in that
order). The Anthropic path has no equivalent enforcement — there, the field
order above is only ever a strong suggestion via the example template, not a
hard guarantee. Section 11 covers why this ordering exists and what it fixed.

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
  the same shape as the Damascus-apprentice-ladder failure (Section 12).
  gpt-5.5's anchor for the same topic — the actual U.S. federal **General
  Schedule pay table** — is not even a historical claim; it's a live,
  checkable, contemporary system. On Perfectionism, Claude's anchor — "Persian
  rug weavers' deliberate flaw" — is the specific anchor flagged elsewhere in
  this document as possibly folklore rather than documented practice.
  gpt-5.5's anchor for the same topic — early printed-book errata pages — is
  uncontroversial, well-documented printing history.
- **It showed tighter beat-count discipline.** 6 slides in 3 of 5 trials,
  versus Claude's near-uniform landing at 7 across roughly 20 of 22 trials
  logged in this document (Section 12). The prompt's own rule 9 says "however
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
   (Section 13, `FINDINGS.md` #1) may not be purely a per-model quirk to
   route around by switching providers — there may be a small pool of
   maximally "famous," high-scoring anchors (kintsugi for Claude, first/second
   sleep for both) that any sufficiently capable model gravitates toward
   regardless of which one is asked. If true, a real fix needs to account for
   convergence across models, not just repetition within one model's calls.

---

## 10. The storyteller-voice tightening — rules 1, 4, 11, and the Shimenawa/Shmita edits

Real-output review (not inference — actual generated pieces read line by
line) surfaced a failure mode distinct from anchor fabrication or duplicate
beats: pieces that were factually sound and structurally correct but still
read like an explainer addressing an audience instead of a story pulling a
reader in. Three concrete examples, from real generations, drove this:

- **A dolphin-themed piece's second sentence:** *"If you looked closely, you
  might notice one eye still open."* A cold reader has no context yet for who
  "you" is — the line reads as documentary-voiceover invitation ("notice
  this"), not observed scene, and the double hedge ("if... might") undercuts
  what should be the sentence's sharpest detail rather than letting it land
  as fact.
- **An attachment-theory piece naming a real researcher directly:**
  *"Mary Ainsworth and her colleagues used it to observe..."* — turning a
  discovery into a citation, unlike every locked reference example, which
  either omits the person entirely or describes them by role only ("a
  psychiatrist," in amae).
- **The same piece generalizing its reflective turn to a demographic:**
  *"Somewhere along the way, many of us kept that room inside us."* This
  exact pattern — "I wonder how many women," "many of us," "so many people"
  — turned up independently in a second, unrelated piece too (a dolphin/rest
  piece: *"I wonder how many women know this posture"*), confirming it was a
  real recurring pattern, not a one-off.

**Three prompt changes, in order of how directly they trace to the evidence
above:**

- **Rule 4 tightened** to prefer a role only ("a psychiatrist," "a marine
  biologist," "a historian") over naming a real researcher, unless the
  person's specific identity is itself part of why the anchor matters.
- **New rule 11** added, banning both patterns at once: demographic
  generalization of the reflective turn, and hedged/invitational phrasing
  addressed to an undefined reader.
- **Rule 1 extended**, twice. First pass: a soft note that the reader should
  "sense within the first slide or two" that the piece connects to their
  life. Testing found this didn't move anything — real trials on Attachment
  Styles, Hormonal Cycle, and Boundaries all still delayed their actual
  reader-bridge to slide 4–5 of 6–7, identical to before the soft version was
  added. Second pass: a hard slide-2 ceiling with an explicit self-check
  (mirroring rule 9's already-proven duplicate-beat diagnostic pattern) —
  *"By slide 2 at the latest, include at least one clause, phrase, or beat
  that gestures toward the reader's own life... Before finalizing, check:
  does slide 1 or 2 contain that signal?"*

**Testing, in rounds, reported plainly rather than rounded up:**

1. **Rules 4 and 11 held cleanly from the first trial on** — zero violations
   across every round of testing this section covers (12 of 12 trials total,
   spanning three separate testing rounds and six different topics).
2. **Rule 1's hard version still didn't move the needle on its own.** Same
   three topics, re-tested: the explicit reader-bridge landed at the
   identical slide number as before the tightening, every single time
   (Attachment Styles: slide 5 of 7 both times; Hormonal Cycle: slide 4 of 6
   both times; Boundaries: slide 4 of 7 both times). Wording alone wasn't the
   lever.
3. **The real lever turned out to be the locked reference examples
   themselves.** Two of the four — Shimenawa and Shmita, both carried
   forward from v1 — still contained the exact patterns rule 11 now forbids
   (*"many of us learned..."*, *"we stopped extending ourselves..."*) and
   neither demonstrated an early reader-signal for rule 1. mad money and
   amae were already fully compliant with both and needed no changes.
   Shimenawa and Shmita were edited: their collective "many of us"/"we"
   language was converted to first-person "I," and each gained one added
   clause at its own natural slide-2 point (Shimenawa: *"Sometimes meaning is
   stronger than force. I wonder if this is closer to what a boundary is
   supposed to feel like."*; Shmita: *"This practice was called Shmita. A
   permission the earth received without asking — the kind I still find hard
   to give myself."*). mad money and amae were left untouched.
4. **Re-tested after the example edits: real, direct improvement, not
   universal.** Attachment Styles immediately picked up the technique —
   *"There are grown-up versions of this moment: the unanswered text, the
   closed office door, the shift in someone's voice"* — landing exactly at
   slide 2, a direct echo of the edited Shimenawa example's shape. Boundaries
   and Hormonal Cycle didn't move on the same round (still stuck at slide 4),
   because only one example (Shimenawa) demonstrated the technique and its
   shape happened to match Attachment Styles' structure specifically. Editing
   *Shmita* too — a structurally different anchor (a practice/tradition, not
   an interrupted-scene shape) — generalized the fix: on the next round,
   Boundaries produced a clean slide-2 hit (*"I think of it when I have
   mistaken being clear for becoming hard"*) and Hormonal Cycle improved from
   a faint implicit hint to a real, if still-not-fully-explicit, early
   gesture. Net result across every round: rule 1 went from 0-of-3 topics
   showing an early signal, to 2-of-3 clean plus 1 partial after both example
   edits. Real, demonstrated, not guaranteed — the same reliability profile
   every other rule in this prompt has shown under testing, not a special
   exception.

**Shipped** as commit `a542c18` ("Tighten POC prompt: storyteller voice,
earlier reader signal, no named citations"). Full backend suite (127/127)
unaffected throughout — this is prompt-text-only work; no route, script, or
provider code changed.

---

## 11. The caption-first restructuring — slides as a mechanical split of the caption, not a second draft

**The question that started this:** across nearly every round of testing
logged in this document, captions consistently read better than slides —
richer imagery, more varied sentence rhythm, cleaner transitions. Direct
comparison made the reason legible: the original schema asked for `slides`
before `caption`, and the caption's own instruction was *"a full second
telling... elaborating."* Since JSON fields generate in order, the model was
always writing the caption second, with the entire arc already decided —
functionally a revision, written with hindsight the slides never got. Slides
also carried more simultaneous constraints than the caption ever did (rule
9's beat-distinctness check, rule 1's slide-2 signal placement, each slide
needing to stand alone as a swipeable unit), which left less room for the
caption's fluid, cumulative sentence rhythm.

**First attempt: reorder the schema, ask slides to "reshape" the caption.**
`caption` moved before `slides` in both `backend/app/poc/prompt.py`'s prose
template *and* `backend/app/poc/openai_provider.py`'s
`POC_RESPONSE_JSON_SCHEMA` — the schema reorder isn't cosmetic on the
`gpt-5.5` path specifically, since OpenAI's structured-output mode enforces
generation order from the schema's own `properties` order, unlike the
Anthropic path, which only ever follows the prose template as a strong
suggestion (see the technical note at the end of Section 6). Verified the
order flip actually happened by checking literal byte position of `"anchor"`
< `"caption"` < `"slides"` in the raw response text, not just the parsed
JSON — confirmed 3 of 3 real trials.

Slide quality genuinely improved. But real-output review surfaced two
side effects:

1. **Inconsistent reshaping.** 1 of 3 trials copied the caption verbatim
   into slide-sized chunks; the other 2 reworded or added material while
   "reshaping" as instructed — an unpredictable mix, same reliability
   pattern as everything else in this prompt, but specifically undesirable
   here since the goal was consistency.
2. **One trial used embedded double-line-breaks inside a single slide** for
   rhythmic effect (three short beats separated by blank lines within one
   JSON string). `frontend/components/slides/PocParagraphSlide.tsx` doesn't
   set `white-space: pre-line`, so this formatting choice would have
   silently collapsed to plain spaces in the actual rendered app — a real,
   if minor, mismatch between what the model produced and what the UI could
   show. This concern became moot once the final fix below removed slides'
   ability to invent their own internal structure at all.

**The actual fix, prompted by direct pushback on the premise itself:**
rather than accepting "reshape" as a second creative pass with its own
judgment calls, the question was asked directly — why does a derived
artifact need independent rules at all, if the source it's derived from is
already good? The answer: it doesn't. `backend/app/poc/prompt.py` was
rewritten so slides are explicitly **a mechanical split, not a rewrite**:
*"Use the caption's exact wording. Do not reword, rewrite, summarize, or add
new lines... otherwise the slides are the caption, split."* Rules 1 and 9
were retargeted in the same pass to describe the **caption's** internal
structure (its beats, its early signal) rather than the slides' — since
slides no longer have independent structure to check, they inherit
whatever the caption already has.

**Verified, real trials, byte-for-byte:** re-ran three topics (Burnout,
Attachment Styles, Motivational). Every single slide in every trial matched
its corresponding caption paragraph **character for character** — no
rewording, no additions, no exceptions. Both side effects from the first
attempt resolved as a direct consequence: reshaping inconsistency is gone
because there's nothing left to reshape, and the embedded-line-break
formatting issue didn't recur because slides no longer invent structure the
caption doesn't already have. Rules 4 and 11 held clean across all three
(no named researcher, no demographic language). Rule 1's early-signal hit
rate was unchanged from Section 10's finding (2 of 3 clean, matching the
established reliability profile) — this restructuring targeted the
caption/slide quality gap specifically, not rule 1's own reliability, and
correctly didn't move that number either way.

**Shipped** as commit `81c632d` — verified live on Railway, byte-identical
caption/slide output confirmed via a real production call.

**Round 2, prompted by direct pushback on the shipped result itself:**
immediately after confirming the byte-identical split live, the question was
asked directly — *"why is caption and slide content exactly same? caption
needs to be a different perspective right?"* This was a legitimate
correction, not a restatement of the original complaint. On a real Instagram
post, slides and caption are both visible in the same viewing session — a
reader swipes the carousel, then reads the caption right below it. Making
them byte-identical solved the quality gap by deleting the distinction
between the two artifacts, not by making slides good as their own retelling;
it also contradicted the caption's own original design intent (a "second
telling," not a copy).

**The fix:** kept caption-first (that part was correct — drafting the
caption first, with full-arc hindsight, is what actually fixed quality,
independent of the verbatim-copy question). Replaced the "use the caption's
exact wording, do not reword" instruction with the opposite requirement:
slides must retell the same beats, same anchor, same order the caption
already established, but each one **rewritten fresh for its own screen** —
explicitly flagged as wrong if a slide sentence matches the caption's wording
closely. This is not simply reverting to the first attempt's "reshape, don't
cut" instruction from earlier in this section — that version never
explicitly forbade verbatim reuse, which is the most likely reason 1 of 3
trials copied wholesale anyway; this version makes reuse an explicit,
named failure mode to self-check against, the same pattern rule 1 and rule 9
already use elsewhere in this prompt.

**Verified, real trials:** re-ran three fresh topics (unsent letters,
learning to say no, grief that shows up years later). All three produced
slides that preserved the caption's beats, images, and order while using
distinct sentence construction in every slide — no verbatim or
near-verbatim sentence reuse in any trial. Rule 9's beat-distinctness
check still holds under this change without modification: it operates on
beat/idea distinctness, not literal wording, so rewording a beat for its
own slide doesn't reintroduce a duplicate-beat problem as long as the same
underlying beat structure is preserved.

**Not yet shipped as of this writing** — tested and ready; see Section 13
for exact current state.

---

## 12. Testing results summary across all POC rounds

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

## 13. Current state, explicitly

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
  Section 12 (real anchors, unverified attached reasons) suggests rule 2 or
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
- **The storyteller-voice tightening (rules 1, 4, 11, plus the
  Shimenawa/Shmita example edits) is shipped** (Section 10), commit `a542c18`.
  Rules 4 and 11 held with zero violations across every trial tested (12 of
  12). Rule 1's early reader-signal is real but not universal — 2 of 3 fresh
  topics clean, 1 partial, the same reliability profile every other rule in
  this prompt has shown, not a special case.
- **The caption-first restructuring shipped as commit `81c632d`** (Section
  11), then was revised once more on real feedback the same session — the
  first shipped version made slides byte-identical to the caption, which
  closed the quality gap but deleted the caption's own reason to exist
  (both are visible in the same Instagram viewing session; identical text
  reads as redundant, and it contradicted the caption's original "second
  telling" design intent). The revision keeps caption-first (proven to fix
  quality) but requires slides to retell the caption's beats in fresh
  wording rather than copy them. Verified across three real trials — same
  beats/anchor/order as the caption, no verbatim or near-verbatim sentence
  reuse in any trial. **Tested and ready, not yet shipped as of this
  writing.** Whoever picks this up next should confirm via `git log` and
  `git status` whether it has since been committed and pushed — this line
  needs the same close-the-loop update the project's own logbook discipline
  requires if it's stale by the time it's read.
- **Punctuation/pacing and selective slide line breaks are tested and ready,
  not yet shipped** (Section 14) — rules 12/13 added to `prompt.py`,
  `PocParagraphSlide.tsx` updated to render line breaks. Same
  not-yet-shipped status and close-the-loop caveat as the bullet above.

---

## 14. Punctuation/pacing and selective slide line breaks

**The ask:** direct feedback that slides needed grammatical/punctuation
polish for reading rhythm (correct pauses, emphasis), plus the ability to
use a line break inside a slide when one genuinely aids pacing.

**Punctuation (rule 12):** a new rule instructing periods for real stops,
commas only for a light breath within one continuous thought (never splicing
two complete sentences), em dashes for a turn or reveal, and breaking a
long multi-clause sentence into two rather than stacking commas. Framed as
"read it back aloud" self-check, matching the pattern the rest of this
prompt already uses for anything that needs to hold reliably.

**Line breaks (rule 13) — needed one round of tightening.** The first
version allowed a slide to use a line break "sparingly, at most once or
twice across all the slides in a piece." Real trials showed this doesn't
hold as a soft instruction: one topic ("setting boundaries with family")
used line breaks in 3 of 5 slides, another ("imposter syndrome at work")
used them in 5 of 6 — the model treated the option as a default stylistic
device rather than a rare one, the same failure mode soft instructions have
shown everywhere else in this prompt (rule 1 needed the same hardening in
Section 10). Rewritten as a hard cap with an explicit count-and-check step:
**at most one line break in the entire piece, across every slide combined**,
only for a single-word or few-word phrase that has earned standing
completely alone, with an instruction to count every line break before
finalizing and cut down to the strongest one (or none). Re-ran both topics
after the fix — zero line breaks in either, which is compliant (the rule
allows zero-to-one, and "most pieces should use zero" is the explicit
guidance) but means this round of testing didn't produce a positive example
of the capability actually firing. Worth a specific eye on this the next
time real trials run, to confirm it can still produce one when a phrase
genuinely earns it, not just suppress it entirely.

**Frontend fix, not just a prompt change.** `PocParagraphSlide.tsx` — the
component the live `/poc` page uses to preview slides — did not set
`white-space: pre-line`, so an embedded `\n` in slide text would have
silently collapsed to a space rather than rendering as a break. Added
`whiteSpace: "pre-line"` to the slide's text `<span>`. This component
renders as a plain React/DOM element directly in the browser (confirmed by
checking `frontend/app/poc/page.tsx` — no `/api/render` or Satori call
anywhere in the POC's frontend path), unlike the production pipeline's slide
templates, which render through Satori (`@vercel/og`) and have their own,
separate set of CSS-subset constraints (see `CLAUDE.md`'s rendering note).
Standard CSS `white-space` support applies cleanly here with no equivalent
risk.

**Verified, real trials:** four fresh topics run after both rule 12 and the
tightened rule 13 (boundaries with family, imposter syndrome at work, plus
the two from the line-break-tightening re-run). Punctuation read cleanly in
every trial — no comma splices, no run-on sentences, appropriate em dash use
for turns. No line breaks fired in any of the post-fix trials, consistent
with the new hard cap.

**Not yet shipped as of this writing** — tested and ready; see Section 13
for current-state status.

---

## 15. What a fresh chat should pick up next

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
3. **The deferred "hedge attributed reasons" refinement** (Section 13) is
   sitting there as a candidate next fix, informed by Section 12's refined
   diagnosis, if POC testing continues before the integration decision.
4. **Anchor repetition** still has no real fix, only the manual test-harness
   stopgap — worth real attention if the POC direction is chosen to continue
   past evaluation.
5. **Rule 13's line-break cap has only been verified at zero** (Section 14)
   — every post-fix trial produced zero line breaks, which is compliant but
   untested at the "exactly one, well-placed" end of what the rule allows.
   Worth watching for a genuine positive example in a future round, not just
   confirming it stays suppressed.
