import sqlite3
from datetime import datetime, timezone
from typing import Tuple

from flask import Flask, jsonify, request
from flask_restx import Api, Namespace, Resource, fields

DB_PATH = "chess.db"
K_FACTOR = 32

app = Flask(__name__)
api = Api(
    app,
    version="1.0",
    title="Chess Tournament Manager API",
    description="Simple chess tournament manager with Elo rating updates.",
    doc="/docs",
)

players_ns = Namespace("players", description="Player operations", path="/players")
games_ns = Namespace("games", description="Game operations", path="/games")
leaderboard_ns = Namespace("leaderboard", description="Leaderboard operations", path="/leaderboard")

api.add_namespace(players_ns)
api.add_namespace(games_ns)
api.add_namespace(leaderboard_ns)


player_model = players_ns.model(
    "Player",
    {
        "id": fields.Integer(readOnly=True),
        "name": fields.String(required=True, description="Player name"),
        "rating": fields.Integer(description="Elo rating"),
        "created_at": fields.String(description="UTC ISO timestamp"),
    },
)

player_create_model = players_ns.model(
    "PlayerCreate",
    {
        "name": fields.String(required=True, description="Player name"),
        "rating": fields.Integer(required=False, description="Optional initial rating"),
    },
)

player_update_model = players_ns.model(
    "PlayerUpdate",
    {
        "name": fields.String(required=True, description="Updated player name"),
    },
)

game_model = games_ns.model(
    "Game",
    {
        "id": fields.Integer(readOnly=True),
        "player1_id": fields.Integer(required=True),
        "player2_id": fields.Integer(required=True),
        "result": fields.String(required=True, enum=["player1", "player2", "draw"]),
        "played_at": fields.String(description="UTC ISO timestamp"),
    },
)

