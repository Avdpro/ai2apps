# 📘 ModelHunt 部署脚本开发手册 (macOS 版)

**版本**: 3.0.0 (Natural Language Edition)
**适用平台**: macOS (Apple Silicon & Intel)
**标准根目录**: `~/.modelhunt` (即 `$HOME/.modelhunt`)

## 1. 核心原则 (Core Principles)

本手册指导开发者编写 `deploy.json`。ModelHunt 部署引擎会读取此文件，将 AI 模型安装到用户的 `~/.modelhunt` 目录下。

编写脚本时，请务必遵守以下四大原则：

1. **路径规范**：所有操作必须限制在 `~/.modelhunt` 目录下，严禁污染用户其他目录。
2. **状态检测**：所有 `bash` 命令必须以 `&& echo "Successful" || echo "Failed"` 结尾。
3. **环境隔离**：必须使用 Conda 管理 Python 环境。
4. **自然语言交互**：`tip` 提示语必须**自然、友好、清晰**，避免使用纯技术术语（如 "Exec git clone"），而应使用用户视角的语言（如 "正在为您下载代码仓库..."）。

---

## 2. 配置文件结构 (Configuration Structure)

```json
{
  "id": "项目ID_小写下划线",
  "name": "项目显示名称",
  "version": "1.0.0",
  "platforms": {
    "mac": {
      "steps": [
        // 部署步骤数组
      ]
    }
  }
}

```

---

## 3. 动作编写规范 (Action Specifications)

### 🛠️ Action 1: `bash` (执行 Shell 命令)

* **参数**:
* `action`: `"bash"`
* `tip`: **(Object)** 双语提示。**要求语气自然，像助手在汇报工作。**
* `commands`: **(Array)** 命令数组。


* **编写规则**:
1. **根目录**: 统一使用 `$HOME/.modelhunt`。
2. **状态检测**: 必须包含 `&& echo "Successful" || echo "Failed"`。
3. **括号包裹**: 复合命令请用 `(...)` 包裹。



**标准模板 (Clone 项目):**

```json
{
  "action": "bash",
  "tip": {
    "zh": "正在为您初始化目录并拉取代码仓库...",
    "en": "Initializing directory and fetching the code repository for you..."
  },
  "commands": [
    "mkdir -p $HOME/.modelhunt && cd $HOME/.modelhunt && ([ -d \"项目文件夹名\" ] && echo \"Repo exists\" || git clone https://github.com/xxx/xxx.git 项目文件夹名) && echo \"Successful\" || echo \"Failed\""
  ]
}

```

**标准模板 (安装 Pip 依赖):**

```json
{
  "action": "bash",
  "tip": {
    "zh": "正在安装项目所需的 Python 依赖库，这可能需要一点时间...",
    "en": "Installing necessary Python dependencies, this might take a moment..."
  },
  "commands": [
    "(cd $HOME/.modelhunt/项目文件夹名 && pip install -r requirements.txt) && echo \"Successful\" || echo \"Failed\""
  ]
}

```

### 🐍 Action 2: `conda` (Python 环境)

* **参数**:
* `action`: `"conda"`
* `tip`: **(Object)** 双语提示。
* `conda`: 环境名称。必须以 `_aa` 结尾
* `pythonVersion`: 版本号。



**示例**:

```json
{
  "action": "conda",
  "tip": {
    "zh": "正在为项目配置专属的 Python 运行环境...",
    "en": "Setting up a dedicated Python environment for the project..."
  },
  "conda": "sparktts_aa",
  "pythonVersion": "3.11"
}

```

### 🍺 Action 3: `brew` (系统依赖)

* **参数**:
* `action`: `"brew"`
* `tip`: **(Object)** 双语提示。
* `install`: 包名称。



**示例**:

```json
{
  "action": "brew",
  "tip": {
    "zh": "正在检测并安装音频处理工具 (FFmpeg)...",
    "en": "Checking and installing audio processing tool (FFmpeg)..."
  },
  "install": "ffmpeg"
}

```

