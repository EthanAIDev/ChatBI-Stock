from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from backend.config import settings


def get_session_memory(session_id: str) -> SQLChatMessageHistory:
    return SQLChatMessageHistory(
        session_id=session_id,
        connection=f"sqlite:///{settings.db_path}",
        table_name="chat_messages_langchain",
    )


def load_memory_to_state(session_id: str) -> list[BaseMessage]:
    chat_history = get_session_memory(session_id)
    return chat_history.messages


def save_context(session_id: str, user_input: str, assistant_output: str) -> None:
    chat_history = get_session_memory(session_id)
    chat_history.add_message(HumanMessage(content=user_input))
    chat_history.add_message(AIMessage(content=assistant_output))
