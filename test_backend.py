import time
import queue
import threading
import numpy as np

# Assuming your backend package is structured correctly
from backend import BackendService

# --- Configuration ---
TEST_DURATION_SECONDS = 15 # How long to run the main test loop
MONITOR_DEVICE_INDEX = None # Set to a specific index if needed, otherwise uses first available
MONITOR_CHANNEL_INDEX = 0
REQUEST_BUFFER_SECONDS = 10 # How many seconds of the buffer to request at the end

def print_queue_messages(q: queue.Queue, name: str, stop_event: threading.Event):
    """Continuously prints messages from a queue in a separate thread."""
    print(f"[{name} Queue Monitor] Started.")
    while not stop_event.is_set():
        try:
            message = q.get(timeout=0.1) # Timeout to allow checking stop_event
            if message is None: # Sentinel value
                break
            print(f"[{name} Queue] Received: {message['type']} - Device: {message.get('device_id', 'N/A')}, Channel: {message.get('channel_index', 'N/A')}")
            # Optionally print more details based on type
            if message['type'] == 'level_update':
                print(f"  RMS: {message['rms']:.4f}")
            elif message['type'] == 'live_audio':
                print(f"  Data Length: {len(message['data'])}")
            elif message['type'] == 'buffer_data':
                print(f"  Buffer Data Shape: {message['data'].shape if isinstance(message['data'], np.ndarray) else len(message['data'])}")
            elif message['type'] == 'pop_update':
                 print(f"  Pop Detected: {message['pop_detected']}")
            elif message['type'] == 'device_list':
                 print(f"  Devices: {message['data']}")
            q.task_done() # Mark message as processed
        except queue.Empty:
            continue # No message, loop again
        except Exception as e:
            print(f"[{name} Queue Monitor] Error: {e}")
    print(f"[{name} Queue Monitor] Stopped.")


if __name__ == "__main__":
    print("--- Backend Test Script --- ")
    backend = BackendService()

    # Start queue monitoring threads
    stop_event = threading.Event()
    feature_monitor = threading.Thread(target=print_queue_messages, args=(backend.feature_queue, "Feature", stop_event), daemon=True)
    live_audio_monitor = threading.Thread(target=print_queue_messages, args=(backend.live_audio_queue, "LiveAudio", stop_event), daemon=True)
    feature_monitor.start()
    live_audio_monitor.start()

    try:
        # Start the backend service
        backend.start()
        time.sleep(1) # Give threads time to initialize

        # 1. Get available devices
        print("\nRequesting device list...")
        backend.command_queue.put({'type': 'get_devices'})
        time.sleep(1) # Allow time for response

        # Use the actual device list if needed, here we just use index 0 or specified
        devices = backend.get_available_devices() # Get directly for test simplicity
        if not devices:
             print("\nNo input devices found. Exiting test.")
             backend.stop()
             exit()

        if MONITOR_DEVICE_INDEX is None:
            monitor_device_id = devices[0]['index']
            print(f"\nUsing first available device: ID {monitor_device_id}, Name: {devices[0]['name']}")
        else:
            monitor_device_id = MONITOR_DEVICE_INDEX
            print(f"\nUsing specified device ID: {monitor_device_id}")

        monitor_channel_id = MONITOR_CHANNEL_INDEX
        print(f"Monitoring channel index: {monitor_channel_id}")

        # 2. Start monitoring the selected device/channel
        print(f"\nSending command to start monitoring device {monitor_device_id}, channel {monitor_channel_id}...")
        backend.command_queue.put({
            'type': 'start_monitoring',
            'device_id': monitor_device_id,
            'channel_index': monitor_channel_id
        })
        time.sleep(1) # Allow time for stream to start

        # 3. Simulate requesting live audio playback
        print(f"\nSending command to start live audio stream for device {monitor_device_id}, channel {monitor_channel_id}...")
        backend.command_queue.put({
            'type': 'start_live_audio',
            'device_id': monitor_device_id,
            'channel_index': monitor_channel_id
        })

        # 4. Run for a duration, monitoring queue outputs via threads
        print(f"\nRunning test for {TEST_DURATION_SECONDS} seconds (monitor console for queue outputs)...")
        time.sleep(TEST_DURATION_SECONDS)

        # 5. Stop live audio stream
        print(f"\nSending command to stop live audio stream for device {monitor_device_id}, channel {monitor_channel_id}...")
        backend.command_queue.put({
            'type': 'stop_live_audio',
            'device_id': monitor_device_id,
            'channel_index': monitor_channel_id
        })
        time.sleep(0.5)

        # 6. Request audio buffer segment
        print(f"\nSending command to get last {REQUEST_BUFFER_SECONDS}s buffer for device {monitor_device_id}, channel {monitor_channel_id}...")
        backend.command_queue.put({
            'type': 'get_buffer',
            'device_id': monitor_device_id,
            'channel_index': monitor_channel_id,
            'seconds': REQUEST_BUFFER_SECONDS
        })
        time.sleep(1) # Allow time for response

        # 7. Stop monitoring
        print(f"\nSending command to stop monitoring device {monitor_device_id}, channel {monitor_channel_id}...")
        backend.command_queue.put({
            'type': 'stop_monitoring',
            'device_id': monitor_device_id,
            'channel_index': monitor_channel_id
        })
        time.sleep(1)

    except KeyboardInterrupt:
        print("\nKeyboard interrupt received.")
    finally:
        # 8. Stop the backend service
        print("\nStopping backend service...")
        backend.stop()

        # Signal queue monitors to stop and wait for them
        print("\nStopping queue monitors...")
        stop_event.set()
        # Put sentinel values to ensure monitors wake up if blocked on get()
        backend.feature_queue.put(None)
        backend.live_audio_queue.put(None)
        feature_monitor.join(timeout=2)
        live_audio_monitor.join(timeout=2)

        print("\n--- Backend Test Finished --- ")
