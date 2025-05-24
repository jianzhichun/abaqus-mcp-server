English | [中文](README_zh.md)

# ABAQUS MCP Server for GUI Scripting

An MCP (Model Context Protocol) server designed to interact with an **already running** Abaqus/CAE Graphical User Interface (GUI). It allows for the execution of Python scripts within the Abaqus environment and retrieval of messages from the Abaqus message log/area, all through MCP tools.

This server uses GUI automation techniques (`pywinauto`) to control the Abaqus/CAE application.

## Features

- **Script Execution in GUI**: Executes Python scripts by automating the "File -> Run Script..." menu in an active Abaqus/CAE session.
- **Message Log Retrieval**: Attempts to scrape text content from the Abaqus/CAE message/log display area.
- **MCP Interface**: Exposes functionalities as standard MCP tools and prompts for easy integration with LLM agents and other MCP-compatible clients.
- **Operates on Existing GUI**: Does not start or stop Abaqus/CAE; it requires an Abaqus/CAE session to be already open and running.

## System Requirements

-   **Operating System**: Windows (due to `pywinauto` and Abaqus GUI interaction).
-   **Python**: Python 3.7+.
-   **Abaqus/CAE**: A compatible version of Abaqus/CAE must be installed and **already running with its GUI open** when using this server.

## Python Dependencies

Install the required Python packages using pip:

```bash
pip install -r requirements.txt
```

(See `requirements.txt` for the list of dependencies, primarily `mcp[cli]`, `pywinauto`, `pygetwindow`, `psutil`, `pywin32`.)

## Configuration

1.  **Ensure Abaqus/CAE is Running**: Before starting this MCP server, make sure the Abaqus/CAE application is open on your desktop, with the GUI loaded and responsive.
2.  **Accessibility**: Ensure no other modal dialogs are blocking the Abaqus/CAE interface when the server attempts to interact with it.

## Usage

### Starting the MCP Server

Navigate to the server's directory and run:

```bash
python mcp_server.py
```

The server will start and be ready to accept MCP requests.

### MCP Tools Provided

1.  **`execute_script_in_abaqus_gui`**
    *   **Description**: Executes a given Python code string within the active Abaqus/CAE GUI session. It automates the 'File -> Run Script...' menu process.
    *   **Argument**:
        *   `python_code (str)`: The Python script content (Abaqus Scripting Interface commands) to be executed.
    *   **Returns**: `str` - A message indicating the outcome of the script *submission* attempt (e.g., "Script submitted for execution...").
    *   **Important**: This tool **does not** return the direct output or error messages from the script's execution within Abaqus. To see the script's actual outcome, you must use the `get_abaqus_gui_message_log` tool after allowing time for the script to run.

2.  **`get_abaqus_gui_message_log`**
    *   **Description**: Attempts to retrieve the text content from the Abaqus/CAE message/log area (usually found at the bottom of the main GUI window).
    *   **Arguments**: None.
    *   **Returns**: `str` - The extracted text from the message area, or an error/status message if retrieval fails.
    *   **Note**: The reliability of this tool depends on accurately identifying the message area UI element. The current implementation uses heuristics. For robust operation in a specific Abaqus environment, you might need to update the server code with specific UI element identifiers (e.g., AutomationId, Name, ClassName) obtained using an inspect tool (see Development/Troubleshooting).

### MCP Prompts Provided

1.  **`abaqus_scripting_strategy`**
    *   **Description**: This prompt provides comprehensive guidance on how to best use the server's tools (`execute_script_in_abaqus_gui` and `get_abaqus_gui_message_log`) together effectively. It explains the workflow for script execution and result verification, tool assumptions, and troubleshooting tips. It is highly recommended that LLM agents consult this prompt before attempting to use the tools.

## Important Considerations & Limitations

-   **Requires Running Abaqus GUI**: This server *only* interacts with an Abaqus/CAE session that is already open and has its GUI active and responsive. It cannot start or manage the Abaqus application itself.
-   **GUI Automation Sensitivity**: GUI automation can be sensitive to the Abaqus version, screen resolution, window themes, and minor UI layout changes. While `pywinauto` provides a good level of abstraction, issues can still arise.
-   **Focus and Window State**: The Abaqus window should ideally be the active, non-minimized window for the most reliable interaction, although the server attempts to manage focus.
-   **Modal Dialogs**: Unexpected modal dialogs in Abaqus (e.g., save reminders, warnings) can block the automation tools.
-   **Error Reporting**: Differentiate between errors from the MCP tools (e.g., "Abaqus window not found") and errors reported *within* the Abaqus message log (which originate from your script running inside Abaqus).

## Development / Troubleshooting

-   **Inspecting UI Elements**: If the `get_abaqus_gui_message_log` tool fails to retrieve messages accurately, or if `execute_script_in_abaqus_gui` has trouble with the "Run Script" dialog, you may need to use a UI inspection tool (e.g., `pywinauto.inspect` module's `InspectDialog` or `py_inspect.py` script, FlaUInspect for UIA backend) to identify the correct properties (AutomationId, Name, ClassName, ControlType) of the target UI elements in your Abaqus version. These properties can then be used to refine the search logic in `mcp_server.py`.
-   **Timeouts**: The server includes some `time.sleep()` calls and uses `pywinauto`'s `Timings.slow()` to better handle Abaqus's potentially slow UI response times. These might need adjustment in some environments.

## Project Structure

```
abaqus-mcp-gui-server/
├── mcp_server.py         # The main MCP server script
├── requirements.txt      # Python dependencies
└── README.md             # This documentation file
```

## License

This project is intended for learning, research, and specific automation tasks. When using Abaqus software, always adhere to the licensing terms provided by Dassault Systèmes.