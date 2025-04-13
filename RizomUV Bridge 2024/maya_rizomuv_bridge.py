import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMayaUI as omui
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import subprocess, tempfile, os, platform, sys, locale, base64, logging
import xml.dom.minidom as xml
from xml.parsers.expat import ExpatError

if sys.version_info.major >= 3 and sys.version_info.minor >= 11:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance
else:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance

PATH_DEFAULTS = {
    "Windows": r"C:\Program Files\Rizom Lab\RizomUV 2024.0\rizomuv.exe",
    "Darwin": "/Applications/RizomUV 2024.1.app",
    "Linux": "/usr/local/bin/rizomuv"
}

logo_encoded = "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"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def safe_decode_subprocess(command):
    encodings_to_try = [
        locale.getpreferredencoding(False),
        'utf-8',
        'cp866',
        'cp1251',
        'latin1'
    ]
    for enc in encodings_to_try:
        try:
            output = subprocess.check_output(command, stderr=subprocess.STDOUT).decode(enc, errors='replace')
            return output
        except (UnicodeDecodeError, subprocess.SubprocessError):
            continue
    return ""

class ConfigManager:
    def __init__(self):
        try:
            maya_prefs_dir = cmds.internalVar(userPrefDir=True)
            self.storage_path = os.path.join(maya_prefs_dir, "RizomUVBridge")
        except Exception:
            self.storage_path = os.path.join(tempfile.gettempdir(), "RizomUVBridge")
            logging.warning("Could not get Maya prefs dir, using temp directory for settings.")

        self.config_xml = os.path.join(self.storage_path, "settings.xml")
        self.lua_control_file = os.path.join(self.storage_path, "rizomuv_control_script.lua").replace("\\", "/")
        self.ensure_storage_exists()
        try:
            self.load_config()
        except FileNotFoundError:
            logging.info("Settings file not found. Creating default configuration.")
            self.set_initial_config()
            self.save_config()
            self.load_config()
        except (ExpatError, IndexError, ValueError, TypeError) as e:
            logging.error(f"Error parsing settings file '{self.config_xml}': {e}. Resetting to defaults.")
            self.set_initial_config()
            self.save_config()
            self.load_config()
        except Exception as e:
            logging.error(f"Unexpected error loading configuration: {e}. Resetting to defaults.")
            self.set_initial_config()
            self.save_config()
            self.load_config()

    def ensure_storage_exists(self):
        if not os.path.exists(self.storage_path):
            try:
                os.makedirs(self.storage_path)
                logging.info(f"Created settings directory: {self.storage_path}")
            except OSError as e:
                 logging.error(f"Failed to create settings directory {self.storage_path}: {e}")

        if not os.path.exists(self.config_xml):
             if os.access(self.storage_path, os.W_OK):
                 self.set_initial_config()
                 self.save_config()
             else:
                 logging.error(f"Cannot write to settings directory: {self.storage_path}. Cannot create default config.")

    def set_initial_config(self):
        self.rizom_location = PATH_DEFAULTS.get(platform.system(), PATH_DEFAULTS["Windows"])
        self.output_file = os.path.join(self.storage_path, "RizomUVMayaBridge.fbx").replace("\\", "/")
        self.include_uvs = True
        self.pack_quality = 2
        self.pack_iterations = 256
        logging.info("Set initial default configuration values.")


    def load_config(self):
        doc = xml.parse(self.config_xml)
        root = doc.getElementsByTagName("Settings")[0]
        self.rizom_location = root.getAttribute("rizomPath")
        self.output_file = root.getAttribute("exportFile")
        self.include_uvs = root.getAttribute("loadUVs").lower() == "true"
        self.pack_quality = int(root.getAttribute("quality") or 2)
        self.pack_iterations = int(root.getAttribute("mutations") or 256)
        logging.info(f"Loaded configuration from {self.config_xml}")

    def save_config(self):
        try:
            doc = xml.Document()
            root = doc.createElement("Settings")
            root.setAttribute("rizomPath", str(self.rizom_location))
            root.setAttribute("exportFile", str(self.output_file))
            root.setAttribute("loadUVs", str(self.include_uvs))
            root.setAttribute("quality", str(self.pack_quality))
            root.setAttribute("mutations", str(self.pack_iterations))
            doc.appendChild(root)
            with open(self.config_xml, "w") as f:
                doc.writexml(f, indent="  ", addindent="  ", newl="\n")
            logging.info(f"Saved configuration to {self.config_xml}")
        except IOError as e:
             logging.error(f"Failed to save configuration to {self.config_xml}: {e}")
        except Exception as e:
             logging.error(f"Unexpected error saving configuration: {e}")


