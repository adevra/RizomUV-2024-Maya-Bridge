import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMayaUI as omui
import maya.utils
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import subprocess
import os
import platform
import sys
import locale
import logging
import json
import shutil
from pathlib import Path

rizom_bridge_panel_instance = None
logger = logging.getLogger("RizomBridge")

PYSIDE_VERSION = 2
try:
    if sys.version_info.major >= 3 and sys.version_info.minor >= 11:
        try:
            from PySide6 import QtWidgets, QtCore, QtGui
            from shiboken6 import wrapInstance

            PYSIDE_VERSION = 6
            print("RizomBridge: Using PySide6")
        except ImportError:
            print("RizomBridge: PySide6 not found, falling back to PySide2.")
            from PySide2 import QtWidgets, QtCore, QtGui
            from shiboken2 import wrapInstance

            print("RizomBridge: Using PySide2")
    else:
        from PySide2 import QtWidgets, QtCore, QtGui
        from shiboken2 import wrapInstance

        print("RizomBridge: Using PySide2 (Python < 3.11)")
except ImportError as e:
    print(f"RizomBridge: FATAL - PySide import failed: {e}")
    raise ImportError("RizomBridge requires PySide6 or PySide2.") from e

MODULE_NAME = "maya_rizomuv_bridge"
SCRIPT_FILE_NAME = f"{MODULE_NAME}.py"
INSTALL_SUBDIR = "RZMUV"
ICON_FILE_NAME = "rzmuv.png"
SHELF_BUTTON_LABEL = "RizomUV"
SHELF_BUTTON_TOOLTIP = "Launch RizomUV Maya Bridge"
WORKSPACE_CONTROL_NAME = "rizomUVBridgeWorkspaceControl"
CONFIG_DIR_NAME = "RizomUVBridge"
CONFIG_FILE_NAME = "settings.json"
LUA_SCRIPT_FILE_NAME = "rizomuv_control_script.lua"
FBX_FILE_NAME = "RizomUVMayaBridge.fbx"
BRIDGE_ASCII_ART = r"""                                                                            
 +++++-+-------++---------++---------.  .---+-+++-+++--+-+++---+---+------++ 
 +---+-----+++----+++-+++---++---+-+--##-     .----+---------+++-++------+++ 
 +--+---++-----+++--+---++++------+-..########   -+--+----+-------++++----+- 
 -+---++----++++--++-.     ----------.######## ## .-+++---+++++---++-+--+++- 
 +---++--++++---+-----####+   ------. ######## ###  --++++--+-+-+-------+++- 
 ----+---++--------+- ######## +++----######## ####. --+-+--+-+-+------+---- 
 -++---+++---+--++--- ######## ---+--   .##### #####- -----+--+-----+-+--+-- 
 ---+-++---+---+--++-. ####### -----+---      ########.+++--+++------+-++--- 
 -++++---++----+++---- #######+.++-++-++----+ #######-.--++----+-++---+++-++ 
 +++----+----+--++++++ ######## ----++-++---- ####### --------------++++---- 
 +----++--+-----+++-+- +####### --++--+--+--..####### --+-+--+------+----+++ 
 ----+-++-------------- ####### ----+---+--- ######## --+++--++------------+ 
 ----+--------+++---+-- #######              #######+ ++--++--++------------ 
 --+--------+----------. ################### ####### -------+-+------------- 
 ---------+---+---+-----.  ##### ########### ####.  --------+-+---+--------- 
 -+----++-------+-------+-.  -## ###########-##   --+-----+-+++++---+------- 
 -+---+------+++-------+---+-  .+##########-+  .--------+-------++++---+---- 
 ----------+------------------.             .------++-.--++----..-------.--- 
 -+-..     .- .. ..   .   ..  ###  .-.-. .+--. -.--+-.#-.++.-# +# .-+- +#.-- 
 -+-.######-. ##.+####+### .##..###.  ### .- .##.-++-+## ++ ## ### -- ###.-- 
 --- #-    #  ##      ##   ## ..   ## ####  ###. --+.-## -+ ##  ##-  -## --- 
 --- #######  ## -. ### ..##- -++. ## ## ####-.# --+--## -- ## - ##- ## .+-- 
 --.+#   ##   ##  -##      ##     ### ##  ##. ## ---- ##   -## -. ## # .-+-- 
 --.##+.  ##. ##.-########  ######.   ## .  . ##.----. #####  .--. ##+ ---+- 
                                                                                                                   
> RizomUV - Maya Bridge v2.3.0
     >    https://www.rizomuv.com/virtual-spaces/#bridges   
     >    https://github.com/adevra/RizomUV-2024-Maya-Bridge
                                                                                              
"""
                                                                                                   
PATH_DEFAULTS = {
    "Windows": "C:\\Program Files\\Rizom Lab\\RizomUV 2024.0\\rizomuv.exe",
    "Darwin": "/Applications/RizomUV 2024.1.app",
    "Linux": "/usr/local/bin/rizomuv",
}

def setup_logging(level=logging.ERROR):
    if not logger.handlers:
        logger.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
        )
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        logger.propagate = False
        logger.info(
            f"RizomBridge logger initialized with level {logging.getLevelName(level)}."
        )
    else:
        current_level = logger.level
        if current_level != level:
            logger.setLevel(level)
            logger.info(
                f"RizomBridge logger level set to {logging.getLevelName(level)}."
            )


setup_logging(level=logging.ERROR)


