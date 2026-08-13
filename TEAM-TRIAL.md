# Research Group Trial Guide / 课题组试用指南

## 1. Install / 安装

Recommended Codex plugin installation:

```powershell
codex plugin marketplace add CeobeFA333/codex-scientific-diagram-visio --ref v1.2.0
codex plugin add codex-scientific-diagram-visio@ceobefa-scientific-tools
```

Restart the Codex or ChatGPT desktop app and begin a new thread after installation.

推荐使用以上 Codex Plugin 安装方式。安装后重启 Codex 或 ChatGPT 桌面端，并新建对话进行测试。

If Marketplace installation is unavailable, install either skill directly:

```text
$skill-installer install https://github.com/CeobeFA333/codex-scientific-diagram-visio/tree/v1.2.0/skills/scientific-model-diagram-prompting
$skill-installer install https://github.com/CeobeFA333/codex-scientific-diagram-visio/tree/v1.2.0/skills/scientific-model-diagram-visio
```

## 2. Prerequisites / 环境要求

- Codex with Skills or Plugins support.
- Windows and Microsoft Visio for native VSDX construction.
- A dedicated work directory for source files, backups, screenshots, and exports.
- A paper, model code/configuration, existing figure, or verified architecture description.

原生 Visio 绘制需要 Windows 与 Microsoft Visio。请使用单独工作目录，不要直接覆盖唯一的 VSDX 原文件。

## 3. Suggested trial / 建议测试流程

Start with the evidence and prompting skill:

```text
Use $scientific-model-diagram-prompting to compare my model code,
configuration, manuscript description, and current architecture figure.
Return a model contract, tensor-dimension audit, conflicts, and a
publication-ready reconstruction specification. Do not draw until
material contradictions are resolved.
```

Then build or revise the Visio figure:

```text
Use $scientific-model-diagram-visio to create an editable VSDX from the
verified contract. Keep repeated branches horizontal and evenly spaced,
use independent operators and glued connectors, prevent all overlaps,
and export PDF plus a 300-DPI PNG after reopen/editability QA.
```

中文提示词：

```text
使用 $scientific-model-diagram-prompting 对照读取我的模型代码、配置、
论文方法描述和现有模型图，输出模型契约、逐层维度核验、冲突清单和
可执行的 Visio 重建规范。存在影响架构的矛盾时先停止绘图并报告。
```

```text
使用 $scientific-model-diagram-visio 根据已核验契约生成原生可编辑 VSDX。
重复分支必须水平、等距；运算符独立；连接线粘合且不穿过文字或模块；
不得有任何重叠。保存后重新打开测试可编辑性，并导出 PDF 与 300 DPI PNG。
```

## 4. What to report / 反馈内容

Open a GitHub issue and include only non-confidential information:

- operating system, Codex surface, and Visio version;
- model family and input artifact types;
- whether architecture/dimension conflicts were found correctly;
- whether the VSDX remained independently editable after reopening;
- any overlap, bent-line, font, export, or installation problem;
- a redacted screenshot when useful.

请勿在公开 Issue 中上传未发表论文、私有代码、数据集、模型权重、个人路径或密钥。

Issues: https://github.com/CeobeFA333/codex-scientific-diagram-visio/issues
