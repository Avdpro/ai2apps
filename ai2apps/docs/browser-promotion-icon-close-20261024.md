# 无文字关闭图标的弹层处理

Businessworld 原任务 run_1ed0c3668ce249a09a30148f12285d64 在 read 步骤返回 blocking_prompt。实际 Task-owned BiDi context 的 DOM 显示 newsletter-modal 内为图片推广，按钮没有文字/aria-label/title，样式为 btn-close modal-close-custom，具有 data-bs-dismiss=modal 和 type=button。旧检查只匹配可访问名称，因而未选中可见的 CSS 关闭图标。

共享 SDK control 在可关闭的推广/可选登录提示中接受无文字 BUTTON 的明确 modal/dialog dismiss 属性，或明确的 btn-close/modal-close/dialog-close/close-button 类 token。仍要求可见、启用、非 submit、视口命中检测通过；不能仅根据位置、普通链接或模糊 x 类猜测关闭。不将此规则用于 Cookie 同意选择，验证码/付费墙优先检查不变。点击继续使用原生 BiDi 输入并重新检查，最多三次；没有 DOM 删除、脚本模拟 click、站点特例或新浏览器控制协议。

Browser SDK 为源，生成 browser/dom_helpers.json 供 Local 使用，两者一致性检查通过。14 项 Node 检查与18项 Python 读取/弹层回归通过。真实 Dev 原有任务页面验证：识别 Close，原生点击后 classification=none/dismissed=true，提取正文2179字符；没有重新执行搜索。

Dev 当前后台任务仍停在原有用户协助交互。没有直接改数据库、重放未知动作或强制重启 Dev；需通过任务 UI 的“继续”恢复。主 App 无可用 BiDi 页面上下文，原生 Computer Use 超时，本轮未代为提交继续。Dev 后台进程尚未加载新的 helper JSON，等任务结束后按标准 Helper 重启激活；真实网页验证使用从当前 checkout 导入的新 SDK。

App-Dev 空闲，经标准 Helper 重启加载，最终路径/资源验证见发布账本。不涉及 Package 或生产发布。
