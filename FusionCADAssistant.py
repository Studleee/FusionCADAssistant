"""Fusion CAD Assistant — Fusion 360 add-in entry point.

Adds a CAD ASSISTANT panel to the Design workspace and registers geometry
commands (Create Screw, Create Jewel, Create Pivot, Create Wheel,
Create Ring Gear, …).
"""

import os
import sys
import traceback

import adsk.core

# Ensure the add-in folder is on sys.path so package imports resolve inside Fusion.
_ADDIN_DIR = os.path.dirname(os.path.realpath(__file__))
if _ADDIN_DIR not in sys.path:
    sys.path.insert(0, _ADDIN_DIR)

# Package roots that must reload when the add-in switch is toggled.
_RELOAD_PREFIXES = (
    'ui',
    'commands',
    'config',
    'fusion',
    'geometry',
)


def _purge_cached_modules():
    """Drop cached add-in modules so Stop/Start picks up disk edits.

    Fusion keeps Python modules in memory across add-in toggles; without this,
    new commands (e.g. Create Screw) never appear after an update.
    """
    to_remove = []
    for name in sys.modules:
        for prefix in _RELOAD_PREFIXES:
            if name == prefix or name.startswith(prefix + '.'):
                to_remove.append(name)
                break
    for name in to_remove:
        del sys.modules[name]


def run(context):
    """Called by Fusion when the add-in starts."""
    ui = None
    try:
        _purge_cached_modules()
        from ui import assistant_panel

        app = adsk.core.Application.get()
        ui = app.userInterface
        assistant_panel.create_panel(ui)
    except Exception:
        if ui:
            ui.messageBox(
                'Fusion CAD Assistant failed to start:\n{}'.format(traceback.format_exc()))


def stop(context):
    """Called by Fusion when the add-in stops."""
    ui = None
    try:
        # Import may still be the previous session's module; purge first so
        # destroy_panel matches whatever create_panel last registered.
        try:
            from ui import assistant_panel
        except Exception:
            _purge_cached_modules()
            from ui import assistant_panel

        app = adsk.core.Application.get()
        ui = app.userInterface
        assistant_panel.destroy_panel(ui)
    except Exception:
        if ui:
            ui.messageBox(
                'Fusion CAD Assistant failed to stop:\n{}'.format(traceback.format_exc()))
