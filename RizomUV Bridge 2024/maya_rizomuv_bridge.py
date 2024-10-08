## RizomUV 2024 - Maya Bridge
# A. Devran @ 2024 https://github.com/adevra/RizomUV-2024-Maya-Bridge

import maya.cmds as cmds
import subprocess, tempfile, os, platform
import base64

rizomPath = r'C:\Program Files\Rizom Lab\RizomUV 2024.0\rizomuv.exe'
base64_image = "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B8CYsWOJcTioqqpixi9+gamVqEBbIYRgzgsvMHjIEN336CZk8JAhrFyxguMVFazIzycvL69NQrZWx8cff8zRo0cpKCigb9++LYYy2gqHw8H2bds4cOAAK/LzGT58eNjrAE0LP1uzxlB6nm5C/vjJJ8FYTmJiIv/YudOgeK3jR716Ue90Bv9//PjxRhHUcOGPn3wS/N67d++QUYPLgaIoZGVlUVZebih11fCknpOTQ25uLmtWrzZ6a5sQCQ0BiI2N5dHHHkMxmTihIw5nFPfddx8bN27EYXCO0h3ttVqtTJ48mfXr1/OnP/3JsIB64HI13kdmt9kahWrCheTkZAYPGcInf/iD7pU8I8jOzuaOAQMALUia3LUraenpugKwuj313Nxc1qxZw+nTpy9L2JbgV1Vi7HZqamowmUwMvecetnz3XdjreSovjw+XL48I2QDnzp1j165dlJeXc762FofDwfdbt4YM318M3Roy4M47yc7ODr5xeNv334ddU3bv2sU9w4YxZMgQLFYrv//d78JaPmjLuTfddBMLFy4MtmXN6tXs3bs3bHX4fD5OnToFaMkVNdXVusPwnaGTKEOnpx5l6CQkytBJSJShk5AoQychUYZOQqIMnYREGToJiTJ0EhJl+H/HSgVla+TLgwAAAABJRU5ErkJggg=="

def sendToRizom(*args):
    import time
    selected_objs = cmds.ls(selection=True, long=True, transforms=True)
    if not selected_objs:
        cmds.warning("No geometry selected to send to RizomUV.")
        return
    include_uvs = cmds.checkBox('uvcheck', query=True, value=True)
    exportFile = os.path.join(tempfile.gettempdir(), "RizomUVMayaBridge.obj")
    exportFileUnix = exportFile.replace("\\", "/")
    cmds.select(selected_objs, replace=True)
    export_options = "groups=1;ptgroups=1;materials=1;smoothing=1;normals=1;uvs=1"
    cmds.file(
        exportFile,
        force=True,
        preserveReferences=True,
        type="OBJexport",
        exportSelected=True,
        options=export_options
    )
    print(f"Exported OBJ to {exportFile} with {'existing UVs' if include_uvs else 'no existing UVs (will generate new UVs)'}")
    if include_uvs:
        lua_script = f'''
    ZomLoad({{File={{Path="{exportFileUnix}", ImportGroups=true, UVWProps=true, XYZUVW=true}}, NormalizeUVW=true}})
        '''
    else:
        lua_script = f'''
    ZomLoad({{File={{Path="{exportFileUnix}", ImportGroups=true, XYZ=true}}, NormalizeUVW=true}})
    ZomUnfold({{PrimType="Island", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, BorderIntersections=true, TriangleFlips=true}})
    ZomPack({{ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={{Mode=2}}, Rotate={{}}, Translate=true, LayoutScalingMode=2}})
    ZomSave({{File={{Path="{exportFileUnix}", UVWProps=true}}, __UpdateUIObjFileName=true}})
        '''
    control_script_path = os.path.join(tempfile.gettempdir(), "rizomuv_control_script.lua")
    control_script_path_unix = control_script_path.replace("\\", "/")
    with open(control_script_path, "w") as f:
        f.write(lua_script)
    print(f"Updated control script at {control_script_path}")
    rizom_running = False
    if platform.system() == "Windows":
        try:
            tasks = subprocess.check_output(['tasklist']).decode().lower()
            if 'rizomuv.exe' in tasks:
                rizom_running = True
        except Exception as e:
            print(f"Error checking if RizomUV is running: {e}")
    else:
        try:
            tasks = subprocess.check_output(['ps', 'aux']).decode().lower()
            if 'rizomuv' in tasks:
                rizom_running = True
        except Exception as e:
            print(f"Error checking if RizomUV is running: {e}")
    if not rizom_running:
        print("RizomUV is not running. Starting RizomUV with control script monitoring.")
        if platform.system() == "Windows":
            cmd = f'"{rizomPath}" -cfi "{control_script_path_unix}"'
            subprocess.Popen(cmd)
        else:
            cmd = [rizomPath, '-cfi', control_script_path_unix]
            subprocess.Popen(cmd)
        time.sleep(5)
    else:
        print("RizomUV is already running.")
        os.utime(control_script_path, None)
        print("Updated control script file timestamp to trigger RizomUV reload.")

