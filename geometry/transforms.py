"""Transform helpers (Fusion-free placeholders for later commands)."""


def identity_matrix_3x3():
    """Return a 3x3 identity matrix as nested tuples."""
    return (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
