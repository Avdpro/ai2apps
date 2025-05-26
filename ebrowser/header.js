import {makeButton} from "./button.js"

function makeHeaderBar (browser) {
	const header = document.createElement('div')
	header.style.display = 'flex'
	header.style.flexDirection = 'row'
	header.style.alignItems = 'center'
	header.style.width = '100%'
	header.style.height = '40px'
	header.style.paddingLeft = '72px'
	header.style.paddingRight = '8px'
	header.style.boxSizing = 'border-box' // 确保 padding 不影响总宽度
	header.style.background = '#cde' // 可选：背景方便观察
	
	const btnNewTab=makeButton({
		width:30,height:30,imageUrl:"add.svg",bgColor:"#303030",tipText:"",padding:6,
		onClick:()=>{
			browser.newTab(-2);
		}
	});
	btnNewTab.style.zIndex="2";
	header.appendChild(btnNewTab);
	header.eBtnNewTab=btnNewTab;
	return header;
}

export default makeHeaderBar
export { makeHeaderBar }