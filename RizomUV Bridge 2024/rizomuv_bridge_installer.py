import maya.cmds as cmds
import maya.mel as mel
import os
import sys
import shutil
import traceback
import textwrap
import platform
import json
import logging
import glob
import subprocess
import locale
from pathlib import Path

QT_AVAILABLE = False
try:
    if sys.version_info.major >= 3 and sys.version_info.minor >= 11:
        from PySide6 import QtWidgets, QtCore, QtGui
        from shiboken6 import wrapInstance

        print("RizomBridge Installer: Using PySide6 for dialogs")
    else:
        from PySide2 import QtWidgets, QtCore, QtGui
        from shiboken2 import wrapInstance

        print("RizomBridge Installer: Using PySide2 for dialogs")
    QT_AVAILABLE = True
except ImportError as e:
    QT_AVAILABLE = False
    print(
        f"RizomBridge Installer: Could not import PySide2/PySide6: {e}. UI selection for multiple RizomUV paths disabled."
    )
MODULE_NAME = "maya_rizomuv_bridge"
SCRIPT_FILE_NAME = f"{MODULE_NAME}.py"
INSTALL_SUBDIR = "RZMUV"
ICON_FILE_NAME = "rzmuv.png"
SHELF_BUTTON_LABEL = "RizomUV"
SHELF_BUTTON_TOOLTIP = "Launch RizomUV Maya Bridge"
WORKSPACE_CONTROL_NAME = "rizomUVBridgeWorkspaceControl"
CONFIG_FILE_NAME = "settings.json"
STATE_FILE_NAME = "bridge_state.json"
LUA_SCRIPT_FILE_NAME = "rizomuv_control_script.lua"
LIVE_LUA_SCRIPT_FILE_NAME = "rizomuv_livelink_script.lua"
FBX_FILE_NAME = "RizomUVMayaBridge.fbx"
RIZOMUV_LINK_DIR_NAME = "RizomUVLink"
STARTUP_CODE_START_MARKER = f"# --- {INSTALL_SUBDIR} Startup Logic ---"
STARTUP_CODE_END_MARKER = f"# --- End {INSTALL_SUBDIR} Startup Logic ---"
installer_logger = logging.getLogger("RizomBridgeInstaller")
if not installer_logger.handlers:
    installer_logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
    )
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    installer_logger.addHandler(ch)
    installer_logger.propagate = False


def get_maya_scripts_dir():
    "Gets the user's Maya version-specific scripts directory."
    try:
        scripts_dir = cmds.internalVar(userScriptDir=True)
        if scripts_dir and os.path.isdir(scripts_dir):
            return Path(scripts_dir)
        else:
            installer_logger.warning(f"Could not get valid scripts dir: {scripts_dir}")
            return None
    except Exception as e:
        installer_logger.error(f"Error getting scripts dir: {e}")
        return None


def get_user_setup_path():
    "Gets the preferred userSetup.py path."
    scripts_dir_version_specific = get_maya_scripts_dir()
    path_version_specific = None
    if scripts_dir_version_specific:
        path_version_specific = scripts_dir_version_specific / "userSetup.py"
    scripts_dir_main = None
    path_main = None
    try:
        maya_app_dir = cmds.internalVar(userAppDir=True)
        if maya_app_dir:
            potential_main_scripts = Path(maya_app_dir) / "scripts"
            if potential_main_scripts.is_dir():
                scripts_dir_main = potential_main_scripts
                path_main = scripts_dir_main / "userSetup.py"
    except Exception as e:
        installer_logger.info(f"Could not check main scripts dir: {e}")
    if path_main and path_main.is_file():
        installer_logger.info(f"Found userSetup.py: {path_main}")
        return path_main
    elif path_version_specific and path_version_specific.is_file():
        installer_logger.info(f"Found userSetup.py: {path_version_specific}")
        return path_version_specific
    elif path_version_specific:
        installer_logger.info(f"Will use/create userSetup.py: {path_version_specific}")
        return path_version_specific
    elif path_main:
        installer_logger.info(f"Will use/create userSetup.py: {path_main}")
        return path_main
    else:
        installer_logger.error("Could not determine userSetup.py path.")
        return None


def get_installed_script_path():
    "Gets the expected path of the installed tool script."
    scripts_dir = get_maya_scripts_dir()
    if not scripts_dir:
        return None
    if INSTALL_SUBDIR:
        return scripts_dir / INSTALL_SUBDIR / SCRIPT_FILE_NAME
    else:
        return scripts_dir / SCRIPT_FILE_NAME


def get_installed_icon_path():
    "Gets the expected path of the installed icon file."
    scripts_dir = get_maya_scripts_dir()
    if not scripts_dir:
        return None
    if INSTALL_SUBDIR:
        return scripts_dir / INSTALL_SUBDIR / ICON_FILE_NAME
    else:
        return scripts_dir / ICON_FILE_NAME


