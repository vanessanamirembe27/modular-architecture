import sqlite3


# --------------------------------------------------------------------------- #
# Type inference
# --------------------------------------------------------------------------- #

def _infer_sqlite_type(series):
    """
    Map a pandas Series dtype to a SQLite type string.

    Args:
        series (pandas.Series)

    Returns:
        str: One of "INTEGER", "REAL", or "TEXT"
    """
    dtype = str(series.dtype)
    if dtype.startswith("int"):
        return "INTEGER"
    if dtype.startswith("float"):
        return "REAL"
    return "TEXT"


def infer_schema_from_dataframe(df):
    """
    Derive a schema dict from a DataFrame.

    Args:
        df (pandas.DataFrame)

    Returns:
        dict: {normalized_column_name: sqlite_type}
              e.g. {"name": "TEXT", "age": "INTEGER"}
    """
    return {
        _normalize_column(col): _infer_sqlite_type(df[col])
        for col in df.columns
    }


# --------------------------------------------------------------------------- #
# Column normalization
# --------------------------------------------------------------------------- #

def _normalize_column(name):
    """
    Normalize a column name for comparison:
    - lowercase
    - strip leading/trailing whitespace
    - replace internal spaces with underscores

    Args:
        name (str)

    Returns:
        str
    """
    return name.strip().lower().replace(" ", "_")


def normalize_schema(schema):
    """
    Return a copy of a schema dict with all keys normalized.

    Args:
        schema (dict): {column_name: sqlite_type}

    Returns:
        dict: {normalized_column_name: sqlite_type}
    """
    return {_normalize_column(k): v for k, v in schema.items()}


# --------------------------------------------------------------------------- #
# Existing table schema
# --------------------------------------------------------------------------- #

def get_table_schema(db_path, table_name):
    """
    Read the schema of an existing table from SQLite.

    Args:
        db_path (str): Path to the SQLite database.
        table_name (str): Table to inspect.

    Returns:
        dict: {normalized_column_name: sqlite_type}, or {} if table does not exist.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.Error:
        return {}

    if not rows:
        return {}

    # PRAGMA table_info columns: (cid, name, type, notnull, dflt_value, pk)
    return {_normalize_column(row[1]): row[2].upper() for row in rows}


# --------------------------------------------------------------------------- #
# Schema comparison
# --------------------------------------------------------------------------- #

def compare_schemas(existing_schema, new_schema):
    """
    Check whether two schemas are compatible for appending data.

    Both schemas are normalized before comparison.
    Column names AND data types must match exactly.

    Args:
        existing_schema (dict): Schema already in the database.
        new_schema (dict): Schema inferred from the incoming CSV.

    Returns:
        bool: True if schemas match, False otherwise.
    """
    return normalize_schema(existing_schema) == normalize_schema(new_schema)


# --------------------------------------------------------------------------- #
# DDL generation
# --------------------------------------------------------------------------- #

def generate_create_table_sql(table_name, schema):
    """
    Build a CREATE TABLE IF NOT EXISTS statement from a schema dict.

    Always prepends an auto-incrementing surrogate primary key column:
        id INTEGER PRIMARY KEY AUTOINCREMENT

    Args:
        table_name (str): Name of the table to create.
        schema (dict): {column_name: sqlite_type}

    Returns:
        str: SQL DDL statement.
    """
    col_defs = ["id INTEGER PRIMARY KEY AUTOINCREMENT"] + [
        f"{_normalize_column(col)} {dtype}"
        for col, dtype in schema.items()
    ]
    return f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(col_defs)})"
