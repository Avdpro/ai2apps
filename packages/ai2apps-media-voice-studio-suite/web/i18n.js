(function () {
  'use strict';

  const EN = {
    '音频智能': 'Audio intelligence',
    '音频处理': 'Audio processing',
    '声音转换': 'Voice conversion',
    '视频本地化': 'Video localization',
    '视频配音': 'Video dubbing',
    '视频声音转换': 'Video voice conversion',
    '步骤 01': 'Step 01',
    '步骤 02': 'Step 02',
    '步骤 03': 'Step 03',
    '步骤 04': 'Step 04',
    '结果': 'Result',
    '生成录音文本记录': 'Create a detailed transcript',
    '识别逐字时间戳和说话人，完成后可把匿名角色改成真实姓名，并导出结构化记录或字幕。': 'Detect word-level timestamps and speakers, assign names to anonymous speakers, and export a structured transcript or subtitles.',
    '录音或视频': 'Audio or video',
    '解析媒体': 'Analyze media',
    '语音识别': 'Transcribe speech',
    '角色分离': 'Separate speakers',
    '人工命名': 'Name speakers',
    '导出': 'Export',
    '开始本地转写': 'Start local transcription',
    '模型配置': 'Model profile',
    'Compact · 速度优先': 'Compact · Faster',
    'Quality · 质量优先': 'Quality · Higher quality',
    '音频语言': 'Audio language',
    '自动检测': 'Auto-detect',
    '中文': 'Chinese',
    '粤语': 'Cantonese',
    '主要输出': 'Primary output',
    '逐字记录 + JSON': 'Detailed transcript + JSON',
    '可读 Markdown': 'Readable Markdown',
    'SRT 字幕': 'SRT subtitles',
    '保留逐字时间戳': 'Keep word-level timestamps',
    '分离人声和背景音': 'Separate voice and background audio',
    '从音频中拆出独立人声与背景轨，并保持原始时间线，方便后续换声、混音或字幕制作。': 'Separate voice and background tracks while preserving the original timeline for voice conversion, mixing, or subtitle work.',
    '音频或含音轨的视频': 'Audio or video with an audio track',
    '分离音轨': 'Separate tracks',
    '响度检查': 'Check loudness',
    '开始本地分离': 'Start local separation',
    '输出拓扑': 'Output layout',
    '人声 / 伴奏': 'Vocals / instrumental',
    '对白 / 背景': 'Dialogue / background',
    '鼓 / 贝斯 / 其他 / 人声': 'Drums / bass / other / vocals',
    '替换录音中的某个角色声音': 'Replace one speaker in an audio recording',
    '识别目标说话人的片段，只转换该角色的音色，并将其他人声与背景轨按原时间线混回。': 'Find the target speaker, convert only that voice, and mix all other voices and background audio back onto the original timeline.',
    '包含多个角色的录音': 'Recording with multiple speakers',
    '识别角色': 'Identify speakers',
    '分离目标片段': 'Isolate target segments',
    '音色转换': 'Convert voice',
    '混合与校验': 'Mix and verify',
    '先识别录音角色': 'Identify recording speakers',
    '要替换的角色': 'Speaker to replace',
    '目标声音名称': 'Target voice name',
    '例如：旁白角色 A': 'For example: Narrator A',
    '换声质量': 'Voice conversion quality',
    '音色 · 快速': 'Timbre · Fast',
    '音色 · 高质量': 'Timbre · High quality',
    '声音 · 高质量': 'Voice · High quality',
    '我确认拥有使用目标声音和处理源录音的权利': 'I confirm that I have the rights to use the target voice and process the source recording',
    '生成、翻译与添加视频字幕': 'Create, translate, and add video subtitles',
    '从视频对白生成带时间轴的字幕，可翻译为另一种语言，导出字幕文件或直接烧录到视频。': 'Create timed subtitles from video dialogue, translate them, export subtitle files, or burn them into the video.',
    '需要制作字幕的视频': 'Video to subtitle',
    '提取音轨': 'Extract audio',
    '生成字幕': 'Create subtitles',
    '翻译与校对': 'Translate and review',
    '排版': 'Style subtitles',
    '提取字幕段落': 'Extract subtitle segments',
    '原始语言': 'Source language',
    '翻译': 'Translation',
    '不翻译': 'Do not translate',
    '翻译为中文': 'Translate to Chinese',
    '字幕文件': 'Subtitle file',
    '字体大小': 'Font size',
    '小': 'Small',
    '标准': 'Standard',
    '大 · 推荐': 'Large · Recommended',
    '特大': 'Extra large',
    '背景样式': 'Background style',
    '白字 + 黑色粗描边': 'White text + thick black outline',
    '白字 + 半透明黑框': 'White text + translucent black box',
    '翻译时保留双语字幕': 'Keep bilingual subtitles when translating',
    '字幕中显示角色名': 'Show speaker names in subtitles',
    '翻译视频音轨': 'Translate a video audio track',
    '面向单讲解者视频：翻译原始旁白，可选 Voice Studio Character 或临时克隆原始音色重新配音，并保留音乐与环境背景。': 'For single-narrator videos: translate the narration, dub with a Voice Studio Character or a temporary clone of the original voice, and preserve music and ambience.',
    '单讲解者或旁白视频': 'Single-narrator video',
    '转写旁白': 'Transcribe narration',
    '翻译文本': 'Translate text',
    '生成配音': 'Generate dubbing',
    '保留背景': 'Preserve background',
    '封装视频': 'Mux video',
    '开始翻译并配音': 'Translate and dub',
    '目标语言': 'Target language',
    '配音 Character': 'Dubbing Character',
    '语音克隆模型': 'Voice-cloning model',
    'ASR 回听校验（异常句自动重试）': 'ASR verification (automatically retry problematic lines)',
    '替换视频中的某个角色声音': 'Replace one speaker in a video',
    '从视频中定位一个说话人，转换对应对白音色，再与其他角色、环境声和画面同步合成。': 'Locate one speaker in the video, convert that dialogue, and recombine it with other speakers, ambience, and picture.',
    '包含目标角色的视频': 'Video containing the target speaker',
    '同步混音': 'Synchronize and mix',
    '先识别视频角色': 'Identify video speakers',
    '例如：角色新配音': 'For example: New character voice',
    '我确认拥有使用目标声音和处理源视频的权利': 'I confirm that I have the rights to use the target voice and process the source video',
    '点击选择，或把文件拖到这里': 'Click to choose a file, or drop one here',
    '文件已就绪，可继续配置。': 'The file is ready. Continue with the settings.',
    '删除角色': 'Delete speaker',
    '添加角色': 'Add speaker',
    '此工作流已接入 mount-bound Host Capability Broker。文件只提交给本机已安装的可信模型 Package。': 'This workflow uses the mount-bound Host Capability Broker. Files are sent only to verified model Packages installed on this device.',
    'MVP 已完成 Package、Mini-App UI、工作流配置与草稿导出。此工作流的模型执行仍在接入 Host Capability Broker。': 'The Package, Mini-App UI, workflow settings, and draft export are ready. Model execution is still being connected to the Host Capability Broker.',
    '安装并配置模型': 'Install and configure models',
    '正在安装配置…': 'Installing and configuring…',
    '无法打开安装配置，请重试。': 'Could not open setup. Try again.',
    '选择素材': 'Choose media',
    '目标声音参考（必选）': 'Target voice reference (required)',
    '目标声音参考（可选）': 'Target voice reference (optional)',
    '配置工作流': 'Configure workflow',
    '角色名称': 'Speaker names',
    '模型先产生匿名角色；用户确认后再绑定名字。MVP 可预先配置，执行结果回来后仍可修改。': 'The model first creates anonymous speakers. Assign names after reviewing them; names can be edited again after processing.',
    '处理链路': 'Processing pipeline',
    '尚未保存任务草稿。': 'The task draft has not been saved.',
    '重置': 'Reset',
    '导出 JSON': 'Export JSON',
    '保存任务草稿': 'Save task draft',
    '开始本地处理': 'Start local processing',
    '生成字幕视频': 'Create subtitled video',
    '未分配': 'Unassigned',
    '可选：用 AI 润色 / 修正字幕': 'Optional: refine or correct subtitles with AI',
    '使用系统 Standard tasks 模型。只修正文字，保留时间轴和段落；审阅后确认应用。': 'Uses the system Standard tasks model. Only text is changed; timing and segments are preserved. Review suggestions before applying them.',
    '修正规则 Profile': 'Correction rules profile',
    'Profile 名称': 'Profile name',
    '例如：把 AI to Apps 写作 Ai2Apps；尽量用阿拉伯数字而不是中文数字。': 'For example: write “AI to Apps” as “Ai2Apps”; prefer Arabic numerals.',
    '字幕修正规则': 'Subtitle correction rules',
    '临时规则 / 新建 Profile': 'Temporary rules / New profile',
    '保存 Profile': 'Save profile',
    '删除 Profile': 'Delete profile',
    '生成修正建议': 'Generate correction suggestions',
    '请填写 Profile 名称。': 'Enter a profile name.',
    '修正规则 Profile 已保存。': 'The correction profile was saved.',
    'Profile 已删除，当前规则仍可使用。': 'The profile was deleted. The current rules remain available.',
    '正在生成字幕修正建议，原文暂不修改…': 'Generating subtitle correction suggestions without changing the original…',
    '字幕已变化，请重新生成修正建议。': 'The subtitles changed. Generate correction suggestions again.',
    '修正结果段落数量不一致。': 'The corrected result has a different number of segments.',
    '确认应用修正': 'Apply corrections',
    '放弃建议': 'Discard suggestions',
    '字幕已变化，请重新生成建议。': 'The subtitles changed. Generate suggestions again.',
    '已应用修正并保存草稿，请继续校对或导出。': 'Corrections were applied and the draft was saved. Continue reviewing or export it.',
    '修正建议已生成，请审阅。': 'Correction suggestions are ready for review.',
    '校对字幕段落': 'Review subtitle segments',
    '角色识别结果': 'Speaker identification results',
    '识别结果已修改，请保存草稿或导出。': 'The transcript was changed. Save the draft or export it.',
    '字幕文本已修改。确认后生成字幕文件或视频。': 'Subtitle text was changed. Review it, then create a subtitle file or video.',
    '生成字幕文件': 'Create subtitle file',
    '执行前请重新选择本地素材文件。': 'Select the local media file again before running.',
    '执行前请重新选择本地视频文件。': 'Select the local video file again before running.',
    '执行前请重新选择本地视频。': 'Select the local video again before running.',
    '执行前请重新选择本地录音。': 'Select the local recording again before running.',
    '可信 Mini-App mount 上下文不可用。': 'The trusted Mini-App mount context is unavailable.',
    '正在本机执行详细转写与角色分离…': 'Running detailed transcription and speaker diarization locally…',
    '转写失败': 'Transcription failed',
    '本地转写完成。请检查角色名称和文本后再导出。': 'Local transcription is complete. Review speaker names and text before exporting.',
    '正在本机分离音轨；较长素材需要一些时间…': 'Separating tracks locally. Longer media may take some time…',
    '音轨分离失败': 'Track separation failed',
    '音轨分离完成': 'Track separation complete',
    '下载分离音轨 ZIP': 'Download separated tracks ZIP',
    '无法下载，请重试。': 'Could not download the result. Try again.',
    '本地音轨分离完成。各音轨已加入 Preview & Output，可单独试听或下载。': 'Local track separation is complete. Each track is available in Preview & Output for playback or download.',
    '本地音轨分离完成。请下载保存结果。': 'Local track separation is complete. Download the result to save it.',
    '正在本机提取对白并生成可编辑字幕段落…': 'Extracting dialogue locally and creating editable subtitle segments…',
    '正在使用校对后的文本生成字幕结果…': 'Creating subtitle results from the reviewed text…',
    '字幕生成失败': 'Subtitle generation failed',
    '没有识别到可编辑的字幕段落。': 'No editable subtitle segments were detected.',
    '字幕段落已提取。请逐段检查和修改文本，然后生成字幕文件或视频。': 'Subtitle segments were extracted. Review and edit each segment, then create a subtitle file or video.',
    '视频字幕已生成': 'Video subtitles created',
    '下载字幕结果 ZIP': 'Download subtitle results ZIP',
    '字幕工作流完成。带字幕视频已加入 Video Studio 的 Preview & Output；字幕 ZIP 可在此下载。': 'The subtitle workflow is complete. The subtitled video is in Video Studio Preview & Output, and the subtitle ZIP can be downloaded here.',
    '字幕工作流完成。可以继续修改段落后重新生成，或下载当前字幕 ZIP。': 'The subtitle workflow is complete. You can edit segments and regenerate, or download the current subtitle ZIP.',
    '正在转写和翻译旁白、生成 Character 配音并保留背景声；较长视频需要一些时间…': 'Transcribing and translating narration, generating Character dubbing, and preserving background audio. Longer videos may take some time…',
    '视频音轨翻译失败': 'Video audio translation failed',
    '视频音轨翻译完成': 'Video audio translation complete',
    '视频音轨翻译完成。结果已加入 Video Studio 的 Generation result，可播放、下载或加入 Gallery。': 'Video audio translation is complete. The result is available in Video Studio for playback, download, or adding to Gallery.',
    '下载翻译配音视频': 'Download translated and dubbed video',
    '视频音轨翻译完成。请及时下载结果。': 'Video audio translation is complete. Download the result to save it.',
    '请选择目标声音参考。': 'Choose a target voice reference.',
    '正在识别说话人和时间轴…': 'Identifying speakers and timeline…',
    '角色识别失败': 'Speaker identification failed',
    '角色换声失败': 'Speaker voice replacement failed',
    '开始替换所选角色': 'Replace selected speaker',
    '角色识别完成。请命名角色、选择目标角色和参考声音，然后再次执行。': 'Speaker identification is complete. Name the speakers, select the target speaker and reference voice, then run again.',
    '换声完成。请在 Voice Studio 的 Preview & Output 中播放、下载或拖拽结果。': 'Voice replacement is complete. Play, download, or drag the result from Voice Studio Preview & Output.',
    '角色换声完成': 'Speaker voice replacement complete',
    '下载替换后的视频': 'Download replaced video',
    '下载替换后的音频': 'Download replaced audio',
    '请先选择源素材。': 'Choose source media first.',
    '请选择语音克隆模型。': 'Choose a voice-cloning model.',
    '任务草稿已保存；可以开始本地执行。': 'The task draft was saved. You can start local processing.',
    '已请求 Shell 另存为；导出文件也已加入 Preview & Output。': 'Save As was requested from the Shell. The exported file was also added to Preview & Output.',
    '导出失败': 'Export failed',
    '草稿和输入已重置。': 'The draft and inputs were reset.',
    '已恢复上次草稿和已保存的识别结果。重新执行前需要选择本地素材文件。': 'The previous draft and saved results were restored. Select the local media file again before running.',
    '无法恢复草稿。': 'Could not restore the draft.',
    '逐句回听生成的配音；不合格时最多自动重试两次。': 'Verify generated dubbing line by line with ASR, retrying problematic lines up to two times.',
    '未检测到可用的 Detailed Transcription ASR 模型。': 'No available Detailed Transcription ASR model was detected.',
    '音轨分离能力已就绪。素材只提交给本机已安装并验证的 MLX Demucs Package。': 'Track separation is ready. Media is sent only to the installed and verified MLX Demucs Package on this device.',
    '音轨分离模型尚未配置。点击下方按钮，安装并配置 MLX Demucs。': 'The track-separation model is not configured. Use the button below to install and configure MLX Demucs.',
    '视频字幕 Host 流程已就绪；转写、翻译和烧录能力会在执行时分别校验。': 'The video subtitle Host workflow is ready. Transcription, translation, and burn-in capabilities are checked when used.',
    '视频字幕 Host 流程不可用；请更新当前 AI2Apps App。': 'The video subtitle Host workflow is unavailable. Update the current AI2Apps App.',
    '单讲解者音轨翻译链路已就绪；原对白会被移除，翻译后的配音将与保留的背景声重新混合。': 'The single-narrator translation workflow is ready. Original dialogue will be removed and translated dubbing mixed with the preserved background.',
    '视频音轨翻译所需模型尚未齐备。点击下方按钮，配置 Detailed Transcription 和 MLX Demucs。': 'Required video audio translation models are missing. Configure Detailed Transcription and MLX Demucs below.',
    '指定角色换声链路已就绪；先识别角色，再用授权参考声音替换所选角色。': 'Speaker voice replacement is ready. Identify speakers, then replace the selected speaker with an authorized reference voice.',
    '指定角色换声所需模型尚未齐备。点击下方按钮，配置 Detailed Transcription、MLX Demucs 和 MLX Seed-VC v2。': 'Required voice replacement models are missing. Configure Detailed Transcription, MLX Demucs, and MLX Seed-VC v2 below.',
    '视频指定角色换声链路已就绪；先识别角色，再转换目标对白并保留原画面封装。': 'Video speaker voice replacement is ready. Identify speakers, convert the target dialogue, and preserve the original picture.',
    '视频角色换声所需模型尚未齐备。点击下方按钮，配置 Detailed Transcription、MLX Demucs 和 MLX Seed-VC v2。': 'Required video voice replacement models are missing. Configure Detailed Transcription, MLX Demucs, and MLX Seed-VC v2 below.',
    '详细转写能力已就绪。文件只提交给本机已安装并验证的 MLX WhisperX Package。': 'Detailed transcription is ready. Files are sent only to the installed and verified MLX WhisperX Package on this device.',
    '详细转写模型尚未配置。点击下方按钮，选择并安装 Compact 或 Quality。': 'The detailed transcription model is not configured. Choose and install Compact or Quality below.',
    '无法确认本机 ASR 能力。': 'Could not verify local ASR capability.',
    '无法检查本地模型能力；重新打开 Mini-App 后可重试。': 'Could not check local model capabilities. Reopen the Mini-App to try again.',
    '正在读取 Voice Studio Characters…': 'Loading Voice Studio Characters…',
    '请选择已验证的 Character': 'Choose a verified Character',
    '原始音色 · 临时克隆': 'Original voice · Temporary clone',
    '原始音色': 'Original voice',
    '未就绪': 'Not ready',
    '请先在 Voice Studio → Characters 创建、预览并验证一个配音角色。': 'Create, preview, and verify a dubbing Character in Voice Studio → Characters first.',
    'Characters 读取失败': 'Could not load Characters',
    '无法读取 Voice Studio Characters。': 'Could not load Voice Studio Characters.',
    '正在读取本机语音克隆模型…': 'Loading local voice-cloning models…',
    '安装更多模型…': 'Install more models…',
    '无法读取语音克隆模型。': 'Could not load voice-cloning models.',
    '无法打开语音克隆模型安装器。': 'Could not open voice-cloning model setup.',
    '正在准备字幕工作流…': 'Preparing the subtitle workflow…',
    '正在准备视频音轨翻译…': 'Preparing video audio translation…',
    '请选择语音克隆模型': 'Choose a voice-cloning model',
    'Studio Host 通道不可用，请更新 App 后重新打开。': 'The Studio Host channel is unavailable. Update the App and reopen this Mini-App.',
    '操作等待超时，请检查任务状态，不要重复提交。': 'The operation timed out. Check task status before submitting it again.',
    '录音文本记录': 'Detailed transcript'
  };

  const TITLES = {
    transcription: ['生成录音文本记录', 'Detailed Transcription'],
    separation: ['分离人声和背景音', 'Voice and Background Separation'],
    'audio-voice-replacement': ['替换录音角色声音', 'Audio Speaker Voice Replacement'],
    'video-subtitles': ['视频字幕与翻译', 'Video Subtitles and Translation'],
    'video-audio-translation': ['视频音轨翻译', 'Video Audio Translation'],
    'video-voice-replacement': ['替换视频角色声音', 'Video Speaker Voice Replacement']
  };

  function normalize(value) {
    return String(value || '').trim().replaceAll('_', '-').toLowerCase().startsWith('zh') ? 'zh-CN' : 'en';
  }

  function englishPattern(value) {
    let match = /^所需能力 · (\d+)$/.exec(value);
    if (match) return `Required capabilities · ${match[1]}`;
    match = /^角色 (\d+) 名称$/.exec(value);
    if (match) return `Speaker ${match[1]} name`;
    match = /^删除角色 (\d+)$/.exec(value);
    if (match) return `Delete speaker ${match[1]}`;
    match = /^角色 (\d+)$/.exec(value);
    if (match) return `Speaker ${match[1]}`;
    match = /^片段 (\d+) 角色$/.exec(value);
    if (match) return `Segment ${match[1]} speaker`;
    match = /^片段 (\d+) 文本$/.exec(value);
    if (match) return `Segment ${match[1]} text`;
    match = /^片段 (\d+)(.*)$/.exec(value);
    if (match) return `Segment ${match[1]}${match[2]}`;
    match = /^共 (\d+) 个片段建议修改。$/.exec(value);
    if (match) return `${match[1]} segment${match[1] === '1' ? '' : 's'} have suggested changes.`;
    match = /^(\d+) 个字幕段落 · 修改文本不会改变时间轴；清空文本可移除该段字幕。$/.exec(value);
    if (match) return `${match[1]} subtitle segments · Editing text does not change timing; clear a segment to remove its subtitle.`;
    match = /^(.*) · ([0-9:.]+) · (\d+) 个片段$/.exec(value);
    if (match) return `${match[1] === '未知语言' ? 'Unknown language' : match[1]} · ${match[2]} · ${match[3]} segments`;
    match = /^原文：(.*)$/s.exec(value);
    if (match) return `Original: ${match[1]}`;
    match = /^建议：(.*)$/s.exec(value);
    if (match) return `Suggestion: ${match[1]}`;
    match = /^已应用修正，但保存草稿失败：(.*)$/s.exec(value);
    if (match) return `Corrections were applied, but the draft could not be saved: ${match[1]}`;
    match = /^正在分离对白、转换目标角色并重新(封装视频|混音)…$/.exec(value);
    if (match) return match[1] === '封装视频' ? 'Separating dialogue, converting the target speaker, and muxing the video…' : 'Separating dialogue, converting the target speaker, and remixing audio…';
    match = /^目标角色换声与(视频封装|混音)完成。结果只保留在当前页面，请及时下载。$/.exec(value);
    if (match) return `Speaker voice replacement and ${match[1] === '视频封装' ? 'video muxing' : 'mixing'} are complete. Download the result before leaving this page.`;
    match = /^请完成“(.*)”。$/.exec(value);
    if (match) return `Complete “${translate('en', match[1])}”.`;
    match = /^导出 (.*)$/.exec(value);
    if (match) return `Export ${match[1]}`;
    match = /^(.*) · ([0-9.]+ (?:KB|MB)) · ZIP 内含 WAV 音轨和 separation\.json$/.exec(value);
    if (match) return `${match[1]} · ${match[2]} · ZIP contains WAV tracks and separation.json`;
    match = /^([0-9.]+ (?:KB|MB)) · ZIP 内含 (.*)$/.exec(value);
    if (match) {
      const contents = match[2].replace('、转写 JSON 和烧录视频', ', transcript JSON, and a subtitled video').replace(' 和转写 JSON', ' and transcript JSON');
      return `${match[1]} · ZIP contains ${contents}`;
    }
    return value;
  }

  function translate(locale, value) {
    if (value == null || normalize(locale) === 'zh-CN') return value;
    const text = String(value);
    return EN[text] || englishPattern(text);
  }

  function configureDocument(mode, locale) {
    const normalized = normalize(locale);
    document.documentElement.lang = normalized;
    const title = TITLES[mode];
    if (title) document.title = title[normalized === 'zh-CN' ? 0 : 1];
  }

  window.AI2AppsMediaVoiceI18n = Object.freeze({normalize, translate, configureDocument});
})();
