import hashlib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from logger_utils import get_daily_logger


LOG = get_daily_logger('semantic_layer')
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'stock_prices.db'
SCHEMA_DB_PATH = BASE_DIR / 'schema_vector.db'


def get_db_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def get_schema_db_connection() -> sqlite3.Connection:
    return sqlite3.connect(SCHEMA_DB_PATH)


def init_schema_metadata_table() -> None:
    with get_schema_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                table_description TEXT,
                field_name TEXT NOT NULL,
                field_type TEXT,
                field_description TEXT,
                business语义 TEXT,
                is_key_field INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(table_name, field_name)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_schema_table ON schema_metadata(table_name)"
        )


def init_vector_table() -> None:
    with get_schema_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                field_name TEXT NOT NULL,
                combined_text TEXT NOT NULL,
                vector BLOB,
                updated_at TEXT NOT NULL,
                UNIQUE(table_name, field_name)
            )
            """
        )


def init_example_table() -> None:
    with get_schema_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sql_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                sql_text TEXT NOT NULL,
                business_scenario TEXT,
                tags TEXT,
                usage_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_examples_question ON sql_examples(question)"
        )


def init_semantic_table() -> None:
    with get_schema_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS semantic_layer (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                layer_type TEXT NOT NULL,
                layer_key TEXT NOT NULL,
                layer_value TEXT NOT NULL,
                description TEXT,
                extra_data TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(layer_type, layer_key)
            )
            """
        )


def init_cache_table() -> None:
    with get_schema_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS query_cache (
                cache_key TEXT PRIMARY KEY,
                sql_hash TEXT NOT NULL,
                sql_text TEXT,
                result_preview TEXT,
                answer_text TEXT,
                chart_path TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )


def now_ts() -> str:
    return datetime.now().isoformat(timespec='seconds')


STOCK_PRICES_METADATA = [
    {
        'table_name': 'stock_prices',
        'table_description': '股票价格日线数据表，包含A股上市公司的每日交易行情',
        'field_name': 'ts_code',
        'field_type': 'TEXT',
        'field_description': '股票代码，格式为 XXXXXX.SH 或 XXXXXX.SZ',
        'business语义': '股票代码，SH表示上海，SZ表示深圳',
        'is_key_field': 1,
    },
    {
        'table_name': 'stock_prices',
        'table_description': '股票价格日线数据表，包含A股上市公司的每日交易行情',
        'field_name': 'stock_name',
        'field_type': 'TEXT',
        'field_description': '股票名称',
        'business语义': '股票简称，如贵州茅台、五粮液',
        'is_key_field': 1,
    },
    {
        'table_name': 'stock_prices',
        'table_description': '股票价格日线数据表，包含A股上市公司的每日交易行情',
        'field_name': 'trade_date',
        'field_type': 'TEXT',
        'field_description': '交易日期，格式为 YYYY-MM-DD',
        'business语义': '日期，用于按时间筛选和聚合',
        'is_key_field': 1,
    },
    {
        'table_name': 'stock_prices',
        'table_description': '股票价格日线数据表，包含A股上市公司的每日交易行情',
        'field_name': 'open',
        'field_type': 'REAL',
        'field_description': '开盘价，单位为元',
        'business语义': '当日开盘价格',
        'is_key_field': 0,
    },
    {
        'table_name': 'stock_prices',
        'table_description': '股票价格日线数据表，包含A股上市公司的每日交易行情',
        'field_name': 'high',
        'field_type': 'REAL',
        'field_description': '最高价，单位为元',
        'business语义': '当日最高价格',
        'is_key_field': 0,
    },
    {
        'table_name': 'stock_prices',
        'table_description': '股票价格日线数据表，包含A股上市公司的每日交易行情',
        'field_name': 'low',
        'field_type': 'REAL',
        'field_description': '最低价，单位为元',
        'business语义': '当日最低价格',
        'is_key_field': 0,
    },
    {
        'table_name': 'stock_prices',
        'table_description': '股票价格日线数据表，包含A股上市公司的每日交易行情',
        'field_name': 'close',
        'field_type': 'REAL',
        'field_description': '收盘价，单位为元',
        'business语义': '当日收盘价格，最常用的价格字段',
        'is_key_field': 0,
    },
    {
        'table_name': 'stock_prices',
        'table_description': '股票价格日线数据表，包含A股上市公司的每日交易行情',
        'field_name': 'pre_close',
        'field_type': 'REAL',
        'field_description': '前一日收盘价，单位为元',
        'business语义': '昨日收盘价，用于计算涨跌幅',
        'is_key_field': 0,
    },
    {
        'table_name': 'stock_prices',
        'table_description': '股票价格日线数据表，包含A股上市公司的每日交易行情',
        'field_name': 'change',
        'field_type': 'REAL',
        'field_description': '涨跌额，单位为元，等于 close - pre_close',
        'business语义': '价格变化金额',
        'is_key_field': 0,
    },
    {
        'table_name': 'stock_prices',
        'table_description': '股票价格日线数据表，包含A股上市公司的每日交易行情',
        'field_name': 'pct_chg',
        'field_type': 'REAL',
        'field_description': '涨跌幅，单位为百分比，等于 (close - pre_close) / pre_close * 100',
        'business语义': '涨跌幅(%)，正值表示上涨，负值表示下跌',
        'is_key_field': 0,
    },
    {
        'table_name': 'stock_prices',
        'table_description': '股票价格日线数据表，包含A股上市公司的每日交易行情',
        'field_name': 'vol',
        'field_type': 'REAL',
        'field_description': '成交量，单位为手（1手=100股）',
        'business语义': '当日成交量',
        'is_key_field': 0,
    },
    {
        'table_name': 'stock_prices',
        'table_description': '股票价格日线数据表，包含A股上市公司的每日交易行情',
        'field_name': 'amount',
        'field_type': 'REAL',
        'field_description': '成交额，单位为千元',
        'business语义': '当日成交金额',
        'is_key_field': 0,
    },
]


