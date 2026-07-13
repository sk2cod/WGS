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
