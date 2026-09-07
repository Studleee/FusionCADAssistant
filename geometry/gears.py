"""Spur-gear outline math (Fusion-free): involute and cycloidal.

Shared sizing (full-depth tip convention):
  module m = outside_diameter / (teeth + 2)
  pitch diameter d = m * z
  tip diameter da = outside_diameter (user input)
  root diameter df = m * (z - 2.5)

Cycloidal generating circle (when not overridden):
  radius a = π m / 4   (generating Ø = half circular pitch)
"""

import math

PROFILE_INVOLUTE = 'involute'
PROFILE_CYCLOIDAL = 'cycloidal'


def module_from_outside_diameter(outside_diameter, teeth):
    """Module from tip/outside diameter assuming addendum = m (da = m*(z+2))."""
    z = int(teeth)
    if z < 6:
        raise ValueError('Tooth count must be at least 6.')
    da = float(outside_diameter)
    if da <= 0:
        raise ValueError('Outside diameter must be greater than zero.')
    return da / float(z + 2)


def outside_diameter_from_module(module, teeth):
    """Tip/outside diameter from module: da = m * (z + 2)."""
    z = int(teeth)
    if z < 6:
        raise ValueError('Tooth / leaf count must be at least 6.')
    m = float(module)
    if m <= 0:
        raise ValueError('Module must be greater than zero.')
    return m * float(z + 2)


def _rotate(x, y, angle):
    c = math.cos(angle)
    s = math.sin(angle)
    return x * c - y * s, x * s + y * c


def _polar_angle(x, y):
    return math.atan2(y, x)


def _involute(rb, t):
    """Involute of base circle radius rb at roll angle t (radians)."""
    return (
        rb * (math.cos(t) + t * math.sin(t)),
        rb * (math.sin(t) - t * math.cos(t)),
    )


def _involute_angle_at_radius(rb, radius):
    if radius <= rb + 1e-12:
        return 0.0
    return math.sqrt((radius / rb) ** 2 - 1.0)


def _point_on_circle(radius, angle):
    return (radius * math.cos(angle), radius * math.sin(angle), 0.0)


def _arc_points(radius, a0, a1, steps):
    """Points along a circular arc from a0 to a1 (radians). Includes both ends."""
    pts = []
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * (float(i) / float(steps))
        pts.append(_point_on_circle(radius, a))
    return pts


def _flank_root_to_tip(rb, r_start, ra, steps):
    """Involute points from r_start → tip (inclusive), unevaluated orientation."""
    t0 = _involute_angle_at_radius(rb, r_start)
    t1 = _involute_angle_at_radius(rb, ra)
    pts = []
    for i in range(steps + 1):
        t = t0 + (t1 - t0) * (float(i) / float(steps))
        x, y = _involute(rb, t)
        pts.append((x, y, 0.0))
    return pts


def _epicycloid(R, a, phi):
    """Epicycloid: generating circle a rolling outside fixed circle R."""
    k = (R + a) / a
    return (
        (R + a) * math.cos(phi) - a * math.cos(k * phi),
        (R + a) * math.sin(phi) - a * math.sin(k * phi),
    )


def _hypocycloid(R, a, phi):
    """Hypocycloid: generating circle a rolling inside fixed circle R."""
    if a <= 1e-15:
        raise ValueError('Generating circle radius must be greater than zero.')
    k = (R - a) / a
    return (
        (R - a) * math.cos(phi) + a * math.cos(k * phi),
        (R - a) * math.sin(phi) - a * math.sin(k * phi),
    )


def _radius_xy(x, y):
    return math.hypot(x, y)


