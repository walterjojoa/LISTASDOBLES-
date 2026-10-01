"""Flask backend for the Live Stream Scene Manager."""
import os
from itertools import count
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, request, send_from_directory

from doubly_linked_list import DoublyLinkedList

BASE_DIR = Path(__file__).resolve().parent
PALETTE = ["#1f5f8b", "#c4572a", "#4a7c59", "#7a4b94", "#b8860b", "#2e7d8c", "#a63d5a"]
MAX_NAME_LENGTH = 30

app = Flask(__name__, static_folder=None)
scenes = DoublyLinkedList()
state_lock = Lock()
id_counter = count(1)


def create_scene(name):
    scene_id = next(id_counter)
    return {"id": scene_id, "name": name, "color": PALETTE[(scene_id - 1) % len(PALETTE)]}


def seed_scenes():
    for name in ("Intro Screen", "Webcam", "Screen Share", "Gameplay", "Be Right Back"):
        scenes.append(create_scene(name))


def snapshot(message=None):
    """Build the JSON payload describing the whole list."""
    current = scenes.current
    live_id = current.data["id"] if current else None
    return {
        "scenes": [{**s, "is_live": s["id"] == live_id} for s in scenes],
        "size": len(scenes),
        "current_id": live_id,
        "previous_name": current.prev.data["name"] if current and current.prev else None,
        "next_name": current.next.data["name"] if current and current.next else None,
        "has_previous": scenes.has_previous(),
        "has_next": scenes.has_next(),
        "message": message,
        "mode": "demo",
    }


def error(message, status=400):
    return jsonify({"error": message}), status


def obs_configured():
    return bool(os.environ.get("OBS_HOST"))


def create_obs_client():
    import obsws_python as obs

    return obs.ReqClient(
        host=os.environ["OBS_HOST"],
        port=int(os.environ.get("OBS_PORT", "4455")),
        password=os.environ.get("OBS_PASSWORD", ""),
        timeout=3,
    )


def obs_snapshot(client, message=None):
    response = client.get_scene_list()
    names = [scene["sceneName"] for scene in response.scenes]
    current_name = response.current_program_scene_name
    current_index = names.index(current_name) if current_name in names else None
    scene_data = [
        {
            "id": index + 1,
            "name": name,
            "color": PALETTE[index % len(PALETTE)],
            "is_live": index == current_index,
        }
        for index, name in enumerate(names)
    ]
    return {
        "scenes": scene_data,
        "size": len(scene_data),
        "current_id": current_index + 1 if current_index is not None else None,
        "previous_name": names[current_index - 1] if current_index else None,
        "next_name": names[current_index + 1]
        if current_index is not None and current_index + 1 < len(names)
        else None,
        "has_previous": current_index is not None and current_index > 0,
        "has_next": current_index is not None and current_index + 1 < len(names),
        "message": message,
        "mode": "obs",
    }


def obs_unavailable(exc):
    return error(f"No se pudo comunicar con OBS: {exc}", 503)


def move_obs_scene(step):
    try:
        with create_obs_client() as client:
            state = obs_snapshot(client)
            live_index = next(
                (index for index, scene in enumerate(state["scenes"]) if scene["is_live"]),
                None,
            )
            target_index = live_index + step if live_index is not None else None
            if target_index is None or not 0 <= target_index < state["size"]:
                direction = "anterior" if step < 0 else "siguiente"
                return error(f"No hay una escena {direction}.", 409)
            target = state["scenes"][target_index]["name"]
            client.set_current_program_scene(target)
            return jsonify(obs_snapshot(client, f"'{target}' ahora está en vivo."))
    except Exception as exc:
        return obs_unavailable(exc)


def stream_action(action):
    if not obs_configured():
        return error("Configura OBS_HOST para controlar la transmisión de OBS.", 503)
    try:
        with create_obs_client() as client:
            getattr(client, action)()
            status = client.get_stream_status()
            streaming = bool(status.output_active)
            message = "Transmisión iniciada." if action == "start_stream" else "Transmisión detenida."
            return jsonify({"streaming": streaming, "message": message})
    except Exception as exc:
        return obs_unavailable(exc)


