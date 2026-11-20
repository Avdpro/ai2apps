(() => {
    'use strict';

    window.AI2AppsDocStudioTranslation = function mount({api, tr, languages, setBusy, onUpdate}) {
        const get = selector => document.querySelector(selector);
        const form = get('#ds-translation-form');
        const profileSelect = form.elements.profile_id;
        const edit = get('#ds-profile-edit'), remove = get('#ds-profile-delete');
        const dialog = get('#ds-profile-dialog'), profileForm = dialog.querySelector('form');
        let profiles = [], editing = '', receipt = null, loading = false, ready = false, saving = false;
        let layoutFormats = [];
        let pdfForm = false, defaultModel = '';
        let refreshSequence = 0;
        let snapshot = {outputs: [], tasks: []};

        function error(message, selector = '#ds-translation-error') {
            const node = get(selector);
            node.textContent = message?.message || '';
            node.hidden = !message;
        }
        const handle = callback => async event => {
            event.preventDefault();
            error(null);
            try { await callback(event); } catch (failure) { error(failure); }
        };
        const selected = () => profiles.find(profile => profile.id === profileSelect.value);
        profileSelect.onchange = () => { edit.disabled = remove.disabled = !selected(); };
        async function loadProfiles(id = profileSelect.value) {
            profiles = await api('/translation/profiles');
            profileSelect.replaceChildren(new Option(tr('无额外指导', 'No extra guidance'), ''),
                ...profiles.map(profile => new Option(profile.name, profile.id)));
            profileSelect.value = profiles.some(profile => profile.id === id) ? id : '';
            profileSelect.onchange();
        }

        const lang = form.elements.language;
        lang.replaceChildren(...[...languages.options].map(option => option.cloneNode(true)));
        lang.value = document.documentElement.lang.startsWith('zh') ? 'en' : 'zh';
        setBusy(form, true);
        function updateFormat() {
            const name = form.elements.file.files[0]?.name || '';
            const suffix = name.slice(name.lastIndexOf('.') + 1).toLowerCase();
            const supportsLayout = layoutFormats.includes(suffix);
            const format = form.elements.output_format;
            const formOption = format.querySelector('[value="form"]');
            formOption.hidden = formOption.disabled = !pdfForm || suffix !== 'pdf';
            if (formOption.disabled && format.value === 'form') format.value = 'layout';
            get('#ds-translation-format').hidden = !supportsLayout;
            get('#ds-translation-legacy-format').hidden = supportsLayout || !/\.(docx|pdf)$/i.test(name);
            const model = form.elements.model_id;
            for (const option of model.options) {
                const id = option.value || defaultModel;
                option.disabled = !id || (format.value === 'form' && id.startsWith('cloud/'));
            }
            if (model.selectedOptions[0]?.disabled || model.selectedIndex < 0) {
                model.selectedIndex = [...model.options].findIndex(option => !option.disabled);
            }
            ready = model.selectedIndex >= 0;
            setBusy(form, !ready || saving || loading);
        }
        form.elements.file.addEventListener('change', updateFormat);
        form.elements.output_format.addEventListener('change', updateFormat);

        async function refresh() {
            const sequence = ++refreshSequence;
            const result = await api('/translation');
            if (sequence !== refreshSequence) return;
            snapshot = result;
            onUpdate();
        }

        async function open() {
            if (loading) return;
            loading = true;
            error(null);
            try {
                const model = form.elements.model_id;
                const previous = model.value;
                const [catalog] = await Promise.all([api('/translation/models'), loadProfiles(), refresh()]);
                layoutFormats = catalog.layout_formats || [];
                pdfForm = catalog.pdf_form === true;
                defaultModel = catalog.default || '';
                const local = document.createElement('optgroup');
                local.label = tr('本地模型', 'Local models');
                const cloud = document.createElement('optgroup');
                cloud.label = tr('云端模型', 'Cloud models');
                for (const item of catalog.models) {
                    const group = item.id.startsWith('cloud/') ? cloud : local;
                    group.append(new Option(item.name, item.id));
                }
                const fallback = new Option(tr('默认工作模型', 'Default work model'), '');
                fallback.disabled = !catalog.default;
                model.replaceChildren(fallback, ...[local, cloud].filter(group => group.childElementCount));
                if ([...model.options].some(option => !option.disabled && option.value === previous)) model.value = previous;
                else model.selectedIndex = [...model.options].findIndex(option => !option.disabled);
                updateFormat();
                if (!ready) error(new Error(tr('没有可用的对话模型，请先配置模型。', 'Configure a chat model to translate.')));
            } catch (failure) {
                error(failure);
            } finally {
                loading = false;
                setBusy(form, !ready || saving);
            }
        }

        function showProfile(profile) {
            editing = profile?.id || '';
            profileForm.elements.name.value = profile?.name || '';
            profileForm.elements.guidance.value = profile?.guidance || '';
            error(null, '#ds-profile-error');
            dialog.showModal();
        }
        get('#ds-profile-create').onclick = () => showProfile();
        edit.onclick = () => { if (selected()) showProfile(selected()); };
        get('#ds-profile-cancel').onclick = () => dialog.close();
        profileForm.onsubmit = async event => {
            event.preventDefault();
            error(null, '#ds-profile-error');
            setBusy(profileForm, true);
            try {
                const fields = Object.fromEntries(new FormData(profileForm));
                const saved = await api('/translation/profiles' + (editing ? '/' + encodeURIComponent(editing) : ''),
                    fields, editing ? 'PUT' : 'POST');
                await loadProfiles(saved.id);
                dialog.close();
            } catch (failure) {
                error(failure, '#ds-profile-error');
            } finally { setBusy(profileForm, false); }
        };
        remove.onclick = handle(async () => {
            const profile = selected();
            if (!profile || !window.confirm(tr(`删除指导方案「${profile.name}」？`, `Delete the guidance profile “${profile.name}”?`))) return;
            await api('/translation/profiles/' + encodeURIComponent(profile.id), undefined, 'DELETE');
            await loadProfiles('');
        });

        form.onsubmit = handle(async () => {
            if (saving || !ready) return;
            const file = form.elements.file.files[0], text = form.elements.text.value;
            if (Boolean(file) === Boolean(text.trim())) {
                throw Error(tr('请选择一个文件或粘贴文本。', 'Upload one file or paste text.'));
            }
            if (file && file.size > 12 * 1024 * 1024) {
                throw Error(tr('文件超过 12 MiB。', 'The file exceeds 12 MiB.'));
            }
            const options = {language: lang.value, model_id: form.elements.model_id.value,
                profile_id: profileSelect.value || null};
            const format = form.elements.output_format.value;
            const signature = JSON.stringify([options, text, form.elements.markdown.checked, format]);
            if (receipt?.signature !== signature || receipt?.file !== file) {
                receipt = {signature, file, id: crypto.randomUUID()};
            }
            const data = new FormData();
            data.set('options', JSON.stringify({...options, request_id: receipt.id}));
            data.set('output_format', format);
            if (file) data.set('file', file);
            else {
                data.set('text', text);
                data.set('markdown', String(form.elements.markdown.checked));
            }
            saving = true;
            setBusy(form, true);
            try {
                await api('/translation', data);
                receipt = null;
                await refresh();
            } catch (failure) {
                if (failure.status && failure.status < 500) receipt = null;
                throw failure;
            } finally {
                saving = false;
                setBusy(form, !ready);
            }
        });
        const settings = () => ({
            language: lang.value, output_format: form.elements.output_format.value, markdown: form.elements.markdown.checked,
        });
        function validate(values) {
            if (saving || loading) throw Error(tr('请等待当前操作结束。', 'Wait for the current operation.'));
            for (const [key, value] of Object.entries(values)) {
                const field = form.elements[key];
                if (!field || (field.options && ![...field.options].some(option => option.value === (value ?? '') && !option.disabled))) {
                    throw Error(tr('翻译选项不可用。', 'A translation option is unavailable.'));
                }
            }
            if (values.output_format === 'form' && (values.model_id || form.elements.model_id.value || defaultModel).startsWith('cloud/')) {
                throw Error(tr('保留表单需要本地模型。', 'Keep form requires a local model.'));
            }
        }
        function apply(values) {
            validate(values);
            for (const [key, value] of Object.entries(values)) {
                if (key === 'markdown') form.elements.markdown.checked = value;
                else form.elements[key].value = value ?? '';
            }
            updateFormat();
            profileSelect.onchange();
        }
        function readUI() {
            return {...settings(), model_id: form.elements.model_id.value, profile_id: profileSelect.value || null,
                text: form.elements.text.value.slice(0, 12000),
                file_selected: Boolean(form.elements.file.files.length),
                profiles: profiles.map(({id, name}) => ({id, name})),
                tasks: snapshot.tasks.slice(0, 10).map(({id, status}) => ({id, status}))};
        }
        return {open, refresh, snapshot: () => snapshot, error, settings, validate, apply, readUI};
    };
})();
