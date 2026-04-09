"""
SQL Validator
=============
Validates SQL queries at the *structure* level before execution.
Does NOT use a full SQL parser or EXPLAIN — instead checks:

  1. Query type      — only SELECT is permitted
  2. Injection guard — blocks comments, statement separators, and
                       other patterns that could smuggle in extra SQL
  3. Table existence — every table referenced in FROM / JOIN must
                       exist in the target database

API
---
    validate_query(sql, db_path) -> {"valid": bool, "error": str | None}

    check_query_type(sql)                  -> (bool, str | None)
    check_no_injection_patterns(sql)       -> (bool, str | None)
    extract_referenced_tables(sql)         -> list[str]
    check_tables_exist(tables, db_path)    -> (bool, str | None)
    get_db_tables(db_path)                 -> set[str]

Design notes
------------
- The LLM Adapter is a *consumer* of this module; it never bypasses it.
- The validator defines what is safe — not the LLM.
- Column-level validation is intentionally out of scope for v1.
  Tables are the security boundary; columns are a query-correctness concern.
"""

import re
import sqlite3

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

ALLOWED_QUERY_TYPES = {"SELECT"}

# Patterns that indicate attempts to inject extra SQL or hide intent.
# Checked as raw regex against the full query string.
_INJECTION_PATTERNS = [
    (r"--",      "line comment (--)"),
    (r"/\*",     "block comment (/*)"),
    (r"\*/",     "block comment (*/)"),
    (r";",       "statement separator (;)"),
    (r"\bEXEC\b","EXEC keyword"),
    (r"\bxp_",   "extended procedure prefix (xp_)"),
]


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def check_query_type(sql):
    """
    Confirm the query starts with an allowed keyword (SELECT only).

    Args:
        sql (str): The SQL query string.

    Returns:
        tuple[bool, str | None]: (is_valid, error_message)
    """
    first_word = sql.strip().split()[0].upper() if sql.strip() else ""
    if first_word not in ALLOWED_QUERY_TYPES:
        return False, (
            f"Query type '{first_word}' is not allowed. "
            "Only SELECT queries are permitted."
        )
    return True, None


def check_no_injection_patterns(sql):
    """
    Reject queries containing patterns associated with SQL injection
    or multi-statement execution.

    Args:
        sql (str): The SQL query string.

    Returns:
        tuple[bool, str | None]: (is_valid, error_message)
    """
    for pattern, label in _INJECTION_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE):
            return False, f"Query contains disallowed pattern: {label}"
    return True, None


def extract_referenced_tables(sql):
    """
    Extract the names of all tables referenced in FROM and JOIN clauses,
    including comma-separated multi-table FROM lists.

    Handles:
      - FROM single_table
      - FROM table1, table2, table3
      - JOIN table_name
      - Aliases: FROM users u  /  FROM users AS u

    Does NOT descend into subqueries — subquery aliases are not real tables
    and should not be validated against the database.

    Args:
        sql (str): The SQL query string.

    Returns:
        list[str]: Unique table names (lower-cased).
    """
    tables = set()

    # Match the full FROM clause up to WHERE / GROUP / ORDER / HAVING /
    # LIMIT / JOIN or end-of-string, then split on commas.
    from_block = re.search(
        r'\bFROM\s+(.*?)(?:\s+(?:WHERE|GROUP|ORDER|HAVING|LIMIT|JOIN|INNER|LEFT|RIGHT|FULL|CROSS)\b|$)',
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    if from_block:
        for token in from_block.group(1).split(","):
            token = token.strip()
            # First word of each token is the table name (ignores alias)
            match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)', token)
            if match:
                tables.add(match.group(1).lower())

    # Capture each JOIN … table
    for match in re.finditer(
        r'\bJOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        sql,
        re.IGNORECASE,
    ):
        tables.add(match.group(1).lower())

    return list(tables)


def get_db_tables(db_path):
    """
    Return the set of table names that exist in the SQLite database.

    Args:
        db_path (str): Path to the SQLite .db file.

    Returns:
        set[str]: Lower-cased table names.
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        return {row[0].lower() for row in cursor.fetchall()}
    finally:
        conn.close()


def check_tables_exist(tables, db_path):
    """
    Verify that every table name extracted from the query exists in the DB.

    Args:
        tables (list[str]): Table names to check.
        db_path (str): Path to the SQLite database.

    Returns:
        tuple[bool, str | None]: (is_valid, error_message)
    """
    if not tables:
        return True, None

    existing = get_db_tables(db_path)
    missing = [t for t in tables if t not in existing]
    if missing:
        return False, f"Table(s) not found in database: {', '.join(sorted(missing))}"
    return True, None


def validate_query(sql, db_path):
    """
    Full validation pipeline.

    Steps (in order):
      1. Check query type (SELECT only)
      2. Check for injection patterns
      3. Extract referenced tables and confirm they exist in the DB

    Args:
        sql (str): The SQL query to validate.
        db_path (str): Path to the SQLite database.

    Returns:
        dict: {"valid": bool, "error": str | None}
    """
    for check in (
        lambda: check_query_type(sql),
        lambda: check_no_injection_patterns(sql),
        lambda: check_tables_exist(extract_referenced_tables(sql), db_path),
    ):
        valid, error = check()
        if not valid:
            return {"valid": False, "error": error}

    return {"valid": True, "error": None}
