from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RssSourceFeedSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    trust_score: float = Field(ge=0.0, le=1.0)
    language: str | None = None
    enabled: bool = True
    img: str | None = Field(default=None, max_length=500)
    parsing_config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str]) -> list[str]:
        cleaned_values: list[str] = []
        for value in values:
            cleaned_value = value.strip()
            if cleaned_value:
                cleaned_values.append(cleaned_value)
        return cleaned_values
