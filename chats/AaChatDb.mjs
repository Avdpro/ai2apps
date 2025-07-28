import PouchDB from 'pouchdb';
import PouchDBFind from 'pouchdb-find';
import fsp from "fs/promises";

const CHATDB_SYNC=process.env.CHATDB_SYNC;
const CHATDB_RESET=process.env.CHATDB_RESET;
PouchDB.plugin(PouchDBFind);
const MAX_LIVE_THREADS=10;

//***************************************************************************
//AaChatDb
//***************************************************************************
let AaChatDb,aaChatDb;
{
	AaChatDb=function(server){
		this.server=server;
		this.db=null;
	};
	aaChatDb=AaChatDb.prototype={};
	
	//-----------------------------------------------------------------------
	aaChatDb.resetDb=async function(dbName){
		dbName=dbName||'./chatdb/chatserver';
		await new PouchDB(dbName).destroy();
		if(CHATDB_SYNC) {
			const remote = new PouchDB(CHATDB_SYNC);
			await remote.destroy();
		}
	};
	
	//-----------------------------------------------------------------------
	aaChatDb.init=async function(dbName){
		let dbPath;
		const indexDefs = [
			{ fields: ['type_'] },                        				// for all type-based queries
			{ fields: ['type_', 'status'] },                         	// for get all live threads
			{ fields: ['type_', 'status', 'timeStamp'] },    			// for thread filtering
			{ fields: ['type_', 'status', 'userId', 'timeStamp'] },    	// for thread filtering
			{ fields: ['type_', 'userId'] },                         	// searchThreads 的 thread
			{ fields: ['type_', 'threadId', 'text'] },                	// searchThreads 的 message 部分
			{ fields: ['type_', 'threadId', 'idx'] },      				// for messages by thread + idx
			{ fields: ['type_', 'threadId'] }      				// for messages by thread + idx
		];
		if(dbName){
			dbPath=dbName;
		}else{
			dbPath='./chatdb/chatserver';
		}
		await fsp.mkdir(dbPath, { recursive: true });
		if(CHATDB_RESET==="TRUE"){
			await this.resetDb(dbPath);
		}
		const db=this.db = new PouchDB(dbPath);
		for (const def of indexDefs) {
			await db.createIndex({ index: def });
		}
		if(CHATDB_SYNC){
			const remoteDB = new PouchDB(CHATDB_SYNC);
			db.sync(remoteDB, {
				live: true,
				retry: true
			}).on('change', info => {
				console.log('同步变化:', info);
			}).on('error', err => {
				console.error('同步出错:', err);
			});
		}
		
		const info = await db.getIndexes();
		console.log(JSON.stringify(info, null, 2));
	};
	
	//-----------------------------------------------------------------------
	aaChatDb.newClient=async function(clientId,userId){
		return;
		await this.db.put({
			_id: clientId,
			type_: 'client',
			userId: userId,
			timeStamp:Date.now(),
		});
	};
	
	//-----------------------------------------------------------------------
	aaChatDb.clientActive=async function(clientId){
		const client = await this.db.get(clientId);
		if(!client){
			return false;
		}
		if(Date.now()-client.timeStamp>3600*24*1000*5){
			//Expired:
			await this.db.remove(client);
			return false;
		}
		client.timeStamp=Date.now();
		await this.db.put(client);
		return true;
	};

	//-----------------------------------------------------------------------
	aaChatDb.getClient=async function(clientId){
		const client = await this.db.get(clientId);
		if(!client){
			return null;
		}
		if(Date.now()-client.timeStamp>3600*24*1000*5){
			//Expired:
			await this.db.remove(client);
			return null;
		}
		client.timeStamp=Date.now();
		await this.db.put(client);
		return client;
	};
	
	//-----------------------------------------------------------------------
	aaChatDb.getAllLiveThreads=async function({archive=false}){
		const res = await this.db.find({
			selector: { type_: 'thread', status: 'live'},
		});
		let list = res.docs;
		list=list.sort((item1,item2)=>{return item2.timeStamp-item1.timeStamp});
		list=list.splice(0,MAX_LIVE_THREADS);
		return list;
	};

	//-----------------------------------------------------------------------
	aaChatDb.getUserLiveThreads=async function(userId,maxMessages=10,readMessages=true){
		const res = await this.db.find({
			selector: { type_: 'thread', status: 'live', userId },
			sort: [{ timeStamp: 'desc' }]
		});
		let docs=res.docs;
		if(maxMessages>0 && docs.length>maxMessages){
			let archives;
			archives=docs.slice(maxMessages);
			docs=docs.slice(0,maxMessages);
			for(let doc of archives){
				doc.archived=true;
			}
			await this.db.bulkDocs(archives);
		}
		if(readMessages) {
			for (let doc of docs) {
				doc.messages = await this.getThreadMessages(doc._id);
			}
		}
		return docs;
	};

	//-----------------------------------------------------------------------
	aaChatDb.getArchivedThreads=async function(userId){
		const res = await this.db.find({
			selector: { type_: 'thread', status: 'archived', userId },
			sort: [{ timeStamp: 'desc' }]
		});
		return res.docs;
	};
	
	//-----------------------------------------------------------------------
	aaChatDb.newThread=async function(thread){
		try {
			await this.db.put({
				_id: thread.id,
				type_: 'thread',
				title: thread.title,
				userId: thread.userId,
				timeStamp: thread.timeStamp,
				star: !!thread.star,
				status: thread.status
			});
		}catch(err){
			console.log("NewThread DB Error:");
			console.error(err);
			throw err;
		}
	};
	
	//-----------------------------------------------------------------------
	aaChatDb.getThreadMessages=async function(threadId){
		const res = await this.db.find({
			selector: { type_: 'message', threadId},
			//sort: [{ idx: 'asc' }]
		});
		return res.docs.sort((doc1,doc2)=>{return doc1.idx-doc2.idx});
	};

	//-----------------------------------------------------------------------
	aaChatDb.getThread=async function(threadId,readMessages=false){
		const threadVo=await this.db.get(threadId);
		if(!threadVo){
			return null;
		}
		if(readMessages) {
			threadVo.messages = await this.getThreadMessages(threadId);
		}
		return threadVo;
	};
	
	//-----------------------------------------------------------------------
	aaChatDb.newThreadMessage=async function(thread,msgVO){
		const threadId=thread.id;
		const messages = thread.messages;
		const newIdx = messages.length;
		
		msgVO._id = `${thread.id}:${newIdx}`;
		msgVO.type_ = 'message';
		msgVO.threadId = threadId;
		msgVO.idx = newIdx;
		
		const threadDoc = await this.db.get(threadId);
		threadDoc.timeStamp = thread.timeStamp;

		try {
			await this.db.bulkDocs([msgVO, threadDoc]);
		}catch(err){
			console.log("NewThreadMessage DB Error:");
			console.error(err);
			throw err;
		}
	};
	
	//-----------------------------------------------------------------------
	aaChatDb.rollBack=async function(thread,rollbackIdx){
		let threadId=thread.id;
		const res = await this.db.find({
			selector: { type_: 'message', threadId, idx: { $gt: rollbackIdx } },
			fields: ['_id', '_rev']
		});
		const deletions = res.docs.map(doc => ({ _id: doc._id, _rev: doc._rev, _deleted: true }));
		if (deletions.length > 0) {
			await this.db.bulkDocs(deletions);
		}
	};
	
	//-----------------------------------------------------------------------
	aaChatDb.deleteThread=async function(thread){
		const threadId=thread.id;
		const threadDoc = await this.db.get(threadId);
		const msgs = await this.db.find({
			selector: { type_: 'message', threadId },
			fields: ['_id', '_rev']
		});
		const deletions = msgs.docs.map(doc => ({ _id: doc._id, _rev: doc._rev, _deleted: true }));
		deletions.push({ _id: threadDoc._id, _rev: threadDoc._rev, _deleted: true });
		try {
			await this.db.bulkDocs(deletions);
		}catch(err){
			console.log("DeleteThread DB Error:");
			console.error(err);
			throw err;
		}
	};
	
	//-----------------------------------------------------------------------
	aaChatDb.setThreadStar=async function(thread,star){
		const threadId=thread.id;
		const threadDoc = await this.db.get(threadId);
		thread.stared = !!star;
		try {
			await this.db.put(threadDoc);
		}catch(err){
			console.log("setThreadStar DB Error:");
			console.error(err);
			throw err;
		}
	};
	
	//-----------------------------------------------------------------------
	aaChatDb.renameThread=async function(thread){
		const threadId=thread.id;
		const threadDoc = await this.db.get(threadId);
		if(threadDoc) {
			threadDoc.title = thread.title;
			await this.db.put(threadDoc);
		}
	};
	
	//-----------------------------------------------------------------------
	aaChatDb.archiveThread=async function(thread){
		const threadId=thread.id;
		const threadDoc = await this.db.get(threadId);
		threadDoc.status = 'archived';
		try{
			await this.db.put(threadDoc);
		}catch(err){
			console.log("archiveThread DB Error:");
			console.error(err);
			throw err;
		}
	};
	
	//-----------------------------------------------------------------------
	aaChatDb.callbackArchivedThread=async function(thread){
		const threadId=thread.id;
		const threadDoc = await this.db.get(threadId);
		thread.status = 'live';
		try{
			await this.db.put(threadDoc);
		}catch(err){
			console.log("callbackArchivedThread DB Error:");
			console.error(err);
			throw err;
		}
		//TODO: Code this:
	};
	
	//-----------------------------------------------------------------------
	aaChatDb.findThreadByKeyword=async function(userId,keyword){
		const lowerKeyword = keyword.toLowerCase();
		
		// 获取属于该 userId 的 thread 列表
		const threadRes = await this.db.find({
			selector: { type_: 'thread', userId },
			fields: ['_id', 'title']
		});
		
		const threadIdSet = new Set(threadRes.docs.map(doc => doc._id));
		
		// 1. 标题中匹配
		const matchedThreadIdsFromTitle = threadRes.docs
			.filter(doc => doc.title?.toLowerCase().includes(lowerKeyword))
			.map(doc => doc._id);
		
		// 2. 消息中匹配（必须是该用户的 threadId）
		const msgRes = await this.db.find({
			selector: { type_: 'message' },
			fields: ['threadId', 'text']
		});
		
		const matchedThreadIdsFromMsg = msgRes.docs
			.filter(doc =>
				threadIdSet.has(doc.threadId) &&
				doc.text?.toLowerCase().includes(lowerKeyword)
			)
			.map(doc => doc.threadId);
		
		// 合并所有 threadId 并去重
		const allMatched = new Set([
			...matchedThreadIdsFromTitle,
			...matchedThreadIdsFromMsg
		]);
		
		// 返回匹配的 thread 对象
		return await Promise.all(
			[...allMatched].map(id => this.db.get(id))
		);
	};
}
export {AaChatDb};