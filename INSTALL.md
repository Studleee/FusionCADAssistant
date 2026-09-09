# Fusion CAD Assistant — install

This is a **Fusion 360 Python add-in**. It is a **folder**, not a single file. Fusion requires:

- `FusionCADAssistant.py` (entry point)
- `FusionCADAssistant.manifest`
- the `commands/`, `config/`, `fusion/`, `geometry/`, and `ui/` packages

## Quick install (Windows)

1. Unzip so you have a folder named exactly `FusionCADAssistant`.
2. Copy that folder to:

   `%appdata%\Autodesk\Autodesk Fusion 360\API\AddIns\`

   Full typical path:

   `C:\Users\<You>\AppData\Roaming\Autodesk\Autodesk Fusion 360\API\AddIns\FusionCADAssistant`

3. Restart Fusion (or open **Utilities → Scripts and Add-Ins** / `Shift+S`).
4. Open the **Add-Ins** tab, select **FusionCADAssistant**, click **Run**.
5. Optionally enable **Run on Startup**.
6. In the **Design** workspace, look for the **CAD ASSISTANT** panel.

## Quick install (macOS)

1. Unzip to a folder named `FusionCADAssistant`.
2. Copy it to:

   `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`

3. Restart Fusion and **Run** the add-in as above.

## Alternate: link from anywhere

If you keep the folder on the Desktop or in a shared drive:

1. `Shift+S` → **Add-Ins** → green **+** next to My Add-Ins  
2. Browse to the `FusionCADAssistant` folder and select it  
3. **Run**

## Update

Replace the old `FusionCADAssistant` folder with the new one (or overwrite files), then stop/start the add-in in Scripts and Add-Ins so modules reload.

## Requirements

- Autodesk Fusion 360 (Design workspace)
- No extra Python install — Fusion’s built-in Python runs the add-in
