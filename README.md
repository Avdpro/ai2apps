
<a name="readme-top"></a>
[English](README.md) [中文](README_ZH.md)
# AI2Apps

## News

:fire: June 20, 2024: Browser control capabilities upgraded! Web Agents can now learn to control web pages via zero-shot learning, enabling users to build Web Agents + RPA that dynamically adapt to target web pages.

:fire: June 15, 2024: Supports fully automatic and semi-automatic development mechanisms for Agents/components. Users can interact with Agent languages to build new Agents/components without programming.

:fire: June 15, 2024: Supports the Release of Agents/components. Users can freely share Agents/components with each other.

:fire: May 25, 2024: Supports users in building Web Agents through built-in browser control components.

:fire: May 25, 2024: Supports users in invoking large language models on local computers via Ollama.

:fire: May 25, 2024: Supports users in utilizing existing Agents as APIs or components.

:fire: May 9, 2024: [Vitalbridge Capital](http://www.vitalbridge.com/blog/复旦大学ai³徐盈辉研究员：agent的可视化创作界面-|-agent-insights?id=428)has released an interview article featuring members of the AI2Apps team.

:fire: Apr 14, 2024: Our paper has been published the paper on arXiv:“[AI2Apps: A Visual IDE for Building LLM-based AI Agent Applications](https://arxiv.org/abs/2404.04902)”!

:tada: Oct 29, 2023: AI2Apps has been creatd!

Welcome to our community!

| Feishu | 
|---------|
| <img src="assets/feishu_pic.jpg" width="200" height="200"> |


# What's AI2Apps？

![home](assets/ai2apps_framework.png)

## AI2Apps Overview
AI2Apps, as the inaugural visual IDE for LLM-based AI agent applications, encompasses the entire development cycle—from prototyping, coding, and agent debugging to final packaging and release—enabling developers to efficiently build AI Agent applications. It integrates engineering-level development tools and full-stack visualization components for both front-end and back-end, empowering developers to swiftly create AI Agents via drag-and-drop, generating publishable and installable apps directly.

https://github.com/pilgrim00/ai2apps/assets/66883561/4c5eaf0d-a426-4cca-88cc-63cd79fab4aa

## Quick Start
AI2Apps can be used directly via Web Browser or deployed locally using this project.
### 1. Direct Use via Web Browser
Accessed with a desktop browser: [https://www.ai2apps.com](https://www.ai2apps.com)  
When you first open the webpage, the development environment will install and set up. Depending on your browser and internet speed, this process usually takes from a few seconds to one minute. During testing, accessing AI models requires registering and logging into Tab-OS (signing up for a Tab-OS account is completely free). Once you successfully register or log in, you can use the project wizard to create AI Agent projects.

### 2. Local Deployment
Download this project in your local environment:
```
git clone https://github.com/Avdpro/ai2apps.git
```
**Within the ai2apps directory:**  
Edit the `.env` file and configure the correct OpenAI Key and server port. The default port is 3015:
```
APIROOT=https://www.ai2apps.com/ws/
OPENAI_API_KEY=sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
PORT=3015
```

Install dependecies：
```
nmp install
```

Start services：
```
node ./start.js
```

Assuming the specified port is 3015, open the following URL in your browser:
`http://localhost:3015/`
Just like accessing ai2apps.com directly, the first visit will initiate the installation and configuration process.

<p align="center">
  <img src="assets/aahome_cn.png" alt="home" width="700" />
</p>
This is the desktop status of AI2Apps after a successful launch. Click "Project Wizard" on the left-hand Dock to begin creating an AI Agent project. The current version offers several AI Agent project templates to choose from. For creating the simplest AI Agent, select the first template: "Simple AI Agent Application."
After inputting the project name (e.g., MyAgent) and clicking the create button, the system will create and open the project development environment.

<p align="center">
  <img src="assets/aaide_01_cn.png" alt="home" width="700" />
</p>
<p align="right" style="font-size: 14px; color: #555; margin-top: 20px;">
  <a href="#readme-top" style="text-decoration: none; color: blue; font-weight: bold;">
    ↑ Back to Top ↑
  </a>
</p>

## Advantages of Using AI2Apps for Development

#### **1. Design-to-Development for Rapid Prototyping**  
Easily design Agent logic with drag-and-drop to create topological diagrams, which automatically synchronize with Agent code, saving significant programming time.

#### **2. Direct Packaging of Agents into Apps**  
Completed AI Agents can be packaged into standalone web/mobile apps (currently supporting iOS and Android systems). They can also integrate seamlessly as AI extensions into existing websites/apps with just a few lines of code.

#### **3. Powerful Debugging Capabilities**  
AI2Apps offers robust Agent debugging features: use breakpoints, step-by-step execution, and GPT camouflage to quickly identify issues and improve Agent performance, saving both development time and AI invocation costs.

#### **4. Enhanced User Interaction**  
In many scenarios, chatting isn't the most effective form of user interaction. AI2Apps supports various UI controls during development such as menus, buttons, and charts, enabling Agents to interact with users like professional apps.

#### **5. Efficient Team Collaboration**  
Taking cues from popular collaborative design tools like Figma, AI2Apps supports real-time sharing of creative progress via QR code links and facilitates collaborative development with built-in version control.
#### **6. Flexible and Safely Deployment**  
AI2Apps is equipped with Web-IDE features, which can be used after opening the browser after deployment, ensuring seamless connectivity across smartphones, computers, tablets, VR headsets, and other devices.Each Agent project operates within a secure sandbox environment, isolated in independent browser tab pages without the need for server-side Docker or container configurations.

#### **7. Multilingual Support**  
Traditional approaches to multilingual support often prove cumbersome and tedious. AI2Apps streamlines multilingual development with AI assistance, enabling developers to efficiently localize entire Agent projects with just a few clicks.

#### **8. Simplified Product Maintenance**  
Unlike traditional methods where code implementation can diverge from original designs, the "design-to-development" of AI2Apps approach ensures continuous synchronization between design and code. Topological diagrams embedded in AI Agent code provide clear insights into original design intentions, facilitating faster issue resolution compared to navigating dense code.

#### **9. Extensibility through Plugins**  
Similar to popular open-source IDEs like VSCode, AI2Apps supports full extensibility. Developers can encapsulate external code into microservices and easily extend functionality via Add-Ons, creating customized visual plugins as needed.
  

## How to Write an Agent
In AI2Apps, each Agent is an independent js file, and the topology map information is saved in the form of comments at the end of the file, ensuring real-time synchronization between design and implementation.
The Agent file editing interface offers both "Code" and "Canvas" modes, with "Canvas" mode as the default upon opening an Agent.
#### Cavas Mode
In the Canvas mode of the development IDE:  
  
<p align="center">
  <img src="assets/aaide_01_cn.png" alt="home" width="700" />
</p>


On the left side, you have the organizational view of the Agent. Here, you can see the Agent objects and the list of "execution segments" they contain. Clicking on a project selects the object.
In the middle, there's the Agent topology diagram canvas. Here, you can drag and drop to create "execution segments" and connect them together by dragging connections between segments.
On the right side, there's the object property editor view. Here, editable properties of the currently selected object are listed. For example, parameters like model selection and temperature settings when calling ChatGPT.
 
#### Code Mode
In the Code mode of the development IDE:  
  
<p align="center">
  <img src="assets/aaide_02_cn.png" alt="home" width="700" />
</p>

On the left and right sides, the organizational structure of the Agent and the object property editing view remain unchanged. In the center, however, is the Agent code. When editing the Agent topology diagram and object properties, the code updates automatically. Developers can also manually write code to implement logic that cannot be achieved through visual editing alone.

#### Launch Agent

<p align="center">
  <img src="assets/aa_run_cn.png" alt="home" width="700" />
</p>
The run button is located in both the organizational structure panel on the left side of the IDE and the comprehensive toolbar at the bottom. Clicking the run button starts either the debugging mode or terminal mode to run the current Agent project. Once the Agent is launched, you can test it through dialogue interactions.

#### Debug Agent
 
<p align="center">
  <img src="assets/aa_debug_cn.png" alt="home" width="700" />
</p>
Launching an AI Agent in Debug mode activates the debugging environment. In Debug mode, click the "Debug" button at the top of the UI to access the debugging view.
**Information Flow and Breakpoints**   
On the left side of the debugging view is the message flow, where you can review detailed conversation sequences, including the content of each step in and out. Clicking on a step's name within the flow opens detailed logs on the right side and allows you to set breakpoints.

**Single Step Execution and Breakpoint Operations** 
At the bottom of the UI, you can turn on the single-step execution function. When executing the AI Agent in a single step or encountering a breakpoint, the debugger will pause the execution and report the execution information of the current step to the user, so that the user can modify the input/output information of the step to see different effects.  

**GPT Cheat**
GPT Cheat can be used during debugging by clicking on the step to call GPT and adding a GPT Cheat in the right panel. with GPT Cheat it is possible to simulate (bypass) a ChatGPT call with a preconfigured result, which saves time and costs.

**Topology Trace and Debug**

<p align="center">
  <img src="assets/aa_trace_cn.png" alt="home" width="700" />
</p>

While debugging an AI Agent, the Agent's topology diagram updates dynamically, highlighting the paths and parameter transfers involved in each call. Executed paths are highlighted with bold blue lines, and input/output details are listed in the Trace Log within the object properties view.

### Energy and Consumption
If using a self-deployed AI2Apps environment configured with an OpenAI Key, invoking ChatGPT utilizes the developer's own OpenAI credits without any system-imposed restrictions.
When running/debugging an Agent on www.ai2apps.com, the system covers the costs incurred from ChatGPT calls. To prevent unexpected bills, the system limits ChatGPT usage through an "energy" system.

### Acquire Energy
After successfully registering and logging into Tab-OS, users receive a certain amount of free energy credits. Additionally, each day upon logging in, users receive a replenishment of energy based on their current user level. Successfully referring new members also earns users free system tokens, which can be exchanged for energy credits.

### Release Agent
Once an Agent is edited and finalized, it can be packaged and released as a web or mobile application (iOS/Android).

<p align="right" style="font-size: 14px; color: #555; margin-top: 20px;">
  <a href="#readme-top" style="text-decoration: none; color: blue; font-weight: bold;">
    ↑ Back to Top ↑
  </a>
</p>

## Coming Soon：
- Support for Wechat bot
- More related documents and examples

## Citation
If you find our work useful for your research or application, please cite our paper [AI2Apps](https://arxiv.org/abs/2404.04902)
```
@article{pang2024ai2apps,
  title={AI2Apps: A Visual IDE for Building LLM-based AI Agent Applications},
  author={Pang, Xin and Li, Zhucong and Chen, Jiaxiang and Cheng, Yuan and Xu, Yinghui and Qi, Yuan},
  journal={arXiv preprint arXiv:2404.04902},
  year={2024}
}
```
