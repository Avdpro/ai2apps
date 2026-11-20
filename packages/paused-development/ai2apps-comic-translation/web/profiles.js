(() => {
    'use strict';
    const schema = 'ai2apps.mini-app-draft/v1';
    const miniApp = 'ai2apps.imagine.comic-translation';
    const limit = 500;
    const kinds = ['person', 'place', 'item', 'other'];
    const key = text => text.normalize('NFC').toLowerCase();
    const $ = id => document.getElementById(id);

    function addTerms(destination, terms) {
        const seen = new Set(destination.map(term => key(term.source)));
        for (const term of terms) {
            if (destination.length >= limit) break;
            if (seen.has(key(term.source))) continue;
            destination.push(term);
            seen.add(key(term.source));
        }
    }

    function bind({call, t, work, node, button, label}) {
        let profiles = [];
        const selected = new Map(), temporary = new Map();
        const language = () => $('language').value;
        const active = () => profiles.find(profile => profile.id === selected.get(language()));
        const activeTerms = () => active()?.terms || temporary.get(language()) || [];
        const feedback = message => { $('profile-status').textContent = message; };
        const draftCall = (operation, fields = {}) => call(null, fields, operation);

        async function read() {
            const raw = JSON.parse(await draftCall('draft.get') || 'null');
            if (!raw?.profiles) return [];
            if (!Array.isArray(raw.profiles)) throw Error(t('Could not read profiles.', '无法读取 Profile。'));
            return raw.profiles;
        }
        async function write(updated) {
            await draftCall('draft.set', {value: JSON.stringify({schema, miniApp, profiles: updated})});
            profiles = updated;
        }
        function addRow(term = {}) {
            const row = node('div', null, {className: 'profile-term'});
            const source = node('input', null, {type: 'text', value: term.source || '', maxLength: 100});
            const translation = node('input', null, {type: 'text', value: term.translation || '', maxLength: 150});
            const kind = node('select');
            const names = [t('Person', '人名'), t('Place', '地名'), t('Item', '物品名'), t('Other', '其他')];
            kind.append(...kinds.map((value, index) => node('option', names[index], {value})));
            kind.value = term.kind || 'person';
            const remove = button('×', () => {
                row.remove();
                $('profile-add').disabled = false;
            });
            remove.setAttribute('aria-label', t('Remove term', '删除译名'));
            row.append(label(t('Source name', '原名'), source), label(t('Preferred translation', '指定译名'), translation),
                label(t('Category', '类别'), kind), remove);
            $('profile-terms').append(row);
            $('profile-add').disabled = $('profile-terms').childElementCount >= limit;
            return source;
        }
        function render() {
            const profile = active();
            const terms = activeTerms();
            $('profile-summary').textContent = `${t('Translation profile', '译名 Profile')} · ${profile?.name ||
                t('Temporary glossary', '临时词表')} (${terms.length})`;
            $('profile-select').replaceChildren(
                node('option', t('Temporary glossary', '临时词表'), {value: ''}),
                ...profiles.filter(item => item.language === language())
                    .map(item => node('option', item.name, {value: item.id})),
            );
            $('profile-select').value = profile?.id || '';
            $('profile-name').value = profile?.name || '';
            $('profile-terms').replaceChildren();
            $('profile-add').disabled = false;
            terms.forEach(addRow);
        }
        function collectRows() {
            const terms = [], seen = new Set();
            for (const row of $('profile-terms').children) {
                const [sourceInput, translationInput, kind] = row.querySelectorAll('input, select');
                const source = sourceInput.value.trim(), translation = translationInput.value.trim();
                if (!source && !translation) continue;
                if (!source || !translation) throw Error(t('Each term needs both names.', '每项都需要原名和指定译名。'));
                if (seen.has(key(source))) throw Error(t('Duplicate source name: ', '原名重复：') + source);
                seen.add(key(source));
                terms.push({source, translation, kind: kind.value});
            }
            return terms;
        }
        $('profile-select').onchange = () => {
            selected.set(language(), $('profile-select').value);
            feedback('');
            render();
        };
        $('profile-add').onclick = () => addRow().focus();
        $('profile-save').onclick = () => work(async () => {
            const name = $('profile-name').value.trim();
            if (!name) throw Error(t('Enter a profile name.', '请输入 Profile 名称。'));
            const terms = collectRows(), original = active();
            const latest = await read();
            if (latest.some(profile => profile.language === language() && key(profile.name) === key(name) &&
                    profile.id !== original?.id)) throw Error(t('That name is already in use.', '此名称已被使用。'));
            const current = latest.find(profile => profile.id === original?.id);
            if (original && JSON.stringify(current) !== JSON.stringify(original)) {
                throw Error(t('This profile changed in another window. Reopen the app before editing.',
                    '此 Profile 已在另一窗口更新，请重新打开应用后编辑。'));
            }
            const id = original?.id || globalThis.crypto?.randomUUID?.() || `profile-${Date.now()}-${latest.length}`;
            const saved = {id, name, language: language(), terms, revision: (original?.revision || 0) + 1};
            await write(current ? latest.map(profile => profile.id === id ? saved : profile) : [...latest, saved]);
            selected.set(language(), id);
            feedback(t('Profile saved.', 'Profile 已保存。'));
            render();
        });

        return {
            async load() {
                profiles = await read();
                render();
            },
            render,
            name() { return active()?.name || ''; },
            resolve(name, targetLanguage) {
                const matches = profiles.filter(profile => profile.language === targetLanguage && key(profile.name) === key(name));
                return matches.length === 1 ? matches[0].id : null;
            },
            select(id) {
                selected.set(language(), id);
                render();
            },
            glossary() { return activeTerms().map(term => ({...term})); },
            version() {
                const profile = active();
                return profile ? `${profile.id}:${profile.revision || 0}` : '';
            },
            async learn(discovered) {
                if (!discovered.length) return;
                const original = active();
                if (original) {
                    const latest = await read();
                    const current = latest.find(profile => profile.id === original.id);
                    if (!current) throw Error(t('The active profile is unavailable.', '当前 Profile 不可用。'));
                    addTerms(current.terms, discovered);
                    await write(latest);
                } else {
                    const terms = [...activeTerms()];
                    addTerms(terms, discovered);
                    temporary.set(language(), terms);
                }
                render();
            },
            addTerms,
        };
    }
    window.ComicProfiles = {bind};
})();