def _phi_at_radius(curve_fn, R, a, target_r, phi_hi):
    """Find phi in [0, phi_hi] where curve radius matches target_r (first lobe)."""
    target = float(target_r)
    r0 = _radius_xy(*curve_fn(R, a, 0.0))
    going_out = target >= r0 - 1e-12

    lo = 0.0
    hi = max(float(phi_hi), 1e-9)
    r_hi = _radius_xy(*curve_fn(R, a, hi))

    # If the lobe never reaches the target, use the end of the lobe.
    if going_out and r_hi < target:
        return hi
    if (not going_out) and r_hi > target:
        return hi

    for _ in range(40):
        mid = 0.5 * (lo + hi)
        r_mid = _radius_xy(*curve_fn(R, a, mid))
        if going_out:
            if r_mid < target:
                lo = mid
            else:
                hi = mid
        else:
            if r_mid > target:
                lo = mid
            else:
                hi = mid
    return 0.5 * (lo + hi)


def _sample_curve_to_radius(curve_fn, R, a, target_r, steps, outward):
    """Points from pitch (phi=0) to target radius along epi/hypo.

    Stays on the first lobe (before the cusp) so flanks do not fold back.
    """
    if outward:
        phi_cusp = math.pi * a / (R + a)
    else:
        phi_cusp = math.pi * a / max(R - a, a * 0.5)
    phi_cap = max(phi_cusp * 0.98, 1e-6)
    phi_end = _phi_at_radius(curve_fn, R, a, target_r, phi_cap)
    phi_end = min(phi_end, phi_cap)
    pts = []
    for i in range(steps + 1):
        phi = phi_end * (float(i) / float(steps))
        x, y = curve_fn(R, a, phi)
        pts.append((x, y, 0.0))
    lx, ly, _ = pts[-1]
    lr = _radius_xy(lx, ly)
    if lr > 1e-15:
        s = float(target_r) / lr
        pts[-1] = (lx * s, ly * s, 0.0)
    return pts


def _sample_budget(teeth, profile):
    """Choose flank/tip/root steps: enough for clean teeth, light enough for Fusion.

    Live preview is disabled on gears; a few hundred sketch lines is fine.
    Avoid fitted splines through decimated points — they create hooked/wavy rims.
    """
    z = max(int(teeth), 6)
    if profile == PROFILE_CYCLOIDAL:
        if z <= 40:
            return 6, 5, 8
        if z <= 80:
            return 5, 4, 6
        return 4, 3, 5
    # Involute
    if z <= 40:
        return 8, 3, 3
    if z <= 80:
        return 6, 2, 2
    return 5, 2, 2


def gear_outline_points(outside_diameter, teeth, profile=PROFILE_INVOLUTE,
                        pressure_angle_deg=20.0, generating_radius=None,
                        flank_steps=None, tip_steps=None, root_steps=None):
    """Dispatch involute or cycloidal outline. Returns (outline, m, d, df)."""
    auto_flank, auto_tip, auto_root = _sample_budget(teeth, profile)
    flank_steps = auto_flank if flank_steps is None else int(flank_steps)
    tip_steps = auto_tip if tip_steps is None else int(tip_steps)
    root_steps = auto_root if root_steps is None else int(root_steps)

    if profile == PROFILE_CYCLOIDAL:
        return cycloidal_gear_outline_points(
            outside_diameter, teeth,
            generating_radius=generating_radius,
            flank_steps=flank_steps,
            tip_steps=tip_steps,
            root_steps=root_steps)
    return spur_gear_outline_points(
        outside_diameter, teeth,
        pressure_angle_deg=pressure_angle_deg,
        flank_steps=flank_steps,
        tip_steps=tip_steps,
        root_steps=root_steps)


def gear_one_tooth_points(outside_diameter, teeth, profile=PROFILE_CYCLOIDAL,
                          pressure_angle_deg=20.0, flank_steps=None, tip_steps=None,
                          root_steps=None):
    """Closed CCW loop for a single tooth centered on +X (for face/crown gears).

    Returns (tooth_loop, module, pitch_diameter, root_diameter).
    """
    auto_flank, auto_tip, auto_root = _sample_budget(teeth, profile)
    flank_steps = auto_flank if flank_steps is None else int(flank_steps)
    tip_steps = auto_tip if tip_steps is None else int(tip_steps)
    root_steps = auto_root if root_steps is None else int(root_steps)

    if profile == PROFILE_CYCLOIDAL:
        tooth, m, d, df = _cycloidal_one_tooth(
            outside_diameter, teeth, flank_steps, tip_steps)
    else:
        tooth, m, d, df = _involute_one_tooth(
            outside_diameter, teeth, pressure_angle_deg, flank_steps, tip_steps)
    if len(tooth) < 4:
        raise RuntimeError('Failed to build single-tooth outline.')
    if tooth[0] != tooth[-1]:
        tooth = list(tooth)
        tooth.append(tooth[0])
    return tooth, m, d, df


