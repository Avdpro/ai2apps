(() => {
    "use strict";
    const root = document.getElementById("mail-app");
    if (!root) return;
    const $ = id => document.getElementById("mail-" + id);
    const tr = (zh, en) => root.lang === "zh" ? zh : en;
    const mobile = root.hasAttribute("data-mobile-screen");
    const markerViews = {
        flagged: tr("旗标", "Flagged"),
        todo: tr("待办", "To do"),
        answered: tr("已回复", "Replied"),
        drafts: tr("草稿", "Drafts"),
    };
    const isMarkerView = id => Object.hasOwn(markerViews, id);
    const hasBuiltInFilters = id => id === "top5" || id === "answered";
    const form = $("form"), settings = $("settings"), dialog = $("dialog");
    let accounts = [], selected = "", reconnect = "", offset = 0, query = "", generation = 0, previewGeneration = 0;
    let busy = false;
    let folders = [], smartView = mobile ? "" : "top5", organizing = false, editingFolder = null;
    let lastAccount = "", lastSmartFolder = "top5", lastSmartScope = "", hasOrganized = false;
    const openedMessages = new Set();
    const rowItems = new WeakMap();
    const pendingMarkers = new Set();
    const recentPreviews = new Map();
    const recentPreviewLimit = 10;
    let unreadCounts = {}, unreadScope = null, unreadGeneration = 0;
    const messageKey = item => [item.account_id, item.uidvalidity, item.uid].join("/");
    const messagePath = item => `/accounts/${item.account_id}/messages/${item.uidvalidity}/${item.uid}`;
    const currentRow = () => $("list").querySelector("[aria-current]");
    if (mobile) {
        const mount = new URLSearchParams(location.hash.slice(1));
        const mountToken = mount.get("ai2apps-mount"), instanceId = mount.get("ai2apps-instance");
        const hosted = window.parent !== window && mountToken && instanceId;
        let historyScreens = ["list"];
        let depth = 0;
        let backPending = false;
        const showScreen = screen => {
            root.dataset.mobileScreen = screen;
            $("mobile-folders").setAttribute("aria-expanded", String(screen === "folders"));
            $("mobile-folders").hidden = screen === "reading";
            $("compose").hidden = screen === "reading";
        };
        const sendNavigation = (action, extra = {}) => window.parent.postMessage({
            type: "ai2apps.shell.navigation." + action, mountToken, instanceId, ...extra,
        }, location.origin);
        const navigate = screen => {
            if (root.dataset.mobileScreen === screen) return;
            if (depth > 0) return;
            historyScreens = ["list", screen];
            depth = 1;
            showScreen(screen);
            if (hosted) sendNavigation("push", {depth});
        };
        const back = () => {
            if (!depth || backPending) return;
            if (hosted) {
                backPending = true;
                sendNavigation("back");
            } else {
                depth = 0;
                showScreen("list");
            }
        };
        window.addEventListener("message", event => {
            const state = event.data;
            if (!hosted || event.source !== window.parent || event.origin !== location.origin ||
                state?.type !== "ai2apps.shell.navigation.history" || state.mountToken !== mountToken ||
                state.instanceId !== instanceId || !Number.isInteger(state.depth) || !historyScreens[state.depth]) return;
            depth = state.depth;
            backPending = false;
            showScreen(historyScreens[depth]);
        });
        $("mobile-folders").onclick = () => depth ? back() : navigate("folders");
        $("mobile-back").onclick = back;
        root.addEventListener("mail-open-reading", () => navigate("reading"));
        root.addEventListener("mail-selected-folder", () => {
            if (root.dataset.mobileScreen === "folders") back();
        });
    }
    let todoState;
    let reconnectAccount = null, gmailPassword = false, oauthPath = "", connecting = false;
    const codeText = {
        authentication_failed: ["认证失败，请检查用户名或应用专用密码。", "Authentication failed. Check the username or app password."],
        reconnect_required: ["请重新连接此账户。", "Reconnect this account."],
        connection_failed: ["无法建立邮件连接，请检查地址、网络或 TLS。", "Could not connect. Check the address, network, or TLS."],
        inbox_changed: ["收件箱已变化，请重新同步。", "The inbox changed. Sync again."],
        mail_busy: ["邮件服务正忙，请稍后再试。", "Mail is busy. Try again shortly."],
        account_changed: ["账户状态已变化，请重试。", "The account changed. Try again."],
        invalid_host: ["请输入服务器主机名。", "Enter a server hostname."],
        gmail_app_password_required: ["Gmail 需要 16 位应用专用密码。", "Gmail requires a 16-character app password."],
        gmail_oauth_unconfigured: ["当前安装尚未配置 Google 登录。", "Google sign-in has not been configured for this installation."],
        gmail_oauth_browser_failed: ["无法打开 Google 登录页面。", "Could not open Google sign-in."],
        gmail_oauth_denied: ["Google 授权已取消或被拒绝。", "Google authorization was cancelled or denied."],
        gmail_oauth_expired: ["Google 授权已超时，请重试。", "Google authorization expired. Try again."],
        gmail_oauth_unavailable: ["无法完成 Google 授权，请重试。", "Could not complete Google authorization. Try again."],
        gmail_oauth_scope_missing: ["Google 未授予 IMAP 所需的 Gmail 权限。", "Google did not grant the Gmail permission required for IMAP."],
        gmail_oauth_account_mismatch: ["请在 Google 页面选择要重新连接的同一邮箱。", "Choose the same mailbox in Google to reconnect."],
        gmail_oauth_account_exists: ["此 Gmail 已添加，请在账户列表选择重新连接。", "This Gmail account is already added. Choose Reconnect in the account list."],
        gmail_oauth_required: ["请使用 Google 登录重新连接。", "Use Google sign-in to reconnect."],
        desktop_mail_only: ["请在桌面使用 Mail。", "Open Mail on Desktop."],
        mail_privacy_model_required: ["请在模型设置中为隐私方案配置标准任务模型。", "Set a standard task model for the Privacy profile in Models."],
        mail_analysis_failed: ["邮件分析失败，请重试。", "Mail analysis failed. Try again."],
        mail_assist_failed: ["AI 没有返回可用内容，请重试。", "AI did not return a usable result. Try again."],
        mail_review_unavailable: ["这个草稿审核已失效，请从 Agent 重新打开。", "This draft review is unavailable. Reopen it from the Agent."],
        mail_invalid_assist: ["请选择回复方向或输入写信要求。", "Choose a reply direction or enter writing instructions."],
        smart_folders_changed: ["智能目录已变化，请重试。", "Smart folders changed. Try again."],
        duplicate_smart_folder: ["已有同名目录。", "A folder with this name already exists."],
        smart_folder_limit: ["最多可创建 24 个智能目录。", "You can create up to 24 smart folders."],
        invalid_smart_folder: ["请填写名称和分类规则。", "Enter a name and a classification rule."],
        invalid_smart_folder_sender: ["请填写有效的发件地址或域名，每行一条。", "Enter a valid sender address or domain on each line."],
        smart_folder_sender_excluded: ["此发件人已被该目录的规则排除。", "This sender is excluded by the folder rules."],
        smart_folder_sender_unavailable: ["无法识别这封邮件的唯一发件地址。", "This message does not have a single identifiable sender address."],
        smart_folder_sender_changed: ["发件人信息已变化，请重新选择要屏蔽的地址或域名。", "The sender changed. Choose the address or domain to block again."],
        smart_folder_sender_limit: ["此目录最多可保存 30 条屏蔽规则。", "This folder can have up to 30 sender blocks."],
        mail_pin_limit: ["Top5 已置顶五封邮件，请先取消一封。", "Top5 already has five pinned messages. Unpin one first."],
        mail_todo_unavailable: ["待办暂不可用，请稍后重试。", "Todo is unavailable. Try again shortly."],
        mail_invalid_recipient: ["请填写有效的收件邮箱。", "Enter a valid recipient email address."],
        mail_item_not_found: ["找不到这封邮件或邮箱账户。", "This message or mailbox could not be found."],
        mail_invalid_draft: ["请检查收件人、主题和正文。", "Check the recipients, subject, and message body."],
        mail_draft_too_large: ["邮件正文过长。", "The message is too long."],
        mail_attachments_too_large: ["最多 10 个附件，合计不超过 10 MB。", "Use up to 10 attachments, 10 MB total."],
        mail_invalid_attachment: ["无法读取附件，请检查文件名或重新选择。", "Could not read the attachment. Check the filename or select it again."],
        mail_draft_changed: ["草稿已变化或不可编辑，请重新打开。", "The draft changed or is locked. Open it again."],
        mail_secret_unavailable: ["暂时无法访问此邮箱的登录凭据。", "This account’s sign-in credentials are temporarily unavailable."],
        mail_smtp_unconfigured: ["这个账户尚未配置发信服务器。", "This account has no outgoing mail server configured."],
        mail_smtp_auth_failed: ["发信服务器拒绝登录，请检查账户设置。", "The outgoing server rejected the sign-in. Check the account settings."],
        mail_reply_target_changed: ["回复地址已变化，请重新打开回复。", "The reply address changed. Open the reply again."],
        mail_reply_unavailable: ["无法取得原邮件的回复地址。", "Could not read a reply address from the original message."],
        mail_send_connection: ["无法连接发信服务器。", "Could not connect to the outgoing mail server."],
        mail_send_rejected: ["发信服务器拒绝了这封邮件。", "The outgoing server rejected this message."],
        mail_recipient_rejected: ["发信服务器拒绝了至少一个收件地址，邮件未发送。", "The outgoing server rejected a recipient. The message was not sent."],
        mail_send_uncertain: ["发送结果未知。请先确认邮件是否已发出，再决定是否重发。", "Sending could not be confirmed. Check whether the message was sent before trying again."],
    };
    function say(text, state = "error") {
        $("footer").dataset.state = state;
        $("status").textContent = text;
    }
    function updateWorkButtons() {
        $("sync").disabled = busy || organizing || !accounts.length;
    }
    const toolbarTip = $("toolbar-tip");
    let toolbarTipTimer;
    function hideToolbarTip() {
        clearTimeout(toolbarTipTimer);
        toolbarTip.hidden = true;
        toolbarTip.classList.remove("is-visible");
    }
    for (const control of [$("smart-edit"), $("sync")]) {
        function showToolbarTip() {
            hideToolbarTip();
            toolbarTipTimer = setTimeout(() => {
                if (control.hidden || control.disabled) return;
                const bounds = control.getBoundingClientRect();
                toolbarTip.textContent = control.getAttribute("aria-label");
                toolbarTip.hidden = false;
                const width = toolbarTip.offsetWidth, height = toolbarTip.offsetHeight;
                toolbarTip.style.left = Math.max(8, Math.min(
                    bounds.left + (bounds.width - width) / 2, window.innerWidth - width - 8,
                )) + "px";
                toolbarTip.style.top = Math.max(8, bounds.bottom + height + 15 > window.innerHeight
                    ? bounds.top - height - 7 : bounds.bottom + 7) + "px";
                requestAnimationFrame(() => {
                    if (!toolbarTip.hidden) toolbarTip.classList.add("is-visible");
                });
            }, 70);
        }
        control.addEventListener("pointerenter", showToolbarTip);
        control.addEventListener("pointerleave", hideToolbarTip);
        control.addEventListener("focus", showToolbarTip);
        control.addEventListener("blur", hideToolbarTip);
    }
    root.addEventListener("pointerdown", hideToolbarTip);
    root.addEventListener("keydown", event => {
        if (event.key === "Escape") hideToolbarTip();
    });
    window.addEventListener("scroll", hideToolbarTip, true);
    window.addEventListener("resize", hideToolbarTip);
    async function api(path, method = "GET", data, signal) {
        const response = await fetch("/v1/platform/mail" + path, {
            method, credentials: "same-origin", cache: "no-store", signal,
            ...(data ? {headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)} : {}),
        });
        if (response.status === 204) return;
        const result = await response.json();
        if (!response.ok) {
            const code = [result.error?.code, result.error?.message, result.detail]
                .find(value => Object.hasOwn(codeText, value));
            throw new Error(tr(...(codeText[code] || ["请求失败，请重试。", "The request failed. Try again."])),
                {cause: code});
        }
        return result;
    }
    function button(label, action) {
        const node = document.createElement("button");
        node.type = "button";
        node.textContent = label;
        node.onclick = () => Promise.resolve(action()).catch(error => say(error.message));
        return node;
    }
    function renderAccounts() {
        $("all").setAttribute("aria-current", String(!selected && !smartView));
        updateWorkButtons();
        const scope = $("smart-scope");
        scope.hidden = accounts.length < 2;
        scope.replaceChildren(new Option(tr("所有账号", "All accounts"), ""),
            ...accounts.map(account => new Option(account.display_name, account.id)));
        scope.value = lastSmartScope;
        $("accounts").replaceChildren(...accounts.map(account => {
            const item = document.createElement("li");
            const select = button(account.display_name, () => selectAccount(account.id));
            select.setAttribute("aria-current", String(selected === account.id && !smartView));
            const info = document.createElement("small");
            const state = account.status === "connected" ? tr("已连接", "Connected") : tr("需重新连接", "Reconnect needed");
            const smtp = {authenticated: tr("SMTP 已验证", "SMTP verified"), not_configured: tr("未配置 SMTP", "SMTP not configured")};
            info.textContent = account.address + " · " + state + " · " + (smtp[account.smtp_status] || tr("SMTP 不可用", "SMTP unavailable"));
            item.append(select, info);
            if (!mobile) {
                const actions = document.createElement("div");
                actions.append(
                    button(tr("重新连接", "Reconnect"), () => openForm(account)),
                    button(tr("断开", "Disconnect"), async () => {
                        if (!window.confirm(tr("断开账户并清除本地缓存？服务器邮件不会被删除。", "Disconnect and clear the local cache? Server mail will be kept."))) return;
                        await api("/accounts/" + account.id, "DELETE");
                        for (const key of recentPreviews.keys()) {
                            if (key.startsWith(account.id + "/")) recentPreviews.delete(key);
                        }
                        await refreshAccounts();
                        await selectAccount("");
                    }),
                );
                item.append(actions);
            }
            return item;
        }));
    }
    async function refreshAccounts() {
        accounts = await api("/accounts");
        if (!accounts.some(account => account.id === selected)) selected = "";
        if (!accounts.some(account => account.id === lastAccount)) lastAccount = "";
        if (!accounts.some(account => account.id === lastSmartScope)) lastSmartScope = "";
        renderAccounts();
    }
    async function load(reset = true) {
        const ticket = ++generation;
        const start = reset ? 0 : offset;
        if (reset && smartView) refreshUnreadCounts();
        $("more").disabled = true;
        try {
            if (smartView === "drafts") {
                const args = new URLSearchParams();
                if (selected) args.set("account_id", selected);
                const drafts = await api("/drafts?" + args);
                if (ticket !== generation) return;
                $("more").hidden = true;
                $("coverage").textContent = tr("草稿仅保存在此设备。", "Drafts are saved on this device.");
                $("list").replaceChildren(...drafts.map(draft => {
                    const li = document.createElement("li");
                    const row = button("", () => openSavedDraft(draft.id));
                    row.className = "mail-message";
                    const top = document.createElement("span");
                    top.className = "mail-message-top";
                    const subject = document.createElement("strong");
                    subject.textContent = draft.subject || tr("无主题", "No subject");
                    const date = document.createElement("time");
                    date.textContent = new Date(draft.updated_at).toLocaleDateString();
                    top.append(subject, date);
                    const detail = document.createElement("span");
                    detail.className = "mail-message-subject";
                    detail.textContent = [
                        draft.recipients.join(", ") || tr("未填写收件人", "No recipients"),
                        draft.attachment_count ? tr(`${draft.attachment_count} 个附件`, `${draft.attachment_count} attachments`) : "",
                        draft.status === "draft" ? "" : tr("发送状态待确认", "Send status unconfirmed"),
                    ].filter(Boolean).join(" · ");
                    row.append(top, detail);
                    li.append(row);
                    return li;
                }));
                if (!drafts.length) {
                    const empty = document.createElement("li");
                    empty.textContent = tr("暂无草稿。", "No drafts yet.");
                    $("list").append(empty);
                }
                return;
            }
            const args = new URLSearchParams({offset: start, q: query});
            if (selected) args.set("account_id", selected);
            const data = await api((smartView ? "/smart-folders/" + smartView + "/messages?" : "/messages?") + args);
            if (ticket !== generation) return;
            const active = reset ? currentRow() : null;
            const activeItem = active && data.items.find(item => messageKey(item) === active.dataset.messageKey);
            const keepActive = smartView === "top5" && active && !activeItem;
            if (active && !activeItem && isMarkerView(smartView)) clearPreview();
            const activeIndex = keepActive ? [...$("list").children].indexOf(active.parentElement) : 0;
            const activeHasFocus = active && document.activeElement === active;
            const items = keepActive ? data.items.slice(0, 4) : data.items;
            if (reset) {
                if (keepActive) $("list").replaceChildren(active.parentElement);
                else $("list").replaceChildren();
            }
            for (const [index, item] of items.entries()) {
                const li = document.createElement("li");
                if (smartView === "top5") li.classList.add("mail-top-item");
                const row = button("", () => preview(item, row));
                rowItems.set(row, item);
                row.className = "mail-message";
                row.dataset.messageKey = messageKey(item);
                const top = document.createElement("span");
                top.className = "mail-message-top";
                const sender = document.createElement("strong");
                sender.textContent = senderName(item.sender);
                const date = document.createElement("time");
                const received = new Date(item.received_at);
                date.textContent = received.toDateString() === new Date().toDateString()
                    ? received.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"})
                    : received.toLocaleDateString([], {month: "short", day: "numeric"});
                const subject = document.createElement("span");
                subject.className = "mail-message-subject";
                subject.textContent = item.subject || tr("无主题", "No subject");
                const metadata = document.createElement("span");
                metadata.className = "mail-message-meta";
                metadata.append(date);
                top.append(sender, metadata);
                row.append(top, subject);
                renderMarkerIcons(row, item);
                if (item.reason) {
                    const reason = document.createElement("small");
                    reason.className = "mail-classification-reason";
                    reason.textContent = item.reason;
                    row.append(reason);
                }
                if (!item.seen && !openedMessages.has(row.dataset.messageKey)) {
                    row.classList.add("mail-unread");
                    row.setAttribute("aria-label", tr("未读：", "Unread: ") + subject.textContent + " · " + sender.textContent);
                }
                if (!selected && accounts.length > 1) {
                    const label = document.createElement("small");
                    label.textContent = item.address;
                    row.append(label);
                }
                li.append(row);
                if (smartView === "top5") {
                    const pin = button("", () => updateMarker(item, "pin", !item.pinned));
                    const label = item.pinned ? tr("取消置顶", "Unpin") : tr("置顶到 Top5", "Pin to Top5");
                    pin.className = "mail-pin";
                    pin.title = label;
                    pin.setAttribute("aria-label", label);
                    pin.setAttribute("aria-pressed", String(Boolean(item.pinned)));
                    pin.append(markerIcon("pin"));
                    li.append(pin);
                }
                if (keepActive && index < activeIndex) active.parentElement.before(li);
                else $("list").append(li);
                if (active && row.dataset.messageKey === active.dataset.messageKey) {
                    row.setAttribute("aria-current", "true");
                    classificationActions(item);
                    if (activeHasFocus) row.focus({preventScroll: true});
                }
            }
            if (keepActive && activeHasFocus) active.focus({preventScroll: true});
            window.ai2appsProcessIcons?.();
            if (smartView === "top5") renderUnreadCounts();
            offset = start + data.items.length;
            $("more").hidden = !data.has_more;
            const scope = selected ? accounts.filter(a => a.id === selected) : accounts;
            const times = scope.filter(a => a.synced_at).map(a => new Date(a.synced_at).getTime());
            const oldest = times.length ? new Date(Math.min(...times)).toLocaleString() : tr("尚未同步", "Not synced yet");
            $("coverage").textContent = tr("本地收件箱快照：最近 30 天，每个账户最多 200 封。最早同步：" , "Local inbox snapshot: last 30 days, up to 200 per account. Oldest sync: ") + oldest +
                (scope.some(a => !a.synced_at) && times.length ? tr("；部分账户未同步。", "; some accounts are unsynced.") : "");
            if (smartView && !isMarkerView(smartView)) {
                $("coverage").textContent += tr(" · 已分析 ", " · Analyzed ") + data.analyzed + "/" + data.total;
                hasOrganized ||= data.analyzed > 0;
            }
            if (!offset && !keepActive) {
                const empty = document.createElement("li");
                empty.textContent = smartView && !isMarkerView(smartView) && data.total && !data.analyzed
                    ? tr("选择「刷新」同步并整理邮件。", "Choose Refresh to sync and organize mail.")
                    : tr("没有匹配的已同步邮件。", "No matching synced mail.");
                $("list").append(empty);
            }
        } finally {
            if (ticket === generation) $("more").disabled = false;
        }
    }
    async function selectAccount(id, folderId = "", {stayInNavigation = false} = {}) {
        selected = id;
        smartView = folderId;
        if (folderId) {
            lastSmartFolder = folderId;
            lastSmartScope = id;
        } else {
            lastAccount = id;
        }
        renderSidebarTabs();
        $("list").replaceChildren();
        $("more").hidden = true;
        clearPreview();
        $("inbox-title").textContent = folderId === "top5" ? "Top5" : markerViews[folderId] || folders.find(folder => folder.id === folderId)?.name ||
            accounts.find(a => a.id === id)?.display_name || tr("统一收件箱", "Unified inbox");
        $("search").hidden = Boolean(folderId);
        renderAccounts();
        renderFolders();
        if (mobile && !stayInNavigation) root.dispatchEvent(new Event("mail-selected-folder"));
        await load();
    }

    const folderForm = $("smart-form");
    const folderDialog = $("smart-dialog");
    const requestScope = account => ({account_id: account || null, language: root.lang});
    const sidebarTabs = [$("smart-tab"), $("accounts-tab")];
    function renderSidebarTabs() {
        const smart = Boolean(smartView);
        sidebarTabs.forEach((tab, index) => {
            const active = index === (smart ? 0 : 1);
            tab.setAttribute("aria-selected", String(active));
            tab.tabIndex = active ? 0 : -1;
        });
        $("smart-panel").hidden = !smart;
        $("accounts-panel").hidden = smart;
    }
    function selectSidebar(index) {
        if (index === (smartView ? 0 : 1)) return;
        const change = index === 0
            ? selectAccount(lastSmartScope, lastSmartFolder, {stayInNavigation: true})
            : selectAccount(lastAccount, "", {stayInNavigation: true});
        change.catch(error => say(error.message));
    }
    sidebarTabs.forEach((tab, index) => {
        tab.onclick = () => selectSidebar(index);
        tab.onkeydown = event => {
            const next = {ArrowLeft: 1 - index, ArrowRight: 1 - index, Home: 0, End: 1}[event.key];
            if (next === undefined) return;
            event.preventDefault();
            selectSidebar(next);
            sidebarTabs[next].focus();
        };
    });
    $("smart-scope").onchange = event => {
        selectAccount(event.target.value, smartView, {stayInNavigation: true}).catch(error => say(error.message));
    };
    function renderFolders() {
        hideToolbarTip();
        $("smart-edit").hidden = !hasBuiltInFilters(smartView) && !folders.some(folder => folder.id === smartView);
        $("sync").setAttribute("aria-label", smartView === "drafts" ? tr("刷新草稿", "Refresh drafts") : smartView && !isMarkerView(smartView)
            ? tr("刷新：同步并整理邮件", "Refresh: sync and organize mail")
            : tr("同步邮件", "Sync mail"));
        const builtins = Object.entries(markerViews).map(([id, name]) => ({id, name}));
        $("smart-folders").replaceChildren(...[{id: "top5", name: "Top5"}, ...builtins, ...folders].map(folder => {
            const item = document.createElement("li");
            const select = button(folder.name, () => selectAccount(selected, folder.id));
            select.setAttribute("aria-current", String(smartView === folder.id));
            select.dataset.folderId = folder.id;
            select.dataset.folderName = folder.name;
            const badge = document.createElement("span");
            badge.className = "mail-folder-unread";
            badge.setAttribute("aria-hidden", "true");
            select.append(badge);
            item.append(select);
            return item;
        }));
        window.ai2appsProcessIcons?.();
        renderUnreadCounts();
    }
    function renderUnreadCounts() {
        for (const button of $("smart-folders").querySelectorAll("[data-folder-id]")) {
            const folderId = button.dataset.folderId;
            let count = unreadScope === selected ? unreadCounts[folderId] || 0 : 0;
            if (folderId === "top5" && smartView === folderId && currentRow()?.matches(":not(.mail-unread)")) {
                count = Math.min(count, $("list").querySelectorAll(".mail-unread").length);
            }
            const badge = button.querySelector(".mail-folder-unread");
            badge.hidden = !count;
            badge.textContent = count || "";
            if (count) {
                button.setAttribute("aria-label", button.dataset.folderName + tr(`，${count} 封未读`, `, ${count} unread`));
            } else {
                button.removeAttribute("aria-label");
            }
        }
    }
    async function refreshUnreadCounts() {
        if (!smartView) return;
        const ticket = ++unreadGeneration;
        const account = selected;
        try {
            const query = account ? "?" + new URLSearchParams({account_id: account}) : "";
            const counts = await api("/smart-folders/unread-counts" + query);
            if (ticket !== unreadGeneration || account !== selected || !smartView) return;
            unreadCounts = counts;
            unreadScope = account;
            renderUnreadCounts();
        } catch {
            // The folder list and message view still work if counts are unavailable.
        }
    }
    async function refreshFolders() {
        folders = await api("/smart-folders?language=" + root.lang);
        if (!isMarkerView(lastSmartFolder) && !folders.some(folder => folder.id === lastSmartFolder)) lastSmartFolder = "top5";
        renderFolders();
    }
    async function refreshAnalysisModel() {
        const {model} = await api("/analysis/model");
        $("smart-model").textContent = model
            ? tr("分析模型 · ", "Analysis model · ") + model
            : tr("请配置隐私方案的标准任务模型。", "Set a standard task model for the Privacy profile.");
    }
    async function organize(targets, syncErrors = []) {
        if (organizing || !targets.length) return;
        organizing = true;
        updateWorkButtons();
        const failures = [...syncErrors];
        let analyzed = 0;
        try {
            const pending = [...targets];
            while (pending.length) {
                const account = pending.shift();
                try {
                    say(tr("正在整理邮件… 已分析 ", "Organizing mail… Analyzed ") + analyzed, "running");
                    const result = await api("/analysis", "POST", requestScope(account.id));
                    analyzed += result.analyzed;
                    hasOrganized ||= result.analyzed > 0;
                    if (result.remaining > 0) pending.push(account);
                    if (smartView) await load();
                } catch (error) {
                    failures.push(account.display_name + " · " + error.message);
                }
            }
            say(failures.join(" · ") || tr("整理完成。", "Organization complete."), failures.length ? "error" : "success");
        } finally {
            organizing = false;
            updateWorkButtons();
        }
    }
    function openFolder(folder = null, examples = []) {
        editingFolder = folder?.id ? folder : null;
        const filtersOnly = hasBuiltInFilters(folder?.id);
        $("smart-title").textContent = filtersOnly
            ? tr(folder.name + " · 屏蔽规则", folder.name + " · Sender blocks")
            : tr("智能目录", "Smart folder");
        for (const label of folderForm.querySelectorAll("[data-folder-rule]")) {
            label.hidden = filtersOnly;
            label.querySelector("input, textarea").disabled = filtersOnly;
        }
        $("smart-preview").hidden = filtersOnly;
        folderForm.elements.name.value = folder?.name || "";
        folderForm.elements.rule.value = folder?.rule || "";
        folderForm.elements.excluded_senders.value = (folder?.excluded_senders || []).join("\n");
        folderForm.elements.guidance.value = folder?.guidance || "";
        $("smart-delete").hidden = !editingFolder || filtersOnly;
        $("smart-error").textContent = "";
        showExamples(examples);
        folderDialog.showModal();
        folderForm.querySelector(".mail-smart-dialog-body").scrollTop = 0;
    }
    function showExamples(examples) {
        $("smart-examples").replaceChildren(...examples.map(example => {
            const row = document.createElement("li");
            row.textContent = example;
            return row;
        }));
    }
    function folderValues() {
        const fields = folderForm.elements;
        const excluded_senders = fields.excluded_senders.value.split("\n").map(value => value.trim()).filter(Boolean);
        if (excluded_senders.length > 30 || excluded_senders.some(value => value.length > 254)) {
            throw new Error(tr("最多填写 30 条排除规则，每行最多 254 个字符。", "Enter up to 30 exclusions, with at most 254 characters per line."));
        }
        return {name: fields.name.value.trim(), rule: fields.rule.value.trim(), excluded_senders,
            guidance: fields.guidance.value.trim()};
    }
    async function folderAction(action) {
        const buttons = [...folderForm.querySelectorAll("button")].filter(node => node.id !== "mail-smart-cancel");
        buttons.forEach(node => { node.disabled = true; });
        $("smart-error").textContent = "";
        try {
            await action();
        } catch (error) {
            $("smart-error").textContent = error.message;
        } finally {
            buttons.forEach(node => { node.disabled = false; });
        }
    }
    $("smart-add").onclick = () => openFolder();
    $("smart-cancel").onclick = () => folderDialog.close();
    $("smart-edit").onclick = async () => {
        hideToolbarTip();
        const folderId = smartView;
        if (hasBuiltInFilters(folderId)) {
            try {
                const filters = await api("/smart-folders/" + folderId + "/sender-filters");
                if (smartView === folderId && !folderDialog.open) {
                    openFolder({...filters, id: folderId, name: markerViews[folderId] || "Top5"});
                }
            } catch (error) { say(error.message); }
            return;
        }
        const folder = folders.find(folder => folder.id === folderId);
        if (folder) openFolder(folder);
    };
    $("smart-preview").onclick = () => {
        if (!folderForm.reportValidity()) return;
        folderAction(async () => {
            $("smart-error").textContent = tr("正在预览规则…", "Checking the rule…");
            showExamples([]);
            const result = await api("/analysis/preview", "POST", {...requestScope(selected), ...folderValues()});
            showExamples(result.items.map(item => item.subject + " · " + item.reason));
            $("smart-error").textContent = tr("样本命中 ", "Sample matches ") + result.items.length + "/" + result.analyzed;
            $("smart-error").scrollIntoView({block: "nearest"});
        });
    };
    folderForm.onsubmit = event => {
        event.preventDefault();
        folderAction(async () => {
            const values = folderValues();
            if (hasBuiltInFilters(editingFolder?.id)) {
                const {id, revision} = editingFolder;
                await api("/smart-folders/" + id + "/sender-filters", "PUT", {
                    excluded_senders: values.excluded_senders, revision,
                });
                folderDialog.close();
                if (smartView === id) {
                    clearPreview();
                    await load();
                }
                say(tr("已保存屏蔽规则。", "Sender blocks saved."), "success");
                return;
            }
            const result = editingFolder
                ? await api("/smart-folders/" + editingFolder.id, "PUT", {...values, revision: editingFolder.revision})
                : await api("/smart-folders", "POST", values);
            folderDialog.close();
            await refreshFolders();
            await selectAccount(lastSmartScope, result.id);
            say(tr("目录已保存。选择「刷新」可将规则应用到收件箱。", "Folder saved. Choose Refresh to apply the rule to the inbox."), "success");
        });
    };
    $("smart-delete").onclick = () => {
        if (!editingFolder || !window.confirm(tr("删除此智能目录？", "Delete this smart folder?"))) return;
        folderAction(async () => {
            await api("/smart-folders/" + editingFolder.id + "?revision=" + editingFolder.revision, "DELETE");
            folderDialog.close();
            await refreshFolders();
            await selectAccount(lastSmartScope, lastSmartFolder);
        });
    };
    $("smart-suggest").onclick = async () => {
        const suggestions = $("suggestions");
        const status = $("suggestions-status");
        const sheet = $("suggestions-dialog");
        suggestions.replaceChildren();
        status.textContent = tr("正在分析收件箱样本…", "Analyzing an inbox sample…");
        sheet.showModal();
        try {
            const proposals = await api("/analysis/suggestions", "POST", requestScope(selected));
            status.textContent = proposals.length ? "" : tr("当前样本没有目录建议。", "No folders suggested for this sample.");
            suggestions.replaceChildren(...proposals.map(proposal => {
                const row = document.createElement("li");
                const detail = document.createElement("p");
                detail.textContent = proposal.rule;
                row.append(button(proposal.name, () => {
                    sheet.close();
                    openFolder(proposal, proposal.examples);
                }), detail);
                return row;
            }));
        } catch (error) {
            status.textContent = error.message;
        }
    };
    function markerIcon(name) {
        const icon = document.createElement("i");
        icon.dataset.lucide = name;
        icon.setAttribute("aria-hidden", "true");
        return icon;
    }
    function renderMarkerIcons(row, item) {
        row.querySelector(".mail-row-markers")?.remove();
        const marks = document.createElement("span");
        marks.className = "mail-row-markers";
        for (const [enabled, icon, label] of [
            [item.flagged, "flag", markerViews.flagged],
            [item.todo, "list-todo", markerViews.todo],
            [item.answered, "reply", markerViews.answered],
        ]) {
            if (!enabled) continue;
            const mark = document.createElement("span");
            mark.title = label;
            mark.setAttribute("aria-label", label);
            mark.setAttribute("role", "img");
            mark.append(markerIcon(icon));
            marks.append(mark);
        }
        if (marks.childElementCount) row.querySelector(".mail-message-meta").append(marks);
    }
    async function updateMarker(item, kind, enabled) {
        const key = messageKey(item);
        const pendingKey = key + "/" + kind;
        if (pendingMarkers.has(pendingKey)) return;
        pendingMarkers.add(pendingKey);
        const [field, progress, added, removed] = {
            flag: ["flagged", tr("正在保存旗标…", "Saving flag…"),
                tr("已加旗标。", "Flag added."), tr("已取消旗标。", "Flag removed.")],
            pin: ["pinned", tr("正在保存置顶…", "Saving pin…"),
                tr("已置顶。", "Message pinned."), tr("已取消置顶。", "Message unpinned.")],
            todo: ["todo", tr("正在更新待办…", "Updating Todo…"),
                tr("已设为待办。", "Added to Todo."), tr("已标记为处理完成。", "Marked handled.")],
        }[kind];
        try {
            say(progress, "running");
            await api(messagePath(item) + "/marker", "PUT", {kind, enabled, language: root.lang});
            item[field] = enabled;
            const row = $("list").querySelector(`[data-message-key="${CSS.escape(key)}"]`);
            if (row) {
                // A read Top5 row can be held for preview after the server stops listing it.
                const visibleItem = rowItems.get(row);
                visibleItem[field] = enabled;
                renderMarkerIcons(row, visibleItem);
                if (row === currentRow()) {
                    if (!enabled && kind === "pin" && smartView === "top5") clearPreview();
                    else classificationActions(visibleItem);
                }
                window.ai2appsProcessIcons?.();
            }
            say(enabled ? added : removed, "success");
            await load();
        } finally {
            pendingMarkers.delete(pendingKey);
        }
    }
    async function refreshTodoState() {
        const next = JSON.stringify(await api("/todo-state"));
        const changed = todoState !== undefined && todoState !== next;
        todoState = next;
        return changed;
    }
    function confirmSenderBlock(value, folderName, kind) {
        const dialog = $("block-dialog");
        if (dialog.open) return Promise.resolve(false);
        $("block-title").textContent = kind === "domain"
            ? tr("屏蔽发件域名", "Block sender domain") : tr("屏蔽发件人", "Block sender");
        $("block-target").textContent = value;
        $("block-scope").textContent = kind === "domain"
            ? tr(`「${folderName}」将屏蔽来自该域名及其子域名的邮件。`,
                `Messages from this domain and its subdomains will be excluded from ${folderName}.`)
            : tr(`「${folderName}」将屏蔽来自此地址的邮件。`,
                `Messages from this address will be excluded from ${folderName}.`);
        dialog.showModal();
        return new Promise(resolve => {
            const listeners = new AbortController();
            const options = {signal: listeners.signal};
            const finish = confirmed => {
                listeners.abort();
                dialog.close();
                resolve(confirmed);
            };
            dialog.addEventListener("submit", event => {
                event.preventDefault();
                finish(event.submitter?.value === "block");
            }, options);
            dialog.addEventListener("cancel", event => {
                event.preventDefault();
                finish(false);
            }, options);
        });
    }
    function classificationActions(item) {
        const actions = $("smart-feedback");
        actions.replaceChildren();
        const why = $("priority-reason");
        why.hidden = smartView !== "top5" || !item.reason;
        const change = async (folderId, included) => {
            const path = messagePath(item);
            await api(path + "/classification", "POST", {folder_id: folderId, included});
            say(tr("已保存分类反馈。", "Classification feedback saved."), "success");
            if (!included && folderId === "top5" && smartView === folderId &&
                currentRow()?.dataset.messageKey === messageKey(item)) clearPreview();
            if (smartView) await load();
        };
        if (smartView === "top5") {
            why.textContent = item.reason + " · “" + item.evidence + "”";
            if (!item.pinned) actions.append(button(tr("移出 Top5", "Dismiss from Top5"), () => change("top5", false)));
        } else if (smartView && !isMarkerView(smartView)) {
            actions.append(button(tr("移出此目录", "Remove from this folder"), () => change(smartView, false)));
        }
        const folderId = smartView;
        if (hasBuiltInFilters(folderId) || folders.some(folder => folder.id === folderId)) {
            const block = document.createElement("select");
            block.setAttribute("aria-label", tr("屏蔽", "Block"));
            block.append(new Option(tr("屏蔽…", "Block…"), ""),
                new Option(tr("屏蔽发件人", "Block sender"), "address"),
                new Option(tr("屏蔽发件域名", "Block sender domain"), "domain"));
            block.onchange = async () => {
                const kind = block.value;
                if (!kind) return;
                block.disabled = true;
                try {
                    const path = messagePath(item) + "/block-sender";
                    const rule = {folder_id: folderId, kind};
                    const {excluded_sender} = await api(path, "POST", {...rule, preview: true});
                    if (smartView !== folderId || currentRow()?.dataset.messageKey !== messageKey(item)) return;
                    const name = folders.find(folder => folder.id === folderId)?.name || markerViews[folderId] || "Top5";
                    if (!await confirmSenderBlock(excluded_sender, name, kind)) return;
                    await api(path, "POST", {
                        ...rule, expected_sender: excluded_sender,
                    });
                    if (smartView === folderId && currentRow()?.dataset.messageKey === messageKey(item)) clearPreview();
                    await refreshFolders();
                    if (smartView === folderId) await load();
                    say(tr("已在此目录屏蔽 ", "Blocked in this folder: ") + excluded_sender, "success");
                } catch (error) { say(error.message); }
                finally {
                    block.value = "";
                    block.disabled = false;
                }
            };
            actions.append(block);
        }
        actions.prepend(button(tr("回复", "Reply"), () => openComposer(item)));
        actions.append(
            button(item.flagged ? tr("取消旗标", "Remove flag") : tr("加旗标", "Flag"),
                () => updateMarker(item, "flag", !item.flagged)),
            button(item.todo ? tr("已处理", "Mark handled") : tr("设为待办", "Add to Todo"),
                () => updateMarker(item, "todo", !item.todo)),
        );
        if (folders.length) {
            const select = document.createElement("select");
            select.setAttribute("aria-label", tr("加入智能目录", "Add to smart folder"));
            select.append(new Option(tr("加入智能目录…", "Add to smart folder…"), ""));
            for (const folder of folders) select.append(new Option(folder.name, folder.id));
            select.onchange = async () => {
                if (!select.value) return;
                try { await change(select.value, true); } catch (error) { say(error.message); }
                select.value = "";
            };
            actions.append(select);
        }
    }
    function senderName(value) {
        return value.replace(/\s*<[^<>]+>\s*$/, "").replace(/^"|"$/g, "").trim() || value;
    }
    const composeDialog = $("compose-dialog");
    const composeForm = $("compose-form");
    const attachmentPicker = $("attachment-picker");
    const attachmentLimit = 10 * 1024 * 1024;
    let activeDraft = null, composeAttachments = [], sendLocked = false;
    let draftReview = null;
    let writingRequest = null, replyDirection = "", suggestedBody = "";
    let replyAnalyzed = false, directionChanged = false;
    let replyItem = null;
    let sending = false;
    let openingReply = false;
    async function openComposer(item = null) {
        if (composeDialog.open || openingReply) return;
        const senders = accounts.filter(account => account.status === "connected" && account.smtp_host);
        const preferred = item ? senders.find(account => account.id === item.account_id)
            : senders.find(account => account.id === selected) || senders[0];
        if (!preferred) {
            say(tr("请先连接一个已配置发信服务器的邮箱。", "Connect a mailbox with an outgoing server first."));
            return;
        }
        let details;
        if (item) {
            const ticket = previewGeneration;
            openingReply = true;
            say(tr("正在准备回复…", "Preparing reply…"), "running");
            try {
                details = await api(messagePath(item) + "/reply");
                if (ticket !== previewGeneration) {
                    say(tr("就绪。", "Ready."), "idle");
                    return;
                }
                say(tr("回复草稿已打开。", "Reply draft opened."), "idle");
            } finally {
                openingReply = false;
            }
        }
        showComposer(item, preferred.id, details, senders);
    }
    async function openSavedDraft(id) {
        if (composeDialog.open || openingReply) return;
        const ticket = generation;
        openingReply = true;
        try {
            const draft = await api("/drafts/" + id);
            if (ticket !== generation) return;
            const item = draft.reply && {account_id: draft.account_id, uidvalidity: draft.reply.validity, uid: draft.reply.uid};
            showComposer(item, draft.account_id, null, accounts, draft);
        } finally {
            openingReply = false;
        }
    }
    function showComposer(item, accountId, details, senders, saved = null, review = null) {
        resetWritingAssist();
        draftReview = review;
        replyItem = item;
        activeDraft = saved && {id: saved.id, revision: saved.revision, status: saved.status};
        sendLocked = Boolean(saved && saved.status !== "draft");
        composeAttachments = (saved?.attachments || []).map(attachment => ({
            ...attachment, size: attachment.data.length * 3 / 4 - (attachment.data.endsWith("==") ? 2 : attachment.data.endsWith("=") ? 1 : 0),
        }));
        composeForm.reset();
        const fields = composeForm.elements;
        fields.account.replaceChildren(...senders.filter(account => !item || account.id === accountId).map(account =>
            new Option(account.address, account.id)));
        fields.account.value = accountId;
        fields.recipients.value = saved?.recipients.join(", ") ?? details?.recipient ?? "";
        fields.subject.value = saved?.subject ?? details?.subject ?? "";
        fields.body.value = saved?.body ?? "";
        if (review) review.savedPayload = JSON.stringify({
            recipients: saved.recipients, subject: fields.subject.value, body: fields.body.value,
            attachments: (saved.attachments || []).map(({name, data}) => ({name, data})),
        });
        $("compose-title").textContent = item ? tr("回复邮件", "Reply") : tr("写邮件", "New email");
        $("compose-status").textContent = sendLocked ? tr(...codeText.mail_send_uncertain) : "";
        updateComposer();
        composeDialog.showModal();
        (item ? fields.body : fields.recipients).focus();
    }
    function updateComposer() {
        const locked = sending || sendLocked;
        const fields = composeForm.elements;
        fields.account.disabled = locked || Boolean(replyItem);
        fields.recipients.readOnly = locked || Boolean(replyItem);
        fields.subject.readOnly = fields.body.readOnly = locked;
        $("send").disabled = $("compose-save").disabled = attachmentPicker.disabled = locked;
        $("compose-cancel").disabled = sending;
        $("compose-delete").hidden = !activeDraft;
        $("compose-delete").disabled = sending || activeDraft?.status === "sending";
        $("send").hidden = Boolean(draftReview);
        if (draftReview) $("compose-delete").hidden = true;
        for (const id of ["review-note", "review-confirm", "review-cancel"]) $(id).hidden = !draftReview;
        $("review-confirm").disabled = $("review-cancel").disabled = locked || Boolean(writingRequest);
        updateWritingControls();
        const list = $("compose-attachments");
        list.hidden = !composeAttachments.length;
        list.replaceChildren(...composeAttachments.map((attachment, index) => {
            const li = document.createElement("li");
            const label = document.createElement("span");
            label.textContent = attachment.name;
            const remove = button(tr("移除", "Remove"), () => {
                composeAttachments.splice(index, 1);
                updateComposer();
                attachmentPicker.focus();
            });
            remove.setAttribute("aria-label", tr("移除附件：", "Remove attachment: ") + attachment.name);
            remove.disabled = locked;
            li.append(label, remove);
            return li;
        }));
    }
    attachmentPicker.onchange = () => {
        const chosen = [...attachmentPicker.files];
        attachmentPicker.value = "";
        const all = [...composeAttachments, ...chosen];
        if (all.length > 10 || all.reduce((sum, file) => sum + file.size, 0) > attachmentLimit) {
            $("compose-status").textContent = tr(...codeText.mail_attachments_too_large);
            return;
        }
        composeAttachments.push(...chosen.map(file => ({name: file.name, size: file.size, file})));
        $("compose-status").textContent = "";
        updateComposer();
    };
    async function composePayload() {
        const fields = composeForm.elements;
        const recipients = fields.recipients.value.split(",").map(value => value.trim()).filter(Boolean);
        const attachments = await Promise.all(composeAttachments.map(async attachment => {
            const {name, file} = attachment;
            if (!file) return {name, data: attachment.data};
            const data = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result.split(",")[1]);
                reader.onerror = reader.onabort = () => reject(new Error(tr(...codeText.mail_invalid_attachment)));
                reader.readAsDataURL(file);
            });
            return {name, data};
        }));
        return {recipients, subject: fields.subject.value, body: fields.body.value, attachments};
    }
    async function persistDraft(payload) {
        const body = {...payload, account_id: composeForm.elements.account.value,
            reply: replyItem ? {validity: replyItem.uidvalidity, uid: replyItem.uid} : null};
        if (activeDraft) body.revision = activeDraft.revision;
        const saved = await api(activeDraft ? "/drafts/" + activeDraft.id : "/drafts",
            activeDraft ? "PUT" : "POST", body);
        activeDraft = {...saved, status: "draft"};
    }
    function refreshDraftList() {
        if (smartView === "drafts") load().catch(error => say(error.message));
    }
    function composeError(message) {
        $("compose-status").textContent = message;
        say(message);
    }
    function updateWritingControls() {
        const locked = sending || sendLocked;
        const disabled = locked || Boolean(writingRequest);
        $("ai-assist").disabled = locked;
        $("ai-generate").disabled = disabled;
        $("ai-instruction").disabled = locked;
        $("ai-stop").hidden = !writingRequest;
        $("ai-retry").hidden = !replyItem || replyAnalyzed || Boolean(writingRequest);
        $("ai-retry").disabled = locked;
        $("ai-apply").hidden = !suggestedBody;
        $("ai-apply").disabled = disabled;
        $("review-confirm").disabled = $("review-cancel").disabled = disabled;
        $("ai-directions").querySelectorAll("button").forEach(node => { node.disabled = disabled; });
        const revising = Boolean(suggestedBody || composeForm.elements.body.value.trim());
        $("ai-generate").textContent = revising ? tr("修改正文", "Revise body") : tr("生成正文", "Generate body");
    }
    function stopWritingAssist() {
        const request = writingRequest;
        writingRequest = null;
        request?.abort();
    }
    function resetWritingAssist() {
        stopWritingAssist();
        replyDirection = suggestedBody = "";
        replyAnalyzed = false;
        directionChanged = false;
        $("ai-panel").hidden = true;
        $("ai-assist").setAttribute("aria-expanded", "false");
        $("ai-summary").hidden = $("ai-result").hidden = true;
        for (const id of ["ai-summary", "ai-result", "ai-directions", "ai-status"]) $(id).textContent = "";
        $("ai-instruction").value = "";
    }
    async function runWritingAssist(action) {
        if (writingRequest || sending || sendLocked) return;
        const fields = composeForm.elements;
        const instruction = $("ai-instruction").value.trim();
        if (action === "write" && !instruction && !directionChanged) {
            $("ai-status").textContent = tr("请输入撰写或修改要求，或选择一个回复方向。", "Enter writing or revision instructions, or choose a reply direction.");
            $("ai-instruction").focus();
            return;
        }
        const request = new AbortController();
        writingRequest = request;
        updateWritingControls();
        $("ai-status").textContent = action === "directions"
            ? tr("正在分析原邮件…", "Analyzing the original email…")
            : tr("正在撰写正文…", "Writing the message…");
        const base = replyItem ? messagePath(replyItem) : "/accounts/" + fields.account.value;
        const payload = {action, language: root.lang};
        if (action === "write") Object.assign(payload, {
            instruction, direction: replyDirection, subject: fields.subject.value,
            body: suggestedBody || fields.body.value,
        });
        try {
            const result = await api(base + "/writing-assist", "POST", payload, request.signal);
            if (writingRequest !== request) return;
            if (action === "directions") {
                replyAnalyzed = true;
                $("ai-summary").textContent = result.summary;
                $("ai-summary").hidden = false;
                const directions = $("ai-directions");
                directions.replaceChildren(...result.directions.map(direction => {
                    const choice = button(direction, () => {
                        replyDirection = direction;
                        directionChanged = true;
                        directions.querySelectorAll("button").forEach(node =>
                            node.setAttribute("aria-pressed", String(node === choice)));
                    });
                    choice.setAttribute("aria-pressed", "false");
                    return choice;
                }));
                $("ai-status").textContent = tr("选择回复方向，也可以直接输入要求。", "Choose a reply direction or enter your own instructions.");
            } else {
                suggestedBody = result.body;
                directionChanged = false;
                $("ai-result").textContent = suggestedBody;
                $("ai-result").hidden = false;
                if ($("ai-instruction").value.trim() === instruction) $("ai-instruction").value = "";
                $("ai-status").textContent = tr("可以使用这版正文，或输入要求继续修改。", "Use this version or enter instructions to revise it.");
            }
        } catch (error) {
            if (writingRequest === request) $("ai-status").textContent = error.message;
        } finally {
            if (writingRequest === request) {
                writingRequest = null;
                updateWritingControls();
            }
        }
    }
    $("ai-assist").onclick = () => {
        const panel = $("ai-panel");
        panel.hidden = !panel.hidden;
        $("ai-assist").setAttribute("aria-expanded", String(!panel.hidden));
        if (panel.hidden) return;
        if (replyItem && !replyAnalyzed && !writingRequest) void runWritingAssist("directions");
        else $("ai-instruction").focus();
    };
    $("ai-generate").onclick = () => void runWritingAssist("write");
    $("ai-retry").onclick = () => void runWritingAssist("directions");
    $("ai-stop").onclick = () => {
        stopWritingAssist();
        $("ai-status").textContent = tr("已停止等待。", "Stopped waiting.");
        updateWritingControls();
    };
    $("ai-apply").onclick = () => {
        if (!suggestedBody || sending || sendLocked || writingRequest) return;
        composeForm.elements.body.value = suggestedBody;
        suggestedBody = "";
        $("ai-result").textContent = "";
        $("ai-result").hidden = true;
        $("ai-status").textContent = tr("已填入正文，可以继续修改。", "Added to the message. You can keep editing.");
        updateWritingControls();
        composeForm.elements.body.focus();
    };
    composeForm.elements.body.addEventListener("input", updateWritingControls);
    $("compose").onclick = () => openComposer().catch(error => say(error.message));
    window.addEventListener("ai2apps:host-context", async event => {
        const intent = event.detail?.appInteraction;
        if (!intent || intent.returning || composeDialog.open || openingReply) return;
        const path = "/reviews/" + encodeURIComponent(intent.runId) + "/" + encodeURIComponent(intent.interactionId);
        openingReply = true;
        try {
            const handoff = await fetch("/v1/platform/agent-runs/" + encodeURIComponent(intent.runId) +
                "/interactions/" + encodeURIComponent(intent.interactionId) + "/handoff", {credentials: "same-origin"});
            if (!handoff.ok) throw new Error(tr(...codeText.mail_review_unavailable));
            const target = await handoff.json();
            if (target.target?.app_id !== "ai2apps.mail" || target.target.mini_app_id || target.status !== "pending") return;
            const [draft] = await Promise.all([api(path), refreshAccounts()]);
            if (composeDialog.open) return;
            const item = {account_id: draft.account_id, uidvalidity: draft.reply.validity, uid: draft.reply.uid};
            showComposer(item, draft.account_id, null, accounts, draft, {path, intent});
        } catch (error) {
            say(error.message);
        } finally {
            openingReply = false;
        }
    });
    async function finishReview(decision) {
        if (!draftReview || sending || sendLocked || writingRequest) return;
        const {path, intent} = draftReview;
        sending = true;
        updateComposer();
        try {
            if (decision === "confirmed") {
                const payload = await composePayload();
                const serialized = JSON.stringify(payload);
                if (serialized !== draftReview.savedPayload) {
                    await persistDraft(payload);
                    draftReview.savedPayload = serialized;
                }
            }
            await api(path, "POST", {decision, revision: activeDraft.revision});
            composeDialog.close();
            refreshDraftList();
            await window.ai2appsShell.openHandoff(intent.runId, intent.interactionId, true);
        } catch (error) {
            if (composeDialog.open) composeError(error.message);
            else say(error.message);
        } finally {
            sending = false;
            updateComposer();
        }
    }
    $("review-confirm").onclick = () => void finishReview("confirmed");
    $("review-cancel").onclick = () => void finishReview("cancelled");
    $("compose-cancel").onclick = () => composeDialog.close();
    composeDialog.addEventListener("cancel", event => {
        if (sending) event.preventDefault();
    });
    composeDialog.addEventListener("close", () => {
        if (composeDialog.open) return;
        resetWritingAssist();
        draftReview = null;
        composeForm.reset();
        composeAttachments = [];
        activeDraft = null;
        replyItem = null;
        $("compose-attachments").replaceChildren();
    });
    $("compose-save").onclick = async () => {
        if (sending || sendLocked) return;
        sending = true;
        updateComposer();
        $("compose-status").textContent = tr("正在保存…", "Saving…");
        try {
            await persistDraft(await composePayload());
            composeDialog.close();
            say(tr("已保存到草稿。", "Saved to Drafts."), "success");
            refreshDraftList();
        } catch (error) {
            composeError(error.message);
        } finally {
            sending = false;
            updateComposer();
        }
    };
    $("compose-delete").onclick = async () => {
        if (sending || !activeDraft || !confirm(tr("删除这封草稿？", "Delete this draft?"))) return;
        sending = true;
        updateComposer();
        try {
            await api(`/drafts/${activeDraft.id}?revision=${activeDraft.revision}`, "DELETE");
            composeDialog.close();
            say(tr("草稿已删除。", "Draft deleted."), "success");
            refreshDraftList();
        } catch (error) {
            composeError(error.message);
        } finally {
            sending = false;
            updateComposer();
        }
    };
    composeForm.onsubmit = async event => {
        event.preventDefault();
        if (sending || draftReview || $("send").disabled) return;
        const fields = composeForm.elements;
        const item = replyItem;
        if (!fields.body.value.trim() && !composeAttachments.length) {
            composeError(tr("请填写正文或添加附件。", "Write a message or add an attachment."));
            return;
        }
        const path = item ? messagePath(item) + "/reply" : "/accounts/" + fields.account.value + "/send";
        sending = true;
        let submitted = false;
        updateComposer();
        const progress = tr("正在发送…", "Sending…");
        $("compose-status").textContent = progress;
        say(progress, "running");
        try {
            const payload = await composePayload();
            if (activeDraft) await persistDraft(payload);
            submitted = true;
            const result = activeDraft
                ? await api("/drafts/" + activeDraft.id + "/send", "POST", {revision: activeDraft.revision})
                : await api(path, "POST", payload);
            composeDialog.close();
            if (result.draft_cleanup_failed) {
                say(tr("邮件已发送，未能清除本地草稿。", "Message sent, but the local draft could not be removed."));
            } else if (item && !result.reply_marked) {
                say(tr("已发送，未能更新原邮件的回复标记。", "Sent, but could not update the original message’s reply marker."));
            } else {
                say(tr("邮件已发送。", "Message sent."), "success");
            }
            if (item && result.reply_marked) {
                item.answered = true;
                const row = $("list").querySelector(`[data-message-key="${CSS.escape(messageKey(item))}"]`);
                if (row) {
                    rowItems.get(row).answered = true;
                    renderMarkerIcons(row, rowItems.get(row));
                    window.ai2appsProcessIcons?.();
                }
                refreshUnreadCounts();
            }
            refreshDraftList();
        } catch (error) {
            sendLocked = submitted && (!error.cause || error.cause === "mail_send_uncertain");
            if (sendLocked && activeDraft) activeDraft.status = "sending";
            composeError(sendLocked ? tr(...codeText.mail_send_uncertain) : error.message);
        } finally {
            sending = false;
            updateComposer();
        }
    };
    const richFrame = $("rich-preview");
    const imageButton = $("load-images");
    const imageStatus = $("image-status");
    let openingMailLink = false;
    function mailWebUrl(value) {
        if (!/^https?:\/\//i.test(value)) return null;
        try {
            const url = new URL(value);
            if (!url.username && !url.password && url.href.length <= 2048) return url.href;
        } catch (_) { /* Invalid address. */ }
        return null;
    }
    async function openMailLink(value) {
        const url = mailWebUrl(value);
        if (!url || openingMailLink) return;
        openingMailLink = true;
        let connection;
        try {
            const response = await fetch("/v1/platform/client/browser-profiles/default/launch", {
                method: "POST", credentials: "same-origin",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({initial_url: url}),
            });
            if (!response.ok) throw new Error();
            const launch = await response.json();
            // A newly launched window takes its initial URL. A focused window
            // needs a separate tab in the returned Profile's user context.
            if (launch.status === "launched") return;
            if (launch.status !== "focused" || !launch.user_context) throw new Error();
            connection = new window.AI2AppsBiDi.AI2AppsBiDiConnection();
            await connection.connect();
            const {contexts} = await connection.command("browsingContext.getTree", {maxDepth: 0});
            const reference = contexts.find(item => item.userContext === launch.user_context);
            if (!reference) throw new Error();
            const {context} = await connection.command("browsingContext.create", {
                type: "tab", referenceContext: reference.context, userContext: launch.user_context,
            });
            await connection.command("browsingContext.navigate", {context, url, wait: "none"});
        } catch (_) {
            say(tr("无法在默认 AI 浏览器中打开此链接。", "Could not open this link in the default AI Browser."));
        } finally {
            try {
                await connection?.close();
            } finally {
                openingMailLink = false;
            }
        }
    }
    function handleMailLink(event) {
        const link = event.target.closest?.("a[data-mail-url]");
        if (!link) return;
        event.preventDefault();
        if (event.isTrusted && (event.button === 0 || event.button === 1)) {
            void openMailLink(link.dataset.mailUrl);
        }
    }
    function setMobileLink(link) {
        const url = mailWebUrl(link.dataset.mailUrl);
        if (!url) return;
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
    }
    richFrame.addEventListener("load", () => {
        if (richFrame.hidden || !richFrame.hasAttribute("srcdoc")) return;
        const doc = richFrame.contentDocument;
        if (mobile) {
            doc?.querySelectorAll("a[data-mail-url]").forEach(setMobileLink);
        } else {
            doc?.addEventListener("click", handleMailLink);
            doc?.addEventListener("auxclick", handleMailLink);
        }
    });
    if (!mobile) {
        $("preview").addEventListener("click", handleMailLink);
        $("preview").addEventListener("auxclick", handleMailLink);
    }
    function showTextPreview(text) {
        const preview = $("preview");
        const parts = [];
        let offset = 0;
        for (const match of text.matchAll(/\bhttps?:\/\/[^\s<>"']+/gi)) {
            const value = match[0].replace(/[.,;!?]+$/, "");
            if (!mailWebUrl(value)) continue;
            const link = document.createElement("a");
            link.href = "#";
            link.dataset.mailUrl = value;
            link.textContent = value;
            if (mobile) setMobileLink(link);
            parts.push(text.slice(offset, match.index), link);
            offset = match.index + value.length;
        }
        preview.replaceChildren(...parts, text.slice(offset));
    }
    function resetPreview() {
        imageButton.hidden = true;
        imageButton.onclick = null;
        imageButton.disabled = false;
        imageStatus.textContent = "";
        richFrame.hidden = true;
        richFrame.removeAttribute("srcdoc");
        $("preview").hidden = false;
        $("preview").textContent = "";
        $("preview").parentElement.scrollTop = 0;
    }
    function clearPreview() {
        previewGeneration++;
        currentRow()?.removeAttribute("aria-current");
        $("subject").textContent = tr("邮件预览", "Message preview");
        $("from").textContent = "";
        resetPreview();
        $("smart-feedback").replaceChildren();
        $("priority-reason").hidden = true;
    }
    function setRichMarkup(markup, withImages = false) {
        // Only locally decoded raster data can appear after the opt-in request.
        const imagePolicy = withImages ? "img-src data:;" : "";
        richFrame.srcdoc = '<!doctype html><meta charset="utf-8">' +
            `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; ${imagePolicy} style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">` +
            '<style>html{color-scheme:light}body{margin:0;padding:12px;color:#25272b;background:white;font:15px/1.5 system-ui,sans-serif;overflow-wrap:anywhere}table,img{max-width:100%}img{object-fit:contain}pre{white-space:pre-wrap}a[data-mail-url]{color:inherit;cursor:pointer}</style>' +
            markup;
    }
    function recentPreview(item) {
        const key = messageKey(item);
        let entry = recentPreviews.get(key);
        if (entry) recentPreviews.delete(key);
        else {
            entry = {body: api(messagePath(item)).catch(error => {
                if (recentPreviews.get(key) === entry) recentPreviews.delete(key);
                throw error;
            })};
        }
        recentPreviews.set(key, entry);
        if (recentPreviews.size > recentPreviewLimit) recentPreviews.delete(recentPreviews.keys().next().value);
        return entry;
    }
    function previewImages(entry, path) {
        entry.imageRequest ||= api(path + "/remote-images", "POST", {}).then(result => {
            if (result.html && result.loaded_images) entry.images = result;
            return result;
        }).finally(() => { entry.imageRequest = null; });
        return entry.imageRequest;
    }
    function showRichPreview(data, entry, path, ticket) {
        function showLoadedImages(result) {
            setRichMarkup(result.html, true);
            imageButton.hidden = true;
            imageStatus.textContent = tr(`已加载 ${result.loaded_images} 张图片`, `Loaded ${result.loaded_images} images`);
        }
        richFrame.hidden = false;
        $("preview").hidden = true;
        if (entry.images) {
            showLoadedImages(entry.images);
            return;
        }
        setRichMarkup(data.html);
        imageButton.hidden = !data.remote_images;
        async function loadImages() {
            imageButton.disabled = true;
            imageStatus.textContent = tr("正在加载图片…", "Loading images…");
            try {
                await previewImages(entry, path);
                if (ticket !== previewGeneration) return;
                if (entry.images) showLoadedImages(entry.images);
                else imageStatus.textContent = tr("没有可加载的远程图片", "No remote images could be loaded");
            } catch (error) {
                if (ticket === previewGeneration) imageStatus.textContent = error.message;
            } finally {
                if (ticket === previewGeneration) imageButton.disabled = false;
            }
        }
        imageButton.onclick = loadImages;
        if (data.remote_images && (data.auto_load_images || entry.imageRequest)) loadImages();
    }
    async function preview(item, row) {
        if (mobile) root.dispatchEvent(new Event("mail-open-reading"));
        const previous = currentRow();
        const releasePrevious = smartView === "top5" && previous && previous !== row &&
            !previous.classList.contains("mail-unread") && !previous.parentElement.querySelector('[aria-pressed="true"]');
        classificationActions(item);
        const ticket = ++previewGeneration;
        resetPreview();
        previous?.removeAttribute("aria-current");
        row.setAttribute("aria-current", "true");
        if (releasePrevious) load().catch(error => say(error.message));
        $("subject").textContent = item.subject || tr("无主题", "No subject");
        $("from").textContent = item.sender + " · " + tr("收件人：", "To: ") + item.address;
        $("preview").textContent = tr("正在加载…", "Loading…");
        try {
            const path = messagePath(item);
            const entry = recentPreview(item);
            const data = await entry.body;
            if (ticket !== previewGeneration) return;
            const unavailable = data.preview_status === "too_large" ? tr("邮件过大，无法预览。", "This message is too large to preview.") : tr("没有可预览的正文文字。", "No readable message text to preview.");
            const suffix = data.preview_status === "truncated" ? tr("\n\n预览已截断。", "\n\nPreview truncated.") : "";
            showTextPreview((data.text || unavailable) + suffix);
            if (data.html) showRichPreview(data, entry, path, ticket);
            if (!item.seen && (data.text || data.html) && !openedMessages.has(messageKey(item))) {
                try {
                    await api(path + "/read", "POST", {});
                    const key = messageKey(item);
                    openedMessages.add(key);
                    item.seen = 1;
                    for (const message of $("list").querySelectorAll(".mail-unread")) {
                        if (message.dataset.messageKey === key) {
                            message.classList.remove("mail-unread");
                            message.removeAttribute("aria-label");
                        }
                    }
                    if (smartView === "top5" && currentRow()?.dataset.messageKey !== key) await load();
                    else {
                        if (smartView === "top5") renderUnreadCounts();
                        refreshUnreadCounts();
                    }
                } catch (error) {
                    if (ticket === previewGeneration) say(error.message);
                }
            }
        } catch (error) {
            if (ticket === previewGeneration) $("preview").textContent = error.message;
        }
    }
    function usesGoogle() {
        return (reconnectAccount?.provider || form.elements.provider.value) === "gmail" && !gmailPassword;
    }
    function updatePreset(provider = reconnectAccount?.provider || form.elements.provider.value) {
        const custom = provider === "imap";
        const google = usesGoogle();
        $("address-label").hidden = google;
        form.elements.address.disabled = google;
        $("display-name-label").hidden = google;
        $("password-label").hidden = google;
        form.elements.password.disabled = google;
        $("gmail-mode").hidden = provider !== "gmail" || reconnectAccount?.auth_mode === "xoauth2";
        $("gmail-mode").textContent = google ?
            tr("使用应用专用密码", "Use an app password") : tr("改用 Google 登录", "Use Google sign-in instead");
        $("submit").textContent = google ? tr("使用 Google 登录", "Sign in with Google") :
            tr("验证并连接", "Verify and connect");
        $("custom").hidden = !custom;
        $("custom").disabled = !custom;
        $("user-label").hidden = provider === "gmail";
        $("provider-hint").textContent = provider === "icloud" ?
            tr("IMAP 993 TLS，SMTP 587 STARTTLS。IMAP 默认使用地址前缀，可填写完整地址。", "IMAP 993 TLS, SMTP 587 STARTTLS. IMAP defaults to the address prefix; you can enter the full address.") :
            google ? tr("在系统浏览器中选择 Google 账号并授权 Mail 通过 IMAP 连接 Gmail。",
                "Choose your Google account in the system browser and authorize Mail to connect to Gmail over IMAP.") :
            provider === "gmail" ? tr(
                "在 Google 账户中开启两步验证，再生成 16 位应用专用密码填在这里。工作或学校账户及高级保护账户可能没有此选项。",
                "Turn on 2-Step Verification in your Google Account, then generate a 16-character app password to enter here. Work, school, or Advanced Protection accounts may not offer this option.",
            ) :
            tr("使用服务商提供的 TLS 服务器与凭据。", "Use the TLS server and credentials supplied by your provider.");
        $("password-label").querySelector("span").textContent = custom ? tr("密码", "Password") : tr("应用专用密码", "App password");
        $("password-link").hidden = custom || google;
        $("password-link").href = provider === "icloud" ? "https://account.apple.com/" : "https://myaccount.google.com/apppasswords";
        $("password-link").textContent = provider === "gmail" ?
            tr("前往 Google 生成应用专用密码", "Create a Google app password") :
            tr("管理 Apple 应用专用密码", "Manage Apple app passwords");
    }
    function openForm(account) {
        form.reset();
        reconnectAccount = account || null;
        gmailPassword = false;
        reconnect = account?.id || "";
        settings.disabled = Boolean(account);
        settings.hidden = Boolean(account);
        $("form-error").textContent = "";
        $("dialog-title").textContent = account ? tr("重新连接：", "Reconnect: ") + account.address : tr("添加账户", "Add account");
        updatePreset(account?.provider);
        dialog.showModal();
    }
    if (!mobile) $("add").onclick = () => openForm();
    form.elements.provider.onchange = () => {
        gmailPassword = false;
        form.elements.password.value = "";
        form.elements.username.value = "";
        updatePreset();
    };
    $("gmail-mode").onclick = () => {
        gmailPassword = !gmailPassword;
        form.elements.password.value = "";
        updatePreset();
    };
    function cancelConnection() {
        const path = oauthPath;
        oauthPath = "";
        if (path) api(path, "DELETE").catch(() => {});
        dialog.close();
    }
    $("cancel").onclick = cancelConnection;
    dialog.addEventListener("cancel", event => {
        event.preventDefault();
        if (!$("cancel").disabled) cancelConnection();
    });
    dialog.addEventListener("close", () => { form.elements.password.value = ""; });
    async function connectGoogle() {
        const result = await api("/gmail/oauth", "POST", {account_id: reconnect || null});
        const path = "/gmail/oauth/" + encodeURIComponent(result.flow_id);
        oauthPath = path;
        $("submit").textContent = tr("等待 Google 授权…", "Waiting for Google…");
        $("cancel").disabled = false;
        const deadline = Date.now() + 305000;
        try {
            while (oauthPath === path && Date.now() < deadline) {
                await new Promise(resolve => setTimeout(resolve, 1000));
                if (oauthPath !== path) return null;
                $("cancel").disabled = true;
                try {
                    const outcome = await api(path, "POST", {});
                    if (outcome.status === "connected") return outcome.account;
                } catch (error) {
                    if (error.cause !== "mail_busy") throw error;
                }
                $("cancel").disabled = false;
            }
            if (oauthPath === path) throw new Error(tr(...codeText.gmail_oauth_expired));
            return null;
        } finally {
            if (oauthPath === path) {
                oauthPath = "";
                api(path, "DELETE").catch(() => {});
            }
        }
    }
    form.onsubmit = async event => {
        event.preventDefault();
        if (connecting) return;
        $("form-error").textContent = "";
        const google = usesGoogle();
        let data = Object.fromEntries(new FormData(form));
        if (!reconnect) {
            if (data.port) data.port = Number(data.port);
            if (data.smtp_port) data.smtp_port = Number(data.smtp_port);
        }
        form.elements.password.value = "";
        const submit = $("submit");
        connecting = true;
        submit.disabled = true;
        $("gmail-mode").disabled = true;
        form.elements.provider.disabled = true;
        submit.textContent = tr("正在验证…", "Verifying…");
        $("cancel").disabled = true;
        try {
            const account = google ? await connectGoogle() :
                await api(reconnect ? "/accounts/" + reconnect + "/reconnect" : "/accounts", "POST", data);
            if (!account) return;
            dialog.close();
            await refreshAccounts();
            await selectAccount(account.id);
            say(tr("连接成功。选择同步以加载邮件。", "Connected. Select Sync to load mail."), "success");
        } catch (error) {
            if (dialog.open) $("form-error").textContent = error.message;
            else say(error.message);
        } finally {
            data = null;
            connecting = false;
            submit.disabled = false;
            $("gmail-mode").disabled = false;
            form.elements.provider.disabled = false;
            $("cancel").disabled = false;
            updatePreset();
        }
    };
    $("all").onclick = () => selectAccount("").catch(error => say(error.message));
    $("more").onclick = () => load(false).catch(error => say(error.message));
    $("search").onsubmit = event => {
        event.preventDefault();
        query = new FormData(event.target).get("q").trim();
        load().catch(error => say(error.message));
    };
    $("sync").onclick = async () => {
        if (busy || organizing) return;
        hideToolbarTip();
        if (smartView === "drafts") {
            await load().catch(error => say(error.message));
            return;
        }
        if (smartView === "top5") clearPreview();
        const organizeAfterSync = Boolean(smartView && !isMarkerView(smartView));
        const syncOnly = isMarkerView(smartView);
        const targets = accounts.filter(a => !selected || a.id === selected);
        busy = true;
        updateWorkButtons();
        say(tr("正在同步…", "Syncing…"), "running");
        try {
            const results = [];
            for (let start = 0; start < targets.length; start += 4) {
                results.push(...await Promise.allSettled(
                    targets.slice(start, start + 4).map(a => api("/accounts/" + a.id + "/sync", "POST")),
                ));
            }
            await refreshAccounts();
            await load();
            const errors = results.flatMap((r, i) => r.status === "rejected" ? [targets[i].display_name + ": " + r.reason.message] : []);
            say(errors.length ? errors.join(" · ") : tr("同步完成。", "Sync complete."), errors.length ? "error" : "success");
            if (!syncOnly && (organizeAfterSync || hasOrganized || folders.some(folder => !folder.preset || folder.revision > 1))) {
                await organize(targets.filter((_, i) => results[i].status === "fulfilled"), errors);
            }
        } catch (error) {
            say(error.message);
        } finally {
            busy = false;
            updateWorkButtons();
        }
    };
    renderFolders();
    Promise.allSettled([refreshAccounts(), refreshFolders()]).then(async results => {
        const failure = results.find(result => result.status === "rejected");
        if (failure) say(failure.reason.message);
        if (generation === 0) await load();
        else if (smartView === "top5") await load();
        checkTodoChanges();
    }).catch(error => say(error.message));
    refreshAnalysisModel().catch(error => say(error.message));
    let checkingTodos = false;
    async function checkTodoChanges() {
        if (checkingTodos || document.hidden || !accounts.length) return;
        checkingTodos = true;
        try {
            if (await refreshTodoState()) await load();
        } catch {
            // The next check can retry without interrupting mail reading.
        } finally {
            checkingTodos = false;
        }
    }
    document.addEventListener("visibilitychange", checkTodoChanges);
    window.addEventListener("focus", checkTodoChanges);
    setInterval(checkTodoChanges, 5000);
})();
