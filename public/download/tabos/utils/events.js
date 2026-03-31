//>>>>>>Node2Coke>>>>>>
var module$1={exports:{}};
var module=module$1;
var exports=module.exports;

//<<<<<<Node2Coke<<<<<<

// Copyright Joyent, Inc. and other Node contributors.
//
// Permission is hereby granted, free of charge, to any person obtaining a
// copy of this software and associated documentation files (the
// "Software"), to deal in the Software without restriction, including
// without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to permit
// persons to whom the Software is furnished to do so, subject to the
// following conditions:
//
// The above copyright notice and this permission notice shall be included
// in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
// OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
// NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
// DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
// OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
// USE OR OTHER DEALINGS IN THE SOFTWARE.

'use strict';

var R = typeof Reflect === 'object' ? Reflect : null
var ReflectApply = R && typeof R.apply === 'function'
	? R.apply
	: function ReflectApply(target, receiver, args) {
		return Function.prototype.apply.call(target, receiver, args);
	}

var ReflectOwnKeys
if (R && typeof R.ownKeys === 'function') {
	ReflectOwnKeys = R.ownKeys
} else if (Object.getOwnPropertySymbols) {
	ReflectOwnKeys = function ReflectOwnKeys(target) {
		return Object.getOwnPropertyNames(target)
			.concat(Object.getOwnPropertySymbols(target));
	};
} else {
	ReflectOwnKeys = function ReflectOwnKeys(target) {
		return Object.getOwnPropertyNames(target);
	};
}

function ProcessEmitWarning(warning) {
	if (console && console.warn) console.warn(warning);
}

var NumberIsNaN = Number.isNaN || function NumberIsNaN(value) {
	return value !== value;
}

function EventEmitter() {
	EventEmitter.init.call(this);
}
module.exports = EventEmitter;
module.exports.once = once;

// Backwards-compat with node 0.10.x
EventEmitter.EventEmitter = EventEmitter;

EventEmitter.prototype._events = undefined;
EventEmitter.prototype._eventsCount = 0;
EventEmitter.prototype._maxListeners = undefined;

// By default EventEmitters will print a warning if more than 10 listeners are
// added to it. This is a useful default which helps finding memory leaks.
var defaultMaxListeners = 10;

function checkListener(listener) {
	if (typeof listener !== 'function') {
		throw new TypeError('The "listener" argument must be of type Function. Received type ' + typeof listener);
	}
}

Object.defineProperty(EventEmitter, 'defaultMaxListeners', {
	enumerable: true,
	get: function() {
		return defaultMaxListeners;
	},
	set: function(arg) {
		if (typeof arg !== 'number' || arg < 0 || NumberIsNaN(arg)) {
			throw new RangeError('The value of "defaultMaxListeners" is out of range. It must be a non-negative number. Received ' + arg + '.');
		}
		defaultMaxListeners = arg;
	}
});

EventEmitter.init = function() {
	
	if (this._events === undefined ||
		this._events === Object.getPrototypeOf(this)._events) {
		this._events = Object.create(null);
		this._eventsCount = 0;
	}
	
	this._maxListeners = this._maxListeners || undefined;
};

// Obviously not all Emitters should be limited to 10. This function allows
// that to be increased. Set to zero for unlimited.
EventEmitter.prototype.setMaxListeners = function setMaxListeners(n) {
	if (typeof n !== 'number' || n < 0 || NumberIsNaN(n)) {
		throw new RangeError('The value of "n" is out of range. It must be a non-negative number. Received ' + n + '.');
	}
	this._maxListeners = n;
	return this;
};

function _getMaxListeners(that) {
	if (that._maxListeners === undefined)
		return EventEmitter.defaultMaxListeners;
	return that._maxListeners;
}

EventEmitter.prototype.getMaxListeners = function getMaxListeners() {
	return _getMaxListeners(this);
};

