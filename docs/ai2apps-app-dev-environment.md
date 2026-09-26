# AI2Apps App-Shell App 开发环境

## 目标

App-Shell 上层 App 使用固定的独立开发环境，不再与底层、Runtime、网络和浏览器协议开发
共用 `AI2Apps-dev.app` 及其 `dev` 实例。

| 项目 | App 开发环境 | 通用/底层开发环境 |
| --- | --- | --- |
| App 路径 | `apps/ai2apps-acefox/.build/AI2Apps-app-dev.app` | `apps/ai2apps-acefox/.build/AI2Apps-dev.app` |
| 显示名称 | `AI2Apps-App-Dev` | `AI2Apps` |
| Bundle ID | `com.ai2apps.desktop.appdev` | `com.ai2apps.desktop.dev` |
| Instance ID | `app-dev` | `dev` |
| Local | 固定 Runtime/`omlx` 快照 + 当前仓库 `ai2apps`/Package 源码热挂载 | 仓库 `.venv` 的可变入口 + Package 源码热挂载 |
| Runtime profile | `cloud` | 由通用开发构建决定 |
| 更新 | 禁用 | 由通用开发构建决定 |

`AI2Apps-App-Dev` 的 Helper 保留标准托盘图标，并在左上角增加橙色圆点；App 图标球体的
上半部使用淡紫色。普通 `AI2Apps-dev.app` 和生产 App 的图标不变。

这不是包装脚本的可选装饰。共享 `build-release-app.sh` 会根据完整的固定身份自动强制
App-Dev 图标合同，校验主 App 与内嵌 Shell 的 `.icns` 完全一致，并检查四种 Helper 状态
图标都带有专用橙点；身份字段不完整或图标不一致时会在签名前终止构建。

两个实例使用不同的 Local 进程、自动分配端口、数据库、配置、日志、Cookie、Shell Profile、
Browser Agent Profile、下载目录和模型缓存，可以同时运行。

## 构建

仓库已有 `packaging/_export` 时执行：

```bash
apps/ai2apps-acefox/scripts/build-app-dev-environment.sh
```

脚本默认使用 SDK 中固定的 AI2Apps AceFox 构建。需要显式验证另一份 AceFox 或 Runtime
依赖快照时，可以只覆盖输入：

```bash
ACEFOX_APP=/absolute/path/to/Acefox.app \
ACEFOX_SHELL_SOURCE=/absolute/path/to/acefox/browser/components/ai2apps/content/shell.mjs \
RUNTIME_LAYERS=/absolute/path/to/packaging/_export \
apps/ai2apps-acefox/scripts/build-app-dev-environment.sh
```

固定身份和输出路径不可通过环境变量覆盖。每次成功构建会先把旧 App 归档到
`apps/ai2apps-acefox/.build/archive/`，失败则保留原环境不动。

如果 Runtime layers 尚未生成，先执行：

```bash
.venv/bin/python packaging/build.py --venvstacks-only
```

## 启动与数据

启动固定 App：

```bash
open apps/ai2apps-acefox/.build/AI2Apps-app-dev.app
```

实例数据位于：

```text
~/Library/Application Support/AI2Apps/instances/app-dev/
~/Library/Caches/AI2Apps/instances/app-dev/
```

开发 App 所需的账号、配置、测试数据和已安装 Package 应只在 `app-dev` 实例维护。不要把
`dev` 实例的数据目录复制进来。Helper 的“重置数据…”会在二次确认后只删除上述两个
`app-dev` 私有根目录并退出，不删除公共 `~/.cache/huggingface/hub`，也不删除同机实例共享的
`~/Library/Caches/AI2Apps/shared/checkpoint-cache-v1`。旧版本位于实例数据根中的 Checkpoint
缓存会先原子移动到共享保留区，后续按签名 manifest 验证后导入共享池；只有明确需要重建这个
长期环境时才应使用。

## 日常开发循环

App-Dev Helper 在“重置数据…”下提供“启动测试环境”。它启动受信任源码根中的
`ai2apps-test-system/bin/ai2apps-test select --no-open`，并在 App-Dev AI 浏览器的固定
Test Center 容器中打开页面。启动后菜单变为“停止测试”；停止先取消当前测试并等待收尾，
再退出控制台。关闭浏览器页面不停止服务。Test、Dev 和 Release 均无此入口。
测试 App 仍为独立 `test` 实例，不使用或重置 App-Dev 数据。

固定 App 启动后，Local 从当前仓库加载 `ai2apps/`，但继续从 Bundle 加载 `omlx` 和第三方
依赖。因此不同修改采用不同的反馈循环：

