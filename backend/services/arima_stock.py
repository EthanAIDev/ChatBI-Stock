import hashlib
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from backend.config import settings

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

ARIMA_ORDER = (5, 1, 5)
DEFAULT_N = 7
MAX_N = 120
MIN_POINTS = 30


def _normalize_tscode(tscode: str) -> str:
    return (tscode or '').strip().upper()


def _validate_n(n: int | None) -> int:
    if n is None:
        return DEFAULT_N
    if n <= 0:
        raise ValueError('预测天数 n 必须大于 0')
    if n > MAX_N:
        raise ValueError(f'预测天数 n 不能超过 {MAX_N}')
    return n


def _load_history(tscode: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    today = date.today().isoformat()
    with sqlite3.connect(settings.db_path) as conn:
        df_all = pd.read_sql_query(
            """
            SELECT trade_date, close
            FROM stock_prices
            WHERE ts_code = ?
              AND trade_date <= ?
              AND close IS NOT NULL
            ORDER BY trade_date ASC
            """,
            conn,
            params=(tscode, today),
        )

    if df_all.empty:
        raise ValueError('股票代码不存在或无可用数据')

    df_all['trade_date'] = pd.to_datetime(df_all['trade_date'])
    cutoff = pd.Timestamp(date.today() - timedelta(days=365))
    df_recent = df_all[df_all['trade_date'] >= cutoff].copy()
    if len(df_recent) >= MIN_POINTS:
        return df_recent, df_recent
    return df_recent, df_all.copy()


def _next_trade_dates(last_trade_date: datetime, n: int) -> list[str]:
    dates: list[str] = []
    cursor = last_trade_date
    while len(dates) < n:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            dates.append(cursor.strftime('%Y-%m-%d'))
    return dates


def _render_forecast_chart(
    tscode: str,
    history_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
) -> str:
    image_dir = Path(settings.image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(
        f'{tscode}|{history_df.trade_date.iloc[-1]}|{len(history_df)}|{len(forecast_df)}'.encode('utf-8')
    ).hexdigest()[:16]
    chart_filename = f'arima_{tscode}_{digest}.png'
    chart_path = image_dir / chart_filename

    forecast_dates = pd.to_datetime(forecast_df['future_date'])
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(
        history_df['trade_date'],
        history_df['close'],
        label='历史收盘价',
        color='#3b82f6',
        linewidth=1.8,
    )
    ax.plot(
        forecast_dates,
        forecast_df['predicted_close'],
        label='ARIMA预测',
        color='#f59e0b',
        linestyle='--',
        linewidth=2,
    )
    ax.fill_between(
        forecast_dates,
        forecast_df['lower_ci'],
        forecast_df['upper_ci'],
        color='#f59e0b',
        alpha=0.2,
        label='95%置信区间',
    )
    ax.set_title(f'{tscode} 收盘价历史与未来预测')
    ax.set_xlabel('交易日')
    ax.set_ylabel('价格')
    ax.legend()
    all_dates = pd.concat(
        [history_df['trade_date'].reset_index(drop=True), forecast_dates.reset_index(drop=True)],
        ignore_index=True,
    )
    if len(all_dates) > 14:
        max_labels = 12
        step = max(1, len(all_dates) // max_labels)
        tick_dates = all_dates.iloc[::step].tolist()
        if tick_dates[-1] != all_dates.iloc[-1]:
            tick_dates.append(all_dates.iloc[-1])
        ax.set_xticks(tick_dates)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close(fig)
    return str(chart_path)


def arima_stock(tscode: str, n: int = DEFAULT_N) -> dict[str, Any]:
    normalized_tscode = _normalize_tscode(tscode)
    if not normalized_tscode:
        raise ValueError('tscode 必填')
    n = _validate_n(n)

    recent_df, fitting_df = _load_history(normalized_tscode)
    if len(fitting_df) < MIN_POINTS:
        raise ValueError(f'历史数据不足，至少需要 {MIN_POINTS} 条有效收盘价')

    try:
        from statsmodels.tsa.arima.model import ARIMA
    except ModuleNotFoundError as exc:
        raise RuntimeError('缺少依赖 statsmodels，请先安装：pip install statsmodels') from exc

    series = fitting_df['close'].astype(float)
    model = ARIMA(series, order=ARIMA_ORDER, enforce_stationarity=False, enforce_invertibility=False)
    fitted = model.fit()
    forecast_res = fitted.get_forecast(steps=n)

    predicted = forecast_res.predicted_mean
    conf_int = forecast_res.conf_int(alpha=0.05)
    lower_col = conf_int.columns[0]
    upper_col = conf_int.columns[1]

    future_dates = _next_trade_dates(fitting_df['trade_date'].iloc[-1], n)
    forecast_df = pd.DataFrame(
        {
            'future_date': future_dates,
            'predicted_close': predicted.to_numpy(),
            'lower_ci': conf_int[lower_col].to_numpy(),
            'upper_ci': conf_int[upper_col].to_numpy(),
        }
    )
    forecast_df['predicted_close'] = forecast_df['predicted_close'].round(2)
    forecast_df['lower_ci'] = forecast_df['lower_ci'].round(2)
    forecast_df['upper_ci'] = forecast_df['upper_ci'].round(2)

    history_df = fitting_df[['trade_date', 'close']].copy()
    history_df['trade_date'] = history_df['trade_date'].dt.strftime('%Y-%m-%d')
    history_df['close'] = history_df['close'].astype(float).round(2)

    chart_path = _render_forecast_chart(normalized_tscode, fitting_df, forecast_df)

    fallback_used = len(recent_df) < MIN_POINTS
    summary_text = (
        f"已使用 {normalized_tscode} 从 {history_df['trade_date'].iloc[0]} 到 {history_df['trade_date'].iloc[-1]} "
        f"的 {len(history_df)} 条收盘价数据，采用 ARIMA{ARIMA_ORDER} 预测未来 {n} 个交易日。"
        f"预测区间：{forecast_df['future_date'].iloc[0]} ~ {forecast_df['future_date'].iloc[-1]}，"
        f"首日预测 {forecast_df['predicted_close'].iloc[0]}，末日预测 {forecast_df['predicted_close'].iloc[-1]}。"
    )
    if fallback_used:
        summary_text += '（近一年数据不足，已自动回退到可用历史数据建模）'

    return {
        'history': history_df.to_dict(orient='records'),
        'forecast': forecast_df.to_dict(orient='records'),
        'result_preview': forecast_df.to_json(orient='split', force_ascii=False),
        'chart_path': chart_path,
        'summary_text': summary_text,
        'model': 'ARIMA',
        'order': ARIMA_ORDER,
        'tscode': normalized_tscode,
        'n': n,
    }
