# ---------------------------------- Constants and Defaults ----------------------------------
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

# Replace with your actual base64 string
base64_image = "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"

# ---------------------------------- Settings Class ----------------------------------
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

# ---------------------------------- Main Window Class ----------------------------------
class RizomUVBridgeWindow(MayaQWidgetDockableMixin, QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(RizomUVBridgeWindow, self).__init__(parent)
        self.settings = Settings()
        self.setWindowTitle("RizomUV Bridge")
        self.setMinimumWidth(250)
        # Post-process attributes
        self.soften_tolerance_value = 45.1  # Default angle
        self.soften_tolerance_enabled = True  # Default checkbox state
        self.create_ui()
        self.create_connections()

    # ---------------------------------- UI Creation ----------------------------------
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

        # Post Process Group
        post_process_group = QtWidgets.QGroupBox("Post Process")
        post_process_layout = QtWidgets.QVBoxLayout()
        self.harden_uv_edges_button = QtWidgets.QPushButton("Harden UV Edges")
        self.harden_uv_edges_button.setToolTip("Softens all normals, then hardens UV border edges based on angle")
        self.show_edges_button = QtWidgets.QPushButton("Show Edges")
        self.show_edges_button.setToolTip("Toggles polygon edge visibility on/off")
        self.soften_tolerance_check = QtWidgets.QCheckBox("Soften Tolerance")
        self.soften_tolerance_check.setChecked(self.soften_tolerance_enabled)
        self.soften_tolerance_check.setToolTip("Enable to soften edges below the specified angle")
        angle_layout = QtWidgets.QHBoxLayout()
        angle_layout.addWidget(QtWidgets.QLabel("Angle:"))
        self.angle_field = QtWidgets.QDoubleSpinBox()
        self.angle_field.setRange(0.1, 90.1)
        self.angle_field.setValue(self.soften_tolerance_value)
        self.angle_field.setSingleStep(0.1)
        self.angle_field.setToolTip("Angle threshold for softening/hardening UV border edges")
        angle_layout.addWidget(self.angle_field)
        post_process_layout.addWidget(self.harden_uv_edges_button)
        post_process_layout.addWidget(self.show_edges_button)
        post_process_layout.addWidget(self.soften_tolerance_check)
        post_process_layout.addLayout(angle_layout)
        post_process_group.setLayout(post_process_layout)
        main_layout.addWidget(post_process_group)

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

    # ---------------------------------- Event Connections ----------------------------------
    def create_connections(self):
        self.send_button.clicked.connect(lambda: self.send_to_rizom(pack=False))
        self.pack_button.clicked.connect(lambda: self.send_to_rizom(pack=True))
        self.get_button.clicked.connect(self.get_from_rizom)
        self.uvs_check.stateChanged.connect(self.save_settings)
        self.path_button.clicked.connect(self.browse_path)
        self.quality_combo.currentIndexChanged.connect(self.save_settings)
        self.mutations_spin.valueChanged.connect(self.save_settings)
        cmds.scriptJob(event=["SelectionChanged", self.update_uv_sets], parent=self.objectName())
        # Post-process connections
        self.harden_uv_edges_button.clicked.connect(self.harden_uv_edges)
        self.show_edges_button.clicked.connect(self.show_edges)
        self.soften_tolerance_check.stateChanged.connect(self.soften_tolerance_value_changed)
        self.angle_field.valueChanged.connect(self.float_value_changed)

    # ---------------------------------- Utility Methods ----------------------------------
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

    def update_status(self, message):
        self.status_label.setText(message)

    # ---------------------------------- Export and Import Methods ----------------------------------
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
        
        if include_uvs or (pack and selected_uv_set != "All UV Sets"):
            for obj in selected_objs:
                shapes = cmds.listRelatives(obj, shapes=True, fullPath=True, noIntermediate=True)
                if shapes and selected_uv_set in cmds.polyUVSet(shapes[0], query=True, allUVSets=True):
                    cmds.polyUVSet(shapes[0], currentUVSet=True, uvSet=selected_uv_set)
                    print(f"Set current UV set to {selected_uv_set} on {obj}")
                else:
                    print(f"Warning: UV set {selected_uv_set} not found on {obj}, using default.")
        
        mel.eval('FBXExportSmoothingGroups -v true;')
        mel.eval('FBXExportTriangulate -v false;')
        mel.eval('FBXExportSmoothMesh -v false;')
        mel.eval('FBXExportUpAxis Y;')
        mel.eval(f'FBXExport -f "{export_file}" -s;')
        self.update_status(f"Exported to {export_file} with UV set {selected_uv_set if include_uvs or pack else 'none'}")
        
        if pack:
            quality_map = {0: 128, 1: 256, 2: 512, 3: 1024, 4: 2048}
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
                time.sleep(5)
                self.update_status("RizomUV started successfully")
            except (subprocess.SubprocessError, subprocess.TimeoutExpired, Exception) as e:
                self.update_status(f"Failed to start RizomUV: {str(e)}")
                print(f"Command attempted: {cmd}")
                return
        else:
            os.utime(self.settings.lua_script_path, None)
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

    # ---------------------------------- Post-Process Methods ----------------------------------
    def float_value_changed(self):
        self.soften_tolerance_value = self.angle_field.value()
        print(f"Soften tolerance angle set to {self.soften_tolerance_value}")

    def soften_tolerance_value_changed(self):
        self.soften_tolerance_enabled = self.soften_tolerance_check.isChecked()
        print(f"Soften tolerance checkbox {'on' if self.soften_tolerance_enabled else 'off'}")

    def harden_uv_edges(self):
        selected_objs = cmds.ls(selection=True, objectsOnly=True)
        if not selected_objs:
            self.update_status("Error: No objects selected for hardening UV edges.")
            return
        
        for obj in selected_objs:
            # Switch to object mode and soften all edges
            cmds.selectMode(object=True)
            cmds.polySoftEdge(obj, angle=180, constructionHistory=False)
            
            # Convert to edges and select UV borders
            cmds.ConvertSelectionToEdges()
            mel.eval("SelectUVBorderComponents;")
            uv_border_edges = cmds.ls(selection=True, flatten=True)
            
            # Harden UV border edges
            if uv_border_edges:
                cmds.polySoftEdge(uv_border_edges, angle=0, constructionHistory=False)
            
            # Apply tolerance if enabled
            if self.soften_tolerance_enabled:
                cmds.polySelectConstraint(mode=2, type=0x0008, smoothness=1, angle=True, anglebound=[0, 54])
                cmds.polySoftEdge(angle=self.soften_tolerance_value, constructionHistory=False)
                cmds.polySelectConstraint(mode=0)  # Reset constraints
            
            # Clean up
            cmds.selectMode(object=True)
            cmds.delete(obj, constructionHistory=True)
        
        self.update_status("Normals softened, UV border edges hardened" if not self.soften_tolerance_enabled else 
                          "Normals softened, UV border edges below tolerance hardened")
        print(self.update_status.__self__.status_label.text())

    def show_edges(self):
        current_mode = cmds.displayPref(query=True, wireframeOnShaded=True)
        if current_mode == "full":
            cmds.displayPref(wireframeOnShaded="none")
            self.update_status("Edge display style changed to NONE")
            print("Edge display style changed to NONE")
        elif current_mode == "none":
            cmds.displayPref(wireframeOnShaded="full")
            self.update_status("Edge display style changed to FULL")
            print("Edge display style changed to FULL")
        else:
            cmds.displayPref(wireframeOnShaded="full")
            self.update_status("Edge display style defaulted to FULL")
            print("Edge display style defaulted to FULL")

# ---------------------------------- Main Execution ----------------------------------
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