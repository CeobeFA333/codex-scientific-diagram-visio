# Codex 科研模型图 Visio 工作流

<p align="right">
  <a href="README.md">English</a> | <strong>简体中文</strong>
</p>

将模型代码、论文方法描述和旧架构图转换为适合论文发表的 Microsoft Visio 原生可编辑模型图。

核心流程：

```text
提示词 + 实验代码 + 论文 + 旧图
                ↓
证据核验与张量维度契约
                ↓
Codex 生图生成视觉参考（可选）
                ↓
Microsoft Visio 原生矢量重建或局部修改
                ↓
重新打开、可编辑性验收和导出检查
                ↓
VSDX + PDF + 300 DPI PNG
```

生成图片只用于布局和风格探索，不覆盖代码与公式确定的实际模型。

## 完整工作流动图

下面是真实 Microsoft Visio 窗口录制式演示：Codex 先读取并冻结 Transformer Encoder 模型契约，再用生图生成风格参考，随后以 Visio 原生形状逐步重建，保存并重新打开 VSDX，最后选择独立模块和已粘合连接线验证可编辑性。

![从论文和代码到可编辑 Visio 的完整流程](examples/transformer-encoder-demo/assets/workflow-demo.gif)

[查看可复现示例](examples/transformer-encoder-demo/) · [下载可编辑 VSDX](examples/transformer-encoder-demo/assets/transformer-encoder-demo.vsdx) · [查看 PDF](examples/transformer-encoder-demo/assets/transformer-encoder-demo.pdf)

[模型与额度示例](examples/transformer-encoder-demo/COST-EXAMPLE.md)：在文档假设下，使用 `gpt-5.6-terra`、生成 1 张中等质量 `gpt-image-2` 参考图，再由本机 Visio 绘制，API 等价成本约为 **0.32 美元**。ChatGPT/Codex 套餐消息额度不等于固定的 token 换算比例。

## 两个技能

### `scientific-model-diagram-prompting`

- 读取模型代码、训练配置、论文、截图和旧图。
- 核对流程、公式、投影方向、融合方式、维度与类别数。
- 生成科研模型图设计提示词和视觉参考图。
- 输出 Visio 原生重建所需的结构化规范。

### `scientific-model-diagram-visio`

- 使用 Microsoft Visio 完整重建或局部修改 VSDX。
- 使用原生可编辑容器、3D 方块、运算符、标签和连接线。
- 保持平行分支水平、等距，避免文字、形状和连接线重叠。
- 保存后关闭并重新打开，测试方块、符号、标签和连接线是否可独立编辑。
- 导出 PDF 与至少 300 DPI PNG，并检查裁切、字体和阴影。

## 安装

推荐通过本仓库的版本化 Marketplace 安装 Codex Plugin：

```powershell
codex plugin marketplace add CeobeFA333/codex-scientific-diagram-visio --ref v1.2.0
codex plugin add codex-scientific-diagram-visio@ceobefa-scientific-tools
```

安装后重启 Codex 或 ChatGPT 桌面端，并新建对话。课题组试用时，可直接分享[中英双语试用指南](TEAM-TRIAL.md)，或 Release 中的 `team-trial` 压缩包。

也可以使用 Agent Skills 方式安装：

通过开放 Agent Skills CLI 安装：

```bash
npx skills add CeobeFA333/codex-scientific-diagram-visio
```

也可以在 Codex 中分别从 GitHub 安装两个技能：

```text
$skill-installer install https://github.com/CeobeFA333/codex-scientific-diagram-visio/tree/main/skills/scientific-model-diagram-prompting

$skill-installer install https://github.com/CeobeFA333/codex-scientific-diagram-visio/tree/main/skills/scientific-model-diagram-visio
```

## 适用场景

- 根据 PyTorch/TensorFlow 代码重建论文模型图。
- 检查论文描述和实际训练模型是否一致。
- 将生图得到的参考图转换为原生可编辑 Visio。
- 修改现有 VSDX 中某个阶段、维度、公式、字体或连接线。
- 检查多页、嵌入位图、原生形状、分组和连接记录。

## v1 支持范围

- 模型证据核验和设计提示词可以跨平台使用。
- 原生 VSDX 构建需要 Windows 和 Microsoft Visio。

## 安全边界

技能可能要求 Agent 读取用户指定的论文和代码、控制 Visio，并在指定工作目录中保存文件。它不会要求上传论文、源代码、密码或令牌。运行公开第三方 Skill 前仍应阅读其内容和脚本。

许可证：MIT。
