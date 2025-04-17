# -*- coding: utf-8 -*-
"""
RizomUV Bridge Tool for Autodesk Maya

Provides a dockable panel in Maya to facilitate sending geometry to RizomUV
for UV unwrapping/packing and retrieving the results back into Maya.
Includes options for manual transfer, automated packing via Lua scripting,
and post-processing of normals based on UV shells.
"""

import base64
import json
import locale
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile  # Although imported, tempfile doesn't seem explicitly used. Consider removal if truly unused.
from pathlib import Path

# --- Maya and UI Imports ---
import maya.OpenMayaUI as omui
import maya.cmds as cmds
import maya.mel as mel
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

# --- PySide Import Logic ---
# Attempt to import PySide6 for Maya 2024+ (Python 3.10+ typically),
# fall back to PySide2 otherwise.
# NOTE: The final `PYSIDE_VERSION = 2` forces PySide2 regardless of detection.
# This might be intentional for compatibility or a remnant of previous code.
# If targeting newer Maya versions exclusively, this logic could be simplified.
PYSIDE_VERSION = 2 # Default assumption
if sys.version_info.major >= 3: # PySide6 requires Python 3+
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
        from shiboken6 import wrapInstance

        PYSIDE_VERSION = 6
        print("RizomBridge: Using PySide6")
    except ImportError:
        try:
            from PySide2 import QtCore, QtGui, QtWidgets
            from shiboken2 import wrapInstance

            PYSIDE_VERSION = 2
            print("RizomBridge: PySide6 not found, using PySide2.")
        except ImportError:
            print("ERROR: Neither PySide6 nor PySide2 found. UI cannot be created.")
            # You might want to raise an exception or handle this more gracefully
            sys.exit("Missing required UI library (PySide2 or PySide6).")
else: # Python 2 (older Maya versions)
     try:
        from PySide2 import QtCore, QtGui, QtWidgets
        from shiboken2 import wrapInstance
        PYSIDE_VERSION = 2
        print("RizomBridge: Using PySide2 (Python 2 environment).")
     except ImportError:
        print("ERROR: PySide2 not found. UI cannot be created.")
        sys.exit("Missing required UI library (PySide2).")

# Force PySide2 - Remove or comment this line if automatic detection is desired.
# PYSIDE_VERSION = 2
# print(f"RizomBridge: Forcing PySide Version {PYSIDE_VERSION}")


# --- Constants ---
INSTALL_SUBDIR_NAME = "RZMUV"
CONFIG_FILE_NAME = "settings.json"
LUA_SCRIPT_FILE_NAME = "rizomuv_control_script.lua"
FBX_FILE_NAME = "RizomUVMayaBridge.fbx"

# Default paths differ per OS
PATH_DEFAULTS = {
    "Windows": r"C:\Program Files\Rizom Lab\RizomUV 2024.0\rizomuv.exe",
    "Darwin": "/Applications/RizomUV 2024.1.app", # macOS .app is a directory
    "Linux": "/opt/rizomuv/rizomuv", # Example Linux path, adjust as needed
}

# Base64 encoded logo data (truncated in prompt, kept as is)
logo_encoded = "iVBORw0KGgoAAAANSUhEUgAAAH0AAAB9CA"

BRIDGE_ASCII_ART = r"""
                      +++++++
                    ++++++++++++++
                   +++++++++++++++ +
                   +++++++++++++++ ++
         ++        ++++++++++++++ +++++
       ++++++++++  ++++++++++++++ ++++++
       ++++++++++++  ++++++++++++++ +++++++
       ++++++++++++   +++++++++++++ ++++++++
       +++++++++++++       ++++++ ++++++++++
        ++++++++++++             +++++++++++
        ++++++++++++            ++++++++++++
        ++++++++++++            ++++++++++++
         ++++++++++++           ++++++++++++
         ++++++++++++           ++++++++++++
         ++++++++++++          ++++++++++++
         +++++++++++++         ++++++++++++
          ++++++++++++         ++++++++++++
          ++++++++++++         ++++++++++++
          ++++++++++++         ++++++++++++
           +++++++++++ +++++++++++++++++++ +++++++++++
                +++++++++ +++++++++++++++++++ +++++++++
                   +++++++ +++++++++++++++++++ +++++++
                    +++++  ++++++++++++++++++ +++++
                     ++++ +++++++++++++++++ +++
                      ++ +++++++++++++++++ ++


      ++++++   ++ ++++++++  +++++     ++     ++     +++   ++ +++     ++
      +++  +++ ++     +++ ++   +++  +++    +++     +++   ++  ++    +++
      ++   ++ ++    +++  +++     ++ +++++ ++ +     +++   +++  ++  +++
      +++++++  ++   +++   +++     ++ ++ ++++ ++     +++   ++   ++++++
      ++  +++ ++ +++++++  +++   +++ ++  ++  ++      ++  ++++   ++++
      ++   ++ ++ ++++++++   ++++    ++    ++ ++       +++      ++
"""

# --- Setup Logging ---
# Create a dedicated logger instance for this tool
logger = logging.getLogger("RizomBridge")

def setup_logging(level=logging.ERROR):
    """Configures the RizomBridge logger."""
    # Prevent adding multiple handlers on script reload
    if not logger.handlers:
        logger.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
        )
        # Log to Maya script editor (standard output)
        ch = logging.StreamHandler(sys.stdout)
        # Handler level should be low to allow logger level to control output
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        # Prevent messages reaching the root logger (avoid duplicate logs)
        logger.propagate = False
        logger.info(f"RizomBridge logger initialized with level {logging.getLevelName(level)}.")
    else:
        # If handlers exist, just update the level
        logger.setLevel(level)
        logger.info(f"RizomBridge logger level set to {logging.getLevelName(level)}.")

# Initialize logging with default level (ERROR)
setup_logging(level=logging.INFO) # Start with INFO for better initial feedback
# --- End Logging Setup ---


def safe_decode_subprocess(output_bytes, command_str=""):
    """
    Attempts to decode subprocess output bytes using common encodings.

    Args:
        output_bytes (bytes): The raw byte string from subprocess.
        command_str (str, optional): The command that produced the output (for logging). Defaults to "".

    Returns:
        str: The decoded string, or an empty string if decoding fails.
    """
    if not output_bytes:
        return ""

    encodings_to_try = [
        locale.getpreferredencoding(False), # System default
        "utf-8", # Very common
        "cp1252", # Windows Latin 1
        "latin1", # ISO 8859-1
        "cp866",  # Russian DOS
        "cp1251", # Windows Cyrillic
    ]
    # Add more encodings if needed based on target user base

    for enc in encodings_to_try:
        try:
            decoded_str = output_bytes.decode(enc, errors="replace")
            # Optional: Log success if it wasn't the first attempt
            # if enc != encodings_to_try[0]:
            #    logger.debug(f"Successfully decoded output using '{enc}'.")
            return decoded_str
        except UnicodeDecodeError:
            # logger.debug(f"Decoding failed with '{enc}'. Trying next...")
            continue
        except Exception as e:
            # Log unexpected decoding errors, but continue trying
            logger.warning(f"Unexpected error decoding subprocess output with '{enc}': {e}")
            continue

    logger.warning(f"Could not decode subprocess output after trying multiple encodings. Command: {command_str}")
    # Fallback: return raw representation or placeholder
    return output_bytes.decode('utf-8', errors='replace')


