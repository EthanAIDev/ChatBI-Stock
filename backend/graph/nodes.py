import json
import re
import hashlib
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

from langchain_core.runnables import RunnableConfig
from langchain_community.utilities import SQLDatabase

from backend.config import settings
from backend.graph.state import PipelineState
from backend.prompts.classify import intent_chain, has_data_keywords
from backend.prompts.sql_generator import sql_chain, parse_sql_output
from backend.prompts.analyst import analyst_chain, ANALYSIS_INSTRUCTIONS
from backend.prompts.correction import correction_chain
from backend.prompts.common import CORE_TABLE_DDL, STOCK_NAMES
from backend.vector_store import get_schema_retriever, get_example_retriever
from backend.services.security import validate_sql

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

MAX_RETRY = 3


def classify_intent(state: PipelineState, config: RunnableConfig = None) -> dict:
    question = state["question"]
    if has_data_keywords(question):
        return {"data_query": True, "reply": ""}
    result = intent_chain.invoke({"question": question})
    return {"data_query": result.data_query, "reply": result.reply}


def generate_sql(state: PipelineState, config: RunnableConfig = None) -> dict:
    question = state["question"]
    schema_retriever = get_schema_retriever(6)
    schema_docs = schema_retriever.invoke(question)
    ddl_section = "\n".join([d.page_content for d in schema_docs])

    example_retriever = get_example_retriever(3)
    example_docs = example_retriever.invoke(question)
    few_shot = []
    for doc in example_docs:
        few_shot.append({"role": "user", "content": doc.metadata["question"]})
        few_shot.append({"role": "assistant", "content": doc.metadata["sql_text"]})

    chat_history = state.get("messages", [])

    result = sql_chain.invoke({
        "question": question,
        "ddl_section": ddl_section,
        "few_shot_examples": few_shot,
        "chat_history": chat_history,
    })

    sql = parse_sql_output(result) if isinstance(result, str) else (result.sql if hasattr(result, 'sql') else "")
    if not sql:
        sql = _generate_fallback_sql(question)
    return {"sql": sql}


def execute_sql(state: PipelineState) -> dict:
    sql = state["sql"]
    validated = validate_sql(sql, settings.max_result_rows)

    db_path = f"sqlite:///{settings.db_path}"
    conn = sqlite3.connect(settings.db_path)
    df = pd.read_sql_query(validated, conn)
    conn.close()

    chart_path = _render_chart(df)
    df_json = df.to_json(orient="split", force_ascii=False)
    result_preview = df.head(50).to_json(orient="split", force_ascii=False)

    return {
        "df_json": df_json,
        "result_preview": result_preview,
        "chart_path": chart_path,
    }


def analyze_data(state: PipelineState) -> dict:
    question = state["question"]
    sql = state["sql"]
    from io import StringIO
    df = pd.read_json(StringIO(state["df_json"]), orient="split")

    mode = _detect_analysis_mode(question)
    instruction_parts = []
    for m in mode.split("+"):
        if m in ANALYSIS_INSTRUCTIONS:
            instruction_parts.append(ANALYSIS_INSTRUCTIONS[m])
    instruction = "\n\n".join(instruction_parts) if instruction_parts else ANALYSIS_INSTRUCTIONS["simple"]

    stats = _compute_stats(df)
    stats_lines = "\n".join([f"- {k}: {v}" for k, v in stats.items()])

    response = analyst_chain.invoke({
        "question": question,
        "sql": sql,
        "data": df.head(20).to_markdown(index=False),
        "analysis_instruction": instruction,
        "stats": stats_lines,
    })

    answer = response.content if hasattr(response, 'content') else str(response)
    if not answer.strip():
        answer = f"查询完成，返回 {len(df)} 行数据。\n\n{df.head(20).to_markdown(index=False)}"
    return {"answer": answer, "analysis_mode": mode}


def _generate_fallback_sql(question: str) -> str:
    for name in STOCK_NAMES:
        if name in question:
            return f"SELECT trade_date, close, pct_chg, vol FROM stock_prices WHERE stock_name = '{name}' ORDER BY trade_date DESC LIMIT 50"
    return "SELECT stock_name, trade_date, close, pct_chg, vol FROM stock_prices ORDER BY trade_date DESC LIMIT 50"


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
    else:
        plot_df = df.copy()
        key_col = plot_df.columns[1] if len(plot_df.columns) > 1 and plot_df.columns[1] not in numeric_cols else x_col
        value_col = numeric_cols[0]
        ax.bar(plot_df[key_col].astype(str), plot_df[value_col])
        ax.set_xlabel(str(key_col))
        ax.set_ylabel(str(value_col))

    ax.set_title('查询结果图表')
    if is_time_like:
        ax.set_xlabel(str(x_col))
        ax.set_ylabel('数值')
        ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close(fig)
    return str(chart_path)


def _compute_stats(df: pd.DataFrame) -> dict:
    stats = {'row_count': len(df), 'column_count': len(df.columns)}
    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    for col in numeric_cols[:5]:
        series = df[col].dropna()
        if len(series) == 0:
            continue
        stats[f'{col}_mean'] = round(float(series.mean()), 2)
        stats[f'{col}_median'] = round(float(series.median()), 2)
        stats[f'{col}_std'] = round(float(series.std()), 2) if len(series) > 1 else 0
        stats[f'{col}_max'] = round(float(series.max()), 2)
        stats[f'{col}_min'] = round(float(series.min()), 2)
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
    if any(kw in question for kw in ['评价', '评价一下', '分析', '看法', '觉得', '怎么样', '如何']):
        modes.append('evaluate')
    if not modes:
        modes.append('simple')
    return '+'.join(modes)
