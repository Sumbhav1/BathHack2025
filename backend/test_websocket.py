import socketio
import time
from main_backend import warning_queue

def test_websocket_connection():
    sio = socketio.Client()
    warnings_received = []

    @sio.on('warning')
    def on_warning(data):
        print(f"Received warning: {data}")
        warnings_received.append(data)

    try:
        print("Connecting to websocket server...")
        sio.connect('http://localhost:5000')
        
        print("Adding test warning...")
        warning_queue.put((0, "Test warning"))
        
        # Wait for warning
        time.sleep(2)
        
        if warnings_received:
            print("✅ Warning received successfully!")
        else:
            print("❌ No warning received")
            
    finally:
        sio.disconnect()

if __name__ == "__main__":
    test_websocket_connection()