class ConfigManager:
    """Manages loading, saving, and accessing configuration settings."""

    def __init__(self):
        """Initializes the ConfigManager, determines paths, and loads config."""
        self.base_dir = self._get_base_directory()
        self.config_file_path = self.base_dir / CONFIG_FILE_NAME
        self.lua_control_file_path = self.base_dir / LUA_SCRIPT_FILE_NAME
        self.fbx_export_file_path = self.base_dir / FBX_FILE_NAME

        # Default values - these will be overridden by loaded config
        self.rizom_location = ""
        self.include_uvs = True
        self.pack_quality = 2  # Corresponds to "High" (index in dropdown)
        self.pack_iterations = 256

        self.ensure_storage_exists()
        self.load_or_create_config()

    def _get_base_directory(self):
        """Determines the base directory for settings and temporary files."""
        try:
            # Standard Maya scripts directory
            scripts_dir = Path(cmds.internalVar(userScriptDir=True))
            base_dir = scripts_dir / INSTALL_SUBDIR_NAME
            return base_dir
        except Exception as e:
            # Fallback if Maya's internal variable fails
            logger.error(
                f"Could not get Maya scripts dir via internalVar: {e}. Falling back."
            )
            fallback_base = (
                Path(os.path.expanduser("~"))
                / ".maya_rizom_bridge"
                / INSTALL_SUBDIR_NAME
            )
            logger.warning(f"Using fallback directory: {fallback_base}")
            return fallback_base

    def ensure_storage_exists(self):
        """Creates the base directory (e.g., RZMUV) if it doesn't exist."""
        if not self.base_dir.exists():
            try:
                self.base_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created settings directory: {self.base_dir}")
            except OSError as e:
                logger.error(
                    f"Failed to create settings directory {self.base_dir}: {e}"
                )
                # Potentially raise an error here if the directory is critical

    def load_or_create_config(self):
        """Loads config from JSON or creates a default one if missing/invalid."""
        if not self.config_file_path.is_file():
            logger.info(
                f"{CONFIG_FILE_NAME} not found. Creating default configuration."
            )
            self.set_initial_config()
            self.save_config() # Save the defaults immediately
        else:
            try:
                with open(self.config_file_path, "r", encoding='utf-8') as f:
                    config_data = json.load(f)

                # Load values, falling back to defaults if keys are missing
                self.rizom_location = config_data.get(
                    "rizomPath", self._get_default_rizom_path()
                )
                self.include_uvs = config_data.get("loadUVs", True)
                self.pack_quality = config_data.get("quality", 2)
                self.pack_iterations = config_data.get("mutations", 256)
                logger.info(f"Loaded configuration from {self.config_file_path}")

            except json.JSONDecodeError as e_json:
                logger.error(
                    f"Error decoding {self.config_file_path}: {e_json}. "
                    "Attempting backup and reset."
                )
                self._backup_and_reset_config("JSONDecodeError")
            except KeyError as e_key:
                logger.error(
                    f"Missing key in {self.config_file_path}: {e_key}. "
                    "Attempting backup and reset."
                )
                self._backup_and_reset_config("KeyError")
            except Exception as e:
                logger.error(
                    f"Unexpected error loading configuration: {e}. "
                    "Attempting backup and reset."
                )
                self._backup_and_reset_config(type(e).__name__)

    def _backup_and_reset_config(self, error_type="UnknownError"):
        """Backs up a corrupted config file and creates a new default one."""
        if self.config_file_path.is_file():
            backup_path = self.config_file_path.with_suffix(
                f".corrupt_{error_type}.bak"
            )
            try:
                # copy2 preserves more metadata than copy
                shutil.copy2(self.config_file_path, backup_path)
                logger.info(f"Backed up corrupted config to: {backup_path}")
            except Exception as e_bak:
                logger.error(f"Failed to backup corrupted config: {e_bak}")

        logger.warning("Resetting configuration to defaults due to loading error.")
        self.set_initial_config()
        self.save_config()

    def _get_default_rizom_path(self):
        """Gets the platform-specific default path for RizomUV."""
        system = platform.system()
        default_path = PATH_DEFAULTS.get(system, "") # Get OS specific default
        if not default_path:
             logger.warning(f"No default RizomUV path defined for OS: {system}. Please configure manually.")
             # Fallback to Windows path if system is unknown? Or leave empty?
             default_path = PATH_DEFAULTS.get("Windows", "") # Or just ""
        return default_path


    def set_initial_config(self):
        """Sets the configuration attributes to their default values."""
        self.rizom_location = self._get_default_rizom_path()
        self.include_uvs = True
        self.pack_quality = 2
        self.pack_iterations = 256
        logger.info("Set initial default configuration values.")

    def save_config(self):
        """Saves the current configuration state to the JSON file."""
        config_data = {
            "rizomPath": str(self.rizom_location), # Ensure Path is string
            "loadUVs": self.include_uvs,
            "quality": self.pack_quality,
            "mutations": self.pack_iterations,
        }
        try:
            # Ensure directory exists and is writable before attempting save
            self.ensure_storage_exists()
            if not self.base_dir.is_dir() or not os.access(str(self.base_dir), os.W_OK):
                logger.error(
                    f"Cannot write to directory: {self.base_dir}. Config not saved."
                )
                return False

            with open(self.config_file_path, "w", encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
            logger.info(f"Saved configuration to {self.config_file_path}")
            return True
        except IOError as e:
            logger.error(
                f"Failed to save configuration to {self.config_file_path}: {e}"
            )
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving configuration: {e}")
            return False

    def get_lua_script_path_str(self):
        """Returns the LUA script path as a string."""
        return str(self.lua_control_file_path)

    def get_fbx_export_path_str(self):
        """Returns the FBX export path as a string."""
        return str(self.fbx_export_file_path)


class UVBridgePanel(MayaQWidgetDockableMixin, QtWidgets.QWidget):
    """The main UI panel for the RizomUV Bridge tool."""

    # Unique object name for the UI instance
    UI_INSTANCE_NAME = "rizomUVBridgePanelInstance"

    def __init__(self, parent=None):
        """Initializes the UI panel."""
        super(UVBridgePanel, self).__init__(parent=parent)
        self.config = ConfigManager()

        self.setWindowTitle("RizomUV Bridge")
        self.setMinimumWidth(350) # Increased width slightly for better layout
        self.setObjectName(self.UI_INSTANCE_NAME) # Crucial for Maya UI management

        # --- UI State Variables ---
        # Initial values for settings not directly in config
        self.edge_angle_threshold = 45.1
        self.use_angle_tolerance = True

        # --- Build UI ---
        self.build_interface()
        self.setup_handlers()
        self.refresh_uv_options() # Populate dropdown initially

        logger.info("RizomUV Bridge Panel Initialized.")

    def build_interface(self):
        """Creates and lays out the UI widgets."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(8, 8, 8, 8) # Added slightly more margin

        # --- Settings Group ---
        settings_group = QtWidgets.QGroupBox("Settings")
        settings_layout = QtWidgets.QVBoxLayout()

        path_layout = QtWidgets.QHBoxLayout()
        path_layout.addWidget(QtWidgets.QLabel("RizomUV Path:"))
        self.location_input = QtWidgets.QLineEdit(str(self.config.rizom_location))
        self.location_input.setToolTip("Path to the RizomUV executable (e.g., .exe, .app)")
        path_layout.addWidget(self.location_input)
        self.browse_btn = QtWidgets.QPushButton("...") # Shorter label
        self.browse_btn.setFixedWidth(30)
        self.browse_btn.setToolTip("Browse for RizomUV executable/application")
        path_layout.addWidget(self.browse_btn)
        settings_layout.addLayout(path_layout)

        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        # --- Manual UV Transfer Group ---
        ops_group = QtWidgets.QGroupBox("Manual UV Transfer")
        ops_layout = QtWidgets.QVBoxLayout()

        self.uv_toggle = QtWidgets.QCheckBox("Send With Existing UVs")
        self.uv_toggle.setChecked(self.config.include_uvs)
        self.uv_toggle.setToolTip(
            "Include existing UV data from the selected 'Target/Source UV Set' below\n"
            "when sending geometry to RizomUV. If unchecked, geometry is sent without UVs."
        )
        ops_layout.addWidget(self.uv_toggle)

        self.transfer_btn = QtWidgets.QPushButton("Send Selection to RizomUV")
        self.transfer_btn.setToolTip(
            "Export selected geometry and launch/update RizomUV.\n"
            "Uses settings below (UV Set / Send With Existing UVs)."
        )
        ops_layout.addWidget(self.transfer_btn)

        separator_manual = QtWidgets.QFrame()
        separator_manual.setFrameShape(QtWidgets.QFrame.HLine)
        separator_manual.setFrameShadow(QtWidgets.QFrame.Sunken)
        ops_layout.addWidget(separator_manual)

        ops_layout.addWidget(QtWidgets.QLabel("Target/Source UV Set:"))
        self.uv_selector = QtWidgets.QComboBox()
        self.uv_selector.setToolTip(
            "Select the Maya UV set to use as source (when sending with UVs)\n"
            "and as the target for importing UVs back from RizomUV."
            )
        ops_layout.addWidget(self.uv_selector)

        self.retrieve_btn = QtWidgets.QPushButton("Get UVs from RizomUV")
        self.retrieve_btn.setToolTip(
            "Import UVs from the temporary bridge FBX file\n"
            "into the selected 'Target/Source UV Set' on the currently selected Maya objects."
        )
        ops_layout.addWidget(self.retrieve_btn)

        ops_group.setLayout(ops_layout)
        main_layout.addWidget(ops_group)

        # --- Rizom Actions Group ---
        auto_group = QtWidgets.QGroupBox("Rizom Actions (via Lua)")
        auto_layout = QtWidgets.QVBoxLayout()

        self.custom_lua_label = QtWidgets.QLabel("Custom Lua Script (Optional):")
        self.custom_lua_input = QtWidgets.QTextEdit()
        self.custom_lua_input.setPlaceholderText(
            "# Enter custom Rizom Lua commands here.\n"
            "# Runs *before* Auto Pack (if used).\n"
            "# Example: ZomSelect({PrimType='Edge', Select=true, Filter='Hard'})\n"
            "# Example: ZomCut({WorkingSet='VSSelection'})"
        )
        self.custom_lua_input.setAcceptRichText(False)
        self.custom_lua_input.setMinimumHeight(60)
        self.custom_lua_input.setMaximumHeight(150) # Limit vertical expansion
        auto_layout.addWidget(self.custom_lua_label)
        auto_layout.addWidget(self.custom_lua_input)

        self.run_custom_lua_btn = QtWidgets.QPushButton("Run Custom Lua Script")
        self.run_custom_lua_btn.setToolTip(
            "Send selection, launch RizomUV, set Target UV Set (if specific),\n"
            "run the custom Lua script above, then save the result in RizomUV.\n"
            "Use 'Get UVs' button afterwards to import the result into Maya."
        )
        auto_layout.addWidget(self.run_custom_lua_btn)

        separator_auto = QtWidgets.QFrame()
        separator_auto.setFrameShape(QtWidgets.QFrame.HLine)
        separator_auto.setFrameShadow(QtWidgets.QFrame.Sunken)
        auto_layout.addWidget(separator_auto)

        # Packing Options Layout
        pack_options_layout = QtWidgets.QHBoxLayout()
        pack_quality_layout = QtWidgets.QVBoxLayout()
        pack_quality_layout.addWidget(QtWidgets.QLabel("Packer Quality:"))
        self.quality_selector = QtWidgets.QComboBox()
        self.quality_selector.addItems(["Low (128)", "Normal (256)", "High (512)", "Higher (1024)", "Ultra (2048)"])
        self.quality_selector.setCurrentIndex(self.config.pack_quality)
        self.quality_selector.setToolTip(
            "Select packing quality/resolution for the Auto Pack action.\n"
            "Higher values take longer but yield better packing density."
        )
        pack_quality_layout.addWidget(self.quality_selector)
        pack_options_layout.addLayout(pack_quality_layout)

        pack_iter_layout = QtWidgets.QVBoxLayout()
        pack_iter_layout.addWidget(QtWidgets.QLabel("Packer Iterations:"))
        self.iterations_spinner = QtWidgets.QSpinBox()
        self.iterations_spinner.setRange(1, 2048) # Increased range slightly
        self.iterations_spinner.setValue(self.config.pack_iterations)
        self.iterations_spinner.setToolTip(
            "Number of packing iterations (mutations) for the Auto Pack action.\n"
            "More iterations can improve results but take significantly longer."
        )
        pack_iter_layout.addWidget(self.iterations_spinner)
        pack_options_layout.addLayout(pack_iter_layout)
        auto_layout.addLayout(pack_options_layout)


        self.auto_pack_btn = QtWidgets.QPushButton("Auto Pack Selected UV Set")
        self.auto_pack_btn.setToolTip(
            "Send selection, launch RizomUV, automatically pack the selected\n"
            "'Target/Source UV Set' (requires selecting a specific set, not 'All'),\n"
            "and save the result in RizomUV.\n"
            "Uses Packer Quality/Iterations settings above.\n"
            "Use 'Get UVs' button afterwards to import the result into Maya."
        )
        auto_layout.addWidget(self.auto_pack_btn)

        auto_group.setLayout(auto_layout)
        main_layout.addWidget(auto_group)

        # --- Post Process Group ---
        post_group = QtWidgets.QGroupBox("Post Process (Maya Normals)")
        post_layout = QtWidgets.QVBoxLayout()

        self.edge_hardener_btn = QtWidgets.QPushButton("Harden UV Shell Borders")
        self.edge_hardener_btn.setToolTip(
            "Process selected objects in Maya:\n"
            "1. Soften all edges.\n"
            "2. Harden edges along UV shell borders.\n"
            "3. Optionally re-soften based on angle tolerance below."
            )
        post_layout.addWidget(self.edge_hardener_btn)

        angle_tolerance_layout = QtWidgets.QHBoxLayout()
        self.tolerance_toggle = QtWidgets.QCheckBox("Use Angle Tolerance")
        self.tolerance_toggle.setChecked(self.use_angle_tolerance)
        self.tolerance_toggle.setToolTip(
             "If checked, after hardening UV borders,\n"
             "soften edges again based on the angle threshold.\n"
             "If unchecked, only UV borders remain hard.")
        angle_tolerance_layout.addWidget(self.tolerance_toggle)

        angle_layout = QtWidgets.QHBoxLayout()
        angle_layout.addWidget(QtWidgets.QLabel("Tolerance Angle:"))
        self.angle_adjuster = QtWidgets.QDoubleSpinBox()
        self.angle_adjuster.setRange(0.1, 179.9)
        self.angle_adjuster.setValue(self.edge_angle_threshold)
        self.angle_adjuster.setSingleStep(0.1)
        self.angle_adjuster.setDecimals(1)
        self.angle_adjuster.setToolTip("Angle threshold for the final softening pass (if enabled)")
        angle_layout.addWidget(self.angle_adjuster)
        angle_tolerance_layout.addLayout(angle_layout)
        post_layout.addLayout(angle_tolerance_layout)


        post_group.setLayout(post_layout)
        main_layout.addWidget(post_group)

        # --- Feedback Label & Bottom Row ---
        self.feedback_label = QtWidgets.QLabel("Ready")
        self.feedback_label.setAlignment(QtCore.Qt.AlignCenter)
        self.feedback_label.setWordWrap(True) # Allow wrapping for longer messages
        main_layout.addWidget(self.feedback_label) # Keep feedback above debug

        main_layout.addStretch() # Add stretch before the bottom row

        # Bottom row layout for debug button
        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0) # No extra margins

        # Spacer to push button to the right
        spacer = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        bottom_layout.addSpacerItem(spacer)

        # Debug Toggle Button
        self.debug_toggle_btn = QtWidgets.QPushButton("🐞") # Using an emoji
        self.debug_toggle_btn.setFlat(True) # Make it less prominent
        self.debug_toggle_btn.setToolTip("Toggle Verbose Logging (INFO/DEBUG vs ERROR)")
        self.debug_toggle_btn.setFixedSize(25, 25) # Make it small and square

        # Set initial appearance based on logger's actual starting level
        self._update_debug_button_appearance()

        bottom_layout.addWidget(self.debug_toggle_btn) # Add button to bottom layout
        main_layout.addLayout(bottom_layout) # Add bottom layout to main layout

    def setup_handlers(self):
        """Connects UI element signals to their corresponding methods."""
        # Settings Group
        self.browse_btn.clicked.connect(self.locate_rizom)
        self.location_input.editingFinished.connect(self.persist_config) # Save when focus lost

        # Manual Transfer Group
        self.transfer_btn.clicked.connect(self.dispatch_manual_send)
        self.retrieve_btn.clicked.connect(self.fetch_from_rizom)
        self.uv_toggle.stateChanged.connect(self.persist_config)
        self.uv_selector.currentIndexChanged.connect(self.handle_uv_set_change) # Added handler

        # Rizom Actions Group
        self.run_custom_lua_btn.clicked.connect(self.dispatch_custom_lua)
        self.auto_pack_btn.clicked.connect(self.dispatch_auto_pack)
        self.quality_selector.currentIndexChanged.connect(self.persist_config)
        self.iterations_spinner.valueChanged.connect(self.persist_config)

        # Post Process Group
        self.edge_hardener_btn.clicked.connect(self.process_uv_edges)
        self.tolerance_toggle.stateChanged.connect(self.toggle_tolerance)
        self.angle_adjuster.valueChanged.connect(self.adjust_angle)

        # Debug Toggle Button
        self.debug_toggle_btn.clicked.connect(self.toggle_debug_logging)

        # UV Set Dropdown Update on Selection Change (ScriptJob)
        # The `parent` flag is crucial for automatic cleanup when the UI is closed.
        try:
            # Kill existing jobs parented to this UI first, just in case
            # This is a safety measure if the parent flag fails somehow during reloads
            existing_jobs = cmds.scriptJob(listJobs=True)
            for job in existing_jobs:
                if f"parent='{self.objectName()}'" in job:
                    try:
                        job_num = int(job.split(":")[0])
                        logger.debug(f"Killing previous scriptJob: {job_num}")
                        cmds.scriptJob(kill=job_num, force=True)
                    except (ValueError, RuntimeError) as e_kill:
                        logger.warning(f"Could not kill previous scriptJob '{job}': {e_kill}")

            # Create the new job
            new_job_num = cmds.scriptJob(
                event=["SelectionChanged", self.refresh_uv_options],
                parent=self.objectName(), # Auto-cleanup with UI deletion
                protected=True # Prevents accidental deletion by user scriptJob management
            )
            logger.debug(f"Created SelectionChanged scriptJob: {new_job_num} parented to {self.objectName()}")

        except Exception as e_sj:
            logger.error(f"Failed to create SelectionChanged scriptJob: {e_sj}", exc_info=True)

    def handle_uv_set_change(self):
        """Logs the UV set change and potentially updates related UI elements."""
        current_set = self.uv_selector.currentText()
        logger.debug(f"Target/Source UV Set changed to: {current_set}")
        # Add any logic here that needs to react to the UV set changing,
        # e.g., enabling/disabling buttons if "All UV Sets" is selected.
        is_specific_set = current_set != "All UV Sets"
        self.auto_pack_btn.setEnabled(is_specific_set)
        self.auto_pack_btn.setToolTip(
            "Send selection, launch RizomUV, automatically pack the selected\n"
            "'Target/Source UV Set' (requires selecting a specific set, not 'All'),\n"
            "and save the result in RizomUV.\n"
            "Uses Packer Quality/Iterations settings above.\n"
            "Use 'Get UVs' button afterwards to import the result into Maya."
            + ("" if is_specific_set else "\n\n**Disabled: Select a specific UV set.**")
        )


    def _update_debug_button_appearance(self):
        """Sets the debug button style based on the current logging level."""
        # Use INFO as the threshold for "verbose" logging
        is_verbose = logger.level <= logging.INFO
        # Simple visual cue: more opaque when verbose, less when not
        opacity = "1.0" if is_verbose else "0.4"
        # Use style sheet for subtle visual change
        self.debug_toggle_btn.setStyleSheet(f"QPushButton {{ color: white; background-color: rgba(80, 80, 80, {opacity}); border: none; }}")
        # Update tooltip to reflect current state
        tooltip_state = "ON (INFO/DEBUG)" if is_verbose else "OFF (ERROR Only)"
        self.debug_toggle_btn.setToolTip(f"Verbose Logging is {tooltip_state}.\nClick to toggle.")


    def toggle_debug_logging(self):
        """Toggles the logger level between INFO and ERROR."""
        # Use the logger instance defined at the module level
        global logger
        current_level = logger.level

        # Use INFO as the threshold for "verbose"
        if current_level <= logging.INFO:
            # If currently INFO or lower (verbose), switch to ERROR (not verbose)
            new_level = logging.ERROR
            # Log *before* changing level so this message is seen
            logger.info("Switching logging level to ERROR (less verbose)")
            logger.setLevel(new_level)
        else:
            # If currently ERROR or higher (not verbose), switch to INFO (verbose)
            new_level = logging.INFO
            # Log *before* changing level (will appear as ERROR level log)
            logger.error("Switching logging level to INFO (more verbose)")
            logger.setLevel(new_level)
            logger.info("Logging level is now INFO") # Confirmation message

        logger.info(f"Logger level set to: {logging.getLevelName(new_level)}")
        self._update_debug_button_appearance() # Update button visuals


    # --- Dispatcher Methods ---

    def dispatch_manual_send(self):
        """Exports selection and launches RizomUV without running extra scripts or packing."""
        logger.info("Dispatching: Manual Send to RizomUV")
        self._dispatch_to_rizom(run_custom_script=False, pack_after=False)

    def dispatch_custom_lua(self):
        """Exports selection, sets target UV set (if specific), runs custom Lua, and launches RizomUV."""
        logger.info("Dispatching: Run Custom Lua Script in RizomUV")
        self._dispatch_to_rizom(run_custom_script=True, pack_after=False)

    def dispatch_auto_pack(self):
        """Exports selection, sets target UV set (requires specific), runs packing, and launches RizomUV."""
        logger.info("Dispatching: Auto Pack UV Set in RizomUV")
        chosen_uv_set = self.uv_selector.currentText()
        if chosen_uv_set == "All UV Sets":
            self.set_feedback(
                "Error: Auto Pack requires a specific Target UV Set.", level="error"
            )
            logger.error("Auto Pack requires a specific UV set, not 'All UV Sets'.")
            return
        self._dispatch_to_rizom(run_custom_script=False, pack_after=True)

    # --- Core Logic Methods ---

    def _dispatch_to_rizom(self, run_custom_script=False, pack_after=False):
        """
        Core logic to export mesh, generate Lua script, and launch RizomUV.

        Args:
            run_custom_script (bool): If True, include custom Lua script from UI.
            pack_after (bool): If True, append standard packing Lua commands.
        """
        self.set_feedback("Preparing to send to RizomUV...", level="info")
        cmds.refresh() # Give Maya a moment to update UI

        selected_items = cmds.ls(selection=True, long=True, type="transform")
        if not selected_items:
            self.set_feedback("Error: No transform objects selected.", level="error")
            logger.error("No transform objects selected for dispatch.")
            return

        # --- Get Paths and Settings ---
        rizom_path_str = str(self.config.rizom_location)
        fbx_export_path_str = self.config.get_fbx_export_path_str()
        lua_script_path_str = self.config.get_lua_script_path_str()

        if not Path(rizom_path_str).exists():
            self.set_feedback(
                f"Error: RizomUV path not found: {rizom_path_str}", level="error"
            )
            logger.error(f"RizomUV executable/app not found at: {rizom_path_str}")
            # Consider calling self.locate_rizom() here?
            return

        use_existing_uvs = self.uv_toggle.isChecked()
        chosen_uv_set = self.uv_selector.currentText()
        is_specific_set_selected = chosen_uv_set != "All UV Sets"

        # --- Validate Action Requirements ---
        if pack_after and not is_specific_set_selected:
            # This case should ideally be prevented by disabling the button,
            # but double-check here.
            self.set_feedback(
                "Error: Auto Pack requires a specific Target UV Set.", level="error"
            )
            logger.error(
                "Internal Error: _dispatch_to_rizom called for packing "
                "with 'All UV Sets' selected."
            )
            return

        # --- Ensure FBX Plugin ---
        if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
            try:
                cmds.loadPlugin("fbxmaya")
                logger.info("Loaded fbxmaya plugin.")
            except Exception as e:
                self.set_feedback("Error: Failed to load FBX plugin.", level="error")
                logger.error(f"Failed to load fbxmaya plugin: {e}")
                return

        # --- Prepare Maya Scene for Export ---
        cmds.select(selected_items, replace=True) # Ensure only desired items are selected

        # Determine the UV set to make active for FBX export
        # FBX exporter typically exports the *currently active* UV set per object.
        active_uv_set_for_export = "map1" # Default fallback
        if use_existing_uvs and is_specific_set_selected:
            active_uv_set_for_export = chosen_uv_set
            logger.info(f"Attempting to export with UV set: {active_uv_set_for_export}")
        elif use_existing_uvs: # "All UV Sets" selected
             logger.info("Exporting with UVs, but 'All UV Sets' selected. FBX will likely use 'map1' or current active set per object.")
             # Keep active_uv_set_for_export as 'map1' or don't explicitly set it.
             # Rizom will load whatever FBX provides.
        else: # Not sending UVs
             logger.info("Exporting without UVs.")
             # Ensure 'map1' is active just so FBX export doesn't potentially fail if no sets exist?
             # Rizom will ignore them anyway based on load flags below.

        # Set the current UV set on each selected mesh shape
        # This influences which UVs the FBX exporter writes by default
        for item in selected_items:
            shapes = cmds.listRelatives(item, shapes=True, fullPath=True, noIntermediate=True, type="mesh") or []
            if shapes:
                shape = shapes[0]
                try:
                    all_sets = cmds.polyUVSet(shape, query=True, allUVSets=True) or []
                    target_set = active_uv_set_for_export if (use_existing_uvs and is_specific_set_selected) else "map1"

                    if target_set in all_sets:
                        cmds.polyUVSet(shape, currentUVSet=True, uvSet=target_set)
                        logger.debug(f"Set current UV set to '{target_set}' on {shape} for export.")
                    elif "map1" in all_sets:
                         cmds.polyUVSet(shape, currentUVSet=True, uvSet="map1")
                         logger.debug(f"Target UV set '{target_set}' not found on {shape}, set current to 'map1'.")
                    elif all_sets:
                         # Set current to the first available set if map1 isn't there
                         first_set = all_sets[0]
                         cmds.polyUVSet(shape, currentUVSet=True, uvSet=first_set)
                         logger.debug(f"Target/map1 UV sets not found on {shape}, set current to '{first_set}'.")
                    else:
                         logger.warning(f"No UV sets found on {shape}. FBX export might behave unexpectedly regarding UVs.")

                except Exception as e_setuv:
                    logger.warning(f"Could not query/set UV set on {shape}: {e_setuv}")


        # Warn about constraints
        constraint_nodes = cmds.listConnections(selected_items, type="constraint")
        if constraint_nodes:
            logger.warning(f"Selection contains constraints: {list(set(constraint_nodes))}. "
                           "Geometry position might differ in RizomUV unless baked.")

        # --- Export FBX ---
        try:
            # Set common FBX export options
            mel.eval("FBXExportSmoothingGroups -v true;")
            mel.eval("FBXExportHardEdges -v false;") # Rely on smoothing groups
            mel.eval("FBXExportTangents -v false;") # Rizom usually recalculates
            mel.eval("FBXExportInstances -v false;") # Avoid issues with instances
            mel.eval("FBXExportReferencedAssetsContent -v false;")
            mel.eval("FBXExportTriangulate -v false;") # Keep quads/ngons if possible
            mel.eval("FBXExportSmoothMesh -v false;") # Export base mesh
            mel.eval("FBXExportConstraints -v false;") # Don't export constraints
            mel.eval("FBXExportCameras -v false;")
            mel.eval("FBXExportLights -v false;")
            mel.eval("FBXExportAnimationOnly -v false;")
            mel.eval("FBXExportBakeComplexAnimation -v false;")
            mel.eval("FBXExportUpAxis y;") # Standard Maya up-axis

            # Ensure target directory exists
            Path(fbx_export_path_str).parent.mkdir(parents=True, exist_ok=True)

            cmds.file(
                fbx_export_path_str,
                force=True,           # Overwrite existing file
                options="v=0;",       # Suppress FBX exporter dialog options
                type="FBX export",
                preserveReferences=False,
                exportSelected=True   # Export only the selection
            )
            logger.info(f"Exported selection to: {fbx_export_path_str}")
        except Exception as e:
            self.set_feedback(f"Error during FBX export: {e}", level="error")
            logger.error("FBX Export failed.", exc_info=True)
            return

        # --- Generate Lua Script ---
        lua_fbx_path = fbx_export_path_str.replace("\\", "/") # Lua needs forward slashes
        lua_script_parts = ["-- RizomUV Bridge Lua Script --"]

        # Load Command
        load_flags = "XYZ=true" # Always load geometry
        if use_existing_uvs:
            # Load UVs and potentially properties like selection sets, groups
            load_flags = "XYZUVW=true, UVWProps=true"
            logger.debug("Lua: Including UVW load flags.")
        else:
             logger.debug("Lua: Excluding UVW load flags.")

        load_cmd_str = (
            f'ZomLoad({{File={{Path="{lua_fbx_path}", ImportGroups=true, {load_flags}}}, '
            f'NormalizeUVW=false}})' # Keep original UV scale
        )
        lua_script_parts.append(load_cmd_str)

        # Set Current UV Set in Rizom (only matters if doing actions like pack/custom script)
        if is_specific_set_selected and (run_custom_script or pack_after):
            lua_script_parts.append(f'-- Setting target UV set for subsequent operations')
            lua_script_parts.append(
                f'ZomUvset({{Mode="SetCurrent", Name="{chosen_uv_set}"}})'
            )
            logger.info(f"Lua: Setting RizomUV current UV set to: {chosen_uv_set}")
        else:
            lua_script_parts.append(
                f'-- Using RizomUV default/current UV set (Maya selection was: {chosen_uv_set})'
            )

        # Custom Lua Script Insertion
        if run_custom_script:
            lua_script_parts.append("")
            lua_script_parts.append("-- Running Custom Lua Script --")
            custom_script = self.custom_lua_input.toPlainText().strip()
            if custom_script:
                lua_script_parts.append(custom_script)
                logger.info("Lua: Adding custom script content.")
            else:
                lua_script_parts.append("-- (Custom script field was empty) --")
                logger.info("Lua: Custom script field is empty, skipping.")
            lua_script_parts.append("-- End Custom Lua Script --")
            lua_script_parts.append("")


        # Auto Pack Commands
        if pack_after:
            # Ensure we are operating on the correct UV set (already set above if specific)
            lua_script_parts.append("")
            lua_script_parts.append(f"-- Running Auto Pack on UV Set: {chosen_uv_set} --")

            # Map UI quality index to Rizom resolution parameter
            quality_levels = {0: 128, 1: 256, 2: 512, 3: 1024, 4: 2048} # Low to Ultra
            pack_res = quality_levels.get(self.config.pack_quality, 512) # Default to High if index out of range
            pack_iter = self.config.pack_iterations

            # Standard Packing Sequence (adjust if needed based on desired Rizom workflow)
            # 1. Distribute islands into tiles based on bounding box (basic layout)
            lua_script_parts.append(
                f'ZomIslandGroups({{Mode="DistributeInTilesByBBox", WorkingSet="Visible", MergingPolicy=8322}})' # Policy 8322: Group per island
            )
            # 2. Refine distribution evenly, respecting locks
            lua_script_parts.append(
                f'ZomIslandGroups({{Mode="DistributeInTilesEvenly", WorkingSet="Visible", MergingPolicy=8322, UseTileLocks=true, UseIslandLocks=true}})'
            )
            # 3. Perform the main packing operation
            lua_script_parts.append(
                f'ZomPack({{ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", WorkingSet="Visible", '
                f'Scaling={{Mode=2}}, ' # Mode 2: Average texel density scaling
                f'Rotate={{Enable=true, Mode=1, Step=90.0}}, ' # Allow 90-degree rotations
                f'Translate=true, LayoutScalingMode=2, '
                f'MaxMutations={pack_iter}, Resolution={pack_res}}})'
            )
            logger.info(
                f"Lua: Adding packing commands with QualityRes={pack_res}, Iterations={pack_iter}"
            )
            lua_script_parts.append("-- End Auto Pack --")
            lua_script_parts.append("")


        # Save Command (always include to save the result for retrieval)
        lua_script_parts.append("-- Saving Result --")
        # Ensure UV properties (like selection sets mapped to UVs) are saved back
        lua_script_parts.append(
            f'ZomSave({{File={{Path="{lua_fbx_path}", UVWProps=true}}, '
            f'__UpdateUIObjFileName=true}})' # Updates Rizom UI title bar
        )

        lua_script = "\n".join(lua_script_parts)

        # --- Write Lua Script File ---
        try:
            # Ensure directory exists
            Path(lua_script_path_str).parent.mkdir(parents=True, exist_ok=True)
            with open(lua_script_path_str, "w", encoding="utf-8") as f:
                f.write(lua_script)
            logger.info(f"Generated Lua script: {lua_script_path_str}")
            logger.debug(f"Lua Script Content:\n------\n{lua_script}\n------")
        except IOError as e:
            self.set_feedback(f"Error writing Lua script: {e}", level="error")
            logger.error("Failed writing Lua script.", exc_info=True)
            return

        # --- Launch RizomUV ---
        process_description = (
            "custom script" if run_custom_script else
            "auto pack" if pack_after else
            "manual send"
        )
        self.set_feedback(f"Launching RizomUV for {process_description}...", level="info")
        logger.info(f"Executing RizomUV process for: {process_description}")

        system = platform.system()
        cmd = []
        cmd_str = "" # For logging the command

        try:
            if system == "Windows":
                # Standard windows execution
                cmd = [rizom_path_str, "-cfi", lua_script_path_str]
                # Optional: Add "-nogui" if you want headless execution for automated tasks
            elif system == "Darwin": # macOS
                 # Use 'open -a' for .app bundles
                cmd = [
                    "open",
                    "-a", rizom_path_str, # Path to the .app directory
                    "--args",             # Pass arguments after this flag
                    "-cfi", lua_script_path_str
                ]
            else: # Linux / Other Unix-like
                # Assume rizom_path_str is the executable
                cmd = [rizom_path_str, "-cfi", lua_script_path_str]

            # Log the command being executed
            cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd) # Quote parts with spaces
            logger.info(f"Running command: {cmd_str}")

            # Use Popen for non-blocking execution (RizomUV GUI will open)
            # Capture stdout/stderr to check for immediate errors
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # Potentially add startupinfo for Windows to hide console window if needed
                # startupinfo=subprocess.STARTUPINFO(wShowWindow=subprocess.SW_HIDE) # Example
            )

            # Check process status briefly, but don't wait indefinitely
            try:
                # Wait for a short time (e.g., 5 seconds) to see if it exits immediately
                stdout, stderr = process.communicate(timeout=5)
                return_code = process.returncode

                # Decode output safely
                stdout_decoded = safe_decode_subprocess(stdout, cmd_str)
                stderr_decoded = safe_decode_subprocess(stderr, cmd_str)

                if return_code != 0:
                    # RizomUV exited quickly with an error
                    logger.warning(f"RizomUV process exited quickly with code {return_code}.")
                    if stdout_decoded: logger.warning(f"Rizom stdout:\n{stdout_decoded}")
                    if stderr_decoded: logger.error(f"Rizom stderr:\n{stderr_decoded}")
                    self.set_feedback(f"RizomUV exited with error (code {return_code}). Check logs.", level="error")
                else:
                    # RizomUV might have finished a headless task or just started GUI
                    logger.info("RizomUV process executed/exited cleanly or detached.")
                    if stdout_decoded: logger.info(f"Rizom stdout:\n{stdout_decoded}")
                    if stderr_decoded: logger.info(f"Rizom stderr:\n{stderr_decoded}")
                    # Small delay to allow Rizom GUI to fully initialize if needed
                    # cmds.pause(seconds=1.5) # Use pause instead of time.sleep in Maya main thread
                    self.set_feedback("RizomUV launched / script sent.", level="info")

            except subprocess.TimeoutExpired:
                # Process is still running, likely the GUI opened successfully
                logger.info("RizomUV process likely running in background (GUI mode).")
                self.set_feedback("RizomUV launched / script sent.", level="info")
                # Can optionally store process handle if needed: self.rizom_process = process

        except (subprocess.SubprocessError, FileNotFoundError) as e:
            self.set_feedback(f"Failed to start RizomUV: {e}", level="error")
            logger.error(f"Failed to execute command: {cmd_str}", exc_info=True)
            return
        except Exception as e:
             self.set_feedback(f"Unexpected error launching RizomUV: {e}", level="error")
             logger.error(f"Unexpected error launching RizomUV. Command: {cmd_str}", exc_info=True)
             return


        # --- Final Feedback ---
        if run_custom_script:
            self.set_feedback(
                "Sent to RizomUV for custom script. Use 'Get UVs' when done.",
                level="info",
            )
        elif pack_after:
            self.set_feedback(
                f"Sent to RizomUV for auto pack on '{chosen_uv_set}'. Use 'Get UVs' when done.",
                level="info",
            )
        else: # Manual send
            self.set_feedback("Sent selection to RizomUV. Use 'Get UVs' when done.", level="info")


    def locate_rizom(self):
        """Opens a file dialog for the user to locate the RizomUV executable/app."""
        original_os_native_dialog_pref = 0
        system = platform.system()
        mac_pref_changed = False

        # Determine starting directory for the dialog
        current_path_str = str(self.config.rizom_location)
        start_dir = ""
        if current_path_str:
            current_path = Path(current_path_str)
            if current_path.exists():
                start_dir = str(current_path.parent)
            elif current_path.parent.exists():
                 start_dir = str(current_path.parent)

        if not start_dir: # Fallback if current path is invalid/unset
            if system == "Darwin":
                start_dir = "/Applications" if Path("/Applications").exists() else "/"
            elif system == "Windows":
                program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
                start_dir = program_files if Path(program_files).exists() else "C:\\"
            else: # Linux
                start_dir = "/opt" if Path("/opt").exists() else "/" # Common install location

        logger.debug(f"Opening file dialog starting at: {start_dir}")

        selected_path_str = ""
        try:
            if system == "Darwin":
                # macOS .app bundles are directories, need native dialog
                try:
                    # Temporarily enable OS native dialog if disabled
                    original_os_native_dialog_pref = cmds.optionVar(query="useOSNativeFileDialog")
                    if original_os_native_dialog_pref == 0:
                        logger.info("Temporarily switching Maya to OS Native file dialog for .app selection.")
                        cmds.optionVar(iv=("useOSNativeFileDialog", 1))
                        mac_pref_changed = True
                except Exception as e:
                    logger.warning(f"Could not query/set OS native dialog preference: {e}")

                # Use getExistingDirectory for .app selection
                # Note: QFileDialog returns a tuple (path, filter) sometimes, sometimes just path.
                path_result = QtWidgets.QFileDialog.getExistingDirectory(
                    self,
                    "Locate RizomUV Application (.app)",
                    start_dir,
                    QtWidgets.QFileDialog.Option.ShowDirsOnly | QtWidgets.QFileDialog.Option.DontResolveSymlinks,
                )
                selected_path_str = path_result # QFileDialog on Mac seems to return string directly here

            else: # Windows or Linux
                if system == "Windows":
                    file_filter = "Executables (*.exe);;All Files (*)"
                else: # Linux
                    file_filter = "Executables (*);;All Files (*)" # Adjust filter if needed

                # Use getOpenFileName for selecting files
                path_tuple = QtWidgets.QFileDialog.getOpenFileName(
                    self, "Locate RizomUV Executable", start_dir, file_filter
                )
                # getOpenFileName returns a tuple (filePath, selectedFilter)
                selected_path_str = path_tuple[0] if isinstance(path_tuple, tuple) else path_tuple

            # --- Validate Selection ---
            if selected_path_str:
                selected_path = Path(selected_path_str)
                is_valid = False
                expected_exe_name = "RizomUV" # Common name inside .app/Contents/MacOS

                if system == "Darwin" and selected_path.is_dir() and selected_path.suffix == ".app":
                    # Check if the common executable exists inside the .app bundle
                    potential_exe = selected_path / "Contents" / "MacOS" / expected_exe_name
                    if potential_exe.is_file() and os.access(str(potential_exe), os.X_OK):
                        is_valid = True
                        logger.info(f"Validated .app bundle structure: {selected_path}")
                    else:
                         # Accept .app path even if internal structure is non-standard
                        logger.warning(f"Could not find standard '{expected_exe_name}' inside {selected_path}. Still accepting .app path.")
                        is_valid = True # Accept the .app path directly
                elif system == "Windows" and selected_path.is_file() and selected_path.suffix.lower() == ".exe":
                    is_valid = True
                elif system == "Linux" and selected_path.is_file() and os.access(str(selected_path), os.X_OK):
                     is_valid = True

                if is_valid:
                    self.config.rizom_location = str(selected_path)
                    self.location_input.setText(str(selected_path))
                    if self.config.save_config():
                        logger.info(f"RizomUV path set and saved: {selected_path}")
                        self.set_feedback("RizomUV path updated.", level="info")
                    else:
                        logger.error("Failed to save the new RizomUV path to configuration.")
                        self.set_feedback("Error: Failed to save new RizomUV path.", level="error")
                else:
                    logger.warning(f"Selected path does not appear valid for {system}: {selected_path}")
                    cmds.warning(f"Selected path may be invalid for {system}: {selected_path}")
                    self.set_feedback("Warning: Selected path may be invalid.", level="warning")
            else:
                 logger.info("File dialog cancelled by user.")
                 self.set_feedback("Ready", level="info") # Reset feedback

        except Exception as e:
            logger.error(f"Error during file dialog or path processing: {e}", exc_info=True)
            self.set_feedback("Error during file browse.", level="error")
        finally:
            # Restore Maya preference if it was changed on Mac
            if mac_pref_changed:
                try:
                    logger.info(f"Restoring Maya file dialog preference to: {original_os_native_dialog_pref}")
                    cmds.optionVar(iv=("useOSNativeFileDialog", original_os_native_dialog_pref))
                except Exception as e:
                    logger.warning(f"Could not restore OS native dialog preference: {e}")

    def refresh_uv_options(self):
        """Updates the UV set dropdown based on the current Maya selection."""
        logger.debug("Refreshing UV set options...")
        # Store current selection to try and restore it
        current_choice = self.uv_selector.currentText() if self.uv_selector.count() > 0 else ""

        self.uv_selector.blockSignals(True) # Prevent firing change signal during update
        self.uv_selector.clear()

        sel_transforms = cmds.ls(sl=True, type="transform", long=True) or []
        options = ["All UV Sets"] # Always have this option
        unique_sets = set()

        if sel_transforms:
            logger.debug(f"Checking UV sets on {len(sel_transforms)} selected transform(s).")
            for transform_node in sel_transforms:
                # Find mesh shapes under the transform
                shapes = cmds.listRelatives(
                    transform_node,
                    shapes=True,
                    type="mesh",
                    fullPath=True,
                    noIntermediate=True, # Ignore intermediate shapes
                ) or []

                if not shapes:
                    logger.debug(f"No mesh shape found for {transform_node}")
                    continue

                # Typically only process the first shape found
                shape_node = shapes[0]
                try:
                    uv_sets_on_shape = cmds.polyUVSet(shape_node, query=True, allUVSets=True)
                    if uv_sets_on_shape:
                        logger.debug(f"Found UV sets on {shape_node}: {uv_sets_on_shape}")
                        unique_sets.update(uv_sets_on_shape)
                    else:
                        # If polyUVSet returns None or empty list, assume default 'map1' might exist implicitly
                        logger.debug(f"No explicit UV sets returned for {shape_node}. Assuming 'map1' might exist.")
                        # Check if a current set exists; if not, add map1 as potential default
                        current_set = cmds.polyUVSet(shape_node, query=True, currentUVSet=True)
                        if not current_set:
                            unique_sets.add("map1") # Assume default exists if none reported

                except Exception as e:
                    logger.warning(f"Could not query UV sets for shape {shape_node}: {e}")
                    # Add 'map1' as a fallback if query fails
                    unique_sets.add("map1")
        else:
            logger.debug("No transforms selected, adding default 'map1' to options.")
            unique_sets.add("map1") # Ensure map1 is available if nothing is selected

        # Add the unique sets found, sorted alphabetically
        if unique_sets:
            options.extend(sorted(list(unique_sets)))

        # Remove duplicates (although using a set should prevent this, belt-and-suspenders)
        final_options = []
        seen = set()
        for item in options:
            if item not in seen:
                final_options.append(item)
                seen.add(item)

        # Populate the dropdown
        logger.debug(f"Populating UV selector with: {final_options}")
        self.uv_selector.addItems(final_options)

        # Try to restore previous selection or set a sensible default
        if current_choice in final_options:
            self.uv_selector.setCurrentText(current_choice)
        elif "map1" in final_options:
            self.uv_selector.setCurrentText("map1")
        elif len(final_options) > 1: # If map1 not present, select the first specific set
            self.uv_selector.setCurrentIndex(1)
        else: # Only "All UV Sets" available (or error)
            self.uv_selector.setCurrentIndex(0)

        self.uv_selector.blockSignals(False) # Re-enable signals
        self.handle_uv_set_change() # Update button states based on final selection


    def persist_config(self):
        """Saves the current UI settings to the configuration file."""
        logger.debug("Persisting config changes...")
        self.config.include_uvs = self.uv_toggle.isChecked()
        self.config.rizom_location = self.location_input.text() # Get text directly
        self.config.pack_quality = self.quality_selector.currentIndex()
        self.config.pack_iterations = self.iterations_spinner.value()

        if not self.config.save_config():
            # Log warning, but don't necessarily show error to user unless critical
            logger.warning("Persist config: Failed to save configuration changes.")
            # Optionally: self.set_feedback("Warning: Could not save settings.", level="warning")


    def set_feedback(self, message, level="info"):
        """Updates the feedback label and logs the message."""
        # Truncate long messages for the label if necessary
        display_message = (message[:100] + '...') if len(message) > 103 else message
        self.feedback_label.setText(display_message)

        # Set text color based on level
        if level == "info":
            logger.info(message)
            # Reset to default style (adapts to Maya theme)
            self.feedback_label.setStyleSheet("")
        elif level == "warning":
            logger.warning(message)
            self.feedback_label.setStyleSheet("QLabel { color : orange; }")
        elif level == "error":
            logger.error(message)
            self.feedback_label.setStyleSheet("QLabel { color : red; }")
        else: # Debug or other levels
             logger.debug(message)
             self.feedback_label.setStyleSheet("") # Default style

        # Ensure UI updates immediately
        QtWidgets.QApplication.processEvents()


    def fetch_from_rizom(self):
        """Imports UVs from the bridge FBX file back into Maya selection."""
        self.set_feedback("Attempting to import UVs from Rizom...", level="info")
        cmds.refresh()

        # Get currently selected objects in Maya (these are the targets)
        target_objects = cmds.ls(selection=True, long=True, type="transform")
        if not target_objects:
            self.set_feedback(
                "Error: No target objects selected in Maya for UV import.", level="error"
            )
            logger.error("No target objects selected for fetch_from_rizom.")
            return

        # Get the path to the FBX file Rizom should have saved
        fbx_source_path_str = self.config.get_fbx_export_path_str()
        fbx_source_path = Path(fbx_source_path_str)

        # Check if the source FBX file exists
        if not fbx_source_path.is_file():
            self.set_feedback(
                f"Error: Source FBX file not found: {fbx_source_path.name}",
                level="error",
            )
            logger.error(
                f"Cannot find FBX file to import UVs from: {fbx_source_path_str}"
            )
            return

        target_uv_set_name = self.uv_selector.currentText()
        logger.info(
            f"Attempting to import from: {fbx_source_path_str} "
            f"to UV set: '{target_uv_set_name}' on {len(target_objects)} object(s)."
        )

        # --- Namespace Management ---
        # Use a temporary namespace to avoid conflicts during import
        import_namespace = "RIZOMUV_TEMP_NS"
        if cmds.namespace(exists=import_namespace):
            logger.warning(f"Removing existing temporary namespace: {import_namespace}")
            try:
                # Force remove namespace and its contents
                cmds.namespace(removeNamespace=import_namespace, mergeNamespaceWithRoot=False)
                logger.info(f"Removed existing namespace and contents: {import_namespace}")
            except RuntimeError as e_rem_ns:
                 # If removal fails (e.g., contains referenced nodes), delete contents first
                logger.warning(f"Direct namespace removal failed: {e_rem_ns}. Attempting content deletion...")
                try:
                    ns_content = cmds.ls(f"{import_namespace}:*", long=True)
                    if ns_content:
                        logger.info(f"Deleting content of namespace {import_namespace}: {ns_content}")
                        cmds.delete(ns_content)
                    # Try removing the now-empty namespace again
                    cmds.namespace(setNamespace=":") # Go to root namespace
                    cmds.namespace(removeNamespace=import_namespace)
                    logger.info(f"Successfully removed namespace {import_namespace} after deleting contents.")
                except Exception as e_del_cont:
                    logger.error(f"Failed cleanup of namespace {import_namespace} contents: {e_del_cont}")
                    # Might need to abort if cleanup fails


        # --- Ensure FBX Plugin ---
        if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
            try:
                cmds.loadPlugin("fbxmaya")
                logger.info("Loaded fbxmaya plugin for import.")
            except Exception as e:
                self.set_feedback("Error: Failed to load FBX plugin for import.", level="error")
                logger.error(f"Failed to load fbxmaya plugin: {e}")
                return

        # --- Import FBX into Temporary Namespace ---
        imported_nodes = []
        try:
            # Set FBX import options (using MEL as Python equivalents can be complex)
            # Import into the scene, don't merge/update existing nodes directly
            mel.eval("FBXImportMode -v Add;")
            mel.eval("FBXImportGenerateLog -v false;") # Don't create import log file
            # Turn off protections that might prevent overwriting attributes later
            mel.eval("FBXImportProtectDrivenKeys -v false;")
            mel.eval("FBXImportMergeAnimationLayers -v false;")
            mel.eval("FBXImportSkins -v false;") # Don't import skinning
            mel.eval("FBXImportShapes -v false;") # Don't import blend shapes
            mel.eval("FBXImportConstraints -v false;")
            mel.eval("FBXImportCameras -v false;")
            mel.eval("FBXImportLights -v false;")
            mel.eval("FBXImportFillTimeline -v false;")
            # Match units if possible, though UVs are usually unitless
            mel.eval('FBXImportConvertUnitString "cm";')

            imported_nodes = cmds.file(
                fbx_source_path_str,
                i=True,                       # Import flag
                type="FBX",
                ignoreVersion=True,
                renameAll=True,               # Avoid name clashes by renaming imports
                namespace=import_namespace,   # Place imported nodes in temp namespace
                options="fbx",                # Use FBX options set above
                preserveReferences=False,
                returnNewNodes=True,          # Get list of top-level imported nodes
                prompt=False,                 # Don't show Maya import dialog
                loadReferenceDepth="all",
            )
            logger.info(
                f"Imported FBX from {fbx_source_path.name} into namespace '{import_namespace}'."
            )
            logger.debug(f"Nodes reported by import command: {imported_nodes}")

        except Exception as e:
            self.set_feedback("Error: Failed to import bridge FBX file.", level="error")
            logger.error(f"FBX Import failed: {e}", exc_info=True)
            # Attempt cleanup even if import fails partially
            self._cleanup_import_namespace(import_namespace)
            return

        # --- Find Imported Geometry ---
        # Get transform nodes within the imported namespace
        imported_transforms = cmds.ls(f"{import_namespace}:*", type="transform", long=True) or []
        if not imported_transforms and imported_nodes:
             # Fallback if returnNewNodes didn't work as expected
             logger.warning("returnNewNodes might not have listed transforms, using ls fallback.")
             # imported_transforms = [n for n in imported_nodes if cmds.nodeType(n) == 'transform'] # Less reliable if hierarchy exists

        if not imported_transforms:
            self.set_feedback(
                "Error: No transform nodes found in imported FBX.", level="error"
            )
            logger.error(
                f"No transforms found in namespace '{import_namespace}' "
                f"after import from {fbx_source_path_str}"
            )
            self._cleanup_import_namespace(import_namespace)
            return

        logger.debug(f"Found {len(imported_transforms)} imported transforms in namespace.")

        # --- Transfer UVs ---
        transfer_count = 0
        error_count = 0
        processed_targets = set() # Keep track of targets processed

        cmds.undoInfo(openChunk=True, chunkName="Fetch Rizom UVs")
        try:
            for target_transform in target_objects:
                if target_transform in processed_targets:
                    continue # Should not happen with initial list, but good practice

                # Find the corresponding imported object based on name matching (without namespace)
                target_leaf_name = target_transform.split("|")[-1].split(":")[-1]
                logger.debug(f"Processing target: {target_transform} (Leaf Name: {target_leaf_name})")

                matched_import_source = None
                for imp_transform in imported_transforms:
                    imp_leaf_name = imp_transform.split("|")[-1].split(":")[-1]
                    if imp_leaf_name == target_leaf_name:
                        matched_import_source = imp_transform
                        logger.info(f"Found matching imported object: {matched_import_source}")
                        break

                if not matched_import_source:
                    logger.warning(f"No matching imported object found for target: {target_transform}")
                    error_count += 1
                    continue # Skip to the next target object

                # --- Get Source and Target Shapes ---
                source_shapes = cmds.listRelatives(matched_import_source, s=True, ni=True, f=True, type="mesh") or []
                target_shapes = cmds.listRelatives(target_transform, s=True, ni=True, f=True, type="mesh") or []

                if not source_shapes or not target_shapes:
                    logger.warning(
                        f"Could not find mesh shapes for match: "
                        f"Source({matched_import_source}):{source_shapes}, "
                        f"Target({target_transform}):{target_shapes}"
                    )
                    error_count += 1
                    continue

                # Assume first shape is the one we want
                src_shape = source_shapes[0]
                trg_shape = target_shapes[0]
                logger.info(f"Preparing UV transfer: From '{src_shape}' To '{trg_shape}'")

                # --- Determine UV Sets to Transfer ---
                try:
                    # Get available UV sets from the *imported* source mesh
                    src_uv_sets = cmds.polyUVSet(src_shape, query=True, allUVSets=True) or ["map1"] # Assume map1 if none reported
                    logger.info(f"Source UV sets found on '{src_shape}': {src_uv_sets}")

                    # Get existing UV sets on the *target* mesh
                    trg_uv_sets_before = cmds.polyUVSet(trg_shape, query=True, allUVSets=True) or []
                    logger.debug(f"Target UV sets on '{trg_shape}' before transfer: {trg_uv_sets_before}")

                    uv_sets_to_transfer = []
                    final_target_display_name = target_uv_set_name # For feedback message

                    if target_uv_set_name == "All UV Sets":
                        # Transfer all UV sets found on the source
                        uv_sets_to_transfer = [uv_set for uv_set in src_uv_sets if uv_set] # Filter out potential None/empty
                        final_target_display_name = "All Found Sets"
                        logger.info(f"Transferring all found source UV sets: {uv_sets_to_transfer}")
                    elif target_uv_set_name in src_uv_sets:
                        # Transfer only the specifically requested set
                        uv_sets_to_transfer = [target_uv_set_name]
                        logger.info(f"Transferring specific UV set: {target_uv_set_name}")
                    else:
                        logger.warning(
                            f"Requested UV set '{target_uv_set_name}' not found "
                            f"on imported source shape '{src_shape}'. Skipping transfer for {target_transform}."
                        )
                        error_count += 1
                        continue # Skip to next target object

                    # --- Perform Transfer for each required UV set ---
                    transfer_successful_for_item = False
                    for uv_set in uv_sets_to_transfer:
                        logger.debug(f"Processing transfer for UV set: '{uv_set}'")

                        # Ensure the target UV set exists on the target mesh
                        if uv_set not in trg_uv_sets_before:
                            try:
                                cmds.polyUVSet(trg_shape, create=True, uvSet=uv_set)
                                logger.info(f"Created UV set '{uv_set}' on target {trg_shape}")
                            except Exception as e_create:
                                logger.error(f"Failed to create UV set '{uv_set}' on {trg_shape}: {e_create}")
                                error_count += 1
                                continue # Skip this UV set for this object

                        # --- Execute transferAttributes ---
                        try:
                            # Set the current UV set correctly on source and target
                            # for transferAttributes sourceUvSpace/targetUvSpace flags
                            cmds.polyUVSet(src_shape, currentUVSet=True, uvSet=uv_set)
                            cmds.polyUVSet(trg_shape, currentUVSet=True, uvSet=uv_set)

                            cmds.transferAttributes(
                                src_shape,
                                trg_shape,
                                transferPositions=0,      # Don't transfer vertex positions
                                transferNormals=0,        # Don't transfer normals
                                transferUVs=2,            # Transfer UV sets (all per face)
                                transferColors=0,         # Don't transfer color sets
                                sampleSpace=4,            # Component space (matches UVs vertex-per-face)
                                sourceUvSpace=uv_set,     # Specify source set name
                                targetUvSpace=uv_set,     # Specify target set name
                                searchMethod=3,           # Closest component (accurate for identical topology)
                                flipUVs=0,                # Don't flip UVs
                                colorBorders=1,           # Transfer color borders (usually not needed for UVs)
                            )
                            # Delete history on the target object after transfer to bake it
                            cmds.delete(trg_shape, constructionHistory=True)
                            logger.info(f"Successfully transferred UV set '{uv_set}' to {trg_shape}")
                            transfer_successful_for_item = True

                        except Exception as e_xfer:
                            logger.error(
                                f"Error transferring UV set '{uv_set}' for {target_transform}: {e_xfer}",
                                exc_info=True,
                            )
                            error_count += 1
                            # Continue to next UV set if transferring "All"

                    # Increment overall transfer count if at least one set succeeded for this object
                    if transfer_successful_for_item:
                        transfer_count += 1

                except Exception as e_setup:
                    logger.error(
                        f"Error during UV transfer setup for {target_transform}: {e_setup}",
                        exc_info=True,
                    )
                    error_count += 1

                processed_targets.add(target_transform) # Mark as processed

        except Exception as e_main_loop:
             logger.error(f"Unexpected error during UV transfer loop: {e_main_loop}", exc_info=True)
             cmds.undoInfo(closeChunk=True)
             cmds.undo() # Attempt to undo partial changes
             self.set_feedback("Error during UV transfer. Check logs.", level="error")
             self._cleanup_import_namespace(import_namespace)
             cmds.select(target_objects, replace=True) # Reselect original targets
             return # Abort further processing
        finally:
            cmds.undoInfo(closeChunk=True)


        # --- Cleanup ---
        self._cleanup_import_namespace(import_namespace)

        # --- Finalize ---
        cmds.select(target_objects, replace=True) # Reselect original target objects
        self.refresh_uv_options()          # Update dropdown based on potentially new sets

        # --- Report Outcome ---
        num_targets = len(target_objects)
        if error_count == 0 and transfer_count > 0:
            self.set_feedback(
                f"UVs successfully imported to {transfer_count} object(s) (Set: '{final_target_display_name}')",
                level="info",
            )
        elif transfer_count > 0:
             self.set_feedback(
                f"UV import completed for {transfer_count}/{num_targets} objects with {error_count} errors. Check logs.",
                level="warning",
            )
        elif num_targets > 0 :
             self.set_feedback(
                f"UV import failed for {num_targets} selected objects. No matches or errors occurred. Check logs.",
                level="error",
            )
        else:
            # This case shouldn't be reached due to initial check, but handle anyway
             self.set_feedback("UV import process completed (no targets?).", level="info")


    def _cleanup_import_namespace(self, namespace):
        """Deletes nodes within the specified namespace and removes the namespace."""
        logger.debug(f"Cleaning up import namespace: {namespace}")
        if not cmds.namespace(exists=namespace):
            logger.debug("Namespace already removed or never existed.")
            return

        try:
            # List contents first
            ns_content = cmds.ls(f"{namespace}:*", long=True)
            valid_nodes_to_delete = [n for n in ns_content if cmds.objExists(n)]

            if valid_nodes_to_delete:
                logger.info(f"Deleting {len(valid_nodes_to_delete)} imported nodes from namespace '{namespace}'.")
                cmds.delete(valid_nodes_to_delete)
            else:
                 logger.info(f"No valid nodes found in namespace '{namespace}' to delete.")

            # Remove the (now hopefully empty) namespace
            cmds.namespace(setNamespace=":") # Move to root
            cmds.namespace(removeNamespace=namespace)
            logger.info(f"Removed import namespace '{namespace}'.")

        except Exception as e_clean:
            logger.error(f"Issues during cleanup of import namespace '{namespace}': {e_clean}")


    def adjust_angle(self):
        """Updates the angle threshold from the UI."""
        self.edge_angle_threshold = self.angle_adjuster.value()
        logger.info(f"Post-process soften tolerance angle set to {self.edge_angle_threshold:.1f}")

    def toggle_tolerance(self):
        """Updates the tolerance usage flag from the UI."""
        self.use_angle_tolerance = self.tolerance_toggle.isChecked()
        logger.info(
            f"Post-process angle tolerance {'enabled' if self.use_angle_tolerance else 'disabled'}"
        )

    def process_uv_edges(self):
        """
        Softens all edges, hardens UV borders, and optionally applies
        angle-based softening to the selected mesh objects in Maya.
        """
        self.set_feedback("Processing normals based on UV borders...", level="info")
        cmds.refresh()

        # --- Identify Target Meshes ---
        selection = cmds.ls(selection=True, long=True, objectsOnly=True) or []
        if not selection:
            self.set_feedback("Error: No objects or components selected.", level="error")
            logger.error("process_uv_edges: No selection found.")
            return

        target_transforms = set()
        target_shapes = set() # Use shape paths for processing

        # Expand component selections to their objects/shapes
        sel_types = cmds.filterExpand(selectionExpand=True, selectionMask=(1, 9, 10, 12)) # Meshes, Verts, Edges, Faces, UVs
        if sel_types:
             objects = cmds.ls(sel_types, objectsOnly=True, long=True, type="transform") or []
             for obj in objects:
                 shapes = cmds.listRelatives(obj, s=True, ni=True, f=True, type="mesh") or []
                 if shapes:
                     target_transforms.add(obj)
                     target_shapes.add(shapes[0]) # Add full path to shape
        else:
             # Handle direct transform/shape selection
             for item in selection:
                 node_type = cmds.nodeType(item)
                 if node_type == "transform":
                     shapes = cmds.listRelatives(item, s=True, ni=True, f=True, type="mesh") or []
                     if shapes:
                         target_transforms.add(item)
                         target_shapes.add(shapes[0])
                 elif node_type == "mesh":
                      parent_transform = cmds.listRelatives(item, parent=True, fullPath=True)
                      if parent_transform:
                          target_transforms.add(parent_transform[0])
                          target_shapes.add(item) # Add full path to shape

        if not target_shapes:
            self.set_feedback(
                "Error: Selection contains no processable mesh objects.", level="error"
            )
            logger.warning(f"No mesh shapes identified from selection: {selection}")
            return

        processed_count = 0
        original_selection_list = cmds.ls(selection=True, long=True) # Preserve original full selection

        cmds.undoInfo(openChunk=True, chunkName="Process UV Edges")
        try:
            logger.info(f"Processing {len(target_shapes)} mesh shape(s): {list(target_shapes)}")
            # Select the shapes/transforms we are processing
            cmds.select(list(target_transforms), replace=True)

            for mesh_shape_path in target_shapes:
                # Double check object still exists (might be deleted during script execution)
                if not cmds.objExists(mesh_shape_path):
                    logger.warning(f"Mesh shape {mesh_shape_path} no longer exists. Skipping.")
                    continue

                # Find parent transform again just to be safe
                parent_transform = cmds.listRelatives(mesh_shape_path, parent=True, fullPath=True)
                if not parent_transform:
                     logger.warning(f"Could not find parent transform for {mesh_shape_path}. Skipping.")
                     continue
                current_transform = parent_transform[0]

                logger.info(f"Processing: {mesh_shape_path}")

                # 1. Soften all edges first
                logger.debug(f"Softening all edges on {mesh_shape_path} (Angle=180)")
                cmds.polySoftEdge(mesh_shape_path, angle=180, constructionHistory=False)

                # 2. Harden UV border edges
                logger.debug(f"Selecting UV borders on {current_transform}")
                border_edges = []
                try:
                    # Select the object, convert to edges, then select UV border edges via MEL
                    cmds.select(current_transform, replace=True)
                    # Ensure component mode is active for MEL command
                    # cmds.selectMode(component=True) # Might interfere if user is in object mode
                    # cmds.selectType( polymeshEdge=True ) # Be specific
                    mel.eval(f"polySelectBorderShellComponent {mesh_shape_path};") # Selects UV shell borders more reliably? Let's test this.
                    # Alternative: Select all Edges then Select UV Border
                    # cmds.ConvertSelectionToEdges()
                    # mel.eval("SelectUVBorderComponents;")

                    # Get the resulting edge selection
                    border_edges = cmds.ls(selection=True, flatten=True) or []
                    logger.debug(f"Found {len(border_edges)} UV border edge components.")

                except Exception as mel_err:
                    logger.error(
                        f"Error selecting UV border edges on {current_transform}: {mel_err}"
                    )
                    # Reset selection mode if error occurs
                    cmds.selectMode(object=True)
                    continue # Skip hardening for this object

                # Harden the selected border edges if any were found
                if border_edges:
                    # Filter just edge components (ls might return transform too)
                    edge_components = cmds.filterExpand(border_edges, selectionMask=32, expand=True, fullPath=True) # Mask 32 = Edges
                    if edge_components:
                        logger.debug(f"Hardening {len(edge_components)} UV border edges (Angle=0).")
                        cmds.polySoftEdge(edge_components, angle=0, constructionHistory=False)
                    else:
                        logger.info(f"No valid edge components found after border selection for {mesh_shape_path}.")
                else:
                    logger.info(f"No UV border edges were selected for {mesh_shape_path}.")


                # 3. Optionally re-soften based on angle tolerance
                if self.use_angle_tolerance:
                    logger.debug(
                        f"Applying tolerance softening ({self.edge_angle_threshold:.1f} deg) to {mesh_shape_path}"
                    )
                    cmds.polySoftEdge(
                        mesh_shape_path,
                        angle=self.edge_angle_threshold,
                        constructionHistory=False,
                    )

                # 4. Clean up history (optional, but good practice after poly operations)
                logger.debug(f"Deleting history on {mesh_shape_path}")
                cmds.delete(mesh_shape_path, constructionHistory=True)

                processed_count += 1

        except Exception as e:
            self.set_feedback("Error during edge processing. Check Script Editor.", level="error")
            logger.error("Edge processing failed.", exc_info=True)
            cmds.undoInfo(closeChunk=True)
            cmds.undo() # Attempt to revert changes
            # Reselect original selection might be helpful here
            if original_selection_list: cmds.select(original_selection_list, replace=True)
            return
        finally:
            cmds.undoInfo(closeChunk=True)
            # Restore original selection after processing finishes or fails
            if original_selection_list: cmds.select(original_selection_list, replace=True)
            else: cmds.select(clear=True)
            logger.debug("Restored original selection.")

        # --- Final Feedback ---
        if processed_count > 0:
            feedback = f"Processed normals on {processed_count} object(s)."
            self.set_feedback(feedback, level="info")
        else:
            self.set_feedback(
                "No mesh objects were successfully processed. Check logs.", level="warning"
            )


# --- Utility Functions ---

def fetch_maya_root():
    """Gets the Maya main window QWidget instance."""
    try:
        # Use MQtUtil to get the main window pointer
        maya_main_window_ptr = omui.MQtUtil.mainWindow()
        if maya_main_window_ptr is None:
            logger.error("Could not get Maya main window pointer.")
            return None

        # Wrap the pointer (which is an integer address) into a QWidget object.
        # Use int() for wrapping in both PySide2/PySide6 and Python 2/3.
        # The correct wrapInstance (from shiboken2 or shiboken6) should have
        # been imported earlier based on the PYSIDE_VERSION check.
        return wrapInstance(int(maya_main_window_ptr), QtWidgets.QWidget)

    except Exception as e:
        logger.error(f"Unexpected error wrapping Maya main window: {e}", exc_info=True)
        return None


# --- Tool Launch Function ---

def launch_tool():
    """Creates and shows the RizomUV Bridge panel."""

    # Define names for workspace control and the panel instance
    # Using a more specific workspace control name helps avoid conflicts
    intended_workspace_control_name = "RizomUVBridgeWorkspaceControl"
    panel_object_name = UVBridgePanel.UI_INSTANCE_NAME # From the class definition
    # Maya might create a default name if we don't provide one, check for that too
    default_workspace_control_name = panel_object_name + "WorkspaceControl"

    logger.info("--- Launching RizomUV Bridge ---")
    logger.debug(
        f"Panel UI Name: {panel_object_name}, "
        f"Intended WC: {intended_workspace_control_name}, "
        f"Default WC Check: {default_workspace_control_name}"
    )

    # --- Cleanup Existing Instances ---
    # Check for and delete any lingering instances of the UI or its controls
    # This is crucial for reloading the script during development

    # Check 1: Default-named Workspace Control (if Maya created one automatically)
    if cmds.workspaceControl(default_workspace_control_name, query=True, exists=True):
        logger.warning(f"Found lingering default-named workspace control: {default_workspace_control_name}. Deleting...")
        try:
            cmds.deleteUI(default_workspace_control_name, control=True)
            logger.info(f"Deleted default-named workspace control: {default_workspace_control_name}")
        except Exception as e_del_def_wc:
            logger.error(f"Error deleting default-named workspace control '{default_workspace_control_name}': {e_del_def_wc}")

    # Check 2: Intentionally-named Workspace Control
    if (intended_workspace_control_name != default_workspace_control_name and
            cmds.workspaceControl(intended_workspace_control_name, query=True, exists=True)):
        logger.info(f"Found intended workspace control: {intended_workspace_control_name}. Deleting...")
        try:
            cmds.deleteUI(intended_workspace_control_name, control=True)
            logger.info(f"Deleted intended workspace control: {intended_workspace_control_name}")
        except Exception as e_del_int_wc:
            logger.error(f"Error deleting intended workspace control '{intended_workspace_control_name}': {e_del_int_wc}")

    # Check 3: The Panel UI Widget itself (based on its objectName)
    if cmds.control(panel_object_name, exists=True):
        logger.info(f"Found lingering panel UI widget: {panel_object_name}. Deleting...")
        try:
            cmds.deleteUI(panel_object_name, control=True)
            logger.info(f"Deleted panel UI widget: {panel_object_name}")
        except Exception as e_del_ui:
            logger.error(f"Error deleting panel UI widget '{panel_object_name}': {e_del_ui}")


    # --- Create New Instance ---
    maya_root = fetch_maya_root()
    if maya_root is None:
        cmds.error("Could not get Maya main window. Rizom Bridge cannot be launched.")
        return None

    try:
        # Create the panel instance
        panel = UVBridgePanel(parent=maya_root)

        # --- Generate uiScript for Workspace Control Persistence ---
        # This script allows Maya to rebuild the UI if the workspace is saved/reloaded
        recreation_script = ""
        try:
            # Try to determine the module name dynamically
            module_name = __name__ # Will be '__main__' if run directly, or module name if imported
            actual_module_name = None

            if module_name == "__main__":
                 # If run directly, try to get module path from __file__
                 script_path = Path(__file__).resolve() # Get absolute path
                 # Find the Maya scripts directory to determine relative path
                 try:
                      maya_scripts_dir = Path(cmds.internalVar(userScriptDir=True)).resolve()
                      relative_path = script_path.relative_to(maya_scripts_dir)
                      # Construct module path from relative path
                      actual_module_name = ".".join(relative_path.with_suffix("").parts)
                      logger.debug(f"Guessed module name for uiScript (relative): {actual_module_name}")
                 except (ValueError, Exception): # Handle cases where script is not under scripts dir
                      actual_module_name = script_path.stem # Fallback to just the filename
                      logger.warning(f"Script not in Maya scripts dir? Using stem: {actual_module_name}")

            else:
                 # If imported, __name__ should be the correct module path
                 actual_module_name = module_name
                 logger.debug(f"Using imported module name for uiScript: {actual_module_name}")

            if actual_module_name:
                # Construct the recreation command
                recreation_script = (
                    f"import {actual_module_name}\n"
                    f"import importlib\n"
                    f"importlib.reload({actual_module_name})\n" # Ensure latest code is used on reload
                    f"{actual_module_name}.launch_tool()"
                )
                logger.info("Generated uiScript for workspace control persistence.")
                logger.debug(f"uiScript content:\n{recreation_script}")
            else:
                 logger.warning("Could not determine module name. uiScript for workspace control recreation will be empty.")

        except NameError:
             logger.warning("Cannot determine script path (__file__ not defined). uiScript will be empty.")
        except Exception as e_ui_script:
             logger.error(f"Error generating uiScript: {e_ui_script}", exc_info=True)


        # --- Show the Panel ---
        # Use the MayaQWidgetDockableMixin's show method to integrate with Maya UI
        panel.show(
            dockable=True,
            area="right", # Default docking area
            allowedArea=["right", "left"], # Allow docking on left or right
            floating=False, # Start docked, not floating
            label="RizomUV Bridge", # Label shown in UI panels menu/tabs
            uiScript=recreation_script, # Script to recreate UI on Maya layout load
            workspaceControlName=intended_workspace_control_name # Explicitly name the control
        )

        logger.info(
            f"RizomUV Bridge panel '{panel_object_name}' launched "
            f"in workspace control '{intended_workspace_control_name}'."
        )
        # Print cool ASCII art to script editor on successful launch
        print(BRIDGE_ASCII_ART)

        return panel # Return the panel instance

    except Exception as e:
        logger.error(f"Error launching RizomUV Bridge panel: {e}", exc_info=True)
        # Attempt cleanup again if launch fails mid-way
        if cmds.control(panel_object_name, exists=True):
            cmds.deleteUI(panel_object_name, control=True)
        if cmds.workspaceControl(intended_workspace_control_name, query=True, exists=True):
            cmds.deleteUI(intended_workspace_control_name, control=True)
        if cmds.workspaceControl(default_workspace_control_name, query=True, exists=True):
            cmds.deleteUI(default_workspace_control_name, control=True)
        return None


# --- Main Execution Block ---
if __name__ == "__main__":
    # This block runs if the script is executed directly (e.g., from Script Editor)
    # Ensure logging level is appropriate for direct execution/debugging
    # setup_logging(level=logging.DEBUG) # Uncomment for maximum verbosity when testing

    logger.info(f"Executing Rizom Bridge script directly (__name__='{__name__}')")

    # Need to defer execution slightly sometimes for Maya UI to be ready
    # cmds.evalDeferred("import RZMUV_Bridge_Module; RZMUV_Bridge_Module.launch_tool()") # Replace with actual module name if saved
    # For direct execution without saving as module:
    cmds.evalDeferred("launch_tool()")


# Example Shelf Button Code:
# --------------------------
# Assumes you save this script as e.g., 'maya/scripts/RZMUV/RizomBridge.py'
"""
import sys
import maya.cmds as cmds

# Define the path to your script directory if it's not standard
script_module_name = "RZMUV.RizomBridge" # Adjust if your path/filename differs

# Check if module is loaded, import/reload if necessary
if script_module_name in sys.modules:
    import importlib
    try:
        # Reload the module to pick up changes
        module_instance = importlib.reload(sys.modules[script_module_name])
        print(f"Reloaded {script_module_name}")
        # Launch the tool from the reloaded module
        module_instance.launch_tool()
    except Exception as e:
        cmds.error(f"Error reloading/launching {script_module_name}: {e}")
else:
    try:
        # Import the module for the first time
        __import__(script_module_name, globals(), locals(), [], 0)
        print(f"Imported {script_module_name}")
        # Launch the tool from the newly imported module
        sys.modules[script_module_name].launch_tool()
    except ImportError as e:
        cmds.error(f"Could not import {script_module_name}. Is it in your Maya script path? Error: {e}")
    except Exception as e:
        cmds.error(f"Error importing/launching {script_module_name}: {e}")

"""