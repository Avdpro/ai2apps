(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (root) root.AI2AppsStreamingTTS = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    const HARD_BOUNDARY = /[。！？!?；;\n]/;
    const SOFT_BOUNDARY = /[，,、：:\s]/;

    function cleanSpeechText(value) {
        return String(value || '')
            .replace(/```[\s\S]*?```/g, ' ')
            .replace(/`([^`]*)`/g, '$1')
            .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
            .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
            .replace(/https?:\/\/\S+/g, ' ')
            .replace(/^\s{0,3}(?:#{1,6}|>|[-+*]\s|\d+[.)]\s)\s*/gm, '')
            .replace(/[|*_~]/g, '')
            .replace(/[\t\r ]+/g, ' ')
            .replace(/\s*\n\s*/g, ' ')
            .trim();
    }

    class StreamingTextSegmenter {
        constructor(options = {}) {
            this.minChars = Math.max(1, Number(options.minChars) || 8);
            this.softChars = Math.max(this.minChars, Number(options.softChars) || 24);
            this.maxChars = Math.max(this.softChars, Number(options.maxChars) || 56);
            this.buffer = '';
        }

        append(value) {
            this.buffer += String(value || '');
            return this._extract(false);
        }

        flushSoft() {
            if (cleanSpeechText(this.buffer).length < this.softChars) return [];
            const boundary = this._lastBoundary(this.buffer, SOFT_BOUNDARY);
            if (boundary < this.minChars) return [];
            const segment = this.buffer.slice(0, boundary + 1);
            this.buffer = this.buffer.slice(boundary + 1);
            const cleaned = cleanSpeechText(segment);
            return cleaned ? [cleaned] : [];
        }

        finish() {
            const segments = this._extract(true);
            const tail = cleanSpeechText(this.buffer);
            this.buffer = '';
            if (tail) segments.push(tail);
            return segments;
        }

        reset() {
            this.buffer = '';
        }

        _extract(finishing) {
            const segments = [];
            while (this.buffer) {
                const hard = this._firstBoundary(this.buffer, HARD_BOUNDARY);
                if (hard >= 0) {
                    const candidate = this.buffer.slice(0, hard + 1);
                    this.buffer = this.buffer.slice(hard + 1);
                    const cleaned = cleanSpeechText(candidate);
                    if (cleaned) segments.push(cleaned);
                    continue;
                }
                if (cleanSpeechText(this.buffer).length < this.maxChars) break;
                let split = this._lastBoundary(this.buffer.slice(0, this.maxChars + 1), SOFT_BOUNDARY);
                if (split < this.minChars) split = this.maxChars - 1;
                const candidate = this.buffer.slice(0, split + 1);
                this.buffer = this.buffer.slice(split + 1);
                const cleaned = cleanSpeechText(candidate);
                if (cleaned) segments.push(cleaned);
            }
            return segments;
        }

        _firstBoundary(value, pattern) {
            for (let index = 0; index < value.length; index += 1) {
                if (pattern.test(value[index])) return index;
            }
            return -1;
        }

        _lastBoundary(value, pattern) {
            for (let index = value.length - 1; index >= 0; index -= 1) {
                if (pattern.test(value[index])) return index;
            }
            return -1;
        }
    }

    // One synthesis at a time; playback overlaps the next bounded synthesis.
    async function playSegments({segments,synthesize,play,signal,maxPrepared=2}) {
        const queue=[];let done=false,failure=null,stopped=false,waiters=[];
        const wake=()=>{const current=waiters;waiters=[];current.forEach(resolve=>resolve());};
        const wait=()=>new Promise(resolve=>waiters.push(resolve));
        const aborted=()=>signal?.aborted||stopped;
        const abortError=()=>Object.assign(new Error('Speech stopped'),{name:'AbortError'});
        signal?.addEventListener('abort',wake);
        const producer=(async()=>{
            try{for(const segment of segments){
                while(!aborted()&&queue.length>=maxPrepared)await wait();
                if(aborted())return;
                const blob=await synthesize(segment);
                if(aborted())return;
                queue.push(blob);wake();
            }}catch(error){failure=error;}finally{done=true;wake();}
        })();
        try{while(true){
            while(!aborted()&&!failure&&!queue.length&&!done)await wait();
            if(aborted())throw abortError();
            if(failure)throw failure;
            if(!queue.length&&done)break;
            const blob=queue.shift();wake();await play(blob);
        }await producer;
        }finally{stopped=true;wake();signal?.removeEventListener('abort',wake);}
    }

    return { StreamingTextSegmenter, cleanSpeechText, playSegments };
});
