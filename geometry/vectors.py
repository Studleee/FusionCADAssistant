"""Vector math helpers independent of the Fusion API."""


def midpoint(a, b):
    """Return the midpoint of two (x, y, z) tuples."""
    return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5)


def subtract(a, b):
    """Return a - b for two (x, y, z) tuples."""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def length(v):
    """Euclidean length of an (x, y, z) tuple."""
    return (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5