def _iter_shelf_buttons():
    """Yields (control, command, label) for every shelf button on every shelf.

    Uses the shelfTabLayout's child layout NAMES (not tab labels, which can
    diverge after a shelf rename) and guards each control individually so one
    exotic plugin control cannot abort the whole scan.
    """
    try:
        shelf_tab_layout = mel.eval(
            "global string $gShelfTopLevel; $gShelfTopLevel = $gShelfTopLevel;"
        )
        if not cmds.shelfTabLayout(shelf_tab_layout, query=True, exists=True):
            return
        all_shelves = (
            cmds.shelfTabLayout(shelf_tab_layout, query=True, childArray=True) or []
        )
    except Exception as e_layout:
        installer_logger.warning(f"Could not query shelf layouts: {e_layout}")
        return
    for shelf in all_shelves:
        try:
            if not cmds.shelfLayout(shelf, query=True, exists=True):
                continue
            controls = cmds.shelfLayout(shelf, query=True, childArray=True) or []
        except Exception as e_shelf:
            installer_logger.debug(f"Could not query shelf '{shelf}': {e_shelf}")
            continue
        for control in controls:
            try:
                if cmds.objectTypeUI(control) != "shelfButton":
                    continue
                if not cmds.shelfButton(control, query=True, exists=True):
                    continue
                cmd_string = (
                    cmds.shelfButton(control, query=True, command=True) or ""
                )
                label_string = (
                    cmds.shelfButton(control, query=True, label=True) or ""
                )
                yield control, cmd_string, label_string
            except Exception as e_control:
                installer_logger.debug(
                    f"Skipping unreadable shelf control '{control}': {e_control}"
                )


def check_installation():
    "Checks if the Rizom Bridge appears to be installed."
    install_info = {"script": False, "userSetup": False, "button": False}
    installed_script_path = get_installed_script_path()
    if installed_script_path and installed_script_path.is_file():
        install_info["script"] = True
    user_setup_path = get_user_setup_path()
    if user_setup_path and user_setup_path.is_file():
        try:
            content = user_setup_path.read_text(encoding="utf-8", errors="replace")
            if STARTUP_CODE_START_MARKER in content:
                install_info["userSetup"] = True
        except Exception as e:
            installer_logger.warning(
                f"Could not read userSetup.py '{user_setup_path}': {e}"
            )
    try:
        for control, cmd_string, label_string in _iter_shelf_buttons():
            if MODULE_NAME in cmd_string or label_string == SHELF_BUTTON_LABEL:
                install_info["button"] = True
                break
    except Exception as e_shelf:
        installer_logger.warning(f"Error checking shelf buttons: {e_shelf}")
    if install_info["script"] and install_info["userSetup"] and install_info["button"]:
        return "installed"
    elif install_info["script"] or install_info["userSetup"] or install_info["button"]:
        return "partially_installed"
    else:
        return "not_installed"


def get_maya_main_window():
    "Gets the Maya main window QWidget."
    if not QT_AVAILABLE:
        return None
    try:
        import maya.OpenMayaUI as omui

        if "shiboken6" in sys.modules:
            from shiboken6 import wrapInstance
        elif "shiboken2" in sys.modules:
            from shiboken2 import wrapInstance
        else:
            try:
                from shiboken6 import wrapInstance
            except ImportError:
                from shiboken2 import wrapInstance
        main_window_ptr = omui.MQtUtil.mainWindow()
        if main_window_ptr is not None:
            return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)
    except Exception as e:
        installer_logger.error(f"Could not get Maya main window: {e}")
    return None


def run_command(cmd_list):
    try:
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        process = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            check=False,
            startupinfo=startupinfo,
            encoding=locale.getpreferredencoding(False),
            errors="replace",
        )
        return process.stdout, process.stderr, process.returncode
    except FileNotFoundError:
        installer_logger.warning(f"Command not found: {cmd_list[0]}")
        return "", f"Command not found: {cmd_list[0]}", -1
    except Exception as e:
        installer_logger.error(f"Error running command '{' '.join(cmd_list)}': {e}")
        return "", str(e), -1


def find_rizomuv_installations():
    system = platform.system()
    found_paths = set()
    installer_logger.info("Detecting RizomUV installations...")
    if system == "Windows":
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        program_files_x86 = os.environ.get(
            "ProgramFiles(x86)", "C:\\Program Files (x86)"
        )
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        search_patterns = [
            os.path.join(program_files, "Rizom Lab\\RizomUV*\\rizomuv.exe"),
            os.path.join(program_files_x86, "Rizom Lab\\RizomUV*\\rizomuv.exe"),
        ]
        if local_app_data:
            search_patterns.append(
                os.path.join(
                    local_app_data, "Programs\\Rizom Lab\\RizomUV*\\rizomuv.exe"
                )
            )
        for pattern in search_patterns:
            for path in glob.glob(pattern):
                if os.path.isfile(path):
                    found_paths.add(os.path.normpath(path))
                    installer_logger.info(f"Found potential Windows path: {path}")
    elif system == "Darwin":
        bundle_id = "com.rizom-lab.rizomuv"
        cmd = ["mdfind", f'kMDItemCFBundleIdentifier == "{bundle_id}"']
        stdout, stderr, code = run_command(cmd)
        if code == 0 and stdout:
            for line in stdout.strip().split("\n"):
                path = line.strip()
                if path.endswith(".app") and os.path.isdir(path):
                    found_paths.add(os.path.normpath(path))
                    installer_logger.info(f"Found via mdfind: {path}")
        search_patterns = [
            "/Applications/RizomUV*.app",
            os.path.expanduser("~/Applications/RizomUV*.app"),
        ]
        for pattern in search_patterns:
            for path in glob.glob(pattern):
                if os.path.isdir(path):
                    found_paths.add(os.path.normpath(path))
                    installer_logger.info(f"Found potential macOS path: {path}")
    elif system == "Linux":
        stdout, stderr, code = run_command(["which", "rizomuv"])
        if code == 0 and stdout:
            path = stdout.strip()
            if os.path.isfile(path) and os.access(path, os.X_OK):
                found_paths.add(os.path.normpath(path))
                installer_logger.info(f"Found via which: {path}")
        search_patterns = [
            "/usr/local/bin/rizomuv",
            "/opt/Rizom Lab/RizomUV*/rizomuv",
            os.path.expanduser("~/.local/bin/rizomuv"),
            "/opt/RizomUV*.AppImage",
            "/usr/local/bin/RizomUV*.AppImage",
            os.path.expanduser("~/Applications/RizomUV*.AppImage"),
            os.path.expanduser("~/.local/bin/RizomUV*.AppImage"),
        ]
        for pattern in search_patterns:
            for path in glob.glob(pattern):
                if os.path.isfile(path) and os.access(path, os.X_OK):
                    found_paths.add(os.path.normpath(path))
                    installer_logger.info(f"Found potential Linux path: {path}")
    installer_logger.info(
        f"Detection finished. Found {len(found_paths)} potential installations."
    )
    return sorted(list(found_paths))


