# SANDUN 真实流程实测脚本（研究实验物 · 可丢弃）

本目录保留 2026-09-26 **用真实账号走完整 SANDUN 流程**的脚本与产物，作为立项前竞品研究的历史证据。

**2026-09-28 工作边界**：后续仅在当前 Linux 本机研究和测试；旧 Windows/WPS 命令不是当前执行要求。历史账号授权不自动授权再次登录、建项目或消耗积分，本轮没有重跑这些操作。当前说明见 [开发与验证环境](../../../docs/开发与验证环境.md)。
完整报告见 [`research/2026-09-26_SANDUN真实流程与产物实证.md`](../../2026-09-26_SANDUN真实流程与产物实证.md)。

## 历史记录中走通的流程

```text
登录 → 建项目 → agent/start → 需求单(自动提交默认值)
     → 生成大纲 → 搜索清单 → 深度搜索 → 内容策划(人工确认)
     → 生成初稿(15页) → 风格选择(4套推荐，人工选1) → 正式设计
     → 导出 PPTX → 下载(69,830 B) → 解包 → WPS 实开
```

## 脚本

| 脚本 | 作用 |
| --- | --- |
| `flow.py` | 登录 / 建项目 / 启动 / 发消息 / 读状态（`login` `create` `start` `message` `watch`） |
| `capture.py` | SSE 事件流抓取与进度分析（`capture.py 300` 抓 300 秒；`capture.py analyze` 只分析） |
| `sse.py` | 单次 SSE 连接，查看实时事件 |
| `inspect_pptx.py` | 解包分析导出产物（图表部件 / 嵌入工作簿 / 原生表格 / 字体引用） |
| `probe_sandun.ps1` | **WPS 32 位探针**：打开、统计形状类型、检查图表可编辑性、抽查文字 |

## 凭据处理（重要）

**凭据不进仓库。** `flow.py` 从 `credentials.json` 读取账号密码（**该文件已于 2026-09-26 删除**，
因凭据不应留存；需要时可重建，它由 `.gitignore` 排除）；也可用环境变量覆盖：

```bash
# 方式一：本机凭据文件（首次需手动创建，勿提交）
# research/experiments/sandun-live/credentials.json
# { "account": "手机号", "password": "密码" }

# 方式二：环境变量
export SANDUN_ACCOUNT="..."
export SANDUN_PASSWORD="..."
```

会话 `token` 存于 `session.json`，同样被忽略。

> **教训**：本目录初版把账号密码**硬编码在脚本里**，提交前扫描才发现。
> 即使是被授权的测试账号，凭据也不应进仓库——因为仓库要长期公开。
> 现在已改为外部注入，并在提交前加了敏感内容扫描（见报告「复现与边界」一节）。

## 产物

| 文件 | 说明 |
| --- | --- |
| `downloads/sandun_generated.pptx` | **SANDUN 生成的真实产物**（15 页，69,830 B） |
| `downloads/sandun_generated.inspect.json` | 解包分析结果 |
| `state.json` | 实时项目状态快照（含 `chart_plans` 等结构化数据） |
| `sse-raw.jsonl` | 完整 SSE 事件流 |
| `flow-log.jsonl` | 关键操作日志 |

## 边界声明

- 当时实验记录为使用**所有者授权的测试账号**并消耗积分；这是历史授权，不是当前可重复执行的授权；
- 所有请求带 `Origin`/`Referer` 与真实 UA，**未绕过任何鉴权**，未调用未授权端点；
- 下载产物是**我们自己的项目**的输出，非其官方案例；
- 本目录是**可丢弃的研究资产**，不构成产品脚手架或选型决定；旧工程 ADR 已清理。
- 产物仅用于本项目研究对照，**不再分发**。

## 历史执行记录（不是当前本机步骤）

以下保留原 Windows 命令用于追溯。无需恢复该环境；若后续确需重新采集，应先确定研究问题、本机可执行步骤与账号/费用授权。

```powershell
E:\Python312\python.exe research/experiments/sandun-live/flow.py login
E:\Python312\python.exe research/experiments/sandun-live/flow.py create
E:\Python312\python.exe research/experiments/sandun-live/flow.py start
E:\Python312\python.exe research/experiments/sandun-live/capture.py 300
E:\Python312\python.exe research/experiments/sandun-live/flow.py message "继续"
# 导出（POST 建 job，再轮询取下载链接）
E:\Python312\python.exe research/experiments/sandun-live/inspect_pptx.py downloads/sandun_generated.pptx
C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -NoProfile `
  -ExecutionPolicy Bypass -File research/experiments/sandun-live/probe_sandun.ps1
```

当时观察到的导出端点（不保证当前接口不变）：

```text
POST /api/export/pptx            {"projectId": "..."}  → {jobId}
GET  /api/export/pptx/job?jobId=...&wait=1&timeoutMs=25000  → job（含 url）
GET  /api/export/pptx/active?projectId=...
POST /api/export/editable-pptx   （"可编辑 PPTX"路径，本次未执行）
```
