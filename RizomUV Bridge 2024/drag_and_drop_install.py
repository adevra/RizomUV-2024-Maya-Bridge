import os
import shutil
import maya.cmds as cmds
import maya.mel as mel
import platform
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def onMayaDroppedPythonFile(*args):
    original_os_native_dialog_pref = 0
    system = platform.system()
    mac_pref_changed = False

    try:
        logging.info("Starting RizomUV Bridge installer...")
        installer_directory = os.path.dirname(__file__)
        script_file_path = os.path.join(installer_directory, "maya_rizomuv_bridge.py")
        shelf_icon_path = os.path.join(installer_directory, "rzmuv.png")

        if not os.path.exists(script_file_path):
            raise FileNotFoundError("Unable to find 'maya_rizomuv_bridge.py' relative to this installer")
        if not os.path.exists(shelf_icon_path):
            raise FileNotFoundError("Unable to find 'rzmuv.png' relative to this installer")

        file_filter = ""
        default_path_dir = ""

        if system == "Windows":
            file_filter = "RizomUV Executable (rizomuv.exe)"
            default_path = r"C:\Program Files\Rizom Lab\RizomUV 2024.0\rizomuv.exe"
            default_path_dir = os.path.dirname(default_path) if os.path.exists(default_path) else r"C:\Program Files"
        elif system == "Darwin":
            file_filter = "RizomUV Application (*.app)"
            default_path = "/Applications/RizomUV 2024.1.app"
            default_path_dir = os.path.dirname(default_path) if os.path.exists(default_path) else "/Applications"
            try:
                original_os_native_dialog_pref = cmds.optionVar(query="useOSNativeFileDialog")
                if original_os_native_dialog_pref == 0:
                    logging.info("Temporarily switching Maya to OS Native file dialog for .app selection.")
                    cmds.optionVar(iv=("useOSNativeFileDialog", 1))
                    mac_pref_changed = True
            except Exception as e:
                logging.warning(f"Could not query/set OS native dialog preference: {e}")
        else:
            file_filter = "RizomUV Executable"
            default_path = "/usr/local/bin/rizomuv"
            default_path_dir = os.path.dirname(default_path) if os.path.exists(default_path) else "/"

        dialog_result = cmds.fileDialog2(
            fileMode=1,
            caption="Select RizomUV Executable or Application (.app)",
            fileFilter=file_filter,
            startingDirectory=default_path_dir,
            dialogStyle=2
        )

        if not dialog_result:
            raise RuntimeError("No RizomUV executable or application selected.")
        rizomPath = dialog_result[0]

        if not os.path.exists(rizomPath):
            raise RuntimeError(f"Selected path does not exist: {rizomPath}")

        if system == "Darwin":
            if not rizomPath.endswith(".app") or not os.path.isdir(rizomPath):
                raise RuntimeError(f"Invalid selection on macOS. Please select the RizomUV application bundle (e.g., RizomUV.app). Selected: {rizomPath}")
        elif system == "Windows" and not rizomPath.lower().endswith(".exe"):
            raise RuntimeError(f"Invalid selection on Windows. Please select the RizomUV executable (.exe). Selected: {rizomPath}")
        elif system == "Linux" and not os.access(rizomPath, os.X_OK):
            if not os.path.isfile(rizomPath) or not os.access(rizomPath, os.X_OK):
                raise RuntimeError(f"Selected path on Linux is not an executable file. Check permissions. Selected: {rizomPath}")

        logging.info(f"Selected RizomUV path: {rizomPath}")

        with open(script_file_path, 'r') as file:
            script_content = file.read()

        placeholder = 'PATH_DEFAULTS = {'
        if placeholder in script_content:
            windows_path_escaped = rizomPath.replace("\\", "\\\\") if system == "Windows" else r"C:\\Program Files\\Rizom Lab\\RizomUV 2024.0\\rizomuv.exe"
            darwin_path = rizomPath if system == "Darwin" else "/Applications/RizomUV 2024.1.app"
            linux_path = rizomPath if system == "Linux" else "/usr/local/bin/rizomuv"
            new_default_paths = (
                'PATH_DEFAULTS = {\n'
                f'    "Windows": r"{windows_path_escaped}",\n'
                f'    "Darwin": "{darwin_path}",\n'
                f'    "Linux": "{linux_path}"\n'
                '}'
            )
            start_idx = script_content.index(placeholder)
            end_idx = script_content.index('}', start_idx) + 1
            script_content = script_content[:start_idx] + new_default_paths + script_content[end_idx:]
            logging.info("Updated PATH_DEFAULTS in script content.")
        else:
            raise RuntimeError("PATH_DEFAULTS dictionary not found in the script.")

        updated_script_file_path = os.path.join(installer_directory, "maya_rizomuv_bridge_updated.py")
        with open(updated_script_file_path, 'w') as file:
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
        current_shelf = mel.eval("string $currentShelf = `tabLayout -query -selectTab $gShelfTopLevel`;")
        if not current_shelf:
            if not cmds.shelfLayout("Custom", exists=True):
                mel.eval('addNewShelfTab "Custom";')
            current_shelf = "Custom"
            logging.warning("Could not determine current shelf, using/creating 'Custom' shelf.")

        cmds.setParent(current_shelf)
        button_label = "RizomUVBridge"
        shelf_buttons = cmds.shelfLayout(current_shelf, query=True, childArray=True) or []
        button_exists = False
        for button in shelf_buttons:
            try:
                cmd_query = cmds.shelfButton(button, query=True, command=True)
                if "maya_rizomuv_bridge.launch_tool" in cmd_query:
                    button_exists = True
                    logging.warning(f"RizomUV Bridge button already seems to exist on shelf '{current_shelf}'. Skipping creation.")
                    break
            except Exception:
                continue

        if not button_exists:
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
                command="import maya_rizomuv_bridge; reload(maya_rizomuv_bridge); maya_rizomuv_bridge.launch_tool()"
            )
            logging.info("Shelf button created successfully.")

        cmds.confirmDialog(
            message=f"RizomUV Bridge successfully installed to:\n{scripts_dir}\n\nLaunch it from the '{current_shelf}' shelf.\n(Restart Maya if the button command doesn't work immediately)",
            title="Installation Successful"
        )

    except FileNotFoundError as e:
        cmds.confirmDialog(message=f"File error during installation:\n{e}", icon="critical", title="ERROR")
        logging.error(f"File not found: {e}")
    except PermissionError as e:
        cmds.confirmDialog(message=f"Permission denied:\n{e}\nEnsure you have write access to Maya’s scripts directory.", icon="critical", title="ERROR")
        logging.error(f"Permission error: {e}")
    except RuntimeError as e:
        cmds.confirmDialog(message=f"Installation failed:\n{e}", icon="critical", title="ERROR")
        logging.error(f"Runtime error: {e}")
    except Exception as e:
        cmds.confirmDialog(message=f"Unexpected error during installation:\n{e}", icon="critical", title="ERROR")
        logging.exception("Unexpected installation error:")
    finally:
        if mac_pref_changed:
            try:
                logging.info(f"Restoring Maya file dialog preference to original value: {original_os_native_dialog_pref}")
                cmds.optionVar(iv=("useOSNativeFileDialog", original_os_native_dialog_pref))
            except Exception as e:
                logging.warning(f"Could not restore OS native dialog preference: {e}")

if __name__ == "__main__":
    pass