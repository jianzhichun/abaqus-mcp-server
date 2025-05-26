import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the directory containing mcp_server.py to the Python path
# This is to ensure that the mcp_server module can be imported
# Assuming test_mcp_server.py is in the same directory as mcp_server.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from mcp_server import (
        find_abaqus_window_and_app,
        execute_script,
        get_abaqus_message_log,
        mcp # For FastMCP instance if needed for context, though tools are standalone
    )
    # Mock a dummy FastMCP instance for the decorators to work if they rely on it at import time
    # This might not be strictly necessary if the functions can be tested in isolation
    # but good for ensuring the module loads.
    if not hasattr(mcp, 'tool'): # If mcp was not fully initialized for some reason
        class DummyMCP:
            def tool(self, *args, **kwargs):
                def decorator(f):
                    return f
                return decorator
            def prompt(self, *args, **kwargs):
                def decorator(f):
                    return f
                return decorator
        mcp = DummyMCP()

except ImportError as e:
    print(f"Failed to import from mcp_server: {e}")
    # Define dummy functions if import fails, so tests can at least be defined
    def find_abaqus_window_and_app(): pass
    def execute_script(python_code: str): pass
    def get_abaqus_message_log(): pass

class TestFindAbaqusWindowAndApp(unittest.TestCase):

    @patch('mcp_server.gw')
    @patch('mcp_server.win32process')
    @patch('mcp_server.psutil')
    @patch('mcp_server.Application')
    @patch('mcp_server.abaqus_app_instance_cache', new=None)
    @patch('mcp_server.abaqus_main_window_cache', new=None)
    def test_find_window_success_no_cache(self, mock_app_class, mock_psutil, mock_win32process, mock_gw):
        # Setup mocks for a successful window find and connection
        mock_window_ref = MagicMock()
        mock_window_ref.title = "Abaqus/CAE ModName - JobName"
        mock_window_ref._hWnd = 12345
        mock_gw.getWindowsWithTitle.return_value = [mock_window_ref]

        mock_win32process.GetWindowThreadProcessId.return_value = (None, 67890)
        
        mock_proc = MagicMock()
        mock_proc.name.return_value = "abaqus_cae.exe"
        mock_psutil.Process.return_value = mock_proc

        mock_pywinauto_app = MagicMock()
        mock_main_window_spec = MagicMock()
        mock_main_window_spec.exists.return_value = True
        mock_main_window_spec.is_visible.return_value = True
        
        mock_pywinauto_app.window.return_value = mock_main_window_spec
        mock_app_class.return_value.connect.return_value = mock_pywinauto_app # connect() returns the app instance
        # Simulate that app.window() is called on the instance returned by connect()
        # If connect() returns the app instance, then app.window() is called on that.
        # The original code does app = Application(backend="uia").connect(...)
        # then main_window = app.window(...)
        # So, mock_app_class itself is the Application class.
        # Its instance (returned by __call__ or connect) should have the window method.
        
        # We need to ensure that the Application constructor itself returns an object
        # that then has the connect method.
        # And connect itself returns an object that has the window method.

        # Revised mocking for Application:
        mock_app_instance_for_connect = MagicMock()
        mock_app_instance_for_connect.window.return_value = mock_main_window_spec
        
        mock_app_constructor_instance = MagicMock()
        mock_app_constructor_instance.connect.return_value = mock_app_instance_for_connect
        mock_app_class.return_value = mock_app_constructor_instance


        app, window = find_abaqus_window_and_app()

        self.assertIsNotNone(app)
        self.assertIsNotNone(window)
        mock_gw.getWindowsWithTitle.assert_called_with("Abaqus/CAE")
        mock_win32process.GetWindowThreadProcessId.assert_called_with(12345)
        mock_psutil.Process.assert_called_with(67890)
        mock_app_class.assert_called_with(backend="uia")
        mock_app_constructor_instance.connect.assert_called_with(handle=12345, timeout=20)
        mock_app_instance_for_connect.window.assert_called_with(handle=12345)
        self.assertEqual(window, mock_main_window_spec)

    @patch('mcp_server.abaqus_app_instance_cache')
    @patch('mcp_server.abaqus_main_window_cache')
    def test_find_window_cache_hit(self, mock_window_cache, mock_app_cache):
        # Setup cache
        mock_app_cache.exists.return_value = True # Assuming app cache itself doesn't need exists()
        mock_window_cache.exists.return_value = True
        mock_window_cache.is_visible.return_value = True
        
        # Need to assign to the module's global directly for the test's context
        import mcp_server
        mcp_server.abaqus_app_instance_cache = mock_app_cache
        mcp_server.abaqus_main_window_cache = mock_window_cache

        app, window = find_abaqus_window_and_app()

        self.assertEqual(app, mock_app_cache)
        self.assertEqual(window, mock_window_cache)
        
        # Reset caches for other tests
        mcp_server.abaqus_app_instance_cache = None
        mcp_server.abaqus_main_window_cache = None


    @patch('mcp_server.gw')
    def test_find_window_not_found(self, mock_gw):
        mock_gw.getWindowsWithTitle.return_value = []
        app, window = find_abaqus_window_and_app()
        self.assertIsNone(app)
        self.assertIsNone(window)

    # Add more tests for find_abaqus_window_and_app (e.g., process name mismatch, connection error)


