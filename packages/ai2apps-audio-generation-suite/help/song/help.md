# Song Creation / 歌曲创作

Write a musical direction and lyrics, then choose melody-and-chords planning,
melody-only planning, or direct generation. Section buttons insert standard lyric
labels. An optional UTF-8 ABC score replaces automatic planning; it is not used in
direct mode. Imported scores are editable inputs, not generated output history.

Songs end naturally or at the chosen limit (up to 120 seconds). The ending may be
cut off at the limit. Keep 32 synthesis steps for the verified default; a fixed seed
helps reproduce identical requests. Save draft retains the form in the Host across
remounts. Generating also saves it. Drafts are separate from audio output history.

Progress reflects reported stages, not an estimated overall percentage. Cancel or
closing this Mini-App cancels the current awaited request. Saved inference stages,
resume after restart, partial re-render and reference-audio transcription are not
available in this version. Playback, export and drag belong to Voice Studio Preview
& Output. Switching Mini-Apps preserves that shared history.

Install model opens the Host ACPF for song-capable models only. YuE2 needs Runtime
1.8.10+ and its separately published model Package; an unpublished model Package
cannot be installed. ACPF enforces availability, integrity and license consent.

填写音乐方向与歌词，选择旋律与和弦、仅旋律或直接生成。段落按钮插入歌词标签；
可选的 UTF-8 ABC 乐谱替代自动规划，直接模式不会使用乐谱。最长时长是上限，
不是精确目标，达到上限可能截断结尾。默认32步；固定种子有助于复现相同请求。

保存草稿保留表单，生成前也会保存。阶段状态来自模型实际进度，没有虚构百分比。
取消或关闭当前小应用会取消请求；暂不支持阶段恢复、局部重跑或参考音频转谱。
歌曲统一进入语音工坊共享预览与输出，切换小应用不清空或过滤历史。

模型下拉中的安装选项通过ACPF选择支持歌曲规划的模型；YuE2模型包需要单独发布，
尚未上架时无法完成安装，不能用普通音乐模型替代。