def browse_manually(parent_window):
    if not QT_AVAILABLE:
        installer_logger.warning(
            "Qt not available for manual browse dialog. Using basic fileDialog2."
        )
        try:
            result = cmds.fileDialog2(
                fileFilter="RizomUV Executable/App (*.exe *.app *)",
                dialogStyle=2,
                fileMode=1,
                caption="Locate RizomUV",
            )
            if result and result[0]:
                return result[0]
        except Exception as e_fd2:
            installer_logger.error(f"Error using fileDialog2 fallback: {e_fd2}")
        return None
    system = platform.system()
    file_filter = ""
    default_path_dir = ""
    selected_path = None
    installer_logger.info("Opening manual browse dialog...")
    try:
        if system == "Windows":
            file_filter = "RizomUV Executable (rizomuv.exe)"
            default_path = "C:\\Program Files\\Rizom Lab"
            qfile_filter = f"{file_filter};;All Files (*)"
            start_dir = (
                default_path if os.path.isdir(default_path) else "C:\\Program Files"
            )
            path_tuple = QtWidgets.QFileDialog.getOpenFileName(
                parent_window, "Select RizomUV Executable", start_dir, qfile_filter
            )
        elif system == "Darwin":
            default_path = "/Applications"
            start_dir = default_path if os.path.isdir(default_path) else "/"
            path = QtWidgets.QFileDialog.getExistingDirectory(
                parent_window,
                "Select RizomUV Application (.app)",
                start_dir,
                QtWidgets.QFileDialog.Option.ShowDirsOnly
                | QtWidgets.QFileDialog.Option.DontUseNativeDialog,
            )
            path_tuple = (path,)
        else:
            file_filter = "RizomUV Executable/AppImage"
            default_path = "/usr/local/bin"
            qfile_filter = f"{file_filter} (*);;All Files (*)"
            start_dir = default_path if os.path.isdir(default_path) else "/"
            path_tuple = QtWidgets.QFileDialog.getOpenFileName(
                parent_window,
                "Select RizomUV Executable/AppImage",
                start_dir,
                qfile_filter,
            )
        path_str = (
            path_tuple[0]
            if isinstance(path_tuple, (list, tuple)) and len(path_tuple) > 0
            else path_tuple
            if isinstance(path_tuple, str)
            else None
        )
        if path_str:
            installer_logger.info(f"Manual selection: {path_str}")
            return path_str
        else:
            installer_logger.info("Manual browse cancelled.")
            return None
    except Exception as e_dialog:
        installer_logger.error(f"Error during QFileDialog operation: {e_dialog}")
        return None


class SelectRizomDialog(QtWidgets.QDialog):
    def __init__(self, paths, parent=None):
        super(SelectRizomDialog, self).__init__(parent)
        self.setWindowTitle("Select RizomUV Version")
        self.setMinimumWidth(400)
        self.selected_path = None
        self.do_browse = False
        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(
            "Multiple RizomUV installations detected.\nPlease select the version to use:"
        )
        layout.addWidget(label)
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.addItems(paths)
        if paths:
            self.list_widget.setCurrentRow(0)
            layout.addWidget(self.list_widget)
        button_layout = QtWidgets.QHBoxLayout()
        self.ok_button = QtWidgets.QPushButton("Use Selected")
        self.browse_button = QtWidgets.QPushButton("Browse Manually...")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.browse_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        self.ok_button.clicked.connect(self.accept_selection)
        self.browse_button.clicked.connect(self.browse_selection)
        self.cancel_button.clicked.connect(self.reject)
        self.list_widget.itemDoubleClicked.connect(self.accept_selection)

    def accept_selection(self):
        current_item = self.list_widget.currentItem()
        if current_item:
            self.selected_path = current_item.text()
            self.accept()
        else:
            installer_logger.warning("OK clicked but no item selected.")

    def browse_selection(self):
        self.do_browse = True
        self.reject()

    @staticmethod
    def get_selection(paths, parent):
        dialog = SelectRizomDialog(paths, parent)
        result = dialog.exec()
        if result == QtWidgets.QDialog.DialogCode.Accepted:
            return dialog.selected_path, False
        elif dialog.do_browse:
            return None, True
        else:
            return None, False


