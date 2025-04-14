import maya.cmds as cmds
import os
prefs_dir = os.path.dirname(cmds.about(preferences=True))
scripts_dir = os.path.normpath(os.path.join(prefs_dir, "scripts"))
config_folder = os.path.join(scripts_dir, "RizomUVBridge")
print(f"Looking for config folder at: {config_folder}")
if not os.path.exists(config_folder):
     
     import tempfile
     config_folder_temp = os.path.join(tempfile.gettempdir(), "RizomUVBridge")
     print(f"Also checking temp folder: {config_folder_temp}")
     if os.path.exists(config_folder_temp):
          config_folder = config_folder_temp
     else:
          config_folder = "NOT FOUND" 
print(f"--> Config folder path determined as: {config_folder}") 

