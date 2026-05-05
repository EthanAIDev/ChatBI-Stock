import json
from pathlib import Path
from langchain_chroma import Chroma
from langchain_core.documents import Document
from backend.llm import embeddings
from backend.config import settings

BASE_DIR = Path(__file__).resolve().parent.parent


def _get_chroma_dir() -> str:
    return str(settings.chroma_persist_dir or (BASE_DIR / "chroma_db"))


def get_schema_retriever(k: int = 6):
    vector_store = Chroma(
        collection_name="schema_fields",
        embedding_function=embeddings,
        persist_directory=_get_chroma_dir(),
    )
    return vector_store.as_retriever(search_kwargs={"k": k})


def get_example_retriever(k: int = 3):
    vector_store = Chroma(
        collection_name="sql_examples",
        embedding_function=embeddings,
        persist_directory=_get_chroma_dir(),
    )
    return vector_store.as_retriever(search_kwargs={"k": k})


def seed_chroma_from_sqlite():
    from semantic_layer import STOCK_PRICES_METADATA, STOCK_EXAMPLES

    schema_store = Chroma(
        collection_name="schema_fields",
        embedding_function=embeddings,
        persist_directory=_get_chroma_dir(),
    )
    if schema_store._collection.count() == 0:
        docs = []
        for meta in STOCK_PRICES_METADATA:
            content = (
                f"{meta['table_description']} | "
                f"表: {meta['table_name']} | "
                f"字段: {meta['field_name']} | "
                f"类型: {meta.get('field_type', '')} | "
                f"{meta.get('field_description', '')} | "
                f"{meta.get('business语义', '')}"
            )
            docs.append(Document(
                page_content=content,
                metadata={
                    "table_name": meta["table_name"],
                    "field_name": meta["field_name"],
                    "field_type": meta.get("field_type", ""),
                    "table_description": meta.get("table_description", ""),
                }
            ))
        schema_store.add_documents(docs)

    example_store = Chroma(
        collection_name="sql_examples",
        embedding_function=embeddings,
        persist_directory=_get_chroma_dir(),
    )
    if example_store._collection.count() == 0:
        docs = []
        for ex in STOCK_EXAMPLES:
            content = (
                f"问题: {ex['question']} | "
                f"场景: {ex.get('business_scenario', '')} | "
                f"标签: {ex.get('tags', '')}"
            )
            docs.append(Document(
                page_content=content,
                metadata={
                    "question": ex["question"],
                    "sql_text": ex["sql_text"],
                    "business_scenario": ex.get("business_scenario", ""),
                    "tags": ex.get("tags", ""),
                }
            ))
        example_store.add_documents(docs)
