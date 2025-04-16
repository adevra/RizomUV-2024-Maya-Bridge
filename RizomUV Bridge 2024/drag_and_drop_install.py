import os
import shutil
import maya.cmds as cmds
import maya.mel as mel
import platform
import sys
import logging
import glob
import subprocess
import locale

try:
    if sys.version_info.major >= 3 and sys.version_info.minor >= 11:
        from PySide6 import QtWidgets, QtCore, QtGui

        logging.info("Using PySide6 for installer dialogs")
    else:
        from PySide2 import QtWidgets, QtCore, QtGui

        logging.info("Using PySide2 for installer dialogs")
    QT_AVAILABLE = True
except ImportError as e:
    QT_AVAILABLE = False
    logging.error(
        f"Could not import PySide2 or PySide6: {e}. Auto-detection selection UI unavailable."
    )
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_maya_main_window():
    if not QT_AVAILABLE:
        return None
    try:
        import maya.OpenMayaUI as omui

        if sys.version_info.major >= 3 and sys.version_info.minor >= 11:
            from shiboken6 import wrapInstance
        else:
            from shiboken2 import wrapInstance
        main_window_ptr = omui.MQtUtil.mainWindow()
        if main_window_ptr is not None:
            return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)
    except Exception as e:
        logging.error(f"Could not get Maya main window: {e}")
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
        logging.warning(f"Command not found: {cmd_list[0]}")
        return "", f"Command not found: {cmd_list[0]}", -1
    except Exception as e:
        logging.error(f"Error running command '{' '.join(cmd_list)}': {e}")
        return "", str(e), -1


def find_rizomuv_installations():
    system = platform.system()
    found_paths = set()
    logging.info("Attempting to detect RizomUV installations...")
    if system == "Windows":
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get(
            "ProgramFiles(x86)", r"C:\Program Files (x86)"
        )
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        search_patterns = [
            os.path.join(program_files, r"Rizom Lab\RizomUV*\rizomuv.exe"),
            os.path.join(program_files_x86, r"Rizom Lab\RizomUV*\rizomuv.exe"),
        ]
        if local_app_data:
            search_patterns.append(
                os.path.join(local_app_data, r"Programs\Rizom Lab\RizomUV*\rizomuv.exe")
            )
        for pattern in search_patterns:
            for path in glob.glob(pattern):
                if os.path.isfile(path):
                    found_paths.add(os.path.normpath(path))
                    logging.info(f"Found potential Windows path: {path}")
    elif system == "Darwin":
        bundle_id = "com.rizom-lab.rizomuv"
        cmd = ["mdfind", f'kMDItemCFBundleIdentifier == "{bundle_id}"']
        stdout, stderr, code = run_command(cmd)
        if code == 0 and stdout:
            for line in stdout.strip().split("\n"):
                path = line.strip()
                if path.endswith(".app") and os.path.isdir(path):
                    found_paths.add(os.path.normpath(path))
                    logging.info(f"Found via mdfind: {path}")
        search_patterns = [
            "/Applications/RizomUV*.app",
            os.path.expanduser("~/Applications/RizomUV*.app"),
        ]
        for pattern in search_patterns:
            for path in glob.glob(pattern):
                if os.path.isdir(path):
                    found_paths.add(os.path.normpath(path))
                    logging.info(f"Found potential macOS path: {path}")
    elif system == "Linux":
        stdout, stderr, code = run_command(["which", "rizomuv"])
        if code == 0 and stdout:
            path = stdout.strip()
            if os.path.isfile(path) and os.access(path, os.X_OK):
                found_paths.add(os.path.normpath(path))
                logging.info(f"Found via which: {path}")
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
                    logging.info(f"Found potential Linux path: {path}")
    logging.info(
        f"Detection finished. Found {len(found_paths)} potential installations."
    )
    return sorted(list(found_paths))


