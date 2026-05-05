import json
import re
import sys
import hashlib
import time
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from openai import OpenAI

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import settings
from backend.memory import save_context
from backend.services.admin_service import (
    get_runtime_model_settings,
    get_runtime_prompt_template_map,
    record_query_audit,
)
from backend.services.arima_stock import arima_stock
from backend.services.security import validate_sql
from backend.services.session_service import (
    add_message,
    get_messages,
    update_title_if_placeholder,
)
from semantic_layer import (
    build_ddl_from_schema,
    build_examples_section,
    get_cache,
    get_semantic_expansion,
    retrieve_relevant_schema,
    retrieve_similar_examples,
    set_cache,
    sql_hash,
)


STOCK_MAP = {
    '贵州茅台': '600519.SH',
    '五粮液': '000858.SZ',
    '中芯国际': '688981.SH',
    '广发证券': '000776.SZ',
}
ARIMA_STOCK_ALIASES = {
    '贵州茅台': '600519.SH',
    '茅台': '600519.SH',
    '五粮液': '000858.SZ',
    '中芯国际': '688981.SH',
    '中芯': '688981.SH',
    '广发证券': '000776.SZ',
    '广发': '000776.SZ',
}

CORE_TABLE_DDL = """核心业务表：
CREATE TABLE stock_prices (
    ts_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    pre_close REAL,
    change REAL,
    pct_chg REAL,
    vol REAL,
    amount REAL,
    PRIMARY KEY (ts_code, trade_date)
);
""" + json.dumps(STOCK_MAP, ensure_ascii=False)

INTENT_CLASSIFY_PROMPT = f"""你是意图分类器。判断用户问题是否需要查询股票数据库。

{CORE_TABLE_DDL}

规则：
1. 只输出 JSON，格式为 {{"data_query": true/false, "reply": "简短回复"}}
2. 如果问题涉及具体的股票数据（价格、涨跌、走势、统计、对比、成交额等），返回 data_query=true
3. 如果用户要求"总结""分析""评价""归纳"股票数据，这也是数据查询，返回 data_query=true
4. 只有当问题是纯粹的寒暄（你好/谢谢/再见）或不涉及任何股票数据时，才返回 data_query=false
5. reply 仅在 data_query=false 时有效"""

MERGED_CLASSIFY_GENERATE_TEMPLATE = """你是股票数据分析助手，同时承担意图分类和SQL生成的职责。

{{schema_section}}

{{full_ddl}}

{{examples_section}}

{{context_section}}

规则：
1. 只输出JSON，不要markdown，不要解释，格式固定为 {{"data_query": true/false, "reply": "闲聊回复", "sql": "SQL语句"}}
2. data_query=true时，必须提供有效的SQL语句；data_query=false时，reply给出简短友好的闲聊回复
3. 如果问题涉及股票数据（价格、涨跌、走势、统计、对比、排名、总结、分析、评价、成交额等），data_query=true
4. 只有纯寒暄（你好、谢谢、再见）或不涉及任何股票数据时，才返回data_query=false
5. SQL生成规则：
   - 只生成SELECT语句，不能生成INSERT/UPDATE/DELETE/DROP/ALTER/CREATE
   - 日期字段是trade_date，格式为YYYY-MM-DD
   - 使用stock_name过滤时，必须使用完整的股票名称（如'贵州茅台'、'五粮液'、'中芯国际'、'广发证券'）
   - 涉及走势优先返回trade_date和数值列，按trade_date升序
   - 涉及最高/最低返回trade_date和对应数值字段
   - 涉及平均使用AVG函数并合理命名列
   - 你的职责是生成SQL，不要用自然语言回答数据问题"""

SQL_CORRECTION_TEMPLATE = """你是一个 SQL 修正助手。用户提出的查询发生了错误，请修正 SQL。

原始用户问题：{question}
之前的 SQL：{previous_sql}
错误信息：{error_message}

{CORE_TABLE_DDL}

请返回 JSON 格式：{{"needs_sql": true/false, "sql": "...", "answer": "..."}}
如果是 SQL 语法错误或拼写错误，直接修正后返回修正版 SQL。
如果是业务逻辑问题（如字段不存在，可以用替代字段），给出合理的修正。
如果确实无法查询，返回 needs_sql=false 并给出解释。"""

ANALYSIS_INSTRUCTIONS = {
    'trend': """这是趋势/走势分析：
- 描述整体趋势方向（上升/下降/震荡）
- 列出起始值、结束值和变化幅度
- 找出阶段高点和低点
- 计算整体波动率或涨跌幅区间
- 给出简短的趋势评价""",
    'compare': """这是对比分析：
- 列出每只股票的核心指标排名
- 指出表现最好和最差的股票
- 计算各股票间的差异幅度
- 给出简短的综合评价""",
    'extreme': """这是极值查询：
- 直接给出最大值/最小值及其对应日期
- 如有多条记录，列出前3-5条
- 给出极值出现的背景说明""",
    'statistics': """这是统计分析：
- 列出核心统计指标（均值、中位数、标准差）
- 分析数据分布特征
- 如有明显异常值，指出并说明
- 给出统计意义上的结论""",
    'evaluate': """这是综合评价分析：
- 从多维度评价股票表现（价格、涨跌幅、成交量等）
- 给出好/中/差的评级和理由
- 如有明显趋势或异常，重点说明
- 给出参考建议""",
    'simple': """这是简单数据查询：
- 直接回答用户问题
- 给出关键数值
- 不需要过度分析""",
}

LOG = None

