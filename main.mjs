import{ app, BrowserWindow,nativeImage,Tray,screen } from "electron";
import { spawn } from 'child_process';
import { fileURLToPath } from "url";
import pathLib from "path";

let mainWindow=null;
const __filename = fileURLToPath(import.meta.url);
const __dirname = pathLib.dirname(fileURLToPath(import.meta.url));
const isPackaged = app.isPackaged;
const basePath = isPackaged ? pathLib.dirname(app.getPath('exe')) : __dirname;

const nodeBin = pathLib.join(basePath, 'my-node/bin/node');
const serverJs = pathLib.join(basePath, 'start.js');

const iconPath = pathLib.join(__dirname, 'icon/icon.png'); // 支持 png、icns
const trayIconPath = pathLib.join(__dirname, 'icon/iconTemplate@4x.png'); // 支持 png、icns
const image = nativeImage.createFromPath(iconPath);
const trayImage = nativeImage.createFromPath(trayIconPath);

let tray=null;


function setupWindow(win) {
	win.webContents.setWindowOpenHandler(({ url, features }) => {
		const { width:screenWidth, height:screenHeight } = screen.getPrimaryDisplay().workAreaSize;
		
		const widthMatch = features.match(/width=(\d+)/);
		const heightMatch = features.match(/height=(\d+)/);
		const width = widthMatch ? parseInt(widthMatch[1]) : parseInt(screenWidth*0.8);//1200;
		const height = heightMatch ? parseInt(heightMatch[1]) : parseInt(screenHeight*0.8);//800;
		
		return {
			action: 'allow',
			overrideBrowserWindowOptions: {
				width,
				height,
				webPreferences: {
					preload: __dirname + '/preload.js',
				}
			}
		};
	});
	
	// 当该窗口打开了新窗口时，拿到新窗口并再次设置 handler
	win.webContents.on('did-create-window', (newWin, details) => {
		if (newWin) setupWindow(newWin); // 递归设置
	});
}
function createWindow() {
	mainWindow = new BrowserWindow({
		width: 1200,
		height: 800,
		//titleBarStyle: 'hidden',
		webPreferences: {
			nodeIntegration: true, // 允许在渲染进程中使用 Node.js
			contextIsolation: false
		}
	});
	//mainWindow.loadURL("file://" + __dirname + "/index.html"); // 载入 UI
	mainWindow.loadURL("http://localhost:3015"); // 载入 UI

	// 控制所有 window.open() 创建的新窗口
	setupWindow(mainWindow);
}

function startServerAndThenWindow() {
	if (process.platform === 'darwin') {
		app.dock.setIcon(image);
		
		trayImage.setTemplateImage(true);
		tray = new Tray(trayIconPath); // macOS 顶栏图标
		
		tray.setToolTip('AI2Apps');
		tray.on('click', () => {
			if (mainWindow.isVisible()) {
				mainWindow.focus();
			} else {
				mainWindow.show();
				mainWindow.focus();
			}
		});
	}
	
	
	
	const child = spawn(nodeBin, [serverJs]);
	
	child.stdout.on('data', (data) => {
		const text = data.toString();
		console.log('[server]', text);
		
		if (text.includes('READY:')) {
			createWindow();
		}
	});
	
	child.stderr.on('data', (data) => {
		console.error('[server error]', data.toString());
	});
	
	child.on('exit', (code) => {
		console.log('Server exited with code', code);
	});
	
	// 可选：退出 app 时 kill 掉子进程
	app.on('before-quit', () => {
		child.kill();
	});
}

app.whenReady().then(startServerAndThenWindow);