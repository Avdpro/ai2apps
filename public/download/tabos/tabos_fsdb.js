class JAXDiskSysStore {
	constructor() {
		let dbName,storeName;
		dbName="CokeCodes";
		storeName="System";
		this.storeName = storeName;
		this._dbp = new Promise((resolve, reject) => {
			const openreq = indexedDB.open(dbName, 1);
			openreq.onerror = () => reject(openreq.error);
			openreq.onsuccess = () => resolve(openreq.result);
			// First time setup: create an empty object store
			openreq.onupgradeneeded = () => {
				openreq.result.createObjectStore(storeName);
			};
		});
	}
	_withIDBStore(type, callback) {
		return this._dbp.then(db => new Promise((resolve, reject) => {
			const transaction = db.transaction(this.storeName, type);
			transaction.oncomplete = () => resolve();
			transaction.onabort = transaction.onerror = () => reject(transaction.error);
			callback(transaction.objectStore(this.storeName));
		}));
	}
}
let sysStore=null;

class JAXDiskStore {
	constructor(diskName, storeName = null) {
		let dbName;
		dbName="Disk_"+diskName;
		this.dbName=dbName;
		storeName=storeName||diskName;
		if(storeName!==diskName && storeName!=="info" && storeName!=="base"){
			throw Error("JAXDiskStore: Store name error: "+storeName);
		}
		this.storeName = storeName;
		this._dbp = new Promise((resolve, reject) => {
			const openreq = indexedDB.open(dbName, 1);
			openreq.onerror = () => reject(openreq.error);
			openreq.onsuccess = () => resolve(openreq.result);
			// First time setup: create an empty object store
			openreq.onupgradeneeded = () => {
				openreq.result.createObjectStore(diskName);
				openreq.result.createObjectStore("info");
				openreq.result.createObjectStore("base");
			};
		});
	}
	_withIDBStore(type, callback) {
		return this._dbp.then(db => new Promise((resolve, reject) => {
			const transaction = db.transaction(this.storeName, type);
			transaction.oncomplete = () => resolve();
			transaction.onabort = transaction.onerror = () => reject(transaction.error);
			callback(transaction.objectStore(this.storeName));
		}));
	}
	static systemStore(){
		if(sysStore){
			return sysStore;
		}
		sysStore=new JAXDiskSysStore();
		return sysStore;
	}
}

function get(key, store) {
	let req;
	return store._withIDBStore('readonly', store => {
		req = store.get(key);
	}).then(() => req.result);
}
function set(key, value, store) {
	return store._withIDBStore('readwrite', store => {
		store.put(value, key);
	});
}
function del(key, store) {
	return store._withIDBStore('readwrite', store => {
		store.delete(key);
	});
}
function clear(store) {
	return store._withIDBStore('readwrite', store => {
		store.clear();
	});
}
function keys(store) {
	const keys = [];
	return store._withIDBStore('readonly', store => {
		// This would be store.getAllKeys(), but it isn't supported by Edge or Safari.
		// And openKeyCursor isn't supported by Safari.
		(store.openKeyCursor || store.openCursor).call(store).onsuccess = function () {
			if (!this.result)
				return;
			keys.push(this.result.key);
			this.result.continue();
		};
	}).then(() => keys);
}

function drop(databaseName){
	indexedDB.deleteDatabase(databaseName);
}
let DiskStore=JAXDiskStore;
export default JAXDiskStore;
export { JAXDiskStore, DiskStore, get, set, del, clear, keys, drop };
