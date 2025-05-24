from mcp.server.fastmcp import FastMCP
import tempfile
import os
import pygetwindow as gw
import win32process
import psutil
from pywinauto import Application, timings, base_wrapper
from pywinauto.controls import uia_controls
import time
from typing import Tuple, Optional

mcp = FastMCP(
    "ABAQUS GUI Script Executor",
    description="An MCP server to execute Python scripts within an existing Abaqus/CAE GUI session and retrieve message log information. Relies on pywinauto for GUI automation."
)

# Global cache for Abaqus window and app instance
abaqus_main_window_cache: Optional[uia_controls.WindowSpecification] = None
abaqus_app_instance_cache: Optional[Application] = None

def find_abaqus_window_and_app() -> Tuple[Optional[Application], Optional[uia_controls.WindowSpecification]]:
    """
    Finds the main Abaqus/CAE window and connects the pywinauto Application object.

    It first checks a cache. If not found or invalid, it searches for windows
    starting with the title "Abaqus/CAE", verifies the process name,
    and then attempts to connect a pywinauto.Application instance to it.
    The found application and window objects are cached for subsequent calls.

    Relies on `pygetwindow` for initial window discovery and `pywinauto` for connection.

    Returns:
        Tuple[Optional[Application], Optional[uia_controls.WindowSpecification]]:
            A tuple containing the connected `pywinauto.Application` instance and the
            main window specification (`WindowSpecification`). Both can be `None` if 
            the Abaqus/CAE window is not found or connection fails.
    """
    global abaqus_main_window_cache, abaqus_app_instance_cache
    if abaqus_app_instance_cache and abaqus_main_window_cache and \
       abaqus_main_window_cache.exists() and abaqus_main_window_cache.is_visible():
        return abaqus_app_instance_cache, abaqus_main_window_cache

    abaqus_app_instance_cache = None
    abaqus_main_window_cache = None

    windows = gw.getWindowsWithTitle("Abaqus/CAE")
    found_win_obj = None
    for win_ref in windows:
        if win_ref.title.startswith("Abaqus/CAE"):
            try:
                _, pid = win32process.GetWindowThreadProcessId(win_ref._hWnd)
                proc = psutil.Process(pid)
                if "abaqus" in proc.name().lower() and \
                   ("cae" in proc.name().lower() or "viewer" in proc.name().lower()):
                    found_win_obj = win_ref
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    
    if found_win_obj:
        try:
            timings.Timings.slow()
            app = Application(backend="uia").connect(handle=found_win_obj._hWnd, timeout=20)
            main_window = app.window(handle=found_win_obj._hWnd)
            if main_window.exists() and main_window.is_visible():
                abaqus_app_instance_cache = app
                abaqus_main_window_cache = main_window
                return app, main_window
        except Exception as e:
            print(f"Error connecting to Abaqus window via pywinauto: {e}")
    
    return None, None

