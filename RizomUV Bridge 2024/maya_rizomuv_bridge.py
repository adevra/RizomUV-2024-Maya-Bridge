import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMayaUI as omui
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import subprocess, tempfile, os, platform, sys, locale, base64, logging

# Removed: xml.dom.minidom, xml.parsers.expat
import json  # Added
import shutil  # Added
from pathlib import Path  # Added

# PySide/Shiboken handling (Keep existing)
if sys.version_info.major >= 3 and sys.version_info.minor >= 11:
    # Maya 2025+ typically uses PySide6 with Python 3.11+
    # A try-except might be more robust for future Maya versions
    try:
        from PySide6 import QtWidgets, QtCore, QtGui
        from shiboken6 import wrapInstance

        PYSIDE_VERSION = 6
    except ImportError:
        # Fallback for unusual environments? Maya 2025 should have PySide6
        from PySide2 import QtWidgets, QtCore, QtGui
        from shiboken2 import wrapInstance

        PYSIDE_VERSION = 2
else:
    # Maya 2022-2024 use PySide2 with Python 3.7/3.9
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance

    PYSIDE_VERSION = 2
# --- Constants ---
# This will be the name of the subdirectory within Maya's scripts folder
INSTALL_SUBDIR_NAME = "RZMUV"
# Files managed within the INSTALL_SUBDIR_NAME
CONFIG_FILE_NAME = "settings.json"
LUA_SCRIPT_FILE_NAME = "rizomuv_control_script.lua"
FBX_FILE_NAME = "RizomUVMayaBridge.fbx"
PATH_DEFAULTS = {
    "Windows": r"C:\Program Files\Rizom Lab\RizomUV 2024.0\rizomuv.exe",
    "Darwin": "/Applications/RizomUV 2024.1.app",
    "Linux": "/usr/local/bin/rizomuv",
}
logo_encoded = "iVBORw0KGgoAAAANSUhEUgAAAH0AAAB9CA"
# Logging Setup (Keep existing)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - RizomBridge - %(levelname)s - %(message)s",  # Added module name
)


# safe_decode_subprocess (Keep existing)
def safe_decode_subprocess(command):
    # ... (implementation remains the same) ...
    encodings_to_try = [
        locale.getpreferredencoding(False),
        "utf-8",
        "cp866",
        "cp1251",
        "latin1",
    ]
    for enc in encodings_to_try:
        try:
            # Ensure command elements are strings for subprocess
            str_command = [str(c) for c in command]
            output = subprocess.check_output(
                str_command, stderr=subprocess.STDOUT
            ).decode(enc, errors="replace")
            return output
        except (
            UnicodeDecodeError,
            subprocess.SubprocessError,
            FileNotFoundError,
        ):  # Added FileNotFoundError
            continue
        except Exception as e:  # Catch other potential errors
            logging.warning(f"Error decoding subprocess for command '{command}': {e}")
            continue
    logging.warning(f"Could not decode output for command: {command}")
    return ""


class ConfigManager:
    def __init__(self):
        self.base_dir = self._get_base_directory()
        self.config_file_path = self.base_dir / CONFIG_FILE_NAME
        self.lua_control_file_path = self.base_dir / LUA_SCRIPT_FILE_NAME
        self.fbx_export_file_path = self.base_dir / FBX_FILE_NAME
        self.rizom_location = ""  # Will be loaded or set to default
        self.include_uvs = True
        self.pack_quality = 2
        self.pack_iterations = 256
        self.ensure_storage_exists()
        self.load_or_create_config()

    def _get_base_directory(self) -> Path:
        """Determines the base directory for all script files (scripts/RZMUV/)."""
        try:
            scripts_dir = Path(cmds.internalVar(userScriptDir=True))
            base_dir = scripts_dir / INSTALL_SUBDIR_NAME
            return base_dir
        except Exception as e:
            logging.error(
                f"Could not get Maya scripts dir via internalVar: {e}. Falling back."
            )
            fallback_base = (
                Path(os.path.expanduser("~"))
                / ".maya_rizom_bridge"
                / INSTALL_SUBDIR_NAME
            )
            logging.warning(f"Using fallback directory: {fallback_base}")
            return fallback_base

    def ensure_storage_exists(self):
        """Creates the base directory (RZMUV) if it doesn't exist."""
        if not self.base_dir.exists():
            try:
                self.base_dir.mkdir(parents=True, exist_ok=True)
                logging.info(f"Created settings directory: {self.base_dir}")
            except OSError as e:
                logging.error(
                    f"Failed to create settings directory {self.base_dir}: {e}"
                )

    def load_or_create_config(self):
        """Loads config from JSON file or creates a default one if missing/invalid."""
        if not self.config_file_path.is_file():
            logging.info(
                f"{CONFIG_FILE_NAME} not found. Creating default configuration."
            )
            self.set_initial_config()
            self.save_config()
        else:
            try:
                with open(self.config_file_path, "r") as f:
                    config_data = json.load(f)
                self.rizom_location = config_data.get(
                    "rizomPath", self._get_default_rizom_path()
                )
                self.include_uvs = config_data.get("loadUVs", True)
                self.pack_quality = config_data.get("quality", 2)
                self.pack_iterations = config_data.get("mutations", 256)
                logging.info(f"Loaded configuration from {self.config_file_path}")
            except json.JSONDecodeError as e_json:
                logging.error(
                    f"Error decoding {self.config_file_path}: {e_json}. Attempting backup and reset."
                )
                self._backup_and_reset_config("JSONDecodeError")
            except KeyError as e_key:
                logging.error(
                    f"Missing key in {self.config_file_path}: {e_key}. Attempting backup and reset."
                )
                self._backup_and_reset_config("KeyError")
            except Exception as e:
                logging.error(
                    f"Unexpected error loading configuration: {e}. Attempting backup and reset."
                )
                self._backup_and_reset_config(type(e).__name__)

    def _backup_and_reset_config(self, error_type="UnknownError"):
        """Backs up the corrupted config and creates a new default one."""
        if self.config_file_path.is_file():
            backup_path = self.config_file_path.with_suffix(
                f".corrupt_{error_type}.bak"
            )
            try:
                shutil.copy2(self.config_file_path, backup_path)
                logging.info(f"Backed up corrupted config to: {backup_path}")
            except Exception as e_bak:
                logging.error(f"Failed to backup corrupted config: {e_bak}")
        logging.warning("Resetting configuration to defaults due to loading error.")
        self.set_initial_config()
        self.save_config()  # Save the new default config

    def _get_default_rizom_path(self) -> str:
        """Gets the platform-specific default path for RizomUV."""
        return PATH_DEFAULTS.get(platform.system(), PATH_DEFAULTS["Windows"])

    def set_initial_config(self):
        """Sets the configuration attributes to their default values."""
        self.rizom_location = self._get_default_rizom_path()
        self.include_uvs = True
        self.pack_quality = 2
        self.pack_iterations = 256
        logging.info("Set initial default configuration values.")

    def save_config(self):
        """Saves the current configuration to the JSON file."""
        config_data = {
            "rizomPath": str(self.rizom_location),  # Store path as string
            "loadUVs": self.include_uvs,
            "quality": self.pack_quality,
            "mutations": self.pack_iterations,
        }
        try:
            # Ensure directory exists before writing
            self.ensure_storage_exists()
            if not self.base_dir.is_dir() or not os.access(str(self.base_dir), os.W_OK):
                logging.error(
                    f"Cannot write to directory: {self.base_dir}. Config not saved."
                )
                # Propagate this error to the UI?
                return False
            with open(self.config_file_path, "w") as f:
                json.dump(config_data, f, indent=4)
            logging.info(f"Saved configuration to {self.config_file_path}")
            return True
        except IOError as e:
            logging.error(
                f"Failed to save configuration to {self.config_file_path}: {e}"
            )
            return False
        except Exception as e:
            logging.error(f"Unexpected error saving configuration: {e}")
            return False

    # --- Provide access to derived paths ---
    def get_lua_script_path_str(self) -> str:
        """Returns the LUA script path as a string, suitable for subprocesses."""
        return str(self.lua_control_file_path)

    def get_fbx_export_path_str(self) -> str:
        """Returns the FBX export path as a string."""
        return str(self.fbx_export_file_path)


