window.selfManagedAccess = function () {
    return {
        mode:'tunnel', bind:'127.0.0.1', port:57440, origin:'', state:{}, qr:'', link:'', error:'', busy:false, timer:null,
        async api(path='',method='GET',body) {
            const response=await fetch('/v1/platform/self-managed-access'+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
            const value=await response.json();
            if(!response.ok)throw Error(value?.detail?.message||value?.error?.message||value?.detail||'操作失败');
            return value;
        },
        async init(){try{this.state=await this.api();if(this.state.config)Object.assign(this,this.state.config);}catch(e){this.error=e.message;}this.timer=setInterval(()=>this.refresh(),3000);},
        destroy(){clearInterval(this.timer);},
        async refresh(){try{this.state=await this.api();}catch(e){this.error=e.message;}},
        async act(action){this.busy=true;this.error='';try{await action();await this.refresh();}catch(e){this.error=e.message;}finally{this.busy=false;}},
        save(){return this.act(async()=>{await this.api('','PUT',{mode:this.mode,bind:this.bind,port:Number(this.port),origin:this.origin});this.qr='';});},
        disable(){return this.act(async()=>{await this.api('','DELETE');this.qr='';});},
        pair(){return this.act(async()=>{const value=await this.api('/pairing','POST');this.qr=value.qr;this.link=value.url;});},
        approve(id){return this.act(()=>this.api('/pairing/'+encodeURIComponent(id)+'/approve','POST'));},
        revoke(id){return this.act(()=>this.api('/devices/'+encodeURIComponent(id),'DELETE'));}
    };
};
