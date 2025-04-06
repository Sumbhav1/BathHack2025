from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from threading import Thread, Event
import time
from queue import Queue
from audio_handler import list_audio_devices, AudioCapture
from main_backend import warning_queue

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Store active audio captures
active_captures = {}

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

@socketio.on('start_audio')
def handle_start_audio(data):
    device_id = data.get('deviceId')
    device_index = data.get('deviceIndex')
    channel = data.get('channel')
    
    if device_id in active_captures:
        emit('audio_error', {'deviceId': device_id, 'message': 'Device already streaming'})
        return

    try:
        # Create queues for audio processing
        audio_queue = Queue(maxsize=200)
        stop_event = Event()
        
        # Initialize audio capture
        capture = AudioCapture(
            device_index=device_index,
            target_channel=channel,
            output_queues={'stream': audio_queue},
            stop_event=stop_event
        )
        
        # Store capture instance and control objects
        active_captures[device_id] = {
            'capture': capture,
            'stop_event': stop_event,
            'queue': audio_queue
        }
        
        # Start capture in a separate thread
        Thread(target=capture.run, daemon=True).start()
        
    except Exception as e:
        print(f"Error starting audio capture: {e}")
        emit('audio_error', {'deviceId': device_id, 'message': str(e)})

@socketio.on('stop_audio')
def handle_stop_audio(data):
    device_id = data.get('deviceId')
    if device_id in active_captures:
        try:
            # Signal the capture thread to stop
            active_captures[device_id]['stop_event'].set()
            # Clean up
            del active_captures[device_id]
        except Exception as e:
            print(f"Error stopping audio capture: {e}")
            emit('audio_error', {'deviceId': device_id, 'message': str(e)})

Thread(target=warning_emitter, daemon=True).start()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)