def confirm_rizom_path(parent_window):
    rizomPath = None
    detected_paths = find_rizomuv_installations()
    num_found = len(detected_paths)
    if num_found == 0:
        installer_logger.warning("Could not automatically detect RizomUV.")
        if (
            cmds.confirmDialog(
                title="RizomUV Not Found",
                message="Could not detect RizomUV.\nBrowse to executable/app?",
                button=["Browse", "Cancel"],
                defaultButton="Browse",
                cancelButton="Cancel",
                dismissString="Cancel",
            )
            == "Browse"
        ):
            rizomPath = browse_manually(parent_window)
    elif num_found == 1:
        installer_logger.info(f"Detected: {detected_paths[0]}")
        if (
            cmds.confirmDialog(
                title="Confirm RizomUV Path",
                message=f"Use this path?\n\n{detected_paths[0]}",
                button=["Use this Path", "Browse Manually..."],
                defaultButton="Use this Path",
                cancelButton="Browse Manually...",
                dismissString="Browse Manually...",
            )
            == "Use this Path"
        ):
            rizomPath = detected_paths[0]
        else:
            rizomPath = browse_manually(parent_window)
    elif QT_AVAILABLE:
        installer_logger.info(f"Multiple ({num_found}) detected. Showing dialog.")
        selected_path, needs_browse = SelectRizomDialog.get_selection(
            detected_paths, parent_window
        )
        if needs_browse:
            rizomPath = browse_manually(parent_window)
        elif selected_path:
            rizomPath = selected_path
    else:
        installer_logger.error(
            "Multiple RizomUV found, but Qt unavailable for selection."
        )
        if (
            cmds.confirmDialog(
                title="Multiple RizomUV Versions",
                message="Multiple versions found.\nPlease browse manually.",
                button=["Browse", "Cancel"],
                defaultButton="Browse",
                cancelButton="Cancel",
                dismissString="Cancel",
            )
            == "Browse"
        ):
            rizomPath = browse_manually(parent_window)
    if not rizomPath:
        installer_logger.error("No RizomUV path selected.")
        cmds.confirmDialog(
            title="Cancelled", message="RizomUV path selection cancelled.", button="OK"
        )
        return None
    installer_logger.info(f"Using RizomUV path: {rizomPath}")
    if not Path(rizomPath).exists():
        installer_logger.error(f"Path does not exist: {rizomPath}")
        cmds.confirmDialog(
            title="Error", message=f"Path does not exist:\n{rizomPath}", button="OK"
        )
        return None
    system = platform.system()
    valid = False
    if system == "Darwin" and rizomPath.endswith(".app") and Path(rizomPath).is_dir():
        valid = True
    elif (
        system == "Windows"
        and rizomPath.lower().endswith(".exe")
        and Path(rizomPath).is_file()
    ):
        valid = True
    elif (
        system == "Linux"
        and Path(rizomPath).is_file()
        and os.access(rizomPath, os.X_OK)
    ):
        valid = True
    if not valid:
        installer_logger.error(f"Path invalid for {system}: {rizomPath}")
        cmds.confirmDialog(
            title="Error",
            message=f"Path invalid for {system}:\n{rizomPath}",
            button="OK",
        )
        return None
    return rizomPath


def update_settings_json(target_config_path, rizom_path_to_set):
    installer_logger.info(f"Updating settings file: {target_config_path}")
    config_data = {}
    try:
        if target_config_path.is_file():
            config_data = json.loads(target_config_path.read_text(encoding="utf-8"))
            installer_logger.info("  - Loaded existing settings.")
        else:
            installer_logger.info("  - Settings file not found, creating new.")
        config_data["rizomPath"] = rizom_path_to_set
        installer_logger.info(f"  - Set rizomPath to: {rizom_path_to_set}")
        target_config_path.parent.mkdir(parents=True, exist_ok=True)
        target_config_path.write_text(
            json.dumps(config_data, indent=4), encoding="utf-8"
        )
        installer_logger.info(f"  - Saved updated settings to {target_config_path}")
        return True
    except json.JSONDecodeError as e:
        installer_logger.error(
            f"Error decoding '{target_config_path}': {e}. Overwriting."
        )
        config_data = {"rizomPath": rizom_path_to_set}
        try:
            target_config_path.write_text(
                json.dumps(config_data, indent=4), encoding="utf-8"
            )
            installer_logger.info("  - Overwrote settings file.")
            return True
        except Exception as e_write:
            installer_logger.error(f"Failed to overwrite settings file: {e_write}")
            return False
    except Exception as e:
        installer_logger.error(
            f"Failed to update settings file '{target_config_path}': {e}"
        )
        traceback.print_exc()
        return False


