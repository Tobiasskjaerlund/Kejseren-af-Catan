
# app.py

import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
from datetime import datetime


from db import (
    init_db, add_player, list_players, add_game, list_games,
    get_leaderboard, get_game_scores, get_all_scores, get_games_with_winners
)


st.set_page_config(page_title="Kejser af Catan", page_icon="🎯", layout="centered")

# ✅ Initialize DB exactly once per session
if "db_initialized" not in st.session_state:
    init_db()
    st.session_state["db_initialized"] = True

st.title("👑 Kejseren af Catan")
tabs = st.tabs(["Rangliste","Tilføj spiller", "Registrer spil", "Spilhistorik", "Eksportér"])


# --- Leaderboard (FIRST TAB) ---
with tabs[0]:
    st.subheader("Rangliste:")

    # Core table (still useful, but you can remove if you only want visuals)
    lb = get_leaderboard()
    df_lb = pd.DataFrame(lb, columns=["player_id", "player", "total_points", "wins", "games_played"])
    st.dataframe(df_lb.drop(columns=["player_id"]), use_container_width=True)

    st.markdown("### Spil statistik:")

    # Fetch data needed for visuals
    score_rows = get_all_scores() or []
    game_rows = get_games_with_winners() or []

    scores_df = pd.DataFrame(score_rows, columns=["game_id", "played_at", "player", "points"])
    games_df = pd.DataFrame(game_rows, columns=["game_id", "played_at", "winner"])

    if scores_df.empty and games_df.empty:
        st.info("No games yet — add a game in the **New Game** tab to see charts here.")
    else:
        # Parse datetime for both frames where available
        if not scores_df.empty:
            scores_df["played_at"] = pd.to_datetime(scores_df["played_at"])
        if not games_df.empty:
            games_df["played_at"] = pd.to_datetime(games_df["played_at"])

        # ---- 1) Average number of points per game (per player)
        if not scores_df.empty:
            # Average points per game per player: total points / number of games they appeared in
            games_per_player = scores_df.groupby("player")["game_id"].nunique().rename("games_played").reset_index()
            total_points_per_player = scores_df.groupby("player")["points"].sum().rename("total_points").reset_index()
            avg_df = games_per_player.merge(total_points_per_player, on="player")
            # Avoid division by zero
            avg_df["avg_points_per_game"] = avg_df.apply(
                lambda r: (r["total_points"] / r["games_played"]) if r["games_played"] else 0, axis=1
            )
            avg_df = avg_df.sort_values("avg_points_per_game", ascending=False)

            import altair as alt
            bar_avg = alt.Chart(avg_df).mark_bar().encode(
                x=alt.X("avg_points_per_game:Q", title="Average points per game"),
                y=alt.Y("player:N", sort="-x", title="Player"),
                color=alt.Color("player:N", legend=None),
                tooltip=[
                    alt.Tooltip("player:N", title="Player"),
                    alt.Tooltip("avg_points_per_game:Q", title="Avg points/game", format=".2f"),
                    alt.Tooltip("games_played:Q", title="Games played"),
                    alt.Tooltip("total_points:Q", title="Total points"),
                ],
            ).properties(
                height=max(180, 22 * len(avg_df)),
                title="Gennemsnitligt antal point pr. spil"
            )
            st.altair_chart(bar_avg, use_container_width=True)
        else:
            st.info("No score data yet to compute average points per game.")

        # ---- 2) Cumulative wins over time (per player)
        if not games_df.empty:
            # Drop games without a winner (just in case)
            wins_df = games_df.dropna(subset=["winner"]).copy()
            wins_df = wins_df.sort_values(["winner", "played_at", "game_id"])
            # Each game counts as +1 win for its winner
            wins_df["win"] = 1
            wins_df["cum_wins"] = wins_df.groupby("winner")["win"].cumsum()

            line_wins = alt.Chart(wins_df).mark_line(point=True).encode(
                x=alt.X("played_at:T", title="Date"),
                y=alt.Y("cum_wins:Q", title="Cumulative wins"),
                color=alt.Color("winner:N", title="Player"),
                tooltip=[
                    alt.Tooltip("winner:N", title="Player"),
                    alt.Tooltip("played_at:T", title="Date"),
                    alt.Tooltip("cum_wins:Q", title="Cumulative wins")
                ],
            ).properties(
                height=300,
                title="Antal sejre over tid:"
            )
            st.altair_chart(line_wins, use_container_width=True)
        else:
            st.info("No games recorded yet to compute cumulative wins.")

        # ---- 3) Pie chart: number of wins per player
        if not games_df.empty:
            wins_per_player = games_df.dropna(subset=["winner"]).groupby("winner").size().reset_index(name="wins")
            if wins_per_player["wins"].sum() == 0:
                st.info("No wins recorded yet.")
            else:
                pie = alt.Chart(wins_per_player).mark_arc(innerRadius=60).encode(
                    theta=alt.Theta("wins:Q", title="Wins"),
                    color=alt.Color("winner:N", title="Player"),
                    tooltip=[alt.Tooltip("winner:N", title="Player"), alt.Tooltip("wins:Q", title="Wins")]
                ).properties(
                    height=300,
                    title="Sejre pr. spiller"
                )
                st.altair_chart(pie, use_container_width=True)
        else:
            st.info("No games recorded yet to show wins per player.")

        # ---- 4) Max games played in one day
        if not games_df.empty:
            # Count games per calendar day
            games_df["date"] = games_df["played_at"].dt.date
            games_per_day = games_df.groupby("date").size().reset_index(name="games")
            max_row = games_per_day.loc[games_per_day["games"].idxmax()]
            max_date = max_row["date"]
            max_games = int(max_row["games"])

            c1, c2 = st.columns(2)
            with c1:
                st.metric(label="Maks antal spil på én dag", value=max_games)
            with c2:
                st.metric(label="Date", value=str(max_date))
            # Optional: show distribution bar chart
            import altair as alt
            bar_games = alt.Chart(games_per_day).mark_bar().encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("games:Q", title="Games"),
                tooltip=["date:T", "games:Q"]
            ).properties(height=200, title="Spil tidslinje")
            st.altair_chart(bar_games, use_container_width=True)
        else:
            st.info("No games recorded yet to compute max games per day.")



