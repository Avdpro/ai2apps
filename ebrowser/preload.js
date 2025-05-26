const { contextBridge, ipcRenderer } = require('electron');

//Tab management API:
contextBridge.exposeInMainWorld('tabApi', {
	//Page=>Browser: Browser page ready:
	browserReady: () => ipcRenderer.send('browser-ready'),

	//Browser->Page: 打开新tab
	onNewTab: (callback) => ipcRenderer.on('new-tab', (_, url) => callback(url)),
	
	//Page=>Browser: 新tab已创建
	newTab: (url,index) => ipcRenderer.send('new-tab', url, index),
	
	//Page=>Browser: 当前tab已改变
	focusTab: (index) => ipcRenderer.send('focus-tab', index),
	
	//Page=>Browser: 关闭指定tab
	closeTab: (index) => ipcRenderer.send('close-tab', index),
	
	//Page=>Browser: 调整Tab顺序
	moveTab: (fromIndex,toIndex) => ipcRenderer.send('move-tab', fromIndex, toIndex),
	
	//Page=>Browser: 调整Tab顺序
	titleChanged: () => ipcRenderer.send('title-changed'),

	//Page=>Browser: 刷新网页
	reloadPage:()=>ipcRenderer.send('reload-page'),
	
	//Page=>Browser: 当前页面前往指定网址
	gotoUrl:(url)=>ipcRenderer.send('goto-url',url),
	
	//Browser=>Page: 页面信息
	onPageInfo: (callback) => ipcRenderer.on('page-info', (_, vo) => callback(vo.index,vo.url,vo.title,vo.icon)),

	//Browser=>Page: 设置当前页面
	onFocusTab: (callback) => ipcRenderer.on('focus-tab', (_, index) => callback(index)),
	
	//Browser=>Page: 关闭指定页面
	onCloseTab:(callback)=>ipcRenderer.on('close-tab', (_, index) => callback(index)),

	//Browser=>Page: 关闭当前页面
	onCloseFocusTab:(callback)=>ipcRenderer.on('close-focused-tab', (_) => callback()),
	
	//Page=>Browser: 打开当前网页的DebugUI
	debugPage:(index)=>ipcRenderer.send('debug-page',index),

});

//Trace page title changes:
contextBridge.exposeInMainWorld('titleWatcher', {
	traceTitleChange: () => {
		const titleElement = document.querySelector('title');
		if (!titleElement) return;
		
		const observer = new MutationObserver(() => {
			ipcRenderer.send('title-changed', document.title); // 可选：发消息到主进程
		});
		
		observer.observe(titleElement, {
			subtree: true,
			childList: true,
			characterData: true
		});
	}
});