def modify_user_setup(add=True):
    user_setup_path = get_user_setup_path()
    if not user_setup_path:
        installer_logger.error("Cannot determine userSetup.py path.")
        return False
    full_module_path = (
        f"{INSTALL_SUBDIR}.{MODULE_NAME}" if INSTALL_SUBDIR else MODULE_NAME
    )
    startup_code = textwrap.dedent(f'''{STARTUP_CODE_START_MARKER}
try:
    _RZM_FULL_MODULE_PATH = "{full_module_path}"
    _RZM_WORKSPACE_CONTROL_NAME = "{WORKSPACE_CONTROL_NAME}"
    def check_and_setup_rizom_bridge_ui(): 
        import maya.cmds as cmds
        import logging
        import traceback
        _us_logger_rzm = logging.getLogger("RizomBridgeUserSetup")
        _us_logger_rzm.info(f"Checking if workspace control \'{{_RZM_WORKSPACE_CONTROL_NAME}}\' exists...")
        try:
            control_exists = cmds.workspaceControl(_RZM_WORKSPACE_CONTROL_NAME, q=True, exists=True)
            _us_logger_rzm.info(f"Control Exists check result: {{control_exists}}")
            if control_exists:
                _us_logger_rzm.info(f"Control exists. Scheduling content setup function...")
                try:
                    deferred_setup_call = f"import {{_RZM_FULL_MODULE_PATH}}; {{ _RZM_FULL_MODULE_PATH}}._setup_panel_content_deferred()"
                    cmds.evalDeferred(deferred_setup_call) 
                    _us_logger_rzm.info(f"Scheduled: {{deferred_setup_call}}")
                except Exception as e_schedule:
                    _us_logger_rzm.error(f"Failed to schedule deferred setup: {{e_schedule}}", exc_info=True)
            else:
                _us_logger_rzm.info(f"Control \'{{_RZM_WORKSPACE_CONTROL_NAME}}\' not found. UI will not auto-load. Use shelf button.")
        except Exception as e_check:
            _us_logger_rzm.error(f"Error checking/scheduling Rizom Bridge UI: {{e_check}}", exc_info=True)
        finally:
            globals().pop(\'_RZM_FULL_MODULE_PATH\', None); globals().pop(\'_RZM_WORKSPACE_CONTROL_NAME\', None)
            globals().pop(\'check_and_setup_rizom_bridge_ui\', None); globals().pop(\'_us_logger_rzm\', None)
    import maya.utils
    if \'check_and_setup_rizom_bridge_ui\' in locals(): maya.utils.executeDeferred(lambda: check_and_setup_rizom_bridge_ui())
    else: print("RizomBridge Error: Startup check function not defined.")
except Exception as e_outer: print(f"[RizomBridge UserSetup] Error: {{e_outer}}"); import traceback; traceback.print_exc()
{STARTUP_CODE_END_MARKER}
''')
    existing_content = []
    found_block = False
    if user_setup_path.is_file():
        try:
            existing_content = user_setup_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        except Exception as e:
            installer_logger.error(f"Error reading userSetup.py: {e}")
            return False
    new_content = []
    in_block = False
    for line in existing_content:
        stripped = line.strip()
        if stripped == STARTUP_CODE_START_MARKER:
            in_block = True
            found_block = True
            continue
        elif stripped == STARTUP_CODE_END_MARKER and in_block:
            in_block = False
            continue
        elif not in_block:
            new_content.append(line)
    if add:
        if found_block:
            installer_logger.info(
                f"  - {INSTALL_SUBDIR} startup logic already exists, overwriting."
            )
        else:
            installer_logger.info(
                f"  - Adding {INSTALL_SUBDIR} startup logic to userSetup.py."
            )
        if new_content and new_content[-1].strip() != "":
            new_content.append("")
        new_content.extend(startup_code.splitlines())
    elif found_block:
        installer_logger.info(
            f"  - Removing {INSTALL_SUBDIR} startup logic from userSetup.py."
        )
    else:
        installer_logger.info(
            f"  - {INSTALL_SUBDIR} startup logic not found. Nothing to remove."
        )
        return True
    try:
        user_setup_path.parent.mkdir(parents=True, exist_ok=True)
        user_setup_path.write_text("\n".join(new_content) + "\n", encoding="utf-8")
        return True
    except Exception as e:
        installer_logger.error(f"Error writing userSetup.py: {e}")
        return False


def remove_shelf_button():
    installer_logger.info(
        f"  - Attempting to remove shelf button: '{SHELF_BUTTON_LABEL}'..."
    )
    found_and_deleted = False
    try:
        # Deletion requires the button's command to reference our module, so an
        # unrelated user button that merely shares the label is left alone.
        controls_to_delete = [
            control
            for control, cmd_string, label_string in _iter_shelf_buttons()
            if MODULE_NAME in cmd_string
        ]
        for btn_to_del in controls_to_delete:
            try:
                if cmds.control(btn_to_del, exists=True):
                    cmds.deleteUI(btn_to_del, control=True)
                    installer_logger.info(f"    - Deleted button '{btn_to_del}'.")
                    found_and_deleted = True
            except Exception as e_del:
                installer_logger.warning(
                    f"    - Could not delete button '{btn_to_del}': {e_del}"
                )
        if not found_and_deleted:
            installer_logger.info("  - Shelf button not found on any shelf.")
    except Exception as e:
        installer_logger.error(f"Error during shelf button removal: {e}")
        traceback.print_exc()
    return found_and_deleted


