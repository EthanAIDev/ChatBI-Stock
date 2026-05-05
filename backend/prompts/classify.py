from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from backend.llm import llm
from backend.schemas import IntentOutput
from backend.prompts.common import CORE_TABLE_DDL, STOCK_NAMES, STOCK_KEYWORDS

intent_parser = PydanticOutputParser(pydantic_object=IntentOutput)

INTENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "你是意图分类器。判断用户问题是否需要查询股票数据库。\n\n{CORE_TABLE_DDL}\n\n规则：\n1. 只输出合法的 JSON，格式由后续 parser 指定\n2. 如果问题涉及具体的股票数据（价格、涨跌、走势、统计、对比、成交额等），返回 data_query=true\n3. 如果用户要求\"总结\"\"分析\"\"评价\"\"归纳\"股票数据，这也是数据查询，返回 data_query=true\n4. 只有当问题是纯粹的寒暄（你好/谢谢/再见）或不涉及任何股票数据时，才返回 data_query=false\n5. reply 仅在 data_query=false 时有效\n\n{format_instructions}"),
    ("human", "{question}"),
]).partial(CORE_TABLE_DDL=CORE_TABLE_DDL, format_instructions=intent_parser.get_format_instructions())

intent_chain = INTENT_PROMPT | llm | intent_parser


def has_data_keywords(question: str) -> bool:
    for name in STOCK_NAMES:
        if name in question or name[:2] in question:
            return True
    for kw in STOCK_KEYWORDS:
        if kw in question:
            return True
    return False
