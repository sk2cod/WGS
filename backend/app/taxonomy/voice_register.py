from app.models.enums import Approach

# Which voice register (BrandKit.voice_samples.poetic | .direct) each approach draws from.
# "story" and "question_reflection" pull the poetic register; everything else is direct.
APPROACH_REGISTER: dict[str, str] = {
    Approach.STORY.value: "poetic",
    Approach.QUESTION_REFLECTION.value: "poetic",
    Approach.EDUCATIONAL.value: "direct",
    Approach.MYTH_VS_FACT.value: "direct",
    Approach.CHECKLIST.value: "direct",
    Approach.STAT_RESEARCH.value: "direct",
    Approach.FRAMEWORK.value: "direct",
    Approach.COMMON_MISTAKES.value: "direct",
}