### 🤗 Action 4: `hf_model` (下载模型)

* **参数**:
* `action`: `"hf_model"`
* `tip`: **(Object)** 双语提示。
* `model`: Hugging Face Repo ID。
* `localPath`: 存储的绝对路径。



**示例**:

```json
{
  "action": "hf_model",
  "tip": {
    "zh": "最后一步：正在下载预训练模型权重 (Spark-TTS-0.5B)...",
    "en": "Final step: Downloading pretrained model weights (Spark-TTS-0.5B)..."
  },
  "model": "SparkAudio/Spark-TTS-0.5B",
  "localPath": "~/.modelhunt/spark-tts/pretrained_models/Spark-TTS-0.5B"
}

```

---

## 4. 实战案例：Spark-TTS 部署脚本 (自然语言版)

这是一份**可以直接使用**的标准范例。请注意 `tip` 的语气变化。

```json
{
  "id": "spark_tts",
  "name": "Spark-TTS",
  "version": "1.0.0",
  "platforms": {
    "mac": {
      "steps": [
        {
          "action": "bash",
          "tip": {
            "zh": "正在为您下载 Spark-TTS 的源代码...",
            "en": "Downloading the Spark-TTS source code for you..."
          },
          "commands": [
            "mkdir -p $HOME/.modelhunt && cd $HOME/.modelhunt && ([ -d \"spark-tts\" ] && echo \"Directory exists, skipping clone...\" || git clone https://github.com/SparkAudio/Spark-TTS.git spark-tts) && echo \"Successful\" || echo \"Failed\""
          ]
        },
        {
          "action": "conda",
          "tip": {
            "zh": "正在准备 Python 3.11 运行环境...",
            "en": "Preparing the Python 3.11 runtime environment..."
          },
          "conda": "sparktts",
          "pythonVersion": "3.11"
        },
        {
          "action": "brew",
          "tip": {
            "zh": "正在安装必要的系统组件 (FFmpeg)...",
            "en": "Installing necessary system components (FFmpeg)..."
          },
          "install": "ffmpeg"
        },
        {
          "action": "bash",
          "tip": {
            "zh": "正在安装 Python 依赖库，请稍候...",
            "en": "Installing Python dependencies, please wait..."
          },
          "commands": [
            "(cd $HOME/.modelhunt/spark-tts && pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple) && echo \"Successful\" || echo \"Failed\""
          ]
        },
        {
          "action": "bash",
          "tip": {
            "zh": "正在配置 PyTorch 计算框架 (已开启 Mac 加速)...",
            "en": "Configuring PyTorch framework (Mac acceleration enabled)..."
          },
          "commands": [
            "(pip install torch torchvision torchaudio --upgrade -i https://pypi.tuna.tsinghua.edu.cn/simple) && echo \"Successful\" || echo \"Failed\""
          ]
        },
        {
          "action": "hf_model",
          "tip": {
            "zh": "正在下载模型文件 (Spark-TTS-0.5B)，马上就好...",
            "en": "Downloading model files (Spark-TTS-0.5B), almost done..."
          },
          "model": "SparkAudio/Spark-TTS-0.5B",
          "localPath": "~/.modelhunt/spark-tts/pretrained_models/Spark-TTS-0.5B"
        }
      ]
    }
  }
}

```

---

## 5. 开发自检清单 (Checklist)

提交脚本前，请务必检查以下几点：

1. [ ] **语气自然**: `tip` 是否像真人在对话？（避免使用 "Exec command..." 这种机器语言）
2. [ ] **路径前缀**: 所有的 `cd` 命令是否都以 `$HOME/.modelhunt` 开头？
3. [ ] **状态回显**: 所有的 `bash` 命令末尾是否都包含 `&& echo "Successful" || echo "Failed"`？
4. [ ] **括号包裹**: 组合命令（如 `cd ... && pip ...`）是否用 `()` 包裹了？
5. [ ] **环境唯一**: `conda` 环境名是否与项目 ID 对应？是否以 `_aa` 结尾？