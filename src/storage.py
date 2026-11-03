"""
Database access layer based on SQLite relational database.

Executes all database operations using pure SQL string queries as required
by Stage 3 of Variant 18.
"""

import sqlite3
import threading
import time
from typing import Any
from src.constants import (
    DEFAULT_CACHE_HIT,
    DEFAULT_DURATION,
    REPORT_WINDOW_MINUTES,
    SECONDS_IN_MINUTE,
    ZERO_VAL,
)

SQL_CREATE_MEMBER = """
CREATE TABLE IF NOT EXISTS Member (
    id INTEGER PRIMARY KEY,
    created INTEGER NOT NULL,
    ip TEXT NOT NULL,
    user_agent TEXT NOT NULL
)
"""

SQL_CREATE_INSTRUCTION = """
CREATE TABLE IF NOT EXISTS Instruction (
    id INTEGER PRIMARY KEY,
    created INTEGER NOT NULL,
    argument TEXT NOT NULL,
    member INTEGER NOT NULL,
    description TEXT NOT NULL,
    state TEXT NOT NULL,
    FOREIGN KEY (member) REFERENCES Member(id)
)
"""

SQL_CREATE_RESPONSE = """
CREATE TABLE IF NOT EXISTS Response (
    id INTEGER PRIMARY KEY,
    created INTEGER NOT NULL,
    response TEXT NOT NULL,
    state TEXT NOT NULL,
    error TEXT NOT NULL,
    instruction INTEGER NOT NULL,
    cache_hit INTEGER NOT NULL,
    duration INTEGER NOT NULL,
    FOREIGN KEY (instruction) REFERENCES Instruction(id)
)
"""

SQL_INSERT_MEMBER = """
INSERT INTO Member (id, created, ip, user_agent)
VALUES (?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    ip = excluded.ip,
    user_agent = excluded.user_agent
"""

SQL_INSERT_INSTRUCTION = """
INSERT INTO Instruction
(id, created, argument, member, description, state)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    argument = excluded.argument,
    member = excluded.member,
    description = excluded.description,
    state = excluded.state
"""

SQL_INSERT_RESPONSE = """
INSERT INTO Response
(id, created, response, state, error, instruction, cache_hit, duration)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    response = excluded.response,
    state = excluded.state,
    error = excluded.error,
    cache_hit = excluded.cache_hit,
    duration = excluded.duration
"""

SQL_REPORT = """
SELECT
    Instruction.description AS description,
    Response.cache_hit AS cache_hit,
    Response.response AS response
FROM (
    SELECT id, description
    FROM Instruction
    WHERE created >= ?
) AS Instruction
RIGHT JOIN Response ON Instruction.id = Response.instruction
"""


