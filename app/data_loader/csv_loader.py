import pandas as pd

from app.schema_manager.manager import (
    infer_schema_from_dataframe,
    get_table_schema,
    compare_schemas,
    generate_create_table_sql
)
from app.db.database import execute_non_query, insert_rows, fetch_all
from app.utils.logger import log_error


def _next_available_table_name(db_path, base_name):
    """
    Find the next unused versioned table name.

    If 'users' exists, tries 'users_1', 'users_2', etc.

    Args:
        db_path (str): Path to the SQLite database.
        base_name (str): Original table name.

    Returns:
        str: A table name not yet in use.
    """
    _, rows = fetch_all(db_path, "SELECT name FROM sqlite_master WHERE type='table'")
    existing = {row[0] for row in rows}
    counter = 1
    while True:
        candidate = f"{base_name}_{counter}"
        if candidate not in existing:
            return candidate
        counter += 1


def load_csv(file_path):
    """
    Load a CSV file into a pandas DataFrame.

    Args:
        file_path (str): Path to the CSV file.

    Returns:
        pandas.DataFrame: Loaded CSV data.

    Raises:
        Exception: If the file cannot be read.
    """
    df = pd.read_csv(file_path)
    return df


def get_columns_and_rows(df):
    """
    Extract column names and row data from a DataFrame.

    Args:
        df (pandas.DataFrame): The loaded CSV data.

    Returns:
        tuple: (columns, rows)
            columns -> list of column names
            rows -> list of tuples containing row values
    """
    columns = list(df.columns)
    rows = [tuple(row) for row in df.itertuples(index=False, name=None)]
    return columns, rows


def ingest_csv(file_path, table_name, db_path):
    """
    Main CSV ingestion function.

    Steps:
    1. Load the CSV file
    2. Infer schema from the DataFrame
    3. Check whether the table already exists
    4. If it does not exist, create it
    5. If it exists, compare schemas
    6. If schemas match, append rows
    7. If schemas do not match, create a new versioned table (e.g. users_1)
    8. Insert rows into the database

    Args:
        file_path (str): Path to CSV file
        table_name (str): Name of table to create/append to
        db_path (str): Path to SQLite database

    Returns:
        dict: Result message and status
    """
    try:
        # Step 1: Load the CSV
        df = load_csv(file_path)

       #Check if file is empty
        if df.empty:
            return {
                "success": False,
                "message": "CSV file is empty."
            }

        # Step 2: Determine column structure from the CSV
        new_schema = infer_schema_from_dataframe(df)

        # Step 3: Check if table exists by trying to get its schema
        existing_schema = get_table_schema(db_path, table_name)

        # Step 4: Create table if it does not exist
        if not existing_schema:
            create_table_sql = generate_create_table_sql(table_name, new_schema)
            execute_non_query(db_path, create_table_sql)

        # Step 5: Compare schemas if table already exists
        else:
            schemas_match = compare_schemas(existing_schema, new_schema)
            if not schemas_match:
                # Schema differs — create a new versioned table instead of appending
                table_name = _next_available_table_name(db_path, table_name)
                create_table_sql = generate_create_table_sql(table_name, new_schema)
                execute_non_query(db_path, create_table_sql)

        # Step 6: Prepare and insert rows
        columns, rows = get_columns_and_rows(df)
        insert_rows(db_path, table_name, columns, rows)

        return {
            "success": True,
            "message": f"Loaded {len(rows)} rows into table '{table_name}'."
        }

    except Exception as e:
        log_error(str(e))
        return {
            "success": False,
            "message": f"Error loading CSV: {str(e)}"
        }