# --- UVBridgePanel Class ---
class UVBridgePanel(MayaQWidgetDockableMixin, QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(UVBridgePanel, self).__init__(parent)
        # Instantiate the updated ConfigManager
        self.config = ConfigManager()
        # --- Rest of __init__ remains similar ---
        self.setWindowTitle("RizomUV Bridge")
        self.setMinimumWidth(250)
        self.edge_angle_threshold = 45.1
        self.use_angle_tolerance = True
        self.setObjectName("rizomUVBridgePanelInstance")  # Keep consistent object name
        self.build_interface()
        self.setup_handlers()
        logging.info("RizomUV Bridge Panel Initialized.")

    def build_interface(self):
        # --- Layout remains largely the same ---
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)
        # Settings Group
        settings_group = QtWidgets.QGroupBox("Settings")
        settings_layout = QtWidgets.QVBoxLayout()
        # Use loaded config value for the line edit
        self.location_input = QtWidgets.QLineEdit(
            str(self.config.rizom_location)
        )  # Use loaded value
        self.location_input.setToolTip("Path to the RizomUV executable or .app bundle")
        self.browse_btn = QtWidgets.QPushButton("Browse")
        path_layout = QtWidgets.QHBoxLayout()
        path_layout.addWidget(QtWidgets.QLabel("RizomUV Path:"))
        path_layout.addWidget(self.location_input)
        path_layout.addWidget(self.browse_btn)
        settings_layout.addLayout(path_layout)
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)
        # UV Operations Group (remains the same structure)
        ops_group = QtWidgets.QGroupBox("UV Operations")
        ops_layout = QtWidgets.QVBoxLayout()
        self.transfer_btn = QtWidgets.QPushButton("Send to RizomUV")
        self.transfer_btn.setToolTip("Export selected geometry and launch RizomUV")
        self.retrieve_btn = QtWidgets.QPushButton("Get UVs from RizomUV")
        self.retrieve_btn.setToolTip(
            "Import UVs from the bridge FBX file to the selected UV set"
        )
        self.uv_toggle = QtWidgets.QCheckBox("With Existing UVs")
        self.uv_toggle.setChecked(self.config.include_uvs)  # Use loaded value
        self.uv_toggle.setToolTip("Include existing UVs when exporting to RizomUV")
        self.uv_selector = QtWidgets.QComboBox()
        self.refresh_uv_options()  # Populate UV sets
        ops_layout.addWidget(self.transfer_btn)
        ops_layout.addWidget(self.uv_toggle)
        ops_layout.addWidget(QtWidgets.QLabel("Target/Source UV Set:"))  # Clarify label
        ops_layout.addWidget(self.uv_selector)
        ops_layout.addWidget(self.retrieve_btn)
        ops_group.setLayout(ops_layout)
        main_layout.addWidget(ops_group)
        # UV Packer Group (remains the same structure)
        packer_group = QtWidgets.QGroupBox("UV Packer")
        packer_layout = QtWidgets.QVBoxLayout()
        self.auto_pack_btn = QtWidgets.QPushButton(
            "Send and Auto Pack"
        )  # Clarify label
        self.auto_pack_btn.setToolTip(
            "Export geometry, launch RizomUV, unfold, and pack UVs"
        )
        self.quality_selector = QtWidgets.QComboBox()
        self.quality_selector.addItems(["Low", "Normal", "High", "Higher", "Ultra"])
        self.quality_selector.setCurrentIndex(
            self.config.pack_quality
        )  # Use loaded value
        self.quality_selector.setToolTip("Select packing quality level")
        self.iterations_spinner = QtWidgets.QSpinBox()
        self.iterations_spinner.setRange(1, 1000)
        self.iterations_spinner.setValue(
            self.config.pack_iterations
        )  # Use loaded value
        self.iterations_spinner.setToolTip("Number of packing iterations (mutations)")
        packer_layout.addWidget(self.auto_pack_btn)
        packer_layout.addWidget(QtWidgets.QLabel("Quality:"))
        packer_layout.addWidget(self.quality_selector)
        packer_layout.addWidget(QtWidgets.QLabel("Iterations:"))
        packer_layout.addWidget(self.iterations_spinner)
        packer_group.setLayout(packer_layout)
        main_layout.addWidget(packer_group)
        # Post Process Group (remains the same structure)
        post_group = QtWidgets.QGroupBox("Post Process (Normals)")
        post_layout = QtWidgets.QVBoxLayout()
        self.edge_hardener_btn = QtWidgets.QPushButton("Harden UV Edges")
        self.edge_hardener_btn.setToolTip(
            "Softens all normals, then hardens UV border edges based on angle"
        )
        self.tolerance_toggle = QtWidgets.QCheckBox(
            "Use Angle Tolerance"
        )  # Clarify label
        self.tolerance_toggle.setChecked(self.use_angle_tolerance)
        self.tolerance_toggle.setToolTip(
            "If checked, soften edges below the specified angle after hardening borders"
        )
        angle_layout = QtWidgets.QHBoxLayout()
        angle_layout.addWidget(QtWidgets.QLabel("Tolerance Angle:"))  # Clarify label
        self.angle_adjuster = QtWidgets.QDoubleSpinBox()
        self.angle_adjuster.setRange(0.1, 179.9)  # Max should be less than 180
        self.angle_adjuster.setValue(self.edge_angle_threshold)
        self.angle_adjuster.setSingleStep(0.1)
        self.angle_adjuster.setToolTip(
            "Angle threshold for softening edges (used if tolerance is checked)"
        )
        angle_layout.addWidget(self.angle_adjuster)
        post_layout.addWidget(self.edge_hardener_btn)
        post_layout.addWidget(self.tolerance_toggle)
        post_layout.addLayout(angle_layout)
        post_group.setLayout(post_layout)
        main_layout.addWidget(post_group)
        # Feedback Label (remains the same)
        self.feedback_label = QtWidgets.QLabel("Ready")
        self.feedback_label.setAlignment(QtCore.Qt.AlignCenter)
        main_layout.addWidget(self.feedback_label)
        # Logo (remains the same)
        try:
            logo_data = base64.b64decode(logo_encoded)
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(logo_data, "PNG")
            # Keep scaling modest or make it configurable? Let's keep 100 for now.
            scaled_pixmap = pixmap.scaled(
                100, 100, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
            )
            logo = QtWidgets.QLabel()
            logo.setPixmap(scaled_pixmap)
            logo.setAlignment(QtCore.Qt.AlignCenter)
            main_layout.addWidget(logo)
        except Exception as e:
            logging.error(f"Error loading logo from base64 data: {e}")
        main_layout.addStretch()

    def setup_handlers(self):
        # --- Connections remain largely the same, check persist_config ---
        self.transfer_btn.clicked.connect(lambda: self.dispatch_to_rizom(pack=False))
        self.auto_pack_btn.clicked.connect(lambda: self.dispatch_to_rizom(pack=True))
        self.retrieve_btn.clicked.connect(self.fetch_from_rizom)
        self.uv_toggle.stateChanged.connect(self.persist_config)  # Saves config
        self.browse_btn.clicked.connect(self.locate_rizom)  # Saves config on success
        self.location_input.editingFinished.connect(self.persist_config)  # Saves config
        self.quality_selector.currentIndexChanged.connect(
            self.persist_config
        )  # Saves config
        self.iterations_spinner.valueChanged.connect(
            self.persist_config
        )  # Saves config
        # ScriptJob for selection change to update UV sets
        try:
            # Kill existing job for this panel instance if it exists
            jobs = cmds.scriptJob(listJobs=True)
            job_tag = f"rizomUVBridgeSelChanged_{self.objectName()}"
            for job in jobs:
                if job_tag in job:
                    try:
                        job_num = int(job.split(":")[0])
                        cmds.scriptJob(kill=job_num, force=True)
                        logging.debug(f"Killed existing scriptJob: {job_num}")
                    except (ValueError, RuntimeError) as e_kill:
                        logging.warning(f"Could not kill job {job}: {e_kill}")
            # Create new job parented to this panel
            cmds.scriptJob(
                event=["SelectionChanged", self.refresh_uv_options],
                # Use parent=self.objectName() so Maya cleans it up if panel is closed
                parent=self.objectName(),
                protected=True,  # Protects from Kill All
                tag=job_tag,  # Add tag for specific killing if needed
            )
            logging.debug(f"Created SelectionChanged scriptJob with tag: {job_tag}")
        except Exception as e_sj:
            logging.error(f"Failed to create SelectionChanged scriptJob: {e_sj}")
        self.edge_hardener_btn.clicked.connect(self.process_uv_edges)
        self.tolerance_toggle.stateChanged.connect(self.toggle_tolerance)
        self.angle_adjuster.valueChanged.connect(self.adjust_angle)

    def locate_rizom(self):
        # --- Uses self.config.rizom_location, saves on success ---
        original_os_native_dialog_pref = 0
        system = platform.system()
        mac_pref_changed = False
        # Start Browse from the directory of the currently configured path
        current_path_str = str(self.config.rizom_location)
        start_dir = ""
        if current_path_str and (
            Path(current_path_str).exists() or Path(current_path_str).parent.exists()
        ):
            start_dir = str(Path(current_path_str).parent)
        else:
            # Platform specific default start dirs if config path is invalid/missing
            if system == "Darwin":
                start_dir = "/Applications" if Path("/Applications").exists() else "/"
            elif system == "Windows":
                program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
                start_dir = program_files if Path(program_files).exists() else "C:\\"
            else:  # Linux
                start_dir = "/"
        try:
            if system == "Darwin":
                # Mac needs special handling for selecting .app bundles
                try:
                    original_os_native_dialog_pref = cmds.optionVar(
                        query="useOSNativeFileDialog"
                    )
                    if original_os_native_dialog_pref == 0:
                        logging.info(
                            "Temporarily switching Maya to OS Native file dialog for .app selection."
                        )
                        cmds.optionVar(iv=("useOSNativeFileDialog", 1))
                        mac_pref_changed = True
                except Exception as e:
                    logging.warning(
                        f"Could not query/set OS native dialog preference: {e}"
                    )
                # Use QFileDialog, Maya's fileDialog command doesn't handle .app well
                path_tuple = QtWidgets.QFileDialog.getExistingDirectory(  # Use getExistingDirectory for .app
                    self,
                    "Locate RizomUV Application (.app)",
                    start_dir,
                    QtWidgets.QFileDialog.ShowDirsOnly
                    | QtWidgets.QFileDialog.DontResolveSymlinks,
                )
                # QFileDialog returns tuple on older PySide?, string on newer? Check type
                path = path_tuple[0] if isinstance(path_tuple, tuple) else path_tuple
            else:  # Windows and Linux
                if system == "Windows":
                    file_filter = "Executables (*.exe);;All Files (*)"
                else:  # Linux
                    file_filter = "Executables (*);;All Files (*)"
                path_tuple = QtWidgets.QFileDialog.getOpenFileName(
                    self, "Locate RizomUV Executable", start_dir, file_filter
                )
                path = path_tuple[0] if isinstance(path_tuple, tuple) else path_tuple
            if path:
                selected_path = Path(path)
                # Validate the selected path based on OS
                valid_path = False
                if (
                    system == "Darwin"
                    and selected_path.is_dir()
                    and selected_path.suffix == ".app"
                ):
                    # Check for the actual executable inside the .app bundle
                    potential_exe = (
                        selected_path / "Contents" / "MacOS" / "RizomUV"
                    )  # Common pattern
                    if potential_exe.is_file() and os.access(
                        str(potential_exe), os.X_OK
                    ):
                        valid_path = True
                    else:
                        logging.warning(
                            f"Could not find standard executable inside {selected_path}. Still accepting .app path."
                        )
                        valid_path = True  # Accept the .app path itself
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
                if valid_path:
                    # Use Path object internally, but display/save string
                    self.config.rizom_location = str(
                        selected_path
                    )  # Store as string in config
                    self.location_input.setText(str(selected_path))  # Display string
                    if self.config.save_config():  # Save the updated config
                        logging.info(f"RizomUV path set and saved: {selected_path}")
                        self.set_feedback(
                            f"RizomUV path set to: {selected_path}", level="info"
                        )
                    else:
                        logging.error(
                            "Failed to save the new RizomUV path to configuration."
                        )
                        self.set_feedback(
                            "Error: Failed to save new RizomUV path.", level="error"
                        )
                else:
                    logging.warning(
                        f"Selected path does not appear valid for {system}: {selected_path}"
                    )
                    cmds.warning(
                        f"Selected path may be invalid for {system}: {selected_path}"
                    )
                    self.set_feedback(
                        "Warning: Selected path may be invalid.", level="warning"
                    )
        except Exception as e:
            logging.error(
                f"Error during file dialog or path processing: {e}", exc_info=True
            )
            self.set_feedback("Error during file browse.", level="error")
        finally:
            # Restore Maya preference if changed
            if mac_pref_changed:
                try:
                    logging.info(
                        f"Restoring Maya file dialog preference to: {original_os_native_dialog_pref}"
                    )
                    cmds.optionVar(
                        iv=("useOSNativeFileDialog", original_os_native_dialog_pref)
                    )
                except Exception as e:
                    logging.warning(
                        f"Could not restore OS native dialog preference: {e}"
                    )

    def refresh_uv_options(self):
        """Updates the UV set dropdown based on the current selection."""
        logging.debug("Refreshing UV set options...")
        current_choice = (
            self.uv_selector.currentText() if self.uv_selector.count() else ""
        )
        self.uv_selector.clear()

        sel_transforms = cmds.ls(sl=True, type="transform", long=True) # Get only transforms
        options = ["All UV Sets"] # Default option
        unique_sets = set() # Use a set to collect unique names

        if sel_transforms:
            logging.debug(f"Selected transforms: {sel_transforms}")
            for transform_node in sel_transforms:
                # Find the mesh shape node(s) under the transform
                shapes = cmds.listRelatives(
                    transform_node,
                    shapes=True,
                    type="mesh",
                    fullPath=True,
                    noIntermediate=True # Ignore intermediate shapes
                ) or []

                if not shapes:
                    logging.debug(f"No mesh shape found for {transform_node}")
                    continue # Skip if no mesh shape

                # Query UV sets from the first valid shape found
                # (Assuming one mesh shape per transform for simplicity here)
                shape_node = shapes[0]
                try:
                    # Query UV sets on the SHAPE node
                    uv_sets_on_shape = cmds.polyUVSet(shape_node, query=True, allUVSets=True)
                    if uv_sets_on_shape:
                        logging.debug(f"Found UV sets on {shape_node}: {uv_sets_on_shape}")
                        # Add all found sets to our unique collection
                        unique_sets.update(uv_sets_on_shape)
                    else:
                        # If polyUVSet returns None or empty list, it likely only has the default 'map1' implicitly
                        logging.debug(f"No explicit UV sets returned for {shape_node}, assuming 'map1'.")
                        # Ensure map1 is considered if no explicit sets are found
                        # Check if map1 *actually* exists (though it usually does if mesh is valid)
                        # We can implicitly assume map1 exists if uv_sets_on_shape is empty/None
                        # or explicitly check if needed, but let's just add it if nothing else was found on this shape
                        if not cmds.polyUVSet(shape_node, query=True, currentUVSet=True): # A proxy check
                            unique_sets.add("map1")


                except Exception as e:
                    logging.warning(f"Could not query UV sets for shape {shape_node}: {e}")
                    # If querying fails for a shape, we might still want map1 as a default
                    unique_sets.add("map1") # Add map1 as a fallback for this object on error

            # After checking all selected objects, add the collected unique sets to options
            if unique_sets:
                 options.extend(sorted(list(unique_sets)))
            elif not options: # If somehow 'All UV Sets' wasn't added and unique_sets is empty
                 options.append("map1") # Ensure at least map1 is available if selection exists but yielded no sets


        else: # No transforms selected
            logging.debug("No transforms selected, adding default 'map1'.")
            options.append("map1") # Add default if nothing is selected

        # Remove potential duplicates if 'All UV Sets' was somehow added to unique_sets
        final_options = []
        seen = set()
        for item in options:
             if item not in seen:
                  final_options.append(item)
                  seen.add(item)


        logging.debug(f"Populating UV selector with: {final_options}")
        self.uv_selector.addItems(final_options)

        # Try to restore previous selection or set a sensible default
        if current_choice in final_options:
            self.uv_selector.setCurrentText(current_choice)
        elif "map1" in final_options:
            self.uv_selector.setCurrentText("map1")
        elif len(final_options) > 1: # Excludes "All UV Sets"
             # Set to the first actual UV set found
             self.uv_selector.setCurrentIndex(1)
        else: # Only "All UV Sets" is present
            self.uv_selector.setCurrentIndex(0)

    def persist_config(self):
        # --- Update config object and save ---
        self.config.include_uvs = self.uv_toggle.isChecked()
        self.config.rizom_location = self.location_input.text()  # Get text from UI
        self.config.pack_quality = self.quality_selector.currentIndex()
        self.config.pack_iterations = self.iterations_spinner.value()
        if not self.config.save_config():
            # Optionally provide feedback if saving failed silently
            logging.warning("Persist config: Failed to save configuration changes.")
            # self.set_feedback("Warning: Could not save settings.", level="warning") # Maybe too noisy

    def set_feedback(self, message, level="info"):
        # --- Remains the same ---
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
        else:  # Default style
            self.feedback_label.setStyleSheet("")

    def dispatch_to_rizom(self, pack=False):
        # --- Major changes: remove process check, use ConfigManager paths ---
        import time  # Keep for sleep after launch

        self.feedback_label.setStyleSheet("")  # Reset feedback style
        selected_items = cmds.ls(selection=True, long=True, transforms=True)
        if not selected_items:
            self.set_feedback("Error: No geometry selected.", level="error")
            return
        # Get paths from ConfigManager
        rizom_path_str = str(self.config.rizom_location)  # Path to executable/.app
        fbx_export_path_str = self.config.get_fbx_export_path_str()
        lua_script_path_str = self.config.get_lua_script_path_str()
        # Validate Rizom path exists
        rizom_path_obj = Path(rizom_path_str)
        if not rizom_path_obj.exists():
            self.set_feedback(
                f"Error: RizomUV path not found: {rizom_path_str}", level="error"
            )
            return
        use_existing_uvs = self.uv_toggle.isChecked()
        chosen_uv_set = self.uv_selector.currentText()
        # --- FBX Plugin Check (remains the same) ---
        if not cmds.pluginInfo("fbxmaya", loaded=True, query=True):
            try:
                cmds.loadPlugin("fbxmaya")
                logging.info("Loaded fbxmaya plugin.")
            except Exception as e:
                self.set_feedback("Error: Failed to load FBX plugin.", level="error")
                logging.error(f"Failed to load fbxmaya plugin: {e}")
                return
        # --- Set Active UV Set Logic (remains similar, ensure logging) ---
        cmds.select(selected_items, replace=True)
        active_uv_set_for_export = "map1"  # Default for FBX if not sending existing
        if use_existing_uvs:
            if chosen_uv_set != "All UV Sets":
                active_uv_set_for_export = chosen_uv_set
                # Set the current UV set on selected objects for FBX export
                for item in selected_items:
                    # ... (rest of the UV set checking/setting logic remains the same) ...
                    shapes = cmds.listRelatives(
                        item, shapes=True, fullPath=True, noIntermediate=True
                    )
                    if shapes:
                        try:
                            all_sets = cmds.polyUVSet(
                                shapes[0], query=True, allUVSets=True
                            )
                            if chosen_uv_set in all_sets:
                                cmds.polyUVSet(
                                    shapes[0], currentUVSet=True, uvSet=chosen_uv_set
                                )
                                logging.debug(
                                    f"Set current UV set to '{chosen_uv_set}' on {item} for export"
                                )
                            else:
                                logging.warning(
                                    f"UV set '{chosen_uv_set}' not found on {item}, FBX will use current default."
                                )
                        except Exception as e:
                            logging.warning(
                                f"Could not set/query UV set on {item}: {e}"
                            )
            else:
                # If "All UV Sets" is chosen but "With Existing UVs" is checked,
                # FBX still needs *a* current set. Default to map1 or first available?
                # Let's try to set map1 as current for consistency.
                for item in selected_items:
                    shapes = cmds.listRelatives(
                        item, shapes=True, fullPath=True, noIntermediate=True
                    )
                    if shapes:
                        try:
                            all_sets = cmds.polyUVSet(
                                shapes[0], query=True, allUVSets=True
                            )
                            if "map1" in all_sets:
                                cmds.polyUVSet(
                                    shapes[0], currentUVSet=True, uvSet="map1"
                                )
                                active_uv_set_for_export = "map1"  # Explicitly track
                        except Exception:
                            pass  # Ignore errors here
        else:
            # Not sending existing UVs, ensure map1 is current for FBX structure if it exists
            for item in selected_items:
                shapes = cmds.listRelatives(
                    item, shapes=True, fullPath=True, noIntermediate=True
                )
                if shapes:
                    try:
                        all_sets = cmds.polyUVSet(shapes[0], query=True, allUVSets=True)
                        if "map1" in all_sets:
                            cmds.polyUVSet(shapes[0], currentUVSet=True, uvSet="map1")
                            active_uv_set_for_export = "map1"
                    except Exception:
                        pass  # Ignore errors here
        # --- Constraint Warning (remains the same) ---
        constraint_nodes = cmds.listConnections(selected_items, type="constraint")
        if constraint_nodes:
            logging.warning(
                f"Scene selection contains constraints: {list(set(constraint_nodes))}. Geometry position might differ unless baked."
            )
        # --- FBX Export (Use updated path) ---
        try:
            # Set FBX options via MEL (usually stable)
            mel.eval("FBXExportSmoothingGroups -v true;")
            mel.eval("FBXExportTriangulate -v false;")
            mel.eval("FBXExportSmoothMesh -v false;")  # Export subdivision preview? No.
            mel.eval("FBXExportConstraints -v false;")
            mel.eval("FBXExportBakeComplexAnimation -v false;")
            mel.eval("FBXExportUpAxis Y;")
            # Ensure the directory exists before exporting
            Path(fbx_export_path_str).parent.mkdir(parents=True, exist_ok=True)
            cmds.file(
                fbx_export_path_str,  # Use string path from config manager
                force=True,
                options="v=0;",
                type="FBX export",
                pr=False,  # Export selected only
                es=True,  # Export selected only
            )
            self.set_feedback(f"Exported selection to FBX.", level="info")
            logging.info(f"Exported selection to: {fbx_export_path_str}")
        except Exception as e:
            self.set_feedback(f"Error during FBX export: {e}", level="error")
            logging.error(f"FBX Export to {fbx_export_path_str} failed.", exc_info=True)
            return
        # --- Lua Script Generation (Use updated path, ensure proper quoting) ---
        quality_levels = {
            0: 128,
            1: 256,
            2: 512,
            3: 1024,
            4: 2048,
        }  # Rizom packer resolution
        quality = quality_levels.get(self.config.pack_quality, 512)
        iterations = self.config.pack_iterations
        # Use forward slashes for Lua paths, escape backslashes if any remain (shouldn't with pathlib)
        # Ensure paths are properly quoted within the Lua string
        lua_fbx_path = fbx_export_path_str.replace("\\", "/")
        lua_script_parts = []
        # Load command based on whether existing UVs are included
        load_flags = "XYZ=true"
        if use_existing_uvs:
            load_flags = "XYZUVW=true, UVWProps=true"  # Load geometry AND UVs
        load_cmd_str = f'ZomLoad({{File={{Path="{lua_fbx_path}", ImportGroups=true, {load_flags}}}, NormalizeUVW=false}})'
        lua_script_parts.append(load_cmd_str)
        # Determine target UV set for Rizom operations
        # If "All UV Sets" selected, Rizom will likely operate on its current default (usually map1 if loaded)
        # or create map1 if no UVs were loaded.
        # If a specific set is chosen, we tell Rizom to use it.
        rizom_target_uv_set = "map1"  # Default assumption
        if chosen_uv_set != "All UV Sets":
            rizom_target_uv_set = chosen_uv_set  # Use the specific set chosen in UI
        # Always ensure the target UV set is current in Rizom before operations
        # Rizom automatically creates the set if it doesn't exist on load/command.
        lua_script_parts.append(
            f'ZomUvset({{Mode="SetCurrent", Name="{rizom_target_uv_set}"}})'
        )
        # Add Unfold/Pack commands if packing is requested OR if no existing UVs were sent
        if pack or not use_existing_uvs:
            # Unfold first (standard practice before packing)
            lua_script_parts.append(
                f'ZomUnfold({{PrimType="Island", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, BorderIntersections=true, TriangleFlips=true}})'
            )
            # Then Pack
            lua_script_parts.append(
                f'ZomPack({{ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={{Mode=2}}, Rotate={{Enable=true, Mode=1, Step=90.0}}, Translate=true, LayoutScalingMode=2, MaxMutations={iterations}, Resolution={quality}}})'  # Added Rotate options
            )
        # Save the result back to the same FBX file (overwriting)
        # Ensure UVs are included in the save.
        lua_script_parts.append(
            f'ZomSave({{File={{Path="{lua_fbx_path}", UVWProps=true}}, __UpdateUIObjFileName=true}})'
        )
        # Add Quit command if we always launch a new instance? Optional.
        # lua_script_parts.append('ZomQuit()') # Add this if needed
        # --- Write Lua Script ---
        lua_script = "\n".join(lua_script_parts)
        try:
            # Ensure directory exists before writing
            Path(lua_script_path_str).parent.mkdir(parents=True, exist_ok=True)
            with open(
                lua_script_path_str, "w", encoding="utf-8"
            ) as f:  # Specify encoding
                f.write(lua_script)
            logging.info(f"Generated Lua script: {lua_script_path_str}")
            logging.debug(f"Lua Script Content:\n{lua_script}")
        except IOError as e:
            self.set_feedback(f"Error writing Lua script: {e}", level="error")
            logging.error(
                f"Failed writing Lua script to {lua_script_path_str}", exc_info=True
            )
            return
        # --- Launch RizomUV (Simplified - Always launch) ---
        self.set_feedback("Launching RizomUV and executing script...", level="info")
        system = platform.system()
        cmd = []
        cmd_str = ""  # For logging command
        try:
            if system == "Windows":
                # Ensure paths are quoted correctly for Popen when shell=False (preferred)
                # If shell=True is needed, construct the command string carefully.
                # Let's try without shell=True first.
                cmd = [rizom_path_str, "-cfi", lua_script_path_str]
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                cmd_str = " ".join(f'"{c}"' for c in cmd)  # For logging
            elif system == "Darwin":
                # Use 'open -a' for .app bundles
                # Ensure lua script path is passed correctly after --args
                cmd = [
                    "open",
                    "-a",
                    rizom_path_str,
                    "--args",
                    "-cfi",
                    lua_script_path_str,
                ]
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                cmd_str = " ".join(f'"{c}"' for c in cmd)  # For logging
            else:  # Linux
                cmd = [rizom_path_str, "-cfi", lua_script_path_str]
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                cmd_str = " ".join(f'"{c}"' for c in cmd)  # For logging
            # Check process start (briefly) - Rizom might detach quickly
            try:
                stdout, stderr = process.communicate(timeout=5)  # Wait max 5s
                return_code = process.returncode
                stdout_decoded = (
                    stdout.decode(locale.getpreferredencoding(False), errors="replace")
                    if stdout
                    else ""
                )
                stderr_decoded = (
                    stderr.decode(locale.getpreferredencoding(False), errors="replace")
                    if stderr
                    else ""
                )
                if return_code != 0:
                    # Rizom might return non-zero even if script runs, depending on settings/license
                    # Log stderr as warning, but don't necessarily fail the operation yet.
                    logging.warning(f"RizomUV process exited with code {return_code}.")
                    if stdout_decoded:
                        logging.warning(f"Rizom stdout: {stdout_decoded}")
                    if stderr_decoded:
                        logging.warning(f"Rizom stderr: {stderr_decoded}")
                    # Allow proceeding, user needs to check Rizom window
                else:
                    logging.info(
                        "RizomUV process executed and exited cleanly (or detached)."
                    )
                    if stdout_decoded:
                        logging.info(f"Rizom stdout: {stdout_decoded}")
                    if stderr_decoded:
                        logging.info(f"Rizom stderr: {stderr_decoded}")
                # Wait a moment for Rizom to potentially process the file
                time.sleep(1.5)
                self.set_feedback("RizomUV launched/script sent.", level="info")
            except subprocess.TimeoutExpired:
                # Process didn't exit quickly, assume it's running in the background
                logging.info("RizomUV process likely running in background.")
                self.set_feedback("RizomUV launched/script sent.", level="info")
        except (subprocess.SubprocessError, FileNotFoundError, Exception) as e:
            self.set_feedback(f"Failed to start RizomUV: {e}", level="error")
            logging.error(f"Command attempted: {cmd_str}", exc_info=True)
            return
        # --- Final Feedback ---
        # Removed the process check and os.utime logic
        final_message = "Sent to RizomUV" if not pack else "Sent to RizomUV for packing"
        self.set_feedback(final_message, level="info")

    def fetch_from_rizom(self):
        # --- Use ConfigManager path ---
        self.feedback_label.setStyleSheet("")
        source_objects = cmds.ls(selection=True, long=True, transforms=True)
        if not source_objects:
            self.set_feedback(
                "Error: No geometry selected for UV import.", level="error"
            )
            return
        # Get the FBX path where Rizom saved the results
        fbx_source_path_str = self.config.get_fbx_export_path_str()
        target_uv_layer = self.uv_selector.currentText()  # Get target set from UI
        logging.info(
            f"Attempting to import from: {fbx_source_path_str} to UV set: {target_uv_layer}"
        )
        fbx_source_path_obj = Path(fbx_source_path_str)
        if not fbx_source_path_obj.is_file():
            self.set_feedback(
                f"Error: Source FBX file not found: {fbx_source_path_str}",
                level="error",
            )
            logging.error(
                f"Cannot find FBX file to import UVs from: {fbx_source_path_str}"
            )
            return
        # --- Namespace Handling (remains the same) ---
        import_namespace = "RIZOMUV_TEMP_NS"
        if cmds.namespace(exists=import_namespace):
            try:
                # Attempt to remove with contents first
                cmds.namespace(
                    removeNamespace=import_namespace, mergeNamespaceWithRoot=False
                )  # Don't merge!
                logging.info(f"Removed existing namespace: {import_namespace}")
            except RuntimeError as e:
                logging.warning(
                    f"Could not remove namespace {import_namespace} directly: {e}. Deleting contents..."
                )
                try:
                    ns_content = cmds.ls(f"{import_namespace}:*", long=True)
                    if ns_content:
                        cmds.delete(ns_content)
                        logging.info(
                            f"Deleted contents of namespace {import_namespace}."
                        )
                    # Try removing again after deleting contents
                    cmds.namespace(setNamespace=":")  # Go to root
                    cmds.namespace(removeNamespace=import_namespace)
                    logging.info(
                        f"Successfully removed namespace {import_namespace} after deleting contents."
                    )
                except Exception as e_del:
                    logging.error(
                        f"Failed cleanup of namespace {import_namespace}: {e_del}"
                    )
                    # Proceed cautiously, import might fail or pollute main namespace
        # --- FBX Plugin Check (remains the same) ---
        if not cmds.pluginInfo("fbxmaya", loaded=True, query=True):
            # ... (load plugin logic) ...
            try:
                cmds.loadPlugin("fbxmaya")
                logging.info("Loaded fbxmaya plugin.")
            except Exception as e:
                self.set_feedback("Error: Failed to load FBX plugin.", level="error")
                logging.error(f"Failed to load fbxmaya plugin: {e}")
                return
        # --- FBX Import (Use updated path) ---
        imported_nodes = []
        try:
            # Set FBX import options via MEL - turn off UI, import into namespace
            # Check available options in docs if needed
            mel.eval(
                "FBXImportMode -v Exmerge;"
            )  # Merge option might be better? Or Add? Let's try Add first.
            mel.eval("FBXImportMode -v Add;")
            mel.eval("FBXImportGenerateLog -v false;")
            mel.eval("FBXImportProtectDrivenKeys -v false;")
            mel.eval("FBXImportMergeAnimationLayers -v false;")
            mel.eval('FBXImportConvertUnitString "cm";')  # Match Maya default?
            imported_nodes = cmds.file(
                fbx_source_path_str,  # Use string path
                i=True,  # Import
                type="FBX",
                ignoreVersion=True,
                renameAll=True,  # Ensure unique names within namespace
                namespace=import_namespace,  # Import into our temp namespace
                options="fbx",  # Basic options flag
                preserveReferences=False,
                returnNewNodes=True,  # Get list of imported nodes
                prompt=False,  # Don't show Maya's import dialog
                loadReferenceDepth="all",  # Ensure all data loaded if it were referenced (unlikely here)
            )
            logging.info(
                f"Imported FBX from {fbx_source_path_str} into namespace '{import_namespace}'"
            )
        except Exception as e:
            self.set_feedback("Error: Failed to import FBX file.", level="error")
            logging.error(f"FBX Import failed: {e}", exc_info=True)
            # Cleanup namespace if import failed partway
            if cmds.namespace(exists=import_namespace):
                try:
                    cmds.namespace(
                        removeNamespace=import_namespace, mergeNamespaceWithRoot=False
                    )
                except:
                    pass
            return
        # --- Object Matching & UV Transfer (remains largely the same logic) ---
        imported_transforms = cmds.ls(imported_nodes, type="transform", long=True) or []
        logging.debug(f"Nodes reported by import: {imported_nodes}")
        logging.debug(f"Transforms found in imported nodes: {imported_transforms}")
        # Fallback if returnNewNodes didn't give transforms
        if not imported_transforms:
            all_in_ns = cmds.ls(f"{import_namespace}:*", long=True)
            imported_transforms = cmds.ls(all_in_ns, type="transform", long=True)
            if imported_transforms:
                logging.warning(
                    "returnNewNodes did not list transforms, using ls fallback."
                )
            else:
                self.set_feedback(
                    "Error: No transform nodes found after FBX import.", level="error"
                )
                logging.error(
                    f"No transforms found in namespace '{import_namespace}' after import from {fbx_source_path_str}"
                )
                # Cleanup namespace
                if cmds.namespace(exists=import_namespace):
                    try:
                        cmds.namespace(
                            removeNamespace=import_namespace,
                            mergeNamespaceWithRoot=False,
                        )
                    except:
                        pass
                return
        transfer_count = 0
        error_count = 0
        processed_targets = set()  # Track processed original objects
        # --- Match original selection to imported objects by leaf name ---
        for orig_item in source_objects:
            if orig_item in processed_targets:
                continue  # Skip if already processed (e.g., via hierarchy)
            orig_leaf = orig_item.split("|")[-1].split(":")[-1]
            logging.info(f"Processing original: {orig_item} (Leaf: {orig_leaf})")
            matched_import = None
            # Find the corresponding imported object
            for imp_item in imported_transforms:
                imp_leaf = imp_item.split("|")[-1].split(":")[-1]
                # Simple name match (could add vertex count later if needed)
                if imp_leaf == orig_leaf:
                    matched_import = imp_item
                    logging.info(f"Found potential name match: {matched_import}")
                    break  # Found match for this original item
            if matched_import:
                # --- Get source (imported) and target (original) shapes ---
                # ... (shape finding logic remains the same) ...
                source_shapes = (
                    cmds.listRelatives(
                        matched_import,
                        shapes=True,
                        type="mesh",
                        fullPath=True,
                        noIntermediate=True,
                    )
                    or []
                )
                target_shapes = (
                    cmds.listRelatives(
                        orig_item,
                        shapes=True,
                        type="mesh",
                        fullPath=True,
                        noIntermediate=True,
                    )
                    or []
                )
                if not source_shapes or not target_shapes:
                    logging.warning(
                        f"Could not find mesh shapes for match: Src({matched_import}):{source_shapes}, Trg({orig_item}):{target_shapes}"
                    )
                    error_count += 1
                    continue  # Skip to next original item
                src_shape = source_shapes[0]
                trg_shape = target_shapes[0]
                logging.info(
                    f"Transferring from Source Shape: {src_shape} To Target Shape: {trg_shape}"
                )
                # --- UV Set Handling & Transfer ---
                try:
                    src_uv_sets = cmds.polyUVSet(
                        src_shape, query=True, allUVSets=True
                    ) or ["map1"]
                    trg_uv_sets = (
                        cmds.polyUVSet(trg_shape, query=True, allUVSets=True) or []
                    )
                    logging.info(
                        f"Source UV sets found on '{src_shape}': {src_uv_sets}"
                    )
                    logging.info(
                        f"Target UV sets found on '{trg_shape}' before transfer: {trg_uv_sets}"
                    )
                    uv_sets_to_process = []
                    final_target_set_name = (
                        target_uv_layer  # Track the specific set user wants
                    )
                    if target_uv_layer == "All UV Sets":
                        uv_sets_to_process = (
                            src_uv_sets  # Transfer all sets found on source
                        )
                        final_target_set_name = ", ".join(
                            uv_sets_to_process
                        )  # For feedback message
                    elif target_uv_layer in src_uv_sets:
                        uv_sets_to_process = [
                            target_uv_layer
                        ]  # Transfer only the selected set
                    else:
                        logging.warning(
                            f"Requested UV set '{target_uv_layer}' not found on imported source {src_shape}. Skipping transfer for {orig_item}."
                        )
                        error_count += 1
                        continue  # Skip to next original item
                    # --- Perform transfer for each required set ---
                    transfer_successful_for_item = False
                    for uv_set in uv_sets_to_process:
                        # Ensure target UV set exists
                        if uv_set not in trg_uv_sets:
                            try:
                                cmds.polyUVSet(trg_shape, create=True, uvSet=uv_set)
                                logging.info(
                                    f"Created UV set '{uv_set}' on target {trg_shape}"
                                )
                            except Exception as e_create:
                                logging.error(
                                    f"Failed to create UV set '{uv_set}' on {trg_shape}: {e_create}"
                                )
                                error_count += 1
                                continue  # Skip this set for this object
                        # Transfer the UVs for this set
                        try:
                            # Set current sets for transfer (important!)
                            cmds.polyUVSet(src_shape, currentUVSet=True, uvSet=uv_set)
                            cmds.polyUVSet(trg_shape, currentUVSet=True, uvSet=uv_set)
                            cmds.transferAttributes(
                                src_shape,
                                trg_shape,
                                transferPositions=0,
                                transferNormals=0,
                                transferUVs=2,  # Transfer UVs only
                                transferColors=0,
                                sampleSpace=4,  # Component space usually best for UVs
                                sourceUvSpace=uv_set,  # Specify source set
                                targetUvSpace=uv_set,  # Specify target set
                                searchMethod=3,  # Closest to point
                                flipUVs=0,
                                colorBorders=1,
                            )
                            # Delete construction history on target after transfer
                            cmds.delete(trg_shape, constructionHistory=True)
                            logging.info(
                                f"Successfully transferred UV set '{uv_set}' from {src_shape} to {trg_shape}"
                            )
                            transfer_successful_for_item = True
                        except Exception as e_xfer:
                            logging.error(
                                f"Error transferring UV set '{uv_set}' for {orig_item}: {e_xfer}",
                                exc_info=True,
                            )
                            error_count += 1
                            # Don't count this object as fully successful
                    if transfer_successful_for_item:
                        transfer_count += 1  # Count successful object transfers
                    processed_targets.add(
                        orig_item
                    )  # Mark as processed regardless of errors on specific sets
                except Exception as e_setup:
                    logging.error(
                        f"Error during UV transfer setup for {orig_item}: {e_setup}",
                        exc_info=True,
                    )
                    error_count += 1
            else:
                logging.warning(
                    f"No matching imported object found for original: {orig_item}"
                )
                error_count += 1
        # --- Cleanup Imported Nodes and Namespace ---
        if imported_nodes:
            all_in_ns_post = cmds.ls(
                f"{import_namespace}:*", long=True
            )  # Get all nodes currently in NS
            if all_in_ns_post:
                try:
                    # Filter nodes that still exist before deleting
                    valid_nodes_to_delete = [
                        n for n in all_in_ns_post if cmds.objExists(n)
                    ]
                    if valid_nodes_to_delete:
                        cmds.delete(valid_nodes_to_delete)
                        logging.info(
                            f"Deleted {len(valid_nodes_to_delete)} imported nodes from namespace."
                        )
                    else:
                        logging.info(
                            "No valid imported nodes found in namespace to delete."
                        )
                except Exception as e_del_imp:
                    logging.warning(
                        f"Issues during cleanup of imported nodes: {e_del_imp}"
                    )
            else:
                logging.info("No nodes found in import namespace for cleanup.")
        # Remove the namespace itself
        if cmds.namespace(exists=import_namespace):
            try:
                cmds.namespace(setNamespace=":")  # Go to root
                cmds.namespace(removeNamespace=import_namespace)
                logging.info(f"Removed import namespace '{import_namespace}'")
            except Exception as e_ns:
                # This might happen if nodes couldn't be deleted but are still in the NS
                logging.error(
                    f"Failed to remove import namespace '{import_namespace}': {e_ns}"
                )
        # Restore original selection
        cmds.select(source_objects, replace=True)
        self.refresh_uv_options()  # Update UV set dropdown
        # --- Final Feedback ---
        num_processed = len(processed_targets)
        if error_count == 0 and transfer_count > 0:
            self.set_feedback(
                f"UVs successfully imported to {transfer_count} object(s) (Set: {final_target_set_name})",
                level="info",
            )
        elif transfer_count > 0:
            self.set_feedback(
                f"UV import completed for {transfer_count}/{num_processed} objects with {error_count} errors. Check logs.",
                level="warning",
            )
        else:
            self.set_feedback(
                f"UV import failed or no matches found. Check script editor.",
                level="error",
            )

    # --- process_uv_edges and helper methods remain the same ---
    def adjust_angle(self):
        self.edge_angle_threshold = self.angle_adjuster.value()
        logging.info(f"Soften tolerance angle set to {self.edge_angle_threshold}")

    def toggle_tolerance(self):
        self.use_angle_tolerance = self.tolerance_toggle.isChecked()
        logging.info(
            f"Soften tolerance checkbox {'enabled' if self.use_angle_tolerance else 'disabled'}"
        )

    def process_uv_edges(self):
        """
        Softens all edges, hardens UV borders, and optionally applies
        angle-based softening to the selected mesh objects.
        Adaptation of the MEL logic.
        """
        self.feedback_label.setStyleSheet("") # Reset feedback
        selection = cmds.ls(selection=True, long=True, objectsOnly=True)
        if not selection:
            self.set_feedback("Error: No objects or components selected.", level="error")
            return

        target_transforms = set()
        target_shapes = set()

        # --- (Selection processing logic remains the same as previous Python version) ---
        for item in selection:
            node_type = cmds.nodeType(item)
            if node_type == "transform":
                shapes = cmds.listRelatives(item, shapes=True, type="mesh", fullPath=True, noIntermediate=True) or []
                if shapes:
                    target_transforms.add(item)
                    target_shapes.add(shapes[0])
            elif node_type == "mesh":
                parent_transform = cmds.listRelatives(item, parent=True, fullPath=True)
                if parent_transform:
                    target_transforms.add(parent_transform[0])
                    target_shapes.add(item)
            else:
                edges = cmds.filterExpand(item, selectionMask=32, expand=False, fullPath=True)
                if edges:
                    obj = item.split('.')[0]
                    if cmds.objExists(obj) and cmds.nodeType(obj) == "mesh":
                         parent_transform = cmds.listRelatives(obj, parent=True, fullPath=True)
                         if parent_transform:
                              target_transforms.add(parent_transform[0])
                              target_shapes.add(obj)
                    elif cmds.objExists(obj) and cmds.nodeType(obj) == "transform":
                          shapes = cmds.listRelatives(obj, shapes=True, type="mesh", fullPath=True, noIntermediate=True) or []
                          if shapes:
                               target_transforms.add(obj)
                               target_shapes.add(shapes[0])
        # --- (End of Selection Processing) ---

        if not target_shapes:
            self.set_feedback("Error: Selection contains no processable mesh objects.", level="error")
            logging.warning(f"No mesh shapes identified from selection: {selection}")
            return

        processed_count = 0
        cmds.undoInfo(openChunk=True, chunkName="Process UV Edges")
        original_selection = list(target_transforms) # Store transforms to reselect

        try:
            for mesh_shape in target_shapes:
                if not cmds.objExists(mesh_shape):
                     logging.warning(f"Mesh shape {mesh_shape} no longer exists. Skipping.")
                     continue

                parent_transform = cmds.listRelatives(mesh_shape, parent=True, fullPath=True)
                if not parent_transform:
                     logging.warning(f"Could not find parent transform for {mesh_shape}. Skipping.")
                     continue
                current_transform = parent_transform[0]

                logging.info(f"Processing UV edges for: {mesh_shape} (Parent: {current_transform})")

                # --- Start MEL Logic Adaptation ---

                # 1. Soften all edges (Same as MEL Step 2)
                logging.debug(f"Softening all edges on {mesh_shape}")
                cmds.polySoftEdge(mesh_shape, angle=180, constructionHistory=False)

                # 2. Select UV Border Edges (Using MEL command directly - MEL Step 4)
                logging.debug(f"Selecting UV borders on {current_transform}")
                border_edges = []
                try:
                    # Select the transform, as MEL commands often need object context
                    cmds.select(current_transform, replace=True)
                    # Convert selection to edges first? MEL does this.
                    cmds.ConvertSelectionToEdges()
                    # Now select only the UV border components from the edge selection
                    mel.eval("SelectUVBorderComponents;")
                    border_edges = cmds.ls(selection=True, flatten=True)
                    logging.debug(f"Selected UV border edges: {border_edges}")
                except Exception as mel_err:
                    logging.error(f"MEL command 'SelectUVBorderComponents' failed on {current_transform}: {mel_err}")
                    # Deselect components? Go back to object mode?
                    cmds.selectMode(object=True)
                    continue # Skip this mesh if border selection failed

                # 3. Harden UV Border Edges (MEL Step 5)
                if border_edges:
                    edge_components = cmds.filterExpand(border_edges, selectionMask=32)
                    if edge_components:
                        logging.debug(f"Hardening {len(edge_components)} UV border edges.")
                        cmds.polySoftEdge(edge_components, angle=0, constructionHistory=False) # Harden
                    else:
                        logging.info(f"No valid edge components found after border selection for {mesh_shape}.")
                else:
                    logging.info(f"No UV border edges were selected for {mesh_shape}.")

                # 4. Apply Tolerance Softening (If checkbox enabled - Simpler Python approach)
                if self.use_angle_tolerance:
                    # Re-apply soften edge based on the tolerance angle *to the whole mesh*.
                    # This preserves the edges explicitly hardened above (angle=0) but softens others below the threshold.
                    logging.debug(f"Applying tolerance softening ({self.edge_angle_threshold} deg) to {mesh_shape}")
                    cmds.polySoftEdge(mesh_shape, angle=self.edge_angle_threshold, constructionHistory=False)
                # If tolerance is OFF, we do nothing here - edges remain soft except the hardened borders.

                # 5. Delete History (MEL Step 10)
                logging.debug(f"Deleting history on {mesh_shape}")
                cmds.delete(mesh_shape, constructionHistory=True)

                processed_count += 1

        except Exception as e:
            self.set_feedback(f"Error during edge processing: {e}", level="error")
            logging.exception("Edge processing error details:")
            cmds.undoInfo(closeChunk=True)
            cmds.undo()
            if original_selection: cmds.select(original_selection, replace=True)
            return
        finally:
            cmds.undoInfo(closeChunk=True)
            if original_selection: cmds.select(original_selection, replace=True) # Restore selection

        # --- Final Feedback --- (Remains the same)
        if processed_count > 0:
            feedback = f"Processed normals on {processed_count} object(s)."
            self.set_feedback(feedback, level="info")
        else:
            self.set_feedback("No mesh objects successfully processed. Check logs.", level="warning")
            
