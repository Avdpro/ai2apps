(function () {
  'use strict';
  window.parent.postMessage({
    type: 'ai2apps:mini-app-suite-ready',
    packageId: 'ai2apps/media-voice-studio-suite',
    version: '0.1.1'
  }, '*');
})();
