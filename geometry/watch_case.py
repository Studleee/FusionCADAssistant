"""Round watch-case half-profile (XZ) for a 360° revolve about Z.

Coordinates are centimeters. X = radius from the case axis, Z = height with
Z=0 at the exterior caseback face and +Z toward the crystal.
"""

from __future__ import annotations


def watch_case_half_profile_points(
        case_od_cm,
        case_height_cm,
        crystal_od_cm,
        cavity_od_cm,
        bezel_height_cm,
        bezel_inset_cm,
        caseback_height_cm,
        caseback_inset_cm,
        caseback_opening_cm,
        edge_softness=0.0):
    """Closed (x, z) polyline for a hollow round midcase + bezel + caseback.

    edge_softness in [0, 1] chamfers the outer bezel and caseback corners.
    """
    case_r = float(case_od_cm) * 0.5
    crystal_r = float(crystal_od_cm) * 0.5
    cavity_r = float(cavity_od_cm) * 0.5
    h = float(case_height_cm)
    bezel_h = float(bezel_height_cm)
    bezel_inset = max(float(bezel_inset_cm), 0.0)
    back_h = float(caseback_height_cm)
    back_inset = max(float(caseback_inset_cm), 0.0)
    back_open_r = float(caseback_opening_cm) * 0.5
    soft = max(0.0, min(1.0, float(edge_softness)))

    if case_r <= 0 or h <= 0:
        raise ValueError('Case diameter and height must be greater than zero.')
    if crystal_r <= 0 or cavity_r <= 0 or back_open_r <= 0:
        raise ValueError('Openings must be greater than zero.')
    if crystal_r >= case_r or cavity_r >= case_r or back_open_r >= case_r:
        raise ValueError('Openings must be smaller than the case diameter.')
    if bezel_h <= 0 or back_h <= 0 or bezel_h + back_h >= h - 1e-6:
        raise ValueError('Bezel and caseback heights must fit inside case height.')

    bezel_r = max(case_r - bezel_inset, crystal_r + 1e-4)
    back_r = max(case_r - back_inset, back_open_r + 1e-4)
    z_bezel = h - bezel_h
    z_back = back_h

    seat = min(bezel_h * 0.45, max(h * 0.06, 0.04))
    z_seat = h - seat
    floor = min(back_h * 0.55, max(h * 0.06, 0.04))
    z_floor = floor

    if cavity_r >= bezel_r - 1e-4 or cavity_r >= back_r - 1e-4:
        raise ValueError('Movement cavity is too large for the wall thickness.')
    if crystal_r >= bezel_r - 1e-4:
        raise ValueError('Crystal opening is too large for the bezel width.')

    top_c = soft * min(bezel_h * 0.45, max(case_r - bezel_r, 1e-4) * 0.9)
    bot_c = soft * min(back_h * 0.45, max(case_r - back_r, 1e-4) * 0.9)

    pts = [(crystal_r, h), (bezel_r, h)]

    if top_c > 1e-5 and bezel_r < case_r - 1e-6:
        pts.append((case_r, h - top_c))
        pts.append((case_r, z_bezel))
    elif bezel_r < case_r - 1e-6:
        pts.append((case_r, z_bezel))
    else:
        # Flush bezel OD — drop straight down the outer wall from the top.
        pts.append((case_r, z_bezel))

    pts.append((case_r, z_back))

    if bot_c > 1e-5 and back_r < case_r - 1e-6:
        pts.append((case_r, bot_c))
        pts.append((back_r, 0.0))
    elif back_r < case_r - 1e-6:
        pts.append((back_r, z_back))
        pts.append((back_r, 0.0))
    else:
        pts.append((case_r, 0.0))

    pts.extend([
        (back_open_r, 0.0),
        (back_open_r, z_floor),
        (cavity_r, z_floor),
        (cavity_r, z_seat),
        (crystal_r, z_seat),
        (crystal_r, h),
    ])
    return _dedupe_closed_xz(pts)


def _dedupe_closed_xz(points, tol=1e-7):
    """Drop near-duplicate consecutive points and ensure closure."""
    if not points:
        return points
    out = [points[0]]
    for p in points[1:]:
        prev = out[-1]
        if abs(p[0] - prev[0]) > tol or abs(p[1] - prev[1]) > tol:
            out.append(p)
    if abs(out[0][0] - out[-1][0]) > tol or abs(out[0][1] - out[-1][1]) > tol:
        out.append(out[0])
    return out


def watch_case_profile_is_valid(
        case_od_cm,
        case_height_cm,
        crystal_od_cm,
        cavity_od_cm,
        bezel_height_cm,
        bezel_inset_cm,
        caseback_height_cm,
        caseback_inset_cm,
        caseback_opening_cm):
    """True when the profile dimensions can form a legal hollow case."""
    try:
        watch_case_half_profile_points(
            case_od_cm, case_height_cm, crystal_od_cm, cavity_od_cm,
            bezel_height_cm, bezel_inset_cm, caseback_height_cm,
            caseback_inset_cm, caseback_opening_cm, edge_softness=0.0)
        return True
    except Exception:
        return False


def watch_case_lug_rects_xy(
        case_od_cm, lug_length_cm, lug_width_cm, lug_gap_cm, embed_cm=0.05):
    """Four lug footprints in XY as axis-aligned rectangles (xmin,ymin,xmax,ymax).

    Pairs sit at 12 o'clock (+Y) and 6 o'clock (-Y). Each horn embeds slightly
    into the case OD so a join-extrude fuses cleanly.
    """
    case_r = float(case_od_cm) * 0.5
    length = float(lug_length_cm)
    width = float(lug_width_cm)
    gap = float(lug_gap_cm)
    embed = max(float(embed_cm), 0.0)
    if length <= 0 or width <= 0 or gap <= 0:
        raise ValueError('Lug length, width, and gap must be greater than zero.')
    if gap + 2.0 * width >= float(case_od_cm):
        raise ValueError('Lug gap + widths are too wide for this case diameter.')

    half_gap = gap * 0.5
    y0 = case_r - embed
    y1 = case_r + length
    # 12 o'clock pair
    left_12 = (-(half_gap + width), y0, -half_gap, y1)
    right_12 = (half_gap, y0, half_gap + width, y1)
    # 6 o'clock pair
    left_6 = (-(half_gap + width), -y1, -half_gap, -y0)
    right_6 = (half_gap, -y1, half_gap + width, -y0)
    return (left_12, right_12, left_6, right_6)


def watch_case_lugs_are_valid(case_od_cm, lug_length_cm, lug_width_cm, lug_gap_cm,
                              lug_thickness_cm, case_height_cm):
    """True when lug sizes fit the case."""
    try:
        if float(lug_thickness_cm) <= 0:
            return False
        if float(lug_thickness_cm) >= float(case_height_cm) - 1e-6:
            return False
        watch_case_lug_rects_xy(
            case_od_cm, lug_length_cm, lug_width_cm, lug_gap_cm)
        return True
    except Exception:
        return False
