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


def _build_schema_description(schema_map):
    """
    Convert a {table_name: {col: type}} dict into a readable string
    for the model prompt.

    Args:
        schema_map (dict): {table_name: {column_name: sqlite_type}}

    Returns:
        str
    """
    lines = []
    for table, columns in schema_map.items():
        col_list = ", ".join(f"{col} ({dtype})" for col, dtype in columns.items())
        lines.append(f"  Table '{table}': {col_list}")
    return "\n".join(lines)


def generate_sql(question, schema_map):
    """
    Ask Claude to produce a SQL SELECT query for the given question.

    Args:
        question (str): Natural language question from the user.
        schema_map (dict): {table_name: {column_name: sqlite_type}}
                           Describes the available tables and columns.

    Returns:
        str: A SQL SELECT statement (not yet validated or executed).

    Raises:
        ValueError: If the model response cannot be parsed into SQL.
        anthropic.APIError: On API communication failures.
    """
    schema_description = _build_schema_description(schema_map)

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

    sql = message.content[0].text.strip()

    # Strip accidental markdown code fences the model might still produce
    if sql.startswith("```"):
        lines = sql.splitlines()
        sql = "\n".join(
            line for line in lines
            if not line.startswith("```")
        ).strip()

    if not sql.upper().startswith("SELECT"):
        raise ValueError(
            f"LLM returned an unexpected response (not a SELECT): {sql!r}"
        )

    return sql
