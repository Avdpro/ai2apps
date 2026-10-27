/* Trusted Desktop Home QR dialog. Never mounted in Mobile or Package frames. */
(() => {
    'use strict';
    const dialog = document.querySelector('[data-home-space-dialog][data-desktop-mobile-agent]');
    const opener = document.querySelector('[data-home-space-open]');
    if (!dialog || !opener) return;
    const find = selector => dialog.querySelector(selector);
    const status = find('[data-agent-desktop-status]');
    const label = find('[data-agent-desktop-label]');
    const image = find('[data-home-space-qr]');
    const scanned = find('[data-agent-scanned]');
    const allow = find('[data-agent-allow]');
    const optionLabel = find('[data-agent-option-label]');
    let unified = false;
    const confirm = find('[data-agent-confirm]');
    let device, connection, state, token, timer, offset = 0, busy = false, reading = false, revision = 0, lastError = '', appsTogether = false;

    async function json(path, body) {
        if (body !== undefined && !token) {
            const response = await fetch('/v1/platform/remote/mobile-agent/confirmation', {credentials: 'same-origin'});
            const value = await response.json();
            if (!response.ok) throw Error(typeof value.detail === 'string' ? value.detail : '请先登录本机管理员账户');
            token = value.token;
            const current = token;
            setTimeout(() => { if (token === current) token = null; }, 50000);
        }
        const response = await fetch(path, {
            method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store',
            headers: body === undefined ? {} : {'Content-Type': 'application/json', 'X-AI2Apps-Desktop-Confirm': token},
            body: body === undefined ? undefined : JSON.stringify(body),
        });
        const value = await response.json();
        if (!response.ok) throw Error(typeof value.detail === 'string' ? value.detail : value.detail?.message || value.error?.message || '连接操作失败');
        return value;
    }
    const call = (path, body) => json('/v1/platform/remote/mobile-agent/' + encodeURIComponent(device) + path, body);
    const remaining = () => Math.max(0, Math.ceil((Date.parse(state?.displayDeadline) - Date.now() + offset) / 1000) || 0);
    function paint() {
        if(optionLabel)optionLabel.parentElement.hidden=!connection;
        if(optionLabel)optionLabel.textContent=unified?'断开其它客户端连接':'允许运行 Agent（旧协议）';
        const pending = state?.status === 'pending' && remaining() > 0;
        const ack = state?.status === 'awaiting_ack';
        const isScanned = ['pending', 'awaiting_ack', 'awaiting_exchange', 'active', 'chat'].includes(state?.status);
        scanned.hidden = !isScanned;
        allow.disabled = busy || !pending;
        if (!pending && !ack) allow.checked = false;
        confirm.disabled = busy || (!pending && !ack);
        confirm.textContent = ack ? '重试确认' : (unified ? '确认连接' : '确认并关闭');
        label.textContent = state?.clientLabel ? String(state.clientLabel) : '';
        const messages = {awaiting_exchange: '已确认，等待手机完成连接。', active: '手机已完成连接。', qr: '', pending: pending ? '手机已扫码，请在 ' + remaining() + ' 秒内确认。' : '确认已超时，请关闭后重新扫码。', awaiting_ack: '确认回执尚未完成，请重试同一次确认。', expired: '二维码或确认已超时，请关闭后重试。', revoked: '连接已撤销。', denied: '连接已拒绝。'};
        status.textContent = lastError || (messages[state?.status] ?? (busy ? '正在准备连接二维码…' : '正在检查连接…'));
        status.hidden = !status.textContent;
    }
    async function poll(version) {
        paint();
        if (busy || reading || !connection || version !== revision || !dialog.open) return;
        reading = true;
        try {
            const value = await call('/pairings/' + connection);
            if (version !== revision || !dialog.open) return;
            if (busy) return;
            state = value;
            offset = Date.now() - value.serverTime * 1000;
            lastError = '';
        } catch (error) { if (version === revision) lastError = error.message; }
        finally { reading = false; if (version === revision) paint(); }
    }
    opener.addEventListener('click', async event => {
        if (!event.isTrusted || dialog.open) return;
        const version = ++revision;
        clearInterval(timer); device = connection = state = null; lastError = ''; busy = true; reading = false;
        allow.checked = false; image.hidden = true; image.removeAttribute('src');
        dialog.showModal(); paint();
        try {
            // Bind to the connector serving this Local, never a primary or arbitrary device.
            await json('/v1/platform/remote/devices/reconcile', {});
            const remote = await json('/v1/platform/remote/status');
            if (version !== revision || !dialog.open) return;
            const local = remote.devices?.find(item => item.deviceId === remote.connector?.deviceId);
            if (!local) throw Error('此 Desktop 的公网连接尚未就绪，请稍后重新打开二维码。');
            if (!local.enabled || local.status !== 'active') throw Error('请先开启此 Desktop 的公网访问。');
            if (!local.proxyConnected) throw Error('公网连接正在恢复，请稍后重新打开二维码。');
            device = local.deviceId;
            const current = await call('/status');
            if (version !== revision || !dialog.open) return;
            // This prepares enforcement only. No Agent authority exists before post-scan consent and ACK.
            if (!current.ready) await call('/configure', {enabled: true});
            if (version !== revision || !dialog.open) return;
            const value = await call('/pairings', {});
            if (version !== revision || !dialog.open) return;
            unified=value.mobileAccessProtocol==='owner-mobile-unified-v1'&&value.commitMode==='exchange-v1';
            connection = value.connectionId;appsTogether=value.appHandoffProtocol==='desktop-mobile-app-handoff-v1';
            if (!String(value.pairingQrDataUrl).startsWith('data:image/svg+xml;base64,')) throw Error('二维码格式无效。');
            image.src = value.pairingQrDataUrl; image.hidden = false; state = {status: 'qr'};
            timer = setInterval(() => poll(version), 500);
        } catch (error) { if (version === revision) lastError = error.message; }
        finally { if (version === revision) { busy = false; paint(); } }
    });
    async function decide(event, choice) {
        if (!event.isTrusted || busy || !connection) return;
        const ack = state?.status === 'awaiting_ack';
        if (!ack && (state?.status !== 'pending' || remaining() <= 0)) return;
        const version = revision;
        busy = true; lastError = ''; paint();
        try {
            const value = await call('/pairings/' + connection + (ack ? '/ack' : '/decision'), ack ? {} : {decision: choice, expectedGeneration: state.generation, humanConfirmed: true, ...(unified&&choice==='connect'?{disconnectOtherClients:allow.checked}:{})});
            if (version !== revision || !dialog.open) return;
            state = value;
            if (!['awaiting_exchange','active', 'chat', 'denied'].includes(value.status)) throw Error('连接尚未确认完成。');
            // Closing this UI does not commit authority; the phone still exchanges.
            dialog.close();
        } catch (error) { if (version === revision) lastError = error.message; }
        finally { if (version === revision) { busy = false; paint(); } }
    }
    confirm.addEventListener('click', event => decide(event, unified ? 'connect' : allow.checked ? 'agent' : 'chat'));
    find('[data-agent-close]').addEventListener('click', event => {
        if (!event.isTrusted || busy) return;
        if (state?.status === 'pending' && remaining() > 0) decide(event, 'deny');
        else dialog.close();
    });
    dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
    dialog.addEventListener('close', () => { ++revision; clearInterval(timer); allow.checked = false; allow.disabled = true; token = null; });
    window.addEventListener('pagehide', () => { ++revision; clearInterval(timer); });
    paint();
})();
