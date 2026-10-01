# Live Stream Scene Manager

A scene switcher (like OBS) built on a doubly linked list written from scratch.
Each scene is a `Node` with `prev` and `next` links; the `current` pointer is the live scene.

## Run in VS Code

1. Open this folder in VS Code (File > Open Folder).
2. Open a terminal (Ctrl+`) and create a virtual environment:
   - Windows: `python -m venv .venv` then `.venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Start the server: `python app.py` (or press F5 and choose "Run Live Stream Manager").
5. Open http://127.0.0.1:5000

## Run the tests

`python -m unittest discover tests`

## REST API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/scenes` | List all scenes and the live one |
| POST | `/api/scenes` | Add a scene: `{"name": "Chat", "position": "end" or "after_current"}` |
| POST | `/api/scenes/next` | Make the next scene live (409 on the last scene) |
| POST | `/api/scenes/previous` | Make the previous scene live (409 on the first scene) |
| DELETE | `/api/scenes/current` | Remove the live scene |

## Complexity

append, insert after current, next, previous and remove current are all O(1).
