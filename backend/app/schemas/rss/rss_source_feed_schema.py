from pydantic import BaseModel, ConfigDict, Field, field_validator


class RssSourceFeedSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True
    trust_score: float = Field(default=0.5, ge=0.0, le=1.0)
    fetchprotection: int | None = Field(default=None, ge=0, le=2)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str]) -> list[str]:
        cleaned_values: list[str] = []
        for value in values:
            cleaned_value = value.strip()
            if cleaned_value:
                cleaned_values.append(cleaned_value)
        return cleaned_values


class RssSourceCatalogSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company: str = Field(min_length=1, max_length=100)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    img: str | None = Field(default=None, max_length=500)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    language: str | None = Field(default=None, min_length=2, max_length=2)
    fetchprotection: int = Field(default=1, ge=0, le=2)
    feeds: list[RssSourceFeedSchema] = Field(default_factory=list)
