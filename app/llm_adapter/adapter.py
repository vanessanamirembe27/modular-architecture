"""
LLM Adapter
===========
Converts a natural language question into a SQL SELECT statement
using the Anthropic Claude API.

Constraints
-----------
- This module NEVER executes SQL.
- It NEVER connects to the database directly.
- It receives schema information as a plain dict and passes it to
  the model as context.
- The returned SQL string must be validated by sql_validator before use.

Usage
-----
    from app.llm_adapter.adapter import generate_sql
    from app.schema_manager.manager import get_table_schema

    schema = get_table_schema(db_path, "users")
    sql = generate_sql("How many users are older than 30?", {"users": schema})
"""

import anthropic

_CLIENT = None


def _get_client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = anthropic.Anthropic()
    return _CLIENT


def _format_schema_description(schema_map):
    """
    Convert a schema map into a human-readable string for the model prompt.

    Args:
        schema_map (dict): A dictionary mapping table names to column schemas.
                           Example: {table_name: {column_name: sqlite_type}}

    Returns:
        str: A formatted string describing the database schema.
    """
    schema_lines = []
    for table_name, column_schemas in schema_map.items():
        column_descriptions = [
            f"{col_name} ({col_type})" for col_name, col_type in column_schemas.items()
        ]
        schema_lines.append(f"  Table '{table_name}': {', '.join(column_descriptions)}")
    return "\n".join(schema_lines)

def generate_sql_query(question, schema_map):
    """
    Generate a SQL SELECT query based on a natural language question and database schema.

    Args:
        question (str): The natural language question to answer.
        schema_map (dict): A dictionary mapping table names to column schemas.
                           Example: {table_name: {column_name: sqlite_type}}

    Returns:
        str: The generated SQL SELECT query.

    Raises:
        ValueError: If the model response cannot be parsed into a valid SQL query.
        anthropic.APIError: If there is an error communicating with the Anthropic API.
    """
    
    schema_description = _format_schema_description(schema_map)

    prompt = f"""You are a SQL generation assistant. Given a database schema and a
natural language question, return ONLY a valid SQLite SELECT statement.

Rules:
- Return only the SQL query — no explanation, no markdown, no code fences.
- Only use tables and columns that appear in the schema below.
- Do not use INSERT, UPDATE, DELETE, DROP, or any other write operation.
- Do not include comments (-- or /* */) in the output.
- Do not include semicolons.

Database schema:
{schema_description}

Question: {question}

SQL:"""

    client = _get_client()
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    sql_query = response.content[0].text.strip()

    # Remove any accidental markdown code fences from the model response
    if sql_query.startswith("```"):
        sql_query = "\n".join(
            line for line in sql_query.splitlines() if not line.startswith("```")
        ).strip()

    if not sql_query.upper().startswith("SELECT"):
        raise ValueError(f"LLM returned an unexpected response (not a SELECT): {sql_query!r}")

    return sql_query
