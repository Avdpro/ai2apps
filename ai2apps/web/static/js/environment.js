function environmentCheck() {
    return {
        report: null,
        loading: false,
        applying: '',
        error: '',
        lastScanLabel: '',

        async scan(network = false) {
            this.loading = true;
            this.error = '';
            try {
                const response = await fetch(`/admin/api/environment-check?network=${network ? 'true' : 'false'}`);
                if (!response.ok) throw new Error(await this.readError(response));
                this.report = await response.json();
                this.lastScanLabel = `${new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})} 更新`;
                this.$nextTick(() => window.lucide?.createIcons());
            } catch (error) {
                this.error = error?.message || '环境检查失败';
            } finally {
                this.loading = false;
            }
        },

        async applyAction(action) {
            this.applying = action.id;
            this.error = '';
            try {
                const response = await fetch('/admin/api/environment-check/actions', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action_id: action.id}),
                });
                if (!response.ok) throw new Error(await this.readError(response));
                await this.scan(false);
            } catch (error) {
                this.error = error?.message || '配置应用失败';
            } finally {
                this.applying = '';
            }
        },

        async readError(response) {
            try {
                const body = await response.json();
                return typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || body);
            } catch (_) {
                return `请求失败（HTTP ${response.status}）`;
            }
        },

        formatBytes(value) {
            if (!Number.isFinite(value)) return '—';
            const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
            let size = value;
            let unit = 0;
            while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
            return `${size >= 100 || unit === 0 ? size.toFixed(0) : size.toFixed(1)} ${units[unit]}`;
        },
        formatNumber(value) { return Number(value || 0).toLocaleString(); },
        passedCount() { return this.report?.checks?.filter(item => ['pass', 'skipped'].includes(item.status)).length || 0; },
        overallLabel() { return {healthy: '运行条件良好', warning: '存在优化项', critical: '需要处理'}[this.report?.status] || '检查中'; },
        statusLabel(status) { return {pass: '通过', warning: '注意', fail: '失败', critical: '严重', skipped: '待检查'}[status] || status; },
        statusIcon(status) { return ['pass', 'skipped'].includes(status) ? 'check' : (status === 'warning' ? 'triangle-alert' : 'x'); },
    };
}
