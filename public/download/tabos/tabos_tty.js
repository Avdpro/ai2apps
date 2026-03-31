import {tabFS as JAXDisk} from "/@tabos";
import {Buffer} from "./utils/buffer.js";
import {Writable,Readable} from "./utils/stream.js";
import {EventEmitter} from "./utils/events.js";

//----------------------------------------------------------------------------
class TTYStdOut extends Writable{
	constructor(tty){
		super();
		this.isTTY=true;
		this.tty=tty;
	}
	_write(chunk,encoding="utf8",callback=null){
		if(Buffer.isBuffer(chunk)){
			if(this.tty) {
				this.tty.textOut(""+chunk);
			}
			
		}else if(typeof(chunk)==="string"){
			if(this.tty) {
				this.tty.textOut(chunk);
			}
		}
		if(callback) {
			callback();
			//setTimeout(() => {callback();}, 0);
		}
	}
	_writev(chunks, callback){
		chunks.forEach(chunk=>{this._write(chunk.chunk,chunk.encoding)});
		if(callback) {
			callback();
			//setTimeout(() => {callback();}, 0);
		}
	}
	get columns(){
		return 80;
	}
	get rows(){
		return 25;
	}
	clearLine(dir, callback){
		if(this.tty){
			this.tty.clearLine(dir);
		}
		if(callback) {
			callback();
			//setTimeout(() => {callback();}, 0);
		}
	}
	clearScreenDown(callback){
		if(this.tty){
			this.tty.clearScreenDown();
		}
		if(callback) {
			callback();
			//setTimeout(() => {callback();}, 0);
		}
	}
	cursorTo(x, y, callback){
		if(this.tty){
			this.tty.cursorTo(x,y);
		}
		if(callback) {
			callback();
			//setTimeout(() => {callback();}, 0);
		}
	}
	getColorDepth(){
		return 1;
	}
	getWindowSize(){
		return [80,25];
	}
	hasColors(){
		return true;
	}
	moveCursor(dx,dy,callback){
		if(this.tty){
			this.tty.moveCursor(dx,dy);
		}
		if(callback) {
			callback();
			//setTimeout(() => {callback();}, 0);
		}
	}
	
}

//----------------------------------------------------------------------------
class TTYStdIn extends Readable{
	constructor (options){
		super(options);
	}
	_read(size){
		//TODO: Start read：
	}
}

//----------------------------------------------------------------------------
const regSearchEscEnd=/[A-Za-z]/g;
function index2Color(c){
	let r,g,b;
	switch(c)
	{
		case 0:
			return "rgba(0,0,0,1)";
		case 1:
			return "rgba(128,0,0,1)";
		case 2:
			return "rgba(0,128,0,1)";
		case 3:
			return "rgba(128,128,0,1)";
		case 4:
			return "rgba(0,0,128,1)";
		case 5:
			return "rgba(128,0,128,1)";
		case 6:
			return "rgba(0,128,128,1)";
		case 7:
			return "rgba(192,192,192,1)";
		//Bright:
		case 8:
			return "rgba(128,128,128,1)";
		case 9:
			return "rgba(255,0,0,1)";
		case 10:
			return "rgba(0,255,0,1)";
		case 11:
			return "rgba(255,255,0,1)";
		case 12:
			return "rgba(0,0,255,1)";
		case 13:
			return "rgba(255,0,255,1)";
		case 14:
			return "rgba(0,255,255,1)";
		case 15:
			return "rgba(255,255,255,1)";
	}
	if(c>=232 && c<=255){
		c-=231;
		c=c*10;
		return `rgba(${c},${c},${c},1)`;
	}else if(c<232){
		c-=16;
		b=c%6;
		c=Math.floor(c/6);
		g=c%6;
		c=Math.floor(c/6);
		r=c%6;
		return `rgba(${r},${g},${b},1)`;
	}
	return "rgba(0,0,0,1)";
}

