from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
from threading import Thread, Event
import time
from queue import Queue
from audio_handler import AudioCapture, list_audio_devices
from ml_interface import buffer_and_analyze_audio
from main_backend import warning_queue

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Track connected clients and active devices
connected_clients = set()
active_devices = {}  # Map device IDs to their info
warning_thread = None
warning_thread_stop = Event()

# Store audio monitoring resources
audio_captures = {}  # Store AudioCapture instances
audio_threads = {}   # Store audio capture threads
ml_queues = {}      # Store ML input queues
ml_threads = {}     # Store ML processing threads
stop_events = {}    # Store stop events for each device

def warning_emitter():
    print("Warning emitter started")
    while not warning_thread_stop.is_set():
        if not warning_queue.empty():
            try:
                source_id, message = warning_queue.get_nowait()
                print(f"Warning Data:")
                print(f"- Source ID: {source_id}, Type: {type(source_id)}")
                print(f"- Message: {message}")
                print(f"- Active Devices: {active_devices}")
                
                # Handle tuple source_id
                device_index = source_id[0] if isinstance(source_id, tuple) else source_id
                source_id_str = str(device_index)
                
                print(f"- Converted Source ID: {source_id_str}")
                
                if active_devices:
                    print(f"Emitting warning for source {source_id_str}")
                    socketio.emit("warning", {
                        "source": source_id_str,
                        "message": message
                    })
                else:
                    print("No active devices registered")
            except Exception as e:
                print(f"Error in warning emitter: {e}")
                import traceback
                traceback.print_exc()
        socketio.sleep(0.1)
    print("Warning emitter stopping...")

def start_monitoring_device(device_id, device_index, channel):
    """Start audio monitoring threads for a device"""
    try:
        # Create stop event for this device
        stop_events[device_id] = Event()
        
        # Create ML queue for this device
        ml_queues[device_id] = Queue(maxsize=500)
        
        # Create audio capture instance
        audio_captures[device_id] = AudioCapture(
            device_index=device_index,
            target_channel=channel,
            output_queues={'ml': ml_queues[device_id]},
            stop_event=stop_events[device_id]
        )
        
        # Start audio capture thread
        audio_threads[device_id] = Thread(
            target=audio_captures[device_id].run,
            daemon=True,
            name=f"Audio_Capture_{device_id}"
        )
        audio_threads[device_id].start()
        
        # Wait briefly to ensure audio capture started
        time.sleep(0.5)
        if not audio_threads[device_id].is_alive():
            raise Exception("Audio capture thread failed to start")
        
        # Start ML processing thread
        source_id = (device_index, channel)  # Format source_id as expected by ML
        ml_threads[device_id] = Thread(
            target=buffer_and_analyze_audio,
            args=(source_id, ml_queues[device_id], None, warning_queue),
            daemon=True,
            name=f"ML_Interface_{device_id}"
        )
        ml_threads[device_id].start()
        
        print(f"Started monitoring threads for device {device_id}")
        return True
        
    except Exception as e:
        print(f"Error starting monitoring for device {device_id}: {e}")
        stop_monitoring_device(device_id)
        return False

def stop_monitoring_device(device_id):
    """Stop and clean up monitoring threads for a device"""
    try:
        # Signal stop to audio capture
        if device_id in stop_events:
            stop_events[device_id].set()
        
        # Signal stop to ML thread
        if device_id in ml_queues:
            try:
                ml_queues[device_id].put(None, block=False)
            except:
                pass
        
        # Wait for threads to stop
        if device_id in audio_threads and audio_threads[device_id].is_alive():
            audio_threads[device_id].join(timeout=5.0)
        if device_id in ml_threads and ml_threads[device_id].is_alive():
            ml_threads[device_id].join(timeout=5.0)
        
        # Clean up resources
        for resource_dict in [audio_captures, audio_threads, ml_queues, ml_threads, stop_events]:
            if device_id in resource_dict:
                del resource_dict[device_id]
                
        print(f"Stopped monitoring threads for device {device_id}")
        
    except Exception as e:
        print(f"Error stopping monitoring for device {device_id}: {e}")

@socketio.on('connect')
def handle_connect():
    client_id = request.sid
    connected_clients.add(client_id)
    print(f"Client connected: {client_id}")
    print(f"Active devices: {active_devices}")

@socketio.on('disconnect')
def handle_disconnect():
    client_id = request.sid
    if client_id in connected_clients:
        connected_clients.remove(client_id)
    print(f"Client disconnected: {client_id}")
    print(f"Remaining active devices: {active_devices}")

@socketio.on('start_audio')
def handle_start_audio(data):
    device_id = str(data.get('deviceId'))
    device_index = data.get('deviceIndex')
    channel = data.get('channel')
    
    print(f"Registering device: {device_id} (index: {device_index}, channel: {channel})")
    
    # Start monitoring threads
    if start_monitoring_device(device_id, device_index, channel):
        active_devices[device_id] = {
            'index': device_index,
            'channel': channel,
            'client': request.sid
        }
        print(f"Successfully registered device {device_id}")
        return {"status": "success"}
    else:
        return {"status": "error", "message": "Failed to start audio monitoring"}

@socketio.on('stop_audio')
def handle_stop_audio(data):
    device_id = str(data.get('deviceId'))
    if device_id in active_devices:
        stop_monitoring_device(device_id)
        del active_devices[device_id]
        print(f"Device {device_id} stopped and unregistered")

@socketio.on('test')
def handle_test():
    print("Received test event")
    return "Test successful"

@app.route("/api/status")
def status():
    return {
        "status": "running",
        "clients": len(connected_clients),
        "active_devices": len(active_devices)
    }

@app.route("/api/audio-devices", methods=["GET"])
def get_audio_devices():
    devices = list_audio_devices()
    return jsonify(devices)

def start_warning_emitter():
    global warning_thread
    if warning_thread is None or not warning_thread.is_alive():
        warning_thread_stop.clear()
        warning_thread = Thread(target=warning_emitter, daemon=True)
        warning_thread.start()
        print("Warning emitter thread started")

if __name__ == "__main__":
    start_warning_emitter()
    socketio.run(app, host="0.0.0.0", port=5000)

