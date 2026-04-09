import sqlite3


def get_connection(db_path):
    """
    Open and return a connection to the SQLite database.

    Args:
        db_path (str): Path to the SQLite .db file.

    Returns:
        sqlite3.Connection
    """
    return sqlite3.connect(db_path)


def execute_non_query(db_path, sql, params=()):
    """
    Execute a SQL statement that does not return rows (CREATE, DROP, etc).

    Args:
        db_path (str): Path to the SQLite database.
        sql (str): SQL statement to execute.
        params (tuple): Optional bind parameters.
    """
    conn = get_connection(db_path)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def insert_rows(db_path, table_name, columns, rows):
    """
    Bulk-insert rows into a table using hand-built SQL (no df.to_sql).

    Args:
        db_path (str): Path to the SQLite database.
        table_name (str): Target table name.
        columns (list[str]): Column names matching the row tuples.
        rows (list[tuple]): Row data to insert.
    """
    placeholders = ", ".join("?" * len(columns))
    col_names = ", ".join(columns)
    sql = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"

    conn = get_connection(db_path)
    try:
        conn.executemany(sql, rows)
        conn.commit()
    finally:
        conn.close()


def fetch_all(db_path, sql, params=()):
    """
    Execute a SELECT and return all result rows with column names.

    Args:
        db_path (str): Path to the SQLite database.
        sql (str): SELECT statement to execute.
        params (tuple): Optional bind parameters.

    Returns:
        tuple: (columns: list[str], rows: list[tuple])
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(sql, params)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return columns, rows
    finally:
        conn.close()
