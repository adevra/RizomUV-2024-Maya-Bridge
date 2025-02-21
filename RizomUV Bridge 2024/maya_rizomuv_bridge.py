import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMayaUI as omui
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import subprocess, tempfile, os, platform
import base64
import xml.dom.minidom as xml

if platform.python_version().startswith('3'):
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance
else:
    from PySide import QtWidgets, QtCore, QtGui
    from shiboken import wrapInstance

DEFAULT_PATHS = {
    "Windows": r"C:\Program Files\Rizom Lab\RizomUV 2024.0\rizomuv.exe",
    "Darwin": "/Applications/RizomUV 2024.0.app",
    "Linux": "/usr/local/bin/rizomuv"
}

# Base64 image data (replace with your actual base64 string)
base64_image = "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B8CYsWOJcTioqqpixi9+gamVqEBbIYRgzgsvMHjIEN336CZk8JAhrFyxguMVFazIzycvL69NQrZWx8cff8zRo0cpKCigb9++LYYy2gqHw8H2bds4cOAAK/LzGT58eNjrAE0LP1uzxlB6nm5C/vjJJ8FYTmJiIv/YudOgeK3jR716Ue90Bv9//PjxRhHUcOGPn3wS/N67d++QUYPLgaIoZGVlUVZebih11fCknpOTQ25uLmtWrzZ6a5sQCQ0BiI2N5dHHHkMxmTihIw5nFPfddx8bN27EYXCO0h3ttVqtTJ48mfXr1/OnP/3JsIB64HI13kdmt9kahWrCheTkZAYPGcInf/iD7pU8I8jOzuaOAQMALUia3LUraenpugKwuj313Nxc1qxZw+nTpy9L2JbgV1Vi7HZqamowmUwMvecetnz3XdjreSovjw+XL48I2QDnzp1j165dlJeXc762FofDwfdbt4YM318M3Roy4M47yc7ODr5xeNv334ddU3bv2sU9w4YxZMgQLFYrv//d78JaPmjLuTfddBMLFy4MtmXN6tXs3bs3bHX4fD5OnToFaMkVNdXVusPwnaGTKEOnpx5l6CQkytBJSJShk5AoQychUYZOQqIMnYREGToJiTJ0EhJl+H/HSgVla+TLgwAAAABJRU5ErkJggg=="


class Settings:
    def __init__(self):
        self.config_path = os.path.join(tempfile.gettempdir(), "RizomUVBridge")
        self.config_file = os.path.join(self.config_path, "settings.xml")
        self.lua_script_path = os.path.join(self.config_path, "rizomuv_control_script.lua").replace("\\", "/")
        self.check_config_exists()
        try:
            self.read_settings()
        except:
            self.set_defaults()
            self.save_settings()
            self.read_settings()

    def check_config_exists(self):
        if not os.path.exists(self.config_path):
            os.makedirs(self.config_path)
        if not os.path.exists(self.config_file):
            self.set_defaults()
            self.save_settings()

    def set_defaults(self):
        self.rizom_path = DEFAULT_PATHS.get(platform.system(), DEFAULT_PATHS["Windows"])
        self.export_file = os.path.join(self.config_path, "RizomUVMayaBridge.fbx").replace("\\", "/")
        self.load_uvs = True
        self.quality = 2  # Default to "High"
        self.mutations = 256

    def read_settings(self):
        doc = xml.parse(self.config_file)
        root = doc.getElementsByTagName("Settings")[0]
        self.rizom_path = root.getAttribute("rizomPath")
        self.export_file = root.getAttribute("exportFile")
        self.load_uvs = root.getAttribute("loadUVs").lower() == "true"
        self.quality = int(root.getAttribute("quality") or 2)
        self.mutations = int(root.getAttribute("mutations") or 256)

    def save_settings(self):
        doc = xml.Document()
        root = doc.createElement("Settings")
        root.setAttribute("rizomPath", self.rizom_path)
        root.setAttribute("exportFile", self.export_file)
        root.setAttribute("loadUVs", str(self.load_uvs))
        root.setAttribute("quality", str(self.quality))
        root.setAttribute("mutations", str(self.mutations))
        doc.appendChild(root)
        with open(self.config_file, "w") as f:
            doc.writexml(f, indent="  ", addindent="  ", newl="\n")

