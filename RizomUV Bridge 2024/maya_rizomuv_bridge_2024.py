## RizomUV 2024 - Maya Bridge
# A. Devran @ 2024 https://github.com/adevra/RizomUV-2024-Maya-Bridge

import maya.cmds as cmds
import subprocess, tempfile, os, platform
import maya.mel as mel
import base64
from PySide2 import QtCore, QtGui, QtWidgets
import maya.OpenMayaUI as omui
from shiboken2 import wrapInstance

rizomPath = r'C:\Program Files\Rizom Lab\RizomUV 2024.0\rizomuv.exe'

base64_image = "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B8CYsWOJcTioqqpixi9+gamVqEBbIYRgzgsvMHjIEN336CZk8JAhrFyxguMVFazIzycvL69NQrZWx8cff8zRo0cpKCigb9++LYYy2gqHw8H2bds4cOAAK/LzGT58eNjrAE0LP1uzxlB6nm5C/vjJJ8FYTmJiIv/YudOgeK3jR716Ue90Bv9//PjxRhHUcOGPn3wS/N67d++QUYPLgaIoZGVlUVZebih11fCknpOTQ25uLmtWrzZ6a5sQCQ0BiI2N5dHHHkMxmTihIw5nFPfddx8bN27EYXCO0h3ttVqtTJ48mfXr1/OnP/3JsIB64HI13kdmt9kahWrCheTkZAYPGcInf/iD7pU8I8jOzuaOAQMALUia3LUraenpugKwuj313Nxc1qxZw+nTpy9L2JbgV1Vi7HZqamowmUwMvecetnz3XdjreSovjw+XL48I2QDnzp1j165dlJeXc762FofDwfdbt4YM318M3Roy4M47yc7ODr5xeNv334ddU3bv2sU9w4YxZMgQLFYrv//d78JaPmjLuTfddBMLFy4MtmXN6tXs3bs3bHX4fD5OnToFaMkVNdXVusPwnaGTKEOnpx5l6CQkytBJSJShk5AoQychUYZOQqIMnYREGToJiTJ0EhJl+H/HSgVla+TLgwAAAABJRU5ErkJggg=="

def maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)

class RizomUVBridgeUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(RizomUVBridgeUI, self).__init__(parent)
        self.setWindowTitle("RizomUV Bridge 2024")
        self.setFixedSize(250, 150)
        self.setStyleSheet("background-color: rgb(26, 26, 26);")
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.WindowCloseButtonHint)

        self.create_layout()
        self.create_connections()

    def create_layout(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        row_layout = QtWidgets.QHBoxLayout()

        col1_layout = QtWidgets.QVBoxLayout()
        self.send_button = self.create_button("Send Selected", (59, 59, 59))
        self.uv_check = QtWidgets.QCheckBox("With Existing UVs")
        self.uv_check.setStyleSheet("color: white;")
        self.get_button = self.create_button("Get UVs", (59, 59, 59))
        self.line_check = QtWidgets.QCheckBox("Long Line Fix")
        self.line_check.setStyleSheet("color: white;")
        self.instant_button = self.create_button("Instant UVs", (59, 59, 59))
        
        col1_layout.addWidget(self.send_button)
        col1_layout.addWidget(self.uv_check)
        col1_layout.addWidget(self.get_button)
        col1_layout.addWidget(self.line_check)
        col1_layout.addWidget(self.instant_button)

        col2_layout = QtWidgets.QVBoxLayout()
        image_data = base64.b64decode(base64_image)
        temp_image_path = os.path.join(tempfile.gettempdir(), "rzmuv_logo_ui.png")
        with open(temp_image_path, "wb") as image_file:
            image_file.write(image_data)
        if os.path.exists(temp_image_path):
            image_label = QtWidgets.QLabel()
            pixmap = QtGui.QPixmap(temp_image_path)
            image_label.setPixmap(pixmap.scaled(100, 100, QtCore.Qt.KeepAspectRatio))
            col2_layout.addWidget(image_label)
        else:
            col2_layout.addWidget(QtWidgets.QLabel("RizomUV 2024"))

        row_layout.addLayout(col1_layout)
        row_layout.addLayout(col2_layout)

        main_layout.addLayout(row_layout)

    def create_button(self, text, color):
        button = QtWidgets.QPushButton(text)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: rgb{color};
                color: white;
                border: none;
                padding: 5px;
            }}
            QPushButton:hover {{
                background-color: rgb(239, 64, 0);
            }}
        """)
        return button

    def create_connections(self):
        self.send_button.clicked.connect(self.send_to_rizom)
        self.get_button.clicked.connect(self.get_from_rizom)
        self.instant_button.clicked.connect(self.rizom_auto_roundtrip)

    def send_to_rizom(self):
        sendToRizom()

    def get_from_rizom(self):
        getFromRizom()

    def rizom_auto_roundtrip(self):
        rizomAutoRoundtrip()

def show_rizom_uv_bridge_ui():
    try:
        for widget in QtWidgets.QApplication.allWidgets():
            if widget.objectName() == "RizomUVBridgeWin":
                widget.close()
    except:
        pass

    global rizom_uv_bridge_ui
    rizom_uv_bridge_ui = RizomUVBridgeUI(parent=maya_main_window())
    rizom_uv_bridge_ui.setObjectName("RizomUVBridgeWin")
    rizom_uv_bridge_ui.show()

def sendToRizom(*args):
    obj = cmds.ls(selection=True, geometry=True, ap=True, dag=True)
    exportFile = tempfile.gettempdir() + os.sep + "RizomUVMayaBridge.obj"
    cmds.file(exportFile, f=1, pr=1, typ="OBJexport", es=1, op="groups=1;ptgroups=1;materials=1;smoothing=1;normals=1")
    if cmds.checkBox('uvcheck', query=True, value=True):
        cmd = '"' + rizomPath + '" "' + exportFile + '"'
    else:
        cmd = '"' + rizomPath + '" /nu "' + exportFile + '"'
    if platform.system() == "Windows":
        subprocess.Popen(cmd)
    else:
        subprocess.Popen(["open", "-a", rizomPath, "--args", exportFile])

def getFromRizom(*args):
    originalOBJs = cmds.ls(selection=True, geometry=True, ap=True, dag=True)
    exportFile = tempfile.gettempdir() + os.sep + "RizomUVMayaBridge.obj"
    originalMaterials = {}
    for obj in originalOBJs:
        shadingGroups = cmds.listConnections(obj, type='shadingEngine')
        materials = cmds.ls(cmds.listConnections(shadingGroups), materials=True)
        originalMaterials[obj] = materials
    
    allNamespaces = cmds.namespaceInfo(listOnlyNamespaces=True)
    for ns in allNamespaces:
        if "RIZOMUV" in ns:
            try:
                cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
            except:
                pass

    if cmds.checkBox('linecheck', query=True, value=True):
        with open(exportFile, "r") as f:
            lines = f.readlines()
        with open(exportFile, "w") as f:
            for line in lines:
                if not line.startswith("#ZOMPROPERTIES"):
                    f.write(line)

    cmds.file(exportFile, i=1, typ="OBJ", pr=1, op="mo=1", ns="RIZOMUV")
    importedOBJs = cmds.ls("RIZOMUV:*", geometry=True, o=True, s=False)
    cmds.select(clear=True)
    actualReplacedUVOJBs = []

    for obj in originalOBJs:
        for imp in importedOBJs:
            if obj.replace("Shape", "") in imp:
                try:
                    cmds.polyTransfer(obj.replace("Shape", ""), vc=0, uv=1, v=0, ao=imp)
                    actualReplacedUVOJBs.append(obj.replace("Shape", ""))
                except:
                    pass
                break
    
    for obj in importedOBJs:
        try:
            cmds.select(obj, r=True)
            cmds.delete()
        except:
            pass

    for obj in actualReplacedUVOJBs:
        cmds.select(obj, add=True)

    for obj in actualReplacedUVOJBs:
        if obj in originalMaterials:
            for material in originalMaterials[obj]:
                cmds.select(obj)
                cmds.hyperShade(assign=material)

    null_objects = [obj for obj in cmds.ls("RIZOMUV:*", dag=True, ap=True) if not cmds.listRelatives(obj, c=True)]
    if null_objects:
        cmds.delete(null_objects)

def rizomAutoRoundtrip(*args):
    originalOBJs = cmds.ls(selection=True, geometry=True, ap=True, dag=True)
    if not originalOBJs:
        cmds.warning("No objects selected.")
        return

    exportFile = tempfile.gettempdir() + os.sep + "RizomUVMayaBridge.obj"
    
    originalMaterials = {}
    for obj in originalOBJs:
        shadingGroups = cmds.listConnections(obj, type='shadingEngine')
        materials = cmds.ls(cmds.listConnections(shadingGroups), materials=True)
        originalMaterials[obj] = materials

    cmds.file(exportFile, f=1, pr=1, typ="OBJexport", es=1, op="groups=1;ptgroups=1;materials=1;smoothing=1;normals=1")

    luascript = """
