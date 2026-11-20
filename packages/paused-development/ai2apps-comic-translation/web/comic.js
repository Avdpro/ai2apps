(() => {
    'use strict';
    const $ = id => document.getElementById(id);
    const L = window.ComicLayout;
    const pages = [], pending = new Map();
    const locale = new URLSearchParams(location.search).get('locale') || 'en';
    let zh = locale.startsWith('zh'), mobile = false, port, serial = 0, busy = false, stopped = false;
    let selected = 0, nextItemId = 0, modelEntries = [], previewUrl, drag, drawingBox;
    let previewSkipped = new Set(), dialoguePage;
    let ocrReady = null;
    const pageLimit = 50;
    const pageLimitMessage = () => t(`A batch supports up to ${pageLimit} pages.`, `每批最多 ${pageLimit} 页。`);
    const t = (en, cn) => zh ? cn : en;
    const node = (tag, text, props = {}) => {
        const result = document.createElement(tag);
        if (text != null) result.textContent = text;
        return Object.assign(result, props);
    };
    const button = (label, click) => node('button', label, {type: 'button', onclick: click});
    const status = text => { $('status').textContent = text; };
    function showBatchProgress(done = 0, total = null) {
        const progress = $('progress-bar');
        const count = $('progress-count');
        $('batch-progress').hidden = false;
        count.textContent = total === null ? t('Counting steps…', '正在统计步骤…') :
            total === 0 ? t('No pending steps', '没有待处理步骤') :
                t(`${Math.floor(done * 100 / total)}% · ${done}/${total} steps`,
                    `${Math.floor(done * 100 / total)}% · ${done}/${total} 步`);
        progress.hidden = total === 0;
        if (total === null) progress.removeAttribute('value');
        else if (total > 0) {
            progress.max = total;
            progress.value = done;
        }
    }
    const current = () => pages[selected];
    const allowed = (a, b) => a[0] >= b[0] && a[1] >= b[1] && a[2] <= b[2] && a[3] <= b[3];

    function call(action, fields = {}, operation = 'owner.request') {
        return new Promise((resolve, reject) => {
            if (!port) { reject(Error(t('Studio is unavailable', '创意画坊连接不可用'))); return; }
            const id = ++serial;
            pending.set(id, {resolve, reject});
            port.postMessage({id, operation, action, ...fields});
        });
    }
    function clearPreview() {
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = null;
        previewSkipped.clear();
    }
    function localize() {
        document.documentElement.lang = zh ? 'zh-CN' : 'en';
        document.querySelectorAll('[data-zh]').forEach(element => {
            element.dataset.en ||= element.textContent;
            element.textContent = zh ? element.dataset.zh : element.dataset.en;
        });
        $('page-image').alt = t('Comic page', '漫画页');
        $('pages').setAttribute('aria-label', t('Comic pages', '漫画页'));
    }
    function state() {
        $('settings').disabled = busy || !port;
        for (const slot of $('pages').querySelectorAll('[data-asset-slot]')) {
            slot.assetSlot.update({disabled: busy || !port});
        }
        $('stop').hidden = !busy;
        for (const id of ['detect', 'recognize', 'translate', 'png', 'html']) $(id).disabled = !pages.length;
        $('translate').disabled ||= !$('model').value;
        $('recognize').disabled ||= ocrReady === false;
        $('translate').disabled ||= ocrReady === false && !pages.some(page => ordered(page).some(row => row.source.trim()));
        $('ocr-setup').hidden = ocrReady !== false;
        $('ocr-setup-message').textContent = mobile
            ? t('Set up SoMark OXR on your Mac, then refresh models here.', '请在 Mac 上安装或配置 SoMark OXR，然后在这里刷新模型。')
            : t('Automatic text recognition requires SoMark OXR.', '自动识别原文需要 SoMark OXR。');
        $('install-ocr').hidden = mobile;
        $('install-ocr').disabled = busy || !port;
        $('editor').hidden = !current();
        $('stop').disabled = stopped;
    }
    async function work(callback) {
        if (busy) return;
        busy = true;
        stopped = false;
        $('error').textContent = '';
        $('batch-progress').hidden = true;
        state();
        try { await callback(); }
        catch (error) { $('error').textContent = error.message || String(error); }
        finally {
            if (stopped) status(t('Stopped. Completed work is kept.', '已停止，已完成的结果保留。'));
            busy = false;
            render();
        }
    }
    async function refreshModels() {
        const saved = $('model').value;
        const result = await call('models');
        ocrReady = result.ocrReady ?? null;
        modelEntries = result.items || [];
        $('model').replaceChildren(node('option', t('Choose a model', '请选择模型'), {value: ''}),
            ...modelEntries.map(model => node('option',
                model.label + (model.local ? '' : t(' · remote', ' · 远程')), {value: model.id})));
        $('model').value = modelEntries.some(model => model.id === saved) ? saved : result.default || '';
    }
    async function addFiles(files, replaceIndex = pages.length, errors = []) {
        let replacing = replaceIndex < pages.length;
        for (const file of files) {
            if (stopped) break;
            if (!replacing && pages.length >= pageLimit) {
                errors.push(pageLimitMessage()); break;
            }
            try {
                if (!file.size || file.size > 16 * 1024 ** 2) throw Error(t('Use an image up to 16 MiB', '图片须小于 16 MiB'));
                const header = new Uint8Array(await file.slice(0, 12).arrayBuffer());
                const bytes = (start, expected) => expected.every((value, i) => header[start + i] === value);
                if (!bytes(0, [137,80,78,71,13,10,26,10]) && !bytes(0, [255,216,255]) &&
                    !(bytes(0, [82,73,70,70]) && bytes(8, [87,69,66,80]))) {
                    throw Error(t('Use PNG, JPEG or WebP', '仅支持 PNG、JPEG 或 WebP'));
                }
                const surface = await L.decode(file);
                const id = ++nextItemId, width = surface.width, height = surface.height;
                const preview = await L.png(L.crop(surface, L.FULL, 1100));
                surface.width = surface.height = 0;
                const page = {id, file, width, height, preview: URL.createObjectURL(preview), regions: [],
                    bubbleLinks: [], bubbleGroups: [],
                    analyzed: false, crop: null, proposal: null, cropUrl: null};
                if (replacing) {
                    releasePage(pages[replaceIndex]);
                    pages[replaceIndex] = page;
                    replacing = false;
                } else {
                    pages.push(page);
                }
            } catch (error) { errors.push(`${file.name} · ${error.message}`); }
        }
        if (errors.length) $('error').textContent = errors.join('\n');
        status(`${pages.length} ${t('pages loaded', '页已载入')}`);
        clearPreview();
    }
    function releasePage(page) {
        URL.revokeObjectURL(page.preview);
        if (page.cropUrl) URL.revokeObjectURL(page.cropUrl);
    }
    function region(box, automatic = false) {
        return {id: ++nextItemId, box, automatic, manualBounds: !automatic, enabled: true, source: '', translated: ''};
    }
    async function setCrop(page, bounds) {
        page.crop = bounds;
        if (page.cropUrl) URL.revokeObjectURL(page.cropUrl);
        page.cropUrl = null;
        if (bounds) {
            const surface = await L.decode(page.file);
            try { page.cropUrl = URL.createObjectURL(await L.png(L.crop(surface, bounds, 1100))); }
            finally { surface.width = surface.height = 0; }
        }
        clearPreview();
    }
    async function detectPage(page) {
        const result = await call('analyze', {file: page.file});
        page.proposal = result.crop;
        if ($('auto-crop').checked && result.crop) await setCrop(page, result.crop);
        const links = result.region_links || [];
        // Replace legacy geometry-only merges with separate OCR candidates.
        page.regions = page.regions.filter(row => !row.automatic || !row.parts ||
            !links.some(pair => pair.every(index => {
                const box = result.regions[index];
                return L.area(L.intersect(box, row.box)) >= .95 * L.area(box) && L.area(row.box) > 1.12 * L.area(box);
            })));
        const mapped = result.regions.map((box, index) => {
            const parts = result.region_parts?.[index];
            const previousBox = result.region_refinements?.[index];
            const existing = page.regions.find(row => L.area(L.intersect(row.box, box)) > L.area(box) * .65);
            if (existing) {
                const tightened = previousBox && existing.box.every((value, axis) => Math.abs(value - previousBox[axis]) < .002);
                if (existing.automatic && (tightened ||
                    (parts && JSON.stringify(existing.parts) !== JSON.stringify(parts)))) {
                    Object.assign(existing, {box, parts, source: '', translated: ''});
                }
                return existing.id;
            }
            if (page.regions.length === 32) return null;
            const row = region(box, true);
            if (parts) row.parts = parts;
            page.regions.push(row);
            return row.id;
        });
        page.bubbleLinks = links.map(pair => pair.map(index => mapped[index]))
            .filter(([a, b]) => a && b && a !== b);
        page.analyzed = true;
    }
    function included(page, row) { return row.enabled && allowed(row.box, page.crop || L.FULL); }
    function isVertical(page) {
        return $('direction').value === 'vertical' ||
            ($('direction').value === 'auto' && page.regions.some(row => /\p{Script=Han}|\p{Script=Hiragana}/u.test(row.source)));
    }
    function dialogueGroups(page, rows = page.regions) {
        const byId = new Map(rows.map(row => [row.id, row]));
        const groupById = new Map();
        for (const ids of page.bubbleGroups) {
            const group = ids.map(id => byId.get(id)).filter(Boolean);
            group.forEach(row => groupById.set(row.id, group));
        }
        return [...new Set(rows.map(row => groupById.get(row.id) || [row]))];
    }
    function ordered(page) {
        const vertical = isVertical(page);
        const sorted = L.orderDialogue(page.regions.filter(row => included(page, row)), vertical);
        return dialogueGroups(page, sorted).flat();
    }
    async function recognizePage(page, rows, advance) {
        if (!rows.length) return;
        const surface = await L.decode(page.file);
        try {
            for (const [index, row] of rows.entries()) {
                if (stopped) break;
                status(`${page.file.name} · OXR ${index + 1}/${rows.length}`);
                const [, , w, h] = L.pixels(row.box, page.width, page.height);
                const direction = $('direction').value;
                const vertical = direction === 'vertical' || (direction === 'auto' && h >= w * 1.2);
                const result = await call(vertical ? 'recognize-vertical' : 'recognize',
                    {file: await L.png(L.crop(surface, row.box, 1400, row.parts))});
                const text = result.text.trim();
                // A stray dot is a frequent OCR result for line art. Keep
                // intentional ellipses and punctuation such as「!?」.
                if (row.automatic && (text === '' || /^[.。．]$/u.test(text))) {
                    page.regions = page.regions.filter(other => other !== row);
                } else {
                    row.source = text;
                }
                advance();
            }
        } finally { surface.width = surface.height = 0; }
    }
    async function batch(gesture) {
        clearPreview();
        const failed = new Set(), errors = [];
        const detecting = gesture === 'detect';
        const translating = gesture === 'translate';
        const detectionPages = detecting ? pages : ocrReady === false ? [] : pages.filter(page => !page.analyzed);
        let done = 0;
        let total = detecting ? detectionPages.length : null;
        const advance = (steps = 1) => {
            done += steps;
            if (total !== null) showBatchProgress(done, total);
        };
        const failedPage = (page, error) => {
            failed.add(page.id);
            errors.push(`${page.file.name} · ${error.message}`);
        };
        const statusPanel = $('task-status');
        status(t('Preparing batch…', '正在准备批处理…'));
        showBatchProgress(0, total);
        statusPanel.scrollIntoView({block: 'center'});
        for (const [index, page] of detectionPages.entries()) {
            if (stopped) break;
            status(`${t('Detecting bubbles', '正在检测气泡')} ${index + 1}/${detectionPages.length} · ${page.file.name}`);
            try { await detectPage(page); }
            catch (error) { failedPage(page, error); }
            advance();
        }

        if (stopped && total === null) $('batch-progress').hidden = true;
        const profileVersion = translating ? profiles.version() : '';
        const needsTranslation = row => !displayTranslation(row) || (row.profileVersion || '') !== profileVersion;
        const recognition = new Map();
        const translation = new Set();
        if (!detecting && !stopped) {
            total = detectionPages.length;
            for (const page of pages) {
                if (failed.has(page.id)) continue;
                const rows = page.regions.filter(row => included(page, row));
                const missing = ocrReady === false ? [] : rows.filter(row => !row.source.trim());
                recognition.set(page.id, missing);
                total += missing.length;
                if (translating && (missing.length || rows.some(row => row.source.trim() && needsTranslation(row)))) {
                    translation.add(page.id);
                    total++;
                }
            }
            showBatchProgress(done, total);
            for (const page of pages) {
                if (stopped) break;
                const rows = recognition.get(page.id);
                if (!rows?.length) continue;
                const start = done;
                try { await recognizePage(page, rows, advance); }
                catch (error) { failedPage(page, error); advance(rows.length - (done - start)); }
            }
        }
        if (translating && !stopped) {
            const model = $('model').value, language = $('language').value;
            const glossary = profiles.glossary(), learned = [];
            const context = ($('context').checked ? pages.map(page => ordered(page).map(row => row.source.trim()).filter(Boolean)) : []);
            for (const [index, page] of pages.entries()) {
                if (stopped) break;
                if (!translation.has(page.id)) continue;
                if (failed.has(page.id)) { advance(); continue; }
                const rows = ordered(page).filter(row => row.source.trim());
                const targets = [];
                rows.forEach((row, index) => { if (needsTranslation(row)) targets.push(index); });
                if (!targets.length) { advance(); continue; }
                const candidates = L.bubbleCandidates(page, rows);
                const targeted = new Set(targets.map(index => rows[index].id));
                status(`${t('Translating', '正在翻译')} ${index + 1}/${pages.length} · ${page.file.name}`);
                try {
                    const result = await call('translate', {settings: {model, language,
                        texts: rows.map(row => row.source.trim()),
                        targets,
                        nearby_pairs: candidates.filter(([a, b]) => b === a + 1).map(([a]) => a),
                        bubble_candidates: candidates,
                        bubble_boxes: rows.map(row => row.box),
                        vertical: isVertical(page),
                        glossary,
                        before: (context[index - 1] || []).slice(-8).map(line => line.slice(0, 400)),
                        after: (context[index + 1] || []).slice(0, 8).map(line => line.slice(0, 400)),
                    }});
                    targets.forEach((index, i) => {
                        rows[index].translated = result.translations[i];
                        rows[index].translatedFor = language;
                        rows[index].profileVersion = profileVersion;
                    });
                    if (Array.isArray(result.bubble_groups)) {
                        const groups = result.bubble_groups.map(group => group.map(index => rows[index].id));
                        const grouped = new Set(groups.flat());
                        page.bubbleGroups = page.bubbleGroups.filter(group =>
                            !group.every(id => targeted.has(id)) && !group.some(id => grouped.has(id)));
                        page.bubbleGroups.push(...groups);
                    }
                    if (Array.isArray(result.new_terms)) {
                        profiles.addTerms(learned, result.new_terms);
                        profiles.addTerms(glossary, result.new_terms);
                    }
                } catch (error) { failedPage(page, error); }
                advance();
            }
            try { await profiles.learn(learned); }
            catch (error) { errors.push(error.message); }
        }
        $('error').textContent = errors.join('\n');
        status(errors.length ? t('Some work needs attention.', '部分处理结果需要检查。') :
            t('Batch finished. Review the detected regions and dialogue.', '批量处理完成，可检查选区、原文和译文。'));
    }
    function label(text, input) {
        const el = node('label');
        el.append(node('span', text), input);
        return el;
    }
    function transformParts(row, box) {
        return row.parts?.map(part => part.map((value, axis) => {
            const start = axis % 2, end = start + 2;
            const scale = (box[end] - box[start]) / (row.box[end] - row.box[start]);
            return box[start] + (value - row.box[start]) * scale;
        }));
    }
    function setRegionBounds(row, box) {
        row.parts = transformParts(row, box);
        row.box = box;
        row.automatic = false;
        row.manualBounds = true;
    }
    function drawBoxes() {
        const page = current();
        $('boxes').replaceChildren();
        if (!page) return;
        const clip = page.crop || L.FULL;
        const tip = node('span', null, {id: 'bubble-tooltip', className: 'bubble-tooltip', hidden: true});
        tip.setAttribute('role', 'tooltip');
        $('boxes').append(tip);
        function overlay(box, title, enabled, translation = '', row = null, outline = false) {
            const [left, top, right, bottom] = L.intersect(box, clip);
            const w = clip[2] - clip[0], h = clip[3] - clip[1];
            if (right <= left || bottom <= top) return;
            const item = node('span', outline ? '' : title, {className: 'box' + (enabled ? '' : ' off')});
            Object.assign(item.style, {left: (left - clip[0]) / w * 100 + '%', top: (top - clip[1]) / h * 100 + '%',
                width: (right - left) / w * 100 + '%', height: (bottom - top) / h * 100 + '%'});
            if (row) {
                item.classList.add('editable');
                if (outline) item.classList.add('multipart');
                item.dataset.regionId = row.id;
                const handle = node('span', null, {className: 'box-resize'});
                handle.setAttribute('aria-hidden', 'true');
                item.append(handle);
            }
            if (!translation) item.setAttribute('aria-hidden', 'true');
            else {
                item.classList.add('has-translation');
                item.tabIndex = 0;
                item.setAttribute('aria-label', `${t('Region', '区域')} ${title}`);
                item.setAttribute('aria-describedby', tip.id);
                const show = () => {
                    if (drag) return;
                    tip.textContent = translation;
                    tip.hidden = false;
                    const stage = $('stage');
                    const min = tip.offsetWidth / 2;
                    const center = item.offsetLeft + item.offsetWidth / 2;
                    tip.style.left = Math.max(min, Math.min(stage.clientWidth - min, center)) + 'px';
                    tip.style.top = (item.offsetTop >= tip.offsetHeight + 6 ?
                        item.offsetTop - tip.offsetHeight - 6 : item.offsetTop + item.offsetHeight + 6) + 'px';
                };
                const hide = () => { tip.hidden = true; tip.textContent = ''; };
                item.onpointerenter = show;
                item.onpointerleave = () => { if (document.activeElement !== item) hide(); };
                item.onfocus = show;
                item.onblur = hide;
                item.onkeydown = event => { if (event.key === 'Escape') hide(); };
            }
            $('boxes').append(item);
        }
        dialogueGroups(page).forEach((group, index) => {
            const translation = group.filter(row => row.enabled).map(displayTranslation).filter(Boolean).join('\n');
            for (const row of group) {
                if (previewUrl && (!displayTranslation(row) || previewSkipped.has(page.regions.indexOf(row)) ||
                        !included(page, row))) continue;
                const box = drag?.row === row && drawingBox ? drawingBox : row.box;
                const parts = box === row.box ? row.parts : transformParts(row, box);
                for (const part of parts || []) overlay(part, index + 1, row.enabled);
                overlay(box, index + 1, row.enabled, translation, row, !!parts);
            }
        });
        if (drawingBox && !drag?.row) overlay(drawingBox, '', true);
    }
    function displayTranslation(row) {
        return row.translatedFor && row.translatedFor !== $('language').value ? '' : row.translated.trim();
    }
    function regionControls(page) {
        const collapsed = new Set([...$('regions').querySelectorAll('details')]
            .filter(card => !card.open).map(card => card.dataset.region));
        $('regions').replaceChildren();
        function regionCard(row, heading) {
            const card = node('details', null, {className: 'region', open: !collapsed.has(String(row.id))});
            card.dataset.region = row.id;
            const subtitle = (displayTranslation(row) || row.source).trim().slice(0, 55);
            card.append(node('summary', subtitle ? `${heading} · ${subtitle}` : heading));
            const enabled = node('input', null, {type: 'checkbox', checked: row.enabled});
            enabled.onchange = () => { row.enabled = enabled.checked; drawBoxes(); };
            const tools = node('div', null, {className: 'tools'});
            const orientation = node('select');
            orientation.append(
                node('option', t('Automatic', '自动'), {value: 'auto'}),
                node('option', t('Horizontal', '横排'), {value: 'horizontal'}),
                node('option', t('Rotate 90°', '旋转 90°'), {value: 'rotate'}),
            );
            orientation.value = row.orientation || 'auto';
            orientation.onchange = () => { row.orientation = orientation.value; };
            if (!previewUrl) tools.append(label(t('Apply', '应用'), enabled), label(t('Translation layout', '译文排版'), orientation));
            tools.append(button(t('Remove', '删除'), () => work(async () => {
                page.regions = page.regions.filter(other => other !== row);
                page.bubbleGroups = page.bubbleGroups.map(group => group.filter(id => id !== row.id))
                    .filter(group => group.length > 1);
                page.bubbleLinks = page.bubbleLinks.filter(pair => !pair.includes(row.id));
                if (previewUrl) await refreshPreview(page);
            })));
            card.append(tools);
            const grid = node('div', null, {className: 'text-grid'});
            for (const [key, title] of [['source', t('Original', '原文')], ['translated', t('Translation', '译文')]]) {
                const field = node('textarea', null, {value: row[key], rows: 2, maxLength: 1500, readOnly: !!previewUrl});
                field.oninput = () => {
                    row[key] = field.value;
                    row.automatic = false;
                    if (key === 'translated') {
                        row.translatedFor = $('language').value;
                        row.profileVersion = profiles.version();
                        drawBoxes();
                    }
                    state();
                };
                grid.append(label(title, field));
            }
            card.append(grid);
            const coordinates = node('div', null, {className: 'tools'});
            [t('Left', '左'), t('Top', '上'), t('Right', '右'), t('Bottom', '下')].forEach((name, axis) => {
                const field = node('input', null, {type: 'number', min: 0, max: 100, step: .1,
                    value: (row.box[axis] * 100).toFixed(1)});
                field.onchange = () => {
                    const value = Number(field.value) / 100;
                    if (field.value !== '' && Number.isFinite(value)) {
                        const box = [...row.box];
                        box[axis] = axis < 2 ? Math.max(0, Math.min(row.box[axis + 2] - L.MIN, value)) :
                            Math.min(1, Math.max(row.box[axis - 2] + L.MIN, value));
                        setRegionBounds(row, box);
                    }
                    field.value = (row.box[axis] * 100).toFixed(1);
                    drawBoxes();
                };
                coordinates.append(label(name + ' %', field));
            });
            if (!previewUrl) card.append(coordinates);
            return card;
        }
        dialogueGroups(page).forEach((group, index) => {
            const heading = `${t('Region', '区域')} ${index + 1}`;
            if (group.length === 1) {
                $('regions').append(regionCard(group[0], heading));
                return;
            }
            const id = group.map(row => row.id).join('-');
            const card = node('details', null, {className: 'region bubble-group', open: !collapsed.has(id)});
            card.dataset.region = id;
            card.append(node('summary', `${heading} · ${t('Merged bubble', '合并气泡')} (${group.length})`));
            group.forEach((row, position) => card.append(regionCard(row,
                `${t('Drawing area', '绘制区域')} ${position + 1}`)));
            $('regions').append(card);
        });
    }
    function renderSlots() {
        const slots = pages.length < pageLimit ? [...pages, null] : pages;
        const rows = slots.map((page, index) => {
            const row = node('li', null, {className: 'page-slot'});
            const slot = $('asset-slot').content.firstElementChild.cloneNode(true);
            const name = page ? `${index + 1}. ${page.file.name}` : t('Choose or drop images', '选择或拖入图片');
            slot.querySelector('[data-slot-empty] span').textContent = name;
            window.AI2AppsAssetSlot.bind(slot, {
                selectFiles: files => work(() => addFiles(files, index)),
                choose: async input => {
                    if (!mobile) { input.click(); return null; }
                    const picked = await call(null, {accept: input.accept, multiple: input.multiple}, 'asset.pick');
                    if (!picked) return null;
                    const files = (Array.isArray(picked) ? picked : [picked])
                        .map(({body, name}) => new File([body], name, {type: body.type}));
                    await work(() => addFiles(files, index));
                    return null;
                },
                drop: event => dropFromGallery(event, index),
                error: error => { $('error').textContent = error.message; },
                clear: () => {
                    releasePage(page);
                    const active = current();
                    pages.splice(index, 1);
                    selected = active === page ? Math.min(index, Math.max(0, pages.length - 1)) : pages.indexOf(active);
                    clearPreview();
                    render();
                },
            }).update({preview: page?.preview, label: name, clearLabel: t('Remove page ', '删除第 ') + (index + 1)});
            row.append(slot);
            if (!page) return row;
            const actions = node('div', null, {className: 'page-actions'});
            const title = button(page.file.name, () => { selected = index; clearPreview(); render(); });
            title.setAttribute('aria-current', selected === index ? 'page' : 'false');
            actions.append(title);
            for (const [offset, symbol, name] of [[-1, '↑', t('Move page up', '前移此页')], [1, '↓', t('Move page down', '后移此页')]]) {
                const shift = button(symbol, () => {
                    const active = current();
                    [pages[index], pages[index + offset]] = [pages[index + offset], pages[index]];
                    selected = pages.indexOf(active);
                    render();
                });
                shift.setAttribute('aria-label', name + ' ' + (index + 1));
                shift.disabled = !pages[index + offset];
                actions.append(shift);
            }
            row.append(actions);
            return row;
        });
        $('pages').replaceChildren(...rows);
    }
    function render() {
        const page = current();
        renderSlots();
        $('page').replaceChildren(...pages.map((page, i) => node('option', `${i + 1}. ${page.file.name}`, {value: i})));
        $('page').value = selected;
        state();
        if (!page) return;
        $('page-image').src = previewUrl || page.cropUrl || page.preview;
        $('preview').textContent = previewUrl ? t('Continue editing', '继续编辑') : t('Preview translation', '预览译文');
        $('crop').disabled = !page.proposal;
        $('crop').textContent = page.crop ? t('Use full screenshot', '恢复整张截图') : t('Use detected crop', '使用自动裁切');
        $('crop-status').hidden = !page.analyzed;
        $('crop-status').textContent = page.crop ? t('Comic crop applied to this page.', '本页已应用漫画裁切。') :
            page.proposal ? t('This page uses the full image.', '本页保留整张图片。') :
                t('No reliable crop found. This page uses the full image.', '未找到可靠的裁切边界，本页保留整张图片。');
        if (dialoguePage !== page.id) {
            $('dialogue').open = false;
            dialoguePage = page.id;
        }
        renderRegions(page);
    }
    function renderRegions(page) {
        $('add-box').disabled = page.regions.length >= 32;
        $('dialogue').hidden = !page.regions.length;
        $('dialogue-label').textContent = `${t('Dialogue', '气泡对白')} · ${dialogueGroups(page).length}`;
        drawBoxes();
        regionControls(page);
    }
    function issueMessages(page, issues) {
        const reasons = {
            untranslated: t('No translation is available for this region.',
                '此区域没有译文，输出保留原文。'),
            bounds: t('The box is too small, outside the page, or overlaps another translation.',
                '选区太小、超出页面或与其他译文重叠。'),
            text: t('Translation does not fit. Try a larger box, 90° rotation, or shorter wording.',
                '译文放不下，可扩大选区、尝试旋转 90° 或缩短译文。'),
            background: t('The selection includes artwork or a textured background.',
                '选区包含画面或纹理，建议缩小到气泡文字。'),
        };
        const groups = dialogueGroups(page);
        return [...new Set(issues.map(({index, reason}) => {
            const number = groups.findIndex(group => group.includes(page.regions[index])) + 1;
            return `${page.file.name} · ${t('Region', '区域')} ${number} · ${reasons[reason]}`;
        }))];
    }
    async function composition(page) {
        const clip = page.crop || L.FULL;
        const language = $('language').value;
        return L.render({...page, regions: page.regions.map(row => ({
            ...row, enabled: row.enabled && allowed(row.box, clip),
            translated: displayTranslation(row),
        }))}, language);
    }
    async function refreshPreview(page) {
        clearPreview();
        const {original, output, issues} = await composition(page);
        try {
            previewUrl = URL.createObjectURL(await L.png(output));
        } finally {
            original.width = output.width = 0;
        }
        previewSkipped = new Set(issues.map(issue => issue.index));
        status(issues.length ? t('Preview ready. Skipped regions retain their original pixels.',
            '预览已就绪，跳过的区域保留原图。') : t('Preview ready.', '预览已就绪。'));
        $('error').textContent = issueMessages(page, issues).join('\n');
    }
    async function exportPages(format) {
        const images = [], readerPages = [], warnings = [];
        let outputBytes = 0;
        for (const [index, page] of pages.entries()) {
            if (stopped) return;
            status(`${t('Preparing page', '正在排版第')} ${index + 1}/${pages.length}`);
            const {original, output, boxes, issues} = await composition(page);
            warnings.push(...issueMessages(page, issues));
            const rendered = await L.png(output);
            if (format === 'png') { images.push(rendered); outputBytes += rendered.size; }
            else {
                const base = await L.png(original);
                outputBytes += Math.ceil((base.size + rendered.size) * 4 / 3);
                if (outputBytes > 63 * 1024 ** 2) throw Error(t('Reader exceeds 64 MiB', '阅读器超过 64 MiB'));
                readerPages.push({width: output.width, height: output.height, boxes,
                    original: await L.url(base), output: await L.url(rendered)});
            }
            original.width = output.width = 0;
            if (outputBytes > 64 * 1024 ** 2) throw Error(t('Export exceeds 64 MiB', '输出超过 64 MiB'));
        }
        if (stopped) return;
        const files = format === 'png' ? images :
            [new Blob([window.ComicReader.readerHtml(readerPages, zh ? 'zh' : 'en')], {type: 'text/html'})];
        await call('export', {format, files});
        status(warnings.length ? t('Saved to Output. Skipped regions retain their original pixels.',
            '已保存到输出栏，跳过的区域保留原图。') : t('Saved to Output.', '已保存到输出栏。'));
        $('error').textContent = warnings.join('\n');
    }

    function dropFromGallery(event, index) {
        let ids = [];
        try { ids = JSON.parse(event.dataTransfer.getData('application/x-ai2apps-gallery-assets') || '[]'); } catch (_) {}
        const id = event.dataTransfer.getData('application/x-ai2apps-gallery-asset');
        if (!Array.isArray(ids) || !ids.length) ids = id ? [id] : [];
        if (!ids.length) return;
        return work(async () => {
            const limit = pageLimit - pages.length + Number(index < pages.length);
            const files = [], errors = [];
            for (const assetId of ids.slice(0, limit)) {
                if (stopped) break;
                try {
                    const {body, name} = await call('reference', {assetId});
                    files.push(new File([body], name, {type: body.type}));
                } catch (error) { errors.push(error.message); }
            }
            if (ids.length > limit) errors.push(pageLimitMessage());
            await addFiles(files, index, errors);
        });
    }
    $('models').onclick = () => work(refreshModels);
    $('install-ocr').onclick = () => work(async () => {
        await call(null, {capability: 'comic.translation'}, 'setup');
        await refreshModels();
    });
    $('model').onchange = state;
    const profiles = window.ComicProfiles.bind({call, t, work, node, button, label});
    $('language').onchange = () => { clearPreview(); profiles.render(); render(); };
    $('stop').onclick = () => { stopped = true; state(); status(t('Finishing the current request…', '正在完成当前请求…')); };
    for (const id of ['detect', 'recognize', 'translate']) $(id).onclick = () => work(() => batch(id));
    for (const id of ['png', 'html']) $(id).onclick = () => work(() => exportPages(id));
    $('page').onchange = () => { selected = Number($('page').value); clearPreview(); render(); };
    $('crop').onclick = () => work(() => setCrop(current(), current().crop ? null : current().proposal));
    $('preview').onclick = () => work(async () => {
        if (previewUrl) { clearPreview(); return; }
        await refreshPreview(current());
    });
    $('add-box').onclick = () => {
        const page = current();
        const [x, y, r, b] = page.crop || L.FULL;
        const w = r - x, h = b - y;
        clearPreview();
        page.regions.push(region([x + w * .3, y + h * .3, x + w * .7, y + h * .5]));
        render();
        $('dialogue').open = true;
    };
    function point(event) {
        const rect = $('stage').getBoundingClientRect();
        const [x, y, r, b] = current().crop || L.FULL;
        const normalized = (value, start, size) => Math.max(0, Math.min(1, (value - start) / size));
        return [x + normalized(event.clientX, rect.left, rect.width) * (r - x),
            y + normalized(event.clientY, rect.top, rect.height) * (b - y)];
    }
    const stage = $('stage');
    stage.onpointerdown = event => {
        const page = current();
        if (!page || busy || drag || event.button !== 0) return;
        const target = event.target.closest('[data-region-id]');
        const row = target && page.regions.find(item => item.id === Number(target.dataset.regionId));
        if (!row && (previewUrl || event.pointerType === 'touch' || page.regions.length >= 32)) return;
        const resize = !!event.target.closest('.box-resize');
        drag = {id: event.pointerId, page, row, resize, start: point(event),
            clientX: event.clientX, clientY: event.clientY, box: row && L.intersect(row.box, page.crop || L.FULL)};
        if (row) {
            event.preventDefault();
            $('bubble-tooltip').hidden = true;
        }
        stage.setPointerCapture(event.pointerId);
    };
    stage.onpointermove = event => {
        if (drag?.id !== event.pointerId || drag.page !== current()) return;
        if (!drawingBox && Math.hypot(event.clientX - drag.clientX, event.clientY - drag.clientY) < 3) return;
        const [x, y] = point(event);
        const [sx, sy] = drag.start;
        if (drag.row) {
            const [left, top, right, bottom] = drag.box;
            const clip = drag.page.crop || L.FULL;
            if (drag.resize) {
                drawingBox = [left, top,
                    Math.min(clip[2], Math.max(left + L.MIN, right + x - sx)),
                    Math.min(clip[3], Math.max(top + L.MIN, bottom + y - sy))];
            } else {
                const dx = Math.max(clip[0] - left, Math.min(clip[2] - right, x - sx));
                const dy = Math.max(clip[1] - top, Math.min(clip[3] - bottom, y - sy));
                drawingBox = [left + dx, top + dy, right + dx, bottom + dy];
            }
        } else drawingBox = [Math.min(x, sx), Math.min(y, sy), Math.max(x, sx), Math.max(y, sy)];
        drawBoxes();
    };
    stage.onpointerup = event => {
        if (drag?.id !== event.pointerId) return;
        const {page, row} = drag;
        const box = drawingBox;
        drag = drawingBox = null;
        if (page !== current() || busy || !box || box[2] - box[0] < L.MIN || box[3] - box[1] < L.MIN) {
            drawBoxes();
            return;
        }
        if (row) {
            setRegionBounds(row, box);
            if (previewUrl) { void work(() => refreshPreview(page)); return; }
        } else page.regions.push(region(box));
        renderRegions(page);
    };
    stage.onpointercancel = stage.onlostpointercapture = event => {
        if (drag?.id !== event.pointerId) return;
        drag = drawingBox = null;
        drawBoxes();
    };

    let portableRevision = 0, portableSignature = '';
    const portableInstance = globalThis.crypto?.randomUUID?.() || String(Math.random());
    const portableFields = {language: 'language', direction: 'direction', model_id: 'model',
        auto_crop: 'auto-crop', page_context: 'context'};
    function portableState() {
        const values = {profile: profiles.name()};
        for (const [key, id] of Object.entries(portableFields)) {
            const control = $(id);
            values[key] = control.type === 'checkbox' ? control.checked : control.value;
        }
        const signature = JSON.stringify(values);
        if (signature !== portableSignature) {
            portableRevision++;
            portableSignature = signature;
        }
        return {instance: portableInstance, revision: portableRevision, values, busy: busy || !port, dirty: pages.length > 0};
    }
    function restorePortableState(values) {
        for (const key of ['language', 'direction', 'model_id']) {
            if ((key !== 'model_id' || values?.[key] !== '') &&
                    !Array.from($(portableFields[key]).options).some(option => option.value === values?.[key] && option.value)) {
                throw Error(t('A saved setting or model is unavailable.', '保存的设置或模型不可用。'));
            }
        }
        if (typeof values.profile !== 'string' || typeof values.auto_crop !== 'boolean' || typeof values.page_context !== 'boolean') {
            throw Error(t('Invalid shortcut settings.', '快捷设置无效。'));
        }
        const profile = values.profile ? profiles.resolve(values.profile, values.language) : '';
        if (profile === null) throw Error(t('The saved translation profile is unavailable.', '保存的译名 Profile 不可用。'));
        for (const [key, id] of Object.entries(portableFields)) {
            const control = $(id);
            if (control.type === 'checkbox') control.checked = values[key];
            else control.value = values[key];
        }
        clearPreview();
        profiles.select(profile);
        render();
    }
    window.addEventListener('message', event => {
        const message = event.data, reply = event.ports[0];
        if (event.source !== parent || event.origin !== location.origin || !reply ||
                message?.type !== 'ai2apps:comic-translation-state/v1') return;
        try {
            const current = portableState();
            if (message.action === 'apply') {
                if (current.busy || message.instance !== portableInstance || message.revision !== current.revision)
                    throw Error(t('Settings changed or the editor is busy.', '设置已变化或编辑器正在处理任务。'));
                restorePortableState(message.values);
            } else if (message.action !== 'capture') throw Error('Unknown settings action');
            reply.postMessage({state: portableState()});
        } catch (error) { reply.postMessage({error: error.message}); }
        finally { reply.close(); }
    });

    window.addEventListener('message', event => {
        if (event.source !== parent || event.data?.type !== 'ai2apps:studio-connected' ||
            event.data.version !== 1 || !event.ports[0] || port) return;
        port = event.ports[0];
        zh = (event.data.locale || locale).startsWith('zh');
        mobile = event.data.mobile === true;
        localize();
        port.onmessage = event => {
            const data = event.data;
            if (data.type === 'ai2apps:studio-locale') {
                zh = (data.locale || 'en').startsWith('zh'); localize(); profiles.render(); render(); return;
            }
            const item = pending.get(data.id);
            if (!item) return;
            pending.delete(data.id);
            if (data.error) item.reject(Error(data.error)); else item.resolve(data.value);
        };
        port.start();
        work(async () => {
            await refreshModels();
            await profiles.load();
        });
    });
    localize();
    profiles.render();
    render();
    // Let the host retire the previous iframe channel before opening this one.
    window.addEventListener('load', () => setTimeout(() =>
        parent.postMessage({type: 'ai2apps:studio-connect', version: 1}, '*'), 0));
    new ResizeObserver(() => parent.postMessage({type: 'ai2apps:mini-app-resize', version: 1,
        height: Math.ceil(document.querySelector('main').getBoundingClientRect().height)}, '*')).observe(document.querySelector('main'));
    window.addEventListener('pagehide', () => {
        clearPreview();
        for (const page of pages) {
            URL.revokeObjectURL(page.preview);
            if (page.cropUrl) URL.revokeObjectURL(page.cropUrl);
        }
        port?.close();
    });
})();
