![ssbridge.png](https://blog.anildevran.com/content/images/2025/02/rizomuvmayabridgecover_adev.png)

# RIZOM UV 2024 - Autodesk MAYA Bridge

**Version 3.1.3** | **Author:** A. Devran | **GitHub:** [https://github.com/adevra/RizomUV-2024-Maya-Bridge](https://github.com/adevra/RizomUV-2024-Maya-Bridge)

**RizomUV - Maya Bridge** is a bridge plugin for **Autodesk Maya** (2022–2027) and **RizomUV 2024+**, for a convenient, native like UV unwrapping and packing workflow. Works on Windows, macOS, and Linux.

---

## Features
- **Live Link mode (new in 3.0, Windows):** drives one persistent RizomUV instance directly. Send/Get are synchronous and reliable — "Get UVs" asks RizomUV to save its current state first, so you can never import stale UVs. Falls back automatically to the classic launch-per-operation Lua workflow (macOS/Linux, or when disabled). Under the hood this uses Rizom-Lab's open-source RizomUVLink library, which is a separate project and is bundled here unmodified.
- One-click Rizom operations (Live Link): Auto Unwrap (Mosaic / Hierarchical / Sharp Edges), Unfold, Optimize, and Auto Pack with presets (pixel padding/margins, UDIM tile layouts). Each button does the full round trip — export, operate in RizomUV, import back — no separate Send/Get needed. A watchdog detects a crashed RizomUV and aborts cleanly.
- Easy drag-and-drop installer/uninstaller/updater (updates keep your settings).
- Send meshes to RizomUV and retrieve UVs — with namespace/duplicate-name safe matching.
- UV set support: the Target/Source UV Set is honored on both Send **and** Get (choose "All UV Sets" to transfer everything).
- Auto-pack UVs with adjustable quality and mutations.
- Custom Lua scripts (works in both Live Link and classic mode).
- Harden UV shell edges post-import — great for game assets.
- Auto-detection of installed RizomUV versions.
- Modern, dockable UI with a debugging toggle.

---

## Installation
1. Download and extract the ZIP from Releases page.
2. Open Maya (2022–2027).
3. Drag `rizomuv_bridge_installer.py` into the viewport.
4. Select your RizomUV executable when prompted.
5. A shelf button is added. Click to start!
#### (if you have a previous version installed, just run the installer again and pick Reinstall/Update — your settings are kept)

---

## Usage
- **Send to RizomUV:** Select mesh, click "Send Selection to RizomUV."
- **Auto Pack:** Select mesh, select a UV Set, click "Auto Pack UV Set". In Live Link mode Maya waits for packing to finish; in classic mode save in RizomUV when it completes.
- **Get UVs:** Select mesh, click "Get UVs" after editing in RizomUV. With a specific UV Set selected only that set is imported; with "All UV Sets" every matching set is imported.
- **Live Link toggle** (Settings section, Windows): keeps one RizomUV session open and talks to it directly. Disable it to use the classic file-based workflow.
- **Harden UV Shell Edges:** Select mesh, click the button to soften/harden normals along UV borders.

---

## Requirements
- **Maya:** 2022–2027
- **RizomUV:** 2024.0+ (Live Link needs RizomUV 2022.2+ on Windows)
- **OS:** Windows, macOS, or Linux (Live Link is Windows-only; other platforms use the classic workflow)

The bundled `RizomUVLink` folder is © Rizom-Lab, MIT licensed (see its LICENSE.md).

---

## Support
Issues?  
  Open a ticket [here](https://github.com/adevra/RizomUV-2024-Maya-Bridge/issues).

🤖 or visit the official [RizomUV Discord Channel](https://discord.com/channels/373032486667550731/1280518135853879296) > Bridges > maya-adev channel.
