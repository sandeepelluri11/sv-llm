from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from sv_llm.config import Settings


def get_chat_model(settings: Settings) -> BaseChatModel:
    """Return the production chat model. Tests inject fakes through ``build_graph``."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.model,
        temperature=settings.temperature,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def get_embeddings(settings: Settings) -> Embeddings:
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(model=settings.embedding_model)
