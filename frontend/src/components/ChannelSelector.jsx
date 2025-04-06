import React from 'react';
import '../styles/DeviceSelector.css'; // We can reuse the same styles

const ChannelSelector = ({ channels, onChannelSelect, selectedChannel }) => {
  return (
    <div className="device-selector">
      <label htmlFor="channel-select">Select Channel</label>
      <select
        id="channel-select"
        value={selectedChannel !== null ? selectedChannel : ""}
        onChange={onChannelSelect}
      >
        <option value="">-- Choose a channel --</option>
        {Array.from({ length: Number(channels) }, (_, i) => (
          <option key={i} value={i}>
            Channel {i + 1}
          </option>
        ))}
      </select>
    </div>
  );
};

export default ChannelSelector;