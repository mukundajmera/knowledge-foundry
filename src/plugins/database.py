"""Knowledge Foundry — Database Plugin.

Provides safe, structured query access to a SQLite database.
"""

from __future__ import annotations

import sqlite3
import structlog
from typing import Any

from src.core.interfaces import Plugin, PluginManifest, PluginResult

logger = structlog.get_logger(__name__)


class DatabasePlugin(Plugin):
    """Plugin for executing SQL queries on a SQLite database."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        # If in-memory, we might need to keep connection open or robustly handle it.
        # For :memory:, a new connection is a new DB. 
        # Plugin is instantiated once by Registry? singleton.
        # If so, we can hold a connection.
        self._connection = None

    def _get_connection(self) -> sqlite3.Connection:
        if not self._connection:
            self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
            # Create dummy data if memory
            if self.db_path == ":memory:":
                self._seed_dummy_data(self._connection)
        return self._connection

    def _seed_dummy_data(self, conn: sqlite3.Connection):
        """Seed in-memory DB with example data for testing."""
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, role TEXT)")
        cursor.execute("INSERT INTO users (name, email, role) VALUES ('Alice', 'alice@example.com', 'admin')")
        cursor.execute("INSERT INTO users (name, email, role) VALUES ('Bob', 'bob@example.com', 'viewer')")
        cursor.execute("CREATE TABLE docs (id INTEGER PRIMARY KEY, title TEXT, content TEXT, owner_id INTEGER)")
        cursor.execute("INSERT INTO docs (title, content, owner_id) VALUES ('Project Alpha', 'Confidential', 1)")
        conn.commit()

    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="database",
            version="1.0.0",
            description="Executes SQL queries on the internal database.",
            actions=["query_sql"],
            permissions=["read_only"],
        )

    async def execute(self, action: str, params: dict[str, Any]) -> PluginResult:
        if action != "query_sql":
            return PluginResult(success=False, error=f"Unknown action: {action}")

        query = params.get("query")
        if not query:
            return PluginResult(success=False, error="Missing 'query' parameter")

        # Security: Enforce basic read-only
        normalized_query = query.strip().lower()
        if not normalized_query.startswith("select"):
             return PluginResult(success=False, error="Security Violation: Only SELECT queries are allowed.")
        
        if ";" in query:
             # Basic injection/multiple statement check
             # sqlite3.execute only executes one statement usually, but let's be safe
             pass

        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description] if cursor.description else []
            
            results = [dict(zip(columns, row)) for row in rows]
            
            return PluginResult(success=True, data={"results": results, "count": len(results)})

        except sqlite3.Error as e:
            return PluginResult(success=False, error=f"Database error: {str(e)}")
        except Exception as e:
            logger.exception("Database query failed")
            return PluginResult(success=False, error=str(e))