leaderboard_model = leaderboard_ns.model(
    "LeaderboardEntry",
    {
        "id": fields.Integer,
        "name": fields.String,
        "rating": fields.Integer,
        "created_at": fields.String,
    },
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                rating INTEGER NOT NULL DEFAULT 1200,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player1_id INTEGER NOT NULL,
                player2_id INTEGER NOT NULL,
                result TEXT NOT NULL CHECK (result IN ('player1', 'player2', 'draw')),
                played_at TEXT NOT NULL,
                FOREIGN KEY (player1_id) REFERENCES players(id) ON DELETE RESTRICT,
                FOREIGN KEY (player2_id) REFERENCES players(id) ON DELETE RESTRICT,
                CHECK (player1_id != player2_id)
            )
            """
        )
        conn.commit()


def get_expected_score(player_rating: int, opponent_rating: int) -> float:
    return 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))


def calculate_new_ratings(player1_rating: int, player2_rating: int, result: str) -> Tuple[int, int]:
    expected1 = get_expected_score(player1_rating, player2_rating)
    expected2 = get_expected_score(player2_rating, player1_rating)

    if result == "player1":
        actual1, actual2 = 1.0, 0.0
    elif result == "player2":
        actual1, actual2 = 0.0, 1.0
    else:
        actual1, actual2 = 0.5, 0.5

    new_rating1 = round(player1_rating + K_FACTOR * (actual1 - expected1))
    new_rating2 = round(player2_rating + K_FACTOR * (actual2 - expected2))
    return new_rating1, new_rating2


def fetch_player_or_404(conn: sqlite3.Connection, player_id: int) -> sqlite3.Row:
    player = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    if player is None:
        api.abort(404, f"Player with id {player_id} not found")
    return player


@app.errorhandler(400)
def handle_bad_request(error):
    return jsonify({"message": str(error)}), 400


@app.errorhandler(404)
def handle_not_found(error):
    return jsonify({"message": str(error)}), 404


@app.errorhandler(500)
def handle_server_error(error):
    return jsonify({"message": "Internal server error", "details": str(error)}), 500


@players_ns.route("")
class PlayerListResource(Resource):
    @players_ns.marshal_list_with(player_model)
    def get(self):
        """List all players with their ratings"""
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT id, name, rating, created_at FROM players ORDER BY id ASC"
            ).fetchall()
        return [dict(row) for row in rows], 200

    @players_ns.expect(player_create_model, validate=True)
    @players_ns.marshal_with(player_model, code=201)
    def post(self):
        """Add a new player (default rating: 1200)"""
        payload = request.get_json() or {}
        name = (payload.get("name") or "").strip()

        if not name:
            api.abort(400, "Field 'name' is required")

        rating = payload.get("rating", 1200)
        if not isinstance(rating, int):
            api.abort(400, "Field 'rating' must be an integer")

        created_at = now_utc_iso()
        with get_db_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO players (name, rating, created_at) VALUES (?, ?, ?)",
                (name, rating, created_at),
            )
            conn.commit()
            new_id = cursor.lastrowid
            player = conn.execute(
                "SELECT id, name, rating, created_at FROM players WHERE id = ?", (new_id,)
            ).fetchone()
        return dict(player), 201


@players_ns.route("/<int:player_id>")
@players_ns.param("player_id", "Player ID")
class PlayerResource(Resource):
    @players_ns.marshal_with(player_model)
    def get(self, player_id: int):
        """Get a single player"""
        with get_db_connection() as conn:
            player = conn.execute(
                "SELECT id, name, rating, created_at FROM players WHERE id = ?", (player_id,)
            ).fetchone()
            if player is None:
                api.abort(404, f"Player with id {player_id} not found")
        return dict(player), 200

    @players_ns.expect(player_update_model, validate=True)
    @players_ns.marshal_with(player_model)
    def put(self, player_id: int):
        """Update player name"""
        payload = request.get_json() or {}
        name = (payload.get("name") or "").strip()

        if not name:
            api.abort(400, "Field 'name' is required")

        with get_db_connection() as conn:
            fetch_player_or_404(conn, player_id)
            conn.execute("UPDATE players SET name = ? WHERE id = ?", (name, player_id))
            conn.commit()
            player = conn.execute(
                "SELECT id, name, rating, created_at FROM players WHERE id = ?", (player_id,)
            ).fetchone()
        return dict(player), 200

    def delete(self, player_id: int):
        """Delete a player"""
        with get_db_connection() as conn:
            fetch_player_or_404(conn, player_id)
            try:
                conn.execute("DELETE FROM players WHERE id = ?", (player_id,))
                conn.commit()
            except sqlite3.IntegrityError:
                api.abort(
                    400,
                    "Cannot delete player because they are referenced by one or more games",
                )
        return {"message": f"Player {player_id} deleted"}, 200


@games_ns.route("")
class GameListResource(Resource):
    @games_ns.marshal_list_with(game_model)
    def get(self):
        """List all games"""
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT id, player1_id, player2_id, result, played_at FROM games ORDER BY id ASC"
            ).fetchall()
        return [dict(row) for row in rows], 200

    @games_ns.expect(game_model, validate=True)
    @games_ns.marshal_with(game_model, code=201)
    def post(self):
        """Record a game result and auto-update Elo ratings"""
        payload = request.get_json() or {}
        player1_id = payload.get("player1_id")
        player2_id = payload.get("player2_id")
        result = payload.get("result")

        if not isinstance(player1_id, int) or not isinstance(player2_id, int):
            api.abort(400, "Fields 'player1_id' and 'player2_id' must be integers")

        if player1_id == player2_id:
            api.abort(400, "A player cannot play against themselves")

        if result not in {"player1", "player2", "draw"}:
            api.abort(400, "Field 'result' must be one of: player1, player2, draw")

        played_at = now_utc_iso()

        with get_db_connection() as conn:
            player1 = fetch_player_or_404(conn, player1_id)
            player2 = fetch_player_or_404(conn, player2_id)

            new_rating1, new_rating2 = calculate_new_ratings(
                player1["rating"],
                player2["rating"],
                result,
            )

            cursor = conn.execute(
                "INSERT INTO games (player1_id, player2_id, result, played_at) VALUES (?, ?, ?, ?)",
                (player1_id, player2_id, result, played_at),
            )
            conn.execute("UPDATE players SET rating = ? WHERE id = ?", (new_rating1, player1_id))
            conn.execute("UPDATE players SET rating = ? WHERE id = ?", (new_rating2, player2_id))
            conn.commit()

            game = conn.execute(
                "SELECT id, player1_id, player2_id, result, played_at FROM games WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()

        return dict(game), 201


@leaderboard_ns.route("")
class LeaderboardResource(Resource):
    @leaderboard_ns.marshal_list_with(leaderboard_model)
    def get(self):
        """Get players sorted by rating (highest first)"""
        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, name, rating, created_at
                FROM players
                ORDER BY rating DESC, id ASC
                """
            ).fetchall()
        return [dict(row) for row in rows], 200


init_db()

if __name__ == "__main__":
    app.run(debug=True)
