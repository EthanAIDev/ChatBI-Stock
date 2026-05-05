import os
import sqlite3
import time
from pathlib import Path

import pandas as pd
import tushare as ts


START_DATE = '20200101'
END_DATE = '20260401'
OUTPUT_DIR = Path(__file__).resolve().parent
EXCEL_PATH = OUTPUT_DIR / 'stock_prices.xlsx'
SQL_PATH = OUTPUT_DIR / 'stock_prices.sql'
SQLITE_PATH = OUTPUT_DIR / 'stock_prices.db'
WORKSHEET_NAME = 'stock_prices'

STOCKS = {
    '600519.SH': '贵州茅台',
    '000858.SZ': '五粮液',
    '688981.SH': '中芯国际',
    '000776.SZ': '广发证券',
}

TABLE_SQL = """CREATE TABLE stock_prices (
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

CREATE INDEX idx_stock_prices_trade_date ON stock_prices(trade_date);
CREATE INDEX idx_stock_prices_stock_name ON stock_prices(stock_name);
"""


def fetch_stock_prices() -> pd.DataFrame:
    token = os.getenv('TUSHARE_TOKEN')
    if not token:
        raise RuntimeError('Missing environment variable TUSHARE_TOKEN')

    pro = ts.pro_api(token=token)
    frames = []
    total = len(STOCKS)
    for index, (ts_code, stock_name) in enumerate(STOCKS.items(), start=1):
        df = pro.daily(ts_code=ts_code, start_date=START_DATE, end_date=END_DATE)
        if df.empty:
            raise RuntimeError(f'No price data returned for {ts_code} ({stock_name})')
        df['stock_name'] = stock_name
        frames.append(df)
        if index < total:
            time.sleep(31)

    merged = pd.concat(frames, ignore_index=True)
    merged = merged[
        ['ts_code', 'stock_name', 'trade_date', 'open', 'high', 'low', 'close', 'pre_close', 'change', 'pct_chg',
         'vol', 'amount']
    ].copy()
    merged['trade_date'] = pd.to_datetime(merged['trade_date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
    merged = merged.sort_values(by=['trade_date', 'ts_code'], ascending=[True, True]).reset_index(drop=True)
    return merged


def save_excel(df: pd.DataFrame) -> None:
    with pd.ExcelWriter(EXCEL_PATH, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=WORKSHEET_NAME, index=False)


def save_sql_file() -> None:
    SQL_PATH.write_text(TABLE_SQL, encoding='utf-8')


def save_sqlite(df: pd.DataFrame) -> None:
    with sqlite3.connect(SQLITE_PATH) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS stock_prices;
            """
        )
        conn.executescript(TABLE_SQL)
        df.to_sql('stock_prices', conn, if_exists='append', index=False)


def main() -> None:
    df = fetch_stock_prices()
    save_excel(df)
    save_sql_file()
    save_sqlite(df)
    print(f'Excel saved to: {EXCEL_PATH}')
    print(f'SQL saved to: {SQL_PATH}')
    print(f'SQLite saved to: {SQLITE_PATH}')
    print(f'Rows inserted: {len(df)}')


if __name__ == '__main__':
    main()