ZomLoad({File={Path="rizomFilePath", ImportGroups=true, XYZ=true}, NormalizeUVW=true})
ZomSelect({PrimType="Edge", Select=true, ResetBefore=true, Auto={ByAngle={Angle=45, Seams=false}, BySharpness=45, Seams=true, ByGroup=true}})
ZomCut({PrimType="Edge"})
ZomUnfold({PrimType="Island", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, BorderIntersections=true, TriangleFlips=true})
ZomIslandGroups({Mode="DistributeInTilesEvenly", MergingPolicy=8322, GroupPath="RootGroup"})
ZomPack({ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={Mode=2}, Rotate={}, Translate=true, LayoutScalingMode=2})
ZomSave({File={Path="rizomFilePath", UVWProps=true}, __UpdateUIObjFileName=true})
ZomQuit()
"""
    
    luaFile = tempfile.gettempdir() + os.sep + "riz.lua"
    with open(luaFile, "w") as f:
        f.write(luascript.replace("rizomFilePath", exportFile.replace("\\", "/")))

    cmd = '"' + rizomPath + '" -cfi "' + luaFile + '"'
    if platform.system() == "Windows":
        subprocess.call(cmd, shell=False)
    else:
        os.system('open -W "' + rizomPath + '" --args -cfi "' + luaFile + '"')

    if cmds.checkBox('linecheck', query=True, value=True):
        with open(exportFile, "r") as f:
            lines = f.readlines()
        with open(exportFile, "w") as f:
            for line in lines:
                if not line.startswith("#ZOMPROPERTIES"):
                    f.write(line)

    allNamespaces = cmds.namespaceInfo(listOnlyNamespaces=True)
    for ns in allNamespaces:
        if "RIZOMUV" in ns:
            try:
                cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
            except:
                pass

    cmds.file(exportFile, i=1, typ="OBJ", pr=1, op="mo=1", ns="RIZOMUV")
    importedOBJs = cmds.ls("RIZOMUV:*", geometry=True, o=True, s=False)

    if not importedOBJs:
        cmds.warning("No objects imported from RizomUV.")
        return

    cmds.select(clear=True)
    actualReplacedUVOJBs = []
    for obj in originalOBJs:
        for imp in importedOBJs:
            if obj.replace("Shape", "") in imp:
                try:
                    cmds.polyTransfer(obj.replace("Shape", ""), vc=0, uv=1, v=0, ao=imp)
                    actualReplacedUVOJBs.append(obj.replace("Shape", ""))
                except Exception as e:
                    cmds.warning(f"Error transferring UVs for {obj}: {e}")
                break

    for obj in importedOBJs:
        try:
            cmds.select(obj, r=True)
            cmds.delete()
        except:
            pass

    for obj in actualReplacedUVOJBs:
        cmds.select(obj, add=True)

    for obj in actualReplacedUVOJBs:
        if obj in originalMaterials:
            for material in originalMaterials[obj]:
                cmds.select(obj)
                cmds.hyperShade(assign=material)

    null_objects = [obj for obj in cmds.ls("RIZOMUV:*", dag=True, ap=True) if not cmds.listRelatives(obj, c=True)]
    if null_objects:
        cmds.delete(null_objects)

    if os.path.exists(luaFile):
        os.remove(luaFile)

if __name__ == "__main__":
    show_rizom_uv_bridge_ui()
