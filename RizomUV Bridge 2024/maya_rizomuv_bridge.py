import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMayaUI as omui
import maya.utils
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import subprocess
import os
import platform
import sys
import logging
import json
import re as _re
import shutil
import threading
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
CONFIG_FILE_NAME = "settings.json"
STATE_FILE_NAME = "bridge_state.json"
LUA_SCRIPT_FILE_NAME = "rizomuv_control_script.lua"
LIVE_LUA_SCRIPT_FILE_NAME = "rizomuv_livelink_script.lua"
FBX_FILE_NAME = "RizomUVMayaBridge.fbx"
RIZOMUV_LINK_DIR_NAME = "RizomUVLink"
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
                                                                                                                   
> RizomUV - Maya Bridge v3.3.0
     >    https://www.rizomuv.com/virtual-spaces/#bridges   
     >    https://github.com/adevra/RizomUV-2024-Maya-Bridge
                                                                                              
"""
                                                                                                   
PATH_DEFAULTS = {
    "Windows": "C:\\Program Files\\Rizom Lab\\RizomUV 2025.0\\rizomuv.exe",
    "Darwin": "/Applications/RizomUV 2024.1.app",
    "Linux": "/usr/local/bin/rizomuv",
}


def find_rizomuv_installations():
    """Returns discovered RizomUV executable paths, newest first."""
    system = platform.system()
    found = []
    if system == "Windows":
        for pf_var in ("ProgramFiles", "ProgramW6432"):
            program_files = os.environ.get(pf_var)
            if not program_files:
                continue
            rizom_root = Path(program_files) / "Rizom Lab"
            if not rizom_root.is_dir():
                continue
            for child in rizom_root.iterdir():
                exe = child / "rizomuv.exe"
                if exe.is_file():
                    found.append(str(exe))
    elif system == "Darwin":
        apps = Path("/Applications")
        if apps.is_dir():
            for child in apps.iterdir():
                if child.suffix == ".app" and "rizomuv" in child.name.lower():
                    found.append(str(child))
    else:
        for candidate in ("/usr/local/bin/rizomuv", "/usr/bin/rizomuv", "/usr/bin/RizomUV"):
            if Path(candidate).is_file() and os.access(candidate, os.X_OK):
                found.append(candidate)
    return sorted(set(found), reverse=True)

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
        self.state_file_path = self.base_dir / STATE_FILE_NAME
        self.lua_control_file_path = self.base_dir / LUA_SCRIPT_FILE_NAME
        self.live_lua_file_path = self.base_dir / LIVE_LUA_SCRIPT_FILE_NAME
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
        self.use_live_link = platform.system() == "Windows"
        self.pack_presets = {}
        self.active_pack_preset = ""
        self.auto_sync_groups = False
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
                self.use_live_link = bool(
                    config_data.get("useLiveLink", self.use_live_link)
                )
                raw_presets = config_data.get("packPresets", {})
                if isinstance(raw_presets, dict):
                    self.pack_presets = {
                        str(name): sanitize_pack_preset(value)
                        for name, value in raw_presets.items()
                    }
                self.active_pack_preset = str(config_data.get("activePackPreset", ""))
                self.auto_sync_groups = bool(config_data.get("autoSyncGroups", False))
                loaded_log_level_str = config_data.get("logLevel", "ERROR").upper()
                if loaded_log_level_str in ["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"]:
                    self.log_level_str = loaded_log_level_str
                else:
                    logger.warning(f"Invalid log level '{loaded_log_level_str}' found in config. Defaulting to ERROR.")
                    self.log_level_str = "ERROR"
                logger.info(f"Loaded configuration from {self.config_file_path}")
                if not Path(self.rizom_location).exists():
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
        try:
            installations = find_rizomuv_installations()
            if installations:
                logger.info(f"Auto-detected RizomUV installation: {installations[0]}")
                return installations[0]
        except Exception as e_find:
            logger.warning(f"RizomUV auto-detection failed: {e_find}")
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
            "useLiveLink": self.use_live_link,
            "packPresets": self.pack_presets,
            "activePackPreset": self.active_pack_preset,
            "autoSyncGroups": self.auto_sync_groups,
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

    def load_state(self):
        try:
            if self.state_file_path.is_file():
                with open(self.state_file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e_state:
            logger.warning(f"Could not read bridge state file: {e_state}")
        return {}

    def save_state(self, **updates):
        state = self.load_state()
        state.update(updates)
        try:
            self.ensure_storage_exists()
            with open(self.state_file_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=4)
        except Exception as e_state:
            logger.warning(f"Could not write bridge state file: {e_state}")
        return state


def _qwidget_is_valid(widget):
    """True if the underlying C++ Qt object is still alive."""
    if widget is None:
        return False
    try:
        if PYSIDE_VERSION == 6:
            from shiboken6 import isValid
        else:
            from shiboken2 import isValid
        return isValid(widget)
    except Exception:
        return True


def _lua_str(value):
    """Escapes a string for safe embedding in a double-quoted Lua literal."""
    out = []
    for ch in str(value):
        if ch in ('"', "\\"):
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ord(ch) < 32 or ord(ch) > 126:
            out.append("".join(f"\\{b}" for b in ch.encode("utf-8")))
        else:
            out.append(ch)
    return "".join(out)


DEFAULT_PACK_PRESET = {
    "paddingPx": 8,
    "marginPx": 4,
    "mapResolution": 1024,
    "maxMutations": 512,
    "tileRows": 1,
    "tileCols": 1,
    "scalingMode": 2,
}

AUTO_UNWRAP_ALGORITHMS = {
    "Mosaic": {
        "label": "Developability",
        "default": 0.5, "min": 0.0, "max": 1.0, "decimals": 2, "hasParam": True,
        "params": lambda v: {"QuasiDevelopable": {"Developability": float(v)}},
    },
    "Hierarchical": {
        # Auto.Skeleton.SegLevels crashes RizomUV 2025.0.114 (0xC0000409);
        # only the safe defaults + Open are sent.
        "label": "(no parameter)",
        "default": 0, "min": 0, "max": 0, "decimals": 0, "hasParam": False,
        "params": lambda v: {"Skeleton": {"Open": True}},
    },
    "Sharp Edges": {
        "label": "Angle Min",
        "default": 30.0, "min": 1.0, "max": 180.0, "decimals": 1, "hasParam": True,
        "params": lambda v: {"SharpEdges": {"AngleMin": float(v)}},
    },
}

_PRESET_FIELD_TYPES = {
    "paddingPx": int, "marginPx": int, "mapResolution": int,
    "maxMutations": int, "tileRows": int, "tileCols": int, "scalingMode": int,
}


def sanitize_pack_preset(data):
    """Returns a full preset dict: defaults filled, types coerced, unknown keys dropped."""
    preset = dict(DEFAULT_PACK_PRESET)
    for key, caster in _PRESET_FIELD_TYPES.items():
        if isinstance(data, dict) and key in data:
            try:
                preset[key] = caster(data[key])
            except (TypeError, ValueError):
                logger.warning(f"Pack preset field '{key}' invalid: {data[key]!r}; using default.")
    preset["tileRows"] = max(1, preset["tileRows"])
    preset["tileCols"] = max(1, preset["tileCols"])
    preset["mapResolution"] = max(64, preset["mapResolution"])
    return preset


def build_pack_params(preset, version_tuple):
    """Builds the Pack task parameter table for the connected RizomUV version."""
    p = sanitize_pack_preset(preset)
    params = {
        "RootGroup": "RootGroup",
        "WorkingSet": "Visible",
        "RecursionDepth": 1,
        "ProcessTileSelection": False,
        "Scaling": {"Mode": p["scalingMode"]},
        "LayoutScalingMode": 2,
        "MaxMutations": p["maxMutations"],
        "Resolution": p["mapResolution"],
        "MapResolution": p["mapResolution"],
    }
    if version_tuple[0] >= 2025:
        params.update({
            "UsePixelUnit": True,
            "PaddingSizePx": p["paddingPx"],
            "MarginSizePx": p["marginPx"],
            "Rotate": {"Step": 90.0},
        })
    else:
        params.update({
            "PaddingSize": float(p["paddingPx"]) / p["mapResolution"],
            "MarginSize": float(p["marginPx"]) / p["mapResolution"],
            "Translate": True,
            "Rotate": {"Mode": 1, "Step": 90.0},
        })
    return params


def build_pack_sequence(preset, version_tuple):
    """Builds the full (task_name, params) sequence for a pack operation."""
    p = sanitize_pack_preset(preset)
    sequence = []
    if p["tileRows"] > 1 or p["tileCols"] > 1:
        sequence.append(
            ("IslandGroups", {"Mode": "SetMultiTileLayout",
                              "TileRows": p["tileRows"], "TileColumns": p["tileCols"]})
        )
        sequence.append(
            ("IslandGroups", {"Mode": "DistributeInTilesByBBox",
                              "WorkingSet": "Visible", "MergingPolicy": 8322})
        )
    else:
        sequence.append(
            ("IslandGroups", {"Mode": "DistributeInTilesByBBox",
                              "WorkingSet": "Visible", "MergingPolicy": 8322})
        )
        sequence.append(
            ("IslandGroups", {"Mode": "DistributeInTilesEvenly",
                              "WorkingSet": "Visible", "MergingPolicy": 8322,
                              "UseTileLocks": True, "UseIslandLocks": True})
        )
    sequence.append(("Pack", build_pack_params(p, version_tuple)))
    return sequence


def build_auto_unwrap_sequence(algorithm, value, iterations):
    """Select auto-seams -> Cut -> Unfold, per the chosen algorithm."""
    algo = AUTO_UNWRAP_ALGORITHMS[algorithm]
    select_params = {
        "PrimType": "Edge",
        "WorkingSet": "Visible",
        "Select": True,
        "ResetBefore": True,
        "Auto": algo["params"](value),
    }
    return [
        ("Select", select_params),
        ("Cut", {"PrimType": "Edge", "WorkingSet": "Visible"}),
        # PrimType Island: process ALL islands of the working set. The default
        # (Edge) intersects with the edge selection and silently does nothing
        # when the selection is empty.
        (
            "Unfold",
            {
                "PrimType": "Island",
                "WorkingSet": "Visible&UnLocked",
                "Iterations": int(iterations),
            },
        ),
    ]


def maya_safe_set_name(prefix, name):
    """Sanitizes a Rizom group/tag name into a legal Maya node name."""
    safe = _re.sub(r"[^A-Za-z0-9_]", "_", str(name))
    if safe and safe[0].isdigit():
        safe = "_" + safe
    return prefix + safe


def tile_name_to_udim(name):
    """'Tile_<col>_<row>' -> UDIM number, else None."""
    m = _re.fullmatch(r"Tile_(\d+)_(\d+)", str(name))
    if not m:
        return None
    col, row = int(m.group(1)), int(m.group(2))
    return 1001 + col + 10 * row


def map_scene_polys_to_objects(sent_face_counts):
    """[[longName, faceCount], ...] (export order) -> [(name, start, end), ...]."""
    ranges = []
    cursor = 0
    for entry in sent_face_counts or []:
        name, count = entry[0], int(entry[1])
        ranges.append((name, cursor, cursor + count))
        cursor += count
    return ranges


def build_reflection_sets(reflection, sent_face_counts):
    """Maps Rizom groups/tags/tiles to per-object Maya face lists.

    Returns {} when the recorded face counts do not cover the polygon table
    (topology changed since Send — syncing would mis-assign faces).
    """
    poly_to_island = reflection.get("polyToIsland") or []
    ranges = map_scene_polys_to_objects(sent_face_counts)
    total = ranges[-1][2] if ranges else 0
    if total != len(poly_to_island):
        logger.error(
            f"Reflection mismatch: {len(poly_to_island)} scene polys vs "
            f"{total} recorded faces. Re-Send before syncing groups."
        )
        return {}
    island_to_polys = {}
    for poly_id, island_id in enumerate(poly_to_island):
        island_to_polys.setdefault(island_id, []).append(poly_id)

    def faces_for_islands(island_ids):
        per_object = {}
        for island_id in island_ids or []:
            for poly_id in island_to_polys.get(island_id, []):
                for name, start, end in ranges:
                    if start <= poly_id < end:
                        per_object.setdefault(name, []).append(poly_id - start)
                        break
        return {name: sorted(faces) for name, faces in per_object.items()}

    sets = {}
    for group_name, info in (reflection.get("groups") or {}).items():
        if info.get("isTile"):
            udim = tile_name_to_udim(group_name)
            set_name = (
                f"RZM_tile_{udim}" if udim
                else maya_safe_set_name("RZM_tile_", group_name)
            )
        else:
            set_name = maya_safe_set_name("RZM_grp_", group_name)
        faces = faces_for_islands(info.get("islandIDs"))
        if faces:
            sets[set_name] = faces
    for tag_name, island_ids in (reflection.get("tags") or {}).items():
        faces = faces_for_islands(island_ids)
        if faces:
            sets[maya_safe_set_name("RZM_tag_", tag_name)] = faces
    return sets


import hashlib as _hashlib

RIZOM_COLOR_SET = "rizomGroups"


def group_color(name):
    """Stable, well-distributed RGB (0-255) for a group name — same name always
    maps to the same visually distinct color."""
    h = _hashlib.md5(str(name).encode("utf-8")).digest()
    hue = h[0] / 255.0
    sat = 0.55 + (h[1] / 255.0) * 0.35
    val = 0.65 + (h[2] / 255.0) * 0.30
    i = int(hue * 6.0)
    f = hue * 6.0 - i
    p = val * (1.0 - sat)
    q = val * (1.0 - f * sat)
    t = val * (1.0 - (1.0 - f) * sat)
    r, g, b = [
        (val, t, p), (q, val, p), (p, val, t),
        (p, q, val), (t, p, val), (val, p, q),
    ][i % 6]
    return (int(r * 255), int(g * 255), int(b * 255))


def _strip_rzm_prefix(set_name):
    for pref in ("RZM_grp_", "RZM_tile_", "RZM_tag_"):
        if set_name.startswith(pref):
            return set_name[len(pref):]
    return set_name


def apply_group_colors(set_names):
    """Colors each RZM_* set's faces by its stable group color, via a dedicated
    'rizomGroups' color set, and turns on per-shape vertex-color display.

    Maya-side, main thread. Returns the number of mesh shapes colored. Purely
    sets mesh attributes — no scene-graph mutation, fully reversible via
    clear_group_colors().
    """
    per_shape = {}
    for set_name in set_names or []:
        label = _strip_rzm_prefix(set_name)
        rgb = tuple(c / 255.0 for c in group_color(label))
        for comp in cmds.sets(set_name, query=True) or []:
            node = comp.split(".")[0]
            if not cmds.objExists(node):
                continue
            if cmds.nodeType(node) == "transform":
                shapes = cmds.listRelatives(
                    node, shapes=True, type="mesh", noIntermediate=True, fullPath=True
                ) or []
            else:
                shapes = [node]
            if not shapes:
                continue
            per_shape.setdefault(shapes[0], []).append((comp, rgb))
    count = 0
    for shape, items in per_shape.items():
        try:
            existing = cmds.polyColorSet(shape, query=True, allColorSets=True) or []
            if RIZOM_COLOR_SET not in existing:
                cmds.polyColorSet(
                    shape, create=True, colorSet=RIZOM_COLOR_SET, representation="RGB"
                )
            cmds.polyColorSet(shape, currentColorSet=True, colorSet=RIZOM_COLOR_SET)
            for comp, rgb in items:
                cmds.polyColorPerVertex(comp, colorRGB=rgb)
            cmds.setAttr(shape + ".displayColors", 1)
            count += 1
        except Exception as e_color:
            logger.warning(f"Could not color group faces on {shape}: {e_color}")
    return count


def clear_group_colors():
    """Removes the 'rizomGroups' color set from all meshes and turns off the
    per-shape vertex-color display."""
    for shape in cmds.ls(type="mesh", long=True) or []:
        try:
            sets_on_shape = cmds.polyColorSet(shape, query=True, allColorSets=True) or []
            if RIZOM_COLOR_SET in sets_on_shape:
                cmds.polyColorSet(shape, delete=True, colorSet=RIZOM_COLOR_SET)
                cmds.setAttr(shape + ".displayColors", 0)
        except Exception as e_clear:
            logger.debug(f"Clear colors on {shape}: {e_clear}")


config = None


def _ensure_config():
    global config
    if config is None:
        try:
            config = ConfigManager()
        except Exception as e_cfg:
            logger.critical(
                f"Failed to initialize ConfigManager: {e_cfg}", exc_info=True
            )
    return config


_ensure_config()


class _LaunchTimeout(Exception):
    """RizomUV launched but never serviced the readiness query."""


class RizomLinkManager:
    """Manages a persistent RizomUV instance driven through RizomUVLink (ZMQ).

    Windows-only: the RizomUVLink module ships compiled .pyd binaries for
    Windows Python only. On other platforms available() is always False and
    the bridge falls back to the classic -cfi Lua workflow.
    """

    # Per-launch readiness wait. Normally RizomUV answers in a few seconds;
    # 30s tolerates a slow cold start while letting a hung launch (see
    # ensure_running) fall through to a retry reasonably fast.
    READY_TIMEOUT_SEC = 30
    DEFAULT_TIMEOUT_MS = 10 * 60 * 1000
    PACK_TIMEOUT_MS = 60 * 60 * 1000

    def __init__(self, cfg):
        self.config = cfg
        self._link = None
        self._port = None
        self._proc = None
        self._module = None
        self._import_error = None
        self._lock = threading.Lock()

    def available(self):
        if platform.system() != "Windows":
            return False
        return self._import_link_module() is not None

    def status_text(self):
        if platform.system() != "Windows":
            return "Live Link is Windows-only"
        if self._import_link_module() is None:
            return f"RizomUVLink unavailable: {self._import_error}"
        if self.is_connected():
            return f"Live Link connected (port {self._port})"
        return "Live Link ready (RizomUV not running)"

    def _candidate_link_dirs(self):
        dirs = []
        rizom_path = Path(str(self.config.rizom_location))
        if rizom_path.is_file():
            dirs.append(rizom_path.parent / RIZOMUV_LINK_DIR_NAME)
        dirs.append(self.config.base_dir / RIZOMUV_LINK_DIR_NAME)
        return [d for d in dirs if (d / "RizomUVLink.py").is_file()]

    def _import_link_module(self):
        if self._module is not None:
            return self._module
        if "RizomUVLink" in sys.modules:
            self._module = sys.modules["RizomUVLink"]
            return self._module
        errors = []
        for link_dir in self._candidate_link_dirs():
            link_dir_str = str(link_dir)
            added = False
            try:
                if link_dir_str not in sys.path:
                    sys.path.insert(0, link_dir_str)
                    added = True
                import RizomUVLink as _rizomuvlink_mod

                self._module = _rizomuvlink_mod
                logger.info(f"Imported RizomUVLink from: {link_dir_str}")
                return self._module
            except Exception as e_import:
                errors.append(f"{link_dir_str}: {e_import}")
                if added:
                    sys.path.remove(link_dir_str)
                for mod_name in ("RizomUVLink", "RizomUVLinkBase", "win"):
                    sys.modules.pop(mod_name, None)
        if not errors:
            errors.append("no RizomUVLink folder found next to rizomuv.exe or in RZMUV")
        self._import_error = "; ".join(errors)
        logger.warning(f"RizomUVLink import failed: {self._import_error}")
        return None

    def is_connected(self):
        if self._link is None or self._port is None:
            return False
        try:
            self._link.rizomuv.Execute("Get", "Vars.Infos.Version.Full", 5000)
            return True
        except Exception:
            # A timed-out probe breaks the ZMQ REQ socket; the link object
            # must be discarded by the caller.
            return False

    def _try_reconnect(self):
        """Reconnects to a RizomUV instance from a previous Maya session/reload.

        Returns True on success, False if no instance is listening on the saved
        port. Raises if something IS listening but not answering (a busy
        RizomUV mid-operation) — launching a second instance in that case would
        orphan the user's session and burn a license token.
        """
        state = self.config.load_state()
        port = state.get("livePort")
        if not port:
            return False
        module = self._import_link_module()
        if module is None:
            return False
        link = module.CRizomUVLink()
        try:
            port_occupied = link.TCPPortIsOpen(port)
        except Exception:
            port_occupied = False
        if not port_occupied:
            return False
        try:
            link.Connect(port)
            link.rizomuv.Execute("Get", "Vars.Infos.Version.Full", 10000)
            self._link = link
            self._port = port
            logger.info(f"Reconnected to running RizomUV on port {port}.")
            return True
        except Exception as e_reconnect:
            raise RuntimeError(
                f"A process on port {port} (probably a busy RizomUV) is not "
                f"answering. Wait for RizomUV to finish its current operation "
                f"and try again. ({e_reconnect})"
            )

    def require_connected(self):
        """Returns the link to an already-running RizomUV; never launches one."""
        with self._lock:
            if self.is_connected():
                return self._link
            self._link = None
            self._port = None
            if self._try_reconnect():
                return self._link
            raise RuntimeError(
                "RizomUV is not running (nothing to get). Use 'Send' first."
            )

    LAUNCH_ATTEMPTS = 3

    def ensure_running(self):
        """Returns a connected link, launching RizomUV if needed. Raises on failure.

        RizomUV 2025.0.114 occasionally never services the readiness query after
        launch (its ZMQ server comes up late/not at all — reproduced
        intermittently). Because a timed-out REQ socket is permanently broken,
        we can't re-poll the same instance; instead each attempt is a fresh
        launch on a fresh port, killing the previous hung instance first.
        """
        with self._lock:
            if self.is_connected():
                return self._link
            self._link = None
            self._port = None
            if self._try_reconnect():
                return self._link
            module = self._import_link_module()
            if module is None:
                raise RuntimeError(f"RizomUVLink unavailable: {self._import_error}")
            exe_path = str(self.config.rizom_location)
            if not Path(exe_path).is_file():
                raise RuntimeError(f"RizomUV executable not found: {exe_path}")
            last_error = None
            for attempt in range(1, self.LAUNCH_ATTEMPTS + 1):
                try:
                    return self._launch_and_connect(module, exe_path, attempt)
                except _LaunchTimeout as e_timeout:
                    last_error = e_timeout
                    logger.warning(
                        f"RizomUV launch attempt {attempt}/{self.LAUNCH_ATTEMPTS} "
                        f"did not become ready; retrying with a fresh instance."
                    )
            raise RuntimeError(
                f"RizomUV failed to become ready after {self.LAUNCH_ATTEMPTS} "
                f"launch attempts ({last_error}). It may be showing a dialog "
                f"(license/crash-recovery) — check the RizomUV window, or "
                f"uncheck 'Use Live Link' to use the classic workflow."
            )

    def _launch_and_connect(self, module, exe_path, attempt):
        """One launch + readiness wait. Raises _LaunchTimeout on no-ready."""
        link = module.CRizomUVLink()
        port = None
        for p in range(49152, 65534):
            if not link.TCPPortIsOpen(p):
                port = p
                break
        if port is None:
            raise RuntimeError("No free TCP port found for RizomUV live link.")
        # Dedicated live-link control file, always rewritten to a no-op so a
        # fresh instance can never replay a stale script at startup. The
        # classic workflow uses a separate file (LUA_SCRIPT_FILE_NAME).
        lua_stub_path = str(self.config.live_lua_file_path)
        try:
            Path(lua_stub_path).parent.mkdir(parents=True, exist_ok=True)
            with open(lua_stub_path, "w", encoding="utf-8") as f:
                f.write("-- RizomUV Maya Bridge live-link control file --\n")
        except OSError as e_stub:
            logger.warning(f"Could not prepare Lua control file: {e_stub}")
        cmd = [exe_path, "-cfi", lua_stub_path, "-id", str(port)]
        logger.info(f"Launching RizomUV live link (attempt {attempt}): {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, cwd=str(Path(exe_path).parent))
        self._proc = proc
        link.Connect(port)
        try:
            version = link.rizomuv.Execute(
                "Get", "Vars.Infos.Version.Full", self.READY_TIMEOUT_SEC * 1000
            )
        except Exception as e_wait:
            self._kill_process(proc)
            self._proc = None
            raise _LaunchTimeout(
                f"no readiness within {self.READY_TIMEOUT_SEC}s ({e_wait})"
            )
        logger.info(f"RizomUV {version} ready on port {port}.")
        self._link = link
        self._port = port
        self.config.save_state(livePort=port)
        return self._link

    @staticmethod
    def _kill_process(proc):
        """Force-kills a launched RizomUV; terminate() alone can leave it up on Windows."""
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass

    def exec_task(self, task_name, params=None, timeout_ms=None):
        """Runs a link task with a long timeout; returns the raw result dict/value."""
        if self._link is None:
            raise RuntimeError("Live link is not connected.")
        timeout = timeout_ms or self.DEFAULT_TIMEOUT_MS
        result = self._link.rizomuv.Execute(task_name, params or {}, timeout)
        if isinstance(result, dict) and result.get("Error"):
            err = result["Error"]
            raise RuntimeError(
                f"RizomUV task '{task_name}' failed: {err.get('Msg')} (code {err.get('Code')})"
            )
        return result

    def rizom_version_tuple(self):
        try:
            version = self._link.rizomuv.Execute(
                "Get", "Vars.Infos.Version.Full", 5000
            )
            parts = str(version).replace("RizomUV", "").strip().split(".")
            return tuple(int(p) for p in parts[:2])
        except Exception:
            return (2024, 0)

    def has_instance(self):
        """True once a RizomUV instance has been launched or reconnected to."""
        return self._proc is not None or (
            self._link is not None and self._port is not None
        )

    def process_alive(self):
        """Best-effort liveness check for the connected RizomUV instance."""
        if self._proc is not None:
            return self._proc.poll() is None
        if self._link is not None and self._port is not None:
            try:
                return bool(self._link.TCPPortIsOpen(self._port))
            except Exception:
                return False
        return False

    def collect_reflection(self):
        """Walks the connected RizomUV's group/tag trees + polygon table.

        Worker-thread only (no cmds/Qt). Returns the reflection dict for
        build_reflection_sets. Requires an existing connection.
        """
        self.require_connected()
        out = self._link.rizomuv.Execute(
            "Save", {"Data": True, "IndexTable.PolygonIDsToIslandIDs": True},
            self.DEFAULT_TIMEOUT_MS,
        )
        if isinstance(out, dict) and out.get("Error"):
            raise RuntimeError(f"Reflection Save failed: {out['Error']}")
        poly_to_island = (out.get("IndexTable") or {}).get(
            "PolygonIDsToIslandIDs"
        ) or []
        groups = {}

        def walk_children(parent_path):
            try:
                names = self._link.rizomuv.Execute(
                    "ItemNames", parent_path + ".Children", 30000
                ) or []
            except Exception:
                return
            for name in names:
                child_path = f"{parent_path}.Children.{name}"
                island_ids = []
                try:
                    island_ids = self._link.rizomuv.Execute(
                        "Get", child_path + ".IslandIDs", 30000
                    ) or []
                except Exception:
                    pass
                groups[name] = {
                    "islandIDs": list(island_ids),
                    "isTile": tile_name_to_udim(name) is not None,
                }
                walk_children(child_path)

        walk_children("Lib.Mesh.RootGroup")
        tags = {}
        try:
            tag_names = self._link.rizomuv.Execute(
                "ItemNames", "Lib.Mesh.Tags", 30000
            ) or []
            for tag in tag_names:
                try:
                    tags[tag] = list(self._link.rizomuv.Execute(
                        "Get", f"Lib.Mesh.Tags.{tag}.IslandIDs", 30000
                    ) or [])
                except Exception:
                    continue
        except Exception:
            logger.info("Tag tree not readable on this RizomUV; skipping tags.")
        return {"polyToIsland": list(poly_to_island), "groups": groups, "tags": tags}

    def disconnect(self):
        self._link = None
        self._port = None
        self._proc = None


class UVBridgePanel(MayaQWidgetDockableMixin, QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(UVBridgePanel, self).__init__(parent)
        if not _ensure_config():
            raise RuntimeError("UVBridgePanel requires a valid ConfigManager instance.")
        self.config = config
        self.link_mgr = RizomLinkManager(config)
        self._busy = False
        self._op_generation = 0
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
        self._update_ops_enabled()
        logger.info("RizomUV Bridge Panel Initialized.")

    def build_interface(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.addWidget(self._build_settings_group())
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.addTab(self._build_bridge_tab(), "Bridge")
        self.tab_widget.addTab(self._build_ops_tab(), "Rizom Ops")
        self.tab_widget.addTab(self._build_integration_tab(), "Integration")
        main_layout.addWidget(self.tab_widget)
        self.feedback_label = QtWidgets.QLabel("Ready")
        self.feedback_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.feedback_label.setWordWrap(True)
        main_layout.addWidget(self.feedback_label)
        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addStretch()
        self.debug_toggle_btn = QtWidgets.QPushButton()
        self.debug_toggle_btn.setToolTip(
            "Toggle logging level between DEBUG (verbose) and Production (minimal)."
        )
        self.debug_toggle_btn.setCheckable(True)
        self.debug_toggle_btn.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Fixed
        )
        bottom_layout.addWidget(self.debug_toggle_btn)
        main_layout.addLayout(bottom_layout)

    def _build_settings_group(self):
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
        self.live_link_toggle = QtWidgets.QCheckBox("Use Live Link (RizomUVLink)")
        live_link_available = self.link_mgr.available()
        self.live_link_toggle.setChecked(
            bool(self.config.use_live_link) and live_link_available
        )
        self.live_link_toggle.setEnabled(live_link_available)
        if live_link_available:
            self.live_link_toggle.setToolTip(
                "Drive one persistent RizomUV instance over a live connection.\nSend/Get become synchronous and reliable (no stale-file guessing).\nUncheck to use the classic launch-per-operation Lua workflow."
            )
        else:
            self.live_link_toggle.setToolTip(
                f"Live Link unavailable on this machine:\n{self.link_mgr.status_text()}\nThe classic Lua workflow will be used."
            )
        settings_layout.addWidget(self.live_link_toggle)
        settings_group.setLayout(settings_layout)
        return settings_group

    def _build_bridge_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
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
            "Import UVs from RizomUV back onto the selected objects in Maya.\nWith a specific Target/Source UV Set chosen, only that set is transferred;\nwith 'All UV Sets', every matching set is transferred.\nIn Live Link mode RizomUV saves its current state first automatically."
        )
        ops_layout.addWidget(self.retrieve_btn)
        ops_group.setLayout(ops_layout)
        layout.addWidget(ops_group)
        auto_group = QtWidgets.QGroupBox("Rizom Actions")
        auto_layout = QtWidgets.QVBoxLayout()
        self.custom_lua_label = QtWidgets.QLabel("Custom Lua Script (Optional):")
        self.custom_lua_input = QtWidgets.QTextEdit()
        self.custom_lua_input.setPlaceholderText(
            "-- Enter custom Lua commands here.\n-- They run AFTER loading and AFTER setting the UV set."
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
        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)
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
        layout.addWidget(post_group)
        layout.addStretch()
        return tab

    def _build_ops_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        unwrap_group = QtWidgets.QGroupBox("Auto Unwrap")
        unwrap_layout = QtWidgets.QGridLayout()
        unwrap_layout.addWidget(QtWidgets.QLabel("Algorithm:"), 0, 0)
        self.unwrap_algo_combo = QtWidgets.QComboBox()
        self.unwrap_algo_combo.addItems(list(AUTO_UNWRAP_ALGORITHMS.keys()))
        unwrap_layout.addWidget(self.unwrap_algo_combo, 0, 1)
        self.unwrap_param_label = QtWidgets.QLabel("Developability:")
        unwrap_layout.addWidget(self.unwrap_param_label, 1, 0)
        self.unwrap_param_spin = QtWidgets.QDoubleSpinBox()
        unwrap_layout.addWidget(self.unwrap_param_spin, 1, 1)
        self.unwrap_pack_after = QtWidgets.QCheckBox("Pack after unwrap")
        unwrap_layout.addWidget(self.unwrap_pack_after, 2, 0, 1, 2)
        self.auto_unwrap_btn = QtWidgets.QPushButton("Auto Unwrap")
        self.auto_unwrap_btn.setToolTip(
            "One click: exports the selection, runs auto-seams (chosen algorithm)\n> Cut > Unfold in RizomUV, and imports the result back.\nAlways a FRESH unwrap — existing UVs and seams are ignored.\nRequires Live Link."
        )
        unwrap_layout.addWidget(self.auto_unwrap_btn, 3, 0, 1, 2)
        unwrap_group.setLayout(unwrap_layout)
        layout.addWidget(unwrap_group)
        flatten_group = QtWidgets.QGroupBox("Unfold / Optimize")
        flatten_layout = QtWidgets.QGridLayout()
        flatten_layout.addWidget(QtWidgets.QLabel("Iterations:"), 0, 0)
        self.flatten_iterations_spin = QtWidgets.QSpinBox()
        self.flatten_iterations_spin.setRange(1, 1000)
        self.flatten_iterations_spin.setValue(50)
        self.flatten_iterations_spin.setToolTip(
            "Optimization iterations. Higher = better quality, slower.\nUnfold uses this for its post-unfold optimize pass;\nOptimize runs exactly this many iterations."
        )
        flatten_layout.addWidget(self.flatten_iterations_spin, 0, 1)
        flatten_layout.addWidget(QtWidgets.QLabel("Angle/Dist Mix:"), 1, 0)
        self.optimize_mix_spin = QtWidgets.QDoubleSpinBox()
        self.optimize_mix_spin.setRange(0.0, 1.0)
        self.optimize_mix_spin.setSingleStep(0.1)
        self.optimize_mix_spin.setDecimals(2)
        self.optimize_mix_spin.setValue(1.0)
        self.optimize_mix_spin.setToolTip(
            "Optimize objective: 0 = preserve angles, 1 = preserve distances."
        )
        flatten_layout.addWidget(self.optimize_mix_spin, 1, 1)
        self.flatten_protect_check = QtWidgets.QCheckBox("Prevent flips && overlaps")
        self.flatten_protect_check.setToolTip(
            "Unfold only: prevents triangle flips and self-intersecting island borders.\nSlower but cleaner results."
        )
        flatten_layout.addWidget(self.flatten_protect_check, 2, 0, 1, 2)
        self.unfold_btn = QtWidgets.QPushButton("Unfold")
        self.unfold_btn.setToolTip(
            "One click: exports the selection, unfolds all islands in RizomUV,\nand imports the result back. Requires Live Link."
        )
        self.optimize_btn = QtWidgets.QPushButton("Optimize")
        self.optimize_btn.setToolTip(
            "One click: exports the selection, optimizes (relaxes) all islands\nin RizomUV, and imports the result back. Requires Live Link."
        )
        self._ops_tooltips = {
            btn: btn.toolTip()
            for btn in (self.auto_unwrap_btn, self.unfold_btn, self.optimize_btn)
        }
        flatten_layout.addWidget(self.unfold_btn, 3, 0)
        flatten_layout.addWidget(self.optimize_btn, 3, 1)
        flatten_group.setLayout(flatten_layout)
        layout.addWidget(flatten_group)
        pack_group = QtWidgets.QGroupBox("Pack")
        pack_layout = QtWidgets.QGridLayout()
        pack_layout.addWidget(QtWidgets.QLabel("Preset:"), 0, 0)
        self.preset_combo = QtWidgets.QComboBox()
        pack_layout.addWidget(self.preset_combo, 0, 1, 1, 2)
        self.preset_save_btn = QtWidgets.QPushButton("Save…")
        self.preset_delete_btn = QtWidgets.QPushButton("Delete")
        pack_layout.addWidget(self.preset_save_btn, 0, 3)
        pack_layout.addWidget(self.preset_delete_btn, 0, 4)
        pack_layout.addWidget(QtWidgets.QLabel("Padding (px):"), 1, 0)
        self.padding_spin = QtWidgets.QSpinBox()
        self.padding_spin.setRange(0, 256)
        pack_layout.addWidget(self.padding_spin, 1, 1)
        pack_layout.addWidget(QtWidgets.QLabel("Margin (px):"), 1, 2)
        self.margin_spin = QtWidgets.QSpinBox()
        self.margin_spin.setRange(0, 256)
        pack_layout.addWidget(self.margin_spin, 1, 3)
        pack_layout.addWidget(QtWidgets.QLabel("Map Res:"), 2, 0)
        self.mapres_combo = QtWidgets.QComboBox()
        self.mapres_combo.addItems(["128", "256", "512", "1024", "2048", "4096", "8192"])
        pack_layout.addWidget(self.mapres_combo, 2, 1)
        pack_layout.addWidget(QtWidgets.QLabel("Mutations:"), 2, 2)
        self.mutations_spin = QtWidgets.QSpinBox()
        self.mutations_spin.setRange(0, 8192)
        self.mutations_spin.setToolTip("0 = automatic (based on island count)")
        pack_layout.addWidget(self.mutations_spin, 2, 3)
        pack_layout.addWidget(QtWidgets.QLabel("UDIM tiles:"), 3, 0)
        self.tile_rows_spin = QtWidgets.QSpinBox()
        self.tile_rows_spin.setRange(1, 10)
        self.tile_cols_spin = QtWidgets.QSpinBox()
        self.tile_cols_spin.setRange(1, 10)
        tile_layout = QtWidgets.QHBoxLayout()
        tile_layout.addWidget(self.tile_rows_spin)
        tile_layout.addWidget(QtWidgets.QLabel("×"))
        tile_layout.addWidget(self.tile_cols_spin)
        pack_layout.addLayout(tile_layout, 3, 1, 1, 2)
        self.auto_pack_btn = QtWidgets.QPushButton("Auto Pack UV Set")
        self.auto_pack_btn.setToolTip(
            "Live Link: one click — exports the selection, packs it in RizomUV using\nthe settings above, and imports the result back.\nClassic: sends selection + packs the target UV set + saves via Lua\n(legacy quality/iterations from settings); use 'Get UVs' afterwards."
        )
        pack_layout.addWidget(self.auto_pack_btn, 4, 0, 1, 5)
        pack_group.setLayout(pack_layout)
        layout.addWidget(pack_group)
        layout.addStretch()
        self._load_preset_fields(sanitize_pack_preset(
            self.config.pack_presets.get(self.config.active_pack_preset, {})
        ))
        self._refresh_preset_combo()
        self._sync_unwrap_param_widget()
        return tab

    def _load_preset_fields(self, preset):
        self.padding_spin.setValue(preset["paddingPx"])
        self.margin_spin.setValue(preset["marginPx"])
        idx = self.mapres_combo.findText(str(preset["mapResolution"]))
        self.mapres_combo.setCurrentIndex(idx if idx != -1 else 3)
        self.mutations_spin.setValue(preset["maxMutations"])
        self.tile_rows_spin.setValue(preset["tileRows"])
        self.tile_cols_spin.setValue(preset["tileCols"])

    def _current_pack_preset(self):
        return sanitize_pack_preset({
            "paddingPx": self.padding_spin.value(),
            "marginPx": self.margin_spin.value(),
            "mapResolution": int(self.mapres_combo.currentText()),
            "maxMutations": self.mutations_spin.value(),
            "tileRows": self.tile_rows_spin.value(),
            "tileCols": self.tile_cols_spin.value(),
        })

    def _refresh_preset_combo(self):
        self.preset_combo.blockSignals(True)
        try:
            self.preset_combo.clear()
            self.preset_combo.addItem("(unsaved)")
            for name in sorted(self.config.pack_presets):
                self.preset_combo.addItem(name)
            active = self.config.active_pack_preset
            idx = self.preset_combo.findText(active) if active else -1
            self.preset_combo.setCurrentIndex(idx if idx != -1 else 0)
        finally:
            self.preset_combo.blockSignals(False)

    def _on_preset_selected(self):
        name = self.preset_combo.currentText()
        if name in self.config.pack_presets:
            self._load_preset_fields(self.config.pack_presets[name])
            self.config.active_pack_preset = name
        else:
            self.config.active_pack_preset = ""
        self.config.save_config()

    def _save_preset(self):
        result = cmds.promptDialog(
            title="Save Pack Preset", message="Preset name:",
            button=["Save", "Cancel"], defaultButton="Save",
            cancelButton="Cancel", dismissString="Cancel",
            text=self.config.active_pack_preset,
        )
        if result != "Save":
            return
        name = cmds.promptDialog(query=True, text=True).strip()
        if not name:
            self.set_feedback("Preset name cannot be empty.", level="warning")
            return
        self.config.pack_presets[name] = self._current_pack_preset()
        self.config.active_pack_preset = name
        if self.config.save_config():
            self._refresh_preset_combo()
            self.set_feedback(f"Saved pack preset '{name}'.", level="info")
        else:
            self.set_feedback("Error saving preset.", level="error")

    def _delete_preset(self):
        name = self.preset_combo.currentText()
        if name not in self.config.pack_presets:
            self.set_feedback("Select a saved preset to delete.", level="warning")
            return
        del self.config.pack_presets[name]
        if self.config.active_pack_preset == name:
            self.config.active_pack_preset = ""
        self.config.save_config()
        self._refresh_preset_combo()
        self.set_feedback(f"Deleted pack preset '{name}'.", level="info")

    def _sync_unwrap_param_widget(self):
        algo = AUTO_UNWRAP_ALGORITHMS[self.unwrap_algo_combo.currentText()]
        has_param = algo.get("hasParam", True)
        self.unwrap_param_label.setText(algo["label"] + ":" if has_param else algo["label"])
        self.unwrap_param_spin.setVisible(has_param)
        self.unwrap_param_spin.setEnabled(has_param)
        if has_param:
            self.unwrap_param_spin.setDecimals(algo["decimals"])
            self.unwrap_param_spin.setRange(algo["min"], algo["max"])
            self.unwrap_param_spin.setSingleStep(0.05 if algo["decimals"] else 1)
            self.unwrap_param_spin.setValue(algo["default"])

    def _update_ops_enabled(self):
        live = self._live_link_active()
        tooltip_off = "Requires Live Link (enable it in Settings; Windows only)."
        for btn in (self.auto_unwrap_btn, self.unfold_btn, self.optimize_btn, self.sync_groups_btn):
            btn.setEnabled(live and not self._busy)
            btn.setToolTip(self._ops_tooltips[btn] if live else tooltip_off)

    def setup_handlers(self):
        self.transfer_btn.clicked.connect(self.dispatch_manual_send)
        self.retrieve_btn.clicked.connect(self.fetch_from_rizom)
        self.uv_toggle.stateChanged.connect(self.persist_config)
        self.live_link_toggle.toggled.connect(self.persist_config)
        self.browse_btn.clicked.connect(self.locate_rizom)
        self.location_input.editingFinished.connect(self.persist_config)
        self.run_custom_lua_btn.clicked.connect(self.dispatch_custom_lua)
        self.auto_pack_btn.clicked.connect(self.dispatch_auto_pack)
        self.auto_unwrap_btn.clicked.connect(self.dispatch_auto_unwrap)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        self.preset_save_btn.clicked.connect(self._save_preset)
        self.preset_delete_btn.clicked.connect(self._delete_preset)
        self.unwrap_algo_combo.currentIndexChanged.connect(self._sync_unwrap_param_widget)
        self.unfold_btn.clicked.connect(self.dispatch_unfold)
        self.optimize_btn.clicked.connect(self.dispatch_optimize)
        self.sync_groups_btn.clicked.connect(self.dispatch_sync_groups)
        self.sets_list.itemClicked.connect(self._on_set_clicked)
        self.auto_sync_check.toggled.connect(self.persist_config)
        self.color_groups_btn.clicked.connect(self.dispatch_color_groups)
        self.clear_colors_btn.clicked.connect(self.dispatch_clear_colors)
        self.edge_hardener_btn.clicked.connect(self.process_uv_edges)
        self.tolerance_toggle.toggled.connect(self.toggle_tolerance)
        self.angle_adjuster.valueChanged.connect(self.adjust_angle)
        self.debug_toggle_btn.toggled.connect(self.toggle_debug_logging)
        try:
            ui_name = self.objectName()
            logger.debug(f"Cleaning up potential old scriptJobs parented to: {ui_name}")
            all_jobs = cmds.scriptJob(listJobs=True) or []
            for job_str in all_jobs:
                job_str = str(job_str)
                if "SelectionChanged" not in job_str or "refresh_uv_options" not in job_str:
                    continue
                try:
                    job_num = int(job_str.split(":")[0])
                    logger.debug(
                        f"Killing pre-existing SelectionChanged scriptJob: {job_num}"
                    )
                    cmds.scriptJob(kill=job_num, force=True)
                except (ValueError, TypeError):
                    pass
                except Exception as e_kill_check:
                    logger.warning(
                        f"Error killing script job '{job_str}': {e_kill_check}"
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
        if self._live_link_active():
            preset = self._current_pack_preset()
            self._run_ops_roundtrip(
                "Auto Pack",
                lambda link_mgr: build_pack_sequence(
                    preset, link_mgr.rizom_version_tuple()
                ),
                load_uvs=True,
            )
            return
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

    def dispatch_auto_unwrap(self):
        algorithm = self.unwrap_algo_combo.currentText()
        value = self.unwrap_param_spin.value()
        iterations = self.flatten_iterations_spin.value()
        pack_preset = (
            self._current_pack_preset() if self.unwrap_pack_after.isChecked() else None
        )

        def seq_builder(link_mgr):
            sequence = list(build_auto_unwrap_sequence(algorithm, value, iterations))
            if pack_preset is not None:
                sequence.extend(
                    build_pack_sequence(pack_preset, link_mgr.rizom_version_tuple())
                )
            return sequence

        # Fresh unwrap: existing UVs/seams are deliberately ignored so the
        # chosen algorithm fully determines the result.
        self._run_ops_roundtrip(
            f"Auto Unwrap ({algorithm})", seq_builder, load_uvs=False
        )

    def dispatch_unfold(self):
        params = {
            "PrimType": "Island",
            "WorkingSet": "Visible&UnLocked",
            "Iterations": self.flatten_iterations_spin.value(),
        }
        if self.flatten_protect_check.isChecked():
            params["TriangleFlips"] = True
            params["BorderIntersections"] = True
        self._run_ops_roundtrip(
            "Unfold", lambda link_mgr: [("Unfold", params)], load_uvs=True
        )

    def dispatch_optimize(self):
        params = {
            "PrimType": "Island",
            "WorkingSet": "Visible&UnLocked",
            "Iterations": self.flatten_iterations_spin.value(),
            "AngleDistanceMix": self.optimize_mix_spin.value(),
        }
        self._run_ops_roundtrip(
            "Optimize", lambda link_mgr: [("Optimize", params)], load_uvs=True
        )

    def _live_link_active(self):
        return self.live_link_toggle.isChecked() and self.link_mgr.available()

    def _set_busy(self, busy, message=None):
        self._busy = busy
        for btn in (
            self.transfer_btn,
            self.retrieve_btn,
            self.run_custom_lua_btn,
            self.auto_pack_btn,
            self.auto_unwrap_btn,
            self.unfold_btn,
            self.optimize_btn,
            self.sync_groups_btn,
        ):
            btn.setEnabled(not busy)
        self._update_ops_enabled()
        if message:
            self.set_feedback(message, level="info")

    def _run_async(self, work, done, watch_link=False, on_crash=None):
        """Runs `work` on a background thread; calls `done(ok, result)` on Maya's main thread.

        The worker must not touch maya.cmds or Qt widgets — only link/file IO.
        With watch_link=True a main-thread watchdog polls the RizomUV process
        and aborts the operation immediately if it crashes — the blocked ZMQ
        call in the worker cannot be interrupted, so its eventual (stale)
        result is dropped via the generation counter instead. on_crash, if
        given, runs (main thread) after a crash abort instead of the generic
        error message — used for automatic retries.
        """
        self._op_generation += 1
        generation = self._op_generation
        watchdog = None
        if watch_link:
            watchdog = QtCore.QTimer(self)
            watchdog.setInterval(2000)

            def check_process():
                if self._op_generation != generation:
                    watchdog.stop()
                    return
                if not self.link_mgr.has_instance():
                    return
                if not self.link_mgr.process_alive():
                    watchdog.stop()
                    self._op_generation += 1
                    self.link_mgr.disconnect()
                    self._set_busy(False)
                    logger.error("RizomUV process died mid-operation.")
                    if on_crash is not None:
                        on_crash()
                    else:
                        self.set_feedback(
                            "RizomUV is no longer running (crashed or was closed). Operation aborted.",
                            level="error",
                        )

            watchdog.timeout.connect(check_process)
            watchdog.start()

        def deliver(outcome):
            if not _qwidget_is_valid(self):
                logger.warning(
                    "Bridge panel was closed before a background task finished; result dropped."
                )
                return
            if watchdog is not None:
                watchdog.stop()
            if self._op_generation != generation:
                logger.info(
                    "Dropping stale background task result (operation was aborted)."
                )
                return
            done(*outcome)

        def runner():
            try:
                outcome = (True, work())
            except Exception as e_work:
                logger.error(f"Background bridge task failed: {e_work}", exc_info=True)
                outcome = (False, e_work)
            maya.utils.executeDeferred(lambda: deliver(outcome))

        threading.Thread(target=runner, daemon=True).start()

    LONG_TASKS = {"Pack", "Select", "Unfold", "Optimize", "Cut"}

    OPS_CRASH_RETRIES = 2

    def _run_ops_roundtrip(self, description, seq_builder, load_uvs=None, _attempt=0):
        """One-click Rizom op: export selection → load → run tasks → save → import back.

        seq_builder(link_mgr) runs on the worker thread after the link is up
        and returns the (task_name, params) sequence to execute between Load
        and Save — all widget reads must happen before this is called.
        load_uvs: True loads existing UVs, False forces a fresh unwrap (3D
        coords as UVs, no seams), None follows the 'Send With Existing UVs'
        toggle.

        RizomUV 2025.0.114 has a non-deterministic internal race that can
        crash it at Cut shortly after a load (reproduced headless at ~20%,
        unaffected by delays, __Focus, Uvset or NormalizeUVW). The watchdog
        detects the dead process and the whole round trip retries itself up
        to OPS_CRASH_RETRIES times.
        """
        if not self._live_link_active():
            self.set_feedback(f"{description} requires Live Link.", level="warning")
            return
        if self._busy:
            self.set_feedback("A bridge operation is already running.", level="warning")
            return
        selected_items = self._export_selection_for_bridge()
        if not selected_items:
            return

        def handle_crash():
            if _attempt < UVBridgePanel.OPS_CRASH_RETRIES:
                self.set_feedback(
                    f"RizomUV crashed during {description} — retrying "
                    f"({_attempt + 1}/{UVBridgePanel.OPS_CRASH_RETRIES})...",
                    level="warning",
                )
                self._run_ops_roundtrip(
                    description, seq_builder, load_uvs, _attempt=_attempt + 1
                )
            else:
                self.set_feedback(
                    f"{description} failed: RizomUV crashed "
                    f"{UVBridgePanel.OPS_CRASH_RETRIES + 1} times on this mesh "
                    f"(a RizomUV bug). Try the operation from the RizomUV UI "
                    f"via Send/Get instead.",
                    level="error",
                )
        use_existing_uvs = (
            self.uv_toggle.isChecked() if load_uvs is None else bool(load_uvs)
        )
        chosen = self.uv_selector.currentText()
        chosen_uv_set = chosen if chosen != "All UV Sets" else None
        fbx_path = self.config.get_fbx_export_path_str().replace("\\", "/")
        link_mgr = self.link_mgr

        def work():
            link_mgr.ensure_running()
            load_params = {
                "File.Path": fbx_path,
                "File.ImportGroups": True,
                "NormalizeUVW": False,
                "__Focus": True,
            }
            if use_existing_uvs:
                load_params["File.XYZUVW"] = True
                load_params["File.UVWProps"] = True
            else:
                load_params["File.XYZ"] = True
            link_mgr.exec_task("Load", load_params)
            # Uvset only when existing UVs were loaded: on a fresh-unwrap load
            # the switch is meaningless, and the combination Uvset SetCurrent +
            # Auto.QuasiDevelopable Select + Cut crashes RizomUV 2025.0.114
            # with an access violation (0xC0000005).
            if chosen_uv_set and use_existing_uvs:
                link_mgr.exec_task(
                    "Uvset", {"Mode": "SetCurrent", "Name": chosen_uv_set}
                )
            for task_name, params in seq_builder(link_mgr):
                timeout = (
                    RizomLinkManager.PACK_TIMEOUT_MS
                    if task_name in UVBridgePanel.LONG_TASKS
                    else None
                )
                link_mgr.exec_task(task_name, params, timeout_ms=timeout)
            link_mgr.exec_task(
                "Save", {"File.Path": fbx_path, "File.UVWProps": True}
            )
            return True

        def done(ok, result):
            self._set_busy(False)
            if not ok:
                crashed = (
                    self.link_mgr.has_instance()
                    and not self.link_mgr.process_alive()
                )
                self.link_mgr.disconnect()
                if crashed:
                    handle_crash()
                else:
                    self.set_feedback(
                        f"{description} failed: {result}", level="error"
                    )
                return
            self._import_fbx_uvs(selected_items)

        self._set_busy(True, f"Live Link: {description} (one-click round trip)...")
        self._run_async(work, done, watch_link=True, on_crash=handle_crash)

    def _dispatch_live(
        self,
        run_custom_script,
        pack_after,
        use_existing_uvs,
        chosen_uv_set,
        pack_preset=None,
    ):
        if self._busy:
            self.set_feedback("A bridge operation is already running.", level="warning")
            return
        fbx_path = self.config.get_fbx_export_path_str()
        custom_script = (
            self.custom_lua_input.toPlainText().strip() if run_custom_script else ""
        )
        lua_stub_path = str(self.config.live_lua_file_path)
        link_mgr = self.link_mgr

        def work():
            link_mgr.ensure_running()
            load_params = {
                "File.Path": fbx_path.replace("\\", "/"),
                "File.ImportGroups": True,
                "NormalizeUVW": False,
                "__Focus": True,
            }
            if use_existing_uvs:
                load_params["File.XYZUVW"] = True
                load_params["File.UVWProps"] = True
            else:
                load_params["File.XYZ"] = True
            link_mgr.exec_task("Load", load_params)
            if chosen_uv_set:
                link_mgr.exec_task(
                    "Uvset", {"Mode": "SetCurrent", "Name": chosen_uv_set}
                )
            if custom_script:
                with open(lua_stub_path, "w", encoding="utf-8") as f:
                    f.write(
                        "-- Custom Lua from Maya Bridge (executed by RizomUV file watcher) --\n"
                    )
                    f.write(custom_script)
                    f.write("\n")
            if pack_preset:
                sequence = build_pack_sequence(
                    pack_preset, link_mgr.rizom_version_tuple()
                )
                for task_name, params in sequence:
                    timeout = (
                        RizomLinkManager.PACK_TIMEOUT_MS
                        if task_name in UVBridgePanel.LONG_TASKS
                        else None
                    )
                    link_mgr.exec_task(task_name, params, timeout_ms=timeout)
            return True

        def done(ok, result):
            self._set_busy(False)
            if ok:
                if pack_after:
                    msg = "Live Link: packed in RizomUV. Use 'Get UVs' to import."
                elif custom_script:
                    msg = "Live Link: mesh loaded; custom Lua handed to RizomUV. Use 'Get UVs' to import."
                else:
                    msg = "Live Link: mesh loaded in RizomUV. Edit UVs, then 'Get UVs'."
                self.set_feedback(msg, level="info")
            else:
                self.link_mgr.disconnect()
                self.set_feedback(f"Live Link error: {result}", level="error")

        description = "auto pack" if pack_after else (
            "custom script" if run_custom_script else "send"
        )
        self._set_busy(True, f"Live Link: sending to RizomUV ({description})...")
        self._run_async(work, done, watch_link=True)

    def _export_selection_for_bridge(self):
        """Validates the current mesh selection and exports it to the bridge FBX.

        Honors 'Send With Existing UVs' and the Target/Source UV set. Returns
        the exported transform list, or None on failure (feedback already set).
        """
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
        fbx_export_path_str = self.config.get_fbx_export_path_str()
        use_existing_uvs = self.uv_toggle.isChecked()
        chosen_uv_set = self.uv_selector.currentText()
        is_specific_set_selected = chosen_uv_set != "All UV Sets"
        if not cmds.pluginInfo("fbxmaya", loaded=True, query=True):
            try:
                cmds.loadPlugin("fbxmaya", quiet=True)
                logger.info("Loaded fbxmaya plugin.")
            except Exception as e:
                self.set_feedback("Error: Failed to load FBX plugin.", level="error")
                logger.error(f"Failed to load fbxmaya plugin: {e}", exc_info=True)
                return
        original_uv_sets = {}
        if use_existing_uvs and is_specific_set_selected:
            logger.info(f"Targeting UV set '{chosen_uv_set}' for export.")
            for item in selected_items:
                shapes = cmds.listRelatives(
                    item, shapes=True, fullPath=True, noIntermediate=True, type="mesh"
                )
                if not shapes:
                    continue
                shape_node = shapes[0]
                try:
                    all_sets = cmds.polyUVSet(
                        shape_node, query=True, allUVSets=True
                    ) or ["map1"]
                    current_set = cmds.polyUVSet(
                        shape_node, query=True, currentUVSet=True
                    )[0]
                    if chosen_uv_set not in all_sets:
                        logger.warning(
                            f"Chosen set '{chosen_uv_set}' not on {shape_node}; its current set '{current_set}' is exported as-is."
                        )
                        continue
                    if current_set != chosen_uv_set:
                        original_uv_sets[shape_node] = current_set
                        cmds.polyUVSet(
                            shape_node, currentUVSet=True, uvSet=chosen_uv_set
                        )
                        logger.debug(
                            f"Set current UV set to '{chosen_uv_set}' on {shape_node} for export."
                        )
                except Exception as e_set:
                    logger.warning(
                        f"Could not query/set UV set on {shape_node}: {e_set}"
                    )
        elif use_existing_uvs:
            logger.info(
                "Exporting with each mesh's current UV sets ('All UV Sets' selected)."
            )
        else:
            logger.info("Not sending existing UVs; RizomUV will use 3D coords as UVs.")
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
            mel.eval("FBXResetExport;")
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
        try:
            sent_mtime = os.path.getmtime(fbx_export_path_str)
        except OSError:
            sent_mtime = 0
        # Record face counts in FBX EXPORT order, which is DAG traversal order —
        # NOT the selection order in `selected_items`. FBX exportSelected
        # concatenates each mesh's polygons in depth-first DAG order regardless
        # of how the objects were selected, and reflection maps RizomUV's flat
        # polygon table back to objects by these cumulative counts. Recording in
        # selection order silently mis-assigns faces whenever the two differ
        # (verified against RizomUV 2025.0.114). Sorting the selection by its
        # position in the scene DAG reproduces the exporter's order.
        dag_all = cmds.ls(long=True, dag=True, type="transform") or []
        dag_index = {name: i for i, name in enumerate(dag_all)}
        ordered_items = sorted(
            selected_items, key=lambda o: dag_index.get(o, len(dag_all))
        )
        sent_face_counts = []
        for item in ordered_items:
            try:
                sent_face_counts.append(
                    [item, int(cmds.polyEvaluate(item, face=True))]
                )
            except Exception as e_count:
                logger.warning(f"Could not count faces on {item}: {e_count}")
                sent_face_counts = []
                break
        self.config.save_state(
            fbxMtimeAtSend=sent_mtime, sentFaceCounts=sent_face_counts
        )
        return selected_items

    def _dispatch_to_rizom(self, run_custom_script=False, pack_after=False):
        rizom_path_str = str(self.config.rizom_location)
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
        if not self._export_selection_for_bridge():
            return
        quality_levels = {0: 128, 1: 256, 2: 512, 3: 1024, 4: 2048}
        quality_index = self.config.pack_quality
        pack_res = quality_levels.get(quality_index, 512)
        pack_iter = self.config.pack_iterations
        if self._live_link_active():
            self._dispatch_live(
                run_custom_script=run_custom_script,
                pack_after=pack_after,
                use_existing_uvs=use_existing_uvs,
                chosen_uv_set=chosen_uv_set if is_specific_set_selected else None,
                pack_preset=self._current_pack_preset() if pack_after else None,
            )
            return
        lua_fbx_path = _lua_str(str(self.config.fbx_export_file_path).replace("\\", "/"))
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
            lua_safe_set_name = _lua_str(rizom_target_uv_set_name)
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
            exe_to_launch = rizom_path_str
            if system == "Darwin" and rizom_path_str.endswith(".app"):
                exe_to_launch = str(
                    Path(rizom_path_str) / "Contents" / "MacOS" / "RizomUV"
                )
            cmd = [exe_to_launch, "-cfi", lua_script_path_str]
            cmd_str_log = " ".join(f'"{c}"' for c in cmd)
            popen_kwargs = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "cwd": str(Path(exe_to_launch).parent),
            }
            if system == "Windows":
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            logger.info(f"Executing (non-blocking): {cmd_str_log}")
            self._classic_procs = [
                p for p in getattr(self, "_classic_procs", []) if p.poll() is None
            ]
            self._classic_procs.append(subprocess.Popen(cmd, **popen_kwargs))
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
        system = platform.system()
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
                path = QtWidgets.QFileDialog.getExistingDirectory(
                    self,
                    "Locate RizomUV Application (.app)",
                    start_dir,
                    QtWidgets.QFileDialog.Option.ShowDirsOnly
                    | QtWidgets.QFileDialog.Option.DontResolveSymlinks
                    | QtWidgets.QFileDialog.Option.DontUseNativeDialog,
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

    def refresh_uv_options(self):
        self.uv_selector.blockSignals(True)
        try:
            self._refresh_uv_options_impl()
        finally:
            self.uv_selector.blockSignals(False)

    def _refresh_uv_options_impl(self):
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
        new_use_live_link = self.live_link_toggle.isChecked()
        if self.config.use_live_link != new_use_live_link:
            self.config.use_live_link = new_use_live_link
            config_changed = True
            logger.debug(f"Config change: use_live_link = {new_use_live_link}")
        new_auto_sync = self.auto_sync_check.isChecked()
        if self.config.auto_sync_groups != new_auto_sync:
            self.config.auto_sync_groups = new_auto_sync
            config_changed = True
        if config_changed:
            logger.info("Configuration changed, saving...")
            if not self.config.save_config():
                self.set_feedback("Error saving configuration.", level="error")
        else:
            logger.debug("No configuration changes detected, skipping save.")
        self._update_ops_enabled()

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

    def fetch_from_rizom(self):
        """Imports UVs from RizomUV back onto the Maya selection.

        Live Link mode asks the running RizomUV instance to save its current
        state to the bridge FBX first, so the import is never stale. Classic
        mode compares the FBX timestamp against the last Send and warns before
        importing data RizomUV has not (re)saved yet.
        """
        if self._busy:
            self.set_feedback("A bridge operation is already running.", level="warning")
            return
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
        if self._live_link_active():
            link_mgr = self.link_mgr

            def work():
                # Never launch RizomUV from Get: a fresh instance would save
                # its empty scene over the bridge FBX.
                link_mgr.require_connected()
                link_mgr.exec_task(
                    "Save",
                    {
                        "File.Path": fbx_source_path_str.replace("\\", "/"),
                        "File.UVWProps": True,
                    },
                )
                return True

            def done(ok, result):
                self._set_busy(False)
                if not ok:
                    self.link_mgr.disconnect()
                    self.set_feedback(
                        f"Live Link error while saving from RizomUV: {result}",
                        level="error",
                    )
                    return
                self._import_fbx_uvs(target_objects)

            self._set_busy(True, "Live Link: saving current state from RizomUV...")
            self._run_async(work, done, watch_link=True)
            return
        state = self.config.load_state()
        sent_mtime = state.get("fbxMtimeAtSend")
        try:
            current_mtime = os.path.getmtime(fbx_source_path_str)
        except OSError:
            current_mtime = None
        if sent_mtime and current_mtime and current_mtime <= sent_mtime:
            answer = cmds.confirmDialog(
                title="RizomUV Bridge",
                message=(
                    "The bridge FBX has not been re-saved since it was sent to "
                    "RizomUV.\nSave in RizomUV first (the bridge script saves "
                    "automatically when it finishes), or import anyway?"
                ),
                button=["Import Anyway", "Cancel"],
                defaultButton="Cancel",
                cancelButton="Cancel",
                dismissString="Cancel",
            )
            if answer != "Import Anyway":
                self.set_feedback(
                    "Import cancelled: RizomUV has not saved new UVs yet.",
                    level="warning",
                )
                return
        self._import_fbx_uvs(target_objects)

    def _build_integration_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        self.sync_groups_btn = QtWidgets.QPushButton("Sync Groups from RizomUV")
        self.sync_groups_btn.setToolTip(
            "Mirrors RizomUV's island groups, tags and UDIM tiles into Maya\n"
            "selection sets (RZM_grp_*, RZM_tag_*, RZM_tile_*).\n"
            "All existing RZM_* sets are replaced on each sync — they are\n"
            "mirrors, not user data. Requires Live Link and a prior Send."
        )
        layout.addWidget(self.sync_groups_btn)
        self._ops_tooltips[self.sync_groups_btn] = self.sync_groups_btn.toolTip()
        self.auto_sync_check = QtWidgets.QCheckBox("Auto-sync after Get UVs")
        self.auto_sync_check.setChecked(self.config.auto_sync_groups)
        layout.addWidget(self.auto_sync_check)
        layout.addWidget(QtWidgets.QLabel("Synced sets (click to select):"))
        self.sets_list = QtWidgets.QListWidget()
        self.sets_list.setToolTip("Click a set to select its faces in Maya.")
        layout.addWidget(self.sets_list)
        self.udim_summary_label = QtWidgets.QLabel("")
        self.udim_summary_label.setWordWrap(True)
        layout.addWidget(self.udim_summary_label)
        color_row = QtWidgets.QHBoxLayout()
        self.color_groups_btn = QtWidgets.QPushButton("Color Groups")
        self.color_groups_btn.setToolTip(
            "Tint each synced Rizom group/tile's faces with a distinct, stable\n"
            "color (per-island, no bleed) and turn on vertex-color display.\n"
            "Reversible — 'Clear Colors' removes it. Run Sync Groups first."
        )
        self.clear_colors_btn = QtWidgets.QPushButton("Clear Colors")
        self.clear_colors_btn.setToolTip(
            "Remove the Rizom group coloring and turn vertex-color display back off."
        )
        color_row.addWidget(self.color_groups_btn)
        color_row.addWidget(self.clear_colors_btn)
        layout.addLayout(color_row)
        layout.addStretch()
        return tab

    def dispatch_color_groups(self):
        group_sets = cmds.ls("RZM_grp_*", type="objectSet") or []
        if not group_sets:
            group_sets = cmds.ls("RZM_tile_*", type="objectSet") or []
        if not group_sets:
            self.set_feedback(
                "No Rizom group sets to color — run Sync Groups first.",
                level="warning",
            )
            return
        cmds.undoInfo(openChunk=True, chunkName="Color Rizom Groups")
        try:
            count = apply_group_colors(group_sets)
        finally:
            cmds.undoInfo(closeChunk=True)
        if count:
            self.set_feedback(
                f"Colored {count} mesh(es) by Rizom group. Turn on 'Color' in the "
                f"viewport/UV Editor display if not already shown.",
                level="info",
            )
        else:
            self.set_feedback("Nothing colored (no mesh faces in the sets).", level="warning")

    def dispatch_clear_colors(self):
        cmds.undoInfo(openChunk=True, chunkName="Clear Rizom Colors")
        try:
            clear_group_colors()
        finally:
            cmds.undoInfo(closeChunk=True)
        self.set_feedback("Cleared Rizom group coloring.", level="info")

    def _refresh_integration_tab(self, sets):
        self.sets_list.clear()
        tile_lines = []
        for set_name in sorted(sets):
            self.sets_list.addItem(set_name)
            if set_name.startswith("RZM_tile_"):
                per_object = sets[set_name]
                objects = ", ".join(
                    o.split("|")[-1] for o in sorted(per_object)
                )
                faces = sum(len(f) for f in per_object.values())
                tile_lines.append(
                    f"{set_name[len('RZM_tile_'):]}: {faces} faces ({objects})"
                )
        self.udim_summary_label.setText(
            "UDIM tiles:\n" + "\n".join(tile_lines) if tile_lines else ""
        )

    def _on_set_clicked(self, item):
        set_name = item.text()
        if cmds.objExists(set_name):
            cmds.select(set_name, replace=True)
            self.set_feedback(f"Selected {set_name}.", level="info")
        else:
            self.set_feedback(
                f"{set_name} no longer exists — run Sync Groups again.",
                level="warning",
            )

    def _apply_reflection_sets(self, sets):
        """Deletes existing RZM_* sets and creates the new mirrors. Main thread."""
        stale = [
            s for s in (cmds.ls("RZM_*", type="objectSet") or [])
        ]
        if stale:
            cmds.delete(stale)
        created = 0
        for set_name, per_object in sets.items():
            members = []
            for obj, faces in per_object.items():
                if not cmds.objExists(obj):
                    logger.warning(f"Sync: {obj} no longer exists; skipping.")
                    continue
                members.extend(f"{obj}.f[{i}]" for i in faces)
            if not members:
                continue
            new_set = cmds.sets(name=set_name, empty=True)
            cmds.sets(members, include=new_set)
            created += 1
        return created

    def dispatch_sync_groups(self):
        if not self._live_link_active():
            self.set_feedback("Sync Groups requires Live Link.", level="warning")
            return
        if self._busy:
            self.set_feedback("A bridge operation is already running.", level="warning")
            return
        sent_face_counts = self.config.load_state().get("sentFaceCounts") or []
        if not sent_face_counts:
            self.set_feedback(
                "Sync Groups needs a Send first (face counts are recorded at Send).",
                level="warning",
            )
            return
        link_mgr = self.link_mgr

        def work():
            return link_mgr.collect_reflection()

        def done(ok, result):
            self._set_busy(False)
            if not ok:
                self.link_mgr.disconnect()
                self.set_feedback(f"Sync Groups failed: {result}", level="error")
                return
            sets = build_reflection_sets(result, sent_face_counts)
            if not sets:
                self.set_feedback(
                    "Sync Groups: nothing to mirror (no groups/tags, or topology "
                    "changed since Send — re-Send first).",
                    level="warning",
                )
                self._refresh_integration_tab({})
                return
            created = self._apply_reflection_sets(sets)
            self._refresh_integration_tab(sets)
            self.set_feedback(
                f"Synced {created} Rizom group/tag/tile set(s) into Maya.",
                level="info",
            )

        self._set_busy(True, "Live Link: reading groups from RizomUV...")
        self._run_async(work, done, watch_link=True)

    def _import_fbx_uvs(self, target_objects):
        fbx_source_path_str = self.config.get_fbx_export_path_str()
        target_uv_set_name_from_ui = self.uv_selector.currentText()
        specific_uv_set = (
            target_uv_set_name_from_ui
            if target_uv_set_name_from_ui != "All UV Sets"
            else None
        )
        logger.info(
            f"Importing UVs from: {fbx_source_path_str} (Target set: '{target_uv_set_name_from_ui}') on {len(target_objects)} object(s)."
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
            mel.eval("FBXResetImport;")
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
        finally:
            try:
                mel.eval("FBXResetImport;")
            except Exception as e_reset:
                logger.debug(f"FBXResetImport after import failed: {e_reset}")
        imported_transforms = (
            cmds.ls(f"{import_namespace}:*", type="transform", long=True) or []
        )
        if not imported_transforms:
            self.set_feedback(
                "Error: Bridge FBX contained no transforms to import.", level="error"
            )
            logger.error("Imported FBX contained no transforms.")
            self._cleanup_import_namespace(import_namespace)
            return

        def fbx_leaf_name(node_path):
            # Maya's FBX exporter writes 'ns:obj' as 'ns_obj'; mirror that here
            # so namespaced/referenced targets still match the imported copies.
            return node_path.split("|")[-1].replace(":", "_")

        imports_by_leaf = {}
        for imp_transform in imported_transforms:
            imports_by_leaf.setdefault(
                imp_transform.split("|")[-1].split(":", 1)[-1], []
            ).append(imp_transform)
        targets_by_leaf = {}
        for target_transform in set(target_objects):
            targets_by_leaf.setdefault(fbx_leaf_name(target_transform), []).append(
                target_transform
            )
        transfer_count = 0
        error_count = 0
        processed_targets = set()
        rollback_needed = False
        cmds.undoInfo(openChunk=True, chunkName="Fetch Rizom UVs")
        try:
            for target_transform in target_objects:
                if target_transform in processed_targets:
                    continue
                processed_targets.add(target_transform)
                target_leaf_name = fbx_leaf_name(target_transform)
                logger.debug(
                    f"Processing target: {target_transform} (FBX leaf name: {target_leaf_name})"
                )
                candidates = imports_by_leaf.get(target_leaf_name, [])
                if len(targets_by_leaf.get(target_leaf_name, [])) > 1 or len(candidates) > 1:
                    logger.error(
                        f"Ambiguous name '{target_leaf_name}': multiple selected or imported objects share it. Skipping {target_transform} to avoid transferring the wrong UVs. Rename the objects uniquely and resend."
                    )
                    error_count += 1
                    continue
                matched_import_source = candidates[0] if candidates else None
                if not matched_import_source:
                    logger.warning(
                        f"No matching imported object for target: {target_transform}"
                    )
                    error_count += 1
                    continue
                logger.info(f"Matched imported object: {matched_import_source}")
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
                    if specific_uv_set and specific_uv_set not in src_uv_sets:
                        logger.error(
                            f"UV set '{specific_uv_set}' not found in RizomUV output for {target_transform} (has: {src_uv_sets}). Skipping."
                        )
                        error_count += 1
                        continue
                    sets_to_ensure = (
                        [specific_uv_set] if specific_uv_set else src_uv_sets
                    )
                    created_sets_count = 0
                    for s_set in sets_to_ensure:
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
                    if specific_uv_set:
                        cmds.transferAttributes(
                            src_shape,
                            trg_shape,
                            transferPositions=0,
                            transferNormals=0,
                            transferUVs=1,
                            sourceUvSet=specific_uv_set,
                            targetUvSet=specific_uv_set,
                            transferColors=0,
                            sampleSpace=5,
                            searchMethod=3,
                        )
                        logger.info(
                            f"Transferred UV set '{specific_uv_set}' from '{src_shape}' to '{trg_shape}'."
                        )
                    else:
                        cmds.polyTransfer(
                            trg_shape,
                            ao=src_shape,
                            uv=True,
                            v=False,
                            vc=False,
                            ch=False,
                        )
                        logger.info(
                            f"Ran polyTransfer (uv=True) from '{src_shape}' to '{trg_shape}' (all matching sets)."
                        )
                    transfer_successful_for_object = True
                    try:
                        cmds.delete(trg_shape, constructionHistory=True)
                    except Exception as e_hist:
                        if specific_uv_set:
                            # transferAttributes is a live history node; if it
                            # cannot be baked (e.g. referenced mesh), deleting
                            # the imported source would destroy the result.
                            try:
                                cmds.bakePartialHistory(trg_shape, prePostDeformers=True)
                                logger.info(
                                    f"Baked transferAttributes history on {trg_shape} (delete failed: {e_hist})"
                                )
                            except Exception as e_bake:
                                logger.error(
                                    f"Could not bake/delete transfer history on {trg_shape}: {e_bake}. Skipping this object."
                                )
                                transfer_successful_for_object = False
                                error_count += 1
                        else:
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
            rollback_needed = True
            self.set_feedback(
                "Critical error during UV transfer. Rolled back.", level="error"
            )
        finally:
            cmds.undoInfo(closeChunk=True)
            if rollback_needed:
                try:
                    cmds.undo()
                except Exception as e_undo:
                    logger.warning(f"Rollback undo failed: {e_undo}")
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
                f"UVs imported to {transfer_count} object(s) ({'set ' + repr(specific_uv_set) if specific_uv_set else 'all matching sets'}).",
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
        if (
            getattr(self.config, "auto_sync_groups", False)
            and self._live_link_active()
            and transfer_count > 0
        ):
            maya.utils.executeDeferred(self.dispatch_sync_groups)

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
            selection, sm=(31, 32, 34, 35), expand=True, fullPath=True
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
        rollback_needed = False
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
            rollback_needed = True
        finally:
            cmds.undoInfo(closeChunk=True)
            if rollback_needed:
                try:
                    cmds.undo()
                except Exception as e_undo:
                    logger.warning(f"Rollback undo failed: {e_undo}")
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
    intended_workspace_control_name = WORKSPACE_CONTROL_NAME
    panel_object_name = "rizomUVBridgePanelInstance"
    window_title = "RizomUV <> Maya Bridge v3.3.0"
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
    if not _ensure_config():
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
    global PYSIDE_VERSION
    workspace_control_name = WORKSPACE_CONTROL_NAME
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
        if not _ensure_config():
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
