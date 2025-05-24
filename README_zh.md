[English](README.md) | 中文

# ABAQUS GUI 脚本执行 MCP 服务器

这是一个 MCP (模型上下文协议) 服务器，设计用于与一个 **已经运行的** Abaqus/CAE 图形用户界面 (GUI) 进行交互。它允许在 Abaqus 环境中执行 Python 脚本，并通过 MCP 工具从 Abaqus 消息日志/区域检索消息。

此服务器使用 GUI 自动化技术 (`pywinauto`) 来控制 Abaqus/CAE 应用程序。

## 功能特性

- **GUI 内脚本执行**：通过自动化活动 Abaqus/CAE 会话中的 "File -> Run Script..." (文件 -> 运行脚本...) 菜单来执行 Python 脚本。
- **消息日志检索**：尝试从 Abaqus/CAE 消息/日志显示区域抓取文本内容。
- **MCP 接口**：将功能公开为标准的 MCP 工具和提示，以便与 LLM 代理和其他 MCP 兼容客户端轻松集成。
- **操作现有 GUI**：不启动或停止 Abaqus/CAE；它要求 Abaqus/CAE 会话已经打开并正在运行。

## 系统要求

-   **操作系统**：Windows (由于 `pywinauto` 和 Abaqus GUI 交互的需要)。
-   **Python 版本**：Python 3.7+。
-   **Abaqus/CAE**: 必须安装兼容版本的 Abaqus/CAE，并且在使用此服务器时，其 **GUI 必须已经打开并正在运行**。

## Python 依赖

使用 pip 安装所需的 Python 包：

```bash
pip install -r requirements.txt
```

(请参阅 `requirements.txt` 文件获取依赖列表，主要包括 `mcp[cli]`、`pywinauto`、`pygetwindow`、`psutil`、`pywin32`。)

## 配置要求

1.  **确保 Abaqus/CAE 正在运行**：在启动此 MCP 服务器之前，请确保 Abaqus/CAE 应用程序已在您的桌面上打开，GUI 已加载且响应正常。
2.  **可访问性**：确保在服务器尝试与 Abaqus/CAE 界面交互时，没有其他模态对话框阻塞界面。

## 使用方法

### 启动 MCP 服务器

导航到服务器所在目录并运行：

```bash
python mcp_server.py
```

服务器将启动并准备好接受 MCP 请求。

### MCP 工具说明

1.  **`execute_script_in_abaqus_gui`**
    *   **描述**：在活动的 Abaqus/CAE GUI 会话中执行给定的 Python 代码字符串。它会自动执行 'File -> Run Script...' (文件 -> 运行脚本...) 菜单流程。
    *   **参数**：
        *   `python_code (str)`：要执行的 Python 脚本内容 (Abaqus 脚本接口命令)。
    *   **返回值**：`str` -  一个消息，指示脚本 *提交* 尝试的结果 (例如，"Script submitted for execution...")。
    *   **重要提示**：此工具 **不会** 返回脚本在 Abaqus内部执行的直接输出或错误消息。要查看脚本的实际结果，您必须在脚本运行一段时间后使用 `get_abaqus_gui_message_log` 工具。

2.  **`get_abaqus_gui_message_log`**
    *   **描述**：尝试从 Abaqus/CAE 消息/日志区域 (通常位于主 GUI 窗口的底部) 检索文本内容。
    *   **参数**：无。
    *   **返回值**：`str` -  从消息区域提取的文本；如果检索失败，则返回错误/状态消息。
    *   **注意**：此工具的可靠性取决于能否准确识别消息区域的 UI 元素。当前实现使用启发式方法。要在特定的 Abaqus 环境中稳健运行，您可能需要使用检查工具 (参见开发/故障排除部分) 获取特定的 UI 元素标识符 (例如 AutomationId, Name, ClassName)，并更新服务器代码。

### MCP 提示说明

1.  **`abaqus_scripting_strategy`**
    *   **描述**：此提示提供了关于如何最佳地组合使用服务器工具 (`execute_script_in_abaqus_gui` 和 `get_abaqus_gui_message_log`) 的全面指南。它解释了脚本执行和结果验证的工作流程、工具的假设以及故障排除技巧。强烈建议 LLM 代理在使用工具前查阅此提示。

## 重要注意事项和限制

-   **需要运行中的 Abaqus GUI**：此服务器 *仅* 与一个已经打开并且其 GUI 处于活动和响应状态的 Abaqus/CAE 会话进行交互。它不能自行启动或管理 Abaqus 应用程序。
-   **GUI 自动化的敏感性**：GUI 自动化可能对 Abaqus 版本、屏幕分辨率、窗口主题以及微小的 UI 布局更改敏感。虽然 `pywinauto` 提供了一定程度的抽象，但仍可能出现问题。
-   **焦点和窗口状态**：理想情况下，Abaqus 窗口应该是活动的、非最小化的窗口，以便进行最可靠的交互，尽管服务器会尝试管理焦点。
-   **模态对话框**：Abaqus 中意外的模态对话框 (例如保存提醒、警告) 可能会阻塞自动化工具。
-   **错误报告区分**：请区分 MCP 工具返回的错误 (例如，"Abaqus window not found") 和 Abaqus 消息日志中报告的错误 (这些错误源于您在 Abaqus 内部运行的脚本)。

## 开发 / 故障排除

-   **检查 UI 元素**：如果 `get_abaqus_gui_message_log` 工具无法准确检索消息，或者 `execute_script_in_abaqus_gui` 在处理 "Run Script" (运行脚本) 对话框时遇到问题，您可能需要使用 UI 检查工具 (例如 `pywinauto.inspect` 模块的 `InspectDialog` 或 `py_inspect.py` 脚本，对于 UIA 后端可使用 FlaUInspect) 来识别您 Abaqus 版本中目标 UI 元素的正确属性 (AutomationId, Name, ClassName, ControlType)。然后，可以使用这些属性来优化 `mcp_server.py` 中的搜索逻辑。
-   **超时设置**：服务器包含一些 `time.sleep()` 调用，并使用 `pywinauto` 的 `Timings.slow()` 来更好地处理 Abaqus 可能较慢的 UI 响应时间。在某些环境中，这些设置可能需要调整。

## 项目结构

```
abaqus-mcp-gui-server/
├── mcp_server.py         # MCP 服务器主脚本
├── requirements.txt      # Python 依赖项
└── README.md             # 本文档文件
└── README_zh.md          # 中文版文档文件 (此文件)
```

## 许可证

本项目旨在用于学习、研究和特定的自动化任务。使用 Abaqus 软件时，请始终遵守 Dassault Systèmes 提供的许可条款。 