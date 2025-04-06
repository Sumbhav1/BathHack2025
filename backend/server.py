from flask import Flask, jsonify, g
from queue import Queue
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from threading import Thread
import time
import threading
from main_backend import warning_queue
from audio_handler import list_audio_devices

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")


def warning_emitter():
    print("Warning emitter started.")
    while True:    
        if not warning_queue.empty():
            source_id, message = warning_queue.get()
            print(f"[EMIT] Source {source_id}: {message}")
            socketio.emit("warning", {"source": str(source_id), "message": message})
        
        time.sleep(0.1)

@app.route("/api/audio-devices", methods=["GET"])
def get_audio_devices():
    devices = list_audio_devices()
    return jsonify(devices)


@app.route("/api/status")
def status():
    return jsonify({"status": "Server is running!"})



Thread(target=warning_emitter, daemon=True).start()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)

