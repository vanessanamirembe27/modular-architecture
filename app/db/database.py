import sqlite3


def get_connection(db_path):
    """
    Establish and return a connection to the SQLite database.

    Args:
        db_path (str): Path to the SQLite database file.

    Returns:
        sqlite3.Connection: Connection object for the database.
    """
    return sqlite3.connect(db_path)


def execute_sql(db_path, sql, params=None):
    """
    Execute a SQL statement that does not return any result rows.

    Args:
        db_path (str): Path to the SQLite database file.
        sql (str): SQL statement to execute.
        params (tuple, optional): Parameters to bind to the SQL statement. Defaults to None.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        conn.commit()


def insert_records(db_path, table_name, columns, records):
    """
    Insert multiple records into a table using a single SQL statement.

    Args:
        db_path (str): Path to the SQLite database file.
        table_name (str): Name of the table to insert records into.
        columns (list): List of column names for the table.
        records (list): List of tuples, where each tuple represents a record to insert.
    """
    placeholders = ', '.join(['?'] * len(columns))
    column_names = ', '.join(columns)
    sql = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany(sql, records)
        conn.commit()


def fetch_all(db_path, sql, params=()):
    """
    Execute a SELECT statement and return all result rows along with column names.

    Args:
        db_path (str): Path to the SQLite database file.
        sql (str): SELECT statement to execute.
        params (tuple, optional): Parameters to bind to the SQL statement. Defaults to None.

    Returns:
        tuple: A tuple containing two elements:
            - columns (list): List of column names.
            - rows (list): List of tuples, where each tuple represents a result row.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        return columns, rows
