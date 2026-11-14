"""Counters for the dashboard."""
import sqlite3


def open_count(conn: sqlite3.Connection, team_id: str) -> int:
    """Open tickets of a team; the id is cast to int before it reaches SQL."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open' AND team_id = %d" % int(team_id))
    return cursor.fetchone()[0]