//****************************************************************************
//TTY:
//****************************************************************************
export default class CokeTTY extends EventEmitter
{
	constructor (div,host,inputHeader="coke"){
		super();
		this.div=div;
		this.host=host;
		
		this.lines=[];
		this.divInput=null;
		this.lastLine=null;
		this.inputHeader=inputHeader;
		this.inputPrefix="$>";
		this.segChNum=8;
		this.lineSeq=0;
		this.isInputPassword=false;
		
		this.divInput=null;
		if(div) {
			div.style.overflowY = "scroll";
			div.style.overflowX = "scroll";
		}
		
		this.stdout=new TTYStdOut(this,host);
		this.stdin=new TTYStdIn();
		this.stderr=this.stdout;
		
		this.cursorLine=null;		//Cursor line:
		this.cursorX=0;				//Cursor column:
		
		if(div) {
			this._outLine("");
		}
		this.defColorTxt=this.colorTxt="rgba(0,0,0,1)";
		this.defColorBG=this.colorBG="rgba(255,255,255,0)";
		this.defFontWeight="";
		this.fontWeight="";
	}
	
	//-----------------------------------------------------------------------
	newTextSpan(){
		let span,style;
		span=document.createElement('span');
		style = span.style;
		style.width = "auto";
		style.height = "";
		style.wordBreak = "break-word";
		style.whiteSpace = "pre";
		style.textOverflow = "";
		style.alignSelf = "";
		style.textAlign = "";
		style.fontFamily = "monospace";
		style.fontSize = "12px";
		style.color = this.colorTxt;
		style.fontWeight=this.fontWeight;
		return span;
	}
	
	//-----------------------------------------------------------------------
	parseEscText(text){
		let pts,n;
		pts=text.split(";");
		n=parseInt(pts[0]);
		while(n===0 || n===1){
			pts.shift();
			if(n===0){
				this.colorTxt=this.defColorTxt;
				this.colorBG=this.defColorBG;
				this.fontWeight="";
			}else{
				this.fontWeight="bold";
			}
			if(pts.length) {
				n = parseInt(pts[0]);
			}else {
				this.colorTxt=this.defColorTxt;
				this.colorBG=this.defColorBG;
				return;
			}
		}
		
		if(n===0){//Reset text:
			this.colorTxt=this.defColorTxt;
			this.colorBG=this.defColorBG;
		}else if(n>=30 && n<=37){//Set foreground color
			switch(n){
				case 30://Black
					this.colorTxt="rgba(0,0,0,1)";
					break;
				case 31://Red
					this.colorTxt="rgba(222,56,43,1)";
					break;
				case 32://Green
					this.colorTxt="rgba(57,181,74,1)";
					break;
				case 33://Yellow
					this.colorTxt="rgba(255,199,6,1)";
					break;
				case 34://Blue
					this.colorTxt="rgba(0,111,184,1)";
					break;
				case 35://Magenta
					this.colorTxt="rgba(118,38,113,1)";
					break;
				case 36://Cyan
					this.colorTxt="rgba(44,181,233,1)";
					break;
				case 37://White
					this.colorTxt="rgba(229,229,229,1)";
					break;
			}
		}else if(n===38){//Set foreground color
			let c;
			n=pts[1];
			if(n===5){//256 colors
				c=parseInt(pts[2]);
				this.colorTxt=index2Color(c);
			}else if(n===2){//RGB colors
				this.colorTxt=`rgba(${pts[2]},${pts[3]},${pts[4]},1)`;
			}
		}else if(n===39){
			this.colorTxt=this.defColorTxt;
		}else if(n>=40 && n<=47){//Set background color
			switch(n){
				case 40://Black
					this.colorBG="rgba(1,1,1,1)";
					break;
				case 41://Red
					this.colorBG="rgba(222,56,43,1)";
					break;
				case 42://Green
					this.colorBG="rgba(57,181,74,1)";
					break;
				case 43://Yellow
					this.colorBG="rgba(255,199,6,1)";
					break;
				case 44://Blue
					this.colorBG="rgba(0,111,184,1)";
					break;
				case 45://Magenta
					this.colorBG="rgba(118,38,113,1)";
					break;
				case 46://Cyan
					this.colorBG="rgba(44,181,233,1)";
					break;
				case 47://White
					this.colorBG="rgba(229,229,229,1)";
					break;
			}
		}else if(n===48){//Set background color
			let c;
			n=pts[1];
			if(n===5){//256 colors
				c=parseInt(pts[2]);
				this.colorBG=index2Color(c);
			}else if(n===2){//RGB colors
				this.colorBG=`rgba(${pts[2]},${pts[3]},${pts[4]},1)`;
			}
		}else if(n===49){
			this.colorBG=this.defColorBG;
		}else if(n>=90 && n<=97){//Set light foreground color
			switch(n){
				case 90://Black
					this.colorTxt="rgba(128,128,128,1)";
					break;
				case 91://Red
					this.colorTxt="rgba(255,0,0,1)";
					break;
				case 92://Green
					this.colorTxt="rgba(0,255,0,1)";
					break;
				case 93://Yellow
					this.colorTxt="rgba(255,255,0,1)";
					break;
				case 94://Blue
					this.colorTxt="rgba(0,0,255,1)";
					break;
				case 95://Magenta
					this.colorTxt="rgba(255,0,255,1)";
					break;
				case 96://Cyan
					this.colorTxt="rgba(0,255,255,1)";
					break;
				case 97://White
					this.colorTxt="rgba(255,255,255,1)";
					break;
			}
		}else if(n>=100 && n<=107){//Set light background color
			switch(n){
				case 100://Black
					this.colorBG="rgba(128,128,128,1)";
					break;
				case 101://Red
					this.colorBG="rgba(255,0,0,1)";
					break;
				case 102://Green
					this.colorBG="rgba(0,255,0,1)";
					break;
				case 103://Yellow
					this.colorBG="rgba(255,255,0,1)";
					break;
				case 104://Blue
					this.colorBG="rgba(0,0,255,1)";
					break;
				case 105://Magenta
					this.colorBG="rgba(255,0,255,1)";
					break;
				case 106://Cyan
					this.colorBG="rgba(0,255,255,1)";
					break;
				case 107://White
					this.colorBG="rgba(255,255,255,1)";
					break;
			}
		}
	}
	