STOCK_EXAMPLES = [
    {
        'question': '查询贵州茅台从2025-01-01到2025-01-31的收盘价走势',
        'sql_text': "SELECT trade_date, close FROM stock_prices WHERE stock_name = '贵州茅台' AND trade_date >= '2025-01-01' AND trade_date <= '2025-01-31' ORDER BY trade_date ASC",
        'business_scenario': '单只股票价格走势查询',
        'tags': '走势,收盘价,单只股票,日期范围',
    },
    {
        'question': '比较2024年1月贵州茅台、五粮液、中芯国际、广发证券的平均收盘价',
        'sql_text': "SELECT stock_name, AVG(close) as avg_close FROM stock_prices WHERE stock_name IN ('贵州茅台', '五粮液', '中芯国际', '广发证券') AND trade_date >= '2024-01-01' AND trade_date <= '2024-01-31' GROUP BY stock_name",
        'business_scenario': '多只股票平均价格对比',
        'tags': '比较,平均收盘价,多只股票,月份',
    },
    {
        'question': '查询中芯国际历史最高收盘价及对应日期',
        'sql_text': "SELECT trade_date, close FROM stock_prices WHERE stock_name = '中芯国际' ORDER BY close DESC LIMIT 1",
        'business_scenario': '股票历史极值查询',
        'tags': '最高,收盘价,单只股票',
    },
    {
        'question': '查询贵州茅台最近30个交易日的涨跌幅',
        'sql_text': "SELECT trade_date, pct_chg FROM (SELECT trade_date, pct_chg FROM stock_prices WHERE stock_name = '贵州茅台' ORDER BY trade_date DESC LIMIT 30) ORDER BY trade_date ASC",
        'business_scenario': '涨跌幅序列查询',
        'tags': '涨跌幅,最近,单只股票',
    },
    {
        'question': '查询五粮液2024年成交额最高的5个交易日',
        'sql_text': "SELECT trade_date, amount FROM stock_prices WHERE stock_name = '五粮液' AND trade_date >= '2024-01-01' AND trade_date <= '2024-12-31' ORDER BY amount DESC LIMIT 5",
        'business_scenario': '成交额极值查询',
        'tags': '成交额,最高,单只股票,年度',
    },
    {
        'question': '查询广发证券2024年每月平均收盘价',
        'sql_text': "SELECT strftime('%Y-%m', trade_date) as month, AVG(close) as avg_close FROM stock_prices WHERE stock_name = '广发证券' AND trade_date >= '2024-01-01' AND trade_date <= '2024-12-31' GROUP BY month ORDER BY month ASC",
        'business_scenario': '月度聚合统计',
        'tags': '月度聚合,平均收盘价,单只股票',
    },
    {
        'question': '查询贵州茅台和五粮液的收盘价对比（2024年全年）',
        'sql_text': "SELECT trade_date, stock_name, close FROM stock_prices WHERE stock_name IN ('贵州茅台', '五粮液') AND trade_date >= '2024-01-01' AND trade_date <= '2024-12-31' ORDER BY trade_date ASC, stock_name ASC",
        'business_scenario': '多只股票价格时序对比',
        'tags': '比较,收盘价,多只股票,年度,走势',
    },
    {
        'question': '查询所有股票在2025年1月的总成交额',
        'sql_text': "SELECT stock_name, SUM(amount) as total_amount FROM stock_prices WHERE trade_date >= '2025-01-01' AND trade_date <= '2025-01-31' GROUP BY stock_name ORDER BY total_amount DESC",
        'business_scenario': '月度成交额汇总',
        'tags': '成交额,汇总,多只股票,月份',
    },
    {
        'question': '查询中芯国际历史最低收盘价及对应日期',
        'sql_text': "SELECT trade_date, close FROM stock_prices WHERE stock_name = '中芯国际' ORDER BY close ASC LIMIT 1",
        'business_scenario': '股票历史极值查询',
        'tags': '最低,收盘价,单只股票',
    },
    {
        'question': '查询贵州茅台2024年12月的开盘价、收盘价、最高价、最低价',
        'sql_text': "SELECT trade_date, open, close, high, low FROM stock_prices WHERE stock_name = '贵州茅台' AND trade_date >= '2024-12-01' AND trade_date <= '2024-12-31' ORDER BY trade_date ASC",
        'business_scenario': '蜡烛图数据查询',
        'tags': 'OHLC,单只股票,月份',
    },
]