def create_shelf_button(icon_path="pythonFamily.png"):
    try:
        current_shelf = None
        shelf_tab_layout = mel.eval(
            "global string $gShelfTopLevel; $gShelfTopLevel = $gShelfTopLevel;"
        )
        if cmds.shelfTabLayout(shelf_tab_layout, query=True, exists=True):
            current_shelf = cmds.shelfTabLayout(
                shelf_tab_layout, query=True, selectTab=True
            )
        if not current_shelf or not cmds.shelfLayout(
            current_shelf, query=True, exists=True
        ):
            installer_logger.warning("Could not determine current shelf.")
            default_shelf = "Custom"
            if not cmds.shelfLayout(default_shelf, exists=True):
                installer_logger.info(f"Creating new shelf '{default_shelf}'.")
                mel.eval(f'addNewShelfTab "{default_shelf}";')
            current_shelf = default_shelf
            installer_logger.info(f"Using shelf: '{current_shelf}'")
        buttons = cmds.shelfLayout(current_shelf, query=True, childArray=True) or []
        button_exists = False
        for button in buttons:
            try:
                if cmds.objectTypeUI(button) == "shelfButton" and cmds.shelfButton(
                    button, query=True, exists=True
                ):
                    cmd_string = (
                        cmds.shelfButton(button, query=True, command=True) or ""
                    )
                    label_string = (
                        cmds.shelfButton(button, query=True, label=True) or ""
                    )
                    if MODULE_NAME in cmd_string or label_string == SHELF_BUTTON_LABEL:
                        installer_logger.info(
                            f"  - Button already exists on shelf '{current_shelf}'."
                        )
                        button_exists = True
                        break
            except Exception as e_control:
                installer_logger.debug(
                    f"Skipping unreadable shelf control '{button}': {e_control}"
                )
        if button_exists:
            return True
        module_import_path = (
            f"{INSTALL_SUBDIR}.{MODULE_NAME}" if INSTALL_SUBDIR else MODULE_NAME
        )
        shelf_command = textwrap.dedent(f"""
import {module_import_path}
import importlib
try:
    importlib.reload({module_import_path})
except Exception as e_reload: print(f"Reload failed: {{e_reload}}")
try:
    {module_import_path}.launch_tool()
except Exception as e_launch: print(f"Error launching tool from shelf: {{e_launch}}"); import traceback; traceback.print_exc()
""")
        final_icon_path = icon_path.replace("\\", "/")
        cmds.shelfButton(
            parent=current_shelf,
            label=SHELF_BUTTON_LABEL,
            annotation=SHELF_BUTTON_TOOLTIP,
            image1=final_icon_path,
            command=shelf_command,
            sourceType="python",
            style="iconOnly",
            width=35,
            height=34,
        )
        installer_logger.info(
            f"  - Button added to shelf '{current_shelf}' using icon '{final_icon_path}'."
        )
        return True
    except Exception as e:
        installer_logger.error(f"Error creating shelf button: {e}")
        traceback.print_exc()
        return False


def install_tool(confirmed_rizom_path):
    installer_logger.info(f"\n--- Starting {INSTALL_SUBDIR} Bridge Installation ---")
    try:
        installer_dir = Path(__file__).parent
    except NameError:
        installer_logger.error("Cannot determine installer directory.")
        return False
    source_script_path = installer_dir / SCRIPT_FILE_NAME
    source_icon_path = installer_dir / ICON_FILE_NAME
    scripts_dir = get_maya_scripts_dir()
    if not scripts_dir:
        installer_logger.error("Cannot find Maya scripts directory.")
        return False
    install_target_dir = scripts_dir
    if INSTALL_SUBDIR:
        install_target_dir = scripts_dir / INSTALL_SUBDIR
        try:
            install_target_dir.mkdir(parents=True, exist_ok=True)
            installer_logger.info(
                f"  - Ensured subdirectory exists: {install_target_dir}"
            )
        except Exception as e:
            installer_logger.error(f"Error creating install subdirectory: {e}")
            return False
        init_py_path = install_target_dir / "__init__.py"
        if not init_py_path.exists():
            try:
                init_py_path.write_text(
                    f"# Package marker for {INSTALL_SUBDIR}\n", encoding="utf-8"
                )
                installer_logger.info(f"  - Created package file: {init_py_path}")
            except Exception as e:
                installer_logger.error(f"Error creating __init__.py: {e}")
                return False
    target_script_path = install_target_dir / SCRIPT_FILE_NAME
    target_icon_path = install_target_dir / ICON_FILE_NAME
    target_config_path = install_target_dir / CONFIG_FILE_NAME
    if not source_script_path.is_file():
        installer_logger.error(f"Main script '{SCRIPT_FILE_NAME}' not found.")
        return False
    final_icon_path_for_shelf = "pythonFamily.png"
    if source_icon_path.is_file():
        final_icon_path_for_shelf = str(target_icon_path).replace("\\", "/")
    else:
        installer_logger.warning(
            f"Icon file '{ICON_FILE_NAME}' not found. Using default."
        )
    try:
        installer_logger.info(
            f"  - Copying '{SCRIPT_FILE_NAME}' to '{install_target_dir}'..."
        )
        shutil.copy2(str(source_script_path), str(target_script_path))
        installer_logger.info("  - Script copied successfully.")
    except Exception as e:
        installer_logger.error(f"Error copying script file: {e}")
        traceback.print_exc()
        return False
    if final_icon_path_for_shelf != "pythonFamily.png":
        try:
            installer_logger.info(
                f"  - Copying '{ICON_FILE_NAME}' to '{install_target_dir}'..."
            )
            shutil.copy2(str(source_icon_path), str(target_icon_path))
            installer_logger.info("  - Icon copied successfully.")
        except Exception as e:
            installer_logger.error(f"Error copying icon file: {e}. Using default icon.")
            final_icon_path_for_shelf = "pythonFamily.png"
    source_link_dir = installer_dir / RIZOMUV_LINK_DIR_NAME
    if source_link_dir.is_dir() and platform.system() == "Windows":
        target_link_dir = install_target_dir / RIZOMUV_LINK_DIR_NAME
        try:
            installer_logger.info(
                f"  - Copying '{RIZOMUV_LINK_DIR_NAME}' (live link module) to '{install_target_dir}'..."
            )
            shutil.copytree(
                str(source_link_dir), str(target_link_dir), dirs_exist_ok=True
            )
            installer_logger.info("  - RizomUVLink copied successfully.")
        except Exception as e_link:
            installer_logger.warning(
                f"Could not copy RizomUVLink (live link falls back to the one inside the RizomUV install dir): {e_link}"
            )
    installer_logger.info(
        f"  - Writing Rizom path to settings file: {target_config_path}..."
    )
    if not update_settings_json(target_config_path, confirmed_rizom_path):
        installer_logger.error("Failed to write Rizom path to settings.json.")
        return False
    installer_logger.info("  - Settings file updated successfully.")
    installer_logger.info("  - Modifying userSetup.py...")
    if not modify_user_setup(add=True):
        installer_logger.error("Error modifying userSetup.py.")
        return False
    installer_logger.info("  - userSetup.py modified successfully.")
    installer_logger.info("  - Creating shelf button...")
    if not create_shelf_button(icon_path=final_icon_path_for_shelf):
        installer_logger.warning("Could not create shelf button.")
    else:
        installer_logger.info("  - Shelf button created successfully.")
    install_loc_str = str(install_target_dir).replace("\\", "/")
    cmds.confirmDialog(
        title="Installation Successful",
        message=f"""{INSTALL_SUBDIR} Bridge installed to:
{install_loc_str}
RizomUV Path configured.
Launch from the '{SHELF_BUTTON_LABEL}' button.
(Restart Maya for startup features)""",
        button="OK",
    )
    installer_logger.info(f"\n{INSTALL_SUBDIR} Bridge Installation Completed!")
    installer_logger.info("Please restart Maya for userSetup.py changes.")
    return True


