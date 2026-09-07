"""Component and occurrence helpers."""

import adsk.core
import adsk.fusion


def get_active_design():
    """Return the active Design or raise a clear error."""
    app = adsk.core.Application.get()
    if not app:
        raise RuntimeError('Could not get the Fusion application.')

    product = app.activeProduct
    if not product:
        raise RuntimeError('No active document. Open or create a Design first.')

    design = adsk.fusion.Design.cast(product)
    if not design:
        raise RuntimeError(
            'The active document is not a Design (parametric model). '
            'Switch to the Design workspace and try again.')
    return design


def _design_intent_name(design):
    """Return a short label for the current designIntent, if available."""
    try:
        intent = design.designIntent
        types = adsk.fusion.DesignIntentTypes
        if intent == types.PartDesignIntentType:
            return 'Part'
        if intent == types.AssemblyDesignIntentType:
            return 'Assembly'
        if intent == types.HybridDesignIntentType:
            return 'Hybrid'
        return str(intent)
    except Exception:
        return 'Unknown'


def ensure_components_allowed(design):
    """Ensure the document can contain child components.

    Newer Fusion 'Part Design' documents only allow the root component.
    CAD Assistant needs subcomponents, so upgrade Part -> Hybrid when needed.

    Returns True if the document already allowed components or was upgraded.
    Raises RuntimeError if components still cannot be created.
    """
    # Older Fusion builds may not expose designIntent; assume components work.
    if not hasattr(design, 'designIntent'):
        return True

    types = adsk.fusion.DesignIntentTypes
    intent = design.designIntent

    if intent != types.PartDesignIntentType:
        return True

    # Hybrid keeps part modeling enabled and allows child components.
    # Part -> Assembly also works; with existing bodies Fusion may become Hybrid.
    for target in (types.HybridDesignIntentType, types.AssemblyDesignIntentType):
        try:
            design.designIntent = target
            if design.designIntent != types.PartDesignIntentType:
                return True
        except Exception:
            continue

    raise RuntimeError(
        'This document is a Part Design and could not be upgraded to allow '
        'multiple components.\n\n'
        'Create a new Design (File > New Design), or change the document to '
        'Hybrid/Assembly, then run the command again.')


def create_component(design, name):
    """Create a new component under the root and return (occurrence, component).

    Uses Occurrences.addNewComponent so the component appears in the browser
    and timeline as a proper assembly node.

    If the active document is a Part Design, attempts to upgrade it to Hybrid
    so child components are allowed.
    """
    if not name:
        raise ValueError('Component name cannot be empty.')

    ensure_components_allowed(design)

    root = design.rootComponent
    transform = adsk.core.Matrix3D.create()
    try:
        occurrence = root.occurrences.addNewComponent(transform)
    except Exception as exc:
        raise RuntimeError(
            'Failed to create component {!r} (document intent: {}).\n{}'.format(
                name, _design_intent_name(design), exc))

    if not occurrence:
        raise RuntimeError('Failed to create a new component occurrence.')

    component = occurrence.component
    component.name = name
    return occurrence, component
