import {makeButton} from "./button.js";

let dragIdx=-1;

function makeTabButton(browser,width,height){
	const tab = document.createElement('div');
	tab.orgHeight=height;
	tab.style.position = 'relative';
	tab.style.width = width + 'px';
	tab.style.height = height + 'px';
	tab.style.flex = '0 1 auto';
	tab.style.display = 'flex';
	tab.style.flexDirection = 'row';
	tab.style.alignItems = 'center';
	tab.style.paddingLeft = '6px';
	tab.style.paddingRight = '6px';
	tab.style.marginRight="10px";
	tab.style.color="black";
	tab.eBrowser=browser;
	tab.eTabIdx=-1;
	tab.style['-webkit-app-region'] = 'no-drag';
	tab.style.zIndex="1";
	tab.setAttribute('draggable', 'true');
	
	const bgBox = document.createElement('div');
	bgBox.style.position = 'absolute';
	bgBox.style.left = '0';
	bgBox.style.top = '0';
	bgBox.style.width = '100%';
	bgBox.style.height = '100%';
	bgBox.style.borderRadius = '10px';
	bgBox.style.backgroundColor = "#003";
	bgBox.style.opacity = '0';
	bgBox.style.transition = 'opacity 0.2s';
	//bgBox.style.zIndex="0";
	tab.appendChild(bgBox);
	tab.eBgBox=bgBox;
	
	const leftCurve= document.createElement('div');
	leftCurve.style.position = 'absolute';
	leftCurve.style.left = '-18px';
	leftCurve.style.top = '19px';
	leftCurve.style.width = '18px';
	leftCurve.style.height = '18px';
	leftCurve.style.borderRadius = '0px';
	leftCurve.style.display='none';
	leftCurve.style.backgroundColor = "white";
	
	const leftMask= document.createElement('div');
	leftMask.style.position = 'absolute';
	leftMask.style.left = '0px';
	leftMask.style.top = '0px';
	leftMask.style.width = '18px';
	leftMask.style.height = '18px';
	leftMask.style.borderRadius = '0px 0px 18px 0px';
	leftMask.style.backgroundColor = "#cde";
	leftCurve.appendChild(leftMask);
	bgBox.appendChild(leftCurve);
	
	
	const rightCurve= document.createElement('div');
	rightCurve.style.position = 'absolute';
	rightCurve.style.left = '100%';
	rightCurve.style.top = '19px';
	rightCurve.style.width = '18px';
	rightCurve.style.height = '18px';
	rightCurve.style.borderRadius = '0px';
	rightCurve.style.display='none';
	rightCurve.style.backgroundColor = "white";
	
	const rightask= document.createElement('div');
	rightask.style.position = 'absolute';
	rightask.style.left = '0px';
	rightask.style.top = '0px';
	rightask.style.width = '18px';
	rightask.style.height = '18px';
	rightask.style.borderRadius = '0px 0px 0px 18px';
	rightask.style.backgroundColor = "#cde";
	rightCurve.appendChild(rightask);
	bgBox.appendChild(rightCurve);

	const img = document.createElement('img');
	img.src = "web.svg";
	img.style.position = 'relative';
	img.style.width = '20px';
	img.style.height = '20px';
	img.style.marginRight = '5px';
	img.draggable=false;
	//img.style.zIndex="2";
	tab.appendChild(img);
	tab.eImage=img;
	
	const label=document.createElement("div");
	label.style.position = 'relative';
	label.style.display="flex";
	label.style['pointer-events']='none';
	label.style.flexDirection = 'row';
	label.style.alignItems = 'center';
	label.style.flex = '1 1 auto';
	label.style.height='100%';
	label.style.overflow = 'hidden';
	label.style.fontSize = '12px';
	label.style['white-space']='nowrap';
	label.style['min-width']='0';
	//label.style.zIndex="2";
	//label.style['text-overflow'] = 'clip';
	label.innerHTML=`<span style="position: absolute">New page</span>`;
	tab.appendChild(label);
	tab.eLabel=label;
	
	
	const gap=document.createElement("div");
	gap.style.position = 'absolute';
	gap.style.left = '100%';
	gap.style.height = '50%';
	gap.style.width = '2px';
	gap.style.background='rgba(0,0,0,0.3)';
	//gap.style.zIndex="2";
	tab.appendChild(gap);
	tab.eGap=gap;
	
	const btn=makeButton({
		width:20,height:20,imageUrl:"close.svg",tipText:"",padding:2,bgColor:"#303030",
		onClick:()=>{
			browser.tryCloseTab(tab);
		}
	});
	btn.style.zIndex="2";
	tab.appendChild(btn);
	tab.eCloseBtn=btn;
	
	let currentState = 'up';
	let isMouseDown = false;
	
	function setState(state) {
		currentState = state;
		if (state === 'up') {
			bgBox.style.opacity = '0';
			gap.style.opacity="1";
			bgBox.style.background='black';
			bgBox.style.height=tab.orgHeight+"px";
			tab.style.paddingTop='0px';
			leftCurve.style.display='none';
			rightCurve.style.display='none';
			tab.style.zIndex="1";
			//tip.style.display = 'none';
		} else if (state === 'hover') {
			bgBox.style.opacity = '0.1';
			gap.style.opacity="0";
			bgBox.style.background='black';
			bgBox.style.height=tab.orgHeight+"px";
			tab.style.paddingTop='0px';
			leftCurve.style.display='none';
			rightCurve.style.display='none';
			tab.style.zIndex="1";
		} else if (state === 'down') {
			bgBox.style.opacity = '0.3';
			bgBox.style.background='black';
			gap.style.opacity="0";
			bgBox.style.height=tab.orgHeight+"px";
			tab.style.paddingTop='0px';
			leftCurve.style.display='none';
			rightCurve.style.display='none';
			tab.style.zIndex="1";
		} else if(state==='focus'){
			bgBox.style.opacity = '1';
			bgBox.style.background='white';
			bgBox.style.height='calc(100% + 40px)'
			gap.style.opacity="0";
			tab.style.paddingTop='3px';
			leftCurve.style.display='block';
			rightCurve.style.display='block';
			tab.style.zIndex="0";
		}
	}
	
	function setPageInfo(title,icon,url){
		label.innerHTML=`<span style="position: absolute">${title}</span>`;
		img.src=icon||"web.svg";
		tab.eTabUrl=url;
	}
	
	tab.addEventListener('mouseenter', () => {
		if (currentState !== 'focus') setState('hover');
	});
	
	tab.addEventListener('mouseleave', () => {
		if (currentState !== 'focus') {
			isMouseDown = false;
			setState('up');
		}
	});
	
	tab.addEventListener('mousedown', (evt) => {
		if (currentState !== 'focus') {
			isMouseDown = true;
			browser.focusTab(tab.eTabIdx);
			evt.preventDefault();
			evt.stopPropagation();
//			setState('down');
		}
	});
	
	tab.addEventListener('mouseup', (evt) => {
		if (currentState !== 'focus' && isMouseDown) {
			setState('hover');
			//browser.focusTab(tab.eTabIdx);
			//evt.preventDefault();
			//evt.stopPropagation();
		}
		isMouseDown = false;
	});
	
	//Drag tab:
	{
		// 拖拽事件绑定
		tab.addEventListener('dragstart', (e) => {
			const dragPreview = document.createElement('div');
			dragPreview.style.position = 'absolute';
			dragPreview.style.top = '-1000px'; // 不显示在页面中
			dragPreview.style.left = '-1000px';
			dragPreview.style.padding = '1px 1px';
			dragPreview.style.background = 'rgba(0, 223, 255, 0.5)';
			dragPreview.style.borderRadius = '10px';
			dragPreview.style.width = `${tab.offsetWidth-2}px`;
			dragPreview.style.height = `30px`;
			dragPreview.style.pointerEvents = 'none';
			dragPreview.style.boxSizing = 'border-box' // 确保 padding 不影响总宽度
			dragPreview.style.border='2px solid #000';
			
			dragIdx=tab.eTabIdx;
			
			document.body.appendChild(dragPreview);
			
			// 设置这个半透明矩形为拖拽图像
			e.dataTransfer.setDragImage(dragPreview, tab.offsetWidth / 2, 15);
			
			// 清理（延迟一下让拖拽启动）
			setTimeout(() => {
				document.body.removeChild(dragPreview);
			}, 0);
			
			//e.dataTransfer.setData('text/plain', tab.eTabIdx);
			tab.setState('over');
		});
		
		tab.addEventListener('dragend', () => {
			tab.setState('focus');
		});
		
		tab.addEventListener('dragover', (e) => {
			e.preventDefault(); // 允许放置
			tab.classList.add('drag-over');
			tab.setState('down');
		});
		
		tab.addEventListener('dragleave', () => {
			tab.classList.remove('drag-over');
			tab.setState('up');
		});
		
		tab.addEventListener('drop', (e) => {
			e.preventDefault();
			const fromIndex = dragIdx;
			const toIndex = parseInt(tab.eTabIdx);
			browser.reorderTabs(fromIndex, toIndex);
		});
	}
	
	//Bind apis:
	tab.setState = setState;
	tab.setPageInfo=setPageInfo;
	return tab;
}

export default makeTabButton;
export {makeTabButton};