EventEmitter.prototype.emit = function emit(type) {
	var args = [];
	for (var i = 1; i < arguments.length; i++) args.push(arguments[i]);
	var doError = (type === 'error');
	
	var events = this._events;
	if (events !== undefined)
		doError = (doError && events.error === undefined);
	else if (!doError)
		return false;
	
	// If there is no 'error' event listener then throw.
	if (doError) {
		var er;
		if (args.length > 0)
			er = args[0];
		if (er instanceof Error) {
			// Note: The comments on the `throw` lines are intentional, they show
			// up in Node's output if this results in an unhandled exception.
			throw er; // Unhandled 'error' event
		}
		// At least give some kind of context to the user
		var err = new Error('Unhandled error.' + (er ? ' (' + er.message + ')' : ''));
		err.context = er;
		throw err; // Unhandled 'error' event
	}
	
	var handler = events[type];
	
	if (handler === undefined)
		return false;
	
	if (typeof handler === 'function') {
		ReflectApply(handler, this, args);
	} else {
		var len = handler.length;
		var listeners = arrayClone(handler, len);
		for (var i = 0; i < len; ++i)
			ReflectApply(listeners[i], this, args);
	}
	
	return true;
};

function _addListener(target, type, listener, prepend) {
	var m;
	var events;
	var existing;
	
	checkListener(listener);
	
	events = target._events;
	if (events === undefined) {
		events = target._events = Object.create(null);
		target._eventsCount = 0;
	} else {
		// To avoid recursion in the case that type === "newListener"! Before
		// adding it to the listeners, first emit "newListener".
		if (events.newListener !== undefined) {
			target.emit('newListener', type,
				listener.listener ? listener.listener : listener);
			
			// Re-assign `events` because a newListener handler could have caused the
			// this._events to be assigned to a new object
			events = target._events;
		}
		existing = events[type];
	}
	
	if (existing === undefined) {
		// Optimize the case of one listener. Don't need the extra array object.
		existing = events[type] = listener;
		++target._eventsCount;
	} else {
		if (typeof existing === 'function') {
			// Adding the second element, need to change to array.
			existing = events[type] =
				prepend ? [listener, existing] : [existing, listener];
			// If we've already got an array, just append.
		} else if (prepend) {
			existing.unshift(listener);
		} else {
			existing.push(listener);
		}
		
		// Check for listener leak
		m = _getMaxListeners(target);
		if (m > 0 && existing.length > m && !existing.warned) {
			existing.warned = true;
			// No error code for this since it is a Warning
			// eslint-disable-next-line no-restricted-syntax
			var w = new Error('Possible EventEmitter memory leak detected. ' +
				existing.length + ' ' + String(type) + ' listeners ' +
				'added. Use emitter.setMaxListeners() to ' +
				'increase limit');
			w.name = 'MaxListenersExceededWarning';
			w.emitter = target;
			w.type = type;
			w.count = existing.length;
			ProcessEmitWarning(w);
		}
	}
	
	return target;
}

EventEmitter.prototype.addListener = function addListener(type, listener) {
	return _addListener(this, type, listener, false);
};

EventEmitter.prototype.on = EventEmitter.prototype.addListener;

EventEmitter.prototype.prependListener =
	function prependListener(type, listener) {
		return _addListener(this, type, listener, true);
	};

function onceWrapper() {
	if (!this.fired) {
		this.target.removeListener(this.type, this.wrapFn);
		this.fired = true;
		if (arguments.length === 0)
			return this.listener.call(this.target);
		return this.listener.apply(this.target, arguments);
	}
}

function _onceWrap(target, type, listener) {
	var state = { fired: false, wrapFn: undefined, target: target, type: type, listener: listener };
	var wrapped = onceWrapper.bind(state);
	wrapped.listener = listener;
	state.wrapFn = wrapped;
	return wrapped;
}

EventEmitter.prototype.once = function once(type, listener) {
	checkListener(listener);
	this.on(type, _onceWrap(this, type, listener));
	return this;
};

EventEmitter.prototype.prependOnceListener =
	function prependOnceListener(type, listener) {
		checkListener(listener);
		this.prependListener(type, _onceWrap(this, type, listener));
		return this;
	};