def _cycloidal_one_tooth(outside_diameter, teeth, flank_steps, tip_steps):
    """One cycloidal tooth polygon (open or closed at root chord)."""
    z = int(teeth)
    da = float(outside_diameter)
    m = module_from_outside_diameter(da, z)
    d = m * z
    ra = da * 0.5
    rf = max(0.5 * m * (z - 2.25), 0.22 * m)
    pitch_ang = 2.0 * math.pi / float(z)
    tip_half = pitch_ang * 0.10
    root_half = pitch_ang * 0.22
    if pitch_ang - 2.0 * root_half < pitch_ang * 0.30:
        root_half = pitch_ang * 0.20

    tip_meet_r = ra - ra * math.sin(tip_half) * 0.55
    tip_r = _point_on_circle(tip_meet_r, -tip_half)
    root_r = _point_on_circle(rf, -root_half)
    mid = _point_on_circle(
        0.58 * ra + 0.42 * rf, -0.5 * (tip_half + root_half))
    right = _arc_through_three_points(
        root_r, mid, tip_r, max(int(flank_steps), 5))
    left = [(p[0], -p[1], 0.0) for p in right]
    tip_arc = _tip_arch(ra, tip_half, tip_meet_r, max(int(tip_steps), 4))

    tooth = [_point_on_circle(rf, -root_half)]
    tooth.extend(right[1:-1])
    tooth.extend(tip_arc)
    tooth.extend(list(reversed(left))[1:-1])
    tooth.append(_point_on_circle(rf, root_half))
    return tooth, m, d, rf * 2.0


def _involute_one_tooth(outside_diameter, teeth, pressure_angle_deg, flank_steps,
                        tip_steps):
    """One involute tooth polygon closed with a root chord."""
    z = int(teeth)
    da = float(outside_diameter)
    alpha = math.radians(float(pressure_angle_deg))
    m = module_from_outside_diameter(da, z)
    d = m * z
    ra = da * 0.5
    r = d * 0.5
    rb = r * math.cos(alpha)
    rf = max(0.5 * m * (z - 2.5), 0.25 * m)
    if ra <= rb * 1.001:
        raise ValueError(
            'Outside diameter is too small for this tooth count / pressure angle.')
    r_start = max(rb * 1.0001, rf)
    raw = _flank_root_to_tip(rb, r_start, ra, flank_steps)
    t_pitch = _involute_angle_at_radius(rb, max(r, rb * 1.0001))
    px, py = _involute(rb, t_pitch)
    adjust = -math.pi / (2.0 * z) - _polar_angle(px, py)
    right = []
    for x, y, _ in raw:
        rx, ry = _rotate(x, y, adjust)
        right.append((rx, ry, 0.0))
    left = [(p[0], -p[1], 0.0) for p in right]
    right_tip = _polar_angle(right[-1][0], right[-1][1])
    left_tip = _polar_angle(left[-1][0], left[-1][1])
    tip_a1 = left_tip
    while tip_a1 <= right_tip:
        tip_a1 += 2.0 * math.pi
    tip_arc = _arc_points(ra, right_tip, tip_a1, tip_steps)
    right_foot = _polar_angle(right[0][0], right[0][1])
    left_foot = _polar_angle(left[0][0], left[0][1])
    tooth = [_point_on_circle(rf, right_foot)]
    tooth.extend(right[1:-1])
    tooth.extend(tip_arc)
    tooth.extend(list(reversed(left))[1:-1])
    tooth.append(_point_on_circle(rf, left_foot))
    return tooth, m, d, rf * 2.0


