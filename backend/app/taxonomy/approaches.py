from app.models.enums import Approach

APPROACHES: list[str] = [a.value for a in Approach]

# Approaches whose content needs real teaching room get two carousel_body_teaching
# slides instead of one carousel_body — a single pre/script/post emphasis fragment
# can't hold the substance these approaches need, which is why real content kept
# landing in the caption instead. Drives both the default slide_count
# (engine/brief_builder.py) and the body-slot role (engine/generator.py).
TEACHING_BODY_APPROACHES: set[str] = {
    Approach.STORY.value,
    Approach.EDUCATIONAL.value,
    Approach.FRAMEWORK.value,
    Approach.MYTH_VS_FACT.value,
    Approach.COMMON_MISTAKES.value,
}

# single_image resolves to exactly one slide (single_quote for the poetic register,
# single_stat for the direct register — engine/generator.py:slide_roles_for), a shape
# that can't hold what checklist/myth_vs_fact/framework structurally require (an
# enumerable set of distinct items, a separate myth + fact, or named multi-part steps
# — see _APPROACH_DEFINITIONS in engine/generator.py). Investigated live: those three
# reliably produced extra, off-schema slides when forced onto single_image; educational
# shares the same multi-step tendency and failed intermittently (~1 in 4 trials). The
# four below never failed across repeated live trials — restricting single_image's
# sampled approach pool to just these avoids the mismatch at the source (the sampler),
# instead of leaving it to be caught — or not — after a wasted generation call.
#
# Split by which single_image template each half resolves to (APPROACH_REGISTER's
# poetic/direct split — see taxonomy/voice_register.py), so a caller can ask for one
# specific style ("Poetic Quote" / "Quick Stat") instead of a random one of the 4 —
# see logbook #28. SINGLE_IMAGE_SAFE_APPROACHES stays the union, unchanged, for the
# existing no-style-given callers.
SINGLE_IMAGE_QUOTE_APPROACHES: set[str] = {
    Approach.STORY.value,
    Approach.QUESTION_REFLECTION.value,
}
SINGLE_IMAGE_STAT_APPROACHES: set[str] = {
    Approach.COMMON_MISTAKES.value,
    Approach.STAT_RESEARCH.value,
}
SINGLE_IMAGE_SAFE_APPROACHES: set[str] = SINGLE_IMAGE_QUOTE_APPROACHES | SINGLE_IMAGE_STAT_APPROACHES

# Carousel-only "v1" content-voice experiment (logbook #39) — restricts carousel's
# sampled approach pool to just these two while the new connected-micro-essay arc
# instruction (engine/generator.py) is trialed. The other 6 approaches are untouched
# in code and remain fully reachable for single_image (SINGLE_IMAGE_SAFE_APPROACHES
# etc. above, unchanged) — this pool only ever gates carousel's sample_cell() branch.
# Experimental, pending real-output review — see logbook #39 before expanding or
# removing this restriction.
CAROUSEL_V1_APPROACHES = [Approach.STORY, Approach.QUESTION_REFLECTION]
