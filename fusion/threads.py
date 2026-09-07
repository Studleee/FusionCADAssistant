"""Thread feature helpers using Fusion's ThreadData tables."""

import adsk.core
import adsk.fusion


def create_external_thread(component, cylindrical_face, thread_type, designation,
                           thread_class, is_modeled=False, is_full_length=True,
                           thread_length_cm=None, is_right_handed=True, name=None):
    """Apply an external thread to a cylindrical face.

    Uses ThreadFeatures.createThreadInfo / createInput / add — the same
    pathway as Fusion's Thread command (not invented helix geometry).

    is_modeled=False → cosmetic thread (recommended default).
    is_modeled=True  → cut modeled thread geometry (heavier).
    """
    if not cylindrical_face:
        raise ValueError('A cylindrical face is required for threading.')

    threads = component.features.threadFeatures
    # createThreadInfo(isInternal, threadType, threadDesignation, threadClass)
    thread_info = threads.createThreadInfo(
        False, thread_type, designation, thread_class)
    if not thread_info:
        raise RuntimeError(
            'Could not create thread info for {} / {} / {}.\n'
            'Check that this designation exists in Fusion thread data.'.format(
                thread_type, designation, thread_class))

    faces = adsk.core.ObjectCollection.create()
    faces.add(cylindrical_face)

    thread_input = threads.createInput(faces, thread_info)
    if not thread_input:
        raise RuntimeError('Failed to create thread feature input.')

    # These properties are supported on ThreadFeatureInput in current Fusion builds.
    thread_input.isModeled = bool(is_modeled)
    thread_input.isRightHanded = bool(is_right_handed)
    thread_input.isFullLength = bool(is_full_length)
    if not is_full_length:
        if thread_length_cm is None or thread_length_cm <= 0:
            raise ValueError('Thread length must be greater than zero when not full length.')
        thread_input.threadLength = adsk.core.ValueInput.createByReal(float(thread_length_cm))

    thread = threads.add(thread_input)
    if not thread:
        raise RuntimeError('Failed to create the thread feature.')

    if name:
        thread.name = name
    return thread


def find_thread_type(thread_features, preferred_name):
    """Return preferred thread type if present, else the first available type."""
    query = thread_features.threadDataQuery
    types = list(query.allThreadTypes)
    if not types:
        raise RuntimeError('No thread types available in this Fusion install.')
    if preferred_name in types:
        return preferred_name
    # Case-insensitive fallback
    preferred_lower = preferred_name.lower()
    for t in types:
        if t.lower() == preferred_lower:
            return t
    return types[0]
