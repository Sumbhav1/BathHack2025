import React, { useState, useEffect } from "react";
import { io } from "socket.io-client";
import DeviceSelector from "./components/DeviceSelector";
import ChannelSelector from "./components/ChannelSelector";
import "./styles/App.css";

const App = () => {
  const [audioDevices, setAudioDevices] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [selectedChannel, setSelectedChannel] = useState(null);
  const [activeDevices, setActiveDevices] = useState([]);

  // Connect to websocket server
  useEffect(() => {
    const socket = io("http://localhost:5000");

    // Listen for warnings
    socket.on("warning", (data) => {
      const sourceId = data.source;
      
      // Update device warning states
      setActiveDevices(prevDevices => 
        prevDevices.map(device => {
          if (device.device.index.toString() === sourceId) {
            // Set warning and create timeout to clear it
            device.warningTimeout && clearTimeout(device.warningTimeout);
            const timeoutId = setTimeout(() => {
              setActiveDevices(devices => 
                devices.map(d => 
                  d.id === device.id ? { ...d, hasWarning: false } : d
                )
              );
            }, 5000);
            
            return { ...device, hasWarning: true, warningTimeout: timeoutId };
          }
          return device;
        })
      );
    });

    return () => socket.disconnect();
  }, []);

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
      const newDevice = {
        id: Date.now(),
        device: selectedDevice,
        channel: selectedChannel,
        isPlaying: false,
        stream: null,
        source: null,
        gainNode: null,
        hasWarning: false,
        warningTimeout: null
      };
      setActiveDevices([...activeDevices, newDevice]);
      setSelectedDevice(null);
      setSelectedChannel(null);
    }
  };

  const handlePlayPause = async (deviceId) => {
    const deviceIndex = activeDevices.findIndex(d => d.id === deviceId);
    if (deviceIndex === -1) return;

    const device = activeDevices[deviceIndex];

    if (device.isPlaying) {
      // Stop the stream
      if (device.stream) {
        device.stream.getTracks().forEach(track => track.stop());
      }
      if (device.source) {
        device.source.disconnect();
      }
      if (device.channelIsolator) {
        device.channelIsolator.disconnect();
      }
      if (device.gainNode) {
        device.gainNode.disconnect();
      }

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
      try {
        // Resume audio context if it's suspended
        if (audioContext.state === 'suspended') {
          await audioContext.resume();
        }

        // Start new stream with high quality settings
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            deviceId: { exact: device.device.deviceId },
            channelCount: 2, // Request stereo input
            autoGainControl: false,
            echoCancellation: false,
            noiseSuppression: false,
            latency: { ideal: 0 },
            sampleRate: { ideal: 48000 },
            sampleSize: { ideal: 24 }
          }
        });

        const source = audioContext.createMediaStreamSource(stream);
        const channelIsolator = new AudioWorkletNode(audioContext, 'channel-isolator', {
          processorOptions: {
            targetChannel: device.channel
          }
        });
        const gainNode = audioContext.createGain();
        
        gainNode.gain.value = 1;

        // Connect the nodes
        source.connect(channelIsolator);
        channelIsolator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        setActiveDevices(devices => devices.map(d =>
          d.id === deviceId ? {
            ...d,
            isPlaying: true,
            stream: stream,
            source: source,
            channelIsolator: channelIsolator,
            gainNode: gainNode
          } : d
        ));
      } catch (error) {
        console.error("Error accessing microphone:", error);
      }
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
          <button
            key={device.id}
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
        ))}
      </div>
    </div>
  );
};

export default App;
