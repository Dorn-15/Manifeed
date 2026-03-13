from __future__ import annotations

import os

DEFAULT_EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-large"


def resolve_embedding_model_name() -> str:
    model_name = os.getenv("EMBEDDING_MODEL_NAME", DEFAULT_EMBEDDING_MODEL_NAME).strip()
    if not model_name:
        return DEFAULT_EMBEDDING_MODEL_NAME
    return model_name
