# Codex 科研图重建与 Visio 工作流

<p align="right">
  <a href="README.md">English</a> | <strong>简体中文</strong>
</p>

一组“先核验科学证据、再绘制”的 Codex 工作流：把模型代码、论文文字、PDF、源数据和旧图转成可编辑科研图。

[正式版 v1.3.2](https://github.com/CeobeFA333/codex-scientific-diagram-visio/releases/tag/v1.3.2) · [MIT 许可证](LICENSE) · [课题组试用指南](TEAM-TRIAL.md)

> 绘图前先核对科学事实，导出后再证明可编辑性；不能让视觉美化悄悄改变研究方法。

## 最终会得到什么

这不是一个不断膨胀、每次都加载全部上下文的巨型 Skill，而是一个包含 **3 个专注 Skill** 的插件。Codex 会按任务匹配需要的能力。

| 工作流 | 常见输入 | 交付物 |
|---|---|---|
| 核验并设计模型图 | 模型代码、配置、公式、论文文字、旧图 | 证据表、冲突清单、张量/模型契约、视觉参考提示词、可执行的矢量重建规范 |
| 新建或局部修改 Visio | 已核验契约、参考图或现有 VSDX | 原生可编辑 VSDX、重开对象测试、PDF、300-DPI PNG、检查报告；修改任务另含版本化备份 |
| 重建论文图片 | 论文 PDF、提取素材、源数据、已复核 OCR、旧的栅格/矢量图 | 图片盘点、重建配方、可编辑 SVG、可选 AI/可编辑 PDF、原子科研像素证据、QA 报告和明确的发表阻断项 |

三个 Skill 分工如下：

- `scientific-model-diagram-prompting`：核对科学证据，形成绘图契约。
- `scientific-model-diagram-visio`：用 Microsoft Visio 原生对象新建、修改、重开并导出模型图。
- `reconstruct-paper-figures`：重建复杂论文图片，同时保留科研像素证据和源数据来源。

## 安装

推荐从本仓库的版本化 Marketplace 安装：

```powershell
codex plugin marketplace add CeobeFA333/codex-scientific-diagram-visio --ref v1.3.2
codex plugin add codex-scientific-diagram-visio@ceobefa-scientific-tools
```

安装后重启 Codex 或 ChatGPT 桌面端并新建任务。也可以通过开放 Agent Skills CLI 一次安装全部 Skill：

```bash
npx skills add CeobeFA333/codex-scientific-diagram-visio
```

单独安装某个 Skill 的地址和课题组分发方法见[试用指南](TEAM-TRIAL.md)。

## 选择工作流

### 1. 先核验再绘制

```text
使用 $scientific-model-diagram-prompting 对照检查我的模型代码、配置、
论文公式和现有图片。输出权威模型契约、张量维度核验、冲突清单和
可执行的重建规范。仍有影响架构的矛盾时先停止绘图。
```

### 2. 新建或局部修改可编辑 VSDX

```text
使用 $scientific-model-diagram-visio 把这份已核验契约重建为原生可编辑
VSDX。重复分支水平等距、运算符独立、连接线真实粘合。保存后重新打开，
测试对象可编辑性，再导出 PDF 和 300-DPI PNG。
```

### 3. 重建复杂论文图片

```text
使用 $reconstruct-paper-figures 盘点这篇 PDF，把指定图片重建成可编辑
SVG、Illustrator AI 和可编辑 PDF。连续色调科研图像只保留为最小的
哈希绑定原子，统计图绑定已提供源数据，未解决的复核项保留为发表阻断。
```

## 已验证演示

### 论文/代码到原生 Visio

这段 Microsoft Visio 实录展示了 Codex 读取已核验的 Transformer Encoder 契约、生成可选风格参考、使用原生形状构图、重开 VSDX，以及选中可独立编辑的对象。

![论文与代码到可编辑 Visio 的工作流](examples/transformer-encoder-demo/assets/workflow-demo.gif)

[复现实例](examples/transformer-encoder-demo/) · [下载 VSDX](examples/transformer-encoder-demo/assets/transformer-encoder-demo.vsdx) · [查看 PDF](examples/transformer-encoder-demo/assets/transformer-encoder-demo.pdf) · [查看消耗算例](examples/transformer-encoder-demo/COST-EXAMPLE.md)

文档中的 `gpt-5.6-terra` + 1 张中等尺寸 `gpt-image-2` 参考图 + 本地 Visio 场景，在其假设下约为 **0.32 美元 API 等效成本**。本地 Visio 自动化本身不消耗模型 token；订阅消息限额也不能固定换算成 token 或积分。

### 保留科研证据的论文图重建

下面的 v1.3.2 演示由仓库内的真实重建产物和机器审计数据组成，展示十面板混合生物图、可编辑统计图组、已复核 OCR 清理证据，以及 Illustrator 三阶段重开计数。它**不是**伪装成 Illustrator 录屏的动画。

![论文图片重建能力演示](examples/paper-figure-reconstruction-demo/assets/paper-figure-reconstruction-demo.gif)

[打开实例](examples/paper-figure-reconstruction-demo/) · [观看 MP4](examples/paper-figure-reconstruction-demo/assets/paper-figure-reconstruction-demo.mp4) · [查看证据 JSON](examples/paper-figure-reconstruction-demo/assets/simpli-figure4-evidence.json)

演示产物刻意保持 `publication_ready=false`：机器检查通过不等于源数据、比例尺和人工科学审核已经完成。

## 64 类可编辑能力图谱

仓库的真实配方构建器确定性生成了 **8 张全尺寸 SVG，共覆盖 64 个图型家族**。每张卡片都有语义 ID、实时文字、可拆分矢量对象、配方哈希、对象计数和真实任务消耗规划；清单要求 **0 个嵌入栅格节点**。这些是合成能力测试，不代表已经对 64 篇论文做了逐像素复刻。

点击下面的大图可打开原始 SVG，无损放大查看文字、路径和细节。

[![AI、机器学习与计算机视觉能力图谱](examples/capability-atlas/assets/ai-computer-vision.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/ai-computer-vision.svg)

<details>
<summary><strong>展开全部 8 个领域的全尺寸可点击图谱</strong></summary>

### AI / 机器学习 / 计算机视觉

[![AI 与计算机视觉图型](examples/capability-atlas/assets/ai-computer-vision.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/ai-computer-vision.svg)

### 统计学 / 数据科学

[![统计学与数据科学图型](examples/capability-atlas/assets/statistics-data-science.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/statistics-data-science.svg)

### 临床 / 生物医学

[![临床与生物医学图型](examples/capability-atlas/assets/clinical-biomedical.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/clinical-biomedical.svg)

### 细胞 / 分子 / 组学

[![细胞、分子与组学图型](examples/capability-atlas/assets/cell-molecular-omics.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/cell-molecular-omics.svg)

### 化学 / 材料 / 电化学

[![化学与材料图型](examples/capability-atlas/assets/chemistry-materials.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/chemistry-materials.svg)

### 工程 / 物理

[![工程与物理图型](examples/capability-atlas/assets/engineering-physics.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/engineering-physics.svg)

### 实验系统 / 微流控

[![实验系统与微流控图型](examples/capability-atlas/assets/experimental-systems.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/experimental-systems.svg)

### 地球科学 / 地理空间

[![地球科学与地理空间图型](examples/capability-atlas/assets/earth-geospatial.svg)](https://raw.githubusercontent.com/CeobeFA333/codex-scientific-diagram-visio/main/examples/capability-atlas/assets/earth-geospatial.svg)

</details>

[打开本地全宽画廊](examples/capability-atlas/gallery.html) · [阅读图谱说明](examples/capability-atlas/) · [检查 64 类清单与 SHA-256 证据](examples/capability-atlas/capability-manifest.json)

### 支持领域与细分图型

这里的“支持”是指工作流能够分类图型、选择保留证据的重建路径，并输出可编辑规范或产物。能否无损恢复仍取决于源矢量、源数据、标定信息和人工科学审核。

| 领域 | 图谱内的细分图型 |
|---|---|
| AI / 机器学习 / 计算机视觉 | 神经网络架构；编码器–解码器与 U-Net；特征图；残差路径；Q/K/V 注意力；多模态融合；检测框/类别/关键点；分割、深度与概率图 |
| 统计学 / 数据科学 | 折线/散点/拟合；误差棒与置信区间；柱状/箱线/小提琴/ROC；Kaplan–Meier/森林图/风险表；热图与矩阵；PCA/t-SNE；树状图/网络/系统发育；Circos 式环形图 |
| 临床 / 生物医学 | 队列与随机流程；森林图；流式细胞门；CT/MRI/PET/超声叠加；组织学；ROI/分割；风险表；研究时间线 |
| 细胞 / 分子 / 组学 | 荧光/共聚焦与多重成像；Western blot；电泳；基因组矩阵；系统发育；蛋白渲染；配体相互作用 |
| 化学 / 材料 / 电化学 | 化学结构；反应式；XRD/Raman/FTIR/XPS；质谱/色谱；DSC/TGA/DTA；CV/EIS/Nyquist；SEM/TEM/AFM；EDS 元素图 |
| 工程 / 物理 | 电路；控制系统；接线图；FEA；CFD；响应面；CAD 图；爆炸装配图与 BOM 标注 |
| 实验系统 / 微流控 | 实验装置；微流控通道；分层器件；传感链；设备照片面板；复合图；过程原理；测量布局 |
| 地球科学 / 地理空间 | GIS 地图；遥感；DEM/地形；地质图；地震图；剖面；经纬网/指北针/比例尺；制图图例 |

### 消耗标注

| 档位 | 真实任务规划范围 | 常见范围 |
|---|---|---|
| S | 15–35k Agent token；0–1 次可选视觉参考 | 单面板、主要为矢量、证据核对较少 |
| M | 35–75k；0–2 次参考 | 多层图片、需要源文件检查和一次编辑器 QA |
| L | 75–150k；1–4 次参考 | 密集或含科研图像，需要科学复核、编辑器往返和返工 |
| S/M 或 M/L | 横跨相邻档位 | 由真实数据、源文件质量、关联面板和验收要求决定 |

这些数字是规划区间，不是价格或用量保证。仓库内图谱由本地确定性 Python 生成，使用 **0 次模型/API 调用**。

## 可编辑对象与科研符号

工作流用明确的矢量图元和语义 ID 组合组件，不依赖封闭图标库。

<details>
<summary><strong>展开可绘制对象清单</strong></summary>

| 家族 | 可编辑组件 |
|---|---|
| 基础图元 | 矩形、椭圆、多边形、直线、折线、三次/圆弧路径、环形扇区、分组、渐变、直线/路径文字、上下标文本 |
| 流程与关系 | 直线/正交箭头、粘合连接线、分支、合并、残差/跳跃与反馈路径、引线、括号、ROI 框、虚线围框、结点 |
| 模型架构 | 3D 张量方块、编码器/解码器、投影/权重矩阵、偏置向量、注意力、归一化、卷积/池化、分类头、平行分支、多模态融合 |
| 数学 | 独立的 `×`、`+`、`Σ`、拼接 `‖`、等号、公式、矩阵、维度、希腊字母、prime、上下标 |
| 统计 | 坐标轴、刻度、网格、点、误差棒、置信区间、删失标记、拟合曲线、图例、显著性括号、p 值、均值/方差/偏度/峰度缩略图 |
| 矩阵、图与环形 | 热图、混淆/相关矩阵、树状图、网络、系统发育分支、同心环、扇区、环形文字、色标 |
| 图像/测量叠加 | 面板字母、通道名、比例尺、方向标记、ROI、分割边界、门、关键点、类别/置信度、峰与参考线 |
| 实验装置与工程 | 容器、管道/通道、电路线、仪器块、边界/载荷箭头、尺寸线、剖面标记、爆炸图引线、BOM 编号 |
| 化学与分子 | 化学键、环、立体楔形、反应箭头、条件/产率、残基/配体标签、虚线相互作用键 |
| 地图 | 边界、点、剖面线、经纬网、指北针、比例尺、图例、断层、震中 |

</details>

## 绘图工具、后端与验证范围

| 后端 | 当前能力 | 证据等级 |
|---|---|---|
| Microsoft Visio | 原生形状、分组和粘合连接线；VSDX 保存/重开；SVG/PDF/PNG 导出 | **原生运行时已验证**：Windows 桌面 Visio 16.0 |
| Adobe Illustrator | SVG 导入；AI 保存/重开；可编辑 PDF 导出/重开；对象、字体和路径审计；受限路径文字修复 | **往返已验证**：Windows + Illustrator 29.8.2 |
| SVG + 可编辑 PDF | 便携矢量/混合组装、实时文字、物理尺寸、哈希和结构审计 | **便携核心已实现**；仍需目标编辑器验收 |
| draw.io / diagrams.net | 把受支持的 SVG 子集转成含稳定 ID、图层、文字、连接线、清单和失败关闭审计的 `mxGraphModel` | **结构适配器已实现**；真实导入/保存/重开待验证 |
| Scientific Illustrator | 面向框架图的后端中立场景契约 | **集成契约已有文档**；未内置其运行时，也不宣称已验证 |
| PowerPoint / WPS | 可通过兼容的外部流程用作中间框架编辑器 | **没有直接控制器**；本项目不把它作为发表验收后端 |
| Inkscape / Figma / Affinity / CorelDRAW | 可以按各编辑器自身兼容性导入 SVG/PDF | **未自动化、未做回归测试** |
| ChemDraw/RDKit / PyMOL/ChimeraX / CAD/GIS | 化学、分子渲染、装配和地图的候选语义后端 | **规划中，尚未实现** |

## 证据恢复与验收模型

论文图按面板记录恢复等级：

| 等级 | 含义 |
|---|---|
| R0 | 恢复 PDF 原生文字/矢量几何 |
| R1 | 用权威源数据重新生成 |
| R2 | 近似数字化，并明确标记为近似结果 |
| R3 | 把不可改写的科研像素保留为最小哈希绑定原子 |

一张图可以混用多个等级。工作流把素材盘点、重建、编辑器往返、视觉 QA 和科学批准分开。缺失数据、标定、比例尺、字体或人工审核会继续显示为阻断项；机器审计不会自动授予“可发表”状态。

## 环境要求与项目边界

- Codex 支持 Agent Skills 或 Plugins。
- 便携脚本需要 Python 3.8+；PDF 盘点/渲染还需 Skill 文档列出的可选依赖。
- 原生 VSDX 构建和 GUI 验证需要 Windows + Microsoft Visio。
- Adobe Illustrator 为可选项，仅在执行当前已验证的 AI/可编辑 PDF 往返流程时需要。
- 生图为可选视觉参考，绝不能作为科学事实来源。

打包插件是本地、纯 Skill 方案：项目维护者不运行服务、不创建账户、不收集遥测。它只会按任务读取用户纳入范围的材料，并在相应流程中控制 Visio 或 Illustrator。不要把保密论文、数据、代码、凭据或模型权重上传到公开 Issue。

工程边界和发布历史见 [DESIGN.md](DESIGN.md)、[SECURITY.md](SECURITY.md)、[PRIVACY.md](PRIVACY.md)、[TERMS.md](TERMS.md) 与 [CHANGELOG.md](CHANGELOG.md)。

## 仓库结构

```text
skills/                                      Skill 权威源码
plugins/codex-scientific-diagram-visio/      与源码同步的 Marketplace 包
examples/transformer-encoder-demo/           可复现的原生 Visio 示例
examples/paper-figure-reconstruction-demo/   证据驱动的论文图重建演示
examples/capability-atlas/                    8 领域、64 类可编辑 SVG 图谱
scripts/validate_release.py                   发布与镜像一致性验证
tests/                                        标准库回归测试
```

## 版本与许可证

当前最新标签版为 **v1.3.2**。`main` 分支还包含归入 `Unreleased` 的确定性能力图谱和新版主页文档；代码发布不会自动改变任何图片的科学审核或发表状态。

源代码和项目原创材料使用 [MIT 许可证](LICENSE)。第三方演示图片继续遵循其示例目录中列出的许可证与署名要求。
