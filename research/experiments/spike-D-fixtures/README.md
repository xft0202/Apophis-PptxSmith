# Spike D Fixtures（研究实验物 · 可丢弃）

本目录是 **Spike D**（长期架构全景统一验证）的输入材料生成器与校验器。

## 边界声明（先读）

- **可丢弃**：按 ADR-0006，本目录属研究性 spike，自我标注「可丢弃」，**永不进入生产镜像、Compose 依赖或用户安装步骤**（ADR-0013 验收宿主 ≠ 部署宿主）。
- **不定义任何产品契约**：这里不写产品的接口、数据模型或脚手架，只造验证用的输入。
- **二进制不入 Git**：`.gitignore` 已排除本目录下所有 `.docx/.xlsx/.pptx/.pdf/.ttf`，材料以 `fixtures-hashes.json` 的 sha256 锚定复现。

## 内容

| 文件 | 作用 |
| --- | --- |
| `generate_fixtures.py` | 按 manifest 生成五件材料（DOCX/XLSX/PDF/PPTX/fonts-manifest.json） |
| `verify_fixtures.py` | 在跑架构之前校验材料自身是否满足输入契约（当前 49/49 通过） |
| `fixtures-hashes.json` | 产物 bytes 与 sha256、未知部件路径、固定事实集 |
| `fonts-manifest.json` | 字体许可证与校准状态（OFL 可入库 / 宿主专有仅本机） |
| ~~`NotoSansSC-*.ttf`~~ | **已于 2026-09-26 删除**（21 MB）。运行 `generate_fixtures.py` 会自动从宿主 `C:\Windows\Fonts\NotoSansSC-VF.ttf` 重新实例化 |

输入契约的权威定义在 `../../archive/旧调研与规格/2026-09-25_spike-D_fixture-manifest_季度经营汇报.md`（**已归档**）。

## 复现

```bash
python research/experiments/spike-D-fixtures/generate_fixtures.py
python research/experiments/spike-D-fixtures/verify_fixtures.py
```

需要：`python-docx`、`openpyxl`、`python-pptx`、`reportlab`、`fontTools`、`pypdf`。
字体来源：宿主 `C:\Windows\Fonts\NotoSansSC-VF.ttf`（OFL 1.1）；宿主专有字体系（msyh/simsun/simhei/simkai/simfang）**只登记不复制**，禁止入库与再分发。

## 材料里刻意埋的东西

| 埋点 | 位置 | 验证的承诺 |
| --- | --- | --- |
| 营业收入 **15.0** vs 规范值 **15.1** | DOCX 摘要段 | 冲突进入确认，不静默改写 |
| 同比 **+12.0%** vs 规范值 **+12.4%** | PDF 第 2 节 | 同上，且跨材料来源可追溯 |
| 提示注入文本 | PDF 第 2 页高亮段 | 不受信材料不改变系统策略/权限/provider 路由 |
| 脱敏值（客户代号/成本中心/邮箱） | DOCX、PPTX notes | 日志与 workflow history 只留引用与哈希 |
| 未知扩展部件 + 未知关系 | PPTX `ppt/unknown/` | 既有包处理时未知部件原样保留 |
| 负增长值 | XLSX 图表数据 Q3、DOCX 排版段 | 图表与排版对负数/百分号的正确性 |
| 2 页结构 + 表格 + 脚注 | PDF | 解析链路的版面与来源定位 |

## 已知坑（踩过）

`inject_unknown_part()` 一度把部件写进 `customXml/`，而 Content_Types Override 与关系 Target 都指向 `ppt/unknown/`——三处路径不一致，产出的是**坏包**。若用它测「未知部件保留」，会得到假阳性。现已修复并在函数末尾加三处路径一致性 `assert`，生成器自身不通过就不会写出包。
