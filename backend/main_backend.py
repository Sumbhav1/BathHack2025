
import time
import threading
from queue import Queue, Empty, Full # Use Empty for non-blocking gets

# Import components from other modules
from audio_handler import AudioCapture, list_audio_devices
from ml_interface import buffer_and_analyze_audio, RATE # Import RATE from ml_interface if needed

# --- Configuration ---
# Define the audio sources to capture (device_index, target_channel)
# Replace with dynamic selection logic later if needed
TARGET_SOURCES = [
    (1, 0), # Example: Device 1, Channel 0 - ADJUST THIS TO YOUR SYSTEM
    # Add more sources as needed, e.g.:
    # (1, 1), # Device 1, Channel 1
    # (3, 0), # Device 3, Channel 0
]
# ---------------------

def main():
    """
    Main function to set up and run multiple audio capture and ML processing pipelines.
    """
    print("--- Backend System Starting ---")

    # 1. List Audio Devices (for reference)
    available_devices = list_audio_devices()
    if not available_devices:
        print("Error: No input audio devices found. Exiting.")
        return
    print("\nAvailable Audio Input Devices:")
    for device in available_devices:
        print(f"  Index {device['index']}: {device['name']} (Channels: {device['channels']})")

    # Validate configured sources
    valid_sources = []
    print("\nConfigured Target Sources:")
    for dev_idx, chan_idx in TARGET_SOURCES:
        device_info = next((d for d in available_devices if d['index'] == dev_idx), None)
        if not device_info:
            print(f"  - WARNING: Device index {dev_idx} not found. Skipping source ({dev_idx}, {chan_idx}).")
            continue
        max_channels = device_info['channels']
        if not 0 <= chan_idx < max_channels:
            print(f"  - WARNING: Channel index {chan_idx} is invalid for device {dev_idx} (max: {max_channels-1}). Skipping source ({dev_idx}, {chan_idx}).")
            continue
        print(f"  - Valid source: Device {dev_idx} ('{device_info['name']}'), Channel {chan_idx}")
        valid_sources.append((dev_idx, chan_idx))

    if not valid_sources:
        print("\nError: No valid audio sources configured or found. Exiting.")
        return

    # 2. Create Shared Resources
    print("\nCreating shared warning queue and stop event...")
    warning_queue = Queue(maxsize=200) # Shared queue for warnings from all ML threads
    stop_event = threading.Event() # Shared signal for graceful shutdown

    # 3. Setup Resources and Threads for Each Source
    audio_captures = {} # Store AudioCapture instances {source_id: instance}
    audio_threads = {} # Store audio capture threads {source_id: thread}
    ml_queues = {} # Store ML input queues {source_id: queue}
    ml_threads = {} # Store ML processing threads {source_id: thread}

    print("Initializing resources for each source...")
    for dev_idx, chan_idx in valid_sources:
        source_id = (dev_idx, chan_idx) # Use tuple as identifier
        print(f"  Setting up for source: {source_id}")

        # Create dedicated ML queue for this source
        ml_queues[source_id] = Queue(maxsize=500)

        # Setup Audio Capture for this source
        audio_captures[source_id] = AudioCapture(
            device_index=dev_idx,
            target_channel=chan_idx,
            output_queues={'ml': ml_queues[source_id]}, # Send only to its ML queue
            stop_event=stop_event # Use the shared stop event
        )
        audio_threads[source_id] = threading.Thread(
            target=audio_captures[source_id].run,
            daemon=True,
            name=f"Audio_Capture_{source_id}"
        )

        # Setup ML Interface Thread for this source
        ml_threads[source_id] = threading.Thread(
            target=buffer_and_analyze_audio,
            args=(source_id, ml_queues[source_id], None, warning_queue), # Pass source_id, its queue, shared warning queue
            daemon=True,
            name=f"ML_Interface_{source_id}"
        )

    # 4. Start All Threads
    print("\nStarting all threads...")
    all_threads_started = True

    # Start Audio Threads first
    for source_id, thread in audio_threads.items():
        print(f"  Starting Audio Capture for {source_id}...")
        thread.start()

    # Brief pause and check if audio streams started
    time.sleep(1.5) # Allow slightly more time for multiple streams
    for source_id, capture in audio_captures.items():
        audio_thread = audio_threads[source_id]
        if not audio_thread.is_alive() or capture._stream is None or not capture._stream.is_active():
             print(f"  ERROR: Audio capture failed to start properly for source {source_id}. Exiting.")
             # Signal stop to any potentially started threads before exiting
             stop_event.set()
             for q in ml_queues.values():
                 q.put(None) # Signal ML threads too
             all_threads_started = False
             break # Stop starting more threads

    # Start ML Threads only if all audio started okay
    if all_threads_started:
        for source_id, thread in ml_threads.items():
            print(f"  Starting ML Interface for {source_id}...")
            thread.start()
    else:
        # Wait for any partially started threads to potentially stop
        print("Waiting briefly for failed startup cleanup...")
        time.sleep(2)
        print("Exiting due to startup failure.")
        return # Exit if any audio capture failed

    # 5. Main Loop (Keep running, check for warnings, wait for Ctrl+C)
    print("\n--- System Running ---")
    print("Monitoring sources:", list(audio_threads.keys()))
    print("Press Ctrl+C to stop.")
    try:
        while True:
            # Check for warnings from the ML process
            try:
                source_id, warning = warning_queue.get_nowait() # Non-blocking check, expect tuple
                print(f"** WARNING DETECTED [Source: {source_id}]: {warning} **")
            except Empty:
                pass # No warning waiting
            except (TypeError, ValueError):
                 # Handle cases where item in queue is not the expected tuple
                 try:
                     raw_item = warning_queue.get_nowait() # Consume the unexpected item
                     print(f"** WARNING QUEUE: Received unexpected item: {raw_item} **")
                 except Empty:
                     pass # Item was already gone

            # Check if threads are still alive (optional health check)
            all_alive = True
            active_audio_threads = {sid: t for sid, t in audio_threads.items() if t.is_alive()}
            active_ml_threads = {sid: t for sid, t in ml_threads.items() if t.is_alive()}

            if len(active_audio_threads) < len(audio_threads):
                stopped_sources = set(audio_threads.keys()) - set(active_audio_threads.keys())
                print(f"Error: Audio capture thread(s) for {stopped_sources} stopped unexpectedly.")
                all_alive = False

            if len(active_ml_threads) < len(ml_threads):
                stopped_sources = set(ml_threads.keys()) - set(active_ml_threads.keys())
                print(f"Error: ML interface thread(s) for {stopped_sources} stopped unexpectedly.")
                all_alive = False

            if not all_alive:
                print("A thread stopped unexpectedly. Initiating shutdown.")
                break # Exit main loop to trigger shutdown

            time.sleep(0.2) # Reduce CPU usage

    except KeyboardInterrupt:
        print("\nCtrl+C detected. Initiating shutdown...")
    except Exception as e:
        print(f"\nAn unexpected error occurred in the main loop: {e}")
    finally:
        # 6. Shutdown Sequence
        print("\nStopping threads...")

        # Signal ALL AudioCapture instances to stop via the shared event
        if not stop_event.is_set():
             print("Signalling audio captures to stop...")
             stop_event.set()

        # Signal ALL ML Interface threads to stop by sending None to their queues
        print("Signalling ML interfaces to stop...")
        for source_id, queue in ml_queues.items():
             # Check if the corresponding ML thread exists and is alive before signalling
             if source_id in ml_threads and ml_threads[source_id].is_alive():
                 print(f"  Signalling ML for {source_id}...")
                 try:
                     queue.put(None, block=False) # Sentinel value, non-blocking
                 except Full:
                     print(f"  Warning: ML queue for {source_id} was full when trying to signal stop.")

        # Wait for threads to finish
        print("Waiting for audio capture threads to join...")
        for source_id, thread in audio_threads.items():
            if thread.is_alive():
                print(f"  Waiting for audio {source_id}...")
                thread.join(timeout=5.0)
                if thread.is_alive():
                    print(f"  Warning: Audio capture thread {source_id} did not stop gracefully.")
                    # Force stop if needed (might already be handled by run->stop)
                    if source_id in audio_captures:
                        audio_captures[source_id].stop() # Attempt explicit stop

        print("Waiting for ML interface threads to join...")
        for source_id, thread in ml_threads.items():
             if thread.is_alive():
                print(f"  Waiting for ML {source_id}...")
                thread.join(timeout=10.0) # Allow more time if processing remaining buffer
                if thread.is_alive():
                    print(f"  Warning: ML interface thread {source_id} did not stop gracefully.")

        print("--- Backend System Stopped ---")

if __name__ == "__main__":
    # Example: Define sources to monitor here or load from config
    # Make sure the device indices are correct for your system!
    # You can run list_audio_devices() separately first to check.
    # TARGET_SOURCES = [(1, 0)] # Example: Device 1, Channel 0
    # TARGET_SOURCES = [(1, 0), (1, 1)] # Example: Device 1, Channels 0 and 1
    # TARGET_SOURCES = [(1, 0), (3, 0)] # Example: Device 1 Ch 0, and Device 3 Ch 0

    # Check if TARGET_SOURCES is defined, provide default if not
    if 'TARGET_SOURCES' not in globals() or not TARGET_SOURCES:
        print("Warning: TARGET_SOURCES not defined or empty in main_backend.py.")
        print("Please edit the script to define the sources you want to monitor.")
        # Example default - adjust this to a likely valid device on your system
        # Find the first available device index
        devices = list_audio_devices()
        default_device_index = devices[0]['index'] if devices else 0
        TARGET_SOURCES = [(default_device_index, 0)] # Defaulting to first device, channel 0
        print(f"Using default source: {TARGET_SOURCES}")

    main()
