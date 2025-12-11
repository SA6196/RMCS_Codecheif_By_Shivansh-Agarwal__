# app.py
"""
Raja-Mantri-Chor-Sipahi - Flask backend
Run: python app.py
API: create/join/players/assign/role/guess/result/leaderboard/reset
In-memory store (thread-safe with a Lock). Meant for Postman / curl testing.
"""
from flask import Flask, request, jsonify
from uuid import uuid4
from datetime import datetime
import random
import threading

app = Flask(__name__)
lock = threading.Lock()

# Default per-round points (configurable here)
DEFAULT_POINTS = {
    "Raja": 1000,
    "Mantri": 800,
    "Sipahi": 500,
    "Chor": 0
}

# In-memory rooms store: roomId -> room dict
rooms = {}

# Room structure (dict):
# {
#   id: str,
#   players: [ { id, name, cumulativeScore, role (current round, private), lastRole } ],
#   state: 'waiting'|'assigned'|'guessed'|'completed',
#   rolesAssigned: { playerId: role },
#   roundHistory: [ { timestamp, rolesAssigned, guess, pointsChange } ]
# }

def gen_id():
    return str(uuid4())

def get_player(room, player_id):
    for p in room["players"]:
        if p["id"] == player_id:
            return p
    return None

def random_shuffle_list(lst):
    a = lst[:]
    random.shuffle(a)
    return a

@app.route("/room/create", methods=["POST"])
def create_room():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400

    with lock:
        room_id = gen_id()
        player_id = gen_id()
        player = {"id": player_id, "name": name, "cumulativeScore": 0, "role": None, "lastRole": None}
        room = {
            "id": room_id,
            "players": [player],
            "state": "waiting",
            "rolesAssigned": {},
            "roundHistory": []
        }
        rooms[room_id] = room

    return jsonify({"roomId": room_id, "playerId": player_id, "message": "Room created. You are player1."}), 201

@app.route("/room/join", methods=["POST"])
def join_room():
    data = request.get_json(force=True, silent=True) or {}
    room_id = data.get("roomId")
    name = data.get("name")
    if not room_id or not name:
        return jsonify({"error": "roomId and name are required"}), 400

    with lock:
        room = rooms.get(room_id)
        if not room:
            return jsonify({"error": "Room not found"}), 404
        if room["state"] != "waiting":
            return jsonify({"error": "Cannot join: room already started or roles assigned"}), 400
        if len(room["players"]) >= 4:
            return jsonify({"error": "Room full (4 players)"}), 400

        player_id = gen_id()
        player = {"id": player_id, "name": name, "cumulativeScore": 0, "role": None, "lastRole": None}
        room["players"].append(player)

    return jsonify({"roomId": room_id, "playerId": player_id, "message": f"Joined room: {room_id}. Players now: {len(room['players'])}/4"}), 200

