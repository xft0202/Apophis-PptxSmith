# 技术栈：TypeScript 全栈 + PptxGenJS + 自研 fontkit 量字

Status: accepted (2026-09-24，所有者授权委托决策)

产品形态对标 sandun.cc（对话式 agent Web 产品：需求调研→大纲策划→策划稿→设计稿的分阶段流水线），且长期开源。据此决定：**全栈 TypeScript 单语言**——Next.js Web 前端、Node agent 编排、PptxGenJS 编译原生 PPTX、基于 fontkit 自研中文量字引擎（方法与校准数据借鉴 MIT 的 cjk-pptx-engine）。**02/03 报告中的 Java 21 编排 + Apache POI 路线作废。**

## Considered Options

- Java 21 编排 + TS 工作进程（03 报告原案）：被否。本问题域生态资产（python-pptx 系、cjk-pptx-engine、PptxGenJS、fontkit）无一在 JVM；三语言栈对开源小团队是三倍复杂度，且 Java 无任何独有收益。
- Python-first（python-pptx 活跃 fork + 直接复用 cjk-pptx-engine）：被否。中文排版落地最快，但 Web/agent 产品形态的前后端生态重心在 TS；python-pptx 官方仓库维护停滞（最后发布 2024-08），fork 长期节奏不可控；图表类型天花板较低。
- SVG 为源格式（sandun.cc 路线）：被否为源格式。SVG 不携带图表数据语义，导出后图表不可改数据——与"原生语义可编辑"的差异化主轴冲突。SVG 只作预览渲染的副产品。

## Consequences

- cjk-pptx-engine 不作为运行时依赖；其价值是量字方法、PowerPoint 校准参数（微软雅黑 1.34×、宋黑楷仿宋 1.16×、等线 1.05×+5% 余量）与 audit 闸门设计，移植到 TS 后作为"量字引擎"内建。
- 语义对象模型是唯一事实源：Web 预览（HTML/SVG）、PPTX 编译、量字、审计全部由同一模型驱动，避免"SVG/网页即真相"导致的语义丢失。
- PptxGenJS 的已知 footguns（hex 颜色、combo 图双轴成对声明、stacked 图 dataLabelPosition、一文件一实例等）必须转为自动化回归用例。
- 中文验收仍以真实 PowerPoint/WPS 打开为准；LibreOffice 渲染仅作开发期近似 QA。
