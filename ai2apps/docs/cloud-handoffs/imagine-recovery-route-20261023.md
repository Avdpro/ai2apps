# Imagine Studio Mobile 历史结果恢复精确路由

进入 Imagine Studio 会 POST `/v1/platform/imagine-studio/runs/recover-session-results`，再 GET runs。此前 Local 的 owner_studio_routes.json 与 Cloud infrastructure/remote/owner-studio-routes.v1.json 都缺少此 POST，导致远程不支持该操作，前端异常中断后续输出加载。

Cloud 需按既有 Owner Studio 访问约束添加上述唯一 POST 路径；不要放宽 runs 通配方法、匿名访问或其它 Studio API。保留 Owner 身份、设备/实例租约、Origin 和资源归属检查，以及 X-AI2Apps-App-Instance 头传递。

Local 已加入精确路由，handler 复用 Imagine owner 的 recover_session_results：检查 App instance 和 Agent run 归属，只恢复已验证的历史图片投影，不执行模型或重新生成。前端兼容尚未部署的新路由：404/405 时继续读取现有 runs，本次页面只尝试一次；401/403/5xx 仍报错，不掩盖授权失败。

验证 Cloud 部署后：合法 Owner POST 可以到达 Local；无 Cookie/错误 Origin/跨实例拒绝；其它未授权路径不新增访问；真实手机进入并看到既有输出。Local 前端兼容不依赖 Cloud 先部署。此文不声称已部署 Cloud。

## 激活记录

Cloud 已交付 imagine-recovery-edge-20261023-v1 回执。Dev Local 已通过标准 Helper 重启，端口61384，源码绑定、实际模块导入和 served JS 已核验，health200。无凭证公网 Host POST 返回403。真实 Owner/手机历史图片恢复仍待用户进入 Studio 复验，本记录不将负向探针视为业务恢复成功。
