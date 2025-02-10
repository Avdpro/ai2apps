import AATask from "./Task.js";
//****************************************************************************
//AATaskIssue:
//****************************************************************************
let AATaskIssue,aaTaskIssue;
{
	//------------------------------------------------------------------------
	AATaskIssue=function(session,desc){
		AATask.call(this,session,desc,null);
		this.solution=null;
	};
	aaTaskIssue=AATaskIssue.prototype=Object.create(AATask.prototype);
	aaTaskIssue.constructor = AATaskIssue;
	
	//------------------------------------------------------------------------
	aaTaskIssue.findGuide=function(guide){
		this.guide=guide;
		this.solutionByGuide=true;
	};
	
	//------------------------------------------------------------------------
	aaTaskIssue.findSolution=function(solution){
		this.solution=solution;
	};
	
	//------------------------------------------------------------------------
	aaTaskIssue.approveSolution=function(content){
		this.finish(content);
	};

	//------------------------------------------------------------------------
	aaTaskIssue.disapproveSolution=function(content){
		this.finish(content);
		this.solutionByGuide=false;
	};
}

export default AATaskIssue;
export {aaTaskIssue};