// Emits a 'removeListener' event if and only if the listener was removed.
EventEmitter.prototype.removeListener =
	function removeListener(type, listener) {
		var list, events, position, i, originalListener;
		
		checkListener(listener);
		
		events = this._events;
		if (events === undefined)
			return this;
		
		list = events[type];
		if (list === undefined)
			return this;
		
		if (list === listener || list.listener === listener) {
			if (--this._eventsCount === 0)
				this._events = Object.create(null);
			else {
				delete events[type];
				if (events.removeListener)
					this.emit('removeListener', type, list.listener || listener);
			}
		} else if (typeof list !== 'function') {
			position = -1;
			
			for (i = list.length - 1; i >= 0; i--) {
				if (list[i] === listener || list[i].listener === listener) {
					originalListener = list[i].listener;
					position = i;
					break;
				}
			}
			
			if (position < 0)
				return this;
			
			if (position === 0)
				list.shift();
			else {
				spliceOne(list, position);
			}
			
			if (list.length === 1)
				events[type] = list[0];
			
			if (events.removeListener !== undefined)
				this.emit('removeListener', type, originalListener || listener);
		}
		
		return this;
	};

EventEmitter.prototype.off = EventEmitter.prototype.removeListener;

EventEmitter.prototype.removeAllListeners =
	function removeAllListeners(type) {
		var listeners, events, i;
		
		events = this._events;
		if (events === undefined)
			return this;
		
		// not listening for removeListener, no need to emit
		if (events.removeListener === undefined) {
			if (arguments.length === 0) {
				this._events = Object.create(null);
				this._eventsCount = 0;
			} else if (events[type] !== undefined) {
				if (--this._eventsCount === 0)
					this._events = Object.create(null);
				else
					delete events[type];
			}
			return this;
		}
		
		// emit removeListener for all listeners on all events
		if (arguments.length === 0) {
			var keys = Object.keys(events);
			var key;
			for (i = 0; i < keys.length; ++i) {
				key = keys[i];
				if (key === 'removeListener') continue;
				this.removeAllListeners(key);
			}
			this.removeAllListeners('removeListener');
			this._events = Object.create(null);
			this._eventsCount = 0;
			return this;
		}
		
		listeners = events[type];
		
		if (typeof listeners === 'function') {
			this.removeListener(type, listeners);
		} else if (listeners !== undefined) {
			// LIFO order
			for (i = listeners.length - 1; i >= 0; i--) {
				this.removeListener(type, listeners[i]);
			}
		}
		
		return this;
	};

function _listeners(target, type, unwrap) {
	var events = target._events;
	
	if (events === undefined)
		return [];
	
	var evlistener = events[type];
	if (evlistener === undefined)
		return [];
	
	if (typeof evlistener === 'function')
		return unwrap ? [evlistener.listener || evlistener] : [evlistener];
	
	return unwrap ?
		unwrapListeners(evlistener) : arrayClone(evlistener, evlistener.length);
}

EventEmitter.prototype.listeners = function listeners(type) {
	return _listeners(this, type, true);
};

EventEmitter.prototype.rawListeners = function rawListeners(type) {
	return _listeners(this, type, false);
};

EventEmitter.listenerCount = function(emitter, type) {
	if (typeof emitter.listenerCount === 'function') {
		return emitter.listenerCount(type);
	} else {
		return listenerCount.call(emitter, type);
	}
};

EventEmitter.prototype.listenerCount = listenerCount;
function listenerCount(type) {
	var events = this._events;
	
	if (events !== undefined) {
		var evlistener = events[type];
		
		if (typeof evlistener === 'function') {
			return 1;
		} else if (evlistener !== undefined) {
			return evlistener.length;
		}
	}
	
	return 0;
}

EventEmitter.prototype.eventNames = function eventNames() {
	return this._eventsCount > 0 ? ReflectOwnKeys(this._events) : [];
};

function arrayClone(arr, n) {
	var copy = new Array(n);
	for (var i = 0; i < n; ++i)
		copy[i] = arr[i];
	return copy;
}

function spliceOne(list, index) {
	for (; index + 1 < list.length; index++)
		list[index] = list[index + 1];
	list.pop();
}

function unwrapListeners(arr) {
	var ret = new Array(arr.length);
	for (var i = 0; i < ret.length; ++i) {
		ret[i] = arr[i].listener || arr[i];
	}
	return ret;
}

