# 人声与背景分离

选择源音频或含音轨的视频，再选择二轨或四轨输出拓扑。`dialogue_background` 是从音乐分离模型
派生的近似结果，不应被解释为原生影视对白/环境声分类。

当前 MVP 已通过 mount-bound Host Capability Broker 接通 `audio.source_separation`。Host 会从
已安装且 checkpoint 就绪的可信模型 Package 中选择支持所选 profile 的 provider，在本机处理
素材，并返回一个 ZIP。ZIP 包含各条 WAV 音轨和 `separation.json`；结果不会写入草稿，请在页面
关闭前下载。
