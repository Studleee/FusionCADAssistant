"""2D profile helpers (Fusion-free)."""


def annular_radii_from_diameters(outer_diameter, inner_diameter):
    """Return (outer_radius, inner_radius) from diameters.

    Raises ValueError if the ring would be invalid.
    """
    if outer_diameter <= 0:
        raise ValueError('Outer diameter must be greater than zero.')
    if inner_diameter <= 0:
        raise ValueError('Inner diameter must be greater than zero.')
    if inner_diameter >= outer_diameter:
        raise ValueError(
            'Inner diameter ({}) must be smaller than outer diameter ({}).'.format(
                inner_diameter, outer_diameter))
    return outer_diameter * 0.5, inner_diameter * 0.5
