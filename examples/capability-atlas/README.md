# Scientific Figure Capability Atlas

本模块用仓库现有的 `reconstruct-paper-figures` 构建器，在本机确定性生成 8 张可编辑 SVG 分类图谱，集中展示 64 个科研图型家族。

## 概述

图谱把主页中的“支持范围”变成可以检查的产物。每个细分图型都有语义 ID、实时文字和可拆分矢量对象；清单记录配方与 SVG 的 SHA-256、对象计数和零栅格检查结果。

这些是合成的能力演示，用来证明对象体系和构建链路覆盖范围；它们不是 64 篇真实论文的逐像素复刻，也不替代源数据、标定信息或人工科学审核。

## 特性

- **8 大领域分类**：AI、统计、临床、细胞/组学、化学/材料、工程物理、实验系统和地理空间。
- **64 个复杂细分图型**：每类 8 个卡片式矢量示例，包含图例、标尺、参数、统计或边界条件，完整清单见 [`capability-manifest.json`](capability-manifest.json)。
- **真实 skill 链路**：JSON 配方交给 `skills/reconstruct-paper-figures/scripts/build_hybrid_svg.py` 生成 SVG。
- **可编辑性证据**：每张图包含 8 个语义卡片分组、实时文字、稳定对象 ID，并要求 0 个栅格节点。
- **逐图消耗规划**：每个细分图下方标注 S/M/L 或条件档位、预计 Agent token 区间和可选视觉参考生图次数。
- **可复现**：使用固定布局和配色，重复生成后可通过哈希发现任何输出变化。

### 消耗标注说明

| 档位 | 规划范围 | 适用情况 |
|---|---|---|
| S | 15–35k token，0–1 次可选生图 | 单面板、主要为矢量、证据核对较少 |
| M | 35–75k token，0–2 次可选生图 | 多层面板、需要源文件检查和一次编辑器 QA |
| L | 75–150k token，1–4 次可选生图 | 密集或含科学像素、需要科学复核与往返验收 |
| S/M、M/L | 跨两个档位 | 简单示意取低档；真实数据、多图层或高保真任务升级到高档 |

这些区间是实际重建任务的规划预算，不是模型或平台计费报价。源文件质量、数据清洗、字体、目标编辑器、人工校验与返工都会改变消耗。目录内图谱生成本身为本地确定性渲染，默认不消耗模型调用。

## 使用方法

在仓库根目录运行：

```powershell
python examples/capability-atlas/scripts/generate_capability_atlas.py --force
```

生成后可打开 [`gallery.html`](gallery.html)，或直接查看 [`assets/`](assets/) 中的 8 张 SVG。SVG 可导入 Illustrator、Inkscape、Figma 等支持 SVG 的编辑器；不同编辑器的字体与分组兼容性仍需各自验收。

## 目录结构

```
capability-atlas/
├── assets/                 # 8 张生成的可编辑 SVG
├── recipes/                # 8 份重建配方
├── scripts/                # 确定性生成器
├── source/blank.png        # 零栅格构建所需的空白画布
├── src/                    # 分类目录与图元库
├── capability-manifest.json
└── gallery.html
```

## 相关文档

- [设计文档](DESIGN.md)
- [能力与证据清单](capability-manifest.json)
