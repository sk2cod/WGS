from pydantic import BaseModel

from .enums import Format, Sensitivity


class Topic(BaseModel):
    id: str
    name: str
    categories: list[str]             # multi-tagged — browsable under many
    primary_category: str              # the ONE category counted on the masthead
    tone_defaults: list[str]
    suitable_formats: list[Format]
    seed_angles: list[str]             # 3-5 example sub-concepts
    knowledge_hints: list[str] = []
    requires_citation: bool = False
    sensitivity: Sensitivity = Sensitivity.NORMAL
