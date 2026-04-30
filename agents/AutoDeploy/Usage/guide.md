# 📝 本地 AI 模型接入配置指南 (Agent Configuration Guide)

这份文档旨在指导你如何为你的本地 AI 项目（如 TTS、生图、视频生成等）编写一个 `.yaml` 配置文件。

通过这个文件，你可以将复杂的 Python 命令行工具封装成一个 **标准化的 AI 技能 (Skill)**，让 Agent 能够理解你的模型功能，并自动帮你执行代码。

---

## 📂 文件结构概览

一个标准的配置文件由四个核心部分组成：

1. **Metadata (元数据)**: 它是谁？（ID、名称、版本）
2. **Interface (交互层)**: 怎么向用户介绍自己？（欢迎语、推荐指令）
3. **Global Execution (执行环境)**: 代码在哪里运行？（环境、路径）
4. **Skills (技能定义)**: 具体能干什么？（参数定义、命令模板）

---

## 🛠️ 第一步：定义元数据 (Metadata)

这部分是项目的“身份证”，用于系统内部索引和 UI 展示。

```yaml
# 唯一标识符 (ID)
# 规则：只能使用小写字母、数字和下划线。不要包含空格。
# 示例：spark_tts, stable_diffusion_xl, llama3_local
id: "your_project_id"

# 显示名称 (Name)
# 规则：显示在 Agent 窗口顶部的标题，可以是任何人类可读的字符串。
name: "Project Display Name"

# 描述 (Description)
# 规则：简短描述项目功能。这对 AI 的“路由系统”很重要，决定了什么时候调用这个模型。
description: "A short description of what this model does."

# 版本号 (Version)
version: "1.0.0"

```

---

## 💬 第二步：配置交互文案 (Interface)

这部分定义了用户刚打开 Agent 时看到的“欢迎界面”。**好的开场白能显著降低用户的使用门槛。**

你需要配置 `default_language` 以及具体的语言包（建议至少提供 `zh` 和 `en`）。

```yaml
interface:
  default_language: "zh"
  
  languages:
    zh:
      # 开场白 (Greeting)
      # 建议：
      # 1. 简单打个招呼。
      # 2. 列出 1-3 个核心功能点（加粗显示）。
      # 3. 告诉用户下一步该怎么做。
      greeting: |
        👋 你好！我是 **[项目名称]** 助手。
        
        我具备以下能力：
        1. 🎨 **功能一**：描述...
        2. 🛠️ **功能二**：描述...
        
        请直接告诉我你的需求。
      
      # 推荐指令 (Suggested Queries)
      # 作用：显示在输入框上方的气泡，用户点击即可发送。
      # 建议：覆盖该项目最常用的 3 个场景。
      suggested_queries:
        - "场景一的典型指令..."
        - "场景二的典型指令..."
        - "场景三的典型指令..."

    en:
      greeting: |
        👋 Hello! I am **[Project Name]**.
        ...
      suggested_queries:
        - "Example query 1..."

```

---

## ⚙️ 第三步：设置运行环境 (Global Execution)

这部分告诉 Agent 去哪里找到你的代码以及用哪个环境来跑。

```yaml
global_execution:
  # 执行类型 (目前固定为 conda_cli)
  type: "conda_cli"

  # Conda 环境名称
  # 系统在执行时会先激活这个环境 (conda activate [env_name])
  env_name: "your_conda_env_name"

  # 项目根目录 (Working Directory)
  # 所有github项目下载到 ~/.modelhunt/
  working_directory: "~/.modelhunt/your-project-folder"

  # 前置命令 (可选)
  # 在每次执行技能前运行的命令，用于启动依赖的后台服务等。
  # 例如 Ollama 部署需要确保服务已启动：base_command: "brew services start ollama"
  # 如果不需要（如 Spark-TTS 等纯 Python 项目），留空即可。
  base_command: ""

```

---

## ⚡ 第四步：定义技能 (Skills) —— 核心部分

这是最关键的一步。你需要把你的 Python 脚本拆解成一个或多个“技能”。

**原则**：如果是单一功能模型，定义一个 Skill 即可；如果是多功能（如既能文生图，又能图生图），建议拆分为多个 Skills。

每个 Skill 包含三个要素：`name` (名称), `command_template` (命令模板), `arguments` (参数约束)。

### 1. 基础信息

```yaml
skills:
  - name: "skill_id"  # 技能ID，如 basic_tts, image_gen
    description: "详细描述这个技能具体做什么，LLM 会阅读这行文字来决定是否调用。"

```

### 2. 命令模板 (Command Template)

这是 AI 将自然语言转换为代码的**模板**。

* 你需要写出完整的运行命令（包括 `python xxx.py`）。
* 用 `{variable_name}` 包裹需要 AI 填写的参数。
* **⚠️ 注意**：如果参数值可能包含空格（如文件路径、长文本），**务必在 `{}` 外面加上双引号**。

```yaml
    # 示例：调用 python 模块
    command_template: python -m cli.inference 
      --text "{text}" 
      --output "{save_path}" 
      --style "{style_name}"

    # 或者示例：调用 python 脚本
    # command_template:
    #   python main.py --prompt "{prompt}" --steps {steps}

```

### 3. 参数约束 (Arguments)

这部分告诉 AI 模板里的 `{text}`, `{save_path}` 具体是什么，以及有哪些限制。它遵循 **JSON Schema** 标准。

* **required**: **必填项列表**。只有列在这里的参数，AI 才会强制要求用户提供。
* **properties**: 参数的详细定义。

```yaml
    arguments:
      type: "object"
      # 【关键】列出哪些参数是必须的
      required: ["text"] 
      
      properties:
        # 定义 String 类型参数
        text:
          type: "string"
          description: "需要处理的文本内容。"
        
        # 定义带默认值的路径参数
        save_path:
          type: "string"
          description: "结果保存路径。"
          default: "./results"
        
        # 定义枚举参数 (Enum) —— 限制 AI 只能从列表中选，防止乱填
        style_name:
          type: "string"
          description: "风格选择。"
          enum: ["modern", "cyberpunk", "sketch"]
          default: "modern"
        
        # 定义数字类型参数
        steps:
          type: "integer"
          description: "生成步数，值越大越慢但质量越好。"
          default: 20
          minimum: 1
          maximum: 50

```

---

## 📝 完整示例模板 (Copy & Paste)

你可以直接复制下面的模板，修改对应字段即可。

```yaml
id: "my_cool_project"
name: "My Cool Project"
description: "Brief description for the system router."
version: "1.0.0"

interface:
  default_language: "zh"
  languages:
    zh:
      greeting: |
        👋 你好！我是 **[模型名]**。
        我可以帮你完成 [功能A] 和 [功能B]。
      suggested_queries:
        - "测试指令 1"
        - "测试指令 2"
    en:
      greeting: |
        👋 Hello! I am **[Model Name]**.
      suggested_queries:
        - "Test query 1"

global_execution:
  type: "conda_cli"
  env_name: "my_env"
  working_directory: "~/.modelhunt/project"
  base_command: ""  # 可选，如需启动后台服务填写对应命令

skills:
  - name: "main_function"
    description: "Describe what this specific function does."
    
    # 编写你的命令，用 {arg} 占位
    command_template: python inference.py 
      --input "{input_text}" 
      --mode "{mode}"
    
    arguments:
      type: "object"
      required: ["input_text"]
      properties:
        input_text:
          type: "string"
          description: "The input content."
        mode:
          type: "string"
          description: "Operation mode."
          enum: ["fast", "quality"]
          default: "fast"
        save_dir:
          type: "string"
          default: "./outputs"
```

---