STOCK_SEMANTIC_LAYER = [
    {
        'layer_type': 'synonym',
        'layer_key': '茅台',
        'layer_value': '贵州茅台',
        'description': '贵州茅台的简称',
    },
    {
        'layer_type': 'synonym',
        'layer_key': '五粮液',
        'layer_value': '五粮液',
        'description': '五粮液简称',
    },
    {
        'layer_type': 'synonym',
        'layer_key': '中芯国际',
        'layer_value': '中芯国际',
        'description': '中芯国际简称',
    },
    {
        'layer_type': 'synonym',
        'layer_key': '广发证券',
        'layer_value': '广发证券',
        'description': '广发证券简称',
    },
    {
        'layer_type': 'synonym',
        'layer_key': '收盘价',
        'layer_value': 'close',
        'description': '收盘价字段映射',
    },
    {
        'layer_type': 'synonym',
        'layer_key': '开盘价',
        'layer_value': 'open',
        'description': '开盘价字段映射',
    },
    {
        'layer_type': 'synonym',
        'layer_key': '最高价',
        'layer_value': 'high',
        'description': '最高价字段映射',
    },
    {
        'layer_type': 'synonym',
        'layer_key': '最低价',
        'layer_value': 'low',
        'description': '最低价字段映射',
    },
    {
        'layer_type': 'synonym',
        'layer_key': '涨跌幅',
        'layer_value': 'pct_chg',
        'description': '涨跌幅字段映射，单位为百分比',
    },
    {
        'layer_type': 'synonym',
        'layer_key': '涨跌额',
        'layer_value': 'change',
        'description': '涨跌额字段映射，单位为元',
    },
    {
        'layer_type': 'synonym',
        'layer_key': '成交量',
        'layer_value': 'vol',
        'description': '成交量字段映射，单位为手',
    },
    {
        'layer_type': 'synonym',
        'layer_key': '成交额',
        'layer_value': 'amount',
        'description': '成交额字段映射，单位为千元',
    },
    {
        'layer_type': 'indicator',
        'layer_key': '平均收盘价',
        'layer_value': 'AVG(close)',
        'description': '平均收盘价指标',
    },
    {
        'layer_type': 'indicator',
        'layer_key': '最高收盘价',
        'layer_value': 'MAX(close)',
        'description': '最高收盘价指标',
    },
    {
        'layer_type': 'indicator',
        'layer_key': '最低收盘价',
        'layer_value': 'MIN(close)',
        'description': '最低收盘价指标',
    },
    {
        'layer_type': 'dimension',
        'layer_key': '按月份',
        'layer_value': "strftime('%Y-%m', trade_date)",
        'description': '月度时间维度',
    },
    {
        'layer_type': 'dimension',
        'layer_key': '按季度',
        'layer_value': "CASE WHEN substr(trade_date, 6, 2) IN ('01','02','03') THEN substr(trade_date, 1, 4) || 'Q1' WHEN substr(trade_date, 6, 2) IN ('04','05','06') THEN substr(trade_date, 1, 4) || 'Q2' WHEN substr(trade_date, 6, 2) IN ('07','08','09') THEN substr(trade_date, 1, 4) || 'Q3' ELSE substr(trade_date, 1, 4) || 'Q4' END",
        'description': '季度时间维度',
    },
    {
        'layer_type': 'dimension',
        'layer_key': '按年度',
        'layer_value': "strftime('%Y', trade_date)",
        'description': '年度时间维度',
    },
]


