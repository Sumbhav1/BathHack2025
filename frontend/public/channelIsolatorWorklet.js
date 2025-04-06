class ChannelIsolatorProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.targetChannel = options.processorOptions.targetChannel;
  }
  
  process(inputs, outputs) {
    const input = inputs[0];
    const output = outputs[0];
    if (!input || !input.length) return true;
    
    // Copy only the target channel's data to all output channels
    const targetChannelData = input[this.targetChannel];
    if (targetChannelData) {
      for (let channel = 0; channel < output.length; channel++) {
        output[channel].set(targetChannelData);
      }
    }
    return true;
  }
}

registerProcessor('channel-isolator', ChannelIsolatorProcessor);