def spur_gear_outline_points(outside_diameter, teeth, pressure_angle_deg=20.0,
                             flank_steps=6, tip_steps=2, root_steps=2):
    """Return a closed list of (x, y, z) points for an involute spur outline.

    Traversed CCW. Each tooth is an exact mirror pair of involute flanks with
    a root-circle transition on both sides (avoids one-sided notches).
    """
    z = int(teeth)
    if z < 6:
        raise ValueError('Tooth count must be at least 6.')
    da = float(outside_diameter)
    alpha = math.radians(float(pressure_angle_deg))
    if not (5.0 <= float(pressure_angle_deg) <= 30.0):
        raise ValueError('Pressure angle should be between 5° and 30°.')

    m = module_from_outside_diameter(da, z)
    d = m * z
    ra = da * 0.5
    r = d * 0.5
    rb = r * math.cos(alpha)
    rf = max(0.5 * m * (z - 2.5), 0.25 * m)

    if ra <= rb * 1.001:
        raise ValueError(
            'Outside diameter is too small for this tooth count / pressure angle '
            '(tip circle inside base circle).')

    r_start = max(rb * 1.0001, rf)
    raw = _flank_root_to_tip(rb, r_start, ra, flank_steps)

    t_pitch = _involute_angle_at_radius(rb, max(r, rb * 1.0001))
    px, py = _involute(rb, t_pitch)
    adjust = -math.pi / (2.0 * z) - _polar_angle(px, py)

    right = []
    for x, y, _ in raw:
        rx, ry = _rotate(x, y, adjust)
        right.append((rx, ry, 0.0))

    left = [(p[0], -p[1], 0.0) for p in right]

    outline = _assemble_mirrored_teeth(
        right, left, z, ra, rf, tip_steps, root_steps)
    return outline, m, d, rf * 2.0


def cycloidal_gear_outline_points(outside_diameter, teeth, generating_radius=None,
                                  flank_steps=6, tip_steps=3, root_steps=5):
    """Closed CCW outline for rounded watch-style cycloidal / ogival teeth.

    Matches typical movement-wheel look:
      - narrow, slightly rounded tip (Gothic / ogival)
      - flanks that taper toward the tip
      - deep U-shaped root fillets between teeth

    Uses one circular-arc flank per side (stable in Fusion). Multi-segment
    flanks previously folded when the short-arc sampler missed mid points.
    """
    z = int(teeth)
    if z < 6:
        raise ValueError('Tooth count must be at least 6.')
    da = float(outside_diameter)
    if da <= 0:
        raise ValueError('Outside diameter must be greater than zero.')

    m = module_from_outside_diameter(da, z)
    d = m * z
    ra = da * 0.5
    rf = max(0.5 * m * (z - 2.25), 0.22 * m)

    pitch_ang = 2.0 * math.pi / float(z)
    # Narrow tip, moderate base; leave a wide gap so gullets can be true U-arcs.
    tip_half = pitch_ang * 0.10
    root_half = pitch_ang * 0.22
    gap = pitch_ang - 2.0 * root_half
    if gap < pitch_ang * 0.30:
        root_half = pitch_ang * 0.20
        gap = pitch_ang - 2.0 * root_half

    # Flanks meet the tip arch below OD so the rounded tip can peak at ra.
    tip_meet_r = ra - ra * math.sin(tip_half) * 0.55
    tip_r = _point_on_circle(tip_meet_r, -tip_half)
    root_r = _point_on_circle(rf, -root_half)

    # Mid-flank control: gently convex ogival flank, no thin neck.
    mid_ang = -0.5 * (tip_half + root_half)
    mid_r = 0.58 * ra + 0.42 * rf
    mid = _point_on_circle(mid_r, mid_ang)

    right = _arc_through_three_points(
        root_r, mid, tip_r, max(int(flank_steps), 5))
    left = [(p[0], -p[1], 0.0) for p in right]

    tip_arc = _tip_arch(ra, tip_half, tip_meet_r, max(int(tip_steps), 4))

    tooth = [_point_on_circle(rf, -root_half)]
    tooth.extend(right[1:-1])
    tooth.extend(tip_arc)
    tooth.extend(list(reversed(left))[1:-1])
    tooth.append(_point_on_circle(rf, root_half))

    outline = []
    for i in range(z):
        rot = pitch_ang * float(i)
        for x, y, _z in (tooth if i == 0 else tooth[1:]):
            rx, ry = _rotate(x, y, rot)
            outline.append((rx, ry, 0.0))

        a0 = root_half + rot
        a1 = -root_half + pitch_ang * float(i + 1)
        while a1 <= a0:
            a1 += 2.0 * math.pi
        outline.extend(_u_root_fillet(rf, a0, a1, max(int(root_steps), 6))[1:])

    if len(outline) < 8:
        raise RuntimeError('Failed to build gear outline points.')
    if len(outline) > 1:
        outline.pop()
    outline.append(outline[0])
    return outline, m, d, rf * 2.0


