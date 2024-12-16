
const lockerMap=new Map();
class Lock {
	constructor() {
		this._locked = false;
		this._waiting = [];
	}
	
	async lock() {
		while (this._locked) {
			await new Promise(resolve => this._waiting.push(resolve));
		}
		this._locked = true;
	}
	
	unlock() {
		this._locked = false;
		if (this._waiting.length > 0) {
			const resolve = this._waiting.shift();
			resolve();
		}
	}
}

let lock=async function(code){
	let locker;
	locker=lockerMap.get(code);
	if(!locker){
		locker=new Lock;
		lockerMap.set(code,locker);
	}
	await locker.lock();
};
let unlock=function(code){
	let locker;
	locker=lockerMap.get(code);
	if(!locker){
		return;
	}
	locker.unlock();
};

export {lock,unlock};
