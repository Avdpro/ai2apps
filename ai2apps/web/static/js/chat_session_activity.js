/* Read-only presentation of durable Run snapshots, independent of executor/Tool identity. */
(() => {
    'use strict';
    const terminal = new Set(['completed','failed','cancelled','interrupted']);
    function summary(run) {
        const result = {};
        for (const key of ['id','session_id','parent_run_id','root_run_id','status','revision','created_at','updated_at','finished_at']) result[key] = run[key];
        result.output = run.output?.message_id ? {message_id:run.output.message_id} : null;
        result.interactions = (run.interactions || []).filter(item => item.status === 'pending').map(() => ({status:'pending'}));
        return result;
    }
    function merge(snapshots, live) {
        const runs = new Map();
        for (const run of [...snapshots, ...live]) {
            const old = runs.get(run.id);
            if (!old || Number(run.revision || 0) > Number(old.revision || 0) ||
                (Number(run.revision || 0) === Number(old.revision || 0) && String(run.updated_at || '') >= String(old.updated_at || ''))) runs.set(run.id, run);
        }
        return [...runs.values()];
    }
    function latest(runs) {
        return runs.filter(run => !run.parent_run_id).sort((a,b) =>
            String(b.created_at || '').localeCompare(String(a.created_at || '')))[0] || null;
    }
    const stamp = run => run && terminal.has(run.status) && run.status !== 'cancelled'
        ? run.id + ':' + run.status : '';
    function state(runs, streaming, seen, ready = true) {
        const root = latest(runs);
        const relevant = runs.filter(run => !run.parent_run_id || !root ||
            (run.root_run_id === root.id && !terminal.has(root.status)));
        if (relevant.some(run => (run.status === 'interrupted' && run.id === root?.id) ||
            (!terminal.has(run.status) && (['waiting_input','waiting_capability'].includes(run.status) ||
                (run.interactions || []).some(item => item.status === 'pending'))))) return 'attention';
        if (streaming || relevant.some(run => !terminal.has(run.status))) return 'busy';
        if (ready && stamp(root) && stamp(root) !== seen) return 'unread';
        return 'idle';
    }
    window.AI2AppsChatSessionActivity = {merge, latest, stamp, state, summary};
})();