def _tip_arch(ra, tip_half, tip_meet_r, steps):
    """Rounded tip arch: flanks meet below OD, peak on the outside diameter."""
    p0 = _point_on_circle(tip_meet_r, -tip_half)
    p1 = _point_on_circle(ra, 0.0)
    p2 = _point_on_circle(tip_meet_r, tip_half)
    return _arc_through_three_points(p0, p1, p2, max(int(steps), 4))


def _u_root_fillet(rf, a0, a1, steps):
    """Semicircular U gullet between tooth feet (not a flat root chord)."""
    mid = 0.5 * (a0 + a1)
    p0 = _point_on_circle(rf, a0)
    p2 = _point_on_circle(rf, a1)
    # Diameter = chord between feet; arc digs inward toward the axis.
    mx = 0.5 * (p0[0] + p2[0])
    my = 0.5 * (p0[1] + p2[1])
    half = 0.5 * math.hypot(p2[0] - p0[0], p2[1] - p0[1])
    if half < 1e-12:
        return [p0, p2]
    # Soften slightly from a full semicircle so flanks meet the U cleanly.
    dig = half * 0.92
    p1 = (mx - dig * math.cos(mid), my - dig * math.sin(mid), 0.0)
    return _arc_through_three_points(p0, p1, p2, max(int(steps), 6))



def _arc_through_three_points(p0, p1, p2, steps):
    """Sample the circle through three points from p0 to p2 via p1."""
    ax, ay = p0[0], p0[1]
    bx, by = p1[0], p1[1]
    cx, cy = p2[0], p2[1]
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        pts = []
        for i in range(steps + 1):
            t = float(i) / float(steps)
            pts.append((ax + (cx - ax) * t, ay + (cy - ay) * t, 0.0))
        return pts
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) +
          (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) +
          (cx * cx + cy * cy) * (bx - ax)) / d
    return _arc_points_about_center_via(ux, uy, p0, p1, p2, steps)


def _circle_circle_intersect_near(x0, y0, r0, x1, y1, r1, target_angle=0.0):
    """Intersection of two circles; pick the point whose polar angle is nearest target."""
    dx = x1 - x0
    dy = y1 - y0
    dist = math.hypot(dx, dy)
    if dist < 1e-12 or dist > r0 + r1 + 1e-9 or dist < abs(r0 - r1) - 1e-9:
        return None
    # Distance from c0 to line of centers foot.
    aa = (r0 * r0 - r1 * r1 + dist * dist) / (2.0 * dist)
    h_sq = r0 * r0 - aa * aa
    if h_sq < -1e-9:
        return None
    h = math.sqrt(max(h_sq, 0.0))
    xm = x0 + aa * dx / dist
    ym = y0 + aa * dy / dist
    rx = -dy * (h / dist)
    ry = dx * (h / dist)
    p_a = (xm + rx, ym + ry, 0.0)
    p_b = (xm - rx, ym - ry, 0.0)
    if abs(_polar_angle(p_a[0], p_a[1]) - target_angle) <= abs(
            _polar_angle(p_b[0], p_b[1]) - target_angle):
        return p_a
    return p_b