def browse_manually(parent_window):
    system = platform.system()
    file_filter = ""
    default_path_dir = ""
    selected_path = None
    logging.info("Opening manual browse dialog...")
    if system == "Windows":
        file_filter = "RizomUV Executable (rizomuv.exe)"
        default_path = r"C:\Program Files\Rizom Lab\RizomUV 2024.0\rizomuv.exe"
        default_path_dir = (
            os.path.dirname(default_path)
            if os.path.exists(default_path)
            else r"C:\Program Files"
        )
        qfile_filter = f"{file_filter};;All Files (*)"
        path_tuple = QtWidgets.QFileDialog.getOpenFileName(
            parent_window, "Select RizomUV Executable", default_path_dir, qfile_filter
        )
        if path_tuple and path_tuple[0]:
            selected_path = path_tuple[0]
    elif system == "Darwin":
        file_filter = "RizomUV Application (*.app)"
        default_path = "/Applications/RizomUV 2024.1.app"
        default_path_dir = (
            os.path.dirname(default_path)
            if os.path.exists(default_path)
            else "/Applications"
        )
        path_tuple = QtWidgets.QFileDialog.getOpenFileName(
            parent_window,
            "Select RizomUV Application (.app)",
            default_path_dir,
            "Applications (*.app)",
        )
        if path_tuple and path_tuple[0]:
            selected_path = path_tuple[0]
    else:
        file_filter = "RizomUV Executable or AppImage"
        default_path = "/usr/local/bin/rizomuv"
        default_path_dir = (
            os.path.dirname(default_path) if os.path.exists(default_path) else "/"
        )
        qfile_filter = f"{file_filter} (*);;All Files (*)"
        path_tuple = QtWidgets.QFileDialog.getOpenFileName(
            parent_window,
            "Select RizomUV Executable/AppImage",
            default_path_dir,
            qfile_filter,
        )
        if path_tuple and path_tuple[0]:
            selected_path = path_tuple[0]
    if selected_path:
        logging.info(f"Manual selection: {selected_path}")
        return selected_path
    else:
        logging.info("Manual browse cancelled.")
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
            logging.warning("OK clicked but no item selected in dialog.")

    def browse_selection(self):
        self.do_browse = True
        self.reject()

    @staticmethod
    def get_selection(paths, parent):
        dialog = SelectRizomDialog(paths, parent)
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.selected_path, False
        elif dialog.do_browse:
            return None, True
        else:
            return None, False