@app.route("/room/players/<room_id>", methods=["GET"])
def list_players(room_id):
    room = rooms.get(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    players = [{"id": p["id"], "name": p["name"]} for p in room["players"]]
    return jsonify({"roomId": room_id, "players": players, "state": room["state"]}), 200

@app.route("/room/assign/<room_id>", methods=["POST"])
def assign_roles(room_id):
    with lock:
        room = rooms.get(room_id)
        if not room:
            return jsonify({"error": "Room not found"}), 404
        if room["state"] != "waiting":
            return jsonify({"error": f"Cannot assign roles in state {room['state']}"}), 400
        if len(room["players"]) != 4:
            return jsonify({"error": "Need exactly 4 players to assign roles"}), 400

        roles = ["Raja", "Mantri", "Chor", "Sipahi"]
        shuffled_players = random_shuffle_list(room["players"])
        assigned = {}
        for i, player in enumerate(shuffled_players):
            pid = player["id"]
            role = roles[i]
            assigned[pid] = role
            player["role"] = role            # private for this round
            player["lastRole"] = role       # for later reveal
        room["rolesAssigned"] = assigned
        room["state"] = "assigned"

    # Do NOT reveal mapping here; only confirm
    return jsonify({"roomId": room_id, "message": "Roles assigned. Mantri, check your role endpoint to submit guess."}), 200

@app.route("/role/me/<room_id>/<player_id>", methods=["GET"])
def role_me(room_id, player_id):
    room = rooms.get(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    player = get_player(room, player_id)
    if not player:
        return jsonify({"error": "Player not found in room"}), 404
    if room["state"] not in ("assigned", "guessed", "completed"):
        return jsonify({"error": "Roles not assigned yet"}), 400
    # Return only this player's role
    return jsonify({"playerId": player["id"], "name": player["name"], "role": player["role"]}), 200

@app.route("/guess/<room_id>", methods=["POST"])
def submit_guess(room_id):
    data = request.get_json(force=True, silent=True) or {}
    mantri_id = data.get("mantriId")
    guessed_player_id = data.get("guessedPlayerId")
    if not mantri_id or not guessed_player_id:
        return jsonify({"error": "mantriId and guessedPlayerId are required"}), 400

    with lock:
        room = rooms.get(room_id)
        if not room:
            return jsonify({"error": "Room not found"}), 404
        if room["state"] != "assigned":
            return jsonify({"error": "Room not in guessing state"}), 400

        mantri = get_player(room, mantri_id)
        if not mantri:
            return jsonify({"error": "mantriId not found in room"}), 404
        if room["rolesAssigned"].get(mantri_id) != "Mantri":
            return jsonify({"error": "Only the Mantri can submit a guess"}), 403

        guessed = get_player(room, guessed_player_id)
        if not guessed:
            return jsonify({"error": "guessedPlayerId not found in room"}), 404

        # find actual Chor id
        actual_chor_id = next((pid for pid, role in room["rolesAssigned"].items() if role == "Chor"), None)
        correct = (guessed_player_id == actual_chor_id)

        # compute per-player change map
        points_change = {p["id"]: 0 for p in room["players"]}

        # find role-holder ids
        raja_id = next((pid for pid, r in room["rolesAssigned"].items() if r == "Raja"), None)
        sipahi_id = next((pid for pid, r in room["rolesAssigned"].items() if r == "Sipahi"), None)
        mantri_assigned_id = next((pid for pid, r in room["rolesAssigned"].items() if r == "Mantri"), None)
        chor_assigned_id = actual_chor_id

        # Always award Raja and Sipahi their default per-round scores (we treat as additions)
        if raja_id:
            points_change[raja_id] += DEFAULT_POINTS["Raja"]
        if sipahi_id:
            points_change[sipahi_id] += DEFAULT_POINTS["Sipahi"]

        # If Mantri guesses correctly, Mantri gets default; else Chor steals Mantri's points
        if correct:
            if mantri_assigned_id:
                points_change[mantri_assigned_id] += DEFAULT_POINTS["Mantri"]
        else:
            if chor_assigned_id:
                points_change[chor_assigned_id] += DEFAULT_POINTS["Mantri"]

        # Apply to cumulative
        for pid, delta in points_change.items():
            p = get_player(room, pid)
            if p:
                p["cumulativeScore"] += delta

        # store history and final state
        room["roundHistory"].append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "rolesAssigned": dict(room["rolesAssigned"]),
            "guess": {"mantriId": mantri_id, "guessedPlayerId": guessed_player_id, "correct": correct},
            "pointsChange": dict(points_change)
        })
        room["state"] = "completed"

        # Prepare output (reveal roles)
        result = {
            "correct": correct,
            "mantriId": mantri_id,
            "guessedPlayerId": guessed_player_id,
            "roles": [{"playerId": p["id"], "name": p["name"], "role": room["rolesAssigned"].get(p["id"])} for p in room["players"]],
            "pointsChange": points_change,
            "cumulativeScores": [{"playerId": p["id"], "name": p["name"], "cumulativeScore": p["cumulativeScore"]} for p in room["players"]],
            "message": "Mantri guessed correctly!" if correct else "Mantri guessed incorrectly. Chor steals Mantri points."
        }

    return jsonify(result), 200

@app.route("/result/<room_id>", methods=["GET"])
def get_result(room_id):
    room = rooms.get(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if room["state"] not in ("guessed", "completed"):
        # allow completed as the canonical final state
        pass
    last_round = room["roundHistory"][-1] if room["roundHistory"] else None
    roles = [{"playerId": p["id"], "name": p["name"], "role": p["lastRole"]} for p in room["players"]]
    cumulative = [{"playerId": p["id"], "name": p["name"], "cumulativeScore": p["cumulativeScore"]} for p in room["players"]]
    return jsonify({"roomId": room_id, "roles": roles, "cumulativeScores": cumulative, "lastRound": last_round}), 200

@app.route("/leaderboard/<room_id>", methods=["GET"])
def leaderboard(room_id):
    room = rooms.get(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    board = sorted([{"playerId": p["id"], "name": p["name"], "score": p["cumulativeScore"]} for p in room["players"]], key=lambda x: x["score"], reverse=True)
    return jsonify({"roomId": room_id, "leaderboard": board}), 200

@app.route("/room/reset/<room_id>", methods=["POST"])
def reset_room(room_id):
    with lock:
        room = rooms.get(room_id)
        if not room:
            return jsonify({"error": "Room not found"}), 404
        for p in room["players"]:
            p["role"] = None
            p["lastRole"] = None
        room["rolesAssigned"] = {}
        room["state"] = "waiting"
    return jsonify({"message": "Room reset for next round. You may assign roles again."}), 200

@app.route("/rooms", methods=["GET"])
def list_rooms():
    summary = [{"roomId": r["id"], "players": len(r["players"]), "state": r["state"]} for r in rooms.values()]
    return jsonify({"rooms": summary}), 200

if __name__ == "__main__":
    # optional: set random seed from system time
    random.seed()
    app.run(host="0.0.0.0", port=3000, debug=True)