class SqliteStorage:
    """
    Relational SQLite storage manager for Member, Instruction and Response.

    Uses thread-safe SQLite connection and pure SQL queries.
    """

    def __init__(self, db_path: str = ":memory:"):
        """Initialize database connection and tables."""
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self) -> None:
        """Create necessary database tables if they do not exist."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("PRAGMA foreign_keys = ON")
            cur.execute(SQL_CREATE_MEMBER)
            cur.execute(SQL_CREATE_INSTRUCTION)
            cur.execute(SQL_CREATE_RESPONSE)
            self._conn.commit()

    def clear(self) -> None:
        """Remove all rows from all tables."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM Response")
            cur.execute("DELETE FROM Instruction")
            cur.execute("DELETE FROM Member")
            self._conn.commit()

    def store_member(
        self,
        uid: int,
        ip: str,
        user_agent: str,
        created: int | None = None,
    ) -> dict[str, Any]:
        """Insert or replace a member entity."""
        created_val = created if created is not None else int(time.time())
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(SQL_INSERT_MEMBER, (uid, created_val, ip, user_agent))
            self._conn.commit()
        return self.get_member(uid)

    def get_member(self, uid: int) -> dict[str, Any]:
        """Fetch single member by primary key identifier."""
        query = "SELECT id, created, ip, user_agent FROM Member WHERE id = ?"
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(query, (uid,))
            row = cur.fetchone()
        return dict(row) if row is not None else {}

    def show_members(self) -> list[dict[str, Any]]:
        """Retrieve all member entities."""
        query = (
            "SELECT id, created, ip, user_agent FROM Member ORDER BY id ASC"
        )
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(query)
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def find_members(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Search members by given filter key-value pairs."""
        allowed = ("id", "ip", "user_agent")
        clauses: list[str] = []
        vals: list[Any] = []
        for key, val in filters.items():
            if key in allowed:
                clauses.append(f"{key} = ?")
                vals.append(val)
        where_str = " AND ".join(clauses) if clauses else "1=1"
        query = (
            f"SELECT id, created, ip, user_agent "
            f"FROM Member WHERE {where_str}"
        )
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(query, vals)
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def correct_member(self, uid: int, data: dict[str, Any]) -> dict[str, Any]:
        """Update existing member fields."""
        old = self.get_member(uid)
        if not old:
            return {}
        new_ip = data.get("ip", old["ip"])
        new_ua = data.get("user_agent", old["user_agent"])
        query = "UPDATE Member SET ip = ?, user_agent = ? WHERE id = ?"
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(query, (new_ip, new_ua, uid))
            self._conn.commit()
        return self.get_member(uid)

    def store_instruction(
        self,
        iid: int,
        argument: str,
        member: int,
        description: str,
        state: str,
        created: int | None = None,
    ) -> dict[str, Any]:
        """Insert or replace an instruction entity."""
        created_val = created if created is not None else int(time.time())
        params = (iid, created_val, argument, member, description, state)
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(SQL_INSERT_INSTRUCTION, params)
            self._conn.commit()
        return self.get_instruction(iid)

    def get_instruction(self, iid: int) -> dict[str, Any]:
        """Fetch single instruction by primary key."""
        query = """
            SELECT id, created, argument, member, description, state
            FROM Instruction WHERE id = ?
        """
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(query, (iid,))
            row = cur.fetchone()
        return dict(row) if row is not None else {}

    def show_instructions_by_member(
        self, member_id: int
    ) -> list[dict[str, Any]]:
        """Fetch all instructions belonging to a specific member."""
        query = """
            SELECT id, created, argument, member, description, state
            FROM Instruction WHERE member = ? ORDER BY id ASC
        """
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(query, (member_id,))
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def find_instructions(
        self, filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Search instructions by arbitrary allowed parameters."""
        allowed = ("id", "argument", "member", "description", "state")
        clauses: list[str] = []
        vals: list[Any] = []
        for key, val in filters.items():
            if key in allowed:
                clauses.append(f"{key} = ?")
                vals.append(val)
        where_str = " AND ".join(clauses) if clauses else "1=1"
        query = f"""
            SELECT id, created, argument, member, description, state
            FROM Instruction WHERE {where_str}
        """
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(query, vals)
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def correct_instruction(
        self, iid: int, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update fields of an existing instruction."""
        old = self.get_instruction(iid)
        if not old:
            return {}
        new_arg = data.get("argument", old["argument"])
        new_desc = data.get("description", old["description"])
        new_state = data.get("state", old["state"])
        query = """
            UPDATE Instruction
            SET argument = ?, description = ?, state = ?
            WHERE id = ?
        """
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(query, (new_arg, new_desc, new_state, iid))
            self._conn.commit()
        return self.get_instruction(iid)

    def store_response(
        self,
        rid: int,
        data: dict[str, Any],
        created: int | None = None,
    ) -> dict[str, Any]:
        """Insert or replace a response record."""
        created_val = created if created is not None else int(time.time())
        params = (
            rid,
            created_val,
            data.get("response", ""),
            data.get("state", "COMPLETED"),
            data.get("error", ""),
            data.get("instruction", ZERO_VAL),
            data.get("cache_hit", DEFAULT_CACHE_HIT),
            data.get("duration", DEFAULT_DURATION),
        )
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(SQL_INSERT_RESPONSE, params)
            self._conn.commit()
        return self.get_response(rid)

    def get_response(self, rid: int) -> dict[str, Any]:
        """Fetch single response by primary key."""
        query = """
            SELECT id, created, response, state, error, instruction,
                   cache_hit, duration
            FROM Response WHERE id = ?
        """
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(query, (rid,))
            row = cur.fetchone()
        return dict(row) if row is not None else {}

    def show_responses_by_instruction(
        self, instruction_id: int
    ) -> list[dict[str, Any]]:
        """Fetch all responses belonging to an instruction."""
        query = """
            SELECT id, created, response, state, error, instruction,
                   cache_hit, duration
            FROM Response WHERE instruction = ? ORDER BY id ASC
        """
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(query, (instruction_id,))
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def find_responses(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Search responses by filtering parameters."""
        allowed = (
            "id",
            "response",
            "state",
            "error",
            "instruction",
            "cache_hit",
            "duration",
        )
        clauses: list[str] = []
        vals: list[Any] = []
        for key, val in filters.items():
            if key in allowed:
                clauses.append(f"{key} = ?")
                vals.append(val)
        where_str = " AND ".join(clauses) if clauses else "1=1"
        query = f"""
            SELECT id, created, response, state, error, instruction,
                   cache_hit, duration
            FROM Response WHERE {where_str}
        """
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(query, vals)
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_next_response_id(self) -> int:
        """Calculate next available primary key for response."""
        query = "SELECT COALESCE(MAX(id), 0) FROM Response"
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(query)
            max_id = cur.fetchone()[ZERO_VAL]
        return max_id + 1

    def get_report(self, now_ts: int | None = None) -> list[dict[str, Any]]:
        """
        Generate report based on Formula 18: Right Outer Join between
        Instruction (filtered by created >= now - 9 minutes) and Response.
        """
        current_time = now_ts if now_ts is not None else int(time.time())
        offset = current_time - REPORT_WINDOW_MINUTES * SECONDS_IN_MINUTE
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(SQL_REPORT, (offset,))
            rows = cur.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "description": row["description"],
                    "cache_hit": row["cache_hit"],
                    "response": row["response"],
                }
            )
        return result

    get_report_formula18 = get_report
