import {WebDriveApp} from "./WebDriveSys.mjs";
import KeyCodes from "./KeyCodes.mjs";

async function sleep(time){
	let func,pms;
	pms=new Promise((resolve,reject)=>{
		setTimeout(resolve,time);
	});
	return pms;
}

async function getPromiseState(promise, timeout = 0) {
	let fulfilled = Symbol('fulfilled');
	let rejected = Symbol('rejected');
	
	const result = await Promise.race([
		promise.then(() => fulfilled).catch(() => rejected),
		new Promise((resolve) => setTimeout(resolve, timeout))
	]);
	
	if (result === fulfilled) return 'fulfilled';
	if (result === rejected) return 'rejected';
	return 'pending';
}

let webDriveApp=null;
async function TestWebDrive(){
	let page, page2;
	//Test: Open FireFox:
	webDriveApp=new WebDriveApp();
	await webDriveApp.start();
	console.log("WebDiver connected");
	
	//Test read-article:
	{
		page=await webDriveApp.newPage();
		//await page.goto("https://news.sina.com.cn/w/2025-08-27/doc-infnkazv9556466.shtml");
		await page.goto("https://www.fratellowatches.com/exploring-new-territory-with-the-zenith-chronomaster-sport-meteorite/");
		await sleep(3000);
		let article=await page.readArticle();
		console.log(article);
	}
	return;
	
	//Test navi-failed:
	let gotoResult,gotoUrl;
	page=await webDriveApp.newPage();
	try {
		gotoUrl="vcv://nopage/";
		gotoResult = await page.goto(gotoUrl);
		console.log(gotoResult)
	}catch(err){
		console.log("Goto failed: "+gotoUrl);
	}
	try {
		gotoUrl="https://www.google.com/dev/nodoc.html";
		gotoResult = await page.goto(gotoUrl,{timeout:3000});
		console.log(gotoResult)
	}catch(err){
		console.log("Goto failed: "+gotoUrl);
	}
	try {
		gotoUrl="https://www.baidu.com";
		gotoResult = await page.goto(gotoUrl);
		console.log(gotoResult)
	}catch(err){
		console.log("Goto failed: "+gotoUrl);
	}

	//Resize window:
	await page.hideWindow();
	await sleep(3000);
	await page.unhideWindow();
	
	
	//Test: Open web-page
	await page.close();
	page=await webDriveApp.newPage("https://www.baidu.com");
	
	//Test: Get web-page info:
	//console.log("Html:",await page.content());
	console.log("URL:",await page.url());
	console.log("Title:",await page.title());

	//Test: Close page
	console.log("IsClosed:",await page.isClosed());
	console.log("Will close page:");
	await page.close();
	console.log("IsClosed:",await page.isClosed());
	
	//Open again, test: goBack, goForward, reload:
	page=await webDriveApp.newPage("https://www.baidu.com");
	await page.goto("https://www.google.com");
	console.log("URL:",await page.url());
	await page.goBack();
	console.log("URL:",await page.url());
	await page.goForward();
	console.log("URL:",await page.url());
	await page.reload();
	console.log("URL:",await page.url());
	
	//Test: Get frames:
	console.log("Frames:",await page.frames(true));
	
	//Test: evaluate
	await page.close();
	page=await webDriveApp.newPage("https://www.baidu.com");
	await page.evaluate("console.log('Hello from WebDrive.');");
	let obj=await page.evaluateHandle("(document.body)");
	console.log("Call function result: ",await page.callFunction("(obj)=>{return obj.nodeType}",[obj]));
	await page.disown(obj);
	
	//Test: screenshot:
	console.log("Screenshot: ",(await page.screenshot({encoding:"base64"})).substring(0,1024));
	
	//Test: $,$$
	let button=await page.$("#su");
	console.log("Search button: ",button);
	await page.disown(button);
	
	let buttons=await page.$$("#su");
	console.log("Search buttons: ",buttons);
	await page.disown(...buttons);
	
	page2=await webDriveApp.newPage();
	await page.bringToFront();
	
	//Test focus;
	await page.focus(null);
	await page.focus("#kw");
	await page.focus(null);
	let input=await page.$("#kw");
	await page.focus(input);
	
	//Action batches and click:
	await page.focus(null);
	let action=await page.startAction();
	try{
		await page.click("#kw",{smooth:true});
		await sleep(200);
		await page.click("#kw", { offset: { x: -50, y: -50 } });
	}catch (err){
		//Do nothing.
	}
	page.endAction(action);
	
	await sleep(200);
	action=await page.startAction();
	{
		await page.click(input);
	}
	page.endAction(action);
	
	//Type, no action:
	await page.focus(null);
	await page.click(input);
	await page.type(null,"F1官网");
	
	//WaitforNavigation:
	let waitNaviPms,waitIdlePms,waitSelectPms1,waitSelectPms2,waitFunc;
	waitNaviPms=page.waitForNavigation();
	waitIdlePms=page.waitForNetworkIdle();
	console.log("Wait navi: "+await getPromiseState(waitNaviPms));
	console.log("Wait idle: "+await getPromiseState(waitIdlePms));
	page.type(null,KeyCodes.Enter);
	console.log("Wait navi: "+await getPromiseState(waitNaviPms));
	console.log("Wait idle: "+await getPromiseState(waitIdlePms));
	await waitNaviPms;
	console.log("Wait navi: "+await getPromiseState(waitNaviPms));
	console.log("Wait idle: "+await getPromiseState(waitIdlePms));
	console.log("Page url: "+await page.url());
	await waitIdlePms;
	console.log("Wait idle: "+await getPromiseState(waitIdlePms));
	waitSelectPms1=page.waitForSelector("#avdpro",{timeout:50});
	waitSelectPms2=page.waitForSelector("#kw");
	await sleep(1000);
	console.log("Wait selector1: "+await getPromiseState(waitSelectPms1));
	console.log("Wait selector2: "+await getPromiseState(waitSelectPms2));
	waitFunc=page.waitForFunction(function(time){
		return Date.now()-time>5000;
	},{},[Date.now()]);
	await sleep(1000);
	console.log("Wait function: "+await getPromiseState(waitFunc));
	await waitFunc;
	console.log("Wait function: "+await getPromiseState(waitFunc));
	
	//Wait for common dialog:
	let waitDlgPms,dlg;
	await page.close();
	page=await webDriveApp.newPage("https://www.baidu.com");
	waitDlgPms=page.waitForDialog();
	console.log("Wait dialog: "+await getPromiseState(waitDlgPms));
	page.evaluate("console.log('Dialog result: '+window.confirm('Dialog1'));");
	console.log("Wait dialog: "+await getPromiseState(waitDlgPms));
	dlg=await waitDlgPms;
	console.log("Dialog: "+dlg);
	dlg.reject();
	
	waitDlgPms=page.waitForDialog();
	console.log("Wait dialog: "+await getPromiseState(waitDlgPms));
	page.evaluate("console.log('Dialog result: '+window.prompt('Dialog2','Input text'));");
	console.log("Wait dialog: "+await getPromiseState(waitDlgPms));
	dlg=await waitDlgPms;
	console.log("Dialog: "+dlg);
	dlg.accept("Hello WebDrive!");
	
	//Wait for file dialog:
	waitDlgPms=page.waitForFileChooser();
	console.log("Wait file dialog: "+await getPromiseState(waitDlgPms));
	page.evaluate(`
      const input = document.createElement('input');
      input.type = 'file';
      input.onchange = () => {
        const file = input.files[0];
        if (file) {
          console.log('你选择的文件名是：', file.name);
        } else {
          console.log('没有选择任何文件。');
        }
      };
      input.click();
	`);
	dlg=await waitDlgPms;
	if(dlg){
		await dlg.accept("/Users/avdpropang/sdk/cchome/home/README.md");
	}
	
	//Paste text:
	page=await webDriveApp.newPage("https://www.baidu.com");
	await page.focus("#kw");
	await page.pasteText("NBA官网");
	await page.clearInputByKey();
	await page.pasteText("F1官网");
	await page.pasteText("NBA官网",{replace:true});
}
export default TestWebDrive;