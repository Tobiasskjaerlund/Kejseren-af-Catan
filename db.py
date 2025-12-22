
# db.py
import sqlite3
from contextlib import closing
from pathlib import Path

# Keep DB next to this file to avoid CWD/OneDrive confusion
APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "scores.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    played_at TEXT NOT NULL,
    winner_id INTEGER,
    FOREIGN KEY (winner_id) REFERENCES players(id)
);

CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    points INTEGER NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games(id),
    FOREIGN KEY (player_id) REFERENCES players(id)
);

"""

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _tables_exist(conn):
    q = "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('players','games','scores')"
    rows = conn.execute(q).fetchall()
    return {r[0] for r in rows}

def init_db():
    """Create tables and seed default players if empty."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(get_conn()) as conn:
        conn.executescript(SCHEMA_SQL)
        # Defensive: ensure tables exist
        if {"players", "games", "scores"} - _tables_exist(conn):
            conn.executescript(SCHEMA_SQL)

        # Seed Kristian & Johan once
        count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        if count == 0:
            conn.execute("INSERT OR IGNORE INTO players(name) VALUES (?)", ("Kristian",))
            conn.execute("INSERT OR IGNORE INTO players(name) VALUES (?)", ("Johan",))
        conn.commit()

def add_player(name: str):
    with closing(get_conn()) as conn:
        conn.execute("INSERT OR IGNORE INTO players(name) VALUES (?)", (name.strip(),))
        conn.commit()

def list_players():
    with closing(get_conn()) as conn:
        return conn.execute("SELECT id, name FROM players ORDER BY name").fetchall()

def add_game(played_at: str, player_points: dict):
    """
    player_points: {player_id: points}
    """
    if not player_points:
        raise ValueError("player_points cannot be empty")

    winner_id = max(player_points, key=lambda pid: player_points[pid])

    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO games(played_at, winner_id) VALUES (?, ?)", (played_at, winner_id))
        game_id = cur.lastrowid

        for pid, pts in player_points.items():
            cur.execute(
                "INSERT INTO scores(game_id, player_id, points) VALUES (?, ?, ?)",
                (game_id, int(pid), int(pts))  # order: game_id, player_id, points
            )
        conn.commit()
    return game_id, winner_id

def list_games():
    with closing(get_conn()) as conn:
        sql = """
        SELECT g.id, g.played_at, p.name AS winner
        FROM games g LEFT JOIN players p ON p.id = g.winner_id
        ORDER BY g.played_at DESC, g.id DESC
        """
        return conn.execute(sql).fetchall()

def get_leaderboard():
    with closing(get_conn()) as conn:
        sql = """
        SELECT
          p.id,
          p.name,
          COALESCE(SUM(s.points), 0) AS total_points,
          COALESCE(SUM(CASE WHEN g.winner_id = p.id THEN 1 ELSE 0 END), 0) AS wins,
          COALESCE(COUNT(DISTINCT s.game_id), 0) AS games_played
        FROM players p
        LEFT JOIN scores s ON s.player_id = p.id
        LEFT JOIN games g ON g.id = s.game_id
        GROUP BY p.id, p.name
        ORDER BY total_points DESC, wins DESC, p.name ASC
        """
        return conn.execute(sql).fetchall()


# db.py
def get_game_scores(game_id: int):
    from contextlib import closing
    with closing(get_conn()) as conn:
        try:
            sql = """
            SELECT p.name, s.points
            FROM scores s
            JOIN players p ON p.id = s.player_id
            WHERE s.game_id = ?
            ORDER BY s.points DESC
            """
            rows = conn.execute(sql, (game_id,)).fetchall()
            # Always return a list (not None)
            return rows or []
        except Exception:
            # If anything goes wrong, return empty list so callers don't crash
            return []


def get_all_scores():
    """
    Returns rows with the schema:
    (game_id, played_at, player, points)
    """
    from contextlib import closing
    with closing(get_conn()) as conn:
        sql = """
        SELECT
          g.id AS game_id,
          g.played_at AS played_at,
          p.name AS player,
          s.points AS points
        FROM scores s
        JOIN games g ON g.id = s.game_id
        JOIN players p ON p.id = s.player_id
        ORDER BY g.played_at ASC, g.id ASC, s.points DESC
        """
        rows = conn.execute(sql).fetchall()
        return rows or []



def get_games_with_winners():
    """
    Returns rows with:
    (game_id, played_at, winner_name)
    """
    from contextlib import closing
    with closing(get_conn()) as conn:
        sql = """
        SELECT
          g.id AS game_id,
          g.played_at AS played_at,
          p.name AS winner
        FROM games g
        LEFT JOIN players p ON p.id = g.winner_id
        ORDER BY g.played_at ASC, g.id ASC
        """
        rows = conn.execute(sql).fetchall()
        return rows or []

