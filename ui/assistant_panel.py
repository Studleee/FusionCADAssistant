"""CAD ASSISTANT toolbar panel setup and teardown."""

from commands import (
    apply_anglage,
    apply_finish_guides,
    create_hairspring,
    create_jewel,
    create_mainspring,
    create_pinion,
    create_pivot,
    create_ring_gear,
    create_screw,
    create_wheel,
)
from config import defaults

_COMMAND_MODULES = (
    create_screw,
    create_jewel,
    create_pivot,
    create_hairspring,
    create_mainspring,
    create_wheel,
    create_ring_gear,
    create_pinion,
    apply_finish_guides,
    apply_anglage,
)
_COMMAND_IDS = (
    defaults.CMD_CREATE_SCREW_ID,
    defaults.CMD_CREATE_JEWEL_ID,
    defaults.CMD_CREATE_PIVOT_ID,
    defaults.CMD_CREATE_HAIRSPRING_ID,
    defaults.CMD_CREATE_MAINSPRING_ID,
    defaults.CMD_CREATE_WHEEL_ID,
    defaults.CMD_CREATE_RING_GEAR_ID,
    defaults.CMD_CREATE_PINION_ID,
    defaults.CMD_FINISH_GUIDES_ID,
    defaults.CMD_ANGLAGE_ID,
)

# Removed commands — still deleted from toolbars on reload so old buttons vanish.
_LEGACY_COMMAND_IDS = (
    'CADAssistant_CreateRing',
)


def _all_command_ids():
    return _COMMAND_IDS + _LEGACY_COMMAND_IDS


def _remove_command_controls(ui):
    """Remove CAD Assistant command controls from every toolbar panel."""
    panels = ui.allToolbarPanels
    for i in range(panels.count):
        panel = panels.item(i)
        if not panel:
            continue
        for cmd_id in _all_command_ids():
            control = panel.controls.itemById(cmd_id)
            if control:
                control.deleteMe()


def _remove_panel(ui):
    """Delete any existing CAD ASSISTANT panel via the global panel list."""
    panel = ui.allToolbarPanels.itemById(defaults.PANEL_ID)
    if panel:
        for cmd_id in _all_command_ids():
            control = panel.controls.itemById(cmd_id)
            if control:
                control.deleteMe()
        panel.deleteMe()


def create_panel(ui):
    """Create the CAD ASSISTANT panel and register commands.

    Idempotent: cleans previous panel/controls first.
    """
    workspace = ui.workspaces.itemById(defaults.WORKSPACE_ID)
    if not workspace:
        raise RuntimeError('Could not find the Design workspace (FusionSolidEnvironment).')

    _remove_command_controls(ui)
    _remove_panel(ui)

    # Drop legacy command defs (e.g. removed Create Ring) if still registered.
    for cmd_id in _LEGACY_COMMAND_IDS:
        cmd_def = ui.commandDefinitions.itemById(cmd_id)
        if cmd_def:
            cmd_def.deleteMe()

    for module in _COMMAND_MODULES:
        module.stop(ui)

    tab = workspace.toolbarTabs.itemById(defaults.TAB_ID)
    panels = tab.toolbarPanels if tab else workspace.toolbarPanels

    try:
        panel = panels.add(
            defaults.PANEL_ID,
            defaults.PANEL_NAME,
            'SolidCreatePanel',
            False)
    except Exception:
        panel = panels.add(defaults.PANEL_ID, defaults.PANEL_NAME)

    if not panel:
        raise RuntimeError('Failed to create the CAD ASSISTANT toolbar panel.')

    for module in _COMMAND_MODULES:
        cmd_def = module.start(ui)
        if not cmd_def:
            raise RuntimeError('Failed to register a CAD Assistant command.')
        control = panel.controls.addCommand(cmd_def)
        if control:
            control.isPromoted = True
            control.isPromotedByDefault = True

    return panel


def destroy_panel(ui):
    """Remove panel controls, panel, and command definitions."""
    try:
        _remove_command_controls(ui)
        _remove_panel(ui)
        for cmd_id in _LEGACY_COMMAND_IDS:
            cmd_def = ui.commandDefinitions.itemById(cmd_id)
            if cmd_def:
                cmd_def.deleteMe()
        for module in _COMMAND_MODULES:
            module.stop(ui)
    except Exception:
        pass
