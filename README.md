![ssbridge.png](https://blog.anildevran.com/content/images/2025/02/rizomuvmayabridgecover_adev.png)

# RIZOM UV 2024 - Autodesk MAYA Bridge

**Version 2.0.0** | **Author:** A. Devran | **GitHub:** [https://github.com/adevra/RizomUV-2024-Maya-Bridge](https://github.com/adevra/RizomUV-2024-Maya-Bridge)

Bridge plugin for **Autodesk Maya** (2022–2025) and **RizomUV 2024**, for a convenient, native like UV unwrapping and packing workflow. Works on Windows, macOS, and Linux.

---

## Features
- Easy drag-and-drop installer with shelf button.
- Send meshes to RizomUV and retrieve UVs.
- UV set support.
- Auto-pack UVs with adjustable quality.
- Harden UV edges post-import.
- Modern, dockable UI.

---

## Installation
1. Download and extract the ZIP from Releases page.
2. Open Maya (2022–2025).
3. Drag `drag_and_drop_install.py` into the viewport.
4. Select your RizomUV executable when prompted.
5. A shelf button is added. Click to start!
#### (if you have previous version installed, please remove it from your /maya/scripts folder and remove shelf button)

---

## Usage
- **Send to RizomUV:** Select mesh, click "Send to RizomUV."
- **Auto Pack:** Select mesh, click "Auto Pack" to unwrap and pack UVs.
- **Get UVs:** Select mesh, click "Get UVs" after editing in RizomUV.
- **Any modifications to UVs in different UVSets will also be transferred.*
- **Harden UV Edges:** Select mesh, click "Harden UV Edges" to refine. Extremely useful if you are unwrapping for game assets.

---

## Requirements
- **Maya:** 2022–2025
- **RizomUV:** 2024.0+
- **OS:** Windows, macOS, or Linux

---

## Support
Issues?  
  Open a ticket [here](https://github.com/adevra/RizomUV-2024-Maya-Bridge/issues).

🤖 or visit the official [RizomUV Discord Channel](https://discord.com/channels/373032486667550731/1280518135853879296) > Bridges > maya-adev channel.