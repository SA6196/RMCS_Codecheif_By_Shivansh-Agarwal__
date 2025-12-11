Raja-Mantri-Chor-Sipahi – Backend (Python Flask)

This repository contains the backend for the classic Indian game Raja–Mantri–Chor–Sipahi, built using Python Flask.
It supports room creation, player joining, role assignment, guessing, and result calculation.

Features:
Create game rooms
Join room using name
Automatic random role assignment (Raja / Mantri / Chor / Sipahi)
Each player can privately check their role
Mantri can guess who is Chor
Result + scoring logic
Test endpoints using requests.http

🛠️ Tech Stack
Python 3
Flask
UUID for unique player/room IDs
In-memory storage (no database)

📌 API Endpoints Overview
1️⃣ Create Room
POST /room/create
Body:

{
  "name": "Alice"
}

2️⃣ Join Room
POST /room/join


Body:

{
  "roomId": "<room-id>",
  "name": "Bob"
}

3️⃣ Assign Roles (call after 4 players joined)
POST /room/assign/<roomId>

4️⃣ View My Role
GET /role/me/<roomId>/<playerId>

5️⃣ Mantri Guess
POST /guess/<roomId>


Body:

{
  "playerId": "<player-id>",
  "guess": "<suspected-chor-player-id>"
}

6️⃣ View Result
GET /result/<roomId>

▶️ Run Backend Locally

Open terminal inside project folder and run:

python app.py


Your API starts at:

http://127.0.0.1:3000

📁 Project Structure
├── app.py
├── requirements.txt
├── requests.http
├── .gitignore
└── .vscode/
    ├── launch.json
    └── tasks.json

✨ Author
Shivansh Agarwal
RMCS Codechef Project Backend
