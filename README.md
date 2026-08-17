# 博士毕业论文 LaTeX 仓库 (Doctoral Thesis LaTeX Repository)

本仓库包含了我的博士毕业论文的完整 LaTeX 源代码、参考文献、图片资源以及相关配置文件。

为了方便后续的维护、修改以及利用 AI 辅助生成或审阅内容，特编写此说明文档。

## 1. 一级文件夹与核心文件说明

### 核心 LaTeX 文件

root.tex: 论文的主干文件（入口文件）。包含文档类的定义，并通过 \input 或 \include 导入 header.tex 以及各个章节文件。通常不需要修改此文件，除非需要调整章节顺序或添加新章节。

header.tex: 导言区文件。包含了所有的宏包导入（\usepackage）、页面布局设置、自定义命令以及格式定义。

Chapter1.tex ~ Chapter7.tex: 论文的正文核心内容，按章节划分。

thanks.tex: 致谢部分。

References.bib: BibTeX 格式的参考文献数据库。

### 核心文件夹

fig/: 编译专用图片库。存放所有在 .tex 源码中通过 \includegraphics 调用的最终版图片（格式多为 .png, .jpg, .eps, .pdf）。内部按章节（如 chp1, chp2 等）进行了分类管理。

fig/origin/: 图片原始工程文件库。存放图片的源文件（如 Visio 的 .vsdx, SVG .svg, 原始照片或作图数据等）。如果需要对论文中的图表进行根本性的修改或重新导出，请在此文件夹中寻找源文件。

OLD_Chapter/ & OLD_References.bib: 历史版本备份。存放修改前或废弃的章节代码和参考文献，仅作归档和参考用。

### 配置文件与样式包

latexmkrc: latexmk 工具的自动化编译配置文件。

*.sty (boites.sty, booktabs.sty, cite.sty, jlisting.sty, pageno.sty): 论文所依赖的本地或自定义 LaTeX 样式包文件。

# 2. 利用 AI 生成或修改内容时的操作指南

当您使用 ChatGPT, Claude, Gemini 等 AI 助手来辅助撰写、润色或修改论文内容时，请遵循以下最佳实践：

单文件操作（化整为零）：

不要把整个 root.tex 或所有章节一次性发给 AI。

每次只专注于一个文件（例如只发送 Chapter3.tex 的某一个小节）。明确告诉 AI：“这是我论文第 3 章的某一部分，请帮我润色/扩写/翻译”。

提供上下文（Context）：

如果需要 AI 帮你添加文献引用，请同时将 References.bib 中相关的条目提供给 AI，并要求其使用 \cite{xxx} 格式插入。

如果涉及到特定的专业术语或格式，可以在提示词（Prompt）中附上 header.tex 中的自定义命令，要求 AI 严格遵守。

明确格式要求：

在提示词中强调：“请仅输出 LaTeX 代码，保持原有的环境标签（如 \section, \begin{itemize} 等）不变，不要随意更改已有的图片引用和交叉引用标签（\label 和 \ref）。”

## 3. 指导 AI 读取仓库内容与寻找文件的指南（AI 视角）

如果您正在使用具备“读取整个代码仓库”能力的 AI Agent（例如 Cursor, GitHub Copilot Workspace, 或向 AI 提供完整目录树），请让 AI 遵循以下逻辑来理解项目和寻找资源：

### 读取顺序的逻辑 (How to parse the project)

第一步：读取 root.tex。AI 必须首先解析此文件，以了解整个文档的组织架构、章节加载顺序。

第二步：读取 header.tex。AI 需解析此文件以掌握文档的宏包依赖、特殊格式以及用户自定义的 LaTeX 命令。

第三步：读取对应的 ChapterX.tex。根据用户的具体指令，精准定位到对应的章节源码进行深度阅读或修改。

### 寻找图片资源的逻辑 (How to find images)

由于 LaTeX 的排版特性，图片管理有特定的映射关系。AI 在处理图片相关需求时应遵循以下规则：

追踪图片路径：在 ChapterX.tex 中，如果遇到 \begin{figure} 环境内的 \includegraphics[width=...]{<filepath>}，AI 应当提取 <filepath>（例如 fig/chp2/Pouring.png）。

定位最终展示图：提取路径后，AI 应直接前往仓库根目录下的 fig/ 文件夹，按照对应的子目录寻找该图片文件，以理解论文中实际插入的视觉内容。

寻找可编辑源文件：如果用户要求“修改图 X 的结构/文字/颜色”，AI 需要意识到 fig/ 下的文件（如 .png, .eps）通常是导出的栅格或扁平化文件。AI 应当前往 fig/origin/ 及其相应的子目录中，寻找同名的源文件（如 .svg, .vsdx 等）来指导用户如何进行矢量或底层修改。

注：本 README 专为规范本博士论文 LaTeX 工程库的维护与 AI 协作流程而定。