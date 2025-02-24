import os
import shutil
import maya.cmds as cmds
import maya.mel as mel
import platform
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def onMayaDroppedPythonFile(*args):
    try:
        logging.info("Starting RizomUV Bridge installer...")

        installer_directory = os.path.dirname(__file__)
        script_file_path = os.path.join(installer_directory, "maya_rizomuv_bridge.py")
        shelf_icon_path = os.path.join(installer_directory, "rzmuv.png")
        
        if not os.path.exists(script_file_path):
            raise FileNotFoundError("Unable to find 'maya_rizomuv_bridge.py' relative to this installer")
        if not os.path.exists(shelf_icon_path):
            raise FileNotFoundError("Unable to find 'rzmuv.png' relative to this installer")

        system = platform.system()
        if system == "Windows":
            file_filter = "Executable Files (*.exe)"
            default_path = r"C:\Program Files\Rizom Lab\RizomUV 2024.0\rizomuv.exe"
        elif system == "Darwin":
            file_filter = "Applications (*.app)"
            default_path = "/Applications/RizomUV 2024.1.app"
        else:  # Linux
            file_filter = "Executable Files (*)"
            default_path = "/usr/local/bin/rizomuv"
        
        rizomPath = cmds.fileDialog2(fileMode=1, caption="Select RizomUV Executable", fileFilter=file_filter, 
                                    startingDirectory=os.path.dirname(default_path))[0]
        if not rizomPath:
            raise RuntimeError("No RizomUV executable selected.")

        if system == "Darwin" and not rizomPath.endswith(".app"):
            logging.warning("Selected path on macOS should end with '.app'. Attempting to proceed...")
        elif system == "Windows" and not rizomPath.lower().endswith(".exe"):
            logging.warning("Selected path on Windows should end with '.exe'. Attempting to proceed...")
        elif system == "Linux" and not os.access(rizomPath, os.X_OK):
            raise RuntimeError("Selected path on Linux is not executable. Check permissions.")

        with open(script_file_path, 'r') as file:
            script_content = file.read()

        placeholder = 'PATH_DEFAULTS = {'
        if placeholder in script_content:
            windows_path = rizomPath if system == "Windows" else r"C:\Program Files\Rizom Lab\RizomUV 2024.0\rizomuv.exe"
            darwin_path = rizomPath if system == "Darwin" else "/Applications/RizomUV 2024.1.app"
            linux_path = rizomPath if system == "Linux" else "/usr/local/bin/rizomuv"
            new_default_paths = (
                'PATH_DEFAULTS = {\n'
                '    "Windows": r"' + windows_path + '",\n'
                '    "Darwin": "' + darwin_path + '",\n'
                '    "Linux": "' + linux_path + '"\n'
                '}'
            )
            start_idx = script_content.index(placeholder)
            end_idx = script_content.index('}', start_idx) + 1
            script_content = script_content[:start_idx] + new_default_paths + script_content[end_idx:]
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

        shutil.copy(updated_script_file_path, os.path.join(scripts_dir, "maya_rizomuv_bridge.py"))
        shutil.copy(shelf_icon_path, os.path.join(scripts_dir, "rzmuv.png"))
        logging.info(f"Files copied to: {scripts_dir}")

        # Clean up temporary file
        os.remove(updated_script_file_path)
        logging.info("Removed temporary updated script file.")

        absolute_shelf_icon_path = os.path.join(scripts_dir, "rzmuv.png").replace("\\", "/")
        current_shelf = mel.eval("string $currentShelf = `tabLayout -query -selectTab $gShelfTopLevel`;")
        if not current_shelf:
            current_shelf = "Custom"  # Fallback shelf name
            logging.warning("Could not determine current shelf, using 'Custom' shelf.")
        
        cmds.setParent(current_shelf)
        cmds.shelfButton(
            enableCommandRepeat=True,
            enable=True,
            width=35,
            height=34,
            manage=True,
            visible=True,
            preventOverride=False,
            annotation="RizomUV Bridge",
            enableBackground=False,
            backgroundColor=(0, 0, 0),
            highlightColor=(0.321569, 0.521569, 0.65098),
            align="center",
            labelOffset=0,
            rotation=0,
            flipX=False,
            flipY=False,
            useAlpha=True,
            overlayLabelColor=(1, 1, 1),
            overlayLabelBackColor=(0, 0, 0, 0),
            image=absolute_shelf_icon_path,
            image1=absolute_shelf_icon_path,
            style="iconOnly",
            marginWidth=1,
            marginHeight=1,
            command="import maya_rizomuv_bridge; maya_rizomuv_bridge.launch_tool()"
        )
        logging.info("Shelf button created successfully.")

        cmds.confirmDialog(message=f"Script successfully installed to: {scripts_dir}\nLaunch it from the shelf or via Script Editor with `import maya_rizomuv_bridge; maya_rizomuv_bridge.launch_tool()`", 
                          title="Installation Successful")

    except FileNotFoundError as e:
        cmds.confirmDialog(message=f"File error during installation: {e}", icon="warning", title="ERROR")
        logging.error(f"File not found: {e}")
    except PermissionError as e:
        cmds.confirmDialog(message=f"Permission denied: {e}\nEnsure you have write access to Maya’s scripts directory.", icon="warning", title="ERROR")
        logging.error(f"Permission error: {e}")
    except RuntimeError as e:
        cmds.confirmDialog(message=f"Installation failed: {e}", icon="warning", title="ERROR")
        logging.error(f"Runtime error: {e}")
    except Exception as e:
        cmds.confirmDialog(message=f"Unexpected error during installation: {e}", icon="warning", title="ERROR")
        logging.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    onMayaDroppedPythonFile()