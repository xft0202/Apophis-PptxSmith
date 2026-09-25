# Spike E：PptxSmith A 级语义验收（研究实验物 · 可丢弃）

本目录验证本项目「铁三角」中可实测的部分：**A 级原生语义输出**与**中文渲染**，
并在唯一可用的验收宿主（WPS 演示 11.8.2.8411）上跑通完整闭环。

完整报告见 [`2026-09-25_spike-E_实测报告.md`](2026-09-25_spike-E_实测报告.md)。

## 为什么这里的二进制要入库

按 `.gitignore` 的分工，本项目实验产物分两类：

- **A 类（不入库）**：能由脚本一条命令确定性重建的，例如 `spike-D-fixtures/`
  的五件材料（`generate_fixtures.py` 有确定性测试保证）。
- **B 类（入库）**：**被报告直接引用为证据的**，删掉就无法复核结论。

本目录属 B 类。这些文件不是「碰巧生成的产物」，而是**验收结论的原始证据**：

| 文件 | 证明什么 |
| --- | --- |
| `sample_pptxsmith.pptx` | 生成侧的原始产物：含 `ppt/charts/chart1.xml` 与 `ppt/embeddings/*.xlsx` |
| `sample_pptxsmith_edited.pptx` | **WPS 实际编辑并另存后的**文件——证明改数据能持久 |
| `png/slide{1,2,3}.png` | WPS 导出的渲染结果：图表随数据更新（Q2 柱升至 88.8）、中文无溢出 |
| `wps-probe.json` | 17 项探针的原始结果记录 |
| `sample_pptxsmith.json` | 量字预测值与解包检查结果 |

删除它们，`17/17 通过` 这个结论就只能靠文字叙述，无法复核。

## 复现方式

```bash
# 1. 生成（用真实 Python，注意 PATH 可能被工具环境劫持）
E:\Python312\python.exe research/experiments/spike-E/build_sample.py

# 2. WPS 验收探针 —— 必须用 32 位宿主
C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe `
  -NoProfile -ExecutionPolicy Bypass `
  -File research/experiments/spike-E/probe_wps.ps1
```

## 两个必须知道的坑

1. **32 位宿主**：WPS 的 COM 自动化服务器注册在 `WoW6432Node`，64 位 PowerShell
   调用会静默失败。详见 [`docs/目标软件验收矩阵.md`](../../../docs/目标软件验收矩阵.md) 第 2.1 节。
2. **`probe_wps.ps1` 必须带 UTF-8 BOM**：PowerShell 5.1 读无 BOM 的 UTF-8 脚本会按
   GBK 解码，导致语法解析全面失败（报 `Unexpected token '}'`）。

## 边界声明

- 本目录属 ADR-0006 所说的「研究性 spike」，**可丢弃**，永不进入生产镜像、
  Compose 依赖或用户安装步骤（见 ADR-0013）。
- 不含任何产品脚手架：不定义接口、数据模型或运行时契约。
- Microsoft PowerPoint 一侧**未验证**（本机无正版 Office，ADR-0013 方案 A）。
