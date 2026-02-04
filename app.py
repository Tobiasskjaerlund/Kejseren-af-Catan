import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime

from db import (
    init_db,
    add_player,
    list_players,
    add_game,
    list_games,
    get_leaderboard,
    get_game_scores,
    get_all_scores,
    get_games_with_winners,
    delete_game,
)

# --------------------------------------------------
# App config
# --------------------------------------------------
st.set_page_config(
    page_title="Kejser af Catan",
    page_icon="🎯",
    layout="centered"
)

# --------------------------------------------------
# Initialize DB once per session
# --------------------------------------------------
if "db_initialized" not in st.session_state:
    init_db()
    st.session_state.db_initialized = True

# --------------------------------------------------
# ✅ GLOBAL DATA (reloaded on every rerun)
# --------------------------------------------------
leaderboard_data = get_leaderboard()
all_scores = get_all_scores() or []
games_with_winners = get_games_with_winners() or []
games_list = list_games() or []

# Convert to DataFrames once
df_lb = pd.DataFrame(
    leaderboard_data,
    columns=["player_id", "player", "total_points", "wins", "games_played"]
)

scores_df = pd.DataFrame(
    all_scores,
    columns=["game_id", "played_at", "player", "points"]
)

games_df = pd.DataFrame(
    games_with_winners,
    columns=["game_id", "played_at", "winner"]
)

if not scores_df.empty:
    scores_df["played_at"] = pd.to_datetime(scores_df["played_at"])

if not games_df.empty:
    games_df["played_at"] = pd.to_datetime(games_df["played_at"])

# --------------------------------------------------
# UI
# --------------------------------------------------
st.title("👑 Kejseren af Catan")
tabs = st.tabs([
    "Rangliste",
    "Tilføj spiller",
    "Registrer spil",
    "Spilhistorik",
    "Eksportér",
])

# ==================================================
# TAB 0 — LEADERBOARD + STATS
# ==================================================
with tabs[0]:
    st.subheader("Rangliste")

    st.dataframe(
        df_lb.drop(columns=["player_id"]),
        use_container_width=True
    )

    st.markdown("### Spil statistik")

    if scores_df.empty and games_df.empty:
        st.info("Ingen spil endnu.")
        st.stop()

    # ---- Avg points per game
    if not scores_df.empty:
        games_per_player = (
            scores_df.groupby("player")["game_id"]
            .nunique()
            .rename("games_played")
            .reset_index()
        )

        total_points = (
            scores_df.groupby("player")["points"]
            .sum()
            .rename("total_points")
            .reset_index()
        )

        avg_df = games_per_player.merge(total_points, on="player")
        avg_df["avg_points_per_game"] = (
            avg_df["total_points"] / avg_df["games_played"]
        )

        bar_avg = (
            alt.Chart(avg_df)
            .mark_bar()
            .encode(
                x=alt.X("avg_points_per_game:Q", title="Gns. point pr. spil"),
                y=alt.Y("player:N", sort="-x", title="Spiller"),
                color=alt.Color("player:N", legend=None),
                tooltip=[
                    "player:N",
                    alt.Tooltip("avg_points_per_game:Q", format=".2f"),
                    "games_played:Q",
                    "total_points:Q",
                ],
            )
            .properties(
                height=alt.Step(28),
                title="Gennemsnitlige point pr. spil",
            )
        )

        st.altair_chart(bar_avg, use_container_width=True)

    # ---- Cumulative wins
    if not games_df.empty:
        wins_df = games_df.dropna(subset=["winner"]).copy()
        wins_df = wins_df.sort_values(["winner", "played_at", "game_id"])
        wins_df["win"] = 1
        wins_df["cum_wins"] = wins_df.groupby("winner")["win"].cumsum()

        line_wins = (
            alt.Chart(wins_df)
            .mark_line(point=True)
            .encode(
                x=alt.X("played_at:T", title="Dato"),
                y=alt.Y("cum_wins:Q", title="Samlede sejre"),
                color=alt.Color("winner:N", title="Spiller"),
                tooltip=["winner:N", "played_at:T", "cum_wins:Q"],
            )
            .properties(height=300, title="Sejre over tid")
        )

        st.altair_chart(line_wins, use_container_width=True)

# ==================================================
# TAB 1 — ADD PLAYER
# ==================================================
with tabs[1]:
    st.subheader("Tilføj spiller")

    new_player = st.text_input("Navn")

    if st.button("Tilføj", type="primary"):
        if new_player.strip():
            add_player(new_player.strip())
            st.success(f"Spiller tilføjet: {new_player}")
            st.rerun()

    st.table(pd.DataFrame(list_players(), columns=["id", "name"]))

# ==================================================
# TAB 2 — ADD GAME
# ==================================================
with tabs[2]:
    st.subheader("Registrer spil")

    players = list()
    if not players:
        st.info("Tilføj spillere først.")
        st.stop()

    names = [p[1] for p in players]
    ids = {p[1]: p[0] for p in players}

    selected = st.multiselect("Spillere", names, default=names)
    points = {}

    cols = st.columns(len(selected) or 1)
    for i, name in enumerate(selected):
        with cols[i % len(cols)]:
            points[ids[name]] = st.number_input(name, min_value=0, step=1)

    date = st.date_input("Dato", value=datetime.now().date())
    time = st.time_input("Tid", value=datetime.now().time())

    if st.button("Gem spil", type="primary"):
        ts = datetime.combine(date, time).isoformat(timespec="seconds")
        add_game(ts, points)
        st.success("Spil gemt")
        st.rerun()

# ==================================================
# TAB 3 — GAME HISTORY / DELETE
# ==================================================
with tabs[3]:
    st.subheader("Spilhistorik")

    df_games = pd.DataFrame(
        games_list,
        columns=["game_id", "played_at", "winner"]
    )

    st.dataframe(df_games, use_container_width=True)

    if games_list:
        gid = st.selectbox(
            "Vælg spil",
            options=[g[0] for g in games_list],
            format_func=lambda x: f"#{x}",
        )

        st.table(
            pd.DataFrame(
                get_game_scores(gid),
                columns=["Spiller", "Point"],
            )
        )

        st.warning("Dette sletter spillet permanent.")

        if st.checkbox("Jeg er sikker") and st.button("Slet spil", type="primary"):
            delete_game(gid)
            st.success("Spil slettet")
            st.rerun()

# ==================================================
# TAB 4 — EXPORT
# ==================================================
with tabs[4]:
    st.subheader("Eksport")

    export_rows = []
    for gid, played_at, winner in games_list:
        for player, points in get_game_scores(gid):
            export_rows.append({
                "game_id": gid,
                "played_at": played_at,
                "winner": winner,
                "player": player,
                "points": points,
            })

    export_df = pd.DataFrame(export_rows)

    st.download_button(
        "Download CSV",
        data=export_df.to_csv(index=False),
        file_name="catan_games.csv",
        mime="text/csv",
    )

    st.dataframe(export_df, use_container_width=True)