def seed_all_metadata() -> None:
    init_schema_metadata_table()
    init_vector_table()
    init_example_table()
    init_semantic_table()
    init_cache_table()

    with get_schema_db_connection() as conn:
        for meta in STOCK_PRICES_METADATA:
            existing = conn.execute(
                "SELECT id FROM schema_metadata WHERE table_name = ? AND field_name = ?",
                (meta['table_name'], meta['field_name']),
            ).fetchone()
            if not existing:
                conn.execute(
                    """
                    INSERT INTO schema_metadata (table_name, table_description, field_name, field_type, field_description, business语义, is_key_field, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        meta['table_name'],
                        meta['table_description'],
                        meta['field_name'],
                        meta['field_type'],
                        meta['field_description'],
                        meta['business语义'],
                        meta['is_key_field'],
                        now_ts(),
                    ),
                )

        for example in STOCK_EXAMPLES:
            existing = conn.execute(
                "SELECT id FROM sql_examples WHERE question = ?",
                (example['question'],),
            ).fetchone()
            if not existing:
                conn.execute(
                    """
                    INSERT INTO sql_examples (question, sql_text, business_scenario, tags, usage_count, success_count, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 0, 0, ?, ?)
                    """,
                    (
                        example['question'],
                        example['sql_text'],
                        example['business_scenario'],
                        example['tags'],
                        now_ts(),
                        now_ts(),
                    ),
                )

        for item in STOCK_SEMANTIC_LAYER:
            existing = conn.execute(
                "SELECT id FROM semantic_layer WHERE layer_type = ? AND layer_key = ?",
                (item['layer_type'], item['layer_key']),
            ).fetchone()
            if not existing:
                conn.execute(
                    """
                    INSERT INTO semantic_layer (layer_type, layer_key, layer_value, description, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item['layer_type'],
                        item['layer_key'],
                        item['layer_value'],
                        item['description'],
                        now_ts(),
                        now_ts(),
                    ),
                )

    LOG.info('All metadata seeded successfully')


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a = np.array(a)
    b = np.array(b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def get_embedding(text: str) -> tuple[list[float], int]:
    try:
        from openai import OpenAI
    except ImportError:
        LOG.error('openai package not available')
        return [0.0] * 1024, 1024

    api_key = os.getenv('DASHSCOPE_API_KEY', '')
    base_url = os.getenv('DASHSCOPE_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
    if not api_key:
        LOG.warning('DASHSCOPE_API_KEY not set, using zero vectors')
        return [0.0] * 1024, 1024

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.embeddings.create(
        model='text-embedding-v3',
        input=text,
    )
    embedding = response.data[0].embedding
    return embedding, len(embedding)


def build_combined_text(row: dict[str, Any]) -> str:
    parts = [
        row.get('table_description', ''),
        f"表名: {row['table_name']}",
        f"字段名: {row['field_name']}",
        f"字段类型: {row.get('field_type', '')}",
        f"字段描述: {row.get('field_description', '')}",
        f"业务语义: {row.get('business语义', '')}",
    ]
    return ' | '.join(p for p in parts if p)


def compute_and_store_vectors() -> None:
    init_schema_metadata_table()
    init_vector_table()

    with get_schema_db_connection() as conn:
        rows = conn.execute("SELECT id, table_name, field_name, table_description, field_description, business语义 FROM schema_metadata").fetchall()

    for row in rows:
        meta_id, table_name, field_name, table_desc, field_desc, biz_sem = row
        combined = f"{table_desc} | 字段: {field_name} | {field_desc} | {biz_sem}"

        vector, dim = get_embedding(combined)
        vector_bytes = np.array(vector, dtype=np.float32).tobytes()

        with get_schema_db_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO schema_vectors (table_name, field_name, combined_text, vector, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (table_name, field_name, combined, vector_bytes, now_ts()),
            )

    LOG.info('Vectors computed and stored for %d fields, dim=%d', len(rows), dim)


def retrieve_relevant_schema(query: str, top_k: int = 6) -> list[dict[str, Any]]:
    query_vector, query_dim = get_embedding(query)

    with get_schema_db_connection() as conn:
        rows = conn.execute("SELECT table_name, field_name, combined_text, vector FROM schema_vectors").fetchall()

    if not rows:
        return []

    scored = []
    for row in rows:
        table_name, field_name, combined_text, vector_bytes = row
        if not vector_bytes:
            continue
        field_dim = len(vector_bytes) // 4
        if field_dim != query_dim:
            LOG.warning('维度不匹配跳过: query_dim=%d, field_dim=%d, field=%s.%s', query_dim, field_dim, table_name, field_name)
            continue
        field_vector = np.frombuffer(vector_bytes, dtype=np.float32).tolist()
        score = cosine_similarity(query_vector, field_vector)
        scored.append({
            'table_name': table_name,
            'field_name': field_name,
            'combined_text': combined_text,
            'score': score,
        })

    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:top_k]


def build_ddl_from_schema(schema_results: list[dict[str, Any]]) -> str:
    table_groups: dict[str, list[dict[str, Any]]] = {}
    for item in schema_results:
        tname = item['table_name']
        if tname not in table_groups:
            table_groups[tname] = []
        table_groups[tname].append(item)

    lines = []
    for table_name, fields in table_groups.items():
        field_lines = []
        for f in fields:
            field_lines.append(f"    {f['field_name']} —— {f['combined_text'].split(' | ')[2] if len(f['combined_text'].split(' | ')) > 2 else ''} ({f['score']:.2f})")
        lines.append(f"表 {table_name} 的相关字段：")
        lines.extend(field_lines)

    return '\n'.join(lines)


def retrieve_similar_examples(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    query_vector, query_dim = get_embedding(query)

    with get_schema_db_connection() as conn:
        rows = conn.execute(
            "SELECT id, question, sql_text, business_scenario, tags FROM sql_examples"
        ).fetchall()

    if not rows:
        return []

    similarities = []
    for row in rows:
        combined = f"问题: {row[1]} | 场景: {row[3]} | 标签: {row[4]}"
        vec, vec_dim = get_embedding(combined)
        if vec_dim != query_dim:
            LOG.warning('示例向量维度不匹配: query_dim=%d, vec_dim=%d, 跳过', query_dim, vec_dim)
            continue
        sim = cosine_similarity(query_vector, vec)
        similarities.append((sim, row))

    similarities.sort(key=lambda x: x[0], reverse=True)
    results = []
    for sim, row in similarities[:top_k]:
        results.append({
            'id': row[0],
            'question': row[1],
            'sql_text': row[2],
            'business_scenario': row[3],
            'tags': row[4],
            'similarity': sim,
        })
    return results


def build_examples_section(examples: list[dict[str, Any]]) -> str:
    if not examples:
        return ""
    lines = ["参考示例（这些示例中的 SQL 仅供参考，不要直接复制）："]
    for ex in examples:
        lines.append(f"\n示例问题：{ex['question']}")
        lines.append(f"对应SQL：{ex['sql_text']}")
    return '\n'.join(lines)


def get_semantic_expansion(text: str) -> str:
    synonyms_map: dict[str, str] = {}
    with get_schema_db_connection() as conn:
        rows = conn.execute(
            "SELECT layer_key, layer_value FROM semantic_layer WHERE layer_type = 'synonym'"
        ).fetchall()
        for row in rows:
            synonyms_map[row[0]] = row[1]

    expanded = text
    for key, value in synonyms_map.items():
        if key in expanded and value != key:
            expanded = expanded.replace(key, f"{key}({value})")

    return expanded


def get_indicator_definition(keyword: str) -> str | None:
    with get_schema_db_connection() as conn:
        row = conn.execute(
            "SELECT layer_value, description FROM semantic_layer WHERE layer_type = 'indicator' AND layer_key LIKE ?",
            (f'%{keyword}%',),
        ).fetchone()
    if row:
        return f"{row[0]} -- {row[1]}"
    return None


def get_dimension_keyword(text: str) -> str | None:
    with get_schema_db_connection() as conn:
        rows = conn.execute(
            "SELECT layer_key, layer_value FROM semantic_layer WHERE layer_type = 'dimension'"
        ).fetchall()
        for row in rows:
            if row[0] in text:
                return row[1]
    return None


def get_cache(sql_hash: str) -> dict[str, Any] | None:
    with get_schema_db_connection() as conn:
        row = conn.execute(
            "SELECT sql_text, result_preview, answer_text, chart_path, expires_at FROM query_cache WHERE cache_key = ?",
            (sql_hash,),
        ).fetchone()
        if row and row[4] >= now_ts():
            return {
                'sql_text': row[0],
                'result_preview': row[1],
                'answer_text': row[2],
                'chart_path': row[3],
            }
    return None


def set_cache(sql_hash: str, sql_text: str, result_preview: str, answer_text: str, chart_path: str | None, ttl_seconds: int = 600) -> None:
    expires_at = datetime.fromisoformat(now_ts()).timestamp() + ttl_seconds
    expires_at_str = datetime.fromtimestamp(expires_at).isoformat(timespec='seconds')
    with get_schema_db_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO query_cache (cache_key, sql_hash, sql_text, result_preview, answer_text, chart_path, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (sql_hash, sql_hash, sql_text, result_preview, answer_text, chart_path, now_ts(), expires_at_str),
        )


def sql_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:32]


def ensure_schema_ready() -> bool:
    try:
        with get_schema_db_connection() as conn:
            rows = conn.execute("SELECT vector FROM schema_vectors LIMIT 1").fetchall()
        if not rows or not rows[0][0]:
            LOG.info('Schema vectors not found, computing...')
            compute_and_store_vectors()
            return True

        test_vector, _ = get_embedding('test')
        stored_dim = len(rows[0][0]) // 4
        if stored_dim != len(test_vector):
            LOG.info('Vector dimension changed (%d -> %d), recomputing...', stored_dim, len(test_vector))
            compute_and_store_vectors()
        return True
    except Exception:
        LOG.exception('Failed to ensure schema ready')
        return False