# --- Add Players ---
with tabs[1]:
    st.subheader("Add Players")

    new_player = st.text_input("Player name", key="new_player_name")

    if st.button("Add player", type="primary"):
        if not st.session_state.get("db_initialized"):
            init_db()
            st.session_state["db_initialized"] = True
        name = (new_player or "").strip()
        if name:
            try:
                add_player(name)
                st.success(f"Added player: {name}")
            except Exception as e:
                st.error(f"Could not add player (DB not initialized?). {e}")

    players = list_players()
    st.write("Current players:")
    st.table(pd.DataFrame(players, columns=["id", "name"]))

# --- New Game ---
with tabs[2]:
    st.subheader("Record a New Game")
    players = list_players()
    if not players:
        st.info("Add players first in the 'Add Players' tab.")
    else:
        names = [p[1] for p in players]
        ids_by_name = {p[1]: p[0] for p in players}

        selected_names = st.multiselect("Players in this game", names, default=names)
        selected_ids = [ids_by_name[n] for n in selected_names]

        st.write("Enter points for each player:")
        points = {}
        cols = st.columns(min(4, len(selected_ids)) or 1)
        for i, pid in enumerate(selected_ids):
            col = cols[i % len(cols)]
            with col:
                pname = next(n for (i2, n) in players if i2 == pid)
                points[pid] = st.number_input(f"{pname}", min_value=0, step=1, value=0)

        played_at = st.date_input("Date", value=datetime.now().date())
        time_str = st.time_input("Time", value=datetime.now().time())

        if st.button("Save game", type="primary"):
            from datetime import datetime as dt
            played_ts = dt.combine(played_at, time_str).isoformat(timespec="seconds")
            try:
                game_id, winner_id = add_game(played_ts, points)
                winner_name = next(n for (i2, n) in players if i2 == winner_id)
                st.success(f"Saved game #{game_id}. Winner: {winner_name}")
            except sqlite3.OperationalError as e:
                st.error(f"Database not initialized. Please reload the app. Details: {e}")
            except Exception as e:
                st.error(f"Could not save game: {e}")

# --- Games History ---
with tabs[3]:
    st.subheader("Games History")
    games = list_games()
    df_games = pd.DataFrame(games, columns=["game_id", "played_at", "winner"])
    st.dataframe(df_games, use_container_width=True)

    if games:
        selected_gid = st.selectbox("Game", options=[g[0] for g in games])
        if selected_gid:
            rows = get_game_scores(selected_gid)
            st.table(pd.DataFrame(rows, columns=["player", "points"]))


# --- Export ---
with tabs[4]:
    st.subheader("Export")
    games = list_games()
    export_rows = []
    for gid, played_at, winner in games:
        rows = get_game_scores(gid)
        for player, points in rows:
            export_rows.append({
                "game_id": gid,
                "played_at": played_at,
                "winner": winner,
                "player": player,
                "points": points
            })
    export_df = pd.DataFrame(export_rows)
    st.download_button(
        label="Download CSV",
        data=export_df.to_csv(index=False),
        file_name="game_results_export.csv",
        mime="text/csv"
    )
    st.write("Preview:")
    st.dataframe(export_df, use_container_width=True)
