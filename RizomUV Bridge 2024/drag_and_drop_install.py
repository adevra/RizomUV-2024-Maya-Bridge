import os
import shutil
import maya.cmds as cmds
import maya.mel as mel
import platform

def onMayaDroppedPythonFile(*args):
    try:
        # Get paths relative to the installer
        installer_directory = os.path.dirname(__file__)
        script_file_path = os.path.join(installer_directory, "maya_rizomuv_bridge.py")
        shelf_icon_path = os.path.join(installer_directory, "rzmuv.png")
        
        # Validate source files
        if not os.path.exists(script_file_path):
            raise RuntimeError("Unable to find 'maya_rizomuv_bridge.py' relative to this installer")
        if not os.path.exists(shelf_icon_path):
            raise RuntimeError("Unable to find 'rzmuv.png' relative to this installer")
        
        # Platform-specific file filter for RizomUV executable selection
        system = platform.system()
        if system == "Windows":
            file_filter = "Executable Files (*.exe)"
            default_path = r"C:\Program Files\Rizom Lab\RizomUV 2024.0\rizomuv.exe"
        elif system == "Darwin":
            file_filter = "Applications (*.app)"
            default_path = "/Applications/RizomUV 2024.0.app"
        else:  # Linux
            file_filter = "Executable Files (*)"
            default_path = "/usr/local/bin/rizomuv"
        
        # Prompt user to select RizomUV executable
        rizomPath = cmds.fileDialog2(fileMode=1, caption="Select RizomUV Executable", fileFilter=file_filter, startingDirectory=os.path.dirname(default_path))[0]
        
        # Read the script content
        with open(script_file_path, 'r') as file:
            script_content = file.read()

        # Update DEFAULT_PATHS dictionary in the script
        placeholder = 'DEFAULT_PATHS = {'
        if placeholder in script_content:
            new_default_paths = (
                f'DEFAULT_PATHS = {{\n'
                f'    "Windows": r"{rizomPath if system == "Windows" else "C:\\Program Files\\Rizom Lab\\RizomUV 2024.0\\rizomuv.exe"}",\n'
                f'    "Darwin": "{rizomPath if system == "Darwin" else "/Applications/RizomUV 2024.0.app"}",\n'
                f'    "Linux": "{rizomPath if system == "Linux" else "/usr/local/bin/rizomuv"}"\n'
                f'}}'
            )
            # Replace the entire DEFAULT_PATHS block
            start_idx = script_content.index(placeholder)
            end_idx = script_content.index('}', start_idx) + 1
            script_content = script_content[:start_idx] + new_default_paths + script_content[end_idx:]
        else:
            raise RuntimeError("DEFAULT_PATHS dictionary not found in the script.")
        
        # Write updated script
        updated_script_file_path = os.path.join(installer_directory, "maya_rizomuv_bridge_updated.py")
        with open(updated_script_file_path, 'w') as file:
            file.write(script_content)
        
        # Install to Maya's scripts directory
        prefs_dir = os.path.dirname(cmds.about(preferences=True))
        scripts_dir = os.path.normpath(os.path.join(prefs_dir, "scripts"))
        
        shutil.copy(updated_script_file_path, os.path.join(scripts_dir, "maya_rizomuv_bridge.py"))
        shutil.copy(shelf_icon_path, scripts_dir)

        # Clean up temporary file
        os.remove(updated_script_file_path)

        # Add shelf button
        absolute_shelf_icon_path = os.path.join(scripts_dir, "rzmuv.png").replace("\\", "/")
        current_shelf = mel.eval("string $currentShelf = `tabLayout -query -selectTab $gShelfTopLevel`;")
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
            command="import maya_rizomuv_bridge; maya_rizomuv_bridge.run()"
        )

        cmds.confirmDialog(message=f"Script successfully installed to: {scripts_dir}", title="Confirmation dialog")
    
    except Exception as e:
        cmds.confirmDialog(message=f"Script failed to install: {e}", icon="warning", title="ERROR")

if __name__ == "__main__":
    onMayaDroppedPythonFile()