function once(emitter, name) {
	return new Promise(function (resolve, reject) {
		function errorListener(err) {
			emitter.removeListener(name, resolver);
			reject(err);
		}
		
		function resolver() {
			if (typeof emitter.removeListener === 'function') {
				emitter.removeListener('error', errorListener);
			}
			resolve([].slice.call(arguments));
		};
		
		eventTargetAgnosticAddListener(emitter, name, resolver, { once: true });
		if (name !== 'error') {
			addErrorHandlerIfEventEmitter(emitter, errorListener, { once: true });
		}
	});
}

function addErrorHandlerIfEventEmitter(emitter, handler, flags) {
	if (typeof emitter.on === 'function') {
		eventTargetAgnosticAddListener(emitter, 'error', handler, flags);
	}
}

function eventTargetAgnosticAddListener(emitter, name, listener, flags) {
	if (typeof emitter.on === 'function') {
		if (flags.once) {
			emitter.once(name, listener);
		} else {
			emitter.on(name, listener);
		}
	} else if (typeof emitter.addEventListener === 'function') {
		// EventTarget does not have `error` event semantics like Node
		// EventEmitters, we do not listen for `error` events here.
		emitter.addEventListener(name, function wrapListener(arg) {
			// IE does not have builtin `{ once: true }` support so we
			// have to do it manually.
			if (flags.once) {
				emitter.removeEventListener(name, wrapListener);
			}
			listener(arg);
		});
	} else {
		throw new TypeError('The "emitter" argument must be of type EventEmitter. Received type ' + typeof emitter);
	}
}

//**********************************************************************************************************************
//Make a object emitter
//**********************************************************************************************************************
var makeObjEventEmitter;
{
	let emitDeep=0;
	makeObjEventEmitter=function(obj){
		let events={};
		let mute=0;
		if(obj.emit){
			return;
		}
		obj.on=function(msg,callback){
			let cbkSet;
			cbkSet=events[msg];
			callback._call_once=false;
			if(!cbkSet){
				events[msg]=cbkSet=new Set();
				cbkSet.mute=0;
			}
			cbkSet.add(callback);
		};
		obj.once=function(msg,callback){
			let cbkSet;
			cbkSet=events[msg];
			callback._call_once=true;
			if(!cbkSet){
				events[msg]=cbkSet=new Set();
				cbkSet.mute=0;
			}
			cbkSet.add(callback);
		};
		obj.off=function(msg,callback){
			let cbkSet;
			cbkSet=events[msg];
			if(cbkSet){
				cbkSet.delete(callback);
			}
		};
		obj.muteEmit=function(msg){
			if(!msg) {
				mute += 1;
			}else {
				let cbkSet;
				cbkSet=events[msg];
				if(!cbkSet){
					events[msg]=cbkSet=new Set();
					cbkSet.mute=0;
				}
				cbkSet.mute+=1;
			}
		};
		obj.unmuteEmit=function(msg){
			if(!msg) {
				mute -= 1;
			}else {
				let cbkSet;
				cbkSet=events[msg];
				if(cbkSet){
					cbkSet.mute+=1;
				}
			}
		};
		obj.emit=function(msg,...args){
			let cbkSet,cbks,cbk;
			if(mute)
				return;
			cbkSet=events[msg];
			emitDeep++;
			if(emitDeep>20){
				console.warn("Emit too deep, no more emits");
				emitDeep--;
				return;
			}
			if(cbkSet){
				if(!cbkSet.mute) {
					cbks = Array.from(cbkSet.keys());
					for (cbk of cbks) {
						cbk(...args);
						if (cbk._call_once) {
							cbkSet.delete(cbk);
						}
					}
				}
			}
			emitDeep--;
		};
		obj.eventNames=function(){
			return Object.keys(events);
		};
		obj.removeAllListeners=function(eventName){
			if(eventName){
				let cbkSet;
				cbkSet=events[eventName];
				if(cbkSet){
					cbkSet.clear();
				}
			}else{
				events={};
			}
		};
	}
}

