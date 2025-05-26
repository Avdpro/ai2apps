import {makeButton} from "./button.js"


function makeAddressBar(placeholder = "Enter website URL",onEnter) {
	const wrapper = document.createElement("div");
	wrapper.style.cssText = `
    display: flex;
    align-items: center;
    padding: 0 16px;
    height: 32px;
    border: 2px solid #f0f2f4;
    border-radius: 16px;
    background-color: #f0f2f4;
    max-width: 600px;
    width: 100%;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial;
    margin-right:5px;
    margin-left:5px;
	box-sizing: border-box;
  `;
	
	const input = document.createElement("input");
	input.type = "text";
	input.placeholder = placeholder;
	input.style.cssText = `
    flex: 1;
    border: none;
    outline: none;
    font-size: 15px;
    background: transparent;
    padding: 0;
    margin: 0;
  `;
	input.addEventListener("focus", () => input.select());
	input.addEventListener("keydown", (e) => {
		if (e.isComposing) return; // 忽略输入法中按键
		if (e.key === "Enter") {
			onEnter(input.value);
		}
	});
	
	input.addEventListener('focus', () => {
		wrapper.style['background-color']='#fff';
		wrapper.style['border']='2px solid #00f';
	});
	
	input.addEventListener('blur', () => {
		wrapper.style['background-color']='#f0f2f4';
		wrapper.style['border']='2px solid #f0f2f4';
	});
	
	wrapper.setUrl=function(url){
		input.value=url;
	}
	wrapper.appendChild(input);
	return wrapper;
}
function makeNaviBar (browser) {
	const navi = document.createElement('div')
	navi.style.display = 'flex'
	navi.style.flexDirection = 'row'
	navi.style.alignItems = 'center'
	navi.style.position = 'absolute';
	navi.style.left = '0px';
	navi.style.top = '40px';
	navi.style.width = '100%'
	navi.style.height = '40px'
	navi.style.paddingLeft = '8px'
	navi.style.paddingRight = '8px'
	navi.style.boxSizing = 'border-box' // 确保 padding 不影响总宽度
	navi.style.background = '#ffffff' // 可选：背景方便观察
	navi.style.borderBottom = "1px solid #ccc";
	navi.style.zIndex="2";
	
	
	const btnReload=makeButton({
		width:24,height:24,imageUrl:"reload.svg",bgColor:"#303030",tipText:"",padding:2,
		onClick:()=>{
			//TODO: Code this:
			browser.reloadCurrentPage();
		}
	});
	navi.appendChild(btnReload);
	navi.eBtnReload=btnReload;
	
	let editAddr=makeAddressBar("Enter page URL",(url)=>{
		browser.gotoUrl(url);
	});
	navi.appendChild(editAddr);
	navi.eEditAddr=editAddr;
	
	const btnDebug=makeButton({
		width:24,height:24,imageUrl:"debug.svg",bgColor:"#303030",tipText:"",padding:2,
		onClick:()=>{
			browser.showPageDebug();
		}
	});
	navi.appendChild(btnDebug);
	navi.eBtnDebug=btnDebug;
	
	navi.setUrl=function(url){
		editAddr.setUrl(url);
	}
	return navi;
}

export default makeNaviBar;
export {makeNaviBar};
