/* Host-owned input recording; recordings never enter generated output history. */
(() => {
  'use strict';
  class StudioAudioRecorder {
    constructor() {
      this.disposed = false; this.pending = false; this.recorder = null; this.stream = null; this.result = null;
      this.onPageHide = () => this.dispose();
      window.addEventListener('pagehide', this.onPageHide);
    }
    release() { this.stream?.getTracks().forEach(track => track.stop()); this.stream = null; clearTimeout(this.timer); }
    async start(seconds = 60) {
      if (this.disposed || this.pending || this.recorder?.state === 'recording') throw new Error('recording_busy');
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') throw new Error('recording_unavailable');
      this.pending = true; this.result = null;
      try {
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
