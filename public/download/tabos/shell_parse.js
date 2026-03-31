function readVar(text,idx,envVals){
	let n,name,next;
	n=text.length;
	if(idx>=n || text[idx]!=="$"){
		return null;
	}
	idx++;
	if(idx>=n){
		return {val:"$",next:idx};
	}
	next=text[idx];
	if(next==="{"){
		let end;
		end=text.indexOf("}",idx+1);
		if(end<0){
			return {error:"Unclosed variable expansion"};
		}
		name=text.substring(idx+1,end);
		idx=end+1;
	}else{
		let start;
		start=idx;
		if(!/[A-Za-z_]/.test(text[idx])){
			return {val:"$",next:idx};
		}
		idx++;
		while(idx<n && /[A-Za-z0-9_]/.test(text[idx])){
			idx++;
		}
		name=text.substring(start,idx);
	}
	let val="";
	if(envVals){
		if(typeof envVals.get==="function"){
			val=envVals.get(name);
		}else{
			val=envVals[name];
		}
	}
	if(val===undefined || val===null){
		val="";
	}
	return {val:""+val,next:idx};
}

function parseShellArgs(text,envVals=null){
	let i,n,ch,next,state,buf,argv,tokenStarted;
	function pushToken(){
		if(tokenStarted){
			argv.push(buf);
			buf="";
			tokenStarted=false;
		}
	}
	text=text||"";
	n=text.length;
	state="normal";
	buf="";
	argv=[];
	tokenStarted=false;
	for(i=0;i<n;i++){
		ch=text[i];
		if(state==="single"){
			if(ch==="'"){
				state="normal";
			}else{
				buf+=ch;
			}
			continue;
		}
		if(state==="double"){
			if(ch==="\""){
				state="normal";
				continue;
			}
			if(ch==="\\"){
				i++;
				if(i<n){
					buf+=text[i];
					tokenStarted=true;
				}else{
					buf+="\\";
					tokenStarted=true;
				}
				continue;
			}
			if(ch==="$"){
				let vo;
				vo=readVar(text,i,envVals);
				if(vo.error){
					return {argv:[],error:vo.error};
				}
				buf+=vo.val;
				tokenStarted=true;
				i=vo.next-1;
				continue;
			}
			buf+=ch;
			tokenStarted=true;
			continue;
		}
		if(/\s/.test(ch)){
			pushToken();
			continue;
		}
		if(ch==="'"){
			state="single";
			tokenStarted=true;
			continue;
		}
		if(ch==="\""){
			state="double";
			tokenStarted=true;
			continue;
		}
		if(ch==="\\"){
			i++;
			if(i<n){
				buf+=text[i];
			}else{
				buf+="\\";
			}
			tokenStarted=true;
			continue;
		}
		if(ch==="$"){
			let vo;
			vo=readVar(text,i,envVals);
			if(vo.error){
				return {argv:[],error:vo.error};
			}
			buf+=vo.val;
			tokenStarted=true;
			i=vo.next-1;
			continue;
		}
		buf+=ch;
		tokenStarted=true;
	}
	if(state==="single" || state==="double"){
		return {argv:[],error:"Unclosed quote"};
	}
	pushToken();
	return {argv:argv,error:null};
}

export {parseShellArgs};