class ConfigManager:
    def __init__(self):
        self.base_dir = self._get_base_directory()
        self.config_file_path = self.base_dir / CONFIG_FILE_NAME
        self.lua_control_file_path = self.base_dir / LUA_SCRIPT_FILE_NAME
        self.fbx_export_file_path = self.base_dir / FBX_FILE_NAME
        self._set_default_attributes()
        self.ensure_storage_exists()
        self.load_or_create_config()

    def _set_default_attributes(self):
        self.rizom_location = self._get_default_rizom_path()
        self.include_uvs = True
        self.pack_quality = 2
        self.pack_iterations = 256
        self.log_level_str = "ERROR"
        logger.debug("Set initial default configuration attributes.")

    def _get_base_directory(self):
        try:
            scripts_dir = Path(cmds.internalVar(userScriptDir=True))
            base_dir = scripts_dir / INSTALL_SUBDIR
            logger.debug(f"Using base directory: {base_dir}")
            return base_dir
        except Exception as e:
            logger.error(
                f"Could not get Maya scripts dir via internalVar: {e}. Falling back."
            )
            fallback_base = (
                Path(os.path.expanduser("~")) / ".maya_rizom_bridge" / INSTALL_SUBDIR
            )
            logger.warning(f"Using fallback directory: {fallback_base}")
            return fallback_base

    def ensure_storage_exists(self):
        if not self.base_dir.exists():
            try:
                self.base_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created settings directory: {self.base_dir}")
            except OSError as e:
                logger.error(
                    f"Failed to create settings directory {self.base_dir}: {e}"
                )

    def load_or_create_config(self):
        if not self.config_file_path.is_file():
            logger.info(
                f"'{CONFIG_FILE_NAME}' not found. Creating default configuration."
            )
            self.save_config()
        else:
            try:
                with open(self.config_file_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                self.rizom_location = config_data.get("rizomPath", self.rizom_location)
                self.include_uvs = config_data.get("loadUVs", self.include_uvs)
                self.pack_quality = config_data.get("quality", self.pack_quality)
                self.pack_iterations = config_data.get(
                    "mutations", self.pack_iterations
                )
                loaded_log_level_str = config_data.get("logLevel", "ERROR").upper()
                if loaded_log_level_str in ["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"]:
                    self.log_level_str = loaded_log_level_str
                else:
                    logger.warning(f"Invalid log level '{loaded_log_level_str}' found in config. Defaulting to ERROR.")
                    self.log_level_str = "ERROR"
                logger.info(f"Loaded configuration from {self.config_file_path}")
                if not Path(self.rizom_location).exists() and not (
                    platform.system() == "Darwin"
                    and self.rizom_location.endswith(".app")
                ):
                    logger.warning(
                        f"Rizom path loaded from config does not exist: {self.rizom_location}"
                    )
            except json.JSONDecodeError as e_json:
                logger.error(
                    f"Error decoding {self.config_file_path}: {e_json}. Attempting backup and reset."
                )
                self._backup_and_reset_config("JSONDecodeError")
            except Exception as e:
                logger.error(
                    f"Unexpected error loading configuration: {e}. Attempting backup and reset.",
                    exc_info=True,
                )
                self._backup_and_reset_config(type(e).__name__)

    def _backup_and_reset_config(self, error_type="UnknownError"):
        if self.config_file_path.is_file():
            try:
                timestamp = QtCore.QDateTime.currentDateTime().toString(
                    "yyyyMMdd_HHmmss"
                )
                backup_path = self.config_file_path.with_suffix(
                    f".corrupt_{error_type}_{timestamp}.bak"
                )
            except NameError:
                backup_path = self.config_file_path.with_suffix(
                    f".corrupt_{error_type}.bak"
                )
            try:
                shutil.copy2(self.config_file_path, backup_path)
                logger.info(f"Backed up corrupted config to: {backup_path}")
            except Exception as e_bak:
                logger.error(f"Failed to backup corrupted config: {e_bak}")
        logger.warning("Resetting configuration to defaults due to loading error.")
        self._set_default_attributes()
        self.save_config()

    def _get_default_rizom_path(self):
        system = platform.system()
        default_path = PATH_DEFAULTS.get(system, "")
        if not default_path:
            logger.warning(f"No default Rizom path defined for system: {system}")
        return default_path

    def save_config(self):
        config_data = {
            "rizomPath": str(self.rizom_location),
            "loadUVs": self.include_uvs,
            "quality": self.pack_quality,
            "mutations": self.pack_iterations,
            "logLevel": self.log_level_str,
        }
        try:
            self.ensure_storage_exists()
            if not self.base_dir.is_dir() or not os.access(str(self.base_dir), os.W_OK):
                logger.error(
                    f"Cannot write to directory: {self.base_dir}. Config not saved."
                )
                return False
            with open(self.config_file_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            logger.info(f"Saved configuration to {self.config_file_path}")
            return True
        except IOError as e:
            logger.error(
                f"Failed to save configuration to {self.config_file_path}: {e}",
                exc_info=True,
            )
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving configuration: {e}", exc_info=True)
            return False

    def get_lua_script_path_str(self):
        return str(self.lua_control_file_path)

    def get_fbx_export_path_str(self):
        return str(self.fbx_export_file_path)


try:
    config = ConfigManager()
except Exception as e_cfg:
    logger.critical(f"Failed to initialize ConfigManager: {e_cfg}", exc_info=True)
    raise RuntimeError("RizomBridge ConfigManager failed to initialize.") from e_cfg


class UVBridgePanel(MayaQWidgetDockableMixin, QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(UVBridgePanel, self).__init__(parent)
        global config
        if not config:
            raise RuntimeError("UVBridgePanel requires a valid ConfigManager instance.")
        self.config = config
        self.setWindowTitle("RizomUV Bridge")
        self.setMinimumWidth(250)
        self.edge_angle_threshold = 45.1
        self.use_angle_tolerance = True
        self.setObjectName("rizomUVBridgePanelInstance")
        initial_log_level = getattr(logging, self.config.log_level_str, logging.ERROR)
        logger.info(f"Setting initial log level from config: {self.config.log_level_str} ({logging.getLevelName(initial_log_level)})")
        setup_logging(level=initial_log_level)
        self.build_interface()
        self.setup_handlers()
        self.refresh_uv_options()
        self.tolerance_toggle.setChecked(self.use_angle_tolerance)
        self.angle_adjuster.setValue(self.edge_angle_threshold)
        self._update_debug_button_text()
        logger.info("RizomUV Bridge Panel Initialized.")

    def build_interface(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)
        settings_group = QtWidgets.QGroupBox("Settings")
        settings_layout = QtWidgets.QVBoxLayout()
        path_layout = QtWidgets.QHBoxLayout()
        path_layout.addWidget(QtWidgets.QLabel("RizomUV Path:"))
        self.location_input = QtWidgets.QLineEdit(str(self.config.rizom_location))
        self.location_input.setToolTip("Path to the RizomUV executable or .app bundle")
        path_layout.addWidget(self.location_input)
        self.browse_btn = QtWidgets.QPushButton("...")
        self.browse_btn.setFixedWidth(30)
        self.browse_btn.setToolTip("Browse for RizomUV")
        path_layout.addWidget(self.browse_btn)
        settings_layout.addLayout(path_layout)
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)
        ops_group = QtWidgets.QGroupBox("Manual UV Transfer")
        ops_layout = QtWidgets.QVBoxLayout()
        self.uv_toggle = QtWidgets.QCheckBox("Send With Existing UVs")
        self.uv_toggle.setChecked(self.config.include_uvs)
        self.uv_toggle.setToolTip(
            "Include existing UV data when sending geometry to RizomUV.\nIf unchecked, RizomUV will likely generate default UVs."
        )
        ops_layout.addWidget(self.uv_toggle)
        self.transfer_btn = QtWidgets.QPushButton("Send Selection to RizomUV")
        self.transfer_btn.setToolTip(
            "Export selected geometry and launch/update RizomUV.\nDoes NOT run any automatic actions in RizomUV."
        )
        ops_layout.addWidget(self.transfer_btn)
        separator_manual = QtWidgets.QFrame()
        separator_manual.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator_manual.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        ops_layout.addWidget(separator_manual)
        ops_layout.addWidget(QtWidgets.QLabel("Target/Source UV Set:"))
        self.uv_selector = QtWidgets.QComboBox()
        self.uv_selector.setToolTip(
            "Select the UV set in Maya to use as SOURCE when sending (if 'Send With Existing UVs' is checked)\nand as TARGET when retrieving UVs or running automated actions."
        )
        ops_layout.addWidget(self.uv_selector)
        self.retrieve_btn = QtWidgets.QPushButton("Get UVs from RizomUV")
        self.retrieve_btn.setToolTip(
            "Import UVs from the bridge FBX file (saved by RizomUV) back to the\nselected objects in Maya, into the Target/Source UV Set specified above."
        )
        ops_layout.addWidget(self.retrieve_btn)
        ops_group.setLayout(ops_layout)
        main_layout.addWidget(ops_group)
        auto_group = QtWidgets.QGroupBox("Rizom Actions")
        auto_layout = QtWidgets.QVBoxLayout()
        self.custom_lua_label = QtWidgets.QLabel("Custom Lua Script (Optional):")
        self.custom_lua_input = QtWidgets.QTextEdit()
        self.custom_lua_input.setPlaceholderText(
            "# Enter custom Lua commands here.\n# They run AFTER loading and AFTER setting the UV set,\n# but BEFORE the Auto Pack step (if Auto Pack is used later)."
        )
        self.custom_lua_input.setAcceptRichText(False)
        self.custom_lua_input.setMinimumHeight(60)
        auto_layout.addWidget(self.custom_lua_label)
        auto_layout.addWidget(self.custom_lua_input)
        self.run_custom_lua_btn = QtWidgets.QPushButton("Run Custom Lua Script")
        self.run_custom_lua_btn.setToolTip(
            "1. Send selection to RizomUV (optionally with existing UVs).\n2. Set Target UV Set in RizomUV (if not 'All UV Sets').\n3. Run the custom Lua script entered above.\n4. Save the result to the bridge FBX.\n\nUse 'Get UVs' button afterwards to import the result into Maya."
        )
        auto_layout.addWidget(self.run_custom_lua_btn)
        separator_auto = QtWidgets.QFrame()
        separator_auto.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator_auto.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        auto_layout.addWidget(separator_auto)
        packer_layout = QtWidgets.QGridLayout()
        packer_layout.addWidget(QtWidgets.QLabel("Packer Quality:"), 0, 0)
        self.quality_selector = QtWidgets.QComboBox()
        self.quality_selector.addItems(
            ["Low (128)", "Normal (256)", "High (512)", "Higher (1024)", "Ultra (2048)"]
        )
        self.quality_selector.setCurrentIndex(self.config.pack_quality)
        self.quality_selector.setToolTip(
            "Select packing quality/resolution for the Auto Pack.\nHigher values take longer but give better packing density."
        )
        packer_layout.addWidget(self.quality_selector, 0, 1)
        packer_layout.addWidget(QtWidgets.QLabel("Packer Iterations:"), 1, 0)
        self.iterations_spinner = QtWidgets.QSpinBox()
        self.iterations_spinner.setRange(1, 8192)
        self.iterations_spinner.setValue(self.config.pack_iterations)
        self.iterations_spinner.setToolTip(
            "Number of packing iterations (mutations) for the Auto Pack.\nMore iterations can improve results but increase time."
        )
        packer_layout.addWidget(self.iterations_spinner, 1, 1)
        auto_layout.addLayout(packer_layout)
        self.auto_pack_btn = QtWidgets.QPushButton("Auto Pack UV Set")
        self.auto_pack_btn.setToolTip(
            "1. Send selection to RizomUV (optionally with existing UVs).\n2. Set Target UV Set in RizomUV (Requires a specific set, NOT 'All UV Sets').\n3. Automatically pack the selected UV set using the Quality/Iterations settings.\n4. Save the result to the bridge FBX.\n\nUse 'Get UVs' button afterwards to import the result into Maya."
        )
        auto_layout.addWidget(self.auto_pack_btn)
        auto_group.setLayout(auto_layout)
        main_layout.addWidget(auto_group)
        post_group = QtWidgets.QGroupBox("Post Process (Normals)")
        post_layout = QtWidgets.QVBoxLayout()
        self.edge_hardener_btn = QtWidgets.QPushButton("Harden UV Shell Edges")
        self.edge_hardener_btn.setToolTip(
            "Process selected meshes in Maya:\n1. Soften all edges.\n2. Harden UV shell border edges.\n3. (Optional) Soften remaining edges based on angle tolerance."
        )
        post_layout.addWidget(self.edge_hardener_btn)
        self.tolerance_toggle = QtWidgets.QCheckBox(
            "Use Angle Tolerance After Hardening"
        )
        self.tolerance_toggle.setToolTip(
            "If checked, after hardening UV borders, apply softenig\nto the rest of the mesh using the angle below."
        )
        post_layout.addWidget(self.tolerance_toggle)
        angle_layout = QtWidgets.QHBoxLayout()
        angle_layout.addWidget(QtWidgets.QLabel("Tolerance Angle:"))
        self.angle_adjuster = QtWidgets.QDoubleSpinBox()
        self.angle_adjuster.setRange(0.1, 179.9)
        self.angle_adjuster.setSingleStep(0.1)
        self.angle_adjuster.setDecimals(1)
        self.angle_adjuster.setToolTip(
            "Angle threshold for softening non-UV-border edges."
        )
        angle_layout.addWidget(self.angle_adjuster)
        post_layout.addLayout(angle_layout)
        post_group.setLayout(post_layout)
        main_layout.addWidget(post_group)
        self.feedback_label = QtWidgets.QLabel("Ready")
        self.feedback_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.feedback_label.setWordWrap(True)
        main_layout.addWidget(self.feedback_label)
        main_layout.addStretch()
        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        bottom_layout.addSpacerItem(spacer)
        self.debug_toggle_btn = QtWidgets.QPushButton()
        self.debug_toggle_btn.setToolTip(
            "Toggle logging level between DEBUG (verbose) and Production (minimal)."
        )
        self.debug_toggle_btn.setCheckable(True)
        self.debug_toggle_btn.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.debug_toggle_btn.adjustSize()
        bottom_layout.addWidget(self.debug_toggle_btn)
        main_layout.addLayout(bottom_layout)

    def setup_handlers(self):
        self.transfer_btn.clicked.connect(self.dispatch_manual_send)
        self.retrieve_btn.clicked.connect(self.fetch_from_rizom)
        self.uv_toggle.stateChanged.connect(self.persist_config)
        self.browse_btn.clicked.connect(self.locate_rizom)
        self.location_input.editingFinished.connect(self.persist_config)
        self.run_custom_lua_btn.clicked.connect(self.dispatch_custom_lua)
        self.auto_pack_btn.clicked.connect(self.dispatch_auto_pack)
        self.quality_selector.currentIndexChanged.connect(self.persist_config)
        self.iterations_spinner.valueChanged.connect(self.persist_config)
        self.edge_hardener_btn.clicked.connect(self.process_uv_edges)
        self.tolerance_toggle.toggled.connect(self.toggle_tolerance)
        self.angle_adjuster.valueChanged.connect(self.adjust_angle)
        self.debug_toggle_btn.toggled.connect(self.toggle_debug_logging)
        try:
            ui_name = self.objectName()
            logger.debug(f"Cleaning up potential old scriptJobs parented to: {ui_name}")
            all_jobs = cmds.scriptJob(listJobs=True)
            for job_num_str in all_jobs:
                try:
                    job_num = int(job_num_str)
                    if (
                        cmds.scriptJob(exists=job_num)
                        and cmds.scriptJob(query=True, parent=job_num) == ui_name
                    ):
                        event_info = cmds.scriptJob(query=True, event=job_num)
                        if (
                            isinstance(event_info, (list, tuple))
                            and event_info[0] == "SelectionChanged"
                        ):
                            logger.debug(
                                f"Killing pre-existing SelectionChanged scriptJob: {job_num} parented to {ui_name}"
                            )
                            cmds.scriptJob(kill=job_num, force=True)
                except (ValueError, TypeError):
                    pass
                except Exception as e_kill_check:
                    logger.warning(
                        f"Error checking/killing script job {job_num_str}: {e_kill_check}"
                    )
            new_job_num = cmds.scriptJob(
                event=["SelectionChanged", self.refresh_uv_options],
                parent=ui_name,
                protected=True,
            )
            logger.debug(
                f"Created SelectionChanged scriptJob: {new_job_num} parented to {ui_name}"
            )
        except Exception as e_sj:
            logger.error(
                f"Failed to create SelectionChanged scriptJob: {e_sj}", exc_info=True
            )

    def _update_debug_button_text(self):
        is_info_level = self.config.log_level_str == "INFO"
        self.debug_toggle_btn.setChecked(is_info_level)
        self.debug_toggle_btn.setText("🐞 DEBUG" if is_info_level else "⚡️")
        self.debug_toggle_btn.adjustSize()

    def toggle_debug_logging(self, checked):
        new_level = logging.INFO if checked else logging.ERROR
        level_name = logging.getLevelName(new_level)
        if checked:
            logger.info(f"Switching logging level to {level_name}")
        else:
            logger.info(f"Switching logging level to {level_name}")
        setup_logging(level=new_level)
        self.config.log_level_str = level_name
        if not self.config.save_config():
            self.set_feedback("Error saving logging preference.", level="error")
            logging.getLogger("RizomBridge").error("Failed to save logging level preference to config.")
        else:
            logging.getLogger("RizomBridge").debug(f"Saved logging level preference: {level_name}")
        
        self._update_debug_button_text()

    def dispatch_manual_send(self):
        self._dispatch_to_rizom(run_custom_script=False, pack_after=False)

    def dispatch_custom_lua(self):
        self._dispatch_to_rizom(run_custom_script=True, pack_after=False)

    def dispatch_auto_pack(self):
        chosen_uv_set = self.uv_selector.currentText()
        if chosen_uv_set == "All UV Sets":
            self.set_feedback(
                "Error: Auto Pack requires a specific Target UV Set.", level="error"
            )
            logger.error("Auto Pack requires a specific UV set, not 'All UV Sets'.")
            cmds.warning(
                "Auto Pack requires a specific Target UV Set to be selected in the dropdown."
            )
            return
        self._dispatch_to_rizom(run_custom_script=False, pack_after=True)

    def _dispatch_to_rizom(self, run_custom_script=False, pack_after=False):
        self.set_feedback("Preparing data for RizomUV...", level="info")
        selected_items = cmds.ls(selection=True, long=True, type="transform")
        mesh_transforms = []
        if selected_items:
            for item in selected_items:
                shapes = cmds.listRelatives(
                    item, shapes=True, type="mesh", noIntermediate=True, fullPath=True
                )
                if shapes:
                    mesh_transforms.append(item)
        if not mesh_transforms:
            self.set_feedback("Error: No meshes selected.", level="error")
            logger.error("No polygon mesh objects found in selection.")
            return
        selected_items = mesh_transforms
        logger.info(f"Processing selection: {selected_items}")
        rizom_path_str = str(self.config.rizom_location)
        fbx_export_path_str = self.config.get_fbx_export_path_str()
        lua_script_path_str = self.config.get_lua_script_path_str()
        system = platform.system()
        rizom_path = Path(rizom_path_str)
        path_valid = False
        error_msg = ""
        if system == "Darwin":
            if rizom_path_str.endswith(".app"):
                if rizom_path.is_dir():
                    path_valid = True
                    potential_exe = rizom_path / "Contents" / "MacOS" / "RizomUV"
                    if not potential_exe.exists():
                        logger.warning(
                            f"Cannot find expected executable inside {rizom_path}."
                        )
                    elif not os.access(str(potential_exe), os.X_OK):
                        logger.warning(
                            f"Executable inside {rizom_path} is not executable."
                        )
                else:
                    error_msg = f".app path does not exist or is not a directory: {rizom_path_str}"
            elif rizom_path.is_file() and os.access(rizom_path_str, os.X_OK):
                path_valid = True
            else:
                error_msg = f"Mac path is not a valid .app bundle or executable file: {rizom_path_str}"
        elif system == "Windows":
            if rizom_path.is_file() and rizom_path.suffix.lower() == ".exe":
                path_valid = True
            else:
                error_msg = f"Windows path is not a valid .exe file: {rizom_path_str}"
        elif rizom_path.is_file() and os.access(rizom_path_str, os.X_OK):
            path_valid = True
        else:
            error_msg = f"Linux path is not a valid executable file: {rizom_path_str}"
        if not path_valid:
            self.set_feedback(
                f"Error: RizomUV path invalid. {error_msg}", level="error"
            )
            logger.error(f"RizomUV path invalid: {error_msg}")
            return
        use_existing_uvs = self.uv_toggle.isChecked()
        chosen_uv_set = self.uv_selector.currentText()
        is_specific_set_selected = chosen_uv_set != "All UV Sets"
        if pack_after and not is_specific_set_selected:
            self.set_feedback(
                "Error: Auto Pack requires a specific Target UV Set.", level="error"
            )
            logger.error(
                "Internal Error: _dispatch_to_rizom called for packing with 'All UV Sets'."
            )
            return
        if not cmds.pluginInfo("fbxmaya", loaded=True, query=True):
            try:
                cmds.loadPlugin("fbxmaya", quiet=True)
                logger.info("Loaded fbxmaya plugin.")
            except Exception as e:
                self.set_feedback("Error: Failed to load FBX plugin.", level="error")
                logger.error(f"Failed to load fbxmaya plugin: {e}", exc_info=True)
                return
        active_uv_set_for_export = "map1"
        if use_existing_uvs:
            if is_specific_set_selected:
                active_uv_set_for_export = chosen_uv_set
                logger.info(
                    f"Targeting UV set '{active_uv_set_for_export}' for export."
                )
            else:
                logger.info(
                    "Using currently active UV set(s) in Maya for export ('All UV Sets' selected)."
                )
                active_uv_set_for_export = "map1"
        else:
            logger.info(
                "Not sending existing UVs. Setting 'map1' as current for export structure."
            )
            active_uv_set_for_export = "map1"
        original_uv_sets = {}
        for item in selected_items:
            shapes = cmds.listRelatives(
                item, shapes=True, fullPath=True, noIntermediate=True, type="mesh"
            )
            if not shapes:
                continue
            shape_node = shapes[0]
            try:
                all_sets = cmds.polyUVSet(shape_node, query=True, allUVSets=True) or [
                    "map1"
                ]
                current_set = cmds.polyUVSet(shape_node, query=True, currentUVSet=True)[
                    0
                ]
                original_uv_sets[shape_node] = current_set
                set_to_activate = active_uv_set_for_export
                if active_uv_set_for_export not in all_sets:
                    if "map1" in all_sets:
                        set_to_activate = "map1"
                        logger.warning(
                            f"Chosen set '{active_uv_set_for_export}' not on {shape_node}. Falling back to 'map1' for export activation."
                        )
                    else:
                        logger.error(
                            f"Neither chosen set '{active_uv_set_for_export}' nor 'map1' found on {shape_node}. Cannot reliably activate set for export."
                        )
                        continue
                if current_set != set_to_activate:
                    cmds.polyUVSet(shape_node, currentUVSet=True, uvSet=set_to_activate)
                    logger.debug(
                        f"Set current UV set to '{set_to_activate}' on {shape_node} for export."
                    )
                else:
                    logger.debug(
                        f"UV set '{set_to_activate}' already active on {shape_node}"
                    )
            except Exception as e_set:
                logger.warning(f"Could not query/set UV set on {shape_node}: {e_set}")
        self.set_feedback("Exporting selection to FBX...", level="info")
        try:
            Path(fbx_export_path_str).parent.mkdir(parents=True, exist_ok=True)
        except OSError as e_mkdir:
            self.set_feedback(
                f"Error creating export directory: {e_mkdir}", level="error"
            )
            logger.error(
                f"Failed to create directory for FBX export: {Path(fbx_export_path_str).parent} - {e_mkdir}"
            )
            return
        export_successful = False
        try:
            mel.eval("FBXExportSmoothingGroups -v true;")
            mel.eval("FBXExportTriangulate -v false;")
            mel.eval("FBXExportSmoothMesh -v false;")
            mel.eval("FBXExportConstraints -v false;")
            mel.eval("FBXExportBakeComplexAnimation -v false;")
            mel.eval("FBXExportUpAxis y;")
            cmds.select(selected_items, replace=True)
            cmds.file(
                fbx_export_path_str,
                force=True,
                options="v=0;",
                type="FBX export",
                preserveReferences=False,
                exportSelected=True,
            )
            logger.info(f"Exported selection to: {fbx_export_path_str}")
            export_successful = True
        except Exception as e_export:
            self.set_feedback(f"Error during FBX export: {e_export}", level="error")
            logger.error("FBX Export failed.", exc_info=True)
        finally:
            logger.debug("Attempting to restore original UV sets...")
            for shape_node, original_set in original_uv_sets.items():
                if cmds.objExists(shape_node):
                    try:
                        current_set_after = cmds.polyUVSet(
                            shape_node, query=True, currentUVSet=True
                        )[0]
                        all_sets_now = (
                            cmds.polyUVSet(shape_node, query=True, allUVSets=True) or []
                        )
                        if (
                            original_set in all_sets_now
                            and current_set_after != original_set
                        ):
                            cmds.polyUVSet(
                                shape_node, currentUVSet=True, uvSet=original_set
                            )
                            logger.debug(
                                f"Restored original UV set '{original_set}' on {shape_node}"
                            )
                    except Exception as e_restore:
                        logger.warning(
                            f"Could not restore original UV set '{original_set}' on {shape_node}: {e_restore}"
                        )
            cmds.select(selected_items, replace=True)
        if not export_successful:
            return
        quality_levels = {0: 128, 1: 256, 2: 512, 3: 1024, 4: 2048}
        quality_index = self.config.pack_quality
        pack_res = quality_levels.get(quality_index, 512)
        pack_iter = self.config.pack_iterations
        lua_fbx_path = str(self.config.fbx_export_file_path).replace("\\", "/")
        lua_script_parts = ["-- RizomUV Lua Script generated by Maya Bridge --"]
        load_flags = "XYZ=true"
        if use_existing_uvs:
            load_flags = "XYZUVW=true, UVWProps=true"
        load_cmd_str = f'ZomLoad({{File={{Path="{lua_fbx_path}", ImportGroups=true, {load_flags}}}, NormalizeUVW=false}})'
        lua_script_parts.append(load_cmd_str)
        rizom_target_uv_set_name_for_log = "current (default)"
        if is_specific_set_selected:
            rizom_target_uv_set_name = chosen_uv_set
            lua_script_parts.append("-- Setting target UV set for operation")
            lua_safe_set_name = json.dumps(rizom_target_uv_set_name)[1:-1]
            lua_script_parts.append(
                f'ZomUvset({{Mode="SetCurrent", Name="{lua_safe_set_name}"}})'
            )
            logger.info(
                f"Setting RizomUV current UV set to: {rizom_target_uv_set_name}"
            )
            rizom_target_uv_set_name_for_log = rizom_target_uv_set_name
        else:
            lua_script_parts.append(
                f"-- Operation will use RizomUV's default/current UV set ('{chosen_uv_set}' selected in Maya)"
            )
            logger.warning(
                f"Running action on RizomUV's default/current set because '{chosen_uv_set}' was selected in Maya."
            )
        if run_custom_script:
            lua_script_parts.append("\n-- Running Custom Lua Script --")
            custom_script = self.custom_lua_input.toPlainText().strip()
            if custom_script:
                lua_script_parts.append(custom_script)
                logger.info("Adding custom Lua script content.")
            else:
                logger.info("Custom Lua script field is empty, skipping.")
                lua_script_parts.append("-- Custom script was empty --")
        if pack_after:
            lua_script_parts.append(
                f"\n-- Running Auto Pack Step on UV Set: {rizom_target_uv_set_name_for_log} --"
            )
            lua_script_parts.append(
                'ZomIslandGroups({Mode="DistributeInTilesByBBox", WorkingSet="Visible", MergingPolicy=8322})'
            )
            lua_script_parts.append(
                'ZomIslandGroups({Mode="DistributeInTilesEvenly", WorkingSet="Visible", MergingPolicy=8322, UseTileLocks=true, UseIslandLocks=true})'
            )
            lua_script_parts.append(
                f'ZomPack({{ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", WorkingSet="Visible", Scaling={{Mode=2}}, Rotate={{Enable=true, Mode=1, Step=90.0}}, Translate=true, LayoutScalingMode=2, MaxMutations={pack_iter}, Resolution={pack_res}}})'
            )
            logger.info(
                f"Adding packing commands (Res={pack_res}, Iter={pack_iter}) for UV set '{rizom_target_uv_set_name_for_log}'"
            )
        lua_script_parts.append("\n-- Saving Result to Bridge FBX --")
        lua_script_parts.append(
            f'ZomSave({{File={{Path="{lua_fbx_path}", UVWProps=true}}, __UpdateUIObjFileName=true}})'
        )
        lua_script = "\n".join(lua_script_parts)
        try:
            Path(lua_script_path_str).parent.mkdir(parents=True, exist_ok=True)
            with open(lua_script_path_str, "w", encoding="utf-8") as f:
                f.write(lua_script)
            logger.info(f"Generated Lua script: {lua_script_path_str}")
            if logger.level <= logging.DEBUG:
                logger.debug(f"Lua Script Content:\n------\n{lua_script}\n------")
        except IOError as e_lua_write:
            self.set_feedback(f"Error writing Lua script: {e_lua_write}", level="error")
            logger.error("Failed writing Lua script.", exc_info=True)
            return
        process_description = "manual send"
        if run_custom_script:
            process_description = "custom script"
        elif pack_after:
            process_description = "auto pack"
        self.set_feedback(
            f"Launching RizomUV for {process_description}...", level="info"
        )
        cmd = []
        cmd_str_log = ""
        try:
            lua_arg = "-cfi"
            if system == "Windows":
                cmd = [rizom_path_str, lua_arg, lua_script_path_str]
                cmd_str_log = " ".join(f'"{c}"' for c in cmd)
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    text=True,
                    encoding=locale.getpreferredencoding(False),
                )
            elif system == "Darwin":
                cmd = [
                    "open",
                    "-a",
                    rizom_path_str,
                    "--args",
                    lua_arg,
                    lua_script_path_str,
                ]
                cmd_str_log = " ".join(f'"{c}"' for c in cmd)
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
            else:
                cmd = [rizom_path_str, lua_arg, lua_script_path_str]
                cmd_str_log = " ".join(f'"{c}"' for c in cmd)
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding=locale.getpreferredencoding(False),
                )
            logger.info(f"Executing: {cmd_str_log}")
            try:
                stdout, stderr = process.communicate(timeout=5)
                return_code = process.returncode
                stdout_decoded = stdout if stdout else ""
                stderr_decoded = stderr if stderr else ""
                if return_code != 0:
                    logger.warning(f"RizomUV process exited with code {return_code}.")
                    if stdout_decoded:
                        logger.warning(f" stdout: {stdout_decoded.strip()}")
                    if stderr_decoded:
                        logger.warning(f" stderr: {stderr_decoded.strip()}")
                else:
                    logger.info(
                        "RizomUV process executed script and exited/detached cleanly."
                    )
                    if stdout_decoded:
                        logger.info(f" stdout: {stdout_decoded.strip()}")
                    if stderr_decoded:
                        logger.info(f" stderr: {stderr_decoded.strip()}")
            except subprocess.TimeoutExpired:
                logger.info(
                    "RizomUV process likely running in background (timeout expired)."
                )
            final_msg = (
                f"Sent to RizomUV ({process_description}). Use 'Get UVs' when ready."
            )
            if pack_after:
                final_msg = f"Sent to RizomUV (Auto Pack on '{rizom_target_uv_set_name_for_log}'). Use 'Get UVs' when ready."
            self.set_feedback(final_msg, level="info")
        except (subprocess.SubprocessError, FileNotFoundError) as e_subproc:
            self.set_feedback(f"Failed to start RizomUV: {e_subproc}", level="error")
            logger.error(
                f"Subprocess error launching RizomUV. Command: {cmd_str_log}",
                exc_info=True,
            )
        except Exception as e_launch:
            self.set_feedback(
                f"Unexpected error launching RizomUV: {e_launch}", level="error"
            )
            logger.error(
                f"Unexpected error launching RizomUV. Command: {cmd_str_log}",
                exc_info=True,
            )

    def locate_rizom(self):
        original_os_native_dialog_pref = 0
        system = platform.system()
        mac_pref_changed = False
        current_path_str = str(self.config.rizom_location)
        start_dir = ""
        current_path = Path(current_path_str) if current_path_str else None
        if current_path and current_path.exists():
            start_dir = str(current_path.parent)
        elif current_path and current_path.parent.exists():
            start_dir = str(current_path.parent)
        elif system == "Darwin":
            start_dir = "/Applications" if Path("/Applications").exists() else "/"
        elif system == "Windows":
            program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            rizom_dir = Path(program_files) / "Rizom Lab"
            start_dir = (
                str(rizom_dir)
                if rizom_dir.exists()
                else program_files
                if Path(program_files).exists()
                else "C:\\"
            )
        else:
            start_dir = "/usr/bin" if Path("/usr/bin").exists() else "/"
        logger.debug(f"Starting file dialog in: {start_dir}")
        path = None
        try:
            if system == "Darwin":
                try:
                    original_os_native_dialog_pref = cmds.optionVar(
                        query="useOSNativeFileDialog"
                    )
                    if original_os_native_dialog_pref == 0:
                        logger.info(
                            "Temporarily switching Maya to OS Native file dialog for .app selection."
                        )
                        cmds.optionVar(iv=("useOSNativeFileDialog", 1))
                        mac_pref_changed = True
                except Exception as e_optvar:
                    logger.warning(
                        f"Could not query/set OS native dialog preference: {e_optvar}"
                    )
                path = QtWidgets.QFileDialog.getExistingDirectory(
                    self,
                    "Locate RizomUV Application (.app)",
                    start_dir,
                    QtWidgets.QFileDialog.Option.ShowDirsOnly
                    | QtWidgets.QFileDialog.Option.DontResolveSymlinks,
                )
            else:
                file_filter = (
                    "Executables (*.exe)"
                    if system == "Windows"
                    else "Executables (*);;All Files (*)"
                )
                path_tuple = QtWidgets.QFileDialog.getOpenFileName(
                    self, "Locate RizomUV Executable", start_dir, file_filter
                )
                path = (
                    path_tuple[0]
                    if isinstance(path_tuple, tuple) and path_tuple
                    else ""
                )
            if path:
                selected_path = Path(path)
                valid_path = False
                error_msg = ""
                if (
                    system == "Darwin"
                    and selected_path.is_dir()
                    and selected_path.suffix == ".app"
                ):
                    valid_path = True
                elif (
                    system == "Windows"
                    and selected_path.is_file()
                    and selected_path.suffix.lower() == ".exe"
                ):
                    valid_path = True
                elif (
                    system == "Linux"
                    and selected_path.is_file()
                    and os.access(str(selected_path), os.X_OK)
                ):
                    valid_path = True
                elif (
                    system == "Darwin"
                    and selected_path.is_file()
                    and os.access(str(selected_path), os.X_OK)
                ):
                    valid_path = True
                else:
                    error_msg = f"Selected path is not a valid RizomUV {'.app' if system == 'Darwin' else 'executable'} for {system}."
                if valid_path:
                    self.config.rizom_location = str(selected_path)
                    self.location_input.setText(str(selected_path))
                    if self.config.save_config():
                        logger.info(f"RizomUV path set and saved: {selected_path}")
                        self.set_feedback("RizomUV path updated.", level="info")
                    else:
                        self.set_feedback(
                            "Error: Failed to save new RizomUV path.", level="error"
                        )
                else:
                    logger.warning(
                        f"Invalid path selected: {selected_path}. Reason: {error_msg}"
                    )
                    cmds.warning(
                        f"{error_msg}\nPlease select the correct file or application bundle."
                    )
                    self.set_feedback(f"Warning: {error_msg}", level="warning")
            else:
                logger.info("File dialog cancelled by user.")
        except Exception as e_dialog:
            logger.error(
                f"Error during file dialog or path processing: {e_dialog}",
                exc_info=True,
            )
            self.set_feedback("Error during file browse.", level="error")
        finally:
            if mac_pref_changed:
                try:
                    logger.info(
                        f"Restoring Maya file dialog preference to: {original_os_native_dialog_pref}"
                    )
                    cmds.optionVar(
                        iv=("useOSNativeFileDialog", original_os_native_dialog_pref)
                    )
                except Exception as e_optvar_restore:
                    logger.warning(
                        f"Could not restore OS native dialog preference: {e_optvar_restore}"
                    )

    def refresh_uv_options(self):
        self.uv_selector.blockSignals(True)
        logger.info("-" * 20 + " Refreshing UV Sets " + "-" * 20)
        current_choice = self.uv_selector.currentText()
        logger.debug(f"Current UV set dropdown choice: {current_choice}")
        self.uv_selector.clear()
        options = ["All UV Sets"]
        unique_sets = set()
        sel = cmds.ls(sl=True, long=True)
        logger.debug(f"Initial selection: {sel}")
        mesh_shapes = set()
        processed_transforms = set()
        if not sel:
            logger.info("Selection is empty.")
        else:
            objects_from_components = set()
            components = cmds.filterExpand(
                sel, sm=(31, 32, 34, 35), expand=True, fullPath=True
            )
            if components:
                logger.debug(f"Found components: {components}")
                for comp in components:
                    obj_name = comp.split(".")[0]
                    full_obj_path = cmds.ls(obj_name, long=True)
                    if full_obj_path and cmds.objExists(full_obj_path[0]):
                        objects_from_components.add(full_obj_path[0])
                    elif cmds.objExists(obj_name):
                        objects_from_components.add(obj_name)
            logger.debug(
                f"Objects derived from components: {list(objects_from_components)}"
            )
            potential_targets = set(sel) | objects_from_components
            logger.debug(
                f"Combined potential targets for shape query: {list(potential_targets)}"
            )
            for item_path in potential_targets:
                if not cmds.objExists(item_path):
                    logger.debug(f"Item '{item_path}' no longer exists, skipping.")
                    continue
                node_type = cmds.nodeType(item_path)
                shapes_found = []
                transform_node = None
                if node_type == "transform":
                    if item_path not in processed_transforms:
                        shapes_found = (
                            cmds.listRelatives(
                                item_path,
                                shapes=True,
                                type="mesh",
                                noIntermediate=True,
                                fullPath=True,
                            )
                            or []
                        )
                        if shapes_found:
                            transform_node = item_path
                            processed_transforms.add(item_path)
                elif node_type == "mesh":
                    try:
                        if not cmds.getAttr(f"{item_path}.intermediateObject"):
                            shapes_found = [item_path]
                            parents = cmds.listRelatives(
                                item_path, parent=True, fullPath=True
                            )
                            if parents:
                                processed_transforms.add(parents[0])
                    except Exception as e_getattr:
                        logger.warning(
                            f"Could not check intermediateObject attr for {item_path}: {e_getattr}"
                        )
                        continue
                if shapes_found:
                    logger.debug(f"Found shape(s) for '{item_path}': {shapes_found}")
                    mesh_shapes.update(shapes_found)
        if not mesh_shapes:
            logger.info(
                "No processable mesh shapes found in selection. Adding default 'map1'."
            )
            unique_sets.add("map1")
        else:
            logger.info(f"Querying UV sets for mesh shapes: {list(mesh_shapes)}")
            for shape_node in mesh_shapes:
                try:
                    if not cmds.objExists(shape_node):
                        logger.warning(
                            f"Shape node '{shape_node}' not found just before UV set query."
                        )
                        continue
                    uv_sets_on_shape = cmds.polyUVSet(
                        shape_node, query=True, allUVSets=True
                    )
                    logger.info(
                        f"Query result for '{shape_node}': {uv_sets_on_shape} (Type: {type(uv_sets_on_shape)})"
                    )
                    if uv_sets_on_shape:
                        unique_sets.update(uv_sets_on_shape)
                    elif uv_sets_on_shape is None:
                        logger.debug(
                            f"Query returned None for '{shape_node}', assuming default 'map1'."
                        )
                        unique_sets.add("map1")
                except Exception as e_query:
                    logger.error(
                        f"Could not query UV sets for shape '{shape_node}': {e_query}",
                        exc_info=True,
                    )
        if unique_sets:
            sorted_sets = sorted(list(unique_sets))
            if "map1" in sorted_sets:
                sorted_sets.remove("map1")
                sorted_sets.insert(0, "map1")
            options.extend(sorted_sets)
        elif not mesh_shapes:
            pass
        elif "map1" not in unique_sets:
            logger.debug("Adding 'map1' as fallback since no other sets were found.")
            unique_sets.add("map1")
            options.append("map1")
        final_options = []
        seen = set()
        for item in options:
            if item not in seen:
                final_options.append(item)
                seen.add(item)
        logger.info(f"Final options for UV selector: {final_options}")
        self.uv_selector.addItems(final_options)
        found_index = self.uv_selector.findText(current_choice)
        if found_index != -1:
            self.uv_selector.setCurrentIndex(found_index)
            logger.debug(f"Restored previous selection: '{current_choice}'")
        else:
            map1_index = self.uv_selector.findText("map1")
            if map1_index != -1:
                self.uv_selector.setCurrentIndex(map1_index)
                logger.debug("Defaulted selection to 'map1'")
            elif len(final_options) > 1:
                self.uv_selector.setCurrentIndex(1)
                logger.debug("Defaulted selection to first available set")
            else:
                self.uv_selector.setCurrentIndex(0)
                logger.debug("Defaulted selection to 'All UV Sets'")
        self.uv_selector.blockSignals(False)
        logger.info("-" * 50)

    def persist_config(self):
        logger.debug("Persisting UI settings to config...")
        config_changed = False
        new_include_uvs = self.uv_toggle.isChecked()
        if self.config.include_uvs != new_include_uvs:
            self.config.include_uvs = new_include_uvs
            config_changed = True
            logger.debug(f"Config change: include_uvs = {new_include_uvs}")
        new_rizom_location = self.location_input.text().strip()
        if str(self.config.rizom_location) != new_rizom_location:
            new_path = Path(new_rizom_location)
            is_valid = False
            if platform.system() == "Darwin":
                is_valid = (
                    new_path.suffix == ".app"
                    and new_path.is_dir()
                    or new_path.is_file()
                    and os.access(new_rizom_location, os.X_OK)
                )
            elif platform.system() == "Windows":
                is_valid = new_path.is_file() and new_path.suffix.lower() == ".exe"
            else:
                is_valid = new_path.is_file() and os.access(new_rizom_location, os.X_OK)
            if is_valid:
                self.config.rizom_location = new_rizom_location
                config_changed = True
                logger.debug(f"Config change: rizom_location = {new_rizom_location}")
            else:
                logger.warning(
                    f"Attempted to save non-existent or invalid Rizom path: {new_rizom_location}. Change not saved."
                )
        new_pack_quality = self.quality_selector.currentIndex()
        if self.config.pack_quality != new_pack_quality:
            self.config.pack_quality = new_pack_quality
            config_changed = True
            logger.debug(f"Config change: pack_quality = {new_pack_quality}")
        new_pack_iterations = self.iterations_spinner.value()
        if self.config.pack_iterations != new_pack_iterations:
            self.config.pack_iterations = new_pack_iterations
            config_changed = True
            logger.debug(f"Config change: pack_iterations = {new_pack_iterations}")
        if config_changed:
            logger.info("Configuration changed, saving...")
            if not self.config.save_config():
                self.set_feedback("Error saving configuration.", level="error")
        else:
            logger.debug("No configuration changes detected, skipping save.")

    def set_feedback(self, message, level="info"):
        message = str(message)
        if level == "info":
            logger.info(message)
            self.feedback_label.setStyleSheet("")
        elif level == "warning":
            logger.warning(message)
            self.feedback_label.setStyleSheet("QLabel { color : orange; }")
        elif level == "error":
            logger.error(message)
            self.feedback_label.setStyleSheet("QLabel { color : red; }")
        else:
            logger.debug(f"Feedback (level='{level}'): {message}")
            self.feedback_label.setStyleSheet("")
        self.feedback_label.setText(message)

    def _send_save_command_to_rizom(self):
        """Sends a Lua save command to RizomUV to update the bridge FBX."""
        rizom_path_str = str(self.config.rizom_location)
        lua_script_path_str = self.config.get_lua_script_path_str()
        lua_fbx_path = str(self.config.fbx_export_file_path).replace("\\", "/")
        lua_script = "\n".join(
            [
                "-- Maya Bridge Auto-Save --",
                f'ZomSave({{File={{Path="{lua_fbx_path}", UVWProps=true}}, __UpdateUIObjFileName=true}})',
            ]
        )
        try:
            Path(lua_script_path_str).parent.mkdir(parents=True, exist_ok=True)
            with open(lua_script_path_str, "w", encoding="utf-8") as f:
                f.write(lua_script)
            logger.info(f"Generated save Lua script: {lua_script_path_str}")
        except IOError as e:
            logger.error(f"Failed to write save Lua script: {e}")
            return False
        system = platform.system()
        lua_arg = "-cfi"
        cmd = []
        try:
            if system == "Windows":
                cmd = [rizom_path_str, lua_arg, lua_script_path_str]
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    text=True,
                    encoding=locale.getpreferredencoding(False),
                )
            elif system == "Darwin":
                cmd = ["open", "-a", rizom_path_str, "--args", lua_arg, lua_script_path_str]
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                cmd = [rizom_path_str, lua_arg, lua_script_path_str]
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding=locale.getpreferredencoding(False),
                )
            logger.info("Executing: %s", " ".join(f'\"{c}\"' for c in cmd))
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                logger.info("RizomUV save command sent (timeout expired).")
            return True
        except Exception as e:
            logger.error("Failed to execute RizomUV save command: %s", e, exc_info=True)
            return False

    def fetch_from_rizom(self):
        "Imports UVs from the bridge FBX file back into Maya selection.\n        NOTE: This version uses polyTransfer and likely transfers ALL matching UV sets."
        self.set_feedback("Requesting save from RizomUV...", level="info")
        self._send_save_command_to_rizom()
        self.set_feedback("Attempting to import UVs from Rizom...", level="info")
        cmds.refresh()
        target_objects = cmds.ls(selection=True, long=True, type="transform")
        if not target_objects:
            self.set_feedback(
                "Error: No target objects selected in Maya.", level="error"
            )
            logger.error("No target objects selected for fetch_from_rizom.")
            return
        fbx_source_path_str = self.config.get_fbx_export_path_str()
        fbx_source_path = Path(fbx_source_path_str)
        if not fbx_source_path.is_file():
            self.set_feedback(
                f"Error: Source FBX file not found: {fbx_source_path.name}",
                level="error",
            )
            logger.error(
                f"Cannot find FBX file to import UVs from: {fbx_source_path_str}"
            )
            return
        target_uv_set_name_from_ui = self.uv_selector.currentText()
        logger.info(
            f"Importing UVs from: {fbx_source_path_str} (Target set in UI: '{target_uv_set_name_from_ui}') on {len(target_objects)} object(s). NOTE: Will likely transfer ALL matching sets."
        )
        import_namespace = "RZMUVIMPORT"
        if cmds.namespace(exists=import_namespace):
            logger.info(f"Cleaning existing namespace: {import_namespace}")
            self._cleanup_import_namespace(import_namespace)
        if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
            try:
                cmds.loadPlugin("fbxmaya", quiet=True)
                logger.info("Loaded fbxmaya plugin for import.")
            except Exception as e:
                self.set_feedback(
                    "Error: Failed to load FBX plugin for import.", level="error"
                )
                logger.error(f"Failed to load fbxmaya plugin: {e}")
                return
        imported_nodes = []
        try:
            mel.eval("FBXImportMode -v Add;")
            mel.eval("FBXImportGenerateLog -v false;")
            imported_nodes = cmds.file(
                fbx_source_path_str,
                i=True,
                type="FBX",
                ignoreVersion=True,
                renameAll=True,
                namespace=import_namespace,
                options="fbx",
                preserveReferences=False,
                returnNewNodes=True,
                prompt=False,
                loadReferenceDepth="all",
            )
            logger.info(f"Imported FBX into namespace '{import_namespace}'.")
        except Exception as e:
            self.set_feedback("Error: Failed to import bridge FBX file.", level="error")
            logger.error(f"FBX Import failed: {e}", exc_info=True)
            self._cleanup_import_namespace(import_namespace)
            return
        imported_transforms = (
            cmds.ls(f"{import_namespace}:*", type="transform", long=True) or []
        )
        if not imported_transforms:
            return
        transfer_count = 0
        error_count = 0
        processed_targets = set()
        cmds.undoInfo(openChunk=True, chunkName="Fetch Rizom UVs")
        try:
            for target_transform in target_objects:
                if target_transform in processed_targets:
                    continue
                processed_targets.add(target_transform)
                target_leaf_name = target_transform.split("|")[-1].split(":")[-1]
                logger.debug(
                    f"Processing target: {target_transform} (Leaf Name: {target_leaf_name})"
                )
                matched_import_source = None
                for imp_transform in imported_transforms:
                    if imp_transform.split("|")[-1].split(":")[-1] == target_leaf_name:
                        matched_import_source = imp_transform
                        logger.info(f"Matched imported object: {matched_import_source}")
                        break
                if not matched_import_source:
                    logger.warning(
                        f"No matching imported object for target: {target_transform}"
                    )
                    error_count += 1
                    continue
                source_shapes = (
                    cmds.listRelatives(
                        matched_import_source, s=True, ni=True, f=True, type="mesh"
                    )
                    or []
                )
                target_shapes = (
                    cmds.listRelatives(
                        target_transform, s=True, ni=True, f=True, type="mesh"
                    )
                    or []
                )
                if not source_shapes or not target_shapes:
                    logger.warning("No mesh shapes for match: Source/Target")
                    error_count += 1
                    continue
                src_shape = source_shapes[0]
                trg_shape = target_shapes[0]
                try:
                    src_uv_sets = (
                        cmds.polyUVSet(src_shape, query=True, allUVSets=True) or []
                    )
                    trg_uv_sets = (
                        cmds.polyUVSet(trg_shape, query=True, allUVSets=True) or []
                    )
                    original_target_active_set = (
                        cmds.polyUVSet(trg_shape, query=True, currentUVSet=True)[0]
                        if trg_uv_sets
                        else None
                    )
                    logger.info(f"Source UV sets: {src_uv_sets}")
                    logger.debug(f"Target UV sets before: {trg_uv_sets}")
                    created_sets_count = 0
                    for s_set in src_uv_sets:
                        if s_set and s_set not in trg_uv_sets:
                            try:
                                cmds.polyUVSet(trg_shape, create=True, uvSet=s_set)
                                logger.info(
                                    f"Created missing UV set '{s_set}' on target {trg_shape}"
                                )
                                created_sets_count += 1
                            except Exception as e_create:
                                logger.error(
                                    f"Failed to create UV set '{s_set}' on {trg_shape}: {e_create}"
                                )
                                error_count += 1
                    if created_sets_count > 0:
                        trg_uv_sets = (
                            cmds.polyUVSet(trg_shape, query=True, allUVSets=True) or []
                        )
                except Exception as e_setup:
                    logger.error(
                        f"Error preparing UV sets for {target_transform}: {e_setup}",
                        exc_info=True,
                    )
                    error_count += 1
                    continue
                transfer_successful_for_object = False
                original_selection = cmds.ls(sl=True, long=True)
                try:
                    cmds.select(trg_shape, replace=True)
                    logger.debug(
                        f"Selected only target shape '{trg_shape}' for polyTransfer."
                    )
                    cmds.polyTransfer(
                        trg_shape, ao=src_shape, uv=True, v=False, vc=False, ch=False
                    )
                    logger.info(
                        f"Ran polyTransfer (uv=True) From '{src_shape}' To '{trg_shape}'. (Likely transferred ALL matching sets)"
                    )
                    transfer_successful_for_object = True
                    try:
                        cmds.delete(trg_shape, constructionHistory=True)
                    except RuntimeError:
                        pass
                    except Exception as e_hist:
                        logger.warning(
                            f"Could not delete history after polyTransfer: {e_hist}"
                        )
                except Exception as e_xfer:
                    logger.error(
                        f"Error using polyTransfer (ref script method) for {target_transform}: {e_xfer}",
                        exc_info=True,
                    )
                    error_count += 1
                finally:
                    if original_selection:
                        try:
                            valid_original_selection = [
                                s for s in original_selection if cmds.objExists(s)
                            ]
                            if valid_original_selection:
                                cmds.select(valid_original_selection, replace=True)
                            else:
                                cmds.select(clear=True)
                        except Exception as e_sel:
                            logger.warning(
                                f"Could not restore original selection: {e_sel}"
                            )
                    else:
                        try:
                            cmds.select(clear=True)
                        except Exception as e_sel_clr:
                            logger.warning(f"Could not clear selection: {e_sel_clr}")
                if transfer_successful_for_object:
                    transfer_count += 1
                if original_target_active_set and cmds.objExists(trg_shape):
                    try:
                        all_sets_now = (
                            cmds.polyUVSet(trg_shape, query=True, allUVSets=True) or []
                        )
                        if original_target_active_set in all_sets_now:
                            cmds.polyUVSet(
                                trg_shape,
                                currentUVSet=True,
                                uvSet=original_target_active_set,
                            )
                            logger.debug(
                                f"Restored original active set '{original_target_active_set}' on {trg_shape}"
                            )
                        elif all_sets_now:
                            cmds.polyUVSet(
                                trg_shape, currentUVSet=True, uvSet=all_sets_now[0]
                            )
                            logger.warning(
                                f"Original active set '{original_target_active_set}' no longer exists. Activating '{all_sets_now[0]}'."
                            )
                    except Exception as e_restore:
                        logger.warning(
                            f"Failed to restore original active set on {trg_shape}: {e_restore}"
                        )
        except Exception as e_main_loop:
            logger.error(
                f"Unexpected error in UV transfer loop: {e_main_loop}", exc_info=True
            )
            cmds.undo()
            self.set_feedback(
                "Critical error during UV transfer. Rolled back.", level="error"
            )
        finally:
            cmds.undoInfo(closeChunk=True)
            self._cleanup_import_namespace(import_namespace)
        logger.info("Forcing UI Refresh after UV transfer attempts.")
        cmds.refresh(force=True)
        if target_objects and all(cmds.objExists(o) for o in target_objects):
            cmds.select(target_objects, replace=True)
        else:
            cmds.select(clear=True)
        self.refresh_uv_options()
        num_targets = len(target_objects)
        if error_count == 0 and transfer_count == num_targets:
            self.set_feedback(
                f"UVs imported to {transfer_count} object(s) (All matching sets transferred).",
                level="info",
            )
        elif transfer_count > 0:
            level = (
                "warning" if error_count > 0 or transfer_count < num_targets else "info"
            )
            self.set_feedback(
                f"UV Import finished for {transfer_count}/{num_targets} objects. Errors/Skipped: {error_count + (num_targets - transfer_count)}.",
                level=level,
            )
        else:
            self.set_feedback(
                f"UV import failed for {num_targets} object(s). Errors: {error_count}. Check logs.",
                level="error",
            )

    def _cleanup_import_namespace(self, namespace):
        if not cmds.namespace(exists=namespace):
            logger.debug(f"Namespace '{namespace}' does not exist, no cleanup needed.")
            return
        logger.info(f"Cleaning up namespace: {namespace}")
        try:
            nodes_in_namespace = cmds.ls(f"{namespace}:*", long=True) or []
            valid_nodes_to_delete = [n for n in nodes_in_namespace if cmds.objExists(n)]
            if valid_nodes_to_delete:
                logger.debug(
                    f"Attempting to delete {len(valid_nodes_to_delete)} nodes in namespace '{namespace}'..."
                )
                try:
                    cmds.lockNode(valid_nodes_to_delete, lock=False)
                    logger.debug(f"Unlocked nodes in namespace '{namespace}'.")
                except Exception as e_unlock:
                    logger.warning(
                        f"Could not unlock nodes in '{namespace}', delete might fail: {e_unlock}"
                    )
                try:
                    cmds.delete(valid_nodes_to_delete)
                    logger.info(
                        f"Deleted {len(valid_nodes_to_delete)} nodes from namespace '{namespace}'."
                    )
                except Exception as e_delete:
                    logger.error(
                        f"Failed to delete some nodes in namespace '{namespace}': {e_delete}. Cleanup may fail."
                    )
            else:
                logger.debug(f"No nodes found to delete in namespace '{namespace}'.")
            cmds.namespace(setNamespace=":")
            if cmds.namespace(exists=namespace):
                cmds.namespace(
                    removeNamespace=namespace, mergeNamespaceWithRoot=False, force=True
                )
                logger.info(f"Successfully removed namespace '{namespace}'.")
            else:
                logger.info(
                    f"Namespace '{namespace}' seems to have been removed during node deletion."
                )
        except RuntimeError as e_ns:
            logger.error(
                f"Failed to remove namespace '{namespace}' even after attempting node deletion: {e_ns}"
            )
        except Exception as e_clean:
            logger.error(
                f"Unexpected error cleaning namespace '{namespace}': {e_clean}",
                exc_info=True,
            )

    def adjust_angle(self, value):
        self.edge_angle_threshold = value
        logger.info(f"Normals: Angle tolerance set to {self.edge_angle_threshold:.1f}")

    def toggle_tolerance(self, checked):
        self.use_angle_tolerance = checked
        logger.info(
            f"Normals: Use angle tolerance {'enabled' if self.use_angle_tolerance else 'disabled'}"
        )

    def process_uv_edges(self):
        self.set_feedback("Processing normals based on UV borders...", level="info")
        selection = cmds.ls(selection=True, long=True, objectsOnly=True)
        if not selection:
            self.set_feedback(
                "Error: No objects or components selected.", level="error"
            )
            logger.error("process_uv_edges: No selection.")
            return
        target_shapes = set()
        original_transforms_selected = set()
        mesh_components = cmds.filterExpand(
            selection, sm=(31, 32, 34), expand=True, fullPath=True
        )
        if mesh_components:
            for comp in mesh_components:
                obj_name = comp.split(".")[0]
                full_obj_path_list = cmds.ls(obj_name, long=True)
                if full_obj_path_list:
                    obj_path = full_obj_path_list[0]
                    if cmds.objExists(obj_path):
                        shapes = []
                        if cmds.nodeType(obj_path) == "mesh":
                            if not cmds.getAttr(f"{obj_path}.intermediateObject"):
                                shapes = [obj_path]
                                parent_tfm = cmds.listRelatives(
                                    obj_path, parent=True, fullPath=True
                                )
                                if parent_tfm:
                                    original_transforms_selected.add(parent_tfm[0])
                        elif cmds.nodeType(obj_path) == "transform":
                            shapes = (
                                cmds.listRelatives(
                                    obj_path,
                                    shapes=True,
                                    type="mesh",
                                    noIntermediate=True,
                                    fullPath=True,
                                )
                                or []
                            )
                            if shapes:
                                original_transforms_selected.add(obj_path)
                        if shapes:
                            target_shapes.add(shapes[0])
        object_selection = cmds.ls(selection, type="transform", long=True) + cmds.ls(
            selection, type="mesh", long=True
        )
        for item in object_selection:
            if cmds.objExists(item):
                shapes = []
                if cmds.nodeType(item) == "mesh":
                    if not cmds.getAttr(f"{item}.intermediateObject"):
                        shapes = [item]
                        parent_tfm = cmds.listRelatives(
                            item, parent=True, fullPath=True
                        )
                        if parent_tfm:
                            original_transforms_selected.add(parent_tfm[0])
                elif cmds.nodeType(item) == "transform":
                    shapes = (
                        cmds.listRelatives(
                            item,
                            shapes=True,
                            type="mesh",
                            noIntermediate=True,
                            fullPath=True,
                        )
                        or []
                    )
                    if shapes:
                        original_transforms_selected.add(item)
                if shapes:
                    target_shapes.add(shapes[0])
        target_shapes = list(target_shapes)
        if not target_shapes:
            self.set_feedback(
                "Error: Selection contains no processable mesh objects.", level="error"
            )
            logger.warning(f"No mesh shapes identified from selection: {selection}")
            return
        logger.info(f"Processing normals for shapes: {target_shapes}")
        processed_count = 0
        cmds.undoInfo(openChunk=True, chunkName="Process UV Edges")
        try:
            for mesh_shape in target_shapes:
                if not cmds.objExists(mesh_shape):
                    continue
                parent_transform = cmds.listRelatives(
                    mesh_shape, parent=True, fullPath=True
                )
                if not parent_transform:
                    continue
                current_transform = parent_transform[0]
                logger.info(f"Processing: {mesh_shape} (Parent: {current_transform})")
                logger.debug(f"Softening all edges on {mesh_shape}")
                cmds.polySoftEdge(mesh_shape, angle=180, constructionHistory=False)
                logger.debug(f"Selecting UV borders on {mesh_shape}")
                cmds.select(mesh_shape, replace=True)
                cmds.polySelectConstraint(mode=3, type=32768, where=1, textureBorder=1)
                border_edges = cmds.ls(selection=True, flatten=True)
                cmds.polySelectConstraint(disable=True)
                if border_edges:
                    edge_components = cmds.filterExpand(border_edges, sm=32)
                    if edge_components:
                        logger.debug(
                            f"Hardening {len(edge_components)} UV border edges."
                        )
                        cmds.polySoftEdge(
                            edge_components, angle=0, constructionHistory=False
                        )
                    else:
                        logger.info(
                            f"No valid edge components found after border selection for {mesh_shape}."
                        )
                else:
                    logger.info(f"No UV border edges were selected for {mesh_shape}.")
                if self.use_angle_tolerance:
                    logger.debug(
                        f"Applying tolerance softening ({self.edge_angle_threshold:.1f} deg) to {mesh_shape}"
                    )
                    cmds.polySoftEdge(
                        mesh_shape,
                        angle=self.edge_angle_threshold,
                        constructionHistory=False,
                    )
                processed_count += 1
            if original_transforms_selected:
                valid_selection = [
                    t for t in original_transforms_selected if cmds.objExists(t)
                ]
                if valid_selection:
                    cmds.select(valid_selection, replace=True)
                else:
                    cmds.select(clear=True)
            else:
                cmds.select(clear=True)
        except Exception as e_process:
            self.set_feedback(
                f"Error during edge processing: {e_process}", level="error"
            )
            logger.exception("Edge processing error details:")
            cmds.undo()
        finally:
            cmds.undoInfo(closeChunk=True)
        if processed_count > 0:
            self.set_feedback(
                f"Processed normals on {processed_count} object(s).", level="info"
            )
        elif target_shapes:
            self.set_feedback("No mesh objects processed. Check logs.", level="warning")


