<a name="readme-top"></a>
[English](README.md) [中文](README_ZH.md)
# AI2Apps

## 新闻

:fire: June 20, 2024: 浏览器控制能力全面升级！支持Web Agent通过Zero-shot方式学会控制网页， 支持用户构建可自适应适配目标网页的Web Agent+RPA。

:fire: June 15, 2024: 支持Agent/组件 的全自动、半自动开发机制。无需编程，用户可通过与Agent语言交互来构建新Agent/组件。

:fire: June 15, 2024: 支持Agent/组件 的发布和发现。用户之间可自由共享Agent/组件。

:fire: May 25, 2024: 支持用户通过内置的浏览器控制组件构建Web Agent。

:fire: May 25, 2024: 支持用户通过Ollama调用本地计算机上的大型语言模型。

:fire: May 25, 2024: 支持用户将已有Agent作为API或组件使用。

:fire: May 9, 2024: [Vitalbridge Capital](http://www.vitalbridge.com/blog/复旦大学ai³徐盈辉研究员：agent的可视化创作界面-|-agent-insights?id=428)发布了对AI2Apps团队成员的专访文章。

:fire: Apr 14, 2024: 我们在arXiv上发布了论文“[AI2Apps: A Visual IDE for Building LLM-based AI Agent Applications](https://arxiv.org/abs/2404.04902)”!

:tada: Oct 29, 2023: AI2Apps被创建!

欢迎加入我们的社区

| 飞书群 | 
|---------|
| <img src="assets/feishu_pic.jpg" width="200" height="200"> |


# AI2Apps是什么？

![home](assets/ai2apps_framework.png)

## AI2Apps概览
AI2Apps作为首个面向LLM-based AI agent应用的可视化集成开发环境（Virtual IDE），覆盖了从原型设计、代码编写、Agent调试以及最终打包发布的完整开发周期，可帮助开发者高效地构建AI Agent应用。AI2Apps 集成了工程级的开发工具，以及覆盖前后端的全栈式可视化组件，开发者可以在几分钟内通过拖拽迅速构建自己的 AI Agent，并直接生成可发布与安装的App。

https://github.com/pilgrim00/ai2apps/assets/66883561/4c5eaf0d-a426-4cca-88cc-63cd79fab4aa

## 快速开始
AI2Apps可以直接在网页中使用，也可以用本项目部署在本地使用。

### 1. 直接使用网页版
用桌面浏览器访问： [https://www.ai2apps.com](https://www.ai2apps.com)  
第一次打开网页会进行开发环境安装与配置，根据浏览器以及网络的不同，大概需要几秒到1分钟的时间。  
测试期间，要访问 AI 模型，需要注册并登录 Tab-OS（注册 Tab-OS 账号完全免费）。成功注册/登录后，
就可以使用项目向导就创建 AI Agent 项目了。

### 2. 部署本地环境
在本地环境下载本项目：
```
git clone https://github.com/Avdpro/ai2apps.git
```
**在ai2apps目录下：**  
编辑 `.env` 文件，配置正确的OpenAI Key以及服务端口，默认的端口是3015：
```
APIROOT=https://www.ai2apps.com/ws/
OPENAI_API_KEY=sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
PORT=3015
```

安装依赖：
```
nmp install
```

启动服务：
```
node ./start.js
```

假设指定的端口是3015，则用浏览器打开:
`http://localhost:3015/`
与直接使用ai2apps.com一样，第一次访问会进行安装配置。  
  

<p align="center">
  <img src="assets/aahome_cn.png" alt="home" width="700" />
</p>
这是成功启动后的AI2Apps桌面状态。点击左侧 Dock 中的"项目向导"开始创建 AI Agent项目。当前版本有几个可以选择的 AI Agent 项目模版。要创建最简单的 AI Agent，可以选择第一个模版："简单的 AI Agent 应用"开始。  
输入项目名称路径（例如：MyAgent）后，点击创建按钮，系统会创建并打开项目开发环境。  

<p align="center">
  <img src="assets/aaide_01_cn.png" alt="home" width="700" />
</p>
<p align="right" style="font-size: 14px; color: #555; margin-top: 20px;">
  <a href="#readme-top" style="text-decoration: none; color: blue; font-weight: bold;">
    ↑ Back to Top ↑
  </a>
</p>

## 使用 AI2Apps 开发的优势

#### **1. 设计即开发，快速构建开发原型**  
通过拖拽绘制拓扑图，快速设计 Agent 逻辑，拓扑图自动同步为 Agent 代码，节省大量编程时间。

#### **2. Agent 可直接打包为App使用**  
开发完成的 AI Agent 可以打包输出为独立的网页/移动App（目前支持iOS和安卓系统）。也可以作为 AI 扩展集成入
现有的网页/App，仅需几行代码就可以完成整合。  

#### **3. 强大的调试功能**  
AI2Apps 拥有强大的 Agent 调试功能：使用断点，单步执行，GPT伪装等功能快速定位问题并优化 Agent 性能，
能大幅节省开发的时间以及 AI 调用成本开销。

#### **4. 与用户更高效的交互**  
在大多数情况下，聊天并不是与用户交互的最佳方式。AI2Apps 在开发时支持菜单、按钮、图表等多种 UI 控件，可以让 Agent
像专业的 App 一样与用户交互。 

#### **5. 高效团队协作**  
AI2Apps 借鉴了知名协作设计工具 Figma 的理念，支持开发者通过二维码链接向协作者实时共享其创作进度，并通过内置的版本控制功能实现协作开发。 

#### **6. 自由安全部署**  
AI2Apps 具备 Web-IDE 特性，部署后打开浏览器即可使用，实现在手机，电脑，平板，vr眼镜等全端互联。AI2Apps自带沙盒环境，将每个 Agent 项目低消耗地安全隔离在独立的浏览器 Tab 页面，无需在端侧配置 Docker 等容器环境。

#### **7. 多语言支持**  
使用传统开发模式进行多语言支持开发总是很繁琐和无趣。在 AI2Apps 中借助 AI 的辅助，只需几下点击就可以完成整个 Agent 的
多语言开发，高效又有趣！  

#### **8. 产品更容易维护**  
传统开发模式无法保证代码实现与原始设计的随时同步，设计文档在进行维护时经常不能作为有效的参考。
AI2Apps的"设计即开发"模式可以保证代码与设计随时同步，不会出现设计与实现脱节的情况。
与逐行阅读晦涩的代码相比，包含拓扑图的 AI Agent 代码在后期维护中的优势巨大，不仅可以清晰的掌握原有代码的
设计思路，还可以更迅速的定位代码问题。

#### **9. 通过插件扩展**  
就像 VScode 等开源通用IDE 一样，AI2Apps 具有完全开放的扩展性，开发者可以将外部代码封装成微服务形式，通过 Add-On 方便的进行功能扩展，根据需要制作自己的可视化插件。  
  

## 如何编写 Agent
在AI2Apps中，每个 Agent 是一个独立的js文件，拓扑图信息以注释的形式保存在文件末尾，
从而保证了设计与实现随时同步。  
Agent文件编辑界面有"代码"和"画布"两种模式，打开 Agent 后默认进入画布模式。

#### 画布模式
开发 IDE 在画布模式下：  
  
<p align="center">
  <img src="assets/aaide_01_cn.png" alt="home" width="700" />
</p>


左侧是 Agent 的组织结构视图，这里显示 Agent 对象以及其包含的"执行片段"对象列表，点击项目可以选中对象。 
中间是 Agent 拓扑图画布，在这里可以通过拖拽创建"执行片段"对象，并通过拖拽把片段之间连接起来。  
右侧是对象属性编辑器视图，在这里会列出当前选中的对象的可编辑属性，例如调用 ChatGPT 时的模型选择、温度参数等。
 
#### 代码模式
开发 IDE 在代码模式下：  
  
<p align="center">
  <img src="assets/aaide_02_cn.png" alt="home" width="700" />
</p>

左、右侧不变，依然是 Agent 的组织结构与对象属性编辑视图，中间部分则是 Agent 代码，
编辑 Agent 拓扑图以及对象属性时，代码会自动更新，开发者也可以自己手动编写代码实现可视化编辑无法完成的逻辑。

#### 运行 Agent

<p align="center">
  <img src="assets/aa_run_cn.png" alt="home" width="700" />
</p>
运行按钮在 IDE 左侧的组织结构栏和 IDE 底部的综合工具栏中。点击运行按钮即可以调试模式或者终端模式运行当前的 Agent 项目。
Agent 启动后，你可以通过对话测试 Agent。

#### 调试 Agent
 
<p align="center">
  <img src="assets/aa_debug_cn.png" alt="home" width="700" />
</p>
以 Debug 模式启动 AI Agent 即进入调试模式。在调试模式中，点击 UI 顶部的"Debug"按钮就可以进入调试视图。  
**信息流及断点**   
调试视图左侧是信息流，在这里可以查看详细的对话流程，每一步进/出的内容。点击流程中步骤的的名字可以在右侧打开步骤的详细记录，并可以设置断点。  

**单步执行与断点操作** 
在 UI 底部可以打开单步执行功能，在单步执行 AI Agent 时或遇到断点时，调试器会暂停执行并向用户汇报当前步骤的执行信息，用户可以修改步骤的输入/输出信息查看不同的效果。  

**GPT Cheat**
在调试时可以使用GPT Cheat，点击调用 GPT 的步骤，可以在右侧的面板中添加 GPT Cheat。通过 GPT Cheat 可以用预先设置好的结果模拟（绕过）ChatGPT 调用，从而节省时间与成本。

**拓扑图追踪调试信息**

<p align="center">
  <img src="assets/aa_trace_cn.png" alt="home" width="700" />
</p>

在调试 AI Agent 的过程中，Agent 的拓扑图会同步更新，标注执行调用的路径及各种参数传递的过程。
执行经过的路径会用加粗的蓝色曲线高亮显示，执行的输入输出则会在对象属性视图的**Trace Log**中列出。

### 能量及消耗
如果使用自己部署的AI2Apps环境并配置了 OpenAI Key，调用 ChatGPT 将使用开发者本人的 OpenAI 流量。
这种情况下系统不会有任何限制。   
如果使用的是www.ai2apps.com环境运行/调试 Agent，在执行ChatGPT调用时会产生由系统承担的 OpenAI 费用。
为了避免账单崩溃，系统通过"能量"限制用户对ChatGPT的调用量。  

### 获得能量
在成功注册登录 Tab-OS 后，用户会获得一定的免费能量，
每天登录后也会根据当前用户等级为用户补充一定的能量。推荐新成员用户成功也可以获得免费的系统代币，
可用于兑换能量。

### 发布 Agent
编辑好的 Agent 可以打包发布为网页或移动应用（iOS/安卓）。 

<p align="right" style="font-size: 14px; color: #555; margin-top: 20px;">
  <a href="#readme-top" style="text-decoration: none; color: blue; font-weight: bold;">
    ↑ Back to Top ↑
  </a>
</p>

## Coming Soon：
- 支持Wechat bot
- 更多文档及例子

## 引用
如果您觉得我们的工作对您的研究或应用有帮助，请引用我们的论文[AI2Apps](https://arxiv.org/abs/2404.04902)
```
@article{pang2024ai2apps,
  title={AI2Apps: A Visual IDE for Building LLM-based AI Agent Applications},
  author={Pang, Xin and Li, Zhucong and Chen, Jiaxiang and Cheng, Yuan and Xu, Yinghui and Qi, Yuan},
  journal={arXiv preprint arXiv:2404.04902},
  year={2024}
}
```
