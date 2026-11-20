/* AudioWorklet: fixed bounded blocks; no networking or task interpretation. */
class BotRealtimeCapture extends AudioWorkletProcessor {
 constructor(){super();this.buffer=new Float32Array(2048);this.used=0;}
 process(inputs){const input=inputs[0]?.[0];if(input)for(const value of input){this.buffer[this.used++]=value;if(this.used===this.buffer.length){this.port.postMessage(this.buffer,[this.buffer.buffer]);this.buffer=new Float32Array(2048);this.used=0;}}return true;}
}
registerProcessor('bot-realtime-capture',BotRealtimeCapture);