@mcp.tool(
    name="execute_script_in_abaqus_gui",
    description="Executes a Python script in an already running Abaqus/CAE GUI session using the 'File -> Run Script...' menu. Assumes Abaqus/CAE is open and responsive."
)
def execute_script(python_code: str) -> str:
    """
    Executes a given Python code string within an active Abaqus/CAE GUI session.

    The process involves:
    1. Saving the `python_code` to a temporary .py file.
    2. Locating the active Abaqus/CAE main window.
    3. Automating the GUI to select 'File -> Run Script...' from the menu.
    4. Typing the path of the temporary script file into the 'Run Script' dialog.
    5. Clicking 'OK' in the dialog to initiate script execution.
    6. Deleting the temporary script file after submission.

    Args:
        python_code (str): The Python script content to be executed, as a string.

    Returns:
        str: A message indicating the outcome of the script submission attempt.
             This primarily confirms if the script was successfully passed to the Abaqus GUI
             via the 'Run Script' dialog. It does *not* return the script's own output
             or execution status from within Abaqus. The executed script would need to
             handle its own output (e.g., writing to files) if results are needed externally.
    """
    global abaqus_main_window_cache, abaqus_app_instance_cache
    app, main_window = find_abaqus_window_and_app()

    if not main_window or not main_window.exists():
        abaqus_app_instance_cache = None 
        abaqus_main_window_cache = None
        return "Abaqus/CAE window not found. Please ensure Abaqus/CAE with GUI is running and not minimized initially."

    script_file_path: Optional[str] = None
    run_script_dialog: Optional[uia_controls.WindowSpecification] = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding='utf-8') as tmp_script:
            tmp_script.write(python_code)
            script_file_path = tmp_script.name
        
        script_file_path_for_dialog = script_file_path.replace("/", "\\")

        if main_window.is_minimized():
            main_window.restore()
        main_window.set_focus()
        time.sleep(0.5)

        main_window.menu_select("File->Run Script...")
        time.sleep(1.5) # Wait for Abaqus to open the dialog

        dialog_found = False
        try:
            run_script_dialog = app.top_window() # Primary attempt
            if run_script_dialog.exists() and \
               ("Run Script" in run_script_dialog.window_text() or "Select file" in run_script_dialog.window_text()):
                dialog_found = True
            
            if not dialog_found:
                time.sleep(1) # Secondary attempt after a slight delay
                run_script_dialog = app.active() # Check currently active window of the app
                if run_script_dialog.exists() and \
                   ("Run Script" in run_script_dialog.window_text() or "Select file" in run_script_dialog.window_text()):
                    dialog_found = True

            if not dialog_found: # Tertiary attempt: search children of main window
                # This is a deeper search if the dialog isn't directly the app's top/active window.
                # Useful if the dialog is a child dialog or has an unusual relationship.
                possible_dialogs = main_window.children(control_type="Window", top_level_only=False, visible=True)
                for diag in possible_dialogs:
                    if diag.exists() and ("Run Script" in diag.window_text() or "Select file" in diag.window_text()):
                        run_script_dialog = diag
                        dialog_found = True
                        break
            
            if not dialog_found or not run_script_dialog:
                 raise Exception("'Run Script' dialog not found or title mismatch after menu click.")
        except Exception as e_dialog:
            print(f"Error finding or identifying the 'Run Script' dialog: {e_dialog}")
            return f"Failed to find or identify the 'Run Script' dialog: {e_dialog}"
        
        try:
            file_name_edit: Optional[uia_controls.EditWrapper] = None
            # Attempt to find by specific title and control type (more reliable)
            potential_edit = run_script_dialog.child_window(title="File &name:", control_type="Edit")
            if potential_edit.exists(timeout=1):
                file_name_edit = potential_edit.wrapper_object()
            else:
                # Fallback: by control type and index (less reliable, but common)
                potential_edit_by_index = run_script_dialog.child_window(control_type="Edit", found_index=0)
                if potential_edit_by_index.exists(timeout=1):
                    file_name_edit = potential_edit_by_index.wrapper_object()
                else:
                    # Fallback: generic Edit control (least reliable for complex dialogs)
                    generic_edit = run_script_dialog.Edit(found_index=0)
                    if generic_edit.exists(timeout=1):
                        file_name_edit = generic_edit
            
            if not file_name_edit:
                raise Exception("File name input field (Edit control) not found in 'Run Script' dialog. Searched by title 'File &name:', then by type/index.")
            
            file_name_edit.set_edit_text(script_file_path_for_dialog)
            time.sleep(0.3) # Pause after setting text

            ok_button: Optional[uia_controls.ButtonWrapper] = None
            # Attempt to find by common titles (OK, Run, Open) and control type
            potential_button = run_script_dialog.child_window(title_re="OK|Run|Open", control_type="Button")
            if potential_button.exists(timeout=1):
                ok_button = potential_button.wrapper_object()
            else:
                # Fallback: by control type and index (less reliable)
                potential_button_by_index = run_script_dialog.child_window(control_type="Button", found_index=0)
                if potential_button_by_index.exists(timeout=1):
                    ok_button = potential_button_by_index.wrapper_object()
                else:
                    # Fallback: generic Button control
                    generic_button = run_script_dialog.Button(found_index=0)
                    if generic_button.exists(timeout=1):
                        ok_button = generic_button

            if not ok_button:
                raise Exception("OK/Run/Open button not found in 'Run Script' dialog. Searched by title regex 'OK|Run|Open', then by type/index.")
            
            ok_button.click_input()
            
            return f"Script submitted for execution via File->Run Script: {script_file_path}"

        except Exception as e_interact:
            error_detail = str(e_interact)
            print(f"Error interacting with 'Run Script' dialog controls: {error_detail}")
            if run_script_dialog and run_script_dialog.exists():
                try: run_script_dialog.close() 
                except: pass # Best effort to close
            return f"Failed to interact with 'Run Script' dialog (e.g., input script path or click OK): {error_detail}"

    except timings.TimeoutError as e_timeout:
        abaqus_app_instance_cache = None 
        abaqus_main_window_cache = None
        return f"Timeout occurred during GUI operation: {str(e_timeout)}"
    except Exception as e_main:
        abaqus_app_instance_cache = None 
        abaqus_main_window_cache = None
        return f"An error occurred during script execution attempt: {str(e_main)}"
    finally:
        if script_file_path and os.path.exists(script_file_path):
            try: os.remove(script_file_path)
            except Exception as e_remove:
                print(f"Warning: Failed to delete temporary script file {script_file_path}: {e_remove}")

