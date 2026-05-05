import re
import logging

LOG = logging.getLogger('sql_security')

FORBIDDEN_KEYWORDS = [
    'INSERT ', 'UPDATE ', 'DELETE ', 'DROP ', 'ALTER ', 'CREATE ',
    'ATTACH ', 'DETACH ', 'PRAGMA ', 'REPLACE ', 'TRUNCATE ',
    'GRANT ', 'REVOKE ', 'EXEC ', 'EXECUTE ',
]

FORBIDDEN_FUNCTIONS = [
    'LOAD_FILE', 'INTO OUTFILE', 'INTO DUMPFILE', 'sys_exec',
    'EXECUTE IMMEDIATE', 'xp_cmdshell',
]

ALLOWED_FUNCTIONS = {
    'AVG', 'SUM', 'COUNT', 'MAX', 'MIN', 'GROUP_CONCAT',
    'strftime', 'date', 'time', 'datetime', 'julianday',
    'substr', 'length', 'replace', 'trim', 'upper', 'lower',
    'abs', 'round', 'coalesce', 'ifnull', 'nullif',
    'printf', 'hex', 'typeof', 'total',
    'CAST', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
    'IN', 'NOT', 'NULL', 'IS', 'LIKE', 'BETWEEN', 'EXISTS',
    'AND', 'OR', 'ASC', 'DESC',
}


def validate_sql(sql: str, max_result_rows: int = 5000) -> str:
    sql_clean = sql.strip().rstrip(';').strip()

    if not sql_clean:
        raise ValueError('SQL不能为空')

    sql_upper = sql_clean.upper()

    if not sql_upper.startswith('SELECT'):
        raise ValueError('只允许SELECT语句')

    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in sql_upper:
            raise ValueError(f'禁止的关键词: {keyword.strip()}')

    for func in FORBIDDEN_FUNCTIONS:
        if func.upper() in sql_upper:
            raise ValueError(f'禁止的函数: {func}')

    if 'LIMIT' not in sql_upper:
        sql_clean = f"{sql_clean} LIMIT {max_result_rows}"
    else:
        limit_pattern = re.search(r'LIMIT\s+(\d+)', sql_upper)
        if limit_pattern:
            limit_val = int(limit_pattern.group(1))
            if limit_val > max_result_rows:
                sql_clean = re.sub(
                    r'LIMIT\s+\d+',
                    f'LIMIT {max_result_rows}',
                    sql_clean,
                    count=1,
                    flags=re.IGNORECASE,
                )
                LOG.warning('行数限制从 %d 裁剪到 %d', limit_val, max_result_rows)

    LOG.debug('SQL校验通过: %s', sql_clean)
    return sql_clean
