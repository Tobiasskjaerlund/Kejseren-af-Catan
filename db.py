
# db.py
import os
import streamlit as st
from sqlalchemy import create_engine, text

# Read URL from Streamlit secrets or environment
DATABASE_URL = (
    st.secrets.get("db", {}).get("url")
    or os.environ.get("DATABASE_URL")
)

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in Streamlit secrets or environment.")

# Create the engine (SQLAlchemy + psycopg2 driver)
# Example URL: postgresql+psycopg2://postgres.<PROJECT_REF>:PWD@...pooler.supabase.com:6543/postgres?sslmode=require
engine = create_engine(DATABASE_URL, pool_pre_ping=True)  # pool_pre_ping avoids stale connections
# SQLAlchemy URL format reference: dialect+driver://username:password@host:port/database
# (Here: postgresql+psycopg2)  [5](https://docs.sqlalchemy.org/en/14/core/engines.html)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS players (
  id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS games (
  id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  played_at TIMESTAMPTZ NOT NULL,
  winner_id INTEGER REFERENCES players(id)
);

CREATE TABLE IF NOT EXISTS scores (
  id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  player_id INTEGER NOT NULL REFERENCES players(id),
  points INTEGER NOT NULL
);
"""

def init_db():
    # Create tables and seed default players (Kristian, Johan)
    with engine.begin() as conn:
        conn.execute(text(SCHEMA_SQL))
        count = conn.execute(text("SELECT COUNT(*) FROM players")).scalar()
        if count == 0:
            conn.execute(text("INSERT INTO players(name) VALUES (:n1) ON CONFLICT DO NOTHING"), {"n1":"Kristian"})
            conn.execute(text("INSERT INTO players(name) VALUES (:n2) ON CONFLICT DO NOTHING"), {"n2":"Johan"})

def add_player(name: str):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO players(name) VALUES (:name) ON CONFLICT DO NOTHING"), {"name": name.strip()})

def list_players():
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, name FROM players ORDER BY name")).fetchall()
        return [(r[0], r[1]) for r in rows]

def add_game(played_at: str, player_points: dict):
    # player_points: {player_id: points}
    if not player_points:
        raise ValueError("player_points cannot be empty")
    # Determine winner_id (highest points)
    winner_id = max(player_points, key=lambda pid: player_points[pid])

    with engine.begin() as conn:
        game_id = conn.execute(
            text("INSERT INTO games(played_at, winner_id) VALUES (:ts, :wid) RETURNING id"),
            {"ts": played_at, "wid": winner_id}
        ).scalar()

        for pid, pts in player_points.items():
            conn.execute(
                text("INSERT INTO scores(game_id, player_id, points) VALUES (:gid, :pid, :pts)"),
                {"gid": game_id, "pid": int(pid), "pts": int(pts)}
            )
    return game_id, winner_id

def list_games():
    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT g.id, g.played_at, p.name AS winner
            FROM games g LEFT JOIN players p ON p.id = g.winner_id
            ORDER BY g.played_at DESC, g.id DESC
        """)).fetchall()
        return [(r[0], r[1].isoformat(), r[2]) for r in rows]

def get_leaderboard():
    with engine.begin() as conn:
        rows = conn.execute(text("""
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
        """)).fetchall()
        return [(r[0], r[1], int(r[2]), int(r[3]), int(r[4])) for r in rows]

def get_game_scores(game_id: int):
    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT p.name, s.points
            FROM scores s
            JOIN players p ON p.id = s.player_id
            WHERE s.game_id = :gid
            ORDER BY s.points DESC
        """), {"gid": game_id}).fetchall()
        return [(r[0], int(r[1])) for r in rows] or []

def get_all_scores():
    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT
              g.id AS game_id,
              g.played_at AS played_at,
              p.name AS player,
              s.points AS points
            FROM scores s
            JOIN games g ON g.id = s.game_id
            JOIN players p ON p.id = s.player_id
            ORDER BY g.played_at ASC, g.id ASC, s.points DESC
        """)).fetchall()
        # played_at is datetime; convert to iso
        return [(r[0], r[1].isoformat(), r[2], int(r[3])) for r in rows] or []

def get_games_with_winners():
    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT g.id AS game_id, g.played_at AS played_at, p.name AS winner
            FROM games g
            LEFT JOIN players p ON p.id = g.winner_id
            ORDER BY g.played_at ASC, g.id ASC
        """)).fetchall()
        return [(r[0], r[1].isoformat(), r[2]) for r in rows] or []