@mcp.tool(
    name="get_abaqus_gui_message_log",
    description="Attempts to retrieve text from the Abaqus/CAE message/log area. Accuracy depends on UI structure and may require inspect tool information for reliable targeting of the message area control."
)
def get_abaqus_message_log() -> str:
    """
    Attempts to retrieve the text content from the Abaqus/CAE message/log area.

    This tool relies on GUI automation to find the Abaqus window and then heuristically
    searches for a UI element that represents the message/log display. The reliability 
    of finding this element and extracting its full text can vary significantly based 
    on the Abaqus version, specific UI configuration, and the complexity of the 
    message area control (e.g., simple text vs. rich-text vs. custom widget).

    For robust operation, providing specific identifiers for the message area UI element
    (obtained via an inspect tool like py_inspect or FlaUInspect) is highly recommended.
    These identifiers (e.g., AutomationId, Name, ClassName) should be used to replace
    the heuristic search logic within this function for your specific Abaqus setup.

    Returns:
        str: A string containing the extracted text from the message area if found and readable.
             If the message area cannot be found or text cannot be extracted, an informative
             error or status message is returned.
    """
    global abaqus_main_window_cache, abaqus_app_instance_cache
    app, main_window = find_abaqus_window_and_app()

    if not main_window or not main_window.exists():
        abaqus_app_instance_cache = None 
        abaqus_main_window_cache = None
        return "Abaqus/CAE window not found. Cannot retrieve message log."

    try:
        message_area_control: Optional[base_wrapper.BaseWrapper] = None
        
        # **Highly Recommended: Replace heuristic search below with specific identifiers from an inspect tool.**
        # Example using AutomationId (BEST choice if available and static):
        # try:
        #     specific_control = main_window.child_window(automation_id="YourAbaqusMessageAreaAutomationId")
        #     if specific_control.exists() and specific_control.is_visible():
        #         message_area_control = specific_control.wrapper_object()
        # except Exception as e_specific_find:
        #     print(f"Failed to find message area by specific AutomationId: {e_specific_find}")

        # Heuristic Search (if specific identifiers are not yet configured):
        if not message_area_control:
            # Heuristic 1: Look for large, visible Panes (often FXWindow in Abaqus for custom areas)
            possible_panes = main_window.descendants(control_type="Pane") # More general than just FXWindow initially
            for pane_spec in possible_panes:
                pane = pane_spec.wrapper_object() # Get the wrapper to access more properties
                if pane.is_visible() and pane.rectangle().height > 100 and pane.rectangle().width() > 200:
                    # Additional check: class_name if it helps narrow down (e.g., "AfxMDIFrame")
                    # Or if it's known to be an FXWindow that contains text.
                    if "FXWindow" in pane.class_name(): # Check if it's an FXWindow as they often host content
                        texts = pane.texts()
                        if texts and any(line.strip() for group in texts if group for line in group):
                            message_area_control = pane
                            break
            if message_area_control: print("Message area found via Pane heuristic.")

        if not message_area_control:
            # Heuristic 2: Look for large, visible, read-only Edit controls
            possible_edits = main_window.descendants(control_type="Edit")
            for edit_spec in possible_edits:
                edit = edit_spec.wrapper_object()
                if edit.is_visible() and not edit.is_editable() and edit.rectangle().height > 50:
                    texts = edit.texts()
                    if texts and any(line.strip() for group in texts if group for line in group):
                        message_area_control = edit
                        break
            if message_area_control: print("Message area found via Edit heuristic.")
        
        # Add other specific fallbacks here if more UI details are known, e.g., based on Name or a deeper path.
        # Example: specific_control_by_name = main_window.child_window(title="Message Window", control_type="Document")

        if message_area_control and message_area_control.exists():
            log_content_lines = []
            raw_texts = message_area_control.texts() # .texts() often returns list of lists of strings for UIA
            for text_group in raw_texts:
                if text_group: # Ensure the group itself is not None or empty
                    for line in text_group:
                        if line: # Ensure the line string is not None or empty
                            log_content_lines.append(line)
            
            log_content = "\n".join(log_content_lines).strip()
            
            if not log_content and hasattr(message_area_control, 'window_text'):
                 log_content = message_area_control.window_text().strip()
            
            if log_content:
                return f"Message Log Content (best effort extraction):\n------------------------\n{log_content}\n------------------------"
            else:
                return ("Found a potential message area UI element, but could not extract text content. "
                        "The control might be custom, empty, or text extraction method failed. More specific inspect details are needed.")
        else:
            return ("Message area UI element not found using current heuristics. "
                    "For reliable message log retrieval, please use an inspect tool to identify the specific properties "
                    "(e.g., AutomationId, Name, ClassName) of the Abaqus message area and update this function's search logic.")

    except Exception as e:
        abaqus_app_instance_cache = None 
        abaqus_main_window_cache = None
        return f"An error occurred while trying to retrieve the Abaqus message log: {str(e)}"

