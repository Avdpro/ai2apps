(() => {
    'use strict';
    const $ = id => document.getElementById(id);
    const zh = (new URLSearchParams(location.search).get('locale') || navigator.language).startsWith('zh');
    const tr = (cn, en) => zh ? cn : en;
    const call = (action, args) => window.ShareHost.request(action, args);
    const root = $('share-social');
    const node = (tag, text) => {
        const element = document.createElement(tag);
        if (text) element.textContent = text;
        return element;
    };
    function button(text, handler) {
        const element = node('button', text);
        element.type = 'button';
        element.onclick = async () => {
            element.disabled = true;
            try { await handler(); }
            catch (error) { showError(error); }
            finally { element.disabled = false; }
        };
        return element;
    }
    function label(text, input) {
        const element = node('label', text);
        element.append(input);
        return element;
    }
    function showError(error) {
        const messages = {
            x_connection_required: tr('尚未配置 X 发布授权。请在 Desktop 配置 X 用户 API 授权。', 'Connect an authorized X user API credential on Desktop.'),
            public_confirmation_required: tr('请先确认本次发布。', 'Approve this publication first.'),
            social_content_required: tr('请输入正文或选取素材。Rednote 需要图片或视频。', 'Add text or media. Rednote requires photos or a video.'),
            social_choose_one_video_or_images: tr('请选择多张图片或一个视频。', 'Choose photos or one video.'),
            mobile_artifact_size_limit: tr('手机单次上传最多 19 MB。请在 Desktop 选择较大的文件。', 'Mobile uploads are limited to 19 MB. Use Desktop for larger files.')
        };
        status.textContent = messages[error.message] || error.message;
    }
    const form = node('form');
    const fields = node('section');
    const platform = node('select');
    for (const [value, name] of [['x', 'X'], ['rednote', 'Rednote']]) {
        const option = node('option', name);
        option.value = value;
        platform.append(option);
    }
    const title = node('input');
    title.maxLength = 160;
    const titleLabel = label(tr('笔记标题', 'Note title'), title);
    const body = node('textarea');
    body.rows = 5;
    body.maxLength = 10000;
    body.style.cssText = 'display:block;width:100%;font:inherit;padding:10px;border:1px solid #d6d3d1;border-radius:10px';
    const files = node('input');
    files.type = 'file';
    files.multiple = true;
    const prepare = node('button', tr('准备并预览', 'Prepare and preview'));
    prepare.className = 'primary';
    const status = node('p');
    status.setAttribute('role', 'status');
    const preview = node('section');
    preview.hidden = true;
    const history = node('section');
    let timer;
    function syncPlatform() {
        titleLabel.hidden = platform.value !== 'rednote';
        files.accept = '.jpg,.jpeg,.png,.webp,.mp4' + (platform.value === 'rednote' ? ',.mov' : '');
        preview.hidden = true;
    }
    platform.onchange = syncPlatform;
    syncPlatform();
    fields.append(label(tr('发布平台', 'Platform'), platform), titleLabel, label(tr('正文', 'Text'), body),
                  label(tr('图片或一个视频', 'Photos or one video'), files), prepare);
    form.append(fields);
    root.append(form, status, preview, history);
    form.onsubmit = async event => {
        event.preventDefault();
        prepare.disabled = true;
        preview.hidden = true;
        status.textContent = '';
        try {
            const draft = await call('social-prepare', {destination: platform.value,
                title: platform.value === 'rednote' ? title.value : '', body: body.value, files: Array.from(files.files)});
            renderDraft(draft);
            await refresh();
        } catch (error) { showError(error); }
        finally { prepare.disabled = false; }
    };
    function renderDraft(draft) {
        preview.hidden = false;
        preview.replaceChildren(node('h2', tr('发布预览', 'Publication preview')));
        if (draft.account) preview.append(node('strong', '@' + draft.account.username));
        if (draft.title) preview.append(node('h3', draft.title));
        const text = node('p', draft.body);
        text.style.cssText = 'white-space:pre-wrap;overflow-wrap:anywhere';
        preview.append(text);
        draft.media.forEach((item, index) => {
            const line = node('p', item.filename + ' · ' + Math.ceil(item.size / 1024) + ' KB ');
            line.append(button(tr('下载素材', 'Download media'),
                () => call('social-download', {draft_id: draft.id, index})));
            preview.append(line);
        });
        if (draft.destination === 'rednote') {
            preview.append(node('p', tr('请在已登录的 Rednote 创作中心上传素材并提交。', 'Upload the media and submit in your signed-in Rednote Creator Center.')));
            preview.append(button(tr('复制标题与正文', 'Copy title and text'),
                () => navigator.clipboard.writeText([draft.title, draft.body].filter(Boolean).join('\n\n'))));
            preview.append(' ', button(tr('打开创作中心', 'Open Creator Center'), () => call('social-open')));
        } else if (draft.status === 'prepared') {
            const confirmed = node('input');
            confirmed.type = 'checkbox';
            const approval = button(tr('批准并发布到 X', 'Approve and publish to X'), async () => {
                if (!confirmed.checked) return;
                const updated = await call('social-publish', {draft_id: draft.id, digest: draft.digest, confirmed: true});
                renderDraft(updated);
                await refresh();
            });
            approval.disabled = true;
            approval.className = 'primary';
            confirmed.onchange = () => { approval.disabled = !confirmed.checked; };
            preview.append(label(tr(' 我批准将以上正文和媒体发布到此 X 账号。', ' I approve posting this text and media to this X account.'), confirmed), approval);
        }
    }
    const labels = {
        prepared: tr('待批准', 'Awaiting approval'), pending_manual_publish: tr('待手动发布', 'Ready for manual posting'),
        queued: tr('已排队', 'Queued'), uploading: tr('上传媒体中', 'Uploading media'),
        dispatching: tr('正在发布', 'Posting'), published: tr('已发布', 'Published'),
        failed: tr('发布失败', 'Failed'), cancelled: tr('已取消', 'Cancelled'),
        interrupted: tr('已中断', 'Interrupted'), outcome_unknown: tr('发布结果未知，请在 X 核对', 'Outcome unknown. Check X.')
    };
    async function refresh() {
        clearTimeout(timer);
        const {items} = await call('social-history');
        history.replaceChildren(node('h2', tr('社交发布记录', 'Social publication history')),
                                button(tr('刷新', 'Refresh'), refresh));
        for (const draft of items) {
            const row = node('div');
            row.className = 'history-item';
            const platformName = draft.destination === 'x' ? 'X' : 'Rednote';
            row.append(node('strong', platformName + ' · ' + (draft.title || draft.body || draft.media[0]?.filename || '').slice(0, 80)),
                       node('p', labels[draft.status] || draft.status));
            if (draft.url && /^https:\/\/x\.com\/[A-Za-z0-9_]+\/status\/[0-9]+$/.test(draft.url))
                row.append(button(tr('复制帖子链接', 'Copy post link'), () => navigator.clipboard.writeText(draft.url)));
            else if (['prepared', 'pending_manual_publish'].includes(draft.status))
                row.append(button(tr('打开草稿', 'Open draft'), () => renderDraft(draft)));
            history.append(row);
        }
        if (!root.hidden && items.some(item => ['queued', 'uploading', 'dispatching'].includes(item.status)))
            timer = setTimeout(() => refresh().catch(showError), 2500);
    }
    const webMode = $('share-web-mode');
    const socialMode = $('share-social-mode');
    webMode.textContent = tr('分享网页', 'Share a web page');
    socialMode.textContent = tr('发布图文／视频', 'Publish photos or video');
    function switchMode(social) {
        webMode.setAttribute('aria-pressed', String(!social));
        socialMode.setAttribute('aria-pressed', String(social));
        root.hidden = !social;
        $('share-web').hidden = social;
        if (social) refresh().catch(showError);
        else clearTimeout(timer);
    }
    webMode.onclick = () => switchMode(false);
    socialMode.onclick = () => switchMode(true);
})();