STOCK_NAMES = list(STOCK_MAP.keys())
STOCK_KEYWORDS = [
    '收盘价', '开盘价', '最高价', '最低价', '涨跌幅', '涨跌额',
    '成交量', '成交额', '走势', '价格', '数据', '查询', '比较',
    '统计', '汇总', '平均', '最高', '最低', '排名', '涨', '跌',
    '分析', '总结', '归纳', '评价', '走势图',
]
DATE_PATTERN = re.compile(r'(\d{4})[-年](\d{1,2})')
ARIMA_TRIGGER_PATTERN = re.compile(r'arima_stock|arima|预测|forecast|走势推演|趋势推演', re.I)
TSCODE_PATTERN = re.compile(r'(?<!\d)\d{6}\.(?:SH|SZ)(?![A-Za-z0-9])', re.I)
ARIMA_FUNC_PATTERN = re.compile(r'arima_stock\s*\(([^)]*)\)', re.I)
N_KV_PATTERN = re.compile(r'\b[nN]\s*[:=：]\s*(\d{1,3})\b')
N_DAY_PATTERN = re.compile(r'(\d{1,3})\s*(?:个)?\s*(?:交易)?\s*天')
FUTURE_DAY_INTENT_PATTERN = re.compile(r'(未来|后面|接下来|后续)\s*(\d{1,3})\s*(?:个)?\s*(?:交易)?\s*天')
ARIMA_CONTEXT_SQL_PATTERN = re.compile(
    r"TOOL:\s*arima_stock\s*\(\s*tscode\s*=\s*['\"]?(\d{6}\.(?:SH|SZ))['\"]?",
    re.I,
)
ARIMA_FOLLOWUP_ONLY_PATTERN = re.compile(
    r'^\s*(?:那|那就|那改|改成|改为|来个|要|就|再|继续|接着|只要)?\s*(\d{1,3})\s*(?:个)?\s*(?:交易)?\s*天(?:[吧吗呢啊呀]?)?\s*$'
)
ARIMA_HISTORY_HINT_PATTERN = re.compile(r'过去|历史|最近|近\s*\d+\s*天')
DEFAULT_ARIMA_N = 7
CONTEXT_WINDOW_ROUNDS = 10
INTENT_CONFIRM_PENDING_PREFIX = 'INTENT_CONFIRM_PENDING:'
CONFIRM_YES_PATTERN = re.compile(r'^\s*(?:是的|好的|确认|对|没错|就这个|是|ok|yes)\s*$', re.I)
CONFIRM_NO_PATTERN = re.compile(r'^\s*(?:不是|不对|不要|否|no|不是这个|先别)\s*$', re.I)
AMBIGUOUS_FOLLOWUP_PATTERN = re.compile(r'^\s*(?:那|这个|那个|这样|就按这个|就按那个|继续|接着|那呢|那这个呢)\s*[？?吗呢啊呀]*\s*$')
ARIMA_N_SQL_PATTERN = re.compile(r'\bn\s*=\s*(\d{1,3})\b', re.I)
INTENT_RESOLUTION_PROMPT = """你是会话意图归一器。请根据“当前用户输入”和“最近会话上下文+状态摘要”，判断真实意图。

你必须只输出 JSON，格式如下：
{
  "intent_type": "forecast|query|chat",
  "tscode": "600519.SH 或 null",
  "stock_name": "贵州茅台 或 null",
  "n_days": 90 或 null,
  "needs_confirmation": true/false,
  "confirmation_question": "若需确认时的问题，否则空字符串",
  "confidence": 0.0-1.0,
  "normalized_question": "补全后的完整用户意图语句",
  "source": {
    "tscode": "current|history|unknown",
    "n_days": "current|history|unknown"
  }
}

规则：
1. 优先理解用户真实意图，允许用上下文补全省略信息。
2. 如果上下文清晰，不要过度反问。
3. 仅当表达含糊且关键槽位高度不确定时，needs_confirmation=true。
4. 若判断是预测意图，intent_type 必须是 forecast。"""


def _get_log():
    global LOG
    if LOG is None:
        from logger_utils import get_daily_logger
        LOG = get_daily_logger('chat_service')
    return LOG


def _get_llm_client() -> OpenAI:
    runtime = get_runtime_model_settings()
    api_key = settings.dashscope_api_key
    if not api_key:
        raise RuntimeError('Missing DASHSCOPE_API_KEY')
    return OpenAI(
        api_key=api_key,
        base_url=runtime['base_url'],
        timeout=runtime['timeout_seconds'],
        max_retries=runtime['retry_count'],
    )


