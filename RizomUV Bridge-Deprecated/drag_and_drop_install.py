import os
import shutil
import maya.cmds as cmds
import maya.mel as mel
import platform

def onMayaDroppedPythonFile(*args):
    try:
        installer_directory = os.path.dirname(__file__)
        script_file_path = os.path.join(installer_directory, "maya_rizomuv_bridge_2024.py")
        shelf_icon_path = os.path.join(installer_directory, "rzmuv.png")
        
        if not os.path.exists(script_file_path):
            raise RuntimeError("Unable to find 'maya_rizomuv_bridge.py' relative to this installer")
        if not os.path.exists(shelf_icon_path):
            raise RuntimeError("Unable to find 'rzmuv.png' relative to this installer")
        
        if platform.system() == "Windows":
            file_filter = "Executable Files (*.exe)"
        elif platform.system() == "Darwin":
            file_filter = "Applications (*.app)"
        else:
            file_filter = "All Files (*.*)"
        
        rizomPath = cmds.fileDialog2(fileMode=1, caption="Select RizomUV Executable", fileFilter=file_filter)[0]
        
        with open(script_file_path, 'r') as file:
            script_content = file.read()

        placeholder_paths = [
            r"rizomPath = r'C:\\Program Files\\Rizom Lab\\RizomUV 2024.0\\rizomuv.exe'",
            r"rizomPath = r'C:\Program Files\Rizom Lab\RizomUV 2024.0\rizomuv.exe'"
        ]

        for placeholder_path in placeholder_paths:
            if placeholder_path in script_content:
                script_content = script_content.replace(placeholder_path, f"rizomPath = r'{rizomPath}'")
                break
        else:
            raise RuntimeError("Placeholder path not found in the script.")
        
        updated_script_file_path = os.path.join(installer_directory, "maya_rizomuv_bridge_updated.py")
        with open(updated_script_file_path, 'w') as file:
            file.write(script_content)
        
        prefs_dir = os.path.dirname(cmds.about(preferences=True))
        scripts_dir = os.path.normpath(os.path.join(prefs_dir, "scripts"))
        
        shutil.copy(updated_script_file_path, os.path.join(scripts_dir, "maya_rizomuv_bridge.py"))
        shutil.copy(shelf_icon_path, scripts_dir)

        os.remove(updated_script_file_path)

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
            command="import maya_rizomuv_bridge; maya_rizomuv_bridge.show_rizom_uv_bridge_ui()"
        )

        cmds.confirmDialog(message="Script successfully installed to: {0}".format(scripts_dir),
                           title="Confirmation dialog")
    
    except Exception as e:
        cmds.confirmDialog(message="Script failed to install: {0}".format(e), icon="warning", title="ERROR")

if __name__ == "__main__":
    onMayaDroppedPythonFile()
