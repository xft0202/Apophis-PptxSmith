# Presenton 固定版本实际验证记录

日期：**2026-09-29**。阶段：立项前研究。范围：在明确授权下，于当前 Linux 本机隔离目录验证固定 Presenton 提交；只使用公开／合成材料；模型调用仅允许走 `https://www.apophis.uk`；不登录外部产品、不付费、不使用其他模型服务、不修改主工作区。本记录不是采用批准、产品验收或完整 benchmark。

## 一、授权与固定对象

- 运行对象：Presenton 根提交 `f9d3eba1a25712e25766b35a7af3b25f93ec1c01`。
- 导出依赖：发布包 `v1.0.34`，由固定根提交的 production 构建带入；此前已核对资产 SHA-256 `17c5aef592721d996a4f658de03282764d0ba900ab01beb7ca10a0404d595079`。
- 模型：按后续确认改为中转站上的 `glm-5.3`；没有使用 `glm-5.3-flash`、本地 Ollama 或其他供应商。
- 凭据：临时从当前 Pi 已配置的中转凭据注入隔离进程；未写入主仓库、报告、命令输出或持久化配置，验证结束后不保留测试容器。
- 容器配置：`DISABLE_IMAGE_GENERATION=true`、`MEM0_ENABLED=false`、`START_OLLAMA=false`，避免图像、记忆或本地模型路径偷偷引入其他服务；直接导出复核使用 Docker `--network none`。

## 二、Smoke 结果

### 通过项

1. 在 `/tmp` 隔离目录按固定提交取得源码，Git 工作树干净，提交哈希与目标一致。
2. 根级 `npm ci --ignore-scripts --no-audit --no-fund` 通过；`npm test` 通过，结果为 **7 tests passed, 0 failed**。这只是根级模板／包元数据测试，不是完整应用测试。
3. Docker production 镜像最终构建成功并生成约 **1.53 GB** 镜像；构建命令本身在 900 秒工具窗口超时，不能写成构建过程在窗口内干净完成。之后使用已生成镜像启动成功。
4. production 容器在本机 `127.0.0.1:55123` 返回 HTTP 200；Nginx、Next.js 和 FastAPI 日志均出现 ready／started 信号。
5. 测试容器、测试网络已停止并删除；没有留下该测试项目的运行容器，也没有触碰其他 Docker 项目。

### 环境边界

固定提交 README 的 Electron 路径要求 Node、Python 3.11 和 `uv`；本机有 Node 22.23.2、Python 3.12.3 和 Docker，但没有 `uv`、Ollama 或正在运行的本地模型。因此实际验证使用 production Docker 路径，不能把 Electron 开发路径在本机通过写入结论。

## 三、一次获准的 AI 生成尝试

请求使用固定 API 的 `slides_markdown`，内容为三页合成英文材料：一页标题、一页包含 Q1/Q2 数值表格、一页修改与交付观察事项；指令要求克制的业务报告布局、不添加外部事实或引用。图像生成已关闭。

结果：

- Presenton API 请求耗时约 **59.7 秒**，返回 **HTTP 500**。
- 日志显示请求已到达 `https://www.apophis.uk/v1/chat/completions` 并收到 **HTTP 200**。
- 固定运行时随后在 `llmai/openai/client.py::_generate_completions_stream` 解析流式结果时抛出 `JSONDecodeError: Extra data: line 3 column 1 (char 11)`，上层错误为 `LLMError: 500: Extra data...`。
- 错误发生在 `generate_presentation_structure`，没有得到可继续修改和交付的生成演示文稿；数据库中也没有留下成功的 presentation 记录。

这证明：**当前固定 Presenton 版本与本次 `glm-5.3` 中转响应之间，至少存在一个未解决的流式响应解析兼容性问题。** 现有证据不能进一步断言问题一定来自中转站响应格式、Presenton 固定依赖或两者组合；也不能把中转站 HTTP 200 当作生成成功。

### 代码协议排查（不新增模型请求）

随后只做了本地／公开代码核查，没有再次调用模型、没有修改 Presenton 或依赖：

- 固定提交的 `servers/fastapi/uv.lock` 锁定 `llmai==0.3.15` 和 `openai==2.32.0`；前者的公开 wheel SHA-256 为 `7a9305f5c61b63f9f7e1718aaf21df1369249f7142f49376bd1de8da6808fe16`。
- `llmai` 的 completions 路径调用 OpenAI Chat Completions，使用 `stream=True` 和 `stream_options={"include_usage": True}`，然后按事件读取 `choices[0].delta`。
- 本次异常发生在流式响应被 SDK 迭代／解码的阶段，早于 Presenton 的 `generate_presentation_structure` 内容处理；`JSONDecodeError: Extra data` 与“一个 SSE 事件中混入多个 JSON／返回 NDJSON 而非单 JSON SSE 事件”等格式不匹配假设相符，但由于没有保存原始响应体，**这仍是强假设，不是已证根因**。
- 当前 Pi 配置中的 `deepseek-v4.1-flash` 与 `glm-5.3` 都是 OpenAI-compatible completions 类，适合做同一入口下的后续比较；`gpt-6-sol` 是 Responses 类，不能直接假定适配 Presenton 要求的 `/v1/chat/completions`，需要另行确认 relay 路由或适配代码。

本次只执行了一次获准的生成尝试，没有重试、切换模型、切换端点或扩大调用次数。因此 R1/R2 的材料组织与 AI 生成效果仍是未验证，不记录为失败率或 benchmark 数字。

## 四、DeepSeek 对照生成结果

在完成代码协议排查后，按所有者授权重新准备同一固定提交和 production 容器。第一次本地生成 API 探测因容器 FastAPI 尚未就绪返回 HTTP 428 `Login setup is required`，没有触达模型；等待认证路由就绪后，得到本地授权并使用临时合成管理员完成 setup/login。该本地账户、cookie 和运行配置仅存在于隔离目录，随后清理。

