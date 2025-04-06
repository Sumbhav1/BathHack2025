import socketio
import time
from main_backend import warning_queue

def print_queue_status():
    size = warning_queue.qsize()
    print(f"Current warning queue size: {size}")
    return size

def test_websocket_connection():
    sio = socketio.Client(logger=True)
    warnings_received = []
    connected = False
    device_id = None

    @sio.event
    def connect():
        nonlocal connected
        connected = True
        print("✅ Connected to server")

    @sio.event
    def connect_error(error):
        print(f"❌ Connection failed: {error}")

    @sio.event
    def disconnect():
        nonlocal connected
        connected = False
        print("❌ Disconnected from server")

    @sio.on('warning')
    def on_warning(data):
        print(f"✅ Received warning: {data}")
        warnings_received.append(data)

    try:
        print("\n🔄 Testing WebSocket Connection")
        print("-------------------------------")
        
        # Check initial queue state
        print("Initial queue status:")
        initial_size = print_queue_status()
        
        print("\n1. Connecting to server...")
        sio.connect('http://localhost:5000')
        
        # Wait for connection to establish
        time.sleep(1)
        
        if connected:
            # Register a test device
            print("\n2. Registering test device...")
            # Using a valid device index format (matching frontend)
            device_data = {
                'deviceId': '1',  # Test device ID
                'deviceIndex': 1,
                'channel': 0
            }
            sio.emit('start_audio', device_data)
            time.sleep(1)  # Wait for registration
            
            print("\n3. Adding test warning to queue...")
            # Use the same device index format as frontend
            warning_queue.put((1, "Test warning message"))
            
            # Verify warning was added
            print("Queue status after adding warning:")
            new_size = print_queue_status()
            
            if new_size > initial_size:
                print("✅ Warning successfully added to queue")
            else:
                print("❌ Warning may not have been added to queue")
            
            # Wait longer for warning processing
            print("\n4. Waiting for warning (5 seconds)...")
            # Check queue size every second
            for i in range(5):
                time.sleep(1)
                print(f"Queue status after {i+1} second(s):")
                print_queue_status()
            
            if warnings_received:
                print("\n✅ Test Successful!")
                print(f"Received {len(warnings_received)} warnings:")
                for warning in warnings_received:
                    print(f"- {warning}")
            else:
                print("\n❌ Test Failed: No warnings received")
                print("Debug info:")
                print(f"- Connected: {connected}")
                print(f"- Final queue size: {warning_queue.qsize()}")
        else:
            print("\n❌ Test Failed: Could not connect to server")
            
    except Exception as e:
        print(f"\n❌ Test Error: {e}")
    finally:
        if sio.connected:
            if device_data:
                print("\n5. Stopping test device...")
                sio.emit('stop_audio', device_data)
                time.sleep(1)
            print("\n6. Disconnecting...")
            sio.disconnect()
        
        # Check final queue state
        print("\nFinal queue status:")
        print_queue_status()
        print("\nTest Complete")

if __name__ == "__main__":
    test_websocket_connection()