def fetch_maya_root():
    try:
        ptr = omui.MQtUtil.mainWindow()
        if ptr is None:
            logger.error("Could not get Maya main window pointer.")
            return None
        main_window = wrapInstance(int(ptr), QtWidgets.QWidget)
        return main_window
    except Exception as e:
        logger.error(f"Could not wrap Maya main window instance: {e}", exc_info=True)
        return None
    
def launch_tool():
    global rizom_bridge_panel_instance
    global config
    intended_workspace_control_name = "rizomUVBridgeWorkspaceControl"
    panel_object_name = "rizomUVBridgePanelInstance"
    window_title = "RizomUV <> Maya Bridge v2.3.0"
    logger.info(f"Launching {window_title} Tool (Manual)...")
    if cmds.workspaceControl(intended_workspace_control_name, q=True, exists=True):
        logger.warning(
            f"Deleting existing workspace control: {intended_workspace_control_name}"
        )
        try:
            cmds.deleteUI(intended_workspace_control_name, control=True)
        except Exception as e_del_wc:
            logger.error(f"Error deleting workspace control: {e_del_wc}")
    if rizom_bridge_panel_instance is not None:
        logger.warning("Cleaning up previous global panel instance...")
        try:
            rizom_bridge_panel_instance.deleteLater()
        except Exception as e_del_inst:
            logger.error(f"Error deleting previous instance: {e_del_inst}")
        finally:
            rizom_bridge_panel_instance = None
    root = fetch_maya_root()
    if root is None:
        logger.critical("Cannot launch: Maya main window not found.")
        cmds.warning("RizomBridge: Cannot find Maya main window.")
        return None
    if not config:
        logger.critical("Cannot launch: ConfigManager failed or not initialized.")
        cmds.warning("RizomBridge: Configuration Manager failed.")
        return None
    try:
        logger.info("Creating new UVBridgePanel instance globally...")
        rizom_bridge_panel_instance = UVBridgePanel(parent=root)
        rizom_bridge_panel_instance.setObjectName(panel_object_name)
    except Exception as e_create_inst:
        logger.error(
            f"Failed to create UVBridgePanel instance: {e_create_inst}", exc_info=True
        )
        rizom_bridge_panel_instance = None
        return None
    module_path_for_script = (
        f"{INSTALL_SUBDIR}.{MODULE_NAME}" if INSTALL_SUBDIR else MODULE_NAME
    )

    ui_script_lines = [
        f"import {module_path_for_script}",
        f"{module_path_for_script}._setup_panel_content_deferred()"
    ]
    ui_script_for_control = "; ".join(line.strip() for line in ui_script_lines)
    logger.info(f"Generated uiScript for control: {ui_script_for_control}")
    try:
        logger.info(f"Creating workspace control: {intended_workspace_control_name}")
        cmds.workspaceControl(
            intended_workspace_control_name,
            label=window_title,
            retain=False,
            loadImmediately=False,
            uiScript=ui_script_for_control,
            initialWidth=300,
            minimumWidth=250,
        )
        logger.info(f"Workspace control '{intended_workspace_control_name}' created.")
        deferred_setup_call = f"import {module_path_for_script}; {module_path_for_script}._setup_panel_content_deferred()"
        logger.info(f"Scheduling deferred content setup: {deferred_setup_call}")
        maya.utils.executeDeferred(lambda: _setup_panel_content_deferred())
        try:
            print(BRIDGE_ASCII_ART)
        except Exception as e_art:
            logger.warning(f"Could not print ASCII art: {e_art}")
        return rizom_bridge_panel_instance
    except Exception as e_wc:
        logger.error(
            f"Error creating/configuring workspace control '{intended_workspace_control_name}': {e_wc}",
            exc_info=True,
        )
        cleanup_rizom_bridge_instance()
        return None


