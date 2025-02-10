
//****************************************************************************
//:AATask:
//****************************************************************************
let AATask,aaTask;
{
	//------------------------------------------------------------------------
	AATask=function(session,desc,guide){
		let gc,env,project,parentTask,glogs;
		this.session=session;
		gc=session.globalContext;
		parentTask=gc.curTask;
		env=gc.env;
		project=gc.project;
		glogs=gc.logs;
		if(!glogs){
			glogs=gc.logs={all:[]};
		}
		this.globalLogs=glogs;
		this.env=env;
		this.project=project;
		this.parentTask=parentTask;
		this.desc=desc;
		this.guide=guide;
		this.done=false;
		if(!parentTask){
			if(!project.tasks){
				project.tasks=[];
			}
			project.tasks.push(this);
		}else{
			parentTask.newSubTask(this);
		}
		gc.curTask=this;
		this.reault=null;
		this.resultContent=null;
		this.steps=[];
		this.issues=[];
		this.subTasks=[];
		this.logs=[];
		this.curStep=null;
		this.reportCallback=null;
		this.log(`Start task: ${desc}`,true);
	};
	aaTask=AATask.prototype={};
	
	//************************************************************************
	//:Logs:
	//************************************************************************
	{
		//--------------------------------------------------------------------
		aaTask._log=async function(type,log,catalog=""){
			const glogs=this.globalLogs;
			const stub={type:type,content:log};
			this.logs.push(stub);
			if(glogs){
				glogs.all && glogs.all.push(stub);
				if(catalog && catalog !=="all"){
					let cat=glogs[catalog];
					if(!cat){
						glogs[catalog]=cat=[];
					}
					cat.push(stub);
				}
			}
		};

		//--------------------------------------------------------------------
		aaTask.log=async function(log,catalog="",notify=false){
			if(typeof(catalog)!=="string"){
				notify=!!catalog;
				catalog="";
			}
			this._log("log",log,catalog);
			if(notify){
				this.session.addChatText("log",typeof(log)==="string"?log:JSON.stringify(log));
			}
		};

		//--------------------------------------------------------------------
		aaTask.warn=function(log,catalog="",notify=false){
			if(typeof(catalog)!=="string"){
				notify=!!catalog;
				catalog="";
			}
			this._log("warning",log,catalog);
			if(notify){
				this.session.addChatText("warning",typeof(log)==="string"?log:JSON.stringify(log));
			}
		};

		//--------------------------------------------------------------------
		aaTask.error=function(log,catalog="",notify=false){
			if(typeof(catalog)!=="string"){
				notify=!!catalog;
				catalog="";
			}
			this._log("error",log,catalog);
			if(notify){
				this.session.addChatText("error",typeof(log)==="string"?log:JSON.stringify(log));
			}
		};
		
		//--------------------------------------------------------------------
		aaTask.tailLogs=function(num=5){
			let logs=this.logs;
			if(logs.length<num){
				return logs.slice(0);
			}
			return logs.slice(-num);
		};
	}

	//************************************************************************
	//:Progress:
	//************************************************************************
	{
		//--------------------------------------------------------------------
		aaTask.setReportCallback=function(callback){
			this.reportCallback=callback;
		};
		
		//--------------------------------------------------------------------
		aaTask.report=function(content,task,level=0,deep=1){
			let parentTask=this.parentTask;
			task=task||this;
			if(level && this.reportCallback){
				this.reportCallback(task,content);
			}
			if(parentTask && deep){
				parentTask.report(content,task,level+1,deep-1);
			}
		};
		
		//--------------------------------------------------------------------
		aaTask.endTask=function(){
			let gc;
			if(this.done){
				//TODO: warning?
				return;
			}
			gc=this.session.globalContext;
			if(gc.curTask===this){
				if(!this.parentTask){
					gc.curTask=null;
				}else{
					gc.curTask=this.parentTask;
				}
			}else{
				//TODO: Error?
			}
			this.log(`End task: ${this.desc}  \n\n${this.result}  \n\n${this.resultContent}`,true);
		};
		
		//--------------------------------------------------------------------
		aaTask.finish=function(content){
			this.result="Finish";
			this.resultContent=content;
		};
		
		//--------------------------------------------------------------------
		aaTask.abort=function(content){
			this.result="Abort";
			this.resultContent=content;
		};

		//--------------------------------------------------------------------
		aaTask.fail=function(content){
			this.result="Fail";
			this.resultContent=content;
		};

		//--------------------------------------------------------------------
		aaTask.skip=function(content){
			this.result="Skip";
			this.resultContent=content;
		};
		
		//--------------------------------------------------------------------
		aaTask.newStep=function(input){
			let step;
			if(this.curStep){
				//Error?
			}
			step=this.curStep={
				input:input,
				op:null,
				result:null
			};
			this.steps.push(step);
			this.log(`New step.`);
		};
		
		//--------------------------------------------------------------------
		aaTask.stepOp=function(op){
			let step;
			step=this.curStep;
			if(step){
				step.op={...op};
			}
			this.log(`Step op: ${JSON.stringify(op)}`);
		};

		//--------------------------------------------------------------------
		aaTask.endStep=function(result){
			let step;
			step=this.curStep;
			if(step){
				step.result=result;
			}
			this.log(`Step result:  \n${typeof(result)==="string"?result:JSON.stringify(result)}`);
		};
		
		//--------------------------------------------------------------------
		aaTask.newSubTask=function(task){
			this.subTasks.push(task);
		};
		
		//--------------------------------------------------------------------
		aaTask.endSubTask=function(){//???
			//TODO: Code this:
		};
		
		//--------------------------------------------------------------------
		aaTask.newIssue=function(issue){
			this.subTasks.push(issue);
			this.issues.push(issue);
		};

		//--------------------------------------------------------------------
		aaTask.endIssue=function(){//???
			//TODO: Code this:
		};
	}
}

export default AATask;
export {AATask};