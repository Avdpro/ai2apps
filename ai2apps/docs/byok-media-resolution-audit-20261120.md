# BYOK 图像／视频分辨率修复与验收（2026-11-20）

## 修复范围

这里的范围是客户端现有可执行的 BYOK 路由，不是为所有厂商增加新的 API 适配器。
检查了图片目录、Bot 参数描述与执行校验、Imagine Studio、图片请求适配器，以及视频目录、Video Studio、请求校验与原生厂商请求。

| 路由／模型 | 分辨率契约与处理 |
| --- | --- |
| GPT Image 2（含日期快照） | 自定义 WIDTHxHEIGHT、auto；16 倍数、边长不超过 3840、长短边比不超过 3、655360～8294400 像素；超过 3686400 像素提示实验范围 |
| GPT Image 2.5 / 2.6 Flare、Sunburst（含日期快照） | 同上；质量支持 auto / low / medium / high / xhigh / max；生成与编辑复用同一契约 |
| GPT Image 1 / 1-mini / 1.5（含日期快照）、chatgpt-image-latest | 保留三档固定尺寸和 auto；不扩大到新版本的尺寸或质量档位 |
| DALL-E 2 | 256 / 512 / 1024 正方形，standard；适配器不传不支持的 quality 字段，单图编辑使用 image 字段 |
| DALL-E 3 | 1024 正方形、1792×1024、1024×1792；standard / hd；不声明编辑能力 |
| 其它 OpenAI 兼容图片模型 | 不再虚构“只支持 1024 正方形”。自定义尺寸原样交给所选服务校验，明确标注未核实厂商尺寸能力；本机 1～16384 单边、268435456 像素只是传输安全边界，不是厂商支持承诺。其它参数仍受现有适配器支持范围限制 |
| MiniMax H3 | 768P / 2K |
| MiniMax H3 Highspeed / Lite / Max | 480P / 768P，不能通过选择绕过模型档位限制 |
| Seedance 2.5 | 480p / 720p / 1080p / 4K，完整六种比例的官方像素表 |
| Seedance 2.5 Flash | 480p / 720p，完整六种比例的官方像素表，不开放 1080p / 4K |

图片增加 `images/byok_capabilities.py` 作为共有定义，Bot 与 Studio 不再各自构造尺寸清单，请求适配器也复用该定义。带厂商命名空间的模型 ID 用同一能力定义，但请求中的完整模型 ID 保持原样。

视频补全 21:9、16:9、4:3、1:1、3:4、9:16。Seedance 的精确尺寸与比例不一致时明确报错，不改写到另一尺寸。MiniMax 的接口接受档位，不保证一个固定的像素尺寸；界面分开选择档位与比例，不把估算尺寸当成厂商承诺。首尾帧、编辑／延长任务原有 adaptive 规则仍按厂商要求执行，输出尺寸可能随输入变化。

没有新增 Sora、Veo、Flux 或 Imagen 的原生适配器，也没有把名字中带 video/image 等同于已经支持对应厂商 API。未知兼容服务的本机校验通过不等于真实服务一定支持。

## 官方依据

- [OpenAI Image prompting](https://developers.openai.com/api/docs/guides/image-prompting#gpt-image-2.5-model-parameters)
- [OpenAI Image generation](https://developers.openai.com/api/docs/guides/image-generation)：含 2.6 参数及早期版本区别
- [OpenAI Images API](https://developers.openai.com/api/reference/resources/images/methods/generate)
- [MiniMax H3 创建任务](https://platform.minimax.io/docs/api-reference/video-generation-v2-create)
- [Seedance 创建任务与输出尺寸表](https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh)

## 验收边界

针对性测试覆盖版本、非法尺寸原因、Bot／Studio 同源、日期与命名空间 ID、JSON 与多参考 multipart 请求、六个视频变体所有声明的分辨率映射，以及界面提交参数。双参考合影与编辑测试使用模拟 HTTP 服务，并检查返回的真实 PNG 头尺寸；不代表已经完成真实模型质量验收。

C01 保持 waiting_input；未提交新的 Cloud 或付费 BYOK 生成请求。Test 更新后使用原来的两张人物照，依次：

1. 明确选择原 GPT Image 2.5 Flare BYOK，合影尺寸 1536×1152。
2. 在该合影上继续修改，仍指定 1536×1152。
3. 两步检查下载图片实际像素、完整模型 ID 和 BYOK 路由；不得以输出元数据中回显的请求尺寸作为实际像素证据。
4. 厂商拒绝时直接保留错误，不自动切 Cloud、换模型、缩放或裁切。

## 本次 Test 激活记录

标准 `build-test-app.sh` 构建成功，内嵌的两个能力模块及两个 Studio 脚本与当前源码哈希一致。Test 在没有 queued/running 任务时，经自己的 Helper `local.restart` 重启，Local PID 31002、端口 62456，健康检查 200。实际提供的 Imagine / Video Studio 脚本哈希与源码一致。唯一 waiting_input 任务仍保留。没有访问 Cookie；受保护的模型目录接口未使用用户会话调用验收。

源码与传递链测试已完成；刷新 Test 的 Studio 后，由 C01 重新查询能力并完成上述两次真实 BYOK 出图验收。当前打开页面的旧 JavaScript 状态需要刷新才会替换。