def _setup_panel_content_deferred():
    global rizom_bridge_panel_instance
    global config
    global PYSIDE_VERSION
    global MODULE_NAME, INSTALL_SUBDIR
    workspace_control_name = "rizomUVBridgeWorkspaceControl"
    panel_object_name = "rizomUVBridgePanelInstance"
    logger.info(
        f"Executing _setup_panel_content_deferred for {workspace_control_name}..."
    )
    if rizom_bridge_panel_instance is None:
        logger.warning(
            "Global panel instance was None during deferred setup. Attempting creation..."
        )
        parent_widget = fetch_maya_root()
        if not parent_widget:
            logger.error("Cannot create panel instance: Maya main window not found.")
            return
        if not config:
            logger.error("Cannot create panel instance: ConfigManager not ready.")
            return
        try:
            rizom_bridge_panel_instance = UVBridgePanel(parent=parent_widget)
            rizom_bridge_panel_instance.setObjectName(panel_object_name)
            logger.info(
                f"Created new global instance during deferred setup: {rizom_bridge_panel_instance}"
            )
        except Exception as e_create_inst:
            logger.error(
                f"Failed to create UVBridgePanel instance during deferred setup: {e_create_inst}",
                exc_info=True,
            )
            rizom_bridge_panel_instance = None
            return
    if rizom_bridge_panel_instance is None:
        logger.error("Instance is still None after creation attempt. Cannot parent UI.")
        return
    workspace_ptr = omui.MQtUtil.findControl(workspace_control_name)
    if not workspace_ptr:
        logger.error(
            f"Could not find workspace control pointer '{workspace_control_name}' during deferred setup."
        )
        return
    workspace_widget = None
    try:
        if PYSIDE_VERSION == 6:
            from shiboken6 import wrapInstance
        else:
            from shiboken2 import wrapInstance
        workspace_widget = wrapInstance(int(workspace_ptr), QtWidgets.QWidget)
        if not workspace_widget:
            raise RuntimeError("wrapInstance returned None")
        logger.info(f"Found workspace widget: {workspace_widget.objectName()}")
    except Exception as e_wrap:
        logger.error(
            f"Failed to wrap workspace control widget: {e_wrap}", exc_info=True
        )
        return
    panel_already_exists = workspace_widget.findChild(
        QtWidgets.QWidget, panel_object_name
    )
    if panel_already_exists and panel_already_exists == rizom_bridge_panel_instance:
        logger.info(
            f"Panel instance '{panel_object_name}' already present and matches global instance."
        )
        try:
            rizom_bridge_panel_instance.show()
            rizom_bridge_panel_instance.refresh_uv_options()
        except Exception as e_reshow:
            logger.warning(f"Error re-showing/refreshing existing panel: {e_reshow}")
        return
    if panel_already_exists:
        logger.warning(
            f"Found an unexpected/different widget '{panel_already_exists.objectName()}' with the target object name in layout. Removing it."
        )
        panel_already_exists.setParent(None)
        panel_already_exists.deleteLater()
    logger.info(
        f"Setting up parent and layout for instance: {rizom_bridge_panel_instance.objectName()}"
    )
    try:
        rizom_bridge_panel_instance.setParent(workspace_widget)
        layout = workspace_widget.layout()
        if not layout:
            logger.debug("Creating new QVBoxLayout for workspace widget.")
            layout = QtWidgets.QVBoxLayout(workspace_widget)
            layout.setContentsMargins(0, 0, 0, 0)
            workspace_widget.setLayout(layout)
        widgets_to_delete = []
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget and widget != rizom_bridge_panel_instance:
                widget.setParent(None)
                widgets_to_delete.append(widget)
        for w in widgets_to_delete:
            w.deleteLater()
        if layout.indexOf(rizom_bridge_panel_instance) < 0:
            logger.debug(
                f"Adding widget {rizom_bridge_panel_instance.objectName()} to layout."
            )
            layout.addWidget(rizom_bridge_panel_instance)
        rizom_bridge_panel_instance.show()
        rizom_bridge_panel_instance.refresh_uv_options()
        logger.info("Panel content setup completed.")
    except Exception as e_setup:
        logger.error(
            f"Error setting up panel content in layout: {e_setup}", exc_info=True
        )


