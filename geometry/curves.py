"""Curve path helpers for future rib/bridge generators.

Kept Fusion-free so path logic can be unit-tested outside Fusion.
"""


PATH_STRAIGHT = 'STRAIGHT'
PATH_ARC = 'ARC'
PATH_S_CURVE = 'S_CURVE'
PATH_SPLINE = 'SPLINE'


def validate_path_type(path_type):
    """Raise ValueError if path_type is unsupported."""
    allowed = (PATH_STRAIGHT, PATH_ARC, PATH_S_CURVE, PATH_SPLINE)
    if path_type not in allowed:
        raise ValueError('Unsupported path type: {!r}. Expected one of {}.'.format(
            path_type, ', '.join(allowed)))
    return path_type