	//-----------------------------------------------------------------------
	//Output a seg of text, no new line, support \t .
	_outLnText(text,line=null,pos=0){
		let idx,lines,curText,outText,lineText,segText;
		let pts,segChNum,span;
		
		function renderTab(){
			let n,m,i;
			n=lineText.length+curText.length;
			m=Math.floor(n/segChNum)*segChNum+segChNum;
			n=m-n;
			for(i=0;i<n;i++){
				curText+=" ";
			}
		}
		if(!line) {
			lines = this.lines;
			idx = lines.length - 1;
			line = lines[idx];
		}
		lineText=line.innerText;
		curText="";//line.innerText;
		segChNum=this.segChNum;
		pts=text.split("\t");
		pts.forEach((sub,idx)=>{
			if(idx!==0){
				renderTab();
			}
			curText+=sub
		})
		if(pos===lineText.length){
			let i,escPos,escChar;
			outText="";
			span = line.curSpan;
			if (!span) {
				let style;
				line.curSpan = span = this.newTextSpan();
				line.appendChild(span);
			}
			escPos=curText.indexOf('\x1b');
			if(escPos>=0){
				//Complex way:
				do{
					segText=curText.substring(0,escPos);
					line.curSpan.innerText+=segText;
					outText+=segText;
					curText=curText.substring(escPos+1);
					escChar=curText[0];
					if(escChar==="["){
						let mkPos=curText.search(regSearchEscEnd);
						let mk=curText[mkPos];
						if(mk==="m"){//Color:
							let colorText=curText.substring(1,mkPos)
							curText=curText.substring(mkPos+1);
							if(colorText==="0"){
								this.colorTxt=this.defColorTxt;
								this.colorBG=this.defColorBG;
								this.fontWeight="";
							}else {
								this.parseEscText(colorText);
							}
							let newSpan=this.newTextSpan();
							line.appendChild(newSpan);
							line.curSpan=newSpan;
							console.log("Terminal set color: "+colorText);
						}else{
							//ignore
							curText=curText.substring(mkPos+1);
						}
					}else{
						line.curSpan.innerText+=curText;
						outText+=curText;
						curText="";
					}
					escPos=curText.indexOf('\x1b');
				}while(escPos>0);
				line.curSpan.innerText+=curText;
				outText+=curText;
			}else{
				line.curSpan.innerText = line.curSpan.innerText+curText;
				outText=curText;
			}
		}else {			
			lineText = lineText.substring(0, pos) + curText + lineText.substring(pos + curText.length);
			line.innerText = lineText;
			line.curSpan=null;
			outText=curText;
		}
		//Record cursor pos:
		this.cursorX=pos+outText.length;
		this.cursorLine=line;
	}
	