//***************************************************************************
//callAtfer function:
//***************************************************************************
let callAfter;
{
	let aboutCall=0;
	let callList=[];
	let makeCall=function(){
		let list,i,n;
		list=callList;
		aboutCall=0;
		callList=[];
		n=list.length;
		for(i=0;i<n;i++){
			list[i]();
		}
	}
	callAfter=async function(func,timeout){
		let pms;
		if(!timeout){
			callList.push(func);
			if(aboutCall){
				return;
			}
			aboutCall=1;
			pms=new Promise((resolve,reject)=>{
				resolve();
			});
			await pms;
			makeCall();
			return;
		}
		window.setTimeout(func,timeout);
	};
}

//***************************************************************************
//Notify-Object
//***************************************************************************
let makeNotify;
{
	makeNotify=function(self){
		let m_NotifyPaused;
		let m_viewHubIn = {};
		let m_viewHubOn = {};
		let m_isInEnvList = 0;
		let m_NotifyOnMsgHash = {};
		let m_PendingNofifyOn=[];
		let m_msgValHash={};
		let removeValBindOfView;
		let notifyToMap,notifyHubOn,notifyOnAll;
		let muteNotify=false;
		if(self.emitNotify){
			return;
		}
		//---------------------------------------------------------------
		//make a property val notify-able, fires notify when this property changes:
		self.upgradeVal = function (name, msg) {
			var oldMsg, curVal, desc, oldGet, oldSet,msgList;
			if (!(name in self)) {
				return;
			}
			if (!msg) {
				msg = "*";//default notify message is "*"
			}
			if(Array.isArray(msg)){
				msgList=msg;
			}
			oldMsg = m_msgValHash[name];
			if (oldMsg) {
				if (msg !== oldMsg) {
					throw "JAXDataObj upgradVal error: val " + name + " is already been upgraded with diffrent msg " + oldMsg + ", new msg: " + msg;
				}
				return;
			}
			desc = Object.getOwnPropertyDescriptor(self, name);
			oldGet = desc.get;
			oldSet = desc.set;
			curVal = self[name];
			m_msgValHash[name] = msg;
			if(msgList){
				//Mapping:
				Object.defineProperty(self, name,
					{
						enumerable: desc.enumerable,
						configurable: true,
						set: function (newVal) {
							let msg;
							curVal = newVal;
							if (oldSet) {
								oldSet.call(self, newVal);
							}
							for(msg of msgList) {
								//notifyHubIn(msg);//这个要去掉
								notifyHubOn(msg);
							}
							return newVal;
						},
						get: function () {
							return oldGet ? oldGet.call(self) : curVal;
						}
					}
				);
			}else {
				//Mapping:
				Object.defineProperty(self, name,
					{
						enumerable: desc.enumerable,
						configurable: true,
						set: function (newVal) {
							curVal = newVal;
							if (oldSet) {
								oldSet.call(self, newVal);
							}
							notifyHubOn(msg);
							return newVal;
						},
						get: function () {
							return oldGet ? oldGet.call(self) : curVal;
						}
					}
				);
			}
		};
		
		//---------------------------------------------------------------
		//Get a "upgraded" property val's notify message string:
		self.getValMsg = function (name) {
			return m_msgValHash[name];
		};
		
		//---------------------------------------------------------------
		//Install a message tracer:
		self.onNotify=self.bindValNotify = function (msgName,func,view,once=0) {
			var map, set, msg;
			if (!func) {
				console.error("hub notify function!!");
				return;
			}
			if (!(msgName in self)) {
				msg=msgName;
			}else {
				msg = m_msgValHash[msgName];
			}
			if(!msg){
				throw ""+msgName+" is not upgraded!";
			}
			map = m_viewHubOn[msg];
			if (!map) {
				map = m_viewHubOn[msg] = new Map();
				map.mute=0;
			}
			set = map.get(view);
			if (!set) {
				set = new Set();
				map.set(view, set);
			}
			if(!once) {
				set.add(func);
			}else{
				let onceFunc;
				onceFunc=function(...args){
					func(...args);
					self.off(msg,onceFunc,view);
				};
				set.add(onceFunc);
			}
			return msg;
		};
		
		//---------------------------------------------------------------
		//Install an one-time message tracer
		self.onceNotify=function(msgName,func,view){
			self.onNotify(msgName,func,view,1);
		};
		
		//---------------------------------------------------------------
		//Uninstall all message tracers of a view
		self.removeValBindOfView = removeValBindOfView = function (msgName, view) {
			var list, i, n, stub;
			if (!msgName) {
				list = m_viewHubIn;
				for (i in list) {
					removeValBindOfView(i, view);
				}
				list = m_viewHubOn;
				for (i in list) {
					removeValBindOfView(i, view);
				}
				return;
			}
			list = m_viewHubIn[msgName];
			if (list) {
				list.delete(view);
			}
			list = m_viewHubOn[msgName];
			if (list) {
				list.delete(view);
			}
		};
		
		//---------------------------------------------------------------
		//Uninstall a message tracer:
		self.offNotify=self.removeValNotify = function (msgName, func, view) {
			var list, map, set, i, msg;
			if (!msgName) {
				list = m_viewHubIn;
				for (i in list) {
					msg=i;
					self.removeValNotify(msg, view, func);
				}
				list = m_viewHubOn;
				for (i in list) {
					msg=i;
					self.removeValNotify(i, view, func);
				}
				return;
			}
			map = m_viewHubIn[msgName];
			if (map) {
				set = map.get(view);
				if (set) {
					set.delete(func);
				}
			}
			map = m_viewHubOn[msgName];
			if (map) {
				set = map.get(view);
				if (set) {
					set.delete(func);
				}
			}
		};
		
		//---------------------------------------------------------------
		notifyToMap = function (map) {
			var views, view, set, func;
			views = map.keys();
			for (view of views) {
				if (!view || view.allowValNotify!==false) {
					set = map.get(view);
					for (func of set) {
						func();
					}
				}
			}
		};
		
		//---------------------------------------------------------------
		//Set to fire a message notify, 
		self.emitNotify=self.notifyValMsgOn = notifyHubOn = function (msg) {
			if(!m_NotifyOnMsgHash[msg] && !muteNotify) {
				let map = m_viewHubOn[msg];
				if(map && map.mute){
					return;
				}
				
				m_NotifyOnMsgHash[msg] = 1;
				m_PendingNofifyOn.push(msg);
				if (m_isInEnvList)
					return;
				m_isInEnvList = 1;
				callAfter(notifyOnAll);
			}
		};
		
		//---------------------------------------------------------------
		//Fire all panding messages:
		notifyOnAll = function () {
			var map, msg, list, loop;
			m_isInEnvList = 0;
			if (m_NotifyPaused) {
				return;
			}
			loop = 0;
			do {
				list = m_PendingNofifyOn.splice(0);
				for (msg of list) {
					m_NotifyOnMsgHash[msg] = 0;
					map = m_viewHubOn[msg];
					if (map) {
						notifyToMap(map);
					}
				}
				loop++;
				if (loop > 3) {
					console.warn(`JAXDataObj notify too many times.`);
					break;
				}
			} while (m_PendingNofifyOn.length);
		};
		
		//---------------------------------------------------------------
		Object.defineProperty(self,"pauseValNotify",{
			get:function(){
				return m_NotifyPaused;
			},
			set:function(v){
				v=v?1:0;
				m_NotifyPaused=v;
				return v;
			}
		})
		
		//-------------------------------------------------------------------
		self.muteNotify=function(msg){
			if(msg){
				let map;
				map = m_viewHubOn[msg];
				if (!map) {
					map = m_viewHubOn[msg] = new Map();
					map.mute=1;
				}
			}else {
				muteNotify++;
			}
		};
		
		//-------------------------------------------------------------------
		self.unmuteNotify=function(msg){
			if(msg){
				let map;
				map = m_viewHubOn[msg];
				if (map) {
					map.mute-=1;
				}
			}else {
				muteNotify--;
			}
		};
	};
}


//>>>>>>Node2Coke>>>>>>
export default module$1.exports;
var export$1=module$1.exports['once'];
export {export$1 as once,EventEmitter,makeObjEventEmitter,makeNotify,callAfter};
//<<<<<<Node2Coke<<<<<<