随后执行了**唯一一次** `deepseek-v4.1-flash` 三页合成材料完整生成：

- 本地 `POST /api/v1/ppt/presentation/generate` 返回 **HTTP 500**，耗时约 **13.4 秒**，错误体为 `Expecting value: line 1 column 1 (char 0)`。
- 服务日志确认至少有 **3 次** `POST https://www.apophis.uk/v1/chat/completions`，均收到 **HTTP 200**；这是一次 Presenton 生成工作流内部的调用，不是代理重试或本代理新增的第二次完整生成。
- 日志先出现 `Generated 3 outlines for the presentation`，随后固定 `llmai/openai/client.py::_generate_completions_stream` 在 `_final_content` 对最终内容做 JSON 解码时抛 `JSONDecodeError: Expecting value`，上层 `generate_presentation_structure` 失败。
- 没有得到可继续修改、导出或交付的生成演示文稿；没有重试、没有换模型或端点。

因此，DeepSeek 这次证明了“认证和中转 HTTP 请求路径可到达”，但没有证明结构化生成兼容或生成质量通过。与 `glm-5.3` 的 `Extra data` 不同，本次错误落在固定运行时对最终内容的 JSON 解码阶段；两次都不能仅凭 HTTP 200 视为生成成功。测试容器、网络、镜像、临时源码和包含运行时配置的目录均已清理。

## 五、无模型的直接 JSON 导出结果

为单独观察 R5/R7，使用发布包 runner 的 `pptx-from-json` 入口，在无网络容器中提交合成的文字、表格和图表对象。第一份夹具误把像素坐标写成英寸级数值，导致文字逐字换行和图表区域过小；该夹具废弃，不把它归因于导出器。使用固定入口实际导出的修正版夹具采用 1280×720 像素级坐标。

修正版结果：

- `runner.mjs` 退出码 **0**，耗时约 **3 秒**。
- 输出 PPTX：2 页，文件大小 **14,559 bytes**，SHA-256：`fda039bd9825ca672cfa2c90ebcbfc0dd87747174eb853deac6a85f233c244a2`。
- PPTX ZIP 中有两个 slide XML、表格 XML、`ppt/charts/chart1.xml` 和 `ppt/embeddings/Microsoft_Excel_Chart1.xlsx`。
- 文字层包含标题、说明、`Signal`、`Q1`、`Q2`、`Successful runs`、`Manual fixes` 及数值 `120`、`156`、`22`、`15`。
- 图表 XML 中存在相同数值和图表关系；不能仅凭这些结构断言所有办公软件中的行为或数据编辑体验。
- LibreOffice 24.2 在本机将 PPTX 转为 2 页 PDF 和 PNG；人工查看渲染图时，第一页文字／表格可见，第二页柱状图、图例、坐标和数值标签可见，没有发现空白页或明显截断。该观察只代表本机 LibreOffice 渲染，不代表 PowerPoint、WPS 或其他软件一致。

这条结果支持：**固定导出包的直接 JSON 对象写出在本机可产出并可渲染的文字、表格和图表样例。** 它不支持以下结论：常规 URL／HTML 页面导出等价、应用内连续编辑已通过、外部 PPTX 可无损回流、所有图表类型均可编辑、交付质量已达标。

## 六、对当前路线判断的更新

- Presenton production 的本机启动与根级测试可行；这降低了“完全无法启动”的风险，但没有证明可运营或可维护。
- 当前 completions 类中转生成在固定版本上均未形成成功产物：`glm-5.3` 在流式解析阶段报 `Extra data`；`deepseek-v4.1-flash` 已实际到达中转站并收到 HTTP 200，但固定运行时在 `_final_content` 报 `Expecting value`。代码排查尚无原始响应体，不能认定中转站为唯一根因；两次均不应计为生成成功。`gpt-6-sol` 的 Responses 协议不能直接套用。运行验证已封口；任何兼容性修复或新的受控请求都需要另行授权，不属于当前主线。
- 直接 JSON 导出与结构／LibreOffice 渲染样例通过，强化了 R5/R7 的“存在一条可运行的结构化写出路径”判断；它不能回填 AI 生成失败，也不能替代常规页面导出、连续修改和交付后回改证据。
- R3 的真实应用内修改、R1/R2 的材料组织与 AI 生成、完整人工负担、失败恢复、长期维护和采用价值仍未闭合。
- 本轮结果不足以批准 B/C 二开或完整产品；下一决策点已转为：依据[下一阶段任务比较矩阵](2026-09-29_下一阶段任务比较矩阵.md)，判断现有作者环境／成熟 AI 演示工具基线与 B/C/D 是否存在任务级差异，或暂缓独立产品。

## 七、来源与可复核对象

- 固定源码：`presenton/presenton@f9d3eba1a25712e25766b35a7af3b25f93ec1c01`；`servers/fastapi/uv.lock` 中记录的 `llmai`／`openai` 版本为上述代码排查依据。
- 代码排查对象：PyPI `llmai==0.3.15` wheel；只下载并读取源文件，未运行其网络客户端。
- 固定发布包：`presenton-export@v1.0.34`；包入口 `/app/presentation-export/runner.mjs`，导出包 `@presenton/export-core`。
- 本地隔离目录：`/tmp/presenton-pptxsmith-verify-20260928`。测试容器和网络已删除；临时源码、镜像和产物未写入主仓库。
- 本记录中的 smoke、生成错误、PPTX ZIP 检查和 LibreOffice 渲染均为本轮实际观察；没有把静态代码、文件存在或中转 HTTP 200 写成端到端成功。