class TestExecuteScript(unittest.TestCase):

    @patch('mcp_server.find_abaqus_window_and_app')
    @patch('mcp_server.tempfile.NamedTemporaryFile')
    @patch('mcp_server.os.remove')
    @patch('mcp_server.time.sleep') # Mock sleep to speed up tests
    def test_execute_script_success(self, mock_sleep, mock_os_remove, mock_tempfile, mock_find_abaqus):
        # Mock successful Abaqus window and app
        mock_app = MagicMock()
        mock_main_window = MagicMock()
        mock_main_window.exists.return_value = True
        mock_main_window.is_minimized.return_value = False
        mock_find_abaqus.return_value = (mock_app, mock_main_window)

        # Mock temp file creation
        mock_tmp_file = MagicMock()
        mock_tmp_file.name = "C:\temp\somescript.py" # Use a windows-like path for consistency
        mock_tempfile.return_value.__enter__.return_value = mock_tmp_file

        # Mock dialog interaction
        mock_run_script_dialog = MagicMock()
        mock_run_script_dialog.exists.return_value = True
        mock_run_script_dialog.window_text.return_value = "Run Script Dialog" # Match one of the conditions
        
        mock_app.top_window.return_value = mock_run_script_dialog # Primary attempt
        # If app.active() or main_window.children() were used, they'd need mocking too.

        mock_file_name_edit = MagicMock()
        mock_file_name_edit.exists.return_value = True
        mock_run_script_dialog.child_window.return_value = mock_file_name_edit # Assuming first child_window call gets it
        # To be more specific, you could use side_effect if multiple calls are made with different args
        
        mock_ok_button = MagicMock()
        mock_ok_button.exists.return_value = True
        # Adjust if the second call to child_window is the one for the button
        # For simplicity, let's assume child_window with title_re="OK|Run|Open" finds it.
        mock_run_script_dialog.child_window.side_effect = [
            MagicMock(exists=MagicMock(return_value=True), wrapper_object=MagicMock(return_value=mock_file_name_edit)), # For File &name:
            MagicMock(exists=MagicMock(return_value=True), wrapper_object=MagicMock(return_value=mock_ok_button))    # For OK button
        ]


        python_code = "print('Hello Abaqus')"
        result = execute_script(python_code)

        mock_find_abaqus.assert_called_once()
        mock_tempfile.assert_called_once_with(mode="w", suffix=".py", delete=False, encoding='utf-8')
        mock_tmp_file.write.assert_called_with(python_code)
        
        mock_main_window.menu_select.assert_called_with("File->Run Script...")
        
        # Check if dialog interactions happened (more specific assertions can be added)
        self.assertTrue("File &name:" in str(mock_run_script_dialog.child_window.call_args_list))
        self.assertTrue("OK|Run|Open" in str(mock_run_script_dialog.child_window.call_args_list))

        mock_file_name_edit_wrapper = mock_run_script_dialog.child_window.side_effect[0].wrapper_object()
        mock_file_name_edit_wrapper.set_edit_text.assert_called_with("C:\temp\somescript.py") # Path replacement happens
        
        mock_ok_button_wrapper = mock_run_script_dialog.child_window.side_effect[1].wrapper_object()
        mock_ok_button_wrapper.click_input.assert_called_once()

        self.assertIn("Script submitted for execution", result)
        mock_os_remove.assert_called_with("C:\temp\somescript.py")


    @patch('mcp_server.find_abaqus_window_and_app')
    def test_execute_script_abaqus_not_found(self, mock_find_abaqus):
        mock_find_abaqus.return_value = (None, None)
        result = execute_script("print('test')")
        self.assertIn("Abaqus/CAE window not found", result)

    # Add more tests for execute_script (e.g., dialog not found, control interaction failures)