def fetch_maya_root():
    # --- Remains the same ---
    ptr = omui.MQtUtil.mainWindow()
    if ptr is None:
        logging.error("Could not get Maya main window pointer.")
        return None
    try:
        # Convert pointer to long if necessary (Python 3)
        main_window_ptr = int(ptr)
        return wrapInstance(main_window_ptr, QtWidgets.QWidget)
    except TypeError as e:
        logging.error(f"Could not wrap Maya main window instance: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error wrapping Maya main window: {e}")
        return None


# Store reference to the panel instance globally? Risky. Let launch_tool handle it.
# global rizom_bridge_panel_instance
# rizom_bridge_panel_instance = None
def launch_tool():
    # Define both potential names
    intended_workspace_control_name = "rizomUVBridgeWorkspaceControl"
    panel_object_name = "rizomUVBridgePanelInstance"
    # Derive the potential default name the mixin might create/use
    default_workspace_control_name = panel_object_name + "WorkspaceControl"

    logging.info(f"Launching tool. Intended WC: {intended_workspace_control_name}, Default WC: {default_workspace_control_name}, Panel UI: {panel_object_name}")

    # --- Cleanup Section ---
    # Explicitly check and delete BOTH possible workspace control names

    # 1. Delete the potential default-named control
    if cmds.workspaceControl(default_workspace_control_name, q=True, exists=True):
        logging.warning(f"Found lingering default-named workspace control: {default_workspace_control_name}. Deleting...")
        try:
            cmds.deleteUI(default_workspace_control_name, control=True)
            logging.info(f"Deleted default-named workspace control: {default_workspace_control_name}")
        except Exception as e_del_def_wc:
            logging.error(f"Error deleting default-named workspace control '{default_workspace_control_name}': {e_del_def_wc}")
            # Decide whether to bail out if cleanup fails
            # cmds.warning("Failed to clean up conflicting UI element. Aborting launch.")
            # return None # Option: Abort if cleanup fails

    # 2. Delete the intended-named control (might be redundant if names are same, but safe)
    if intended_workspace_control_name != default_workspace_control_name and \
       cmds.workspaceControl(intended_workspace_control_name, q=True, exists=True):
        logging.info(f"Found intended workspace control: {intended_workspace_control_name}. Deleting...")
        try:
            cmds.deleteUI(intended_workspace_control_name, control=True)
            logging.info(f"Deleted intended workspace control: {intended_workspace_control_name}")
        except Exception as e_del_int_wc:
            logging.error(f"Error deleting intended workspace control '{intended_workspace_control_name}': {e_del_int_wc}")
            # Decide whether to bail out
            # cmds.warning("Failed to clean up conflicting UI element. Aborting launch.")
            # return None # Option: Abort if cleanup fails

    # 3. Delete the panel UI widget itself if it exists separately
    if cmds.control(panel_object_name, exists=True):
        logging.info(f"Found lingering panel UI widget: {panel_object_name}. Deleting...")
        try:
            cmds.deleteUI(panel_object_name, control=True)
            logging.info(f"Deleted panel UI widget: {panel_object_name}")
        except Exception as e_del_ui:
            logging.error(f"Error deleting panel UI widget '{panel_object_name}': {e_del_ui}")
            # Proceed with caution if panel UI deletion fails

    # --- Create Instance and Show ---
    root = fetch_maya_root()
    if root is None:
        # ... (error handling) ...
        return None

    try:
        panel = UVBridgePanel(parent=root) # Panel objectName is set inside __init__

        # ... determine uiScript ...
        module_name = __name__
        actual_module_name = None
        if module_name == "__main__":
             try:
                  script_path = Path(__file__)
                  if script_path.parent.name == INSTALL_SUBDIR_NAME:
                       actual_module_name = f"{INSTALL_SUBDIR_NAME}.{script_path.stem}"
                  else:
                       actual_module_name = script_path.stem
                  logging.debug(f"Guessed module name for uiScript: {actual_module_name}")
             except NameError:
                  logging.warning("Cannot determine module name for uiScript recreation when run directly.")
                  actual_module_name = None
        else:
            actual_module_name = module_name

        recreation_script = ""
        if actual_module_name:
            recreation_script = f"import {actual_module_name}; import importlib; importlib.reload({actual_module_name}); {actual_module_name}.launch_tool()" # Added reload
        else:
            logging.warning("uiScript for workspace control recreation could not be generated.")


        # Explicitly use the INTENDED name when showing
        panel.show(
            dockable=True,
            area="right",
            allowedArea=["right", "left"],
            floating=False,
            label="RizomUV Bridge",
            uiScript=recreation_script,
            workspaceControlName=intended_workspace_control_name # Explicitly pass the intended name
        )

        logging.info(f"RizomUV Bridge panel '{panel_object_name}' launched in workspace control '{intended_workspace_control_name}'.")
        return panel

    except Exception as e:
        # The RuntimeError likely occurs during panel.show()
        logging.error(f"Error launching RizomUV Bridge panel: {e}", exc_info=True)
        # Attempt final cleanup if launch failed
        if cmds.control(panel_object_name, exists=True): cmds.deleteUI(panel_object_name, control=True)
        if cmds.workspaceControl(intended_workspace_control_name, q=True, exists=True): cmds.deleteUI(intended_workspace_control_name, control=True)
        if cmds.workspaceControl(default_workspace_control_name, q=True, exists=True): cmds.deleteUI(default_workspace_control_name, control=True) # Extra check
        return None


# --- Main execution guard ---
if __name__ == "__main__":
    # This allows running the script directly in Maya Script Editor for testing
    # Note: UI recreation via workspace control might not work correctly
    # when run this way because __name__ is "__main__".
    logging.info(f"Executing Rizom Bridge script directly (__name__='{__name__}')")
    launch_tool()