@app.get("/")
def index():
    return send_from_directory(BASE_DIR / "static", "index.html")


@app.get("/api/scenes")
def get_scenes():
    if obs_configured():
        try:
            with create_obs_client() as client:
                return jsonify(obs_snapshot(client))
        except Exception as exc:
            return obs_unavailable(exc)
    with state_lock:
        return jsonify(snapshot())


@app.get("/api/obs/status")
def get_obs_status():
    if not obs_configured():
        return jsonify({"mode": "demo", "connected": False, "streaming": False})
    try:
        with create_obs_client() as client:
            version = client.get_version()
            stream = client.get_stream_status()
            return jsonify(
                {
                    "mode": "obs",
                    "connected": True,
                    "obs_version": version.obs_version,
                    "streaming": bool(stream.output_active),
                }
            )
    except Exception as exc:
        return obs_unavailable(exc)


@app.post("/api/scenes")
def add_scene():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    position = body.get("position", "end")
    if not name:
        return error("Scene name is required.")
    if len(name) > MAX_NAME_LENGTH:
        return error(f"Scene name must be at most {MAX_NAME_LENGTH} characters.")
    if position not in ("end", "after_current"):
        return error("Position must be 'end' or 'after_current'.")
    if obs_configured():
        if position != "end":
            return error("OBS WebSocket solo permite crear escenas al final de la lista.")
        try:
            with create_obs_client() as client:
                state = obs_snapshot(client)
                if any(scene["name"] == name for scene in state["scenes"]):
                    return error(f"La escena '{name}' ya existe en OBS.", 409)
                client.create_scene(name)
                return jsonify(obs_snapshot(client, f"Escena '{name}' creada en OBS.")), 201
        except Exception as exc:
            return obs_unavailable(exc)
    with state_lock:
        scene = create_scene(name)
        if position == "after_current":
            scenes.insert_after_current(scene)
        else:
            scenes.append(scene)
        return jsonify(snapshot(f"Added scene '{name}'.")), 201


@app.post("/api/scenes/next")
def next_scene():
    if obs_configured():
        return move_obs_scene(1)
    with state_lock:
        try:
            scene = scenes.move_next()
        except IndexError as exc:
            return error(str(exc), 409)
        return jsonify(snapshot(f"'{scene['name']}' is now live."))


@app.post("/api/scenes/previous")
def previous_scene():
    if obs_configured():
        return move_obs_scene(-1)
    with state_lock:
        try:
            scene = scenes.move_previous()
        except IndexError as exc:
            return error(str(exc), 409)
        return jsonify(snapshot(f"'{scene['name']}' is now live."))


@app.delete("/api/scenes/current")
def remove_current_scene():
    if obs_configured():
        try:
            with create_obs_client() as client:
                state = obs_snapshot(client)
                live = next(
                    (scene for scene in state["scenes"] if scene["is_live"]),
                    None,
                )
                if live is None:
                    return error("No hay una escena en vivo para eliminar.", 409)
                client.remove_scene(live["name"])
                return jsonify(obs_snapshot(client, f"Escena '{live['name']}' eliminada de OBS."))
        except Exception as exc:
            return obs_unavailable(exc)
    with state_lock:
        try:
            removed = scenes.remove_current()
        except IndexError as exc:
            return error(str(exc), 409)
        return jsonify(snapshot(f"Removed scene '{removed['name']}'."))


@app.get("/api/stream/status")
def get_stream_status():
    if not obs_configured():
        return jsonify({"available": False, "streaming": False, "mode": "demo"})
    try:
        with create_obs_client() as client:
            status = client.get_stream_status()
            return jsonify({"available": True, "streaming": bool(status.output_active), "mode": "obs"})
    except Exception as exc:
        return obs_unavailable(exc)


@app.post("/api/stream/start")
def start_stream():
    return stream_action("start_stream")


@app.post("/api/stream/stop")
def stop_stream():
    return stream_action("stop_stream")


seed_scenes()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
