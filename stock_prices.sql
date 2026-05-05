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

CREATE INDEX idx_stock_prices_trade_date ON stock_prices(trade_date);
CREATE INDEX idx_stock_prices_stock_name ON stock_prices(stock_name);