	//-----------------------------------------------------------------------
	//Output a line:
	_outLine(text,curLine=null){
		let div,style,divLines,lines;
		divLines=this.div;
		lines=this.lines;
		if(curLine){
			div=curLine.nextSibling;
		}else{
			curLine=this.cursorLine||this.lastLine;
			if(curLine){
				div=curLine.nextSibling;
				if(div===this.divInput){
					div=null;
				}
			}
		}
		if(!div && divLines) {
			div = document.createElement('div');
			style = div.style;
			style.width = "auto";
			style.height = "";
			style.wordBreak = "break-word";
			style.whiteSpace = "pre";
			style.textOverflow = "";
			style.alignSelf = "";
			style.textAlign = "";
			style.fontFamily = "monospace";
			style.fontSize = "12px";
			style.color = "rgba(0,0,0,1)";
			style.paddingLeft="5px";
			div.spellcheck = false;
			if(this.divInput){
				divLines.insertBefore(div,this.divInput);
			}else{
				divLines.appendChild(div);
			}
			lines.push(div);
			div.lineSeq = this.lineSeq++;
			this.lastLine = div;
			if (lines.length > 200) {
				divLines.removeChild(lines[0]);
				lines.shift();
			}
		}
		this.cursorLine=div;
		this.cursorX=0;
		this._outLnText(text,div,0);
		return div;
	}
	
	//-----------------------------------------------------------------------
	//Output [text], if [scroll] is true, scorll view to bottom.
	textOut(text,scroll=1){
		let pts,lead,i,n;
		if(typeof(text)!=="string"){
			text=""+text;
		}
		//console.log(text);
		if(this.div) {
			pts = text.split("\n");
			lead = pts[0];
			if (lead) {
				if(!this.cursorLine && this.divInput){
					this._outLine(lead);
				}else {
					this._outLnText(lead, this.cursorLine, this.cursorX);
				}
			}
			n = pts.length;
			if (n > 1) {
				for (i = 1; i < n; i++) {
					this._outLine(pts[i]);
				}
			}
			if (scroll) {
				//滚动element:
				this.div.scrollTop = this.div.scrollHeight;
			}
		}
		if(this.host){
			this.host.sendRemoteMsg({
				msg:"tty",
				func:"textOut",
				args:[text,scroll]
			});
		}
		this.emit("data",text);
	}
	
	//-----------------------------------------------------------------------
	//Output a seg of HTML elemts:
	htmlOut(htmlText,scroll=1){
		let divLines,div,style;
		divLines=this.div;
		if(divLines) {
			div = document.createElement('div');
			style = div.style;
			style.width = "auto";
			style.height = "";
			style.color = "rgba(0,0,0,1)";
			style.paddingLeft="10px";
			div.spellcheck = false;
			divLines.appendChild(div);
			this.lines.push(div);
			div.lineSeq = this.lineSeq++;
			div.innerHTML=htmlText;
			this.lastLine = div;
			if (this.lines.length > 200) {
				divLines.removeChild(this.lines[0]);
				this.lines.shift();
			}
			this._outLine("",scroll);
		}else if(this.host){
			this.host.sendRemoteMsg({
				msg:"tty",
				func:"htmlOut",
				args:[htmlText,scroll]
			});
		}
		this.emit("data",htmlText);
	}
	