def _arc_points_about_center(cx, cy, p_start, p_end, steps):
    """Points along the shorter arc about (cx,cy) from p_start to p_end."""
    a0 = math.atan2(p_start[1] - cy, p_start[0] - cx)
    a1 = math.atan2(p_end[1] - cy, p_end[0] - cx)
    # Walk the shorter signed delta.
    delta = (a1 - a0 + math.pi) % (2.0 * math.pi) - math.pi
    radius = math.hypot(p_start[0] - cx, p_start[1] - cy)
    pts = []
    for i in range(steps + 1):
        t = float(i) / float(steps)
        ang = a0 + delta * t
        pts.append((cx + radius * math.cos(ang), cy + radius * math.sin(ang), 0.0))
    # Snap ends exactly.
    pts[0] = (float(p_start[0]), float(p_start[1]), 0.0)
    pts[-1] = (float(p_end[0]), float(p_end[1]), 0.0)
    return pts


def _arc_points_about_center_via(cx, cy, p_start, p_via, p_end, steps):
    """Arc about (cx,cy) from p_start to p_end that passes through p_via."""
    a0 = math.atan2(p_start[1] - cy, p_start[0] - cx)
    a1 = math.atan2(p_via[1] - cy, p_via[0] - cx)
    a2 = math.atan2(p_end[1] - cy, p_end[0] - cx)
    # Choose the direction where p_via lies between start and end.
    d02_ccw = (a2 - a0) % (2.0 * math.pi)
    d01_ccw = (a1 - a0) % (2.0 * math.pi)
    if d01_ccw <= d02_ccw + 1e-9:
        delta = d02_ccw
    else:
        delta = -((a0 - a2) % (2.0 * math.pi))
    if abs(delta) < 1e-12:
        delta = d02_ccw if d02_ccw > 1e-12 else -((a0 - a2) % (2.0 * math.pi))
    radius = math.hypot(p_start[0] - cx, p_start[1] - cy)
    pts = []
    for i in range(steps + 1):
        t = float(i) / float(steps)
        ang = a0 + delta * t
        pts.append((cx + radius * math.cos(ang), cy + radius * math.sin(ang), 0.0))
    pts[0] = (float(p_start[0]), float(p_start[1]), 0.0)
    pts[-1] = (float(p_end[0]), float(p_end[1]), 0.0)
    return pts


def _assemble_mirrored_teeth(right, left, z, ra, rf, tip_steps, root_steps):
    """Build full outline from one mirrored tooth (right/left root→tip)."""
    right_foot_ang = _polar_angle(right[0][0], right[0][1])
    left_foot_ang = _polar_angle(left[0][0], left[0][1])
    right_tip_ang = _polar_angle(right[-1][0], right[-1][1])
    left_tip_ang = _polar_angle(left[-1][0], left[-1][1])

    tip_a0 = right_tip_ang
    tip_a1 = left_tip_ang
    while tip_a1 <= tip_a0:
        tip_a1 += 2.0 * math.pi
    tip_arc = _arc_points(ra, tip_a0, tip_a1, tip_steps)

    # Snap feet to the root circle for clean inter-tooth root arcs.
    tooth = [_point_on_circle(rf, right_foot_ang)]
    tooth.extend(right[1:-1])
    tooth.extend(tip_arc)
    tooth.extend(list(reversed(left))[1:-1])
    tooth.append(_point_on_circle(rf, left_foot_ang))

    outline = []
    for i in range(z):
        rot = (2.0 * math.pi) * (float(i) / float(z))
        for x, y, _z in tooth:
            rx, ry = _rotate(x, y, rot)
            outline.append((rx, ry, 0.0))

        next_rot = (2.0 * math.pi) * (float(i + 1) / float(z))
        a0 = left_foot_ang + rot
        a1 = right_foot_ang + next_rot
        while a1 <= a0:
            a1 += 2.0 * math.pi
        span = a1 - a0
        if 1e-8 < span < (2.0 * math.pi / z) * 0.98:
            outline.extend(_arc_points(rf, a0, a1, root_steps)[1:])

    if len(outline) < 8:
        raise RuntimeError('Failed to build gear outline points.')

    outline.append(outline[0])
    return outline