class UVBridgePanel(MayaQWidgetDockableMixin, QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(UVBridgePanel, self).__init__(parent)
        self.config = ConfigManager()
        self.setWindowTitle("RizomUV Bridge")
        self.setMinimumWidth(250)
        self.edge_angle_threshold = 45.1
        self.use_angle_tolerance = True
        self.setObjectName("rizomUVBridgePanelInstance")
        self.build_interface()
        self.setup_handlers()
        logging.info("RizomUV Bridge Panel Initialized.")


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

        try:
            logo_data = base64.b64decode(logo_encoded)
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(logo_data, "PNG")
            scaled_pixmap = pixmap.scaled(100, 100, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            logo = QtWidgets.QLabel()
            logo.setPixmap(scaled_pixmap)
            logo.setAlignment(QtCore.Qt.AlignCenter)
            main_layout.addWidget(logo)
        except Exception as e:
            logging.error(f"Error loading logo from base64 data: {e}")

        main_layout.addStretch()


    def setup_handlers(self):
        self.transfer_btn.clicked.connect(lambda: self.dispatch_to_rizom(pack=False))
        self.auto_pack_btn.clicked.connect(lambda: self.dispatch_to_rizom(pack=True))
        self.retrieve_btn.clicked.connect(self.fetch_from_rizom)
        self.uv_toggle.stateChanged.connect(self.persist_config)
        self.browse_btn.clicked.connect(self.locate_rizom)
        self.location_input.editingFinished.connect(self.persist_config)
        self.quality_selector.currentIndexChanged.connect(self.persist_config)
        self.iterations_spinner.valueChanged.connect(self.persist_config)
        cmds.scriptJob(event=["SelectionChanged", self.refresh_uv_options], parent=self.objectName(), protected=True)
        self.edge_hardener_btn.clicked.connect(self.process_uv_edges)
        self.tolerance_toggle.stateChanged.connect(self.toggle_tolerance)
        self.angle_adjuster.valueChanged.connect(self.adjust_angle)

    def locate_rizom(self):
        original_os_native_dialog_pref = 0
        system = platform.system()
        mac_pref_changed = False
        current_path = self.location_input.text() or self.config.rizom_location
        start_dir = os.path.dirname(current_path) if os.path.exists(current_path) else ""

        try:
            if system == "Darwin":
                start_dir = "/Applications" if not start_dir or not os.path.exists(start_dir) and os.path.exists("/Applications") else start_dir or "/"
                try:
                    original_os_native_dialog_pref = cmds.optionVar(query="useOSNativeFileDialog")
                    if original_os_native_dialog_pref == 0:
                        logging.info("Temporarily switching Maya to OS Native file dialog for .app selection.")
                        cmds.optionVar(iv=("useOSNativeFileDialog", 1))
                        mac_pref_changed = True
                except Exception as e:
                    logging.warning(f"Could not query/set OS native dialog preference: {e}")
                path, _ = QtWidgets.QFileDialog.getOpenFileName(
                    self,
                    "Locate RizomUV Application (.app)",
                    start_dir,
                    "Applications (*.app)"
                )
            else:
                if system == "Windows":
                    file_filter = "Executables (*.exe);;All Files (*)"
                    start_dir = r"C:\Program Files" if not start_dir or not os.path.exists(start_dir) else start_dir
                else:
                    file_filter = "Executables (*);;All Files (*)"
                    start_dir = "/" if not start_dir or not os.path.exists(start_dir) else start_dir
                path, _ = QtWidgets.QFileDialog.getOpenFileName(
                    self,
                    "Locate RizomUV Executable",
                    start_dir,
                    file_filter
                )

            if path:
                valid_path = (
                    (system == "Darwin" and path.endswith(".app") and os.path.isdir(path)) or
                    (system == "Windows" and path.lower().endswith(".exe") and os.path.isfile(path)) or
                    (system == "Linux" and os.path.isfile(path) and os.access(path, os.X_OK))
                )
                if valid_path:
                    self.location_input.setText(path)
                    self.config.rizom_location = path
                    self.config.save_config()
                    logging.info(f"RizomUV path set to: {path}")
                else:
                    logging.warning(f"Selected path does not appear to be a valid RizomUV application/executable: {path}")
                    cmds.warning(f"Selected path may be invalid: {path}")

        except Exception as e:
            logging.error(f"Error during file dialog or path processing: {e}")
        finally:
            if mac_pref_changed:
                try:
                    logging.info(f"Restoring Maya file dialog preference to original value: {original_os_native_dialog_pref}")
                    cmds.optionVar(iv=("useOSNativeFileDialog", original_os_native_dialog_pref))
                except Exception as e:
                    logging.warning(f"Could not restore OS native dialog preference: {e}")

    def refresh_uv_options(self):
        current_choice = self.uv_selector.currentText() if self.uv_selector.count() else ""
        self.uv_selector.clear()
        sel_objects = cmds.ls(sl=True, tr=True)
        options = ["All UV Sets"]
        if sel_objects:
            try:
                uv_sets = cmds.polyUVSet(sel_objects[0], query=True, allUVSets=True) or ["map1"]
                options.extend(uv_sets)
            except Exception as e:
                 logging.warning(f"Could not query UV sets from {sel_objects[0]}: {e}. Using default.")
                 options.append("map1")

        self.uv_selector.addItems(options)

        if current_choice in options:
            self.uv_selector.setCurrentIndex(options.index(current_choice))
        elif len(options) > 1:
             self.uv_selector.setCurrentIndex(1)
        else:
             self.uv_selector.setCurrentIndex(0)


    def persist_config(self):
        self.config.include_uvs = self.uv_toggle.isChecked()
        self.config.rizom_location = self.location_input.text()
        self.config.pack_quality = self.quality_selector.currentIndex()
        self.config.pack_iterations = self.iterations_spinner.value()
        self.config.save_config()

    def set_feedback(self, message, level="info"):
        self.feedback_label.setText(message)
        if level == "info":
            logging.info(message)
            self.feedback_label.setStyleSheet("")
        elif level == "warning":
             logging.warning(message)
             self.feedback_label.setStyleSheet("QLabel { color : orange; }")
        elif level == "error":
             logging.error(message)
             self.feedback_label.setStyleSheet("QLabel { color : red; }")
        else:
             self.feedback_label.setStyleSheet("")


    def dispatch_to_rizom(self, pack=False):
        import time
        self.feedback_label.setStyleSheet("")
        selected_items = cmds.ls(selection=True, long=True, transforms=True)
        if not selected_items:
            self.set_feedback("Error: No geometry selected.", level="error")
            return

        rizom_path = self.config.rizom_location
        if not os.path.exists(rizom_path):
             self.set_feedback(f"Error: RizomUV path not found: {rizom_path}", level="error")
             return

        use_existing_uvs = self.uv_toggle.isChecked()
        target_file = self.config.output_file
        chosen_uv_set = self.uv_selector.currentText()

        if not cmds.pluginInfo("fbxmaya", loaded=True, query=True):
             try:
                cmds.loadPlugin("fbxmaya")
                logging.info("Loaded fbxmaya plugin.")
             except Exception as e:
                 self.set_feedback("Error: Failed to load FBX plugin.", level="error")
                 logging.error(f"Failed to load fbxmaya plugin: {e}")
                 return

        cmds.select(selected_items, replace=True)

        active_uv_set_for_export = "map1"
        if use_existing_uvs or (pack and chosen_uv_set != "All UV Sets"):
            active_uv_set_for_export = chosen_uv_set
            for item in selected_items:
                shapes = cmds.listRelatives(item, shapes=True, fullPath=True, noIntermediate=True)
                if shapes:
                    try:
                        all_sets = cmds.polyUVSet(shapes[0], query=True, allUVSets=True)
                        if chosen_uv_set in all_sets:
                            cmds.polyUVSet(shapes[0], currentUVSet=True, uvSet=chosen_uv_set)
                            logging.info(f"Set current UV set to {chosen_uv_set} on {item}")
                        else:
                            logging.warning(f"UV set '{chosen_uv_set}' not found on {item}, using default for export.")
                    except Exception as e:
                        logging.warning(f"Could not set/query UV set on {item}: {e}")
        else:
             for item in selected_items:
                shapes = cmds.listRelatives(item, shapes=True, fullPath=True, noIntermediate=True)
                if shapes:
                     try:
                        all_sets = cmds.polyUVSet(shapes[0], query=True, allUVSets=True)
                        if "map1" in all_sets:
                            cmds.polyUVSet(shapes[0], currentUVSet=True, uvSet="map1")
                            active_uv_set_for_export = "map1"
                     except Exception as e:
                        logging.warning(f"Could not set map1 as current on {item}: {e}")

        constraint_nodes = cmds.listConnections(selected_items, type='constraint')
        if constraint_nodes:
             logging.warning(f"Scene selection contains constraints: {list(set(constraint_nodes))}. Geometry position might differ unless baked.")

        try:
            mel.eval('FBXExportSmoothingGroups -v true;')
            mel.eval('FBXExportTriangulate -v false;')
            mel.eval('FBXExportSmoothMesh -v false;')
            mel.eval('FBXExportConstraints -v false;')
            mel.eval('FBXExportBakeComplexAnimation -v false;')
            mel.eval('FBXExportUpAxis Y;')
            cmds.file(target_file, force=True, options="v=0;", type="FBX export", pr=False, es=True)
            self.set_feedback(f"Exported selection to FBX.", level="info")
        except Exception as e:
            self.set_feedback(f"Error during FBX export: {e}", level="error")
            return

        quality_levels = {0: 128, 1: 256, 2: 512, 3: 1024, 4: 2048}
        quality = quality_levels.get(self.config.pack_quality, 512)
        iterations = self.config.pack_iterations

        lua_script_parts = []
        load_cmd_str = ""

        if use_existing_uvs:
             load_cmd_str = f'ZomLoad({{File={{Path="{target_file}", ImportGroups=true, XYZUVW=true, UVWProps=true}}, NormalizeUVW=false}})'
        else:
             load_cmd_str = f'ZomLoad({{File={{Path="{target_file}", ImportGroups=true, XYZ=true}}, NormalizeUVW=false}})'

        lua_script_parts.append(load_cmd_str)

        if use_existing_uvs:
             lua_script_parts.append(f'ZomUvset({{Mode="SetCurrent", Name="{active_uv_set_for_export}"}})')
             if pack:
                  lua_script_parts.append(f'ZomUnfold({{PrimType="Island", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, BorderIntersections=true, TriangleFlips=true}})')
                  lua_script_parts.append(f'ZomPack({{ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={{Mode=2}}, Rotate={{}}, Translate=true, LayoutScalingMode=2, MaxMutations={iterations}, Resolution={quality}}})')
        else:
             uv_set_to_generate = active_uv_set_for_export if active_uv_set_for_export != "All UV Sets" else "map1"
             lua_script_parts.append(f'ZomUvset({{Mode="SetCurrent", Name="{uv_set_to_generate}"}})')
             lua_script_parts.append(f'ZomUnfold({{PrimType="Island", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, BorderIntersections=true, TriangleFlips=true}})')
             lua_script_parts.append(f'ZomPack({{ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={{Mode=2}}, Rotate={{}}, Translate=true, LayoutScalingMode=2, MaxMutations={iterations}, Resolution={quality}}})')

        lua_script_parts.append(f'ZomSave({{File={{Path="{target_file}", UVWProps=true}}, __UpdateUIObjFileName=true}})')

        lua_script = "\n".join(lua_script_parts)

        try:
            with open(self.config.lua_control_file, "w") as f:
                f.write(lua_script)
            logging.info(f"Generated Lua script: {self.config.lua_control_file}")
            logging.debug(f"Lua Script Content:\n{lua_script}")
        except IOError as e:
             self.set_feedback(f"Error writing Lua script: {e}", level="error")
             return

        rizom_active = False
        system = platform.system()
        try:
            if system == "Windows":
                tasks = safe_decode_subprocess(['tasklist']).lower()
                if 'rizomuv.exe' in tasks:
                    rizom_active = True
            elif system == "Darwin":
                tasks = safe_decode_subprocess(['pgrep', '-f', 'RizomUV'])
                if tasks.strip():
                    rizom_active = True
            else:
                tasks = safe_decode_subprocess(['ps', 'aux']).lower()
                if 'rizomuv' in tasks:
                    rizom_active = True
        except Exception as e:
            logging.warning(f"Could not reliably determine if RizomUV is running: {e}")

        cmd = []
        cmd_str = ""
        if not rizom_active:
            self.set_feedback("Starting RizomUV...", level="info")
            try:
                if system == "Windows":
                    cmd_str = f'"{rizom_path}" -cfi "{self.config.lua_control_file}"'
                    process = subprocess.Popen(cmd_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                elif system == "Darwin":
                    cmd = ['open', '-a', rizom_path, '--args', '-cfi', self.config.lua_control_file]
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                else:
                    cmd = [rizom_path, '-cfi', self.config.lua_control_file]
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                try:
                     stdout, stderr = process.communicate(timeout=5)
                     if process.returncode != 0:
                          stderr_decoded = stderr.decode(locale.getpreferredencoding(False), errors='replace') if stderr else ""
                          raise subprocess.SubprocessError(f"RizomUV exited with code {process.returncode}. Error: {stderr_decoded}")
                     logging.info("RizomUV process started.")
                     time.sleep(2)
                     self.set_feedback("RizomUV started/running.", level="info")
                except subprocess.TimeoutExpired:
                     logging.info("RizomUV process started and likely running.")
                     self.set_feedback("RizomUV started/running.", level="info")

            except (subprocess.SubprocessError, FileNotFoundError, Exception) as e:
                self.set_feedback(f"Failed to start RizomUV: {e}", level="error")
                error_cmd = ' '.join(cmd) if cmd else cmd_str
                logging.error(f"Command attempted: {error_cmd}")
                return
        else:
            try:
                os.utime(self.config.lua_control_file, None)
                self.set_feedback("RizomUV already running, script updated.", level="info")
            except OSError as e:
                 self.set_feedback(f"Error updating script timestamp: {e}", level="error")
                 return

        final_message = "Sent to RizomUV" if not pack else "Sent to RizomUV for packing"
        self.set_feedback(final_message, level="info")


    def fetch_from_rizom(self):
        self.feedback_label.setStyleSheet("")
        source_objects = cmds.ls(selection=True, long=True, transforms=True)
        if not source_objects:
            self.set_feedback("Error: No geometry selected for UV import.", level="error")
            return

        source_file = self.config.output_file
        target_uv_layer = self.uv_selector.currentText()
        logging.info(f"Attempting to import from: {source_file} to UV set: {target_uv_layer}")

        if not os.path.exists(source_file):
            self.set_feedback(f"Error: Source FBX file not found: {source_file}", level="error")
            return

        import_namespace = "RIZOMUV_TEMP_NS"
        if cmds.namespace(exists=import_namespace):
             try:
                 cmds.namespace(removeNamespace=import_namespace, mergeNamespaceWithRoot=True)
                 logging.info(f"Removed existing namespace: {import_namespace}")
             except RuntimeError as e:
                 logging.warning(f"Could not remove existing namespace {import_namespace}, might contain nodes: {e}. Trying to delete contents.")
                 try:
                     ns_content = cmds.ls(f"{import_namespace}:*", long=True)
                     if ns_content:
                         cmds.delete(ns_content)
                     cmds.namespace(setNamespace=':')
                     cmds.namespace(removeNamespace=import_namespace)
                 except Exception as e_del:
                     logging.error(f"Failed cleanup of namespace {import_namespace}: {e_del}")

        if not cmds.pluginInfo("fbxmaya", loaded=True, query=True):
            try:
                cmds.loadPlugin("fbxmaya")
                logging.info("Loaded fbxmaya plugin.")
            except Exception as e:
                self.set_feedback("Error: Failed to load FBX plugin.", level="error")
                logging.error(f"Failed to load fbxmaya plugin: {e}")
                return

        imported_nodes = []
        try:
            imported_nodes = cmds.file(
                source_file,
                i=True,
                type="FBX",
                ignoreVersion=True,
                renameAll=True,
                namespace=import_namespace,
                options="fbx",
                preserveReferences=False,
                returnNewNodes=True,
                prompt=False
            )
            logging.info(f"Imported FBX from {source_file} into namespace '{import_namespace}'")
        except Exception as e:
            self.set_feedback("Error: Failed to import FBX file.", level="error")
            logging.error(f"FBX Import failed: {e}")
            if cmds.namespace(exists=import_namespace):
                try:
                     cmds.namespace(setNamespace=':')
                     cmds.namespace(removeNamespace=import_namespace)
                except: pass
            return

        imported_transforms = cmds.ls(imported_nodes, type='transform', long=True) or []
        logging.info(f"Found {len(imported_transforms)} imported transforms in namespace '{import_namespace}'.")

        if not imported_transforms:
             imported_transforms = cmds.ls(f"{import_namespace}:*", type='transform', long=True)
             if imported_transforms:
                  logging.warning("returnNewNodes did not list transforms, using ls fallback.")
             else:
                self.set_feedback("Error: No transform nodes found after FBX import.", level="error")
                if cmds.namespace(exists=import_namespace):
                    try:
                        cmds.namespace(setNamespace=':')
                        cmds.namespace(removeNamespace=import_namespace)
                    except: pass
                return

        transfer_count = 0
        error_count = 0
        processed_targets = set()

        for orig_item in source_objects:
             if orig_item in processed_targets: continue

             orig_leaf = orig_item.split('|')[-1].split(':')[-1]
             logging.info(f"Processing original: {orig_item} (Leaf: {orig_leaf})")
             matched_import = None
             for imp_item in imported_transforms:
                 imp_leaf = imp_item.split('|')[-1].split(':')[-1]
                 if imp_leaf == orig_leaf:
                     matched_import = imp_item
                     logging.info(f"Found potential name match: {matched_import}")
                     break

             if matched_import:
                 source_shapes = cmds.listRelatives(matched_import, shapes=True, type='mesh', fullPath=True, noIntermediate=True) or []
                 target_shapes = cmds.listRelatives(orig_item, shapes=True, type='mesh', fullPath=True, noIntermediate=True) or []

                 if not source_shapes or not target_shapes:
                     logging.warning(f"Could not find mesh shapes for match: Source({matched_import}):{source_shapes}, Target({orig_item}):{target_shapes}")
                     error_count += 1
                     continue

                 src = source_shapes[0]
                 trg = target_shapes[0]
                 logging.info(f"Transferring from Source Shape: {src} To Target Shape: {trg}")

                 try:
                     src_uv_layers = cmds.polyUVSet(src, query=True, allUVSets=True) or ["map1"]
                     trg_uv_layers = cmds.polyUVSet(trg, query=True, allUVSets=True) or []
                     logging.info(f"Source UV sets: {src_uv_layers}")
                     logging.info(f"Target UV sets before: {trg_uv_layers}")

                     uv_sets_to_transfer = []
                     if target_uv_layer == "All UV Sets":
                         uv_sets_to_transfer = src_uv_layers
                     elif target_uv_layer in src_uv_layers:
                         uv_sets_to_transfer = [target_uv_layer]
                     else:
                         logging.warning(f"Requested UV set '{target_uv_layer}' not found on imported source {src}. Skipping transfer for {orig_item}.")
                         error_count += 1
                         continue

                     for uv_set in uv_sets_to_transfer:
                          if uv_set not in trg_uv_layers:
                              try:
                                  cmds.polyUVSet(trg, create=True, uvSet=uv_set)
                                  logging.info(f"Created UV set '{uv_set}' on target {trg}")
                              except Exception as e_create:
                                  logging.error(f"Failed to create UV set '{uv_set}' on {trg}: {e_create}")
                                  error_count += 1
                                  continue

                          try:
                              cmds.polyUVSet(src, currentUVSet=True, uvSet=uv_set)
                              cmds.polyUVSet(trg, currentUVSet=True, uvSet=uv_set)
                              cmds.transferAttributes(
                                  src, trg,
                                  transferPositions=0,
                                  transferNormals=0,
                                  transferUVs=2,
                                  transferColors=0,
                                  sampleSpace=4,
                                  sourceUvSpace=uv_set,
                                  targetUvSpace=uv_set,
                                  searchMethod=3,
                                  flipUVs=0,
                                  colorBorders=1
                              )
                              cmds.delete(trg, constructionHistory=True)
                              logging.info(f"Successfully transferred UV set '{uv_set}' from {src} to {trg}")
                              transfer_count += 1
                          except Exception as e_xfer:
                              logging.error(f"Error transferring UV set '{uv_set}' for {orig_item}: {e_xfer}")
                              error_count += 1

                     processed_targets.add(orig_item)

                 except Exception as e_setup:
                      logging.error(f"Error during UV transfer setup for {orig_item}: {e_setup}")
                      error_count += 1

             else:
                 logging.warning(f"No matching imported object found for original: {orig_item}")
                 error_count += 1


        if imported_nodes:
             try:
                 valid_imported_nodes = [n for n in imported_nodes if cmds.objExists(n)]
                 if valid_imported_nodes:
                     cmds.delete(valid_imported_nodes)
                     logging.info(f"Deleted {len(valid_imported_nodes)} imported nodes.")
                 else:
                     logging.info("No valid imported nodes found to delete.")
             except Exception as e_del:
                 logging.warning(f"Issues during cleanup of imported nodes: {e_del}")

        if cmds.namespace(exists=import_namespace):
            try:
                cmds.namespace(setNamespace=':')
                cmds.namespace(removeNamespace=import_namespace)
                logging.info(f"Removed import namespace '{import_namespace}'")
            except Exception as e_ns:
                logging.error(f"Failed to remove import namespace '{import_namespace}': {e_ns}")

        cmds.select(source_objects, replace=True)
        self.refresh_uv_options()

        if error_count == 0 and transfer_count > 0:
             self.set_feedback(f"UVs successfully imported to {len(processed_targets)} object(s) (Set: {target_uv_layer})", level="info")
        elif transfer_count > 0:
             self.set_feedback(f"UV import completed with {error_count} warning(s)/error(s). Check script editor.", level="warning")
        else:
             self.set_feedback(f"UV import failed or no matches found. Check script editor.", level="error")


    def adjust_angle(self):
        self.edge_angle_threshold = self.angle_adjuster.value()
        logging.info(f"Soften tolerance angle set to {self.edge_angle_threshold}")

    def toggle_tolerance(self):
        self.use_angle_tolerance = self.tolerance_toggle.isChecked()
        logging.info(f"Soften tolerance checkbox {'enabled' if self.use_angle_tolerance else 'disabled'}")

    def process_uv_edges(self):
        self.feedback_label.setStyleSheet("")
        selected_items = cmds.ls(selection=True, long=True, type='transform')
        if not selected_items:
            self.set_feedback("Error: No objects selected for hardening UV edges.", level="error")
            return

        processed_count = 0
        cmds.undoInfo(openChunk=True)
        try:
            for item in selected_items:
                shapes = cmds.listRelatives(item, shapes=True, type='mesh', fullPath=True, noIntermediate=True)
                if not shapes:
                    logging.warning(f"Skipping {item}, no mesh shape found.")
                    continue

                mesh = shapes[0]
                logging.info(f"Processing UV edges for: {mesh}")

                cmds.polySoftEdge(mesh, angle=180, constructionHistory=False)

                cmds.select(mesh)
                try:
                    mel.eval("SelectUVBorderComponents;")
                except Exception as mel_err:
                     logging.error(f"MEL command 'SelectUVBorderComponents' failed: {mel_err}")
                     continue

                uv_border_edges = cmds.ls(selection=True, flatten=True)

                if uv_border_edges:
                    cmds.polySoftEdge(uv_border_edges, angle=0, constructionHistory=False)
                    logging.info(f"Hardened {len(uv_border_edges)} UV border edges on {mesh}")
                else:
                    logging.info(f"No UV border edges found on {mesh}")


                if self.use_angle_tolerance:
                     cmds.polySoftEdge(mesh, angle=self.edge_angle_threshold, constructionHistory=False)
                     logging.info(f"Applied angle tolerance softening ({self.edge_angle_threshold} deg) to {mesh}")


                cmds.delete(mesh, constructionHistory=True)
                processed_count += 1

        except Exception as e:
            self.set_feedback(f"Error during edge processing: {e}", level="error")
            logging.exception("Edge processing error details:")
            cmds.undoInfo(closeChunk=True, undoName="Process UV Edges")
            cmds.undo()
            return
        finally:
            cmds.undoInfo(closeChunk=True, undoName="Process UV Edges")
            cmds.select(selected_items)

        if processed_count > 0:
             feedback = "UV border edges hardened"
             if self.use_angle_tolerance:
                 feedback += f", others softened below {self.edge_angle_threshold} deg"
             else:
                 feedback += ", all others softened"
             self.set_feedback(f"{feedback} on {processed_count} object(s).", level="info")
        else:
             self.set_feedback("No suitable mesh objects processed.", level="warning")


def fetch_maya_root():
    ptr = omui.MQtUtil.mainWindow()
    if ptr is None:
         logging.error("Could not get Maya main window pointer.")
         return None
    try:
        return wrapInstance(int(ptr), QtWidgets.QWidget)
    except TypeError:
        logging.error("Could not wrap Maya main window instance.")
        return None


def launch_tool():
    workspace_control_name = "rizomUVBridgeWorkspaceControl"
    panel_object_name = "rizomUVBridgePanelInstance"
    default_control_name = panel_object_name + "WorkspaceControl"

    potential_control_names = [default_control_name, workspace_control_name]
    for control_name in potential_control_names:
        if cmds.workspaceControl(control_name, exists=True):
            try:
                logging.warning(f"Launch: Found lingering workspace control: {control_name}. Attempting delete.")
                cmds.deleteUI(control_name, control=True)
                logging.info(f"Launch: Deleted lingering workspace control: {control_name}")
            except Exception as e:
                logging.error(f"Launch: Could not delete lingering workspace control '{control_name}': {e}")
                if control_name == workspace_control_name:
                     logging.warning(f"Attempting to restore control '{control_name}' as deletion failed.")
                     try:
                        cmds.workspaceControl(control_name, edit=True, restore=True)
                        logging.info(f"Restored existing control '{control_name}'. Panel will not be re-created.")
                        return None
                     except Exception as e_restore:
                         logging.error(f"Failed to restore existing control '{control_name}': {e_restore}. Cannot launch.")
                         return None

    if cmds.control(panel_object_name, exists=True):
        try:
            logging.warning(f"Launch: Found existing panel UI: {panel_object_name}. Attempting deletion...")
            cmds.deleteUI(panel_object_name, control=True)
            logging.info(f"Launch: Successfully deleted panel UI: {panel_object_name}")
        except Exception as e:
            logging.error(f"Launch: Failed to delete panel UI '{panel_object_name}': {e}")


    root = fetch_maya_root()
    if root is None:
        logging.error("Cannot launch tool without Maya main window.")
        return None

    try:
        panel = UVBridgePanel(root)
        ui_script = f"import {__name__}; {__name__}.launch_tool()"

        panel.show(dockable=True,
                   area="right",
                   floating=False,
                   label="RizomUV Bridge",
                   workspaceControlName=workspace_control_name,
                   uiScript=ui_script)

        logging.info("RizomUV Bridge panel launched.")
        return panel
    except Exception as e:
        if "is not unique" in str(e):
             logging.error(f"Failed to launch panel. Workspace control name '{workspace_control_name}' or related UI still exists and could not be cleaned up.")
        logging.exception(f"Error launching RizomUV Bridge panel: {e}")
        return None


if __name__ == "__main__":
    launch_tool()