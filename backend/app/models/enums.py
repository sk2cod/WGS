from enum import Enum


class Format(str, Enum):
    CAROUSEL = "carousel"
    SINGLE_IMAGE = "single_image"


class Approach(str, Enum):
    EDUCATIONAL = "educational"
    MYTH_VS_FACT = "myth_vs_fact"
    CHECKLIST = "checklist"
    STORY = "story"
    STAT_RESEARCH = "stat_research"
    QUESTION_REFLECTION = "question_reflection"
    FRAMEWORK = "framework"
    COMMON_MISTAKES = "common_mistakes"


class EntryPoint(str, Enum):
    A_MISTAKE = "a_mistake"
    A_QUESTION = "a_question"
    A_CONTRARIAN_TAKE = "a_contrarian_take"
    A_STAT = "a_stat"
    A_RELATABLE_MOMENT = "a_relatable_moment"


class Sensitivity(str, Enum):
    NORMAL = "normal"
    HEALTH = "health"
    SENSITIVE = "sensitive"
