from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from backend.llm import llm
from backend.schemas import SQLOutput
from backend.prompts.common import CORE_TABLE_DDL

correction_parser = PydanticOutputParser(pydantic_object=SQLOutput)

CORRECTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "你是一个 SQL 修正助手。用户提出的查询发生了错误，请修正 SQL。\n\n{CORE_TABLE_DDL}\n\n{format_instructions}\n\n如果是 SQL 语法错误或拼写错误，直接修正后返回修正版 SQL。\n如果是业务逻辑问题（如字段不存在，可以用替代字段），给出合理的修正。\n如果确实无法查询，返回空的 sql 字段。"),
    ("human", "原始用户问题：{question}\n之前的 SQL：{previous_sql}\n错误信息：{error_message}\n\n请修正此 SQL 错误。"),
]).partial(CORE_TABLE_DDL=CORE_TABLE_DDL, format_instructions=correction_parser.get_format_instructions())

correction_chain = CORRECTION_PROMPT | llm | correction_parser
