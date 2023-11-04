# AI2Apps Public Beta

## What is AI2Apps?
CokeCodes is designed to be a **in-browser** Web/App development environment. It brings the essence of morden OS (like MacOS, Windows, Unix) to the browser. Developers can do all works within browser. Even it's in such early stage, 90% of my coding work is done in browser with CokeCodes tools now.

You can review current CokeCodes at [www.cokecodes.com](https://www.cokecodes.com)  
  
## Why work in browser?
With new features keep coming out, morden browsers can do much more than just browsing. PWA web apps already taking more roles from native apps. Why not our coding environment?  
- **No system contamination**: Setup a new project work environment won't install anything or make any changes out side the browser. Your computer/ device always stay clean. 

- **Domain Sandboxed**: Cause of the browser' nature, they are strongly isolated. You can think the **sand boxes as computers**. You can have **dedicate computer for each project**. Start and switch between them is lightning fast. Removing a sandbox cleans everything, so neat.   
Currently, beside *www*, **cokecodes.com** has serveral sandbox you can play with:
   - [sandbox001.cokecodes.com](https://sandbox001.cokecodes.com)
   - [sandbox002.cokecodes.com](https://sandbox002.cokecodes.com)
   - [sandbox003.cokecodes.com](https://sandbox003.cokecodes.com)
   - [sandbox004.cokecodes.com](https://sandbox004.cokecodes.com)
   - [sandbox005.cokecodes.com](https://sandbox005.cokecodes.com)

- **Same experience**: CokeCodes' tool and applications works just as good as similar tools run in native. They launch in a blink, and run smoothly the in browsers.  Especially comparing to apps based on node like runtimes, browsers' Javascript VM can be even better.   

- **Any device, any time**: Browsers are best cross-platform-environment out there. PWA apps can run on all morden major browsers on desktop or mobile devices. With it's inbuilt cloud feature, you can easily pick up your work any where, any time. 

## Productivity
- **Work offline**: As PWA apps, all CokeCodes tools/apps can work offline so you won't concern about the network connection while working. 

- **Cloud repository**: Projects (disks) in CokeCodes file system can be synced with CokeCodes cloud repository. You can access your works anytime, anywhere, on any devices. More public clouds support is on the way.

- **Packages**: CokeCodes has a **npm** like package system. Libs, tools and apps are delivered as packages. With minor modifications, most node packages can be port into browser. You can install, update packages to setup or enhance your coding power. You can make your own packages and share with others too. 

## Applications
CokeCodes currently has a **desktop** and 3 major PWA web app tools: **CCEditor**, **Terminal** and **Diskit**:  
  
### CCEditor  
![ccedit](git/ccedit_01.png)  

**CCEditor** is a full-functional **code text editor**. It's based on the great work of **CodeMirror**. It got almost all the cool features that morden code editors have: **Syntax highlights**, **Code folding**, **Autocompletion**, **Linter integration**, **Search and replace**, **Bracket and tag matching**, **Marks/ todos** and more.  

### Terminal  
![ccedit](git/terminal_01.png)  

**Terminal** is a UNIX terminal like CLI environment which can run commands (ls, cwd, cd, cp, rm...), apps and scripts.  
  
### Diskit  
![ccedit](git/diskit_01.png)  

**Diskit** is the file manager of CokeCokes system. It works like just **File Explorer** in Windows or **Finder** in MacOS.

## Tools
Besides common terminal commands like ls, cd, cp, cat, rm... This concept demo also includes several helper command line tool for development:
- **cloud**: CokeCokes account/ login util tool.

- **disk**: Disk management tool, also sync (checkin, checkout, commit, update) the locale disk with could repositories. 

- **pkg**: Package management tool, you can init/install/import/share/update packages with it.

- **rollup**: A rough port of **rollup**, it currently only accept config file as options. Simple **terser** and **babel** plugins can be used. More plugins will be ported.
  
## Open source:
CokeCodes' core system, applications and command tools are all write in Javascript and all **open source**. You can easily make your own tools, addons even applications to aid your work and share with others. You can host your private CokeCodes server, too.

## Incomming more
This version of CokeCodes is just a concept preview. It just proves a all-in-browser development environment is possible. I do not suggest to use CokeCodes as real development tool for now. More features are incomming, check the **Roadmap** below and stay tuned!

## Dev road map:
- **Overall**:
	- Better mobile devices (phones and tablets) support
	- Better JSX/ TS edit support
	- **HMR** support for React and VUE 
	- More documents  
	- Cloud disk allow member access
	- Port **Emscripten** or **CLang** to enable **C++** and other WASM developments
	- **Python** support based on **Pyodide**
	- rollup watch feature
	- node naked support
	
- **File system/ Diskit**:
	- **watch** changes callback
	- File **sync access** solution
	- Sync disk with other repository like GitHub, DropBox
	- Sync disk with locale folder  
	
- **CCEdit**:
	- Migrate to **CodeMirror 6** 
	- Settings, themes, night mode...
	- Support more coding language (JSX, TS, PY, C/C++, Java...)
	- Support collaborate coding
	- **Addon-Cody**: powerful WYSWYG UI-Builder tool behind the major CokeCodes apps.

- **Terminal**
	- Support |grep and > operation
	- Upgrade commands' usage more like UNIX
	- Port more commands from UNIX
	
- **Tools, utility packages**:
	- Port **Babel**, **webpack** and more utilities to have better support React/ VUE projects.
	- Server mockup/develop mechanism with database simulator
	- Self-host CokeCodes server setup guide.
	- Mobile app wrap and publish tool
	- **CCCompare**: "Beyond Compare" like compare application, "Beyond Compare" is one of my favorite apps for all times.

## Like the idea?
CokeCodes is a hobby project. Although very simple and rough, it is indeed working and looks really promising. My earlier web/app development tool chain is node+WebStorm, now my work is done 90% in browser. Hope with new incomming features, it hits 100%!  
If you like **work in browser**, have ideas to improve, welcome to contact me at: pxavdpro@gmail.com.