class TestGetAbaqusMessageLog(unittest.TestCase):

    @patch('mcp_server.find_abaqus_window_and_app')
    def test_get_log_success_pane_heuristic(self, mock_find_abaqus):
        mock_app = MagicMock()
        mock_main_window = MagicMock()
        mock_main_window.exists.return_value = True
        mock_find_abaqus.return_value = (mock_app, mock_main_window)

        mock_pane = MagicMock()
        mock_pane.is_visible.return_value = True
        mock_pane.rectangle.return_value = MagicMock(height=MagicMock(return_value=150), width=MagicMock(return_value=300))
        mock_pane.class_name.return_value = "SomeFXWindow"
        mock_pane.texts.return_value = [["Line 1", "Line 2"], ["", "Line 3"]] # Simulate texts structure
        mock_pane.exists.return_value = True # For the if message_area_control.exists() check

        mock_main_window.descendants.return_value = [MagicMock(wrapper_object=MagicMock(return_value=mock_pane))] # descendants returns specs

        result = get_abaqus_message_log()

        mock_find_abaqus.assert_called_once()
        mock_main_window.descendants.assert_any_call(control_type="Pane")
        self.assertIn("Line 1\nLine 2\nLine 3", result)
        self.assertIn("Message Log Content", result)

    @patch('mcp_server.find_abaqus_window_and_app')
    def test_get_log_success_edit_heuristic(self, mock_find_abaqus):
        mock_app = MagicMock()
        mock_main_window = MagicMock()
        mock_main_window.exists.return_value = True
        mock_find_abaqus.return_value = (mock_app, mock_main_window)

        # Pane heuristic fails (no suitable panes)
        mock_no_pane = MagicMock()
        mock_no_pane.is_visible.return_value = False # Or doesn't match criteria

        # Edit heuristic succeeds
        mock_edit = MagicMock()
        mock_edit.is_visible.return_value = True
        mock_edit.is_editable.return_value = False
        mock_edit.rectangle.return_value = MagicMock(height=MagicMock(return_value=60), width=MagicMock(return_value=300))
        mock_edit.texts.return_value = [["Error: 123", "Warning: 456"]]
        mock_edit.exists.return_value = True

        mock_main_window.descendants.side_effect = [
            [MagicMock(wrapper_object=MagicMock(return_value=mock_no_pane))], # For Pane
            [MagicMock(wrapper_object=MagicMock(return_value=mock_edit))]     # For Edit
        ]

        result = get_abaqus_message_log()
        mock_find_abaqus.assert_called_once()
        self.assertIn("Error: 123\nWarning: 456", result)
        self.assertIn("Message Log Content", result)

    @patch('mcp_server.find_abaqus_window_and_app')
    def test_get_log_abaqus_not_found(self, mock_find_abaqus):
        mock_find_abaqus.return_value = (None, None)
        result = get_abaqus_message_log()
        self.assertIn("Abaqus/CAE window not found", result)

    @patch('mcp_server.find_abaqus_window_and_app')
    def test_get_log_no_message_area_found(self, mock_find_abaqus):
        mock_app = MagicMock()
        mock_main_window = MagicMock()
        mock_main_window.exists.return_value = True
        mock_find_abaqus.return_value = (mock_app, mock_main_window)

        # Both heuristics fail
        mock_main_window.descendants.return_value = [] # No elements found

        result = get_abaqus_message_log()
        self.assertIn("Message area UI element not found", result)

    # Add more tests for get_abaqus_message_log (e.g., control found but no text)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False) 