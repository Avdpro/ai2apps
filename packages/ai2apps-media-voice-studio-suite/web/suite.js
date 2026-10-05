(function () {
  'use strict';
  const locale = String(new URLSearchParams(location.search).get('locale') || navigator.language || 'en').toLowerCase().startsWith('zh') ? 'zh-CN' : 'en';
  const zh = {
    hero: '把对白、角色与字幕<br>变成可编辑的创作流程',
    lede: '一个 Package，六个独立 Mini-App。安装后会按 placement 分别出现在语音工坊与视频工坊中。',
    state: '六个 Mini-App 已接入可信 Host Capability Broker',
    transcriptionName: '详细转写', transcriptionDescription: '逐字时间戳、说话人解析与人工角色命名。',
    separationName: '人声 / 背景分离', separationDescription: '输出人声、背景或四轨音乐 stem。',
    audioVoiceName: '录音角色换声', audioVoiceDescription: '只替换选中角色，保留其余声音和时间线。',
    subtitlesName: '视频字幕与翻译', subtitlesDescription: '导出字幕文件，或直接生成烧录字幕的视频。',
    videoVoiceName: '视频角色换声', videoVoiceDescription: '识别角色、转换对白、同步混音并重新封装。',
    translationName: '视频音轨翻译', translationDescription: '翻译单人旁白，用选定角色配音并保留背景声。'
  };
  document.documentElement.lang = locale;
  if (locale === 'zh-CN') {
    document.title = '音视频语音工作室套件';
    document.querySelectorAll('[data-i18n]').forEach(element => {
      const value = zh[element.dataset.i18n];
      if (value == null) return;
      if (element.dataset.i18n === 'hero') element.innerHTML = value;
      else element.textContent = value;
    });
  }
  window.parent.postMessage({
    type: 'ai2apps:mini-app-suite-ready',
    packageId: 'ai2apps/media-voice-studio-suite',
    version: '0.1.1'
  }, '*');
})();
