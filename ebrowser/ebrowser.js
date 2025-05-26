import {makeHeaderBar} from "./header.js";
import {makeNaviBar} from "./navi.js";
import {makeTabButton} from "./tabbutton.js";

//***************************************************************************
//Browser window:
//***************************************************************************
let EBrowser,eBrowser,browser;
//---------------------------------------------------------------------------
EBrowser=function(){
	this.header=null;
	this.navi=null;
	this.tabs=[];
	
	this.focusedTab=null;
	
	this.createUi();
}
eBrowser=EBrowser.prototype={};

//***************************************************************************
//Create, load page:
//***************************************************************************
{
	//-----------------------------------------------------------------------
	eBrowser.createUi = function () {
		let header,navi;
		this.header=header=makeHeaderBar(this);
		this.navi=navi=makeNaviBar(this);
		document.body.appendChild(header);
		document.body.appendChild(navi);
	};
	
	//-----------------------------------------------------------------------
	eBrowser.openPage = async function (url) {
		//TODO: Code this:
	};
}

//***************************************************************************
//Tabs
//***************************************************************************
{
	//-----------------------------------------------------------------------
	eBrowser._refreshTabIdx=function(){
		let tabs,i,n;
		tabs=this.tabs;
		n=tabs.length;
		for(i=0;i<n;i++){
			tabs[i].eTabIdx=i;
		}
	};
	//-----------------------------------------------------------------------
	eBrowser.newTab=function(idx){
		let tab;
		tab=this.addTab(idx||-1);
		window.tabApi.newTab(null,tab.eTabIdx);
	};
	
	//-----------------------------------------------------------------------
	eBrowser.addTab=function(idx=-1) {
		let tabs,tab;
		tabs=this.tabs;
		tab=makeTabButton(this,200,30);
		if(idx>=0) {
			let nextTab;
			tabs.splice(idx,0,tab);
			this._refreshTabIdx();
			nextTab=tabs[idx+1];
			if(nextTab){
			
			}else{
				this.header.insertBefore(tab,this.header.eBtnNewTab);
			}
		}else{
			if(this.focusedTab && idx!==-2){
				let nextElmt;
				nextElmt=this.focusedTab.nextSibling;
				if(nextElmt){
					if(nextElmt.eTabIdx>=0){
						tabs.splice(nextElmt.eTabIdx,0,tab);
						this.header.insertBefore(tab,nextElmt);
						this._refreshTabIdx();
						return tab;
					}
				}
			}
			tab.eTabIdx = this.tabs.length;
			this.header.insertBefore(tab,this.header.eBtnNewTab);
			tabs.push(tab);
		}
		return tab;
	};
	
	//-----------------------------------------------------------------------
	eBrowser.activeTab=eBrowser.focusTab=function(idx){
		let tabs,tab,navi;
		tabs=this.tabs;
		tab=tabs[idx];
		if(!tab){
			return;
		}
		if(tab ===this.focusedTab){
			return;
		}
		if(this.focusedTab){
			this.focusedTab.setState('up');
		}
		tab.setState('focus');
		this.focusedTab=tab;
		navi = this.navi;
		navi.setUrl(tab.eTabUrl||"");
		//TODO: Show focus frame:
		window.tabApi.focusTab(tab.eTabIdx);
	};
	
	//-----------------------------------------------------------------------
	eBrowser.pageInfo=function(idx,url,title,icon){
		let tab,navi;
		this._refreshTabIdx();
		tab=this.tabs[idx];
		if(!tab){
			return;
		}
		tab.setPageInfo(title,icon,url);
		if(tab===this.focusedTab) {
			navi = this.navi;
			navi.setUrl(url);
		}
	};
	
	//-----------------------------------------------------------------------
	eBrowser.reorderTabs=function(fromIdx,toIdx) {
		if(fromIdx===toIdx){
			return;
		}
		const tabs=this.tabs;
		const tab1=tabs[fromIdx];
		const tab2=tabs[toIdx];
		if(tab1&&tab2){
			const header=this.header;
			tabs.splice(fromIdx, 1);
			tabs.splice(toIdx, 0, tab1);
			tabs.forEach((tab, newIndex) => {
				tab.eTabIdx = newIndex;
				header.appendChild(tab);
			});
			header.appendChild(header.eBtnNewTab);
			window.tabApi.moveTab(fromIdx,toIdx);
		}
	};
	
	//-----------------------------------------------------------------------
	eBrowser.showPageDebug=function(){
		let tab;
		this._refreshTabIdx();
		tab=this.focusedTab;
		if(tab) {
			window.tabApi.debugPage(tab.eTabIdx);
		}
	};
	
	//-----------------------------------------------------------------------
	eBrowser.tryCloseTab=function(tab){
		let idx;
		this._refreshTabIdx();
		idx=tab.eTabIdx;
		window.tabApi.closeTab(idx);
	};
	
	//-----------------------------------------------------------------------
	eBrowser.closeTab=function(idx) {
		let tab;
		if(idx>=0){
			tab=this.tabs[idx];
			if(tab){
				this.tabs.splice(idx,1);
				this.header.removeChild(tab);
				this._refreshTabIdx();
			}
		}else{
			//TODO: Close focused tab
		}
	};
	
	//-----------------------------------------------------------------------
	eBrowser.gotoUrl=function(url){
		window.tabApi.gotoUrl(url);
	};
	
	//-----------------------------------------------------------------------
	eBrowser.reloadCurrentPage=function(){
		window.tabApi.reloadPage();
	};
}

browser=new EBrowser();
window.tabApi.onNewTab((url)=>{
	let tab;
	console.log("Will add a new tab!");
	tab = browser.addTab(-1);
	window.tabApi.newTab(url,tab.eTabIdx);
});

window.tabApi.onPageInfo((index,url,title,icon)=>{
	browser.pageInfo(index,url,title,icon);
});

window.tabApi.onFocusTab((index)=>{
	browser.focusTab(index);
});

window.tabApi.onCloseTab((index)=>{
	browser.closeTab(index);
});


window.tabApi.browserReady();

export default EBrowser;
export {EBrowser,eBrowser};