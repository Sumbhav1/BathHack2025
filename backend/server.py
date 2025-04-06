from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from threading import Thread
import time
from main_backend import warning_queue

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

def warning_emitter():
    print("Warning emitter started")
    while True:
        if not warning_queue.empty():
            source_id, message = warning_queue.get()
            print(f"Emitting warning: {source_id}, {message}")
            socketio.emit("warning", {
                "source": str(source_id),
                "message": message
            })
        time.sleep(0.1)

@app.route("/api/status")
def status():
    return {"status": "running"}

if __name__ == "__main__":
    Thread(target=warning_emitter, daemon=True).start()
    socketio.run(app, host="0.0.0.0", port=5000)

