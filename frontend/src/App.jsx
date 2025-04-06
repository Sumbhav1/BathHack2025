import React, { useState, useEffect, useRef } from "react";
import { io } from "socket.io-client";
import DeviceSelector from "./components/DeviceSelector";
import ChannelSelector from "./components/ChannelSelector";
import "./styles/App.css";

const App = () => {
  const [audioDevices, setAudioDevices] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [selectedChannel, setSelectedChannel] = useState(null);
  const [activeDevices, setActiveDevices] = useState([]);
  const [audioContext] = useState(() => new (window.AudioContext || window.webkitAudioContext)());
  const [workletLoaded, setWorkletLoaded] = useState(false);
  const socketRef = useRef(null);

  // Load audio worklet when component mounts
  useEffect(() => {
    const loadWorklet = async () => {
      if (!workletLoaded) {
        try {
          await audioContext.audioWorklet.addModule('/channelIsolatorWorklet.js');
          setWorkletLoaded(true);
          console.log('Channel isolator worklet loaded successfully');
        } catch (error) {
          console.error('Failed to load audio worklet:', error);
        }
      }
    };
    loadWorklet();
  }, [audioContext, workletLoaded]);

  // Fetch audio devices when component mounts
  useEffect(() => {
    const fetchAudioDevices = async () => {
      try {
        const response = await fetch("http://localhost:5000/api/audio-devices");
        if (!response.ok) {
          throw new Error('Failed to fetch audio devices');
        }
        const devices = await response.json();
        setAudioDevices(devices);
      } catch (error) {
        console.error("Error fetching audio devices:", error);
      }
    };

    fetchAudioDevices();
  }, []);

  // Connect to websocket server
  useEffect(() => {
    const socket = io("http://localhost:5000");
    socketRef.current = socket;

    socket.on("connect", () => {
      console.log("Connected to server");
    });

    socket.on("disconnect", () => {
      console.log("Disconnected from server");
    });

    // --- MODIFIED WARNING HANDLER ---
    socket.on("warning", (data) => {
      console.log("Received warning:", data);
      const { deviceIndex, channel, message } = data; // Destructure new payload

      // Ensure we have the necessary data
      if (deviceIndex === undefined || channel === undefined) {
        console.error("Warning data missing deviceIndex or channel:", data);
        return;
      }

      setActiveDevices(prevDevices => {
        let warningSet = false; // Flag to check if we found the device
        const updatedDevices = prevDevices.map(device => {
          // Match based on both device index and channel
          if (device.device.index.toString() === deviceIndex && device.channel === channel) {
            console.log(`Match found! Setting warning for device ID: ${device.id} (Index: ${deviceIndex}, Channel: ${channel})`);
            warningSet = true;
            // Clear any existing timeout before setting a new one
            if (device.warningTimeout) {
              clearTimeout(device.warningTimeout);
            }
            // Set a timeout to clear this specific warning after 5 seconds
            const timeoutId = setTimeout(() => {
              console.log(`Clearing warning for device ID: ${device.id}`);
              setActiveDevices(currentDevices =>
                currentDevices.map(d =>
                  d.id === device.id ? { ...d, hasWarning: false, warningTimeout: null } : d
                )
              );
            }, 5000); // 5 seconds
            return { ...device, hasWarning: true, warningTimeout: timeoutId };
          }
          return device; // Return unchanged device if no match
        });

        if (!warningSet) {
          console.log(`Warning received for inactive/unknown device (Index: ${deviceIndex}, Channel: ${channel})`);
        }
        return updatedDevices; // Return the potentially updated list
      });
    });
    // --- END MODIFIED WARNING HANDLER ---

    return () => {
      // Clean up any monitored devices when component unmounts
      activeDevices.forEach(device => {
        // Clear any pending warning timeouts
        if (device.warningTimeout) {
          clearTimeout(device.warningTimeout);
        }
        // Stop backend monitoring
        socket.emit('stop_audio', {
          deviceId: device.id,
          // Ensure deviceIndex and channel are sent if needed by backend on stop
          // deviceIndex: device.device.index,
          // channel: device.channel
        });
      });
      socket.disconnect();
    };
  }, [activeDevices]); // Add activeDevices as dependency to ensure cleanup uses the latest list

  const handleDeviceSelect = (event) => {
    const deviceIndex = parseInt(event.target.value, 10);
    const selected = audioDevices.find(
      (device) => device.index === deviceIndex
    );
    setSelectedDevice(selected);
    setSelectedChannel(null);
  };

  const handleChannelSelect = (event) => {
    const channelIndex = parseInt(event.target.value, 10);
    setSelectedChannel(channelIndex);
  };

  const handleAddDevice = () => {
    if (selectedDevice && selectedChannel !== null) {
      const deviceId = Date.now().toString();
      const newDevice = {
        id: deviceId,
        device: selectedDevice,
        channel: selectedChannel,
        isPlaying: false,
        stream: null,
        source: null,
        gainNode: null,
        hasWarning: false,
        warningTimeout: null
      };

      // Start backend monitoring immediately
      socketRef.current.emit('start_audio', {
        deviceId: deviceId,
        deviceIndex: selectedDevice.index,
        channel: selectedChannel
      });

      // Add device to frontend state
      setActiveDevices(prev => [...prev, newDevice]);
      setSelectedDevice(null);
      setSelectedChannel(null);
    }
  };

  const handlePlayPause = async (deviceId) => {
    const deviceIndex = activeDevices.findIndex(d => d.id === deviceId);
    if (deviceIndex === -1) return;

    const device = activeDevices[deviceIndex];

    if (device.isPlaying) {
      // Only stop frontend audio playback
      device.stream?.getTracks().forEach(track => track.stop());
      device.source?.disconnect();
      device.channelIsolator?.disconnect();
      device.gainNode?.disconnect();

      setActiveDevices(devices => devices.map(d =>
        d.id === deviceId ? {
          ...d,
          isPlaying: false,
          stream: null,
          source: null,
          channelIsolator: null,
          gainNode: null
        } : d
      ));
    } else {
      if (!workletLoaded) {
        console.error('Audio worklet not loaded yet');
        return;
      }

      try {
        // Resume audio context if suspended
        if (audioContext.state === 'suspended') {
          await audioContext.resume();
        }

        // Get audio input stream
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            deviceId: { exact: device.device.deviceId },
            channelCount: { ideal: device.device.channels },
            autoGainControl: false,
            echoCancellation: false,
            noiseSuppression: false
          }
        });

        // Create audio nodes
        const source = audioContext.createMediaStreamSource(stream);
        const channelIsolator = new AudioWorkletNode(audioContext, 'channel-isolator', {
          processorOptions: {
            targetChannel: device.channel
          }
        });
        const gainNode = audioContext.createGain();
        gainNode.gain.value = 1;

        // Connect nodes
        source.connect(channelIsolator);
        channelIsolator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        // Update state
        setActiveDevices(devices => devices.map(d =>
          d.id === deviceId ? {
            ...d,
            isPlaying: true,
            stream,
            source,
            channelIsolator,
            gainNode
          } : d
        ));
      } catch (error) {
        console.error('Error starting audio capture:', error);
      }
    }
  };

  const handleRemoveDevice = (deviceId) => {
    const device = activeDevices.find(d => d.id === deviceId);
    if (device) {
      // Stop any playback
      if (device.isPlaying) {
        device.stream?.getTracks().forEach(track => track.stop());
        device.source?.disconnect();
        device.channelIsolator?.disconnect();
        device.gainNode?.disconnect();
      }

      // Stop backend monitoring
      socketRef.current.emit('stop_audio', {
        deviceId: device.id,
        deviceIndex: device.device.index,
        channel: device.channel
      });

      // Remove from state
      setActiveDevices(devices => devices.filter(d => d.id !== deviceId));
    }
  };

  return (
    <div className="app">
      <h1>Audio Device Hub</h1>

      <div className="device-selection">
        <DeviceSelector
          devices={audioDevices}
          selectedDevice={selectedDevice}
          onDeviceSelect={handleDeviceSelect}
        />
        {selectedDevice && (
          <ChannelSelector
            channels={selectedDevice.channels}
            selectedChannel={selectedChannel}
            onChannelSelect={handleChannelSelect}
          />
        )}
        {selectedDevice && selectedChannel !== null && (
          <button className="add-device-button" onClick={handleAddDevice}>
            Add Device
          </button>
        )}
      </div>

      <div className="device-info-container">
        {activeDevices.map((device) => (
          <div key={device.id} className="device-button-container">
            <button
              className={`device-info-button ${device.hasWarning ? 'warning' : ''}`}
              onClick={() => handlePlayPause(device.id)}
            >
              {device.device.name}
              <br />
              Channel {device.channel + 1}
              <br />
              <br />
              {device.isPlaying ? "Stop" : "Play"}
            </button>
            <button 
              className="remove-device-button"
              onClick={() => handleRemoveDevice(device.id)}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

export default App;