class RizomUVBridgeWindow(MayaQWidgetDockableMixin, QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(RizomUVBridgeWindow, self).__init__(parent)
        self.settings = Settings()
        self.setWindowTitle("RizomUV Bridge")
        self.setMinimumWidth(250)
        self.create_ui()
        self.create_connections()

    def create_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Settings Group
        settings_group = QtWidgets.QGroupBox("Settings")
        settings_layout = QtWidgets.QVBoxLayout()
        self.path_field = QtWidgets.QLineEdit(self.settings.rizom_path)
        self.path_field.setToolTip("Path to the RizomUV executable")
        self.path_button = QtWidgets.QPushButton("Browse")
        path_layout = QtWidgets.QHBoxLayout()
        path_layout.addWidget(QtWidgets.QLabel("RizomUV Path:"))
        path_layout.addWidget(self.path_field)
        path_layout.addWidget(self.path_button)
        settings_layout.addLayout(path_layout)
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        # UV Operations Group
        operations_group = QtWidgets.QGroupBox("UV Operations")
        operations_layout = QtWidgets.QVBoxLayout()
        self.send_button = QtWidgets.QPushButton("Send to RizomUV")
        self.send_button.setToolTip("Export selected geometry to RizomUV")
        self.get_button = QtWidgets.QPushButton("Get UVs")
        self.get_button.setToolTip("Import UVs from RizomUV to the selected UV set")
        self.uvs_check = QtWidgets.QCheckBox("With Existing UVs")
        self.uvs_check.setChecked(self.settings.load_uvs)
        self.uvs_check.setToolTip("Include existing UVs when exporting to RizomUV")
        self.uvset_combo = QtWidgets.QComboBox()
        self.update_uv_sets()
        operations_layout.addWidget(self.send_button)
        operations_layout.addWidget(self.uvs_check)
        operations_layout.addWidget(QtWidgets.QLabel("UV Set:"))
        operations_layout.addWidget(self.uvset_combo)
        operations_layout.addWidget(self.get_button)
        operations_group.setLayout(operations_layout)
        main_layout.addWidget(operations_group)

        # UV Packer Group
        packer_group = QtWidgets.QGroupBox("UV Packer")
        packer_layout = QtWidgets.QVBoxLayout()
        self.pack_button = QtWidgets.QPushButton("Export and Pack UVs")
        self.pack_button.setToolTip("Export geometry and pack UVs in RizomUV")
        self.quality_combo = QtWidgets.QComboBox()
        self.quality_combo.addItems(["Low", "Normal", "High", "Higher", "Ultra"])
        self.quality_combo.setCurrentIndex(self.settings.quality)
        self.quality_combo.setToolTip("Select packing quality level")
        self.mutations_spin = QtWidgets.QSpinBox()
        self.mutations_spin.setRange(1, 1000)
        self.mutations_spin.setValue(self.settings.mutations)
        self.mutations_spin.setToolTip("Number of packing mutations to attempt")
        packer_layout.addWidget(self.pack_button)
        packer_layout.addWidget(QtWidgets.QLabel("Packing Quality:"))
        packer_layout.addWidget(self.quality_combo)
        packer_layout.addWidget(QtWidgets.QLabel("Mutations:"))
        packer_layout.addWidget(self.mutations_spin)
        packer_group.setLayout(packer_layout)
        main_layout.addWidget(packer_group)

        # Status and Logo
        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        main_layout.addWidget(self.status_label)

        image_data = base64.b64decode(base64_image)
        temp_image_path = os.path.join(tempfile.gettempdir(), "rzmuv_logo_ui.png")
        with open(temp_image_path, "wb") as f:
            f.write(image_data)
        if os.path.exists(temp_image_path):
            logo = QtWidgets.QLabel()
            pixmap = QtGui.QPixmap(temp_image_path).scaled(100, 100, QtCore.Qt.KeepAspectRatio)
            logo.setPixmap(pixmap)
            logo.setAlignment(QtCore.Qt.AlignCenter)
            main_layout.addWidget(logo)
        main_layout.addStretch()

    def create_connections(self):
        self.send_button.clicked.connect(lambda: self.send_to_rizom(pack=False))
        self.pack_button.clicked.connect(lambda: self.send_to_rizom(pack=True))
        self.get_button.clicked.connect(self.get_from_rizom)
        self.uvs_check.stateChanged.connect(self.save_settings)
        self.path_button.clicked.connect(self.browse_path)
        self.quality_combo.currentIndexChanged.connect(self.save_settings)
        self.mutations_spin.valueChanged.connect(self.save_settings)
        cmds.scriptJob(event=["SelectionChanged", self.update_uv_sets], parent=self.objectName())

    def browse_path(self):
        path = QtWidgets.QFileDialog.getOpenFileName(self, "Locate RizomUV", self.settings.rizom_path)[0]
        if path:
            self.path_field.setText(path)
            self.settings.rizom_path = path
            self.settings.save_settings()

    def update_uv_sets(self):
        current_selection = self.uvset_combo.currentText() if self.uvset_combo.count() else ""
        self.uvset_combo.clear()
        sel_objs = cmds.ls(sl=True, tr=True)
        if sel_objs:
            uv_sets = cmds.polyUVSet(sel_objs[0], query=True, allUVSets=True) or ["map1"]
            new_items = ["All UV Sets"] + uv_sets
            self.uvset_combo.addItems(new_items)
            if current_selection in new_items:
                self.uvset_combo.setCurrentIndex(new_items.index(current_selection))
            else:
                self.uvset_combo.setCurrentIndex(1 if len(new_items) > 1 else 0)

    def save_settings(self):
        self.settings.load_uvs = self.uvs_check.isChecked()
        self.settings.rizom_path = self.path_field.text()
        self.settings.quality = self.quality_combo.currentIndex()
        self.settings.mutations = self.mutations_spin.value()
        self.settings.save_settings()

    def send_to_rizom(self, pack=False):
        import time
        selected_objs = cmds.ls(selection=True, long=True, transforms=True)
        if not selected_objs:
            self.update_status("Error: No geometry selected.")
            return
        
        include_uvs = self.uvs_check.isChecked()
        export_file = self.settings.export_file
        selected_uv_set = self.uvset_combo.currentText()
        
        if not cmds.pluginInfo("fbxmaya", loaded=True, query=True):
            cmds.loadPlugin("fbxmaya")
        cmds.select(selected_objs, replace=True)
        
        # Set the current UV set for export if a specific set is chosen
        if include_uvs or (pack and selected_uv_set != "All UV Sets"):
            for obj in selected_objs:
                shapes = cmds.listRelatives(obj, shapes=True, fullPath=True, noIntermediate=True)
                if shapes and selected_uv_set in cmds.polyUVSet(shapes[0], query=True, allUVSets=True):
                    cmds.polyUVSet(shapes[0], currentUVSet=True, uvSet=selected_uv_set)
                    print(f"Set current UV set to {selected_uv_set} on {obj}")
                else:
                    print(f"Warning: UV set {selected_uv_set} not found on {obj}, using default.")
        
        # FBX export without FBXExportEmbedMedia
        mel.eval('FBXExportSmoothingGroups -v true;')
        mel.eval('FBXExportTriangulate -v false;')
        mel.eval('FBXExportSmoothMesh -v false;')
        mel.eval('FBXExportUpAxis Y;')
        mel.eval(f'FBXExport -f "{export_file}" -s;')
        self.update_status(f"Exported to {export_file} with UV set {selected_uv_set if include_uvs or pack else 'none'}")
        
        # Lua script generation
        if pack:
            quality_map = {0: 128, 1: 256, 2: 512, 3: 1024, 4: 2048}  # Low to Ultra
            quality = quality_map[self.quality_combo.currentIndex()]
            mutations = self.mutations_spin.value()
            if selected_uv_set == "All UV Sets":
                lua_script = f'''
ZomLoad({{File={{Path="{export_file}", ImportGroups=true, XYZUVW=true, UVWProps=true}}, NormalizeUVW=false}})
ZomUvset({{Mode="SetCurrent", Name="map1"}})
ZomUnfold({{PrimType="Island", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, BorderIntersections=true, TriangleFlips=true}})
ZomPack({{ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={{Mode=2}}, Rotate={{}}, Translate=true, LayoutScalingMode=2, MaxMutations={mutations}, Resolution={quality}}})
ZomSave({{File={{Path="{export_file}", UVWProps=true}}, __UpdateUIObjFileName=true}})
'''
            else:
                lua_script = f'''
ZomLoad({{File={{Path="{export_file}", ImportGroups=true, XYZUVW=true, UVWProps=true}}, NormalizeUVW=false}})
ZomUvset({{Mode="SetCurrent", Name="{selected_uv_set}"}})
ZomUnfold({{PrimType="Island", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, BorderIntersections=true, TriangleFlips=true}})
ZomPack({{ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={{Mode=2}}, Rotate={{}}, Translate=true, LayoutScalingMode=2, MaxMutations={mutations}, Resolution={quality}}})
ZomSave({{File={{Path="{export_file}", UVWProps=true}}, __UpdateUIObjFileName=true}})
'''
        elif include_uvs:
            lua_script = f'''
ZomLoad({{File={{Path="{export_file}", ImportGroups=true, UVWProps=true, XYZUVW=true}}, NormalizeUVW=false}})
ZomUvset({{Mode="SetCurrent", Name="{selected_uv_set}"}})
ZomSave({{File={{Path="{export_file}", UVWProps=true}}, __UpdateUIObjFileName=true}})
'''
        else:
            lua_script = f'''
ZomLoad({{File={{Path="{export_file}", ImportGroups=true, XYZ=true}}, NormalizeUVW=true}})
ZomUvset({{Mode="SetCurrent", Name="{selected_uv_set}"}})
ZomUnfold({{PrimType="Island", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, BorderIntersections=true, TriangleFlips=true}})
ZomPack({{ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={{Mode=2}}, Rotate={{}}, Translate=true, LayoutScalingMode=2}})
ZomSave({{File={{Path="{export_file}", UVWProps=true}}, __UpdateUIObjFileName=true}})
'''
        
        with open(self.settings.lua_script_path, "w") as f:
            f.write(lua_script)
        
        # Enhanced RizomUV launch logic
        rizom_running = False
        system = platform.system()
        if system == "Windows":
            try:
                tasks = subprocess.check_output(['tasklist'], stderr=subprocess.STDOUT).decode().lower()
                if 'rizomuv.exe' in tasks:
                    rizom_running = True
            except subprocess.CalledProcessError as e:
                print(f"Failed to check running processes: {e}")
        
        if not rizom_running:
            self.update_status("Starting RizomUV...")
            try:
                if system == "Windows":
                    cmd = f'"{self.settings.rizom_path}" -cfi "{self.settings.lua_script_path}"'
                    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = process.communicate(timeout=10)
                    if process.returncode != 0:
                        raise subprocess.SubprocessError(f"RizomUV failed to start: {stderr.decode()}")
                elif system == "Darwin":
                    cmd = ['open', '-a', self.settings.rizom_path, '--args', '-cfi', self.settings.lua_script_path]
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = process.communicate(timeout=10)
                    if process.returncode != 0:
                        raise subprocess.SubprocessError(f"RizomUV failed to start: {stderr.decode()}")
                else:
                    cmd = [self.settings.rizom_path, '-cfi', self.settings.lua_script_path]
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = process.communicate(timeout=10)
                    if process.returncode != 0:
                        raise subprocess.SubprocessError(f"RizomUV failed to start: {stderr.decode()}")
                time.sleep(5)  # Give RizomUV time to initialize
                self.update_status("RizomUV started successfully")
            except (subprocess.SubprocessError, subprocess.TimeoutExpired, Exception) as e:
                self.update_status(f"Failed to start RizomUV: {str(e)}")
                print(f"Command attempted: {cmd}")
                return
        else:
            os.utime(self.settings.lua_script_path, None)  # Touch the file to trigger RizomUV reload
            self.update_status("RizomUV already running, script updated")
        
        self.update_status("Sent to RizomUV" if not pack else "Sent to RizomUV for packing")

    def get_from_rizom(self):
        original_objs = cmds.ls(selection=True, long=True, transforms=True)
        if not original_objs:
            self.update_status("Error: No geometry selected.")
            return
        import_file = self.settings.export_file
        target_uv_set = self.uvset_combo.currentText()
        
        if not os.path.exists(import_file):
            self.update_status(f"Error: Could not locate {import_file}")
            return
        
        namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []
        for ns in namespaces:
            if "RIZOMUV" in ns:
                try:
                    cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
                    print(f"Removed namespace: {ns}")
                except Exception as e:
                    print(f"Failed to remove namespace {ns}: {e}")
        
        if not cmds.pluginInfo("fbxmaya", loaded=True, query=True):
            cmds.loadPlugin("fbxmaya")
        cmds.file(import_file, i=True, type="FBX", ignoreVersion=True, mergeNamespacesOnClash=True, namespace="RIZOMUV")
        
        imported_transforms = cmds.ls("RIZOMUV:*", transforms=True, long=True)
        if not imported_transforms:
            self.update_status("Error: No objects imported from RizomUV.")
            return
        
        for orig_obj in original_objs:
            target_obj_name = orig_obj.split('|')[-1]
            print(f"Processing original: {orig_obj}, base name: {target_obj_name}")
            corresponding_imp = None
            for imp_transform in imported_transforms:
                imp_name = imp_transform.split(':')[-1].split('|')[-1]
                if imp_name == target_obj_name:
                    corresponding_imp = imp_transform
                    break
            
            if corresponding_imp:
                print(f"Found match: {corresponding_imp}")
                src_shapes = cmds.listRelatives(corresponding_imp, shapes=True, fullPath=True, noIntermediate=True)
                trg_shapes = cmds.listRelatives(orig_obj, shapes=True, fullPath=True, noIntermediate=True)
                if not src_shapes or not trg_shapes:
                    self.update_status(f"Error: Could not find shapes for {corresponding_imp} or {orig_obj}")
                    print(f"Source shapes: {src_shapes}, Target shapes: {trg_shapes}")
                    continue
                
                src = src_shapes[0]
                trg = trg_shapes[0]
                print(f"Source: {src}, Target: {trg}")
                
                src_uv_sets = cmds.polyUVSet(src, query=True, allUVSets=True) or ["map1"]
                trg_uv_sets = cmds.polyUVSet(trg, query=True, allUVSets=True) or []
                print(f"Source UV sets: {src_uv_sets}")
                print(f"Target UV sets before: {trg_uv_sets}")
                
                if target_uv_set == "All UV Sets":
                    for src_uv_set in src_uv_sets:
                        if src_uv_set not in trg_uv_sets:
                            cmds.polyUVSet(trg, create=True, uvSet=src_uv_set)
                            print(f"Created UV set {src_uv_set} on {trg}")
                        try:
                            cmds.polyUVSet(src, currentUVSet=True, uvSet=src_uv_set)
                            cmds.polyUVSet(trg, currentUVSet=True, uvSet=src_uv_set)
                            cmds.transferAttributes(
                                src, trg,
                                transferPositions=0,
                                transferNormals=0,
                                transferUVs=2,
                                transferColors=0,
                                sampleSpace=4,
                                sourceUvSpace=src_uv_set,
                                targetUvSpace=src_uv_set,
                                searchMethod=3,
                                flipUVs=0,
                                colorBorders=1
                            )
                            cmds.delete(trg, constructionHistory=True)
                            print(f"Transferred UVs from {src_uv_set} to {src_uv_set} on {trg}")
                        except Exception as e:
                            print(f"Error transferring UV set {src_uv_set}: {e}")
                            self.update_status(f"Error transferring UVs for {target_obj_name}")
                else:
                    if target_uv_set not in src_uv_sets:
                        self.update_status(f"Error: Selected UV set '{target_uv_set}' not found in imported data.")
                        continue
                    if target_uv_set not in trg_uv_sets:
                        cmds.polyUVSet(trg, create=True, uvSet=target_uv_set)
                        print(f"Created UV set {target_uv_set} on {trg}")
                    try:
                        cmds.polyUVSet(src, currentUVSet=True, uvSet=target_uv_set)
                        cmds.polyUVSet(trg, currentUVSet=True, uvSet=target_uv_set)
                        cmds.transferAttributes(
                            src, trg,
                            transferPositions=0,
                            transferNormals=0,
                            transferUVs=2,
                            transferColors=0,
                            sampleSpace=4,
                            sourceUvSpace=target_uv_set,
                            targetUvSpace=target_uv_set,
                            searchMethod=3,
                            flipUVs=0,
                            colorBorders=1
                        )
                        cmds.delete(trg, constructionHistory=True)
                        print(f"Transferred UVs from {target_uv_set} to {target_uv_set} on {trg}")
                    except Exception as e:
                        print(f"Error transferring UV set {target_uv_set}: {e}")
                        self.update_status(f"Error transferring UVs for {target_obj_name}")
                
                trg_uv_sets_after = cmds.polyUVSet(trg, query=True, allUVSets=True)
                print(f"Target UV sets after: {trg_uv_sets_after}")
            else:
                self.update_status(f"Error: No corresponding imported object for {orig_obj}")
        
        for obj in imported_transforms:
            try:
                cmds.delete(obj)
                print(f"Deleted imported object: {obj}")
            except Exception as e:
                print(f"Failed to delete {obj}: {e}")
        if cmds.namespace(exists="RIZOMUV"):
            try:
                cmds.namespace(removeNamespace="RIZOMUV", mergeNamespaceWithRoot=True)
                print("Removed namespace RIZOMUV")
            except Exception as e:
                print(f"Failed to remove namespace RIZOMUV: {e}")
        cmds.select(original_objs, replace=True)
        self.update_status(f"UVs imported to {target_uv_set}")

    def update_status(self, message):
        self.status_label.setText(message)

def get_maya_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)

def run():
    parent = get_maya_window()
    win = RizomUVBridgeWindow(parent)
    win.show(dockable=True, area="right", floating=False)
    return win

if __name__ == "__main__":
    run()