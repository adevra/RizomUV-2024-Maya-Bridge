![ssbridge.png](https://blog.anildevran.com/content/images/2025/02/rizomuvmayabridgecover_adev.png)

# RIZOM UV 2024 - Autodesk MAYA Bridge

**Version 3.3.1** | **Author:** A. Devran | **GitHub:** [https://github.com/adevra/RizomUV-2024-Maya-Bridge](https://github.com/adevra/RizomUV-2024-Maya-Bridge)

**RizomUV - Maya Bridge** is a bridge plugin for **Autodesk Maya** (2022–2027) and **RizomUV 2024+**, for a convenient, native like UV unwrapping and packing workflow. Works on Windows, macOS, and Linux.

---

## Features

### Two connection modes
- **Live Link (Windows, default):** drives one persistent RizomUV instance directly over a local link. Send/Get are synchronous and reliable. "Get UVs" asks RizomUV to save its current state first, so you can never import stale UVs. Maya waits while RizomUV works, so the window is unresponsive until an operation finishes. Built on Rizom-Lab's open-source RizomUVLink library (a separate MIT project, bundled here unmodified). Automatically retries a flaky RizomUV launch and aborts cleanly if RizomUV crashes mid-operation.
- **Classic (macOS/Linux, or when Live Link is off):** the original file + Lua workflow, launching RizomUV per operation. Includes a staleness guard that warns if RizomUV hasn't re-saved since you sent.

### Bridge tab (send / get)
- Send meshes to RizomUV and retrieve UVs, with **namespace- and duplicate-name-safe object matching**.
- **UV set support:** the Target/Source UV Set is honored on both Send *and* Get; pick a specific set, or "All UV Sets" to transfer everything.
- **Custom Lua scripts** run against your mesh in RizomUV (both modes).
- **Harden UV Shell Edges:** soften/harden normals along UV borders in one click. Great for game assets.

### Rizom Ops tab: one-click operations (Live Link)
Each button does the full round trip (export selection, operate in RizomUV, import the result back), no separate Send/Get:
- **Auto Unwrap:** Mosaic, Hierarchical, or Sharp Edges seaming, then cut + unfold (always a fresh unwrap).
- **Unfold / Optimize:** with iteration count, angle/distance mix, and a flip/overlap-prevention option.
- **Auto Pack** with named **presets:** pixel padding/margins, map resolution, mutations, and UDIM tile layouts (rows × columns).

### Integration tab: Rizom groups in Maya (Live Link)
- **Sync Groups:** mirror RizomUV's island groups and UDIM tiles into Maya selection sets (`RZM_grp_*`, `RZM_tile_*`), with a per-tile UDIM summary. Click a set in the list to select its faces. Optional **auto-sync after every Get**.
- **Color Groups:** tint each synced group/tile's islands a distinct, stable color (per-island, no bleed, fully reversible via a color set) to see the group layout in the 3D viewport (and the UV Editor with shaded display on).

### General
- Drag-and-drop installer / uninstaller / updater. Updates keep your settings.
- Auto-detection of installed RizomUV versions.
- Modern, dockable, tabbed UI with a verbose-logging toggle.

---

## Installation
1. Download and extract the ZIP from Releases page.
2. Open Maya (2022–2027).
3. Drag `rizomuv_bridge_installer.py` into the viewport.
4. Select your RizomUV executable when prompted.
5. A shelf button is added. Click to start!
#### (if you have a previous version installed, just run the installer again and pick Reinstall/Update, your settings are kept)

---

## Usage

The panel has three tabs plus a Settings header (RizomUV path + the **Use Live Link** toggle).

**Bridge tab**
- **Send Selection to RizomUV:** select meshes, click to send them over.
- **Get UVs from RizomUV:** click after editing in RizomUV to import UVs back. In Live Link mode RizomUV saves first automatically; a specific UV Set imports only that set, "All UV Sets" imports every matching set.
- **Run Custom Lua Script** / **Harden UV Shell Edges** as needed.

**Rizom Ops tab (Live Link)**
- Pick an **Auto Unwrap** algorithm and click it, or use **Unfold** / **Optimize**, or set up a **Pack preset** and click **Auto Pack UV Set**. Each runs the whole round trip and imports the result, no Send/Get needed. Maya stays responsive while RizomUV works.

**Integration tab (Live Link)**
- **Sync Groups from RizomUV** to create the `RZM_*` selection sets and UDIM summary (or enable auto-sync). Click a set to select it. **Color Groups** to visualize the group layout; **Clear Colors** to remove it.

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