def uninstall_tool(preserve_settings=False):
    """Removes the installed bridge. With preserve_settings=True (used by the
    Reinstall/Update flow) settings.json is kept so user preferences survive."""
    installer_logger.info(f"\n--- Starting {INSTALL_SUBDIR} Bridge Uninstallation ---")
    success = True
    installed_script_path = get_installed_script_path()
    install_target_dir = None
    if installed_script_path:
        install_target_dir = installed_script_path.parent
    if installed_script_path and installed_script_path.is_file():
        try:
            installer_logger.info(f"  - Removing script file: {installed_script_path}")
            installed_script_path.unlink()
            installer_logger.info("  - Script file removed.")
        except Exception as e:
            installer_logger.error(f"Error removing script file: {e}")
            success = False
    else:
        installer_logger.info("  - Script file not found.")
    installed_icon_path = get_installed_icon_path()
    if installed_icon_path and installed_icon_path.is_file():
        try:
            installer_logger.info(f"  - Removing icon file: {installed_icon_path}")
            installed_icon_path.unlink()
            installer_logger.info("  - Icon file removed.")
        except Exception as e:
            installer_logger.error(f"Error removing icon file: {e}")
            success = False
    else:
        installer_logger.info("  - Icon file not found.")
    if install_target_dir and install_target_dir.is_dir():
        target_config_path = install_target_dir / CONFIG_FILE_NAME
        if preserve_settings:
            installer_logger.info(
                f"  - Keeping settings file (update in progress): {target_config_path}"
            )
        elif target_config_path.is_file():
            try:
                installer_logger.info(
                    f"  - Removing settings file: {target_config_path}"
                )
                target_config_path.unlink()
                installer_logger.info("  - Settings file removed.")
            except Exception as e:
                installer_logger.error(
                    f"Error removing settings file '{target_config_path}': {e}"
                )
                success = False
        else:
            installer_logger.info(
                f"  - Settings file not found at {target_config_path}."
            )
    if install_target_dir and install_target_dir.is_dir():
        init_py = install_target_dir / "__init__.py"
        if init_py.is_file():
            try:
                installer_logger.info(f"  - Removing package file: {init_py}")
                init_py.unlink()
            except Exception as e:
                installer_logger.warning(f"Error removing __init__.py file: {e}")
        runtime_files = [
            install_target_dir / FBX_FILE_NAME,
            install_target_dir / LUA_SCRIPT_FILE_NAME,
            install_target_dir / LIVE_LUA_SCRIPT_FILE_NAME,
            install_target_dir / STATE_FILE_NAME,
        ]
        runtime_files.extend(install_target_dir.glob("settings.corrupt_*.bak"))
        for runtime_file in runtime_files:
            if runtime_file.is_file():
                try:
                    installer_logger.info(f"  - Removing runtime file: {runtime_file}")
                    runtime_file.unlink()
                except Exception as e:
                    installer_logger.warning(
                        f"Error removing runtime file '{runtime_file}': {e}"
                    )
        for runtime_dir in ("__pycache__", RIZOMUV_LINK_DIR_NAME):
            dir_path = install_target_dir / runtime_dir
            if dir_path.is_dir():
                try:
                    installer_logger.info(f"  - Removing directory: {dir_path}")
                    shutil.rmtree(str(dir_path))
                except Exception as e:
                    installer_logger.warning(
                        f"Error removing directory '{dir_path}': {e}. If the live "
                        f"link was used this session its DLLs are locked by Maya — "
                        f"restart Maya and delete the folder manually."
                    )
    if INSTALL_SUBDIR and install_target_dir and install_target_dir.is_dir():
        try:
            if not any(install_target_dir.iterdir()):
                installer_logger.info(
                    f"  - Removing empty subdirectory: {install_target_dir}"
                )
                install_target_dir.rmdir()
                installer_logger.info("  - Removed empty subdirectory.")
            else:
                installer_logger.info(
                    f"  - Info: Subdirectory {install_target_dir} not empty, leaving it."
                )
        except OSError as e_os:
            installer_logger.info(
                f"  - Info: Subdirectory {install_target_dir} could not be removed (might still contain files or lack permissions): {e_os}"
            )
        except Exception as e:
            installer_logger.warning(
                f"  - Warning: Error checking/removing subdirectory {install_target_dir}: {e}"
            )
    installer_logger.info(
        f"  - Modifying userSetup.py to remove {INSTALL_SUBDIR} block..."
    )
    if not modify_user_setup(add=False):
        installer_logger.warning(
            "Could not fully remove logic from userSetup.py (or block not found)."
        )
    else:
        installer_logger.info(
            "  - userSetup.py modification successful (or block not found)."
        )
    installer_logger.info("  - Removing shelf button (if found)...")
    remove_shelf_button()
    if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, q=True, exists=True):
        installer_logger.info(
            f"  - Closing/deleting workspace control: {WORKSPACE_CONTROL_NAME}"
        )
        try:
            cmds.deleteUI(WORKSPACE_CONTROL_NAME, control=True)
            installer_logger.info("   - Workspace control deleted.")
        except Exception as e:
            installer_logger.warning(
                f"  - Warning: Could not delete workspace control: {e}"
            )
    if success:
        installer_logger.info(f"\n{INSTALL_SUBDIR} Bridge Uninstallation Completed.")
        print("Please restart Maya for changes to fully take effect.")
    else:
        installer_logger.warning(
            f"\n{INSTALL_SUBDIR} Bridge Uninstallation finished with issues."
        )
        print("Please check logs above and restart Maya.")
    return success