def cleanup_rizom_bridge_instance():
    global rizom_bridge_panel_instance
    logger.info("Attempting cleanup_rizom_bridge_instance...")
    if rizom_bridge_panel_instance is not None:
        logger.debug(
            f"Found instance (id: {id(rizom_bridge_panel_instance)}). Deleting..."
        )
        try:
            rizom_bridge_panel_instance.deleteLater()
        except Exception as e_del:
            logger.error(f"Error deleting instance: {e_del}", exc_info=True)
        finally:
            rizom_bridge_panel_instance = None
            logger.info("Global instance reference cleared.")
    else:
        logger.info("No active instance found to clean up.")


if __name__ == "__main__":
    logger.info("-" * 60)
    logger.info(f"Executing Rizom Bridge script directly (__name__='{__name__}')")
    logger.info(f"Using PySide Version: {PYSIDE_VERSION}")
    logger.info(f"Maya Version: {cmds.about(version=True)}")
    logger.info(f"Python Version: {sys.version}")
    logger.info(f"Base Directory: {config.base_dir if config else 'CONFIG FAILED'}")
    logger.info("-" * 60)
    panel = launch_tool()
    if panel:
        logger.info("RizomBridge UI launched successfully.")
    else:
        logger.error("Failed to launch RizomBridge UI.")
