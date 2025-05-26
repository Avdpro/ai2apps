import{ app, BrowserWindow,BrowserView,ipcMain,screen,Menu,dialog } from "electron";
import pathLib from "path";
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = pathLib.dirname(__filename);
let EBrowserWindow,eBrowserWindow;
let closedBugFix=false;
let closedBugTag=null;
//***************************************************************************
//EBrowserWindow
//***************************************************************************
{
	EBrowserWindow=function(startUrl){
		let win,views;
		const { width:screenWidth, height:screenHeight } = screen.getPrimaryDisplay().workAreaSize;
		let width=parseInt(screenWidth*0.8);
		let height=parseInt(screenHeight*0.8);
		
		width=width<1200?1200:width;
		height=height<800?800:height;
		width=width>screenWidth?screenWidth:width;
		height=height>screenHeight?screenHeight:height;

		this.window=null;
		this.currentViewIndex=-1;
		this.views=views=[];
		
		win=new BrowserWindow({
			width: width,
			height: height,
			titleBarStyle: 'hiddenInset', // 或者 'hidden'
			trafficLightPosition: { x: 10, y: 10 }, // 可以自定义位置（macOS）
			frame: false, // 移除原生标题栏
			webPreferences: {
				preload: pathLib.join(__dirname, 'preload.js'),
			}
		});
		//win.webContents.openDevTools({ mode: 'detach' });
		win.loadFile('ebrowser/ebrowser.html');
		win.eBrowser=this;
		this.window=win;
		
		// IPC：前端要求切换 tab
		ipcMain.on('browser-ready', (event) => {
			const wc=event.sender;
			if(wc!==win.webContents)
				return;
			if(startUrl){
				this.openPage(null,startUrl);
			}
		});

		// IPC：前端要求切换 tab
		ipcMain.on('focus-tab', (event, index) => {
			const wc=event.sender;
			if(wc!==win.webContents)
				return;
			if (index === this.currentViewIndex || !views[index]) return;
			
			if (this.currentViewIndex >= 0) {
				win.removeBrowserView(views[this.currentViewIndex]);
				if(closedBugTag) {
					let list = win.listeners('closed');
					for (let l of list) {
						if (l.toString() === closedBugTag) {
							win.removeListener('closed', l);
						}
					}
				}
			}
			
			this.currentViewIndex = index;
			const view = views[index];
			if(!closedBugFix){
				let list,callback;
				win.setBrowserView(view);
				list=win.listeners('closed');
				callback=list[list.length-1];
				closedBugTag=callback.toString();
				closedBugFix=true;
			}else {
				win.setBrowserView(view);
			}
			
			const [width, height] = win.getContentSize();
			view.setBounds({ x: 0, y: 80, width, height: height - 80 });
			view.setAutoResize({ width: true, height: true });
		});

		//IPC：前端网页里的Tab创建好了：
		ipcMain.on('new-tab', async (event, url, index) => {
			const wc=event.sender;
			if(wc!==win.webContents)
				return;
			console.log("Will open page-view by add-tab.");
			//Create new browserView
			const view = new BrowserView({
				webPreferences: {
					preload: pathLib.join(__dirname, 'preload.js'),  // 指定你的 preload 脚本
					contextIsolation: true,  // 推荐开启
					nodeIntegration: false   // 视情况开启
				}
			});
			this.views.splice(index,0,view);
			this._refreshTabIdx();
			win.webContents.send('focus-tab', index);

			view.webContents.myPageView=view;
			//Config browserView:
			view.webContents.on('did-finish-load', async () => {
				//获得网页的图标和URL，通知前端更新Tab内容
				let title,url,icon;
				url = view.webContents.getURL();
				title=view.webContents.getTitle();
				icon=await view.webContents.executeJavaScript(`
  					(async () => {
	  					async function urlToDataURL(url) {
							const response = await fetch(url);
							const blob = await response.blob();
							return await new Promise((resolve, reject) => {
								const reader = new FileReader();
								reader.onloadend = () => resolve(reader.result);
								reader.onerror = reject;
								reader.readAsDataURL(blob);
							});
						}
						
						const rels = ['icon', 'shortcut icon', 'apple-touch-icon'];
						for (const rel of rels) {
							const link = document.querySelector(\`link[rel="\${rel}"]\`);
							if (link) return await urlToDataURL(link.href);
						}
						return null;
					})()`);
				win.webContents.send('page-info', {index:view.eTabIdx,url,title,icon});
				await view.webContents.executeJavaScript(`window.titleWatcher.traceTitleChange();`);
			});
			
			//这个不好使
			/*
			view.webContents.on('new-window', (event, url) => {
				event.preventDefault();
				console.log('尝试打开新窗口: ', url);
				this.openPage(null,url);
			});*/
			
			//这个好使
			view.webContents.setWindowOpenHandler(({ url, features }) => {
				win.webContents.send('new-tab',url||"");
				return {
					action: 'deny',
				};
			});
			
			view.webContents.on('devtools-opened', () => {
				view.eDevtoolsOpen = true;
			});
			
			view.webContents.on('devtools-closed', () => {
				view.eDevtoolsOpen = false;
			});
			
			this.openPage(view,url);
		});

		//PIC： 前端页面点击了关闭Tab按钮:
		ipcMain.on('close-tab',async (event,index)=>{
			const wc=event.sender;
			if(wc!==win.webContents)
				return;
			const view=views[index];
			const curView= win.getBrowserView();
			let nextView=null;
			if(!view){
				return;
			}
			
			//TODO: Ask and check close
			
			this._refreshTabIdx();
			win.webContents.send('close-tab', view.eTabIdx);
			views.splice(view.eTabIdx,1);
			this._refreshTabIdx();
			
			
			view.webContents.close();
			if(view===curView){
				
				nextView=views[view.eTabIdx]||views[0];
				if(nextView){
					win.setBrowserView(nextView);
					this.currentViewIndex=nextView.eTabIdx;
					win.webContents.send('focus-tab', nextView.eTabIdx);
					//const [width, height] = win.getContentSize();
					//nextView.setBounds({ x: 0, y: 50, width, height: height - 50 });
					//nextView.setAutoResize({ width: true, height: true });
				}else{
					//TODO: Close this window
					win.close();
				}
			}
		});
		
		//PIC： 前端页面移动了Tab
		ipcMain.on('move-tab',async (event,fromIdx,toIdx)=> {
			const wc = event.sender;
			if (wc !== win.webContents)
				return;
			this._refreshTabIdx();
			let view=views[fromIdx];
			views.splice(fromIdx,1);
			views.splice(toIdx,0,view);
			this.currentViewIndex=toIdx;
			this._refreshTabIdx();
		});
		
		ipcMain.on('debug-page',async (event,index)=> {
			const wc = event.sender;
			if (wc !== win.webContents)
				return;
			const view = views[index];
			if(view.eDevtoolsOpen){
				view.webContents.closeDevTools();
			}else {
				view.webContents.openDevTools({ mode: 'right' });
			}
		});
		
		ipcMain.on('title-changed',async(event)=>{
			let title,url,icon;
			this._refreshTabIdx();
			const wc=event.sender;
			const view=wc.myPageView;
			if(!view){
				return;
			}
			//获得网页的图标和URL，通知前端更新Tab内容
			url = wc.getURL();
			title=wc.getTitle();
			icon=await wc.executeJavaScript(`
  					(async () => {
	  					async function urlToDataURL(url) {
							const response = await fetch(url);
							const blob = await response.blob();
							return await new Promise((resolve, reject) => {
								const reader = new FileReader();
								reader.onloadend = () => resolve(reader.result);
								reader.onerror = reject;
								reader.readAsDataURL(blob);
							});
						}
						const rels = ['icon', 'shortcut icon', 'apple-touch-icon'];
						for (const rel of rels) {
							const link = document.querySelector(\`link[rel="\${rel}"]\`);
							if (link) return await urlToDataURL(link.href);
						}
						return null;
					})()`);
			win.webContents.send('page-info', {index:view.eTabIdx,url,title,icon});
		});
		
		ipcMain.on('reload-page', (event) => {
			const wc = event.sender;
			if (wc !== win.webContents)
				return;
			this.reloadCurrentPage();
		});
		
		ipcMain.on('goto-url', (event, url) => {
			const wc = event.sender;
			if (wc !== win.webContents)
				return;
			this.gotoUrl(url);
		});
		
		
		win.on('close', (e) => {
			// 拦截关闭行为
			if(views.length>1) {
				e.preventDefault();

				const choice = dialog.showMessageBoxSync(win, {
					type: 'question',
					buttons: ['Cancel', 'Close'],
					defaultId: 1,
					cancelId: 0,
					title: 'Confirm to Close',
					message: 'There are more than one tabs opening, are you sure to close all the tabs?',
				});
				
				if (choice === 1) {
					win.destroy();
				}
			}
		});
		
		//替换默认是刷新功能:
		win.webContents.on('will-navigate', (event, url) => {
			if (url === win.webContents.getURL()) {
				event.preventDefault();
			}
		});
		
	}
	eBrowserWindow=EBrowserWindow.prototype={};
	
	//-----------------------------------------------------------------------
	eBrowserWindow._refreshTabIdx=function(){
		let views,i,n;
		views=this.views;
		n=views.length;
		for(i=0;i<n;i++){
			views[i].eTabIdx=i;
		}
	};

	//-----------------------------------------------------------------------
	eBrowserWindow.newTab=function(index,url){
		this.window.webContents.send('new-tab',null);
	};
	
	//-----------------------------------------------------------------------
	eBrowserWindow.openPage=function(view,url){
		if(view){
			if(url) {
				view.webContents.loadURL(url);
			}
		}else{//Open in new tab:
			this.window.webContents.send('new-tab', url);
		}
	};
	
	//-----------------------------------------------------------------------
	eBrowserWindow.gotoUrl=function(url){
		let views,view;
		views=this.views;
		view=views[this.currentViewIndex];
		if(view){
			view.webContents.loadURL(url);
		}
	};
	
	//-----------------------------------------------------------------------
	eBrowserWindow.reloadCurrentPage=function(){
		let views,view;
		views=this.views;
		view=views[this.currentViewIndex];
		if(view){
			view.webContents.reload();
		}
	};
	
	//-----------------------------------------------------------------------
	eBrowserWindow.closeTab=function(index){
		const win=this.window;
		const views=this.views;
		if(!(index>=0)){
			index=this.currentViewIndex;
		}
		const view=views[index];
		const curView= win.getBrowserView();
		let nextView=null;
		if(!view){
			return;
		}
		
		//TODO: Ask and check close
		
		this._refreshTabIdx();
		win.webContents.send('close-tab', view.eTabIdx);
		views.splice(view.eTabIdx,1);
		this._refreshTabIdx();
		
		
		view.webContents.close();
		if(view===curView){
			
			nextView=views[view.eTabIdx]||views[0];
			if(nextView){
				win.setBrowserView(nextView);
				this.currentViewIndex=nextView.eTabIdx;
				win.webContents.send('focus-tab', nextView.eTabIdx);
			}else{
				win.close();
			}
		}
	};
}
export default EBrowserWindow;
export {EBrowserWindow,eBrowserWindow};