# Chess Tournament Manager API

This is a simple REST API project built with Flask and SQLite (using `sqlite3` without an ORM).
It uses Flask-RESTX for Swagger UI documentation.

## Features

- Automatically creates `players` and `games` tables
- Automatically calculates Elo rating updates (`K = 32`)
- All endpoints return JSON responses
- Swagger UI is available at `/docs`
- Single-file structure in `app.py`

## Requirements

- Python 3.10+
- Virtual environment (`.venv`) is recommended

## Installation

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install flask flask-restx
```

## Run

```powershell
python app.py
```

Server URLs:

- API: http://127.0.0.1:5000
- Swagger UI: http://127.0.0.1:5000/docs

## Database

File: `chess.db` (created in the project folder)

Tables:

1. `players`
   - `id`
   - `name`
   - `rating`
   - `created_at`
2. `games`
   - `id`
   - `player1_id`
   - `player2_id`
   - `result` (`player1`, `player2`, `draw`)
   - `played_at`

## Elo Formula

- `K = 32`
- `Expected = 1 / (1 + 10^((opponent_rating - player_rating) / 400))`
- `New rating = old_rating + K * (actual_score - expected_score)`
- `actual_score`: win = 1, draw = 0.5, loss = 0

## Endpoints

### Players

- `POST /players` - add a new player (default rating: 1200)
- `GET /players` - list all players
- `GET /players/<id>` - get a single player
- `PUT /players/<id>` - update player name
- `DELETE /players/<id>` - delete player

### Games

- `POST /games` - record a game result and update Elo ratings
- `GET /games` - list all games

### Leaderboard

- `GET /leaderboard` - list players sorted by rating (descending)

## Sample Requests

### curl

```bash
# Add players
curl -X POST http://127.0.0.1:5000/players \
  -H "Content-Type: application/json" \
  -d '{"name":"Magnus Carlsen"}'

curl -X POST http://127.0.0.1:5000/players \
  -H "Content-Type: application/json" \
  -d '{"name":"Hikaru Nakamura"}'

# List players
curl http://127.0.0.1:5000/players

# Add game
curl -X POST http://127.0.0.1:5000/games \
  -H "Content-Type: application/json" \
  -d '{"player1_id":1,"player2_id":2,"result":"draw"}'

# Leaderboard
curl http://127.0.0.1:5000/leaderboard
```

### PowerShell

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/players" -ContentType "application/json" -Body '{"name":"Magnus Carlsen"}'
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/players" -ContentType "application/json" -Body '{"name":"Hikaru Nakamura"}'

Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:5000/players"

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/games" -ContentType "application/json" -Body '{"player1_id":1,"player2_id":2,"result":"player1"}'

Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:5000/leaderboard"
```

## Notes

- When a game is recorded, both players' ratings are updated.
- A player cannot play against themselves.
- Deleting a player is blocked if they are referenced by existing games.