	//-----------------------------------------------------------------------
	//Start text input :
	startInput(prefix=null,password=false,initText=""){
		let div,path;
		let passwordText="";
		
		path=JAXDisk.appPath;
		if(this.div) {
			if(prefix!==null){
				this.inputPrefix=prefix;
			}else{
				this.inputPrefix=""+this.inputHeader+" "+path+" $> ";
			}
			div = this.divInput;
			if (!div) {
				this._outLine("");
				div = this.lastLine;
				if (!div || div.innerText) {
					div = this._outLine(this.inputPrefix+initText, this.lastLine);
				} else {
					div.innerText = this.inputPrefix+initText;
					div.curSpan=null;
				}
				this.divInput = div;
				this.cursorLine =null;this.cursorX=0;
				div.curInputText = div.inputPrefix = this.inputPrefix;
				div.contentEditable = true;
				div.style.outlineStyle = "none";
				div.style.backgroundColor = "rgba(230,240,255,1)";
				div.isPassword=!!password;
				if(password){
					div.addEventListener("keydown", evt=>{
						switch(evt.key){
							case "Enter":
								evt.preventDefault();
								evt.stopPropagation();
								this.endInput(passwordText);
								break;
							case "Backspace":
								passwordText=passwordText.substring(0,passwordText.length-1);
								evt.preventDefault();
								evt.stopPropagation();
								break;
						}
					}, true);
				}else {
					div.addEventListener("keydown", this.OnKeyDown.bind(this), true);
				}
				div.oninput = () => {
					let text;
					text = div.innerText;
					if(password){
						if (!text.startsWith(div.inputPrefix)) {
						} else {
							text=text.substring(div.inputPrefix.length);
							passwordText+=text;
						}
						div.innerText = div.inputPrefix;
						div.curSpan=null;
						window.getSelection().collapse(div.firstChild, div.inputPrefix.length);
					}else {
						if (!text.startsWith(div.inputPrefix)) {
							div.innerText = div.inputPrefix;
							div.curSpan=null;
							window.getSelection().collapse(div.firstChild, div.inputPrefix.length);
						}
					}
				};
				window.getSelection().collapse(div.firstChild, div.firstChild.length||div.innerText.length);
			}
			this.div.scrollTop = this.div.scrollHeight;
			div.focus();
			window.setTimeout(() => {
				div.focus();
				window.getSelection().collapse(div.firstChild, div.firstChild.length||div.innerText.length);
			}, 0);
		}else if(this.host){
			this.host.sendRemoteMsg({
				msg:"StartInput",
				prefix:prefix,
				initText:initText,
				password:password
			});
		}
		this.isInputPassword=password;
	}
	
	//-----------------------------------------------------------------------
	//End text input:
	endInput(text){
		let div;
		if(this.div) {
			div=this.divInput;
			if(div) {
				div.contentEditable = false;
				div.style.backgroundColor = "rgba(0,0,0,0)";
				this.divInput = null;
			}
			this._outLine("", this.lastLine);
		}
		if(!this.emit("LineInput",text)) {
			this.stdin.push(text + "\n");
		}
	}
	
	//-----------------------------------------------------------------------
	//Set the "input" text
	setInputText(text){
		let div;
		div=this.divInput;
		if(!div){
			return;
		}
		if(div.inputPrefix){
			text=div.inputPrefix+text;
		}
		div.innerText=text;
		div.curSpan=null;
		window.getSelection().collapse(div.firstChild,text.length);
	}
	
	//-----------------------------------------------------------------------
	//Get current "input" text:
	getInputText(){
		let text,div;
		div=this.divInput;
		if(!div){
			return null;
		}
		text= div.innerText;
		if(div.inputPrefix && text.startsWith(div.inputPrefix)){
			text=text.substring(div.inputPrefix.length);
		}
		return text;
	}
	
	//-----------------------------------------------------------------------
	//Handle key events:
	OnKeyDown(e){
		let div;
		div=this.divInput;
		this.emit("KeyDown",e);
		//console.log(e);
		switch(e.key)
		{
			case "c":{
				if(e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey){
					this.emit("KeyInExec","BreakCmd");
				}
				break;
			}
			case "Enter":{
				let cmd;
				if(div){
					//TODO: When Shift down, don't send message:
					let text;
					cmd=div.innerText;
					if(div.inputPrefix && cmd.startsWith(div.inputPrefix)){
						cmd=cmd.substring(div.inputPrefix.length);
					}
					text=this.getInputText();
					this.endInput(text);
					e.preventDefault();
					e.stopPropagation();
					return;
				}
				break;
			}
			case "ArrowLeft":{
				if(window.getSelection().focusOffset<=div.inputPrefix.length){
					window.getSelection().collapse(div.firstChild, div.firstChild.length||div.innerText.length);
					e.preventDefault();
					e.stopPropagation();
					return;
				}
				break;
			}
			case "ArrowDown":
			case "ArrowUp":
			case "Tab":{
				if(div){
					this.emit("ToolKey",e.key);
					e.preventDefault();
					e.stopPropagation();
					return;
				}
				break;
			}
		}
	}
	