def onMayaDroppedPythonFile(*args):
    system = platform.system()
    rizomPath = None
    try:
        logging.info("Starting RizomUV Bridge installer...")
        installer_directory = os.path.dirname(__file__)
        script_file_path = os.path.join(installer_directory, "maya_rizomuv_bridge.py")
        shelf_icon_path = os.path.join(installer_directory, "rzmuv.png")
        if not os.path.exists(script_file_path):
            raise FileNotFoundError(
                "Unable to find 'maya_rizomuv_bridge.py' relative to this installer"
            )
        if not os.path.exists(shelf_icon_path):
            raise FileNotFoundError(
                "Unable to find 'rzmuv.png' relative to this installer"
            )
        maya_window = get_maya_main_window()
        detected_paths = find_rizomuv_installations()
        num_found = len(detected_paths)
        if num_found == 0:
            logging.warning(
                "Could not automatically detect RizomUV. Please browse manually."
            )
            cmds.confirmDialog(
                title="RizomUV Not Found",
                message="Could not automatically detect a RizomUV installation.\nPlease browse to the RizomUV executable or application (.app).",
                button=["OK"],
                defaultButton="OK",
            )
            rizomPath = browse_manually(maya_window)
            if not rizomPath:
                raise RuntimeError("Manual selection cancelled or failed.")
        elif num_found == 1:
            logging.info(f"Detected one RizomUV installation: {detected_paths[0]}")
            result = cmds.confirmDialog(
                title="Confirm RizomUV Path",
                message=f"Detected RizomUV at:\n\n{detected_paths[0]}\n\nUse this path?",
                button=["Use this Path", "Browse Manually..."],
                defaultButton="Use this Path",
                cancelButton="Browse Manually...",
                dismissString="Browse Manually...",
            )
            if result == "Use this Path":
                rizomPath = detected_paths[0]
            else:
                rizomPath = browse_manually(maya_window)
                if not rizomPath:
                    raise RuntimeError("Manual selection cancelled or failed.")
        else:
            if not QT_AVAILABLE:
                logging.error(
                    "Multiple RizomUV versions detected, but Qt unavailable to show selection dialog."
                )
                cmds.confirmDialog(
                    title="Multiple RizomUV Versions",
                    message="Multiple RizomUV versions detected, but the selection dialog cannot be shown.\nPlease browse manually.",
                    button=["OK"],
                    defaultButton="OK",
                )
                rizomPath = browse_manually(None)
                if not rizomPath:
                    raise RuntimeError("Manual selection cancelled or failed.")
            else:
                logging.info(
                    f"Multiple ({num_found}) RizomUV installations detected. Showing selection dialog."
                )
                selected_path_from_dialog, needs_browse = (
                    SelectRizomDialog.get_selection(detected_paths, maya_window)
                )
                if needs_browse:
                    rizomPath = browse_manually(maya_window)
                    if not rizomPath:
                        raise RuntimeError("Manual selection cancelled or failed.")
                elif selected_path_from_dialog:
                    rizomPath = selected_path_from_dialog
                else:
                    raise RuntimeError("RizomUV selection cancelled.")
        if not rizomPath:
            raise RuntimeError("Failed to determine RizomUV path.")
        logging.info(f"Using RizomUV path: {rizomPath}")
        if not os.path.exists(rizomPath):
            raise RuntimeError(f"Selected path does not exist: {rizomPath}")
        if system == "Darwin":
            if not rizomPath.endswith(".app") or not os.path.isdir(rizomPath):
                raise RuntimeError(
                    f"Invalid selection on macOS. Path must be an application bundle ending in .app. Selected: {rizomPath}"
                )
        elif system == "Windows" and not rizomPath.lower().endswith(".exe"):
            raise RuntimeError(
                f"Invalid selection on Windows. Path must be an executable file ending in .exe. Selected: {rizomPath}"
            )
        elif system == "Linux":
            if not os.path.isfile(rizomPath) or not os.access(rizomPath, os.X_OK):
                raise RuntimeError(
                    f"Selected path on Linux is not an executable file (or AppImage). Check permissions. Selected: {rizomPath}"
                )
        with open(script_file_path, "r") as file:
            script_content = file.read()
        placeholder = "PATH_DEFAULTS = {"
        if placeholder in script_content:
            windows_path_escaped = (
                rizomPath.replace("\\", "\\\\")
                if system == "Windows"
                else r"C:\\Program Files\\Rizom Lab\\RizomUV 2024.0\\rizomuv.exe"
            )
            darwin_path = (
                rizomPath if system == "Darwin" else "/Applications/RizomUV 2024.1.app"
            )
            linux_path = rizomPath if system == "Linux" else "/usr/local/bin/rizomuv"
            new_default_paths = (
                "PATH_DEFAULTS = {\n"
                f'    "Windows": r"{windows_path_escaped}",\n'
                f'    "Darwin": "{darwin_path}",\n'
                f'    "Linux": "{linux_path}"\n'
                "}"
            )
            start_idx = script_content.index(placeholder)
            end_idx = script_content.index("}", start_idx) + 1
            script_content = (
                script_content[:start_idx]
                + new_default_paths
                + script_content[end_idx:]
            )
            logging.info("Updated PATH_DEFAULTS in script content.")
        else:
            raise RuntimeError(
                "PATH_DEFAULTS dictionary placeholder not found in the main script. Cannot set path."
            )
        updated_script_file_path = os.path.join(
            installer_directory, "maya_rizomuv_bridge_updated.py"
        )
        with open(updated_script_file_path, "w") as file:
            file.write(script_content)
        prefs_dir = os.path.dirname(cmds.about(preferences=True))
        scripts_dir = os.path.normpath(os.path.join(prefs_dir, "scripts"))
        if not os.path.exists(scripts_dir):
            os.makedirs(scripts_dir)
            logging.info(f"Created scripts directory: {scripts_dir}")
        target_script_path = os.path.join(scripts_dir, "maya_rizomuv_bridge.py")
        target_icon_path = os.path.join(scripts_dir, "rzmuv.png")
        shutil.copy(updated_script_file_path, target_script_path)
        shutil.copy(shelf_icon_path, target_icon_path)
        logging.info(f"Files copied to: {scripts_dir}")
        os.remove(updated_script_file_path)
        logging.info("Removed temporary updated script file.")
        absolute_shelf_icon_path = target_icon_path.replace("\\", "/")
        current_shelf = mel.eval(
            "string $currentShelf = `tabLayout -query -selectTab $gShelfTopLevel`;"
        )
        if not current_shelf:
            if not cmds.shelfLayout("Custom", exists=True):
                mel.eval('addNewShelfTab "Custom";')
            current_shelf = "Custom"
            logging.warning(
                "Could not determine current shelf, using/creating 'Custom' shelf."
            )
        cmds.setParent(current_shelf)
        button_label = "RizomUVBridge"
        shelf_buttons = (
            cmds.shelfLayout(current_shelf, query=True, childArray=True) or []
        )
        button_exists = False
        for button in shelf_buttons:
            try:
                cmd_query = cmds.shelfButton(button, query=True, command=True)
                if "maya_rizomuv_bridge.launch_tool" in cmd_query:
                    button_exists = True
                    logging.warning(
                        f"RizomUV Bridge button already seems to exist on shelf '{current_shelf}'. Skipping creation."
                    )
                    break
            except Exception:
                continue
        if not button_exists:
            shelf_command = "import importlib; import maya_rizomuv_bridge; importlib.reload(maya_rizomuv_bridge); maya_rizomuv_bridge.launch_tool()"
            cmds.shelfButton(
                enableCommandRepeat=True,
                enable=True,
                width=35,
                height=34,
                manage=True,
                visible=True,
                preventOverride=False,
                annotation="RizomUV Bridge",
                label=button_label,
                enableBackground=False,
                align="center",
                image=absolute_shelf_icon_path,
                image1=absolute_shelf_icon_path,
                style="iconOnly",
                marginWidth=1,
                marginHeight=1,
                command=shelf_command,
            )
            logging.info("Shelf button created successfully.")
        cmds.confirmDialog(
            message=f"RizomUV Bridge successfully installed to:\n{scripts_dir}\n\nRizomUV Path set to:\n{rizomPath}\n\nLaunch it from the '{current_shelf}' shelf.\n(Restart Maya if the button command doesn't work immediately)",
            title="Installation Successful",
        )
        logging.info("Installation successful.")
    except FileNotFoundError as e:
        cmds.confirmDialog(
            message=f"File error during installation:\n{e}",
            icon="critical",
            title="ERROR",
        )
        logging.error(f"File not found: {e}")
    except PermissionError as e:
        cmds.confirmDialog(
            message=f"Permission denied:\n{e}\nEnsure you have write access to Maya’s scripts directory.",
            icon="critical",
            title="ERROR",
        )
        logging.error(f"Permission error: {e}")
    except RuntimeError as e:
        cmds.confirmDialog(
            message=f"Installation failed:\n{e}", icon="critical", title="ERROR"
        )
        logging.error(f"Runtime error: {e}")
    except ImportError as e:
        try:
            cmds.confirmDialog(
                message=f"Failed to import Qt bindings. Cannot show UI elements.\n{e}",
                icon="critical",
                title="ERROR",
            )
        except Exception:
            pass
    except Exception as e:
        cmds.confirmDialog(
            message=f"Unexpected error during installation:\n{e}",
            icon="critical",
            title="ERROR",
        )
        logging.exception("Unexpected installation error:")


if __name__ == "__main__":
    pass
