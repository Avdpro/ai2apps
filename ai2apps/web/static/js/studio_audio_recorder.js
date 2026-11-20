/* Host-owned input recording; recordings never enter generated output history. */
(() => {
  'use strict';
  // Shared by single recordings and continuous speech; no media is acquired
  // until this exclusive, same-origin lock has been granted.
  let microphoneOwner = false;
  function acquireMicrophone() {
    if (microphoneOwner) throw new Error('microphone_busy');
    microphoneOwner = true;
    let released = false, unlock = null, finished = Promise.resolve();
    const release = () => { if (!released) { released = true; microphoneOwner = false; unlock?.(); } return finished.catch(()=>{}); };
    if (!navigator.locks?.request) return release;
    return new Promise((resolve, reject) => {
          finished = navigator.locks.request('ai2apps-microphone', {ifAvailable:true}, lock => {
            if (!lock) { reject(new Error('microphone_busy')); return; }
            return new Promise(done => { unlock = done; resolve(); });
          });finished.catch(reject);
        }).then(() => release, error => { release(); throw error; });
  }
  window.AI2AppsMicrophoneLease = {acquire:acquireMicrophone};
  class StudioAudioRecorder {
    constructor() {
      this.disposed = false; this.pending = false; this.recorder = null; this.stream = null; this.result = null;
      this.onPageHide = () => this.dispose();
      window.addEventListener('pagehide', this.onPageHide);
    }
    release() { this.stream?.getTracks().forEach(track => track.stop()); this.stream = null; clearTimeout(this.timer); if (this.unlock) this.releaseDone=this.unlock(); this.unlock = null; }
    async start(seconds = 60) {
      if (this.disposed || this.pending || this.recorder?.state === 'recording') throw new Error('recording_busy');
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') throw new Error('recording_unavailable');
      this.pending = true; this.result = null;
      try {
        const lease = acquireMicrophone();
        this.unlock = typeof lease === 'function' ? lease : await lease;
        if (this.disposed) throw new Error('recording_cancelled');
        const stream = await navigator.mediaDevices.getUserMedia({audio:true});
        if (this.disposed) { stream.getTracks().forEach(track => track.stop()); throw new Error('recording_cancelled'); }
        this.stream = stream;
        const type = ['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(t => MediaRecorder.isTypeSupported(t));
        const recorder = new MediaRecorder(stream, type ? {mimeType:type} : undefined);
        this.recorder = recorder;
        const chunks = []; let size = 0, failure = null;
        this.result = new Promise(resolve => {
          recorder.ondataavailable = event => {
            if (!event.data.size) return;
            size += event.data.size;
            if (size > 100 * 1024 * 1024) { failure = 'recording_too_large'; if (recorder.state === 'recording') recorder.stop(); }
            else chunks.push(event.data);
          };
          recorder.onerror = () => { failure = 'recording_failed'; this.release(); resolve({error:failure}); };
          recorder.onstop = () => {
            this.release();
            const body = new Blob(chunks, {type:recorder.mimeType || type || 'audio/webm'});
            const ext = body.type.includes('ogg') ? 'ogg' : body.type.includes('mp4') ? 'm4a' : 'webm';
            resolve(failure || !body.size ? {error:failure || 'recording_empty'} : {body,name:`recording-${Date.now()}.${ext}`});
          };
        });
        recorder.start(250);
        const maxSeconds = Math.min(600, Math.max(0.2, Number(seconds) || 60));
        this.timer = setTimeout(() => { if (recorder.state === 'recording') recorder.stop(); }, maxSeconds * 1000);
        return {maxSeconds};
      } catch (error) {
        this.release();
        throw new Error(error.name === 'NotAllowedError' ? 'recording_permission_denied' : error.name === 'NotFoundError' ? 'recording_no_device' : error.message || 'recording_failed');
      } finally { this.pending = false; }
    }
    async stop() {
      if (!this.result) throw new Error('recording_empty');
      if (this.recorder?.state === 'recording') this.recorder.stop();
      const result = await this.result;
      await this.releaseDone;
      if (result.error) throw new Error(result.error);
      return result;
    }
    dispose() {
      this.disposed = true;
      window.removeEventListener('pagehide', this.onPageHide);
      if (this.recorder?.state === 'recording') this.recorder.stop();
      this.release();
    }
  }
  window.AI2AppsStudioAudioRecorder = StudioAudioRecorder;
})();
