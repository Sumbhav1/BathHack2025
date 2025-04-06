// components/DeviceBox.jsx
import React, { useState } from 'react';
import '../styles/DeviceBox.css'; // Import the CSS file for styling

const DeviceBox = ({ device }) => {
  const [isPlaying, setIsPlaying] = useState(false);

  const handlePlayPause = () => {
    setIsPlaying((prev) => !prev);
    // Call API to start/stop playback if necessary, or control the audio stream
  };

  return (
    <div className="device-box">
      <div className="device-info">
        <h3>{device.name}</h3>
        <img
          src={`icon-${device.index}.png`}
          alt={`${device.name} icon`}
          className="device-icon"
        />
      </div>
      <button className="play-button" onClick={handlePlayPause}>
        {isPlaying ? 'Pause' : 'Play'}
      </button>
    </div>
  );
};

export default DeviceBox;