	//-----------------------------------------------------------------------
	//Clear screen
	clear(){
		if(this.div) {
			let restartInput=false,inputPrefix,inputText,isPswd;
			if(this.divInput){
				restartInput=true;
				inputPrefix=this.inputPrefix;
				inputText=this.getInputText();
				isPswd=this.divInput.isPassword;
			}
			this.div.innerHTML = "";
			this.lines.splice(0);
			this.lastLine = null;
			this.divInput = null;
			this._outLine("");
			if(restartInput){
				this.startInput(inputPrefix,isPswd,inputText);
			}
		}else if(this.host){
			this.host.sendRemoteMsg({
				msg:"tty",
				func:"clear",
				args:[]
			});
		}
	}
	
	//-----------------------------------------------------------------------
	//Clear a line by dir
	clearLine(dir){
		let line,curText;
		if(this.div) {
			line = this.cursorLine;
			if (!line) {
				return;
			}
			switch (dir) {
				case -1:
					curText = line.innerText;
					curText = curText.substring(this.cursorX);
					line.innerText = curText;
					line.curSpan=null;
					this.cursorX = 0;
					break;
				case 1:
					curText = line.innerText;
					curText = curText.substring(0, this.cursorX);
					line.innerText = curText;
					line.curSpan=null;
					break;
				default:
				case 0:
					line.innerText = "";
					line.curSpan=null;
					break;
			}
		}else if(this.host){
			this.host.sendRemoteMsg({
				msg:"tty",
				func:"clearLine",
				args:[dir]
			});
		}
	}
	
	//-----------------------------------------------------------------------
	//Clear all text below cursor
	clearScreenDown(){
		let line,lines,idx,i,n,divLines;
		if(this.div) {
			line = this.cursorLine;
			lines = this.lines;
			divLines = this.div;
			if (!line) {
				this.clear();
				return;
			}
			idx = lines.indexOf(line);
			if (idx >= 0) {
				n = lines.length;
				for (i = idx + 1; i < n; i++) {
					divLines.removeChild(lines[i]);
				}
				lines.splice(idx + 1);
			}
			this.clearLine(1);
		}else if(this.host){
			//TODO: Code this:
		}
	}
	
	//-----------------------------------------------------------------------
	//Set cursor pos
	setCursorPos(x,y){
		let line;
		if(this.div) {
			if (y >= 0) {
				let lines, baseLine;
				lines = this.lines;
				line = lines[y] || this.lastLine;
			} else {
				line = this.cursorLine;
			}
			this.cursorLine = line;
			x = x < 0 ? 0 : x;
			x = x > line.innerText.length ? line.innerText.length : x;
			this.cursorX = x;
		}else if(this.host){
			//TODO: Code this:
		}
	}
	
	//-----------------------------------------------------------------------
	//Move cursor pos by delta size:
	moveCursor(dx,dy){
		let x,y;
		if(this.div) {
			if (this.cursorLine) {
				y = this.lines.indexOf(this.cursorLine);
				y += dy;
			}
			x = this.cursorX + dx;
			setCursorPos(x, y);
		}else if(this.host){
			//TODO: Code this:
		}
	}
	
	//-----------------------------------------------------------------------
	//Helper function to read quession answer from tty.
	readLine(caption,text=""){
		return new Promise((doneFunc,errFunc)=>{
			this.once("LineInput",(text)=>{
				doneFunc(text);
			});
			this.startInput(caption,0,text);
		})
	}
	
	//-----------------------------------------------------------------------
	//Helper function to read password from tty:
	readPassword(caption){
		return new Promise((doneFunc,errFunc)=>{
			this.once("LineInput",(text)=>{
				doneFunc(text);
			});
			this.startInput(caption,true);
		})
	}
	
	//-----------------------------------------------------------------------
	//get tab char-size:
	getTabSize(size){
		return this.segChNum;
	}

	//-----------------------------------------------------------------------
	//set tab char-size:
	setTabSize(size){
		this.segChNum=size;
		if(!this.div){
			this.host.sendHostMsg({
				msg:"tty",
				func:"setTabSize",
				args:[size]
			});
		}
	}
	
	//-----------------------------------------------------------------------
	getContent(){
		let lines,i,n,line,content;
		lines = this.lines;
		n=lines.length;
		content="";
		for(i=0;i<n;i++){
			if(i>0){
				content+="\n";
			}
			line = lines[i];
			content+=line.innerText;
		}
		return content;
	}
}
let TabTTY=CokeTTY;
export {TTYStdOut,TTYStdIn,CokeTTY,TabTTY};

