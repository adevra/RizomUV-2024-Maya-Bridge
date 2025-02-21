# ---------------------------------- Constants and Defaults ----------------------------------
import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMayaUI as omui
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import subprocess, tempfile, os, platform
import base64
import xml.dom.minidom as xml
import sys

if sys.version_info.major >= 3 and sys.version_info.minor >= 11:  # Maya 2025 (Python 3.11+)
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance
else:  
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance

PATH_DEFAULTS = {
    "Windows": r"C:\Program Files\Rizom Lab\RizomUV 2024.0\rizomuv.exe",
    "Darwin": "/Applications/RizomUV 2024.0.app",
    "Linux": "/usr/local/bin/rizomuv"
}

logo_encoded = "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"

# ---------------------------------- Configuration Manager ----------------------------------
class ConfigManager:
    def __init__(self):
        self.storage_path = os.path.join(tempfile.gettempdir(), "RizomUVBridge")
        self.config_xml = os.path.join(self.storage_path, "settings.xml")
        self.lua_control_file = os.path.join(self.storage_path, "rizomuv_control_script.lua").replace("\\", "/")
        self.ensure_storage_exists()
        try:
            self.load_config()
        except:
            self.set_initial_config()
            self.save_config()
            self.load_config()

    def ensure_storage_exists(self):
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)
        if not os.path.exists(self.config_xml):
            self.set_initial_config()
            self.save_config()

    def set_initial_config(self):
        self.rizom_location = PATH_DEFAULTS.get(platform.system(), PATH_DEFAULTS["Windows"])
        self.output_file = os.path.join(self.storage_path, "RizomUVMayaBridge.fbx").replace("\\", "/")
        self.include_uvs = True
        self.pack_quality = 2  # Default to "High"
        self.pack_iterations = 256

    def load_config(self):
        doc = xml.parse(self.config_xml)
        root = doc.getElementsByTagName("Settings")[0]
        self.rizom_location = root.getAttribute("rizomPath")
        self.output_file = root.getAttribute("exportFile")
        self.include_uvs = root.getAttribute("loadUVs").lower() == "true"
        self.pack_quality = int(root.getAttribute("quality") or 2)
        self.pack_iterations = int(root.getAttribute("mutations") or 256)

    def save_config(self):
        doc = xml.Document()
        root = doc.createElement("Settings")
        root.setAttribute("rizomPath", self.rizom_location)
        root.setAttribute("exportFile", self.output_file)
        root.setAttribute("loadUVs", str(self.include_uvs))
        root.setAttribute("quality", str(self.pack_quality))
        root.setAttribute("mutations", str(self.pack_iterations))
        doc.appendChild(root)
        with open(self.config_xml, "w") as f:
            doc.writexml(f, indent="  ", addindent="  ", newl="\n")

