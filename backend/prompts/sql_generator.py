import json
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from backend.llm import llm
from backend.prompts.common import CORE_TABLE_DDL

SQL_GENERATOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是股票数据 SQL 生成器。你必须把用户问题转换成 SQLite SELECT 语句。

输出要求：直接输出 JSON 格式：{{"sql": "SELECT ..."}}，不要输出任何其他文字。

{ddl_section}

{CORE_TABLE_DDL}

规则：
1. 只允许输出 JSON，不要 markdown，不要解释。
2. JSON 格式固定为 {{"sql": "..."}}
3. 只生成 SELECT 语句，不能生成 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE。
4. 日期字段是 trade_date，格式为 YYYY-MM-DD。
5. 你的唯一职责是生成 SQL，不要用自然语言回答用户的数据问题。
6. 如果涉及走势，优先返回 trade_date 和一个或多个数值列，并按 trade_date 升序。
7. 如果涉及最高/最低收盘价，优先返回 trade_date、close。
8. 如果涉及平均收盘价，使用 AVG(close) 并合理命名列。
9. 如果用户提到股票名称，必须使用 stock_name 过滤。"""),
    MessagesPlaceholder("few_shot_examples"),
    MessagesPlaceholder("chat_history"),
    ("human", "{question}"),
]).partial(CORE_TABLE_DDL=CORE_TABLE_DDL)

sql_chain = SQL_GENERATOR_PROMPT | llm | StrOutputParser()


def parse_sql_output(raw: str) -> str:
    raw = raw.strip()
    import re as _re
    # 尝试 JSON 解析
    try:
        data = json.loads(raw)
        sql = data.get("sql", "")
        if sql:
            return sql
    except json.JSONDecodeError:
        pass
    # 尝试从 markdown 代码块提取
    match = _re.search(r'```(?:sql|json)?\s*\n?(.*?)```', raw, _re.S | _re.I)
    if match:
        inner = match.group(1).strip()
        if not inner.upper().startswith("SELECT"):
            inner_parsed = parse_sql_output(inner)
            if inner_parsed:
                return inner_parsed
        if inner.upper().startswith("SELECT"):
            return inner
        return inner
    # 尝试从 JSON 大括号提取 sql 值（处理可能嵌套SQL引号的情况）
    match = _re.search(r'\{[^}]*"sql"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, _re.S)
    if match:
        sql = match.group(1)
        sql = sql.replace('\\"', '"').replace('\\n', '\n')
        if sql.upper().strip().startswith("SELECT"):
            return sql.strip()
    # 尝试从单引号包裹中提取
    match = _re.search(r"'sql'\s*:\s*'((?:[^'\\]|\\.)*)'", raw, _re.S)
    if match:
        sql = match.group(1)
        if sql.upper().strip().startswith("SELECT"):
            return sql.strip()
    # 检查是否本身就是 SQL
    if raw.upper().startswith("SELECT"):
        return raw
    # 最后尝试：去掉所有非 SELECT 开头之前的内容
    idx = raw.upper().find("SELECT")
    if idx >= 0:
        return raw[idx:].split('\n')[0].strip()
    return ""