| 修改范围 | 生效方式 |
| --- | --- |
| `ai2apps/web/templates/` | 刷新页面 |
| `ai2apps/web/static/` | 刷新页面；浏览器缓存未更新时强制刷新 |
| `ai2apps/web/i18n/` | 刷新页面；若修改加载逻辑则重启 Local |
| `ai2apps/` Python API、Service、App 注册 | 从托盘重启 `app-dev` Local |
| `packages/<package>/web/`、Package Mini-App HTML/CSS/JS | 刷新或重新打开 Mini-App |
| `packages/<package>/app.yaml` | 重新打开 Studio/App 目录；已打开的 Mini-App 需要重新挂载 |
| `omlx/`、Swift Helper/Launcher、AceFox、Python 依赖层 | 重新构建固定 App |

固定构建使用已打包 AceFox 作为二进制快照，同时把同一 AceFox 工作树中当前的
`browser/components/ai2apps/content/shell.mjs` 覆盖进开发 Bundle 的 `browser/omni.ja`。
同时覆盖匹配的 `shell.xhtml`，使启动页结构与中英文初始化代码保持一致。
同时同步同一源码树的 `browser/actors/PromptParent.sys.mjs`，使 Shell 页面的原生
`alert`、`confirm`、`prompt` 标题显示 `AI2Apps`。
因此其窗口标题与通用 Dev App 一样包含设备名和 Local 地址，但前缀固定为
`AI2Apps-App-Dev`。这项覆盖只对 Development Build 开放，生产构建仍完整使用经发布流程
确认的 packaged AceFox 资源。

热挂载只开放给带 Development 标记且在 Bundle 中声明了绝对源码路径的构建。Helper 会验证
该目录包含 `ai2apps/__init__.py`；Local 启动计划会删除父进程继承的同名环境变量，只接受
Helper 显式传入的路径。Python 启动时先加载 Bundle 内的 `omlx`，再加载仓库中的
`ai2apps`，避免底层代码被意外热替换。

## Package 源码热挂载

Development Bundle 会扫描受信任源码根的直接子目录
`packages/<package>/ai2apps.json`。当同一目录还包含 `app.yaml`，且 Package 类型为 `app`
时，Local 会用与正式安装相同的 App 定义、Studio Mini-App 发现、AppInstance、mount 和
Capability Broker 路径注册它，但沙箱资源直接从源码目录读取。

这条路径不要求先生成 `.ai2app`，不会创建 Package Store 安装记录，也不会复制源码。开发中
可以直接修改 Package 的 HTML、CSS 和 JavaScript 后刷新；`app.yaml` 的 Mini-App 名称、入口
和 placement 等声明会在下次读取 App/Studio 目录时重新校验并加载。变更已存在 mount 的入口
声明后，应关闭并重新打开该 Mini-App。

源码 Package 仍必须满足正式 App/Mini-App manifest 的结构约束，声明的入口和帮助文件必须
真实存在。源码根只接受 `packages/` 的非符号链接直接子目录，资源请求也必须留在该 Package
目录内。`dist/`、`.git/`、虚拟环境、缓存和 `node_modules/` 不参与热挂载。

该能力需要 Helper 同时传入 Development Runtime 标记和 Bundle 内固定的绝对源码根。生产
Helper 不会传入这两个条件，即使外部进程伪造同名源码根环境变量，生产 Local 也不会启用源码
Package。正式 Package 安装、签名校验、旧 Package Store 和 Cloud Registry 路径保持不变。

`AI2Apps-App-Dev` 已由固定构建脚本写入源码根。通用 `AI2Apps-dev.app` 重新执行
`build-dev-app.sh` 后也默认使用当前仓库作为 `DEVELOPMENT_SOURCE_ROOT`；需要验证另一份工作树
时可以显式传入另一个绝对路径。

## 快照与重建语义

构建脚本复用正式 App 的嵌入式 Runtime 组装与完整性验证，但标记为 Development Build：

- Local 启动后从当前仓库读取 `ai2apps/`，从 App Bundle 读取 `omlx/` 和 control-plane 依赖；
- HTML、CSS、JavaScript 修改通过页面刷新生效，Python 模块修改通过重启 Local 生效；
- 仓库中的 `omlx/` 或依赖发生变化不会改变已构建的 App；
- 需要吸收底层、Swift/AceFox 或依赖更新时重新执行固定构建脚本；
- 开发构建不注册登录项，也不读取生产更新清单；
- 它不是可发布制品，正式 Desktop 发布仍必须遵循 Desktop Release Runbook。
