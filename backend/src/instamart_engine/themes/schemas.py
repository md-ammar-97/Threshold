"""Theme naming/summarization output schema."""

from typing import Literal

from pydantic import BaseModel, Field

from instamart_engine.themes.models import ThemeType

THEME_TYPE_VALUES = tuple(member.value for member in ThemeType)


class ThemeSynthesisOutput(BaseModel):
    name: str = Field(description="A concise, specific, non-causal theme name.")
    short_summary: str = Field(description="One or two sentences describing the theme.")
    long_summary: str = Field(
        description="A fuller paragraph, acknowledging any counterexample provided."
    )
    theme_type: Literal[THEME_TYPE_VALUES]  # type: ignore[valid-type]
    confidence_score: float = Field(ge=0, le=1)