def _call_model(messages: list[dict[str, str]], temperature: float = 0.2) -> str:
    runtime = get_runtime_model_settings()
    client = _get_llm_client()
    response = client.chat.completions.create(
        model=runtime['model_name'],
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content or ''


def _call_model_stream(messages: list[dict[str, str]], token_callback, temperature: float = 0.3):
    """流式调用 LLM，每收到 token 调用 token_callback(content)，返回完整文本"""
    runtime = get_runtime_model_settings()
    client = _get_llm_client()
    full_text = ''
    stream = client.chat.completions.create(
        model=runtime['model_name'],
        messages=messages,
        temperature=temperature,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            content = delta.content
            full_text += content
            token_callback(content)
    return full_text


def _parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _has_data_keywords(question: str) -> bool:
    for name in STOCK_NAMES:
        if name in question or name[:2] in question:
            return True
    for kw in STOCK_KEYWORDS:
        if kw in question:
            return True
    if DATE_PATTERN.search(question):
        return True
    return False


def _is_arima_intent(question: str) -> bool:
    text = question or ''
    if ARIMA_TRIGGER_PATTERN.search(text):
        return True
    if not FUTURE_DAY_INTENT_PATTERN.search(text):
        return False
    if TSCODE_PATTERN.search(text):
        return True
    return any(alias in text for alias in ARIMA_STOCK_ALIASES)


def _parse_arima_sql_slots(sql_text: str | None) -> tuple[str, int] | None:
    if not sql_text:
        return None
    code_match = ARIMA_CONTEXT_SQL_PATTERN.search(sql_text)
    if not code_match:
        return None
    tscode = code_match.group(1).upper()
    n_match = ARIMA_N_SQL_PATTERN.search(sql_text)
    n = int(n_match.group(1)) if n_match else DEFAULT_ARIMA_N
    return tscode, n


def _extract_arima_tool_params_with_flags(question: str) -> tuple[str | None, int, bool]:
    text = question or ''
    tscode: str | None = None
    n = DEFAULT_ARIMA_N
    has_explicit_n = False

    function_match = ARIMA_FUNC_PATTERN.search(text)
    if function_match:
        args = [segment.strip().strip('"\'') for segment in function_match.group(1).split(',') if segment.strip()]
        if args:
            code_match = TSCODE_PATTERN.search(args[0])
            if code_match:
                tscode = code_match.group(0).upper()
        if len(args) >= 2 and args[1].isdigit():
            n = int(args[1])
            has_explicit_n = True

    if not tscode:
        code_match = TSCODE_PATTERN.search(text)
        if code_match:
            tscode = code_match.group(0).upper()
        else:
            alias_hits: list[tuple[int, str]] = []
            for alias, mapped_code in ARIMA_STOCK_ALIASES.items():
                idx = text.find(alias)
                if idx >= 0:
                    alias_hits.append((idx, mapped_code))
            if alias_hits:
                alias_hits.sort(key=lambda item: item[0])
                tscode = alias_hits[0][1]

    n_match = N_KV_PATTERN.search(text)
    if n_match:
        n = int(n_match.group(1))
        has_explicit_n = True
    else:
        day_match = N_DAY_PATTERN.search(text)
        if day_match:
            n = int(day_match.group(1))
            has_explicit_n = True

    return tscode, n, has_explicit_n


def _extract_context_tscode(context_text: str) -> str | None:
    if not context_text:
        return None
    sql_match = ARIMA_CONTEXT_SQL_PATTERN.search(context_text)
    if sql_match:
        return sql_match.group(1).upper()
    all_codes = TSCODE_PATTERN.findall(context_text)
    if all_codes:
        return all_codes[-1].upper()
    last_hit_index = -1
    selected_code: str | None = None
    for alias, mapped_code in ARIMA_STOCK_ALIASES.items():
        idx = context_text.rfind(alias)
        if idx > last_hit_index:
            last_hit_index = idx
            selected_code = mapped_code
    return selected_code


def _extract_context_latest_arima(context_text: str) -> tuple[str | None, int | None]:
    slots = _parse_arima_sql_slots(context_text)
    if slots:
        return slots[0], slots[1]
    tscode = _extract_context_tscode(context_text)
    return tscode, None


def _parse_confirmation_marker(sql_text: str | None) -> dict[str, Any] | None:
    if not sql_text or not sql_text.startswith(INTENT_CONFIRM_PENDING_PREFIX):
        return None
    payload = sql_text[len(INTENT_CONFIRM_PENDING_PREFIX):].strip()
    if not payload:
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return data
    return None


def _resolve_stock_name(tscode: str | None) -> str | None:
    if not tscode:
        return None
    for stock_name, code in STOCK_MAP.items():
        if code == tscode:
            return stock_name
    return None


def _build_rounds(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    rounds: list[dict[str, str]] = []
    for msg in messages:
        role = msg.get('role')
        if role == 'user':
            rounds.append({'question': msg.get('content', ''), 'answer': '', 'sql_text': ''})
        elif role == 'assistant' and rounds:
            rounds[-1]['answer'] = msg.get('content', '')
            rounds[-1]['sql_text'] = msg.get('sql_text') or ''
    return rounds


def build_session_context(messages: list[dict[str, Any]], max_rounds: int = CONTEXT_WINDOW_ROUNDS) -> dict[str, Any]:
    rounds = _build_rounds(messages)
    recent_rounds = rounds[-max_rounds:] if len(rounds) > max_rounds else rounds

    lines: list[str] = []
    for idx, item in enumerate(recent_rounds, start=1):
        lines.append(f"[第{idx}轮] 用户: {item['question']}")
        if item.get('sql_text'):
            lines.append(f"[第{idx}轮] 执行标记: {item['sql_text']}")
        if item.get('answer'):
            preview = item['answer'][:120]
            lines.append(f"[第{idx}轮] 助手: {preview}")
    context_text = '\n'.join(lines)

    latest_pending_intent = None
    if recent_rounds and recent_rounds[-1].get('sql_text'):
        latest_pending_intent = _parse_confirmation_marker(recent_rounds[-1].get('sql_text'))

    latest_arima: dict[str, Any] | None = None
    latest_explicit_tscode: str | None = None
    latest_explicit_days: int | None = None
    for item in reversed(recent_rounds):
        question = item.get('question', '')
        tscode, n, has_explicit_n = _extract_arima_tool_params_with_flags(question)
        if not latest_explicit_tscode and tscode:
            latest_explicit_tscode = tscode
        if latest_explicit_days is None and has_explicit_n:
            latest_explicit_days = n

        slots = _parse_arima_sql_slots(item.get('sql_text'))
        if not latest_arima and slots:
            latest_arima = {'tscode': slots[0], 'n_days': slots[1]}

        if latest_explicit_tscode and latest_explicit_days is not None and latest_arima:
            break

    summary_lines = [
        f"- 最近预测参数: {latest_arima if latest_arima else '无'}",
        f"- 最近显式股票: {latest_explicit_tscode or '无'}",
        f"- 最近显式天数: {latest_explicit_days if latest_explicit_days is not None else '无'}",
        f"- 待确认意图: {latest_pending_intent if latest_pending_intent else '无'}",
    ]
    state_summary = '\n'.join(summary_lines)
    context_package_text = f"最近会话（最多{max_rounds}轮）：\n{context_text}\n\n状态摘要：\n{state_summary}"
    return {
        'context_text': context_text,
        'state_summary': state_summary,
        'context_package_text': context_package_text,
        'pending_intent': latest_pending_intent,
        'latest_arima': latest_arima,
        'latest_explicit_tscode': latest_explicit_tscode,
        'latest_explicit_days': latest_explicit_days,
    }


def _is_confirmation_reply(text: str) -> bool:
    return bool(CONFIRM_YES_PATTERN.search((text or '').strip()))


def _is_rejection_reply(text: str) -> bool:
    return bool(CONFIRM_NO_PATTERN.search((text or '').strip()))


def _is_ambiguous_followup(text: str) -> bool:
    clean = (text or '').strip()
    if not clean:
        return True
    if AMBIGUOUS_FOLLOWUP_PATTERN.search(clean):
        return True
    return not _has_stock_reference(clean) and not bool(N_DAY_PATTERN.search(clean))


def _build_confirmation_question(tscode: str, n_days: int) -> str:
    stock_name = _resolve_stock_name(tscode) or tscode
    return f"你是想预测{stock_name}未来{n_days}天的走势吗？请回复“确认”继续执行，或说明新的股票/天数。"


def _safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def resolve_intent_from_session(question: str, context_package: dict[str, Any]) -> dict[str, Any]:
    text = (question or '').strip()
    pending_intent = context_package.get('pending_intent') or {}
    if pending_intent:
        pending_tscode = pending_intent.get('tscode')
        pending_days = _safe_int(pending_intent.get('n_days'))
        if _is_confirmation_reply(text) and pending_tscode and pending_days:
            stock_name = _resolve_stock_name(pending_tscode)
            return {
                'intent_type': 'forecast',
                'tscode': pending_tscode,
                'stock_name': stock_name,
                'n_days': pending_days,
                'needs_confirmation': False,
                'confirmation_question': '',
                'confidence': 0.95,
                'normalized_question': f'请预测{stock_name or pending_tscode}未来{pending_days}天走势',
                'source': {'tscode': 'pending', 'n_days': 'pending'},
            }
        if _is_rejection_reply(text):
            return {
                'intent_type': 'forecast',
                'tscode': None,
                'stock_name': None,
                'n_days': None,
                'needs_confirmation': True,
                'confirmation_question': '明白了，请明确股票和预测天数，例如：请预测茅台未来30天走势。',
                'confidence': 0.8,
                'normalized_question': text,
                'source': {'tscode': 'unknown', 'n_days': 'unknown'},
            }

    context_blob = context_package.get('context_package_text') or context_package.get('context_text') or ''
    llm_raw: dict[str, Any] = {}
    try:
        raw = _call_model(
            [
                {'role': 'system', 'content': INTENT_RESOLUTION_PROMPT},
                {
                    'role': 'user',
                    'content': f'当前用户输入：{text}\n\n{context_blob}',
                },
            ],
            temperature=0.0,
        )
        llm_raw = _parse_json_object(raw)
    except Exception:
        llm_raw = {}

    current_tscode, current_n, has_explicit_n = _extract_arima_tool_params_with_flags(text)
    latest_arima = context_package.get('latest_arima') or {}
    history_tscode = latest_arima.get('tscode') or context_package.get('latest_explicit_tscode')
    history_n = _safe_int(latest_arima.get('n_days')) or context_package.get('latest_explicit_days')

    llm_tscode = str(llm_raw.get('tscode') or '').strip().upper() or None
    llm_n = _safe_int(llm_raw.get('n_days'))
    intent_type = str(llm_raw.get('intent_type') or '').strip().lower()
    if intent_type not in {'forecast', 'query', 'chat'}:
        intent_type = 'query' if _has_data_keywords(text) else 'chat'

    resolved_tscode = current_tscode or llm_tscode or history_tscode
    source_tscode = 'current' if current_tscode else ('history' if resolved_tscode else 'unknown')
    resolved_n = current_n if has_explicit_n else (llm_n or history_n or DEFAULT_ARIMA_N)
    source_n = 'current' if has_explicit_n else ('history' if (history_n is not None) else 'unknown')

    if _should_trigger_arima_tool(text, context_package.get('context_text') or '') or intent_type == 'forecast':
        intent_type = 'forecast'

    if (
        intent_type != 'forecast'
        and _is_ambiguous_followup(text)
        and history_tscode
        and (history_n is not None)
        and (latest_arima or pending_intent)
    ):
        intent_type = 'forecast'
        resolved_tscode = history_tscode
        resolved_n = history_n
        source_tscode = 'history'
        source_n = 'history'

    needs_confirmation = bool(llm_raw.get('needs_confirmation', False))
    confirmation_question = str(llm_raw.get('confirmation_question') or '').strip()
    confidence = float(llm_raw.get('confidence', 0.6) or 0.6)

    if intent_type == 'forecast':
        if not resolved_tscode:
            needs_confirmation = True
            confirmation_question = '请明确你要预测哪只股票（可说茅台/五粮液）以及预测天数。'
        elif source_tscode != 'current' and source_n != 'current' and _is_ambiguous_followup(text):
            needs_confirmation = True
            confirmation_question = _build_confirmation_question(resolved_tscode, resolved_n)
        stock_name = _resolve_stock_name(resolved_tscode)
        normalized_question = f'请预测{stock_name or resolved_tscode}未来{resolved_n}天走势'
    else:
        stock_name = _resolve_stock_name(resolved_tscode)
        normalized_question = str(llm_raw.get('normalized_question') or text).strip() or text

    if not confirmation_question and needs_confirmation and resolved_tscode:
        confirmation_question = _build_confirmation_question(resolved_tscode, resolved_n)

    return {
        'intent_type': intent_type,
        'tscode': resolved_tscode,
        'stock_name': stock_name,
        'n_days': resolved_n,
        'needs_confirmation': needs_confirmation,
        'confirmation_question': confirmation_question,
        'confidence': confidence,
        'normalized_question': normalized_question,
        'source': {
            'tscode': source_tscode,
            'n_days': source_n,
        },
    }


def _build_confirmation_marker(intent_plan: dict[str, Any]) -> str:
    payload = {
        'intent_type': intent_plan.get('intent_type'),
        'tscode': intent_plan.get('tscode'),
        'stock_name': intent_plan.get('stock_name'),
        'n_days': intent_plan.get('n_days'),
    }
    return INTENT_CONFIRM_PENDING_PREFIX + json.dumps(payload, ensure_ascii=False, separators=(',', ':'))


def _has_stock_reference(text: str) -> bool:
    if TSCODE_PATTERN.search(text):
        return True
    return any(alias in text for alias in ARIMA_STOCK_ALIASES)


def _is_contextual_arima_followup(question: str, context_text: str) -> bool:
    text = (question or '').strip()
    if not text or not context_text:
        return False
    if ARIMA_HISTORY_HINT_PATTERN.search(text):
        return False
    has_day_request = bool(
        FUTURE_DAY_INTENT_PATTERN.search(text)
        or ARIMA_FOLLOWUP_ONLY_PATTERN.search(text)
        or N_DAY_PATTERN.search(text)
    )
    if not has_day_request:
        return False
    if _has_stock_reference(text) and not FUTURE_DAY_INTENT_PATTERN.search(text):
        return False
    if not _extract_context_tscode(context_text):
        return False
    return bool(ARIMA_CONTEXT_SQL_PATTERN.search(context_text) or ARIMA_TRIGGER_PATTERN.search(context_text))


def _should_trigger_arima_tool(question: str, context_text: str = '') -> bool:
    return _is_arima_intent(question) or _is_contextual_arima_followup(question, context_text)


def _extract_arima_tool_params(question: str) -> tuple[str | None, int]:
    tscode, n, _ = _extract_arima_tool_params_with_flags(question)
    return tscode, n


def _run_arima_tool(tscode: str, n: int) -> dict[str, Any]:
    tool_sql_text = f"TOOL: arima_stock(tscode='{tscode}', n={n})"
    try:
        result = arima_stock(tscode=tscode, n=n)
        return {
            'content': result['summary_text'],
            'sql_text': tool_sql_text,
            'result_preview': result['result_preview'],
            'chart_path': result['chart_path'],
            'from_cache': False,
            'status': 'success',
            'error_message': None,
        }
    except Exception as exc:
        return {
            'content': f'ARIMA 预测失败：{exc}',
            'sql_text': tool_sql_text,
            'result_preview': None,
            'chart_path': None,
            'from_cache': False,
            'status': 'failed',
            'error_message': str(exc),
        }


def _run_arima_tool_if_needed(question: str, context_text: str = '') -> dict[str, Any] | None:
    if not _should_trigger_arima_tool(question, context_text):
        return None

    tscode, n = _extract_arima_tool_params(question)
    if not tscode:
        tscode = _extract_context_tscode(context_text)
    if not tscode:
        return {
            'content': 'arima_stock 需要必填参数 tscode（示例：arima_stock(600519.SH, 10)）',
            'sql_text': None,
            'result_preview': None,
            'chart_path': None,
            'from_cache': False,
            'status': 'failed',
            'error_message': 'missing tscode',
        }

    return _run_arima_tool(tscode, n)


def _is_context_dependent_followup(question: str) -> bool:
    text = (question or '').strip()
    if not text or _has_stock_reference(text):
        return False
    return bool(FUTURE_DAY_INTENT_PATTERN.search(text) or ARIMA_FOLLOWUP_ONLY_PATTERN.search(text))


def _build_cache_key(question: str, context_text: str = '', intent_plan: dict[str, Any] | None = None) -> str:
    if intent_plan:
        if intent_plan.get('needs_confirmation'):
            context_fingerprint = (context_text or '').strip().lower()
            if len(context_fingerprint) > 300:
                context_fingerprint = context_fingerprint[-300:]
            return sql_hash(f"confirm||{question.strip().lower()}||{context_fingerprint}")
        if intent_plan.get('intent_type') == 'forecast' and intent_plan.get('tscode'):
            n_days = _safe_int(intent_plan.get('n_days')) or DEFAULT_ARIMA_N
            return sql_hash(f"forecast||{intent_plan['tscode']}||{n_days}")
        normalized_question = str(intent_plan.get('normalized_question') or '').strip().lower()
        if normalized_question:
            return sql_hash(normalized_question)

    normalized_question = question.strip().lower()
    if _is_context_dependent_followup(question):
        context_fingerprint = (context_text or '').strip().lower()
        if len(context_fingerprint) > 600:
            context_fingerprint = context_fingerprint[-600:]
        return sql_hash(f'{normalized_question}||ctx:{context_fingerprint}')
    return sql_hash(normalized_question)


def _classify_intent(question: str) -> tuple[bool, str]:
    if _has_data_keywords(question):
        return True, ''
    raw = _call_model(
        [
            {'role': 'system', 'content': INTENT_CLASSIFY_PROMPT},
            {'role': 'user', 'content': question},
        ],
        temperature=0.1,
    )
    _get_log().info('Intent classify raw response: %s', raw)
    plan = _parse_json_object(raw)
    data_query = plan.get('data_query', True)
    reply = plan.get('reply', '')
    return data_query, reply


def _load_prompt_templates() -> dict[str, str]:
    return get_runtime_prompt_template_map()


def _parse_manual_few_shot_examples(template_content: str) -> list[dict[str, str]]:
    try:
        data = json.loads(template_content)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    items = []
    for item in data:
        if not isinstance(item, dict):
            continue
        question = str(item.get('question', '')).strip()
        sql_text = str(item.get('sql', '')).strip()
        if question and sql_text:
            items.append({'question': question, 'sql_text': sql_text})
    return items


def _build_sql_generator_prompt(user_question: str, context_text: str = "") -> str:
    prompt_templates = _load_prompt_templates()
    relevant_schema = retrieve_relevant_schema(user_question, top_k=4)
    ddl_section = build_ddl_from_schema(relevant_schema)
    examples = retrieve_similar_examples(user_question, top_k=2)
    manual_examples = _parse_manual_few_shot_examples(prompt_templates['few_shot_examples'])
    combined_examples = [*examples, *manual_examples]
    examples_section = build_examples_section(combined_examples)

    parts = ["你是股票数据 SQL 生成器。你必须把用户问题转换成 SQLite SELECT 语句。\n"]
    if ddl_section:
        parts.append(f"当前问题相关的数据库字段描述：\n{ddl_section}\n")
    parts.append(f"完整表结构参考：\n{CORE_TABLE_DDL}\n")
    if examples_section:
        parts.append(f"{examples_section}\n")
    if context_text:
        parts.append(f"对话历史上下文：\n{context_text}\n")
    parts.append(prompt_templates['sql_generator_rules'])
    return '\n'.join(parts)


def _generate_sql(user_question: str, context_text: str = "") -> dict[str, Any]:
    expanded_question = get_semantic_expansion(user_question)
    system_prompt = _build_sql_generator_prompt(expanded_question, context_text)
    raw = _call_model(
        [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': expanded_question},
        ],
        temperature=0.1,
    )
    _get_log().info('SQL generator raw response: %s', raw)
    plan = _parse_json_object(raw)
    return {
        'sql': plan.get('sql', ''),
    }


def _build_merged_prompt(
    expanded_question: str,
    context_text: str,
    ddl_section: str,
    examples_section: str,
) -> str:
    context_section = f"对话历史上下文：\n{context_text}" if context_text else ""
    return MERGED_CLASSIFY_GENERATE_TEMPLATE.format(
        schema_section=f"当前问题相关的数据库字段描述：\n{ddl_section}" if ddl_section else "",
        full_ddl=CORE_TABLE_DDL,
        examples_section=examples_section if examples_section else "",
        context_section=context_section,
    )


def _classify_and_generate(user_question: str, context_text: str = "") -> dict[str, Any]:
    """合并意图分类和SQL生成，一次LLM调用完成两步，减少一次完整的LLM round-trip（节约8-20秒）"""
    expanded_question = get_semantic_expansion(user_question)

    # 向量检索：为SQL生成准备schema和示例上下文
    relevant_schema = retrieve_relevant_schema(expanded_question, top_k=4)
    ddl_section = build_ddl_from_schema(relevant_schema)
    examples = retrieve_similar_examples(expanded_question, top_k=2)

    prompt_templates = _load_prompt_templates()
    manual_examples = _parse_manual_few_shot_examples(prompt_templates['few_shot_examples'])
    combined_examples = [*examples, *manual_examples]
    examples_section = build_examples_section(combined_examples)

    system_prompt = _build_merged_prompt(expanded_question, context_text, ddl_section, examples_section)

    raw = _call_model(
        [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': expanded_question},
        ],
        temperature=0.1,
    )
    _get_log().info('Classify & Generate raw response: %s', raw)
    plan = _parse_json_object(raw)
    return {
        'data_query': plan.get('data_query', True),
        'reply': plan.get('reply', ''),
        'sql': plan.get('sql', ''),
    }


def _classify_and_generate_stream(user_question: str, context_text: str, token_callback) -> dict[str, Any]:
    """流式版本的合并分类+SQL生成，token_callback接收thinking阶段的token"""
    expanded_question = get_semantic_expansion(user_question)

    # 向量检索：为SQL生成准备schema和示例上下文
    relevant_schema = retrieve_relevant_schema(expanded_question, top_k=4)
    ddl_section = build_ddl_from_schema(relevant_schema)
    examples = retrieve_similar_examples(expanded_question, top_k=2)

    prompt_templates = _load_prompt_templates()
    manual_examples = _parse_manual_few_shot_examples(prompt_templates['few_shot_examples'])
    combined_examples = [*examples, *manual_examples]
    examples_section = build_examples_section(combined_examples)

    system_prompt = _build_merged_prompt(expanded_question, context_text, ddl_section, examples_section)

    raw = _call_model_stream(
        [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': expanded_question},
        ],
        token_callback,
        temperature=0.1,
    )
    _get_log().info('Classify & Generate stream raw response: %s', raw)
    plan = _parse_json_object(raw)
    return {
        'data_query': plan.get('data_query', True),
        'reply': plan.get('reply', ''),
        'sql': plan.get('sql', ''),
    }


def _generate_fallback_sql(question: str) -> str:
    for name in STOCK_NAMES:
        if name in question:
            return f"SELECT trade_date, close, pct_chg, vol FROM stock_prices WHERE stock_name = '{name}' ORDER BY trade_date DESC LIMIT 50"
    date_match = DATE_PATTERN.search(question)
    if date_match:
        year = date_match.group(1)
        month = date_match.group(2).zfill(2)
        return f"SELECT stock_name, trade_date, close, pct_chg FROM stock_prices WHERE trade_date >= '{year}-{month}-01' ORDER BY trade_date DESC LIMIT 100"
    return "SELECT stock_name, trade_date, close, pct_chg, vol FROM stock_prices ORDER BY trade_date DESC LIMIT 50"


def _correct_sql(question: str, previous_sql: str, error_message: str) -> dict[str, Any]:
    prompt = SQL_CORRECTION_TEMPLATE.format(
        question=question,
        previous_sql=previous_sql,
        error_message=error_message,
        CORE_TABLE_DDL=CORE_TABLE_DDL,
    )
    raw = _call_model(
        [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': f'请修正此 SQL 错误：{error_message}'},
        ],
        temperature=0.1,
    )
    _get_log().info('SQL correction raw response: %s', raw)
    plan = _parse_json_object(raw)
    plan.setdefault('needs_sql', True)
    plan.setdefault('sql', '')
    plan.setdefault('answer', '')
    return plan


def _execute_sql(sql_text: str) -> pd.DataFrame:
    from backend.engine.sqlite_engine import SQLiteQueryEngine
    engine = SQLiteQueryEngine()
    return engine.execute(sql_text)


def _render_chart(df: pd.DataFrame) -> str | None:
    if df.empty or len(df.columns) < 2:
        return None
    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    if not numeric_cols or len(df) == 1:
        return None

    image_dir = Path(settings.image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    chart_filename = f'chart_{hashlib.sha256(str(df.shape).encode()).hexdigest()[:12]}.png'
    chart_path = image_dir / chart_filename

    fig, ax = plt.subplots(figsize=(10, 5))
    x_col = df.columns[0]
    x_values = df[x_col].astype(str)
    is_time_like = all(re.match(r'^\d{4}-\d{2}-\d{2}$', str(v)) for v in x_values.head(min(len(x_values), 10)))

    if is_time_like:
        for column in numeric_cols[:3]:
            ax.plot(x_values, df[column], marker='o', label=column)
        ax.set_xlabel(str(x_col))
        ax.set_ylabel('数值')
        ax.legend()
        if len(x_values) > 20:
            step = max(1, len(x_values) // 10)
            visible_indices = list(range(0, len(x_values), step))
            plt.xticks(ticks=visible_indices, labels=[x_values.iloc[i] for i in visible_indices], rotation=45)
        else:
            plt.xticks(rotation=45)
    else:
        plot_df = df.copy()
        key_col = plot_df.columns[1] if len(plot_df.columns) > 1 and plot_df.columns[1] not in numeric_cols else x_col
        value_col = numeric_cols[0]
        bar_labels = plot_df[key_col].astype(str)
        ax.bar(bar_labels, plot_df[value_col])
        ax.set_xlabel(str(key_col))
        ax.set_ylabel(str(value_col))
        if len(bar_labels) > 20:
            step = max(1, len(bar_labels) // 10)
            visible_indices = list(range(0, len(bar_labels), step))
            plt.xticks(ticks=visible_indices, labels=[bar_labels.iloc[i] for i in visible_indices], rotation=45)
        else:
            plt.xticks(rotation=45)

    ax.set_title('查询结果图表')
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close(fig)
    return str(chart_path)


def _compute_stats(df: pd.DataFrame) -> dict[str, Any]:
    stats = {'row_count': len(df), 'column_count': len(df.columns)}
    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    if not numeric_cols:
        return stats
    for col in numeric_cols[:5]:
        series = df[col].dropna()
        if len(series) == 0:
            continue
        stats[f'{col}_mean'] = round(float(series.mean()), 2)
        stats[f'{col}_median'] = round(float(series.median()), 2)
        stats[f'{col}_std'] = round(float(series.std()), 2) if len(series) > 1 else 0
        stats[f'{col}_max'] = round(float(series.max()), 2)
        stats[f'{col}_min'] = round(float(series.min()), 2)
    date_cols = [c for c in df.columns if 'date' in c.lower() or 'time' in c.lower()]
    if date_cols and len(df) > 1:
        try:
            start_date = str(df[date_cols[0]].iloc[0])
            end_date = str(df[date_cols[0]].iloc[-1])
            stats['date_range'] = f'{start_date} ~ {end_date}'
            stats['days_count'] = len(df)
        except Exception:
            pass
    return stats


def _detect_analysis_mode(question: str) -> str:
    modes = []
    if any(kw in question for kw in ['趋势', '走势', '变化', '趋势图']):
        modes.append('trend')
    if any(kw in question for kw in ['比较', '对比', '相比', '哪个', '哪只']):
        modes.append('compare')
    if any(kw in question for kw in ['最高', '最大', '最低', '最小', '极值']):
        modes.append('extreme')
    if any(kw in question for kw in ['统计', '汇总', '平均', '均值', '中位数']):
        modes.append('statistics')
    if any(kw in question for kw in ['评价', '评价一下', '分析', '看法', '觉得', '怎么样', '如何', '好不好']):
        modes.append('evaluate')
    if not modes:
        modes.append('simple')
    return '+'.join(modes)


def _build_analyst_prompt(question: str, df: pd.DataFrame, analysis_mode: str) -> str:
    instruction_parts = []
    for mode in analysis_mode.split('+'):
        if mode in ANALYSIS_INSTRUCTIONS:
            instruction_parts.append(ANALYSIS_INSTRUCTIONS[mode])
    instruction = '\n\n'.join(instruction_parts) if instruction_parts else ANALYSIS_INSTRUCTIONS['simple']

    stats = _compute_stats(df)
    stats_lines = []
    for key, value in stats.items():
        if key in ('row_count', 'column_count', 'days_count'):
            stats_lines.append(f"- {key}: {value}")
        elif key == 'date_range':
            stats_lines.append(f"- 数据时间范围: {value}")
        else:
            label = key.replace('_', ' ')
            stats_lines.append(f"- {label}: {value}")
    stats_section = '\n'.join(stats_lines)

    prompt_template = _load_prompt_templates()['analyst_system_prompt']
    if '{analysis_instruction}' in prompt_template:
        base_prompt = prompt_template.format(analysis_instruction=instruction)
    else:
        base_prompt = f"{prompt_template}\n\n分析指令：{instruction}"
    return f"{base_prompt}\n\n数据统计摘要：\n{stats_section}"


def _analyze_data(question: str, sql_text: str, df: pd.DataFrame) -> str:
    if df.empty:
        return '查询结果为空。'
    analysis_mode = _detect_analysis_mode(question)
    system_prompt = _build_analyst_prompt(question, df, analysis_mode)
    raw = _call_model(
        [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f'用户问题：{question}\n\nSQL：{sql_text}\n\n查询结果：\n{df.head(20).to_markdown(index=False)}'},
        ],
        temperature=0.3,
    )
    if raw.strip():
        return raw.strip()
    return f'查询完成，返回 {len(df)} 行数据。\n\n{df.head(20).to_markdown(index=False)}'


def _result_preview_to_json(df: pd.DataFrame) -> str:
    return df.head(50).to_json(orient='split', force_ascii=False)


def run_chat_query(question: str, context_package: dict[str, Any]) -> dict[str, Any]:
    context_text = context_package.get('context_text', '')
    intent_plan = resolve_intent_from_session(question, context_package)
    cache_key = _build_cache_key(question, context_text, intent_plan)
    cached = get_cache(cache_key)
    if cached:
        _get_log().info('缓存命中，cache_key=%s', cache_key)
        return {
            'content': cached['answer_text'],
            'sql_text': cached.get('sql_text'),
            'result_preview': cached.get('result_preview'),
            'chart_path': cached.get('chart_path'),
            'from_cache': True,
            'status': 'success',
            'error_message': None,
        }
    return _run_pipeline(question, context_package, cache_key, intent_plan)


def _run_pipeline(
    question: str,
    context_package: dict[str, Any],
    cache_key: str,
    intent_plan: dict[str, Any],
) -> dict[str, Any]:
    context_text = context_package.get('context_package_text') or context_package.get('context_text', '')
    resolved_prompt = str(intent_plan.get('normalized_question') or question)

    if intent_plan.get('needs_confirmation'):
        return {
            'content': intent_plan.get('confirmation_question') or '我需要确认一下你的意图，请补充更多信息。',
            'sql_text': _build_confirmation_marker(intent_plan),
            'result_preview': None,
            'chart_path': None,
            'from_cache': False,
            'status': 'success',
            'error_message': None,
        }

    if intent_plan.get('intent_type') == 'forecast':
        tscode = str(intent_plan.get('tscode') or '').strip().upper()
        n_days = _safe_int(intent_plan.get('n_days')) or DEFAULT_ARIMA_N
        if not tscode:
            return {
                'content': '请明确你要预测哪只股票（可说茅台/五粮液）以及预测天数。',
                'sql_text': _build_confirmation_marker(
                    {
                        'intent_type': 'forecast',
                        'tscode': None,
                        'stock_name': None,
                        'n_days': n_days,
                    }
                ),
                'result_preview': None,
                'chart_path': None,
                'from_cache': False,
                'status': 'success',
                'error_message': None,
            }

        arima_result = _run_arima_tool(tscode, n_days)
        if arima_result.get('status') == 'success':
            set_cache(
                cache_key,
                arima_result.get('sql_text'),
                arima_result.get('result_preview'),
                arima_result.get('content'),
                arima_result.get('chart_path'),
                settings.query_cache_ttl,
            )
        return arima_result

    classify_result = _classify_and_generate(resolved_prompt, context_text)
    data_query = classify_result.get('data_query', True)
    reply = classify_result.get('reply', '')
    if not data_query:
        return {
            'content': reply or '你好！有什么股票数据需要查询吗？',
            'sql_text': None,
            'result_preview': None,
            'chart_path': None,
            'from_cache': False,
            'status': 'success',
            'error_message': None,
        }

    sql_text = classify_result.get('sql', '')
    if not sql_text:
        sql_text = _generate_fallback_sql(resolved_prompt)
        _get_log().info('SQL生成失败，使用兜底SQL: %s', sql_text)

    runtime = get_runtime_model_settings()
    sql_text = validate_sql(sql_text, settings.max_result_rows)
    df = None
    last_error = ''
    max_retry = max(1, runtime['retry_count'] + 1)
    for attempt in range(max_retry):
        try:
            df = _execute_sql(sql_text)
            break
        except Exception as exc:
            last_error = str(exc)
            _get_log().warning('SQL执行失败(第%d次): %s', attempt + 1, last_error)
            if attempt < max_retry - 1:
                correction = _correct_sql(resolved_prompt, sql_text, last_error)
                if correction.get('needs_sql', True) and correction.get('sql'):
                    sql_text = validate_sql(correction['sql'], settings.max_result_rows)
                else:
                    return {
                        'content': correction.get('answer', f'SQL 执行多次失败：{last_error}'),
                        'sql_text': sql_text,
                        'result_preview': None,
                        'chart_path': None,
                        'from_cache': False,
                        'status': 'failed',
                        'error_message': last_error,
                    }
            else:
                return {
                    'content': f'SQL 执行失败，已重试{max_retry}次。错误信息：{last_error}',
                    'sql_text': sql_text,
                    'result_preview': None,
                    'chart_path': None,
                    'from_cache': False,
                    'status': 'failed',
                    'error_message': last_error,
                }

    chart_path = _render_chart(df)
    answer = _analyze_data(resolved_prompt, sql_text, df)
    result_preview = _result_preview_to_json(df)
    set_cache(cache_key, sql_text, result_preview, answer, chart_path, settings.query_cache_ttl)

    return {
        'content': answer,
        'sql_text': sql_text,
        'result_preview': result_preview,
        'chart_path': chart_path,
        'from_cache': False,
        'status': 'success',
        'error_message': None,
    }


def execute_chat_for_session(session_id: str, question: str, username: str) -> dict[str, Any]:
    messages = get_messages(session_id)
    context_package = build_session_context(messages, CONTEXT_WINDOW_ROUNDS)
    started_at = time.perf_counter()
    try:
        result = run_chat_query(question, context_package)
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        result['duration_ms'] = duration_ms
        save_context(session_id, question, result['content'])
        add_message(session_id, 'user', question)
        add_message(
            session_id,
            'assistant',
            result['content'],
            sql_text=result.get('sql_text'),
            result_preview=result.get('result_preview'),
            chart_path=result.get('chart_path'),
        )
        update_title_if_placeholder(session_id, question)
        record_query_audit(
            username=username,
            session_id=session_id,
            question=question,
            sql_text=result.get('sql_text'),
            duration_ms=duration_ms,
            from_cache=result.get('from_cache', False),
            chart_generated=bool(result.get('chart_path')),
            status=result.get('status', 'success'),
            error_message=result.get('error_message'),
        )
        return result
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        record_query_audit(
            username=username,
            session_id=session_id,
            question=question,
            sql_text=None,
            duration_ms=duration_ms,
            from_cache=False,
            chart_generated=False,
            status='failed',
            error_message=str(exc),
        )
        raise


def stream_text_chunks(text: str, chunk_size: int = 24) -> list[str]:
    clean_text = text or ''
    return [clean_text[index:index + chunk_size] for index in range(0, len(clean_text), chunk_size)] or ['']
