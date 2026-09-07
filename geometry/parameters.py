"""Parameter naming and validation helpers (Fusion-free)."""

import re

_PARAM_NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')


def validate_parameter_name(name):
    """Ensure a name is a legal Fusion user-parameter identifier."""
    if not name or not _PARAM_NAME_RE.match(name):
        raise ValueError(
            'Invalid parameter name {!r}. Use letters, digits, underscore; '
            'must start with a letter.'.format(name))
    return name