# ---------------------------------- Bridge Interface ----------------------------------
class UVBridgePanel(MayaQWidgetDockableMixin, QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(UVBridgePanel, self).__init__(parent)
        self.config = ConfigManager()
        self.setWindowTitle("RizomUV Bridge")
        self.setMinimumWidth(250)
        # Post-process attributes
        self.edge_angle_threshold = 45.1  # Default angle
        self.use_angle_tolerance = True  # Default checkbox state
        self.build_interface()
        self.setup_handlers()

    # ---------------------------------- Interface Setup ----------------------------------
    def build_interface(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)

        settings_group = QtWidgets.QGroupBox("Settings")
        settings_layout = QtWidgets.QVBoxLayout()
        self.location_input = QtWidgets.QLineEdit(self.config.rizom_location)
        self.location_input.setToolTip("Path to the RizomUV executable")
        self.browse_btn = QtWidgets.QPushButton("Browse")
        path_layout = QtWidgets.QHBoxLayout()
        path_layout.addWidget(QtWidgets.QLabel("RizomUV Path:"))
        path_layout.addWidget(self.location_input)
        path_layout.addWidget(self.browse_btn)
        settings_layout.addLayout(path_layout)
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        ops_group = QtWidgets.QGroupBox("UV Operations")
        ops_layout = QtWidgets.QVBoxLayout()
        self.transfer_btn = QtWidgets.QPushButton("Send to RizomUV")
        self.transfer_btn.setToolTip("Export selected geometry to RizomUV")
        self.retrieve_btn = QtWidgets.QPushButton("Get UVs")
        self.retrieve_btn.setToolTip("Import UVs from RizomUV to the selected UV set")
        self.uv_toggle = QtWidgets.QCheckBox("With Existing UVs")
        self.uv_toggle.setChecked(self.config.include_uvs)
        self.uv_toggle.setToolTip("Include existing UVs when exporting to RizomUV")
        self.uv_selector = QtWidgets.QComboBox()
        self.refresh_uv_options()
        ops_layout.addWidget(self.transfer_btn)
        ops_layout.addWidget(self.uv_toggle)
        ops_layout.addWidget(QtWidgets.QLabel("UV Set:"))
        ops_layout.addWidget(self.uv_selector)
        ops_layout.addWidget(self.retrieve_btn)
        ops_group.setLayout(ops_layout)
        main_layout.addWidget(ops_group)

        packer_group = QtWidgets.QGroupBox("UV Packer")
        packer_layout = QtWidgets.QVBoxLayout()
        self.auto_pack_btn = QtWidgets.QPushButton("Auto Pack")
        self.auto_pack_btn.setToolTip("Export geometry and pack UVs in RizomUV")
        self.quality_selector = QtWidgets.QComboBox()
        self.quality_selector.addItems(["Low", "Normal", "High", "Higher", "Ultra"])
        self.quality_selector.setCurrentIndex(self.config.pack_quality)
        self.quality_selector.setToolTip("Select quality level")
        self.iterations_spinner = QtWidgets.QSpinBox()
        self.iterations_spinner.setRange(1, 1000)
        self.iterations_spinner.setValue(self.config.pack_iterations)
        self.iterations_spinner.setToolTip("Number of packing iterations to attempt")
        packer_layout.addWidget(self.auto_pack_btn)
        packer_layout.addWidget(QtWidgets.QLabel("Quality:"))
        packer_layout.addWidget(self.quality_selector)
        packer_layout.addWidget(QtWidgets.QLabel("Iterations:"))
        packer_layout.addWidget(self.iterations_spinner)
        packer_group.setLayout(packer_layout)
        main_layout.addWidget(packer_group)

        post_group = QtWidgets.QGroupBox("Post Process")
        post_layout = QtWidgets.QVBoxLayout()
        self.edge_hardener_btn = QtWidgets.QPushButton("Harden UV Edges")
        self.edge_hardener_btn.setToolTip("Softens all normals, then hardens UV border edges based on angle")
        self.tolerance_toggle = QtWidgets.QCheckBox("Soften Tolerance")
        self.tolerance_toggle.setChecked(self.use_angle_tolerance)
        self.tolerance_toggle.setToolTip("Enable to soften edges below the specified angle")
        angle_layout = QtWidgets.QHBoxLayout()
        angle_layout.addWidget(QtWidgets.QLabel("Angle:"))
        self.angle_adjuster = QtWidgets.QDoubleSpinBox()
        self.angle_adjuster.setRange(0.1, 90.1)
        self.angle_adjuster.setValue(self.edge_angle_threshold)
        self.angle_adjuster.setSingleStep(0.1)
        self.angle_adjuster.setToolTip("Angle threshold for softening/hardening UV border edges")
        angle_layout.addWidget(self.angle_adjuster)
        post_layout.addWidget(self.edge_hardener_btn)
        post_layout.addWidget(self.tolerance_toggle)
        post_layout.addLayout(angle_layout)
        post_group.setLayout(post_layout)
        main_layout.addWidget(post_group)

        self.feedback_label = QtWidgets.QLabel("Ready")
        self.feedback_label.setAlignment(QtCore.Qt.AlignCenter)
        main_layout.addWidget(self.feedback_label)

        image_data = base64.b64decode(logo_encoded)
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

    # ---------------------------------- Event Handlers ----------------------------------
    def setup_handlers(self):
        self.transfer_btn.clicked.connect(lambda: self.dispatch_to_rizom(pack=False))
        self.auto_pack_btn.clicked.connect(lambda: self.dispatch_to_rizom(pack=True))
        self.retrieve_btn.clicked.connect(self.fetch_from_rizom)
        self.uv_toggle.stateChanged.connect(self.persist_config)
        self.browse_btn.clicked.connect(self.locate_rizom)
        self.quality_selector.currentIndexChanged.connect(self.persist_config)
        self.iterations_spinner.valueChanged.connect(self.persist_config)
        cmds.scriptJob(event=["SelectionChanged", self.refresh_uv_options], parent=self.objectName())

        self.edge_hardener_btn.clicked.connect(self.process_uv_edges)
        self.tolerance_toggle.stateChanged.connect(self.toggle_tolerance)
        self.angle_adjuster.valueChanged.connect(self.adjust_angle)

    # ---------------------------------- Utility Functions ----------------------------------
    def locate_rizom(self):
        path = QtWidgets.QFileDialog.getOpenFileName(self, "Locate RizomUV", self.config.rizom_location)[0]
        if path:
            self.location_input.setText(path)
            self.config.rizom_location = path
            self.config.save_config()

    def refresh_uv_options(self):
        current_choice = self.uv_selector.currentText() if self.uv_selector.count() else ""
        self.uv_selector.clear()
        sel_objects = cmds.ls(sl=True, tr=True)
        if sel_objects:
            uv_sets = cmds.polyUVSet(sel_objects[0], query=True, allUVSets=True) or ["map1"]
            options = ["All UV Sets"] + uv_sets
            self.uv_selector.addItems(options)
            if current_choice in options:
                self.uv_selector.setCurrentIndex(options.index(current_choice))
            else:
                self.uv_selector.setCurrentIndex(1 if len(options) > 1 else 0)

    def persist_config(self):
        self.config.include_uvs = self.uv_toggle.isChecked()
        self.config.rizom_location = self.location_input.text()
        self.config.pack_quality = self.quality_selector.currentIndex()
        self.config.pack_iterations = self.iterations_spinner.value()
        self.config.save_config()

    def set_feedback(self, message):
        self.feedback_label.setText(message)

    # ---------------------------------- Transfer and Retrieve Functions ----------------------------------
    def dispatch_to_rizom(self, pack=False):
        import time
        selected_items = cmds.ls(selection=True, long=True, transforms=True)
        if not selected_items:
            self.set_feedback("Error: No geometry selected.")
            return
        
        use_existing_uvs = self.uv_toggle.isChecked()
        target_file = self.config.output_file
        chosen_uv_set = self.uv_selector.currentText()
        
        if not cmds.pluginInfo("fbxmaya", loaded=True, query=True):
            cmds.loadPlugin("fbxmaya")
        cmds.select(selected_items, replace=True)
        
        if use_existing_uvs or (pack and chosen_uv_set != "All UV Sets"):
            for item in selected_items:
                shapes = cmds.listRelatives(item, shapes=True, fullPath=True, noIntermediate=True)
                if shapes and chosen_uv_set in cmds.polyUVSet(shapes[0], query=True, allUVSets=True):
                    cmds.polyUVSet(shapes[0], currentUVSet=True, uvSet=chosen_uv_set)
                    print(f"Set current UV set to {chosen_uv_set} on {item}")
                else:
                    print(f"Warning: UV set {chosen_uv_set} not found on {item}, using default.")
        
        mel.eval('FBXExportSmoothingGroups -v true;')
        mel.eval('FBXExportTriangulate -v false;')
        mel.eval('FBXExportSmoothMesh -v false;')
        mel.eval('FBXExportUpAxis Y;')
        mel.eval(f'FBXExport -f "{target_file}" -s;')
        self.set_feedback(f"Exported to {target_file} with UV set {chosen_uv_set if use_existing_uvs or pack else 'none'}")
        
        if pack:
            quality_levels = {0: 128, 1: 256, 2: 512, 3: 1024, 4: 2048}
            quality = quality_levels[self.quality_selector.currentIndex()]
            iterations = self.iterations_spinner.value()
            if chosen_uv_set == "All UV Sets":
                lua_script = f'''
ZomLoad({{File={{Path="{target_file}", ImportGroups=true, XYZUVW=true, UVWProps=true}}, NormalizeUVW=false}})
ZomUvset({{Mode="SetCurrent", Name="map1"}})
ZomUnfold({{PrimType="Island", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, BorderIntersections=true, TriangleFlips=true}})
ZomPack({{ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={{Mode=2}}, Rotate={{}}, Translate=true, LayoutScalingMode=2, MaxMutations={iterations}, Resolution={quality}}})
ZomSave({{File={{Path="{target_file}", UVWProps=true}}, __UpdateUIObjFileName=true}})
'''
            else:
                lua_script = f'''
ZomLoad({{File={{Path="{target_file}", ImportGroups=true, XYZUVW=true, UVWProps=true}}, NormalizeUVW=false}})
ZomUvset({{Mode="SetCurrent", Name="{chosen_uv_set}"}})
ZomUnfold({{PrimType="Island", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, BorderIntersections=true, TriangleFlips=true}})
ZomPack({{ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={{Mode=2}}, Rotate={{}}, Translate=true, LayoutScalingMode=2, MaxMutations={iterations}, Resolution={quality}}})
ZomSave({{File={{Path="{target_file}", UVWProps=true}}, __UpdateUIObjFileName=true}})
'''
        elif use_existing_uvs:
            lua_script = f'''
ZomLoad({{File={{Path="{target_file}", ImportGroups=true, UVWProps=true, XYZUVW=true}}, NormalizeUVW=false}})
ZomUvset({{Mode="SetCurrent", Name="{chosen_uv_set}"}})
ZomSave({{File={{Path="{target_file}", UVWProps=true}}, __UpdateUIObjFileName=true}})
'''
        else:
            lua_script = f'''
ZomLoad({{File={{Path="{target_file}", ImportGroups=true, XYZ=true}}, NormalizeUVW=true}})
ZomUvset({{Mode="SetCurrent", Name="{chosen_uv_set}"}})
ZomUnfold({{PrimType="Island", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, BorderIntersections=true, TriangleFlips=true}})
ZomPack({{ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={{Mode=2}}, Rotate={{}}, Translate=true, LayoutScalingMode=2}})
ZomSave({{File={{Path="{target_file}", UVWProps=true}}, __UpdateUIObjFileName=true}})
'''
        
        with open(self.config.lua_control_file, "w") as f:
            f.write(lua_script)
        
        rizom_active = False
        system = platform.system()
        if system == "Windows":
            try:
                tasks = subprocess.check_output(['tasklist'], stderr=subprocess.STDOUT).decode().lower()
                if 'rizomuv.exe' in tasks:
                    rizom_active = True
            except subprocess.CalledProcessError as e:
                print(f"Failed to check running processes: {e}")
        
        if not rizom_active:
            self.set_feedback("Starting RizomUV...")
            try:
                if system == "Windows":
                    cmd = f'"{self.config.rizom_location}" -cfi "{self.config.lua_control_file}"'
                    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = process.communicate(timeout=10)
                    if process.returncode != 0:
                        raise subprocess.SubprocessError(f"RizomUV failed to start: {stderr.decode()}")
                elif system == "Darwin":
                    cmd = ['open', '-a', self.config.rizom_location, '--args', '-cfi', self.config.lua_control_file]
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = process.communicate(timeout=10)
                    if process.returncode != 0:
                        raise subprocess.SubprocessError(f"RizomUV failed to start: {stderr.decode()}")
                else:
                    cmd = [self.config.rizom_location, '-cfi', self.config.lua_control_file]
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = process.communicate(timeout=10)
                    if process.returncode != 0:
                        raise subprocess.SubprocessError(f"RizomUV failed to start: {stderr.decode()}")
                time.sleep(5)
                self.set_feedback("RizomUV started successfully")
            except (subprocess.SubprocessError, subprocess.TimeoutExpired, Exception) as e:
                self.set_feedback(f"Failed to start RizomUV: {str(e)}")
                print(f"Command attempted: {cmd}")
                return
        else:
            os.utime(self.config.lua_control_file, None)
            self.set_feedback("RizomUV already running, script updated")
        
        self.set_feedback("Sent to RizomUV" if not pack else "Sent to RizomUV for packing")

    def fetch_from_rizom(self):
        source_objects = cmds.ls(selection=True, long=True, transforms=True)
        if not source_objects:
            self.set_feedback("Error: No geometry selected.")
            return
        source_file = self.config.output_file
        target_uv_layer = self.uv_selector.currentText()
        
        if not os.path.exists(source_file):
            self.set_feedback(f"Error: Could not locate {source_file}")
            return
        
        existing_namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []
        for ns in existing_namespaces:
            if "RIZOMUV" in ns:
                try:
                    cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
                    print(f"Removed namespace: {ns}")
                except Exception as e:
                    print(f"Failed to remove namespace {ns}: {e}")
        
        if not cmds.pluginInfo("fbxmaya", loaded=True, query=True):
            cmds.loadPlugin("fbxmaya")
        cmds.file(source_file, i=True, type="FBX", ignoreVersion=True, mergeNamespacesOnClash=True, namespace="RIZOMUV")
        
        imported_items = cmds.ls("RIZOMUV:*", transforms=True, long=True)
        if not imported_items:
            self.set_feedback("Error: No objects imported from RizomUV.")
            return
        
        for orig_item in source_objects:
            item_name = orig_item.split('|')[-1]
            print(f"Processing original: {orig_item}, base name: {item_name}")
            matched_import = None
            for imp_item in imported_items:
                imp_name = imp_item.split(':')[-1].split('|')[-1]
                if imp_name == item_name:
                    matched_import = imp_item
                    break
            
            if matched_import:
                print(f"Found match: {matched_import}")
                source_shapes = cmds.listRelatives(matched_import, shapes=True, fullPath=True, noIntermediate=True)
                target_shapes = cmds.listRelatives(orig_item, shapes=True, fullPath=True, noIntermediate=True)
                if not source_shapes or not target_shapes:
                    self.set_feedback(f"Error: Could not find shapes for {matched_import} or {orig_item}")
                    print(f"Source shapes: {source_shapes}, Target shapes: {target_shapes}")
                    continue
                
                src = source_shapes[0]
                trg = target_shapes[0]
                print(f"Source: {src}, Target: {trg}")
                
                src_uv_layers = cmds.polyUVSet(src, query=True, allUVSets=True) or ["map1"]
                trg_uv_layers = cmds.polyUVSet(trg, query=True, allUVSets=True) or []
                print(f"Source UV sets: {src_uv_layers}")
                print(f"Target UV sets before: {trg_uv_layers}")
                
                if target_uv_layer == "All UV Sets":
                    for src_uv in src_uv_layers:
                        if src_uv not in trg_uv_layers:
                            cmds.polyUVSet(trg, create=True, uvSet=src_uv)
                            print(f"Created UV set {src_uv} on {trg}")
                        try:
                            cmds.polyUVSet(src, currentUVSet=True, uvSet=src_uv)
                            cmds.polyUVSet(trg, currentUVSet=True, uvSet=src_uv)
                            cmds.transferAttributes(
                                src, trg,
                                transferPositions=0,
                                transferNormals=0,
                                transferUVs=2,
                                transferColors=0,
                                sampleSpace=4,
                                sourceUvSpace=src_uv,
                                targetUvSpace=src_uv,
                                searchMethod=3,
                                flipUVs=0,
                                colorBorders=1
                            )
                            cmds.delete(trg, constructionHistory=True)
                            print(f"Transferred UVs from {src_uv} to {src_uv} on {trg}")
                        except Exception as e:
                            print(f"Error transferring UV set {src_uv}: {e}")
                            self.set_feedback(f"Error transferring UVs for {item_name}")
                else:
                    if target_uv_layer not in src_uv_layers:
                        self.set_feedback(f"Error: Selected UV set '{target_uv_layer}' not found in imported data.")
                        continue
                    if target_uv_layer not in trg_uv_layers:
                        cmds.polyUVSet(trg, create=True, uvSet=target_uv_layer)
                        print(f"Created UV set {target_uv_layer} on {trg}")
                    try:
                        cmds.polyUVSet(src, currentUVSet=True, uvSet=target_uv_layer)
                        cmds.polyUVSet(trg, currentUVSet=True, uvSet=target_uv_layer)
                        cmds.transferAttributes(
                            src, trg,
                            transferPositions=0,
                            transferNormals=0,
                            transferUVs=2,
                            transferColors=0,
                            sampleSpace=4,
                            sourceUvSpace=target_uv_layer,
                            targetUvSpace=target_uv_layer,
                            searchMethod=3,
                            flipUVs=0,
                            colorBorders=1
                        )
                        cmds.delete(trg, constructionHistory=True)
                        print(f"Transferred UVs from {target_uv_layer} to {target_uv_layer} on {trg}")
                    except Exception as e:
                        print(f"Error transferring UV set {target_uv_layer}: {e}")
                        self.set_feedback(f"Error transferring UVs for {item_name}")
                
                trg_uv_layers_after = cmds.polyUVSet(trg, query=True, allUVSets=True)
                print(f"Target UV sets after: {trg_uv_layers_after}")
            else:
                self.set_feedback(f"Error: No corresponding imported object for {orig_item}")
        
        for item in imported_items:
            try:
                cmds.delete(item)
                print(f"Deleted imported object: {item}")
            except Exception as e:
                print(f"Failed to delete {item}: {e}")
        if cmds.namespace(exists="RIZOMUV"):
            try:
                cmds.namespace(removeNamespace="RIZOMUV", mergeNamespaceWithRoot=True)
                print("Removed namespace RIZOMUV")
            except Exception as e:
                print(f"Failed to remove namespace RIZOMUV: {e}")
        cmds.select(source_objects, replace=True)
        self.set_feedback(f"UVs imported to {target_uv_layer}")

    # ---------------------------------- Post-Process Functions ---------------------------------
    def adjust_angle(self):
        self.edge_angle_threshold = self.angle_adjuster.value()
        print(f"Soften tolerance angle set to {self.edge_angle_threshold}")

    def toggle_tolerance(self):
        self.use_angle_tolerance = self.tolerance_toggle.isChecked()
        print(f"Soften tolerance checkbox {'on' if self.use_angle_tolerance else 'off'}")

    def process_uv_edges(self):
        selected_items = cmds.ls(selection=True, objectsOnly=True)
        if not selected_items:
            self.set_feedback("Error: No objects selected for hardening UV edges.")
            return
        
        for item in selected_items:
            cmds.selectMode(object=True)
            cmds.polySoftEdge(item, angle=180, constructionHistory=False)
            
            cmds.ConvertSelectionToEdges()
            mel.eval("SelectUVBorderComponents;")
            uv_border_edges = cmds.ls(selection=True, flatten=True)
            
            if uv_border_edges:
                cmds.polySoftEdge(uv_border_edges, angle=0, constructionHistory=False)
            
            if self.use_angle_tolerance:
                cmds.polySelectConstraint(mode=2, type=0x0008, smoothness=1, angle=True, anglebound=[0, 54])
                cmds.polySoftEdge(angle=self.edge_angle_threshold, constructionHistory=False)
                cmds.polySelectConstraint(mode=0)
            
            cmds.selectMode(object=True)
            cmds.delete(item, constructionHistory=True)
        
        self.set_feedback("Normals softened, UV border edges hardened" if not self.use_angle_tolerance else 
                          "Normals softened, UV border edges below tolerance hardened")
        print(self.set_feedback.__self__.feedback_label.text())

# ---------------------------------- Launcher ---------------------------------------
def fetch_maya_root():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)

def launch_tool():
    root = fetch_maya_root()
    panel = UVBridgePanel(root)
    panel.show(dockable=True, area="right", floating=False)
    return panel

if __name__ == "__main__":
    launch_tool()