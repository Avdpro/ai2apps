/* Shared single-field dialog for system Apps. */
(() => {
    'use strict';
    let nextId = 0;

    function open({title, label, value = '', maxLength, submitLabel, cancelLabel, onSubmit}) {
        const dialog = document.createElement('dialog');
        const form = document.createElement('form');
        const heading = document.createElement('h2');
        const field = document.createElement('label');
        const input = document.createElement('input');
        const error = document.createElement('p');
        const actions = document.createElement('div');
        const cancel = document.createElement('button');
        const submit = document.createElement('button');

        dialog.className = 'ai2apps-dialog ai2apps-text-dialog';
        heading.id = 'ai2apps-text-dialog-title-' + (++nextId);
        heading.textContent = title;
        dialog.setAttribute('aria-labelledby', heading.id);
        input.type = 'text';
        input.value = value;
        input.required = true;
        if (maxLength != null) input.maxLength = maxLength;
        field.append(document.createTextNode(label), input);
        error.className = 'ai2apps-text-dialog-error';
        error.setAttribute('role', 'alert');
        error.hidden = true;
        actions.className = 'ai2apps-dialog-actions';
        cancel.type = 'button';
        cancel.textContent = cancelLabel;
        submit.type = 'submit';
        submit.textContent = submitLabel;
        submit.className = 'primary';
        actions.append(cancel, submit);
        form.append(heading, field, error, actions);
        dialog.append(form);

        let saving = false;
        const sync = () => {
            input.disabled = cancel.disabled = saving;
            submit.disabled = saving || !input.value.trim();
        };
        input.addEventListener('input', () => { error.hidden = true; sync(); });
        cancel.addEventListener('click', () => dialog.close());
        dialog.addEventListener('cancel', event => {
            if (saving) event.preventDefault();
        });
        dialog.addEventListener('close', () => dialog.remove(), {once: true});
        form.addEventListener('submit', async event => {
            event.preventDefault();
            const text = input.value.trim();
            if (saving || !text) return;
            saving = true;
            error.hidden = true;
            sync();
            try {
                await onSubmit(text);
                dialog.close();
            } catch (failure) {
                error.textContent = failure?.message || String(failure);
                error.hidden = false;
                saving = false;
                sync();
                input.focus();
            }
        });

        sync();
        document.body.append(dialog);
        dialog.showModal();
        input.focus();
        if (value) input.select();
    }

    window.AI2AppsTextInputDialog = {open};
})();
