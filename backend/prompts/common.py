import json

STOCK_MAP = {
    '贵州茅台': '600519.SH',
    '五粮液': '000858.SZ',
    '中芯国际': '688981.SH',
    '广发证券': '000776.SZ',
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

STOCK_NAMES = list(STOCK_MAP.keys())
STOCK_KEYWORDS = [
    '收盘价', '开盘价', '最高价', '最低价', '涨跌幅', '涨跌额',
    '成交量', '成交额', '走势', '价格', '数据', '查询', '比较',
    '统计', '汇总', '平均', '最高', '最低', '排名', '涨', '跌',
    '分析', '总结', '归纳', '评价', '走势图',
]