def run_main_logic():
    status = check_installation()
    maya_window = get_maya_main_window()
    if status == "installed":
        result = cmds.confirmDialog(
            title=f"{INSTALL_SUBDIR} Bridge Installed",
            message=f"{INSTALL_SUBDIR} Bridge installed.\nChoose action:",
            button=["Reinstall/Update", "Uninstall", "Cancel"],
            defaultButton="Cancel",
            cancelButton="Cancel",
            dismissString="Cancel",
        )
        if result == "Reinstall/Update":
            installer_logger.info("--- Starting Reinstallation ---")
            if uninstall_tool(preserve_settings=True):
                confirmed_path = confirm_rizom_path(maya_window)
                if confirmed_path:
                    install_tool(confirmed_path)
                else:
                    installer_logger.error("Path confirm failed. Reinstall aborted.")
            else:
                installer_logger.error("Uninstall failed. Reinstall aborted.")
        elif result == "Uninstall":
            installer_logger.info("--- Starting Uninstallation ---")
            uninstall_tool()
        else:
            installer_logger.info("Operation cancelled.")
    elif status == "partially_installed":
        result = cmds.confirmDialog(
            title=f"{INSTALL_SUBDIR} Bridge Partially Installed?",
            message=f"{INSTALL_SUBDIR} Bridge partially installed.\nChoose action:",
            button=["Attempt Reinstall", "Attempt Uninstall", "Cancel"],
            defaultButton="Cancel",
            cancelButton="Cancel",
            dismissString="Cancel",
        )
        if result == "Attempt Reinstall":
            installer_logger.info("--- Attempting Reinstallation ---")
            uninstall_tool(preserve_settings=True)
            confirmed_path = confirm_rizom_path(maya_window)
            if confirmed_path:
                install_tool(confirmed_path)
            else:
                installer_logger.error("Path confirm failed. Reinstall aborted.")
        elif result == "Attempt Uninstall":
            installer_logger.info("--- Attempting Uninstallation ---")
            uninstall_tool()
        else:
            installer_logger.info("Operation cancelled.")
    elif status == "not_installed":
        installer_logger.info(
            f"{INSTALL_SUBDIR} Bridge not detected. Confirming RizomUV path..."
        )
        confirmed_path = confirm_rizom_path(maya_window)
        if not confirmed_path:
            installer_logger.error("RizomUV path needed. Install aborted.")
            return
        install_message = f"""Install {INSTALL_SUBDIR} Bridge ({MODULE_NAME})?
This will:
- Copy files to: {get_maya_scripts_dir() / INSTALL_SUBDIR}
- Save RizomUV path: {confirmed_path}
- Modify userSetup.py.
- Add shelf button."""
        result = cmds.confirmDialog(
            title=f"Install {INSTALL_SUBDIR} Bridge?",
            message=install_message,
            button=["Install", "Cancel"],
            defaultButton="Install",
            cancelButton="Cancel",
            dismissString="Cancel",
        )
        if result == "Install":
            install_tool(confirmed_path)
        else:
            installer_logger.info("Installation cancelled.")


def onMayaDroppedPythonFile(*args):
    installer_logger.info(f"\n{INSTALL_SUBDIR} Bridge Installer: Detected drop event.")
    try:
        if cmds.about(batch=True):
            installer_logger.error(
                f"{INSTALL_SUBDIR} Installer: Cannot run in batch mode."
            )
            return
        try:
            installer_dir = Path(__file__).parent
        except NameError:
            cmds.confirmDialog(
                title="Error",
                icon="critical",
                message="Cannot determine installer location.",
            )
            return
        source_script = installer_dir / SCRIPT_FILE_NAME
        source_icon = installer_dir / ICON_FILE_NAME
        if not source_script.is_file():
            cmds.confirmDialog(
                title="Error",
                icon="critical",
                message=f"Script '{SCRIPT_FILE_NAME}' not found.",
            )
            return
        if not source_icon.is_file():
            if (
                cmds.confirmDialog(
                    title="Warning",
                    icon="warning",
                    message=f"Icon '{ICON_FILE_NAME}' not found.\nContinue with default icon?",
                    button=["Continue", "Cancel"],
                )
                == "Cancel"
            ):
                installer_logger.info("Cancelled.")
                return
        run_main_logic()
    except Exception as e_main:
        installer_logger.error(f"Unexpected error: {e_main}")
        traceback.print_exc()
        try:
            cmds.confirmDialog(
                title="Error",
                icon="critical",
                message=f"Unexpected error:\n{e_main}\n\nSee script editor.",
                button="OK",
            )
        except:
            pass