def getFromRizom(*args):
    originalOBJs = cmds.ls(selection=True, long=True, transforms=True)
    if not originalOBJs:
        cmds.warning("No geometry selected to get UVs from RizomUV.")
        return
    importFile = os.path.join(tempfile.gettempdir(), "RizomUVMayaBridge.obj")
    importFileUnix = importFile.replace("\\", "/")
    allNamespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True)
    for ns in allNamespaces:
        if "RIZOMUV" in ns:
            try:
                cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
                print(f"Removed namespace: {ns}")
            except Exception as e:
                print(f"Failed to remove namespace {ns}: {e}")
    if cmds.checkBox('linecheck', query=True, value=True):
        if os.path.exists(importFile):
            with open(importFile, "r") as f:
                lines = f.readlines()
            with open(importFile, "w") as f:
                for line in lines:
                    if not line.startswith("#ZOMPROPERTIES"):
                        f.write(line)
            print("Long lines fixed in OBJ file.")
        else:
            cmds.warning(f"Import file not found: {importFile}")
            return
    cmds.file(importFile, i=True, type="OBJ", ignoreVersion=True, mergeNamespacesOnClash=True, namespace="RIZOMUV")
    imported_transforms = cmds.ls("RIZOMUV:*", transforms=True, long=True)
    if not imported_transforms:
        cmds.warning("No objects imported from RizomUV.")
        return
    for orig_obj in originalOBJs:
        target_obj_name = orig_obj.split('|')[-1]
        corresponding_imp = None
        for imp_transform in imported_transforms:
            imp_name = imp_transform.split(':')[-1]
            if imp_name == target_obj_name:
                corresponding_imp = imp_transform
                break
        if corresponding_imp:
            src_shapes = cmds.listRelatives(corresponding_imp, shapes=True, fullPath=True)
            trg_shapes = cmds.listRelatives(orig_obj, shapes=True, fullPath=True)
            if not src_shapes or not trg_shapes:
                cmds.warning(f"Could not find shapes for objects {corresponding_imp} or {orig_obj}")
                continue
            src = src_shapes[0]
            trg = trg_shapes[0]
            source_uv_set = "map1"
            target_uv_set = "map1"
            cmds.polyUVSet(src, currentUVSet=True, uvSet=source_uv_set)
            if target_uv_set not in cmds.polyUVSet(trg, query=True, allUVSets=True):
                cmds.polyUVSet(trg, create=True, uvSet=target_uv_set)
            cmds.polyUVSet(trg, currentUVSet=True, uvSet=target_uv_set)
            cmds.transferAttributes(
                src, trg,
                transferPositions=0,
                transferNormals=0,
                transferUVs=2,
                transferColors=0,
                sampleSpace=4,
                sourceUvSpace=source_uv_set,
                targetUvSpace=target_uv_set,
                searchMethod=3,
                flipUVs=0,
                colorBorders=1
            )
            cmds.delete(trg, ch=True)
            print(f"Transferred UVs from {src} to {trg}")
        else:
            cmds.warning(f"No corresponding imported object found for {orig_obj}")
    for obj in imported_transforms:
        try:
            cmds.delete(obj)
            print(f"Deleted imported object: {obj}")
        except Exception as e:
            cmds.warning(f"Failed to delete imported object {obj}: {e}")