@mcp.prompt()
def abaqus_scripting_strategy() -> str:
    """
    Defines the preferred strategy for interacting with an Abaqus/CAE GUI session
    using this MCP server. This prompt guides an LLM agent on how to effectively
    use the available tools for scripting and information retrieval.
    """
    return """When performing tasks in an Abaqus/CAE GUI session via this MCP server:

    1.  **Core Assumption:** This server interacts with an ALREADY RUNNING Abaqus/CAE GUI session. It does not start or stop Abaqus/CAE. Ensure the Abaqus/CAE application is open, responsive, and ideally the primary focused window when initiating tool calls.

    2.  **Executing Python Scripts (`execute_script_in_abaqus_gui` tool):
        *   **Purpose:** Use this tool to run custom Python scripts within the Abaqus/CAE environment.
        *   **Input:** Provide the complete Python script as a string to the `python_code` argument. This script should contain valid Abaqus Scripting Interface (ASI) commands. Ensure the script is self-contained or that any required models/files are already loaded or accessible within the Abaqus session as the script would expect.
        *   **Mechanism:** This tool automates the 'File -> Run Script...' menu selection and dialog interaction in the Abaqus GUI.
        *   **Return Value:** The tool returns a string message indicating that the script was *submitted* to the Abaqus GUI. It does NOT return the direct output (e.g., print statements from your script) or catch Python exceptions raised *within* the Abaqus script's execution context.
        *   **Idempotency:** This tool is not idempotent. Calling it multiple times with the same script will execute the script multiple times in Abaqus.
        *   **Checking Script Outcome:** After submitting a script, it is CRUCIAL to use the `get_abaqus_gui_message_log` tool to check the Abaqus message area. This is where you will find:
            *   Confirmation of script completion (often specific messages printed by Abaqus itself).
            *   Any `print()` statements from your Python script.
            *   Error messages or warnings generated by Abaqus or your script if it failed or encountered issues.

    3.  **Retrieving Abaqus GUI Messages (`get_abaqus_gui_message_log` tool):
        *   **Purpose:** Use this tool to fetch the text content from the Abaqus/CAE message/log area (often at the bottom of the main window).
        *   **Primary Use Cases:**
            *   To verify the outcome of scripts run via `execute_script_in_abaqus_gui`.
            *   To check for general Abaqus status messages, warnings, or errors that may have occurred during manual or scripted operations.
        *   **Reliability Note:** This tool attempts to scrape text from a GUI element. Its accuracy can depend on the specific Abaqus version and UI configuration. The current implementation uses heuristics to find the message area. If it fails to retrieve the log accurately or completely, the server's GUI interaction logic for this tool might need adjustment based on specific UI element identifiers (e.g., AutomationId, Name, ClassName) obtained from an inspect tool for your Abaqus environment.

    4.  **Recommended Workflow for Script Execution & Verification:**
        a.  Ensure the Abaqus/CAE GUI is running, visible, and in a stable state (e.g., no blocking modal dialogs other than those expected by the tools).
        b.  Formulate the Abaqus Python script (ASI commands) you want to run.
        c.  Call `execute_script_in_abaqus_gui` with your script string.
        d.  Note the confirmation message (script submitted).
        e.  Wait a reasonable amount of time for the script to likely execute within Abaqus. This duration depends heavily on the script's complexity and the operations it performs.
        f.  Call `get_abaqus_gui_message_log`.
        g.  Carefully examine the returned string from `get_abaqus_gui_message_log` to understand the actual outcome of your script, including any errors or messages it printed.

    5.  **Troubleshooting GUI Interaction and Best Practices:**
        *   **Window State:** Ensure the Abaqus/CAE window is not minimized when initiating actions. The tools attempt to restore and focus, but an already active window is best.
        *   **Modal Dialogs:** Avoid having unexpected modal dialogs open in Abaqus, as they can block the GUI automation tools.
        *   **Tool Failures:** If `execute_script_in_abaqus_gui` fails (e.g., cannot find dialogs/controls), it might indicate an unexpected Abaqus state, a change in UI structure, or the Abaqus window being unresponsive. The `get_abaqus_gui_message_log` (if it can run) might offer clues. Otherwise, manual inspection of the Abaqus GUI will be necessary.
        *   **Script Errors vs. Tool Errors:** Differentiate between errors returned by the MCP tools (e.g., "dialog not found") and errors that appear in the Abaqus message log (which are errors from your script's execution within Abaqus).
    """

if __name__ == "__main__":
    mcp.run() 