//***************************************************************************
//DataBase Interface for DataBase in AA
//***************************************************************************
let AADataBase,aaDataBase;
{
	//-----------------------------------------------------------------------
	AADataBase=function(){
		this.nextMsgId=1;
		this.nextTaskId=1;
	};
	aaDataBase=AADataBase.prototype={};
	AADataBase.config={};
	
	//-----------------------------------------------------------------------
	AADataBase.setConfig=function(cfg){
		Object.assign(AADataBase.config,cfg);
	};
	
	//-----------------------------------------------------------------------
	aaDataBase.init=async function(opts){
	
	};

	//***********************************************************************
	//Messages:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaDataBase.newMessageId=async function(){
			return ""+(this.nextMsgId++);
		};
		
		//-------------------------------------------------------------------
		aaDataBase.getMessage = async function (msgId) {
			return null;
		};
		
		//-------------------------------------------------------------------
		aaDataBase.getUnitMessages = async function (unitId) {
			return [];
		};
		
		//-------------------------------------------------------------------
		aaDataBase.findMessages = async function (opts) {
			return [];
		};
		
		//-------------------------------------------------------------------
		aaDataBase.saveMessage = async function (message) {
		};
	}
	
	//***********************************************************************
	//Logs:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaDataBase.getUnitLogs = async function (unitId) {
			return [];
		};
		
		//-------------------------------------------------------------------
		aaDataBase.saveLog = async function (log) {
		};
		
		//-------------------------------------------------------------------
		aaDataBase.findLogs = async function (opts ) {
			return [];
		};
	}
	
	//***********************************************************************
	//Chat flows:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaDataBase.loadLiveChatFlows=async function(){
			return [];
		};
		
		//-------------------------------------------------------------------
		aaDataBase.newChatFlow = async function (chatFlow) {
		};
		
		//-------------------------------------------------------------------
		aaDataBase.addChatFlowMessage = async function (chatFlow,message) {
		};
		
		//-------------------------------------------------------------------
		aaDataBase.setChatFlowTitle = async function (chatFlow,title) {
		};

		//-------------------------------------------------------------------
		aaDataBase.closeChatFlow = async function (chatFlow) {
		};

		//-------------------------------------------------------------------
		aaDataBase.deleteChatFlow = async function (chatFlow) {
		};
		
		//-------------------------------------------------------------------
		aaDataBase.addChatFlowAsk = async function (chatFlow,askId) {
		};
		
		//-------------------------------------------------------------------
		aaDataBase.closeChatFlowAsk = async function (chatFlow,askId) {
		};
		
		//-------------------------------------------------------------------
		aaDataBase.addChatFlowLog = async function (chatFlow,log) {
		};
	}

	//***********************************************************************
	//Tasks:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaDataBase.newTaskId=async function(){
			return ""+(this.nextTaskId++);
		};
		
		//-------------------------------------------------------------------
		aaDataBase.loadOpenTaskReqs=async function(){
			return [];
		};
		
		//-------------------------------------------------------------------
		aaDataBase.loadOpenTaskWorks=async function(){
			return [];
		};
		
		//-------------------------------------------------------------------
		aaDataBase.getTaskReq=async function(taskId){
			return null;
		};
		
		//-------------------------------------------------------------------
		aaDataBase.getTaskWork=async function(taskId){
			return null;
		};
		
		//-------------------------------------------------------------------
		aaDataBase.saveTaskReq=async function(taskReq){
			return true;
		};
		
		//-------------------------------------------------------------------
		aaDataBase.saveTaskWork=async function(taskReq){
			return true;
		};
	}
}
export default AADataBase;
export {AADataBase,aaDataBase};