def rizomAutoRoundtrip(*args):
    import time
    originalOBJs = cmds.ls(selection=True, long=True, transforms=True)
    if not originalOBJs:
        cmds.warning("No objects selected.")
        return
    exportFile = os.path.join(tempfile.gettempdir(), "RizomUVMayaBridge.obj")
    exportFileUnix = exportFile.replace("\\", "/")
    cmds.select(originalOBJs, replace=True)
    cmds.file(
        exportFile,
        force=True,
        preserveReferences=True,
        type="OBJexport",
        exportSelected=True,
        options="groups=1;ptgroups=1;materials=1;smoothing=1;normals=1"
    )
    print(f"Exported OBJ to {exportFile}")
    luascript = """
ZomLoad({File={Path="rizomFilePath", ImportGroups=true, XYZ=true}, NormalizeUVW=true})
ZomSelect({PrimType="Edge", Select=true, ResetBefore=true, Auto={ByAngle={Angle=45, Seams=false}, BySharpness=45, Seams=true, ByGroup=true}})
ZomCut({PrimType="Edge"})
ZomUnfold({PrimType="Island", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, BorderIntersections=true, TriangleFlips=true}})
ZomIslandGroups({Mode="DistributeInTilesEvenly", MergingPolicy=8322, GroupPath="RootGroup"})
ZomPack({ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={Mode=2}, Rotate={}, Translate=true, LayoutScalingMode=2}})
ZomSave({File={Path="rizomFilePath", UVWProps=true}, __UpdateUIObjFileName=true}})
ZomQuit()
"""
    luascript_formatted = luascript.replace("rizomFilePath", exportFileUnix)
    luaFile = os.path.join(tempfile.gettempdir(), "riz.lua")
    with open(luaFile, "w") as f:
        f.write(luascript_formatted)
    print(f"Created Lua script at {luaFile}")
    luaFileUnix = luaFile.replace("\\", "/")
    cmd = [rizomPath, '--execute', luaFileUnix]
    print(f"Executing RizomUV with command: {' '.join(cmd)}")
    try:
        subprocess.call(cmd)
    except Exception as e:
        cmds.warning(f"Failed to execute RizomUV: {e}")
    time.sleep(2)
    getFromRizom()
    if os.path.exists(luaFile):
        try:
            os.remove(luaFile)
            print(f"Deleted Lua script: {luaFile}")
        except Exception as e:
            cmds.warning(f"Failed to delete Lua script {luaFile}: {e}")

def createUI():
    if cmds.window("rizomUVBridgeWin", exists=True):
        cmds.deleteUI("rizomUVBridgeWin", window=True)
    window = cmds.window("rizomUVBridgeWin", title="RizomUV Bridge 2024", widthHeight=(300, 150))
    form = cmds.formLayout()
    image_data = base64.b64decode(base64_image)
    temp_image_path = os.path.join(tempfile.gettempdir(), "rzmuv_logo_ui.png")
    with open(temp_image_path, "wb") as image_file:
        image_file.write(image_data)
    row = cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
    col1 = cmds.columnLayout(adjustableColumn=True, parent=row)
    cmds.button(label="Send Selected", command=sendToRizom, backgroundColor=(0.23, 0.23, 0.23))
    cmds.checkBox('uvcheck', label='With Existing UVs', align='center', value=True)
    cmds.button(label="Get UVs", command=getFromRizom, backgroundColor=(0.23, 0.23, 0.23))
    cmds.checkBox('linecheck', label='Long Line Fix', align='center', value=False)
    cmds.button(label="Instant UVs", command=rizomAutoRoundtrip, backgroundColor=(0.23, 0.23, 0.23))
    col2 = cmds.columnLayout(adjustableColumn=True, parent=row)
    if os.path.exists(temp_image_path):
        cmds.image(image=temp_image_path, width=100, height=100)
    else:
        cmds.text(label="RizomUV")
    cmds.formLayout(form, edit=True,
                    attachForm=[(row, 'top', 5), (row, 'left', 5), (row, 'right', 5), (row, 'bottom', 5)])
    cmds.window(window, edit=True, backgroundColor=(0.1, 0.1, 0.1))
    cmds.showWindow(window)

if __name__ == "__main__":
    createUI()
