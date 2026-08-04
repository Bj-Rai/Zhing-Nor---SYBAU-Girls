"""
highway_scene.py
"Highway to the Urban Market" — a perspective road driving sequence.
Road recedes toward a vanishing point with a city skyline on the horizon,
rolling hills and pine trees on either side, drifting clouds, and a truck
driving toward the city. Traffic-light checkpoints pop a math quiz.

CAMERA SYSTEM
-------------
This build adds a CameraManager that lets the player switch between three
perspectives at any time with the 1 / 2 / 3 keys:

    1 - First-person  (inside the cab, looking through the windshield)
    2 - Second-person  (a chase drone hovering ahead of the truck, looking
                         back at its front end as it "approaches" you)
    3 - Third-person   (classic behind-and-above chase camera - this is
                         the original view the scene shipped with)

Because the road/scenery renderer is a pseudo-3D "scaling sprite" projector
(everything is placed via a single `project()` call that turns a distance
into a screen Y + scale, plus a fixed vanishing point X), there is no real
3D camera to move through space. Instead, CameraManager works by smoothly
interpolating the *parameters that feed the projector* every frame:
    - horizon_y   (where the vanishing point sits vertically -> camera
                   pitch/height)
    - bottom_y    (where the nearest geometry reaches -> camera height)
    - vp_x_offset (lateral shift of the vanishing point -> camera sway)
    - width_mult  (how wide the road/scenery spread out near the camera
                   -> field of view / "zoom")
    - scale_mult  (extra multiplier on sprite scale -> field of view)

All of the drawing classes (PerspectiveRoad, CityBackground, TrafficLight)
now accept these as optional overrides instead of always reading
self.horizon_y / self.vp_x, so the same renderer produces three distinct,
smoothly-blended perspectives without duplicating any drawing code.

The "second-person" view is a deliberate approximation: a literal camera
sitting in oncoming traffic facing backwards isn't something this
renderer's math can produce without a full rewrite (it only ever draws
things *ahead* of a single travel position). Instead we simulate a small
drone/chase vehicle that flies a fixed distance ahead of the truck facing
back at it - the world keeps scrolling by exactly as normal (so traffic
lights, trees, and the skyline all stay correct) while the truck itself is
re-drawn as a distinct "front view" sprite (headlights/grille) that gently
breathes closer/farther via a slow sine-wave "lead distance" so it doesn't
feel like a frozen photo. This is called out again at the call site below.

FIRST-PERSON COCKPIT
---------------------
The first-person dashboard (TruckController.draw_dashboard) was reworked
to feel like a real cab instead of a flat brown rectangle: it now has a
lit instrument cluster with a live speedometer + tachometer (needles that
actually track the truck's current speed), a warning-light strip, a
two-tone leather-and-rubber steering wheel with hands gripping the rim,
tinted A-pillars with a wing mirror, a rear-view mirror with a small
painted reflection, sun visors, and a soft animated glare band across the
top of the dash so the glass doesn't read as pitch black.
"""

import pygame
import random
import math
import array

# ==========================================
# CONSTANTS
# ==========================================
SKY_TOP = (110, 185, 232)
SKY_BOTTOM = (205, 232, 246)
HILL_FAR = (146, 202, 116)
HILL_NEAR = (104, 178, 92)
ROAD_COLOR = (78, 82, 94)
ROAD_EDGE_COLOR = (238, 238, 238)
CENTER_LINE_COLOR = (250, 205, 60)
SKYLINE_FAR = (168, 190, 214)
SKYLINE_NEAR = (128, 150, 182)

RENDER_DISTANCE = 1000.0
CRUISE_SPEED = 230.0
ACCEL = 160.0
SLOWDOWN_DISTANCE = 340.0
STOP_MARGIN = 4.0
CHECKPOINT_DISTANCES = [1500, 3100, 4700, 6300]
FINAL_DISTANCE = 7400


def _hash01(n):
    n = (n * 2654435761) & 0xFFFFFFFF
    return (n % 10000) / 10000.0


def project(rd, horizon_y, bottom_y, scale_mult=1.0):
    """rd = relative world distance ahead of the truck.
    Returns (depth 0..1, scale, screen_y).
    `scale_mult` is an extra multiplier applied on top of the normal
    depth-based scale - used by the camera system to simulate a
    wider/narrower field of view (e.g. the first-person view zooms in
    slightly since the driver's eye is much closer to the windshield)."""
    t = max(0.0, min(1.0, 1.0 - rd / RENDER_DISTANCE))
    depth = t * t
    y = horizon_y + (bottom_y - horizon_y) * depth
    scale = (0.045 + 0.955 * depth) * scale_mult
    return depth, scale, y


def _lerp(a, b, t):
    return a + (b - a) * t


# ==========================================
# CAMERA MANAGER
# ==========================================
class CameraManager:
    """
    Owns the current camera perspective and smoothly blends the render
    parameters (horizon, vanishing-point x, near-plane y, field-of-view
    multipliers) toward whichever mode is active. Nothing here touches
    gameplay state - it only produces numbers the drawing code consumes,
    so switching views can never break the simulation underneath it.
    """

    FIRST_PERSON = "first_person"
    SECOND_PERSON = "second_person"
    THIRD_PERSON = "third_person"

    # How quickly parameters chase their target each second. Higher =
    # snappier, lower = more floaty/cinematic. Tuned per-parameter so
    # e.g. FOV changes feel smooth without making the camera feel laggy.
    SMOOTH_POSITION = 6.0
    SMOOTH_FOV = 4.0
    SMOOTH_SWAY = 8.0

    def __init__(self, screen_w, screen_h, base_horizon_y, base_bottom_y, base_vp_x):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.base_horizon_y = base_horizon_y
        self.base_bottom_y = base_bottom_y
        self.base_vp_x = base_vp_x

        self.mode = self.THIRD_PERSON

        # Current (smoothed) render parameters - start already settled on
        # the third-person defaults so the game opens exactly as before.
        self.horizon_y = base_horizon_y
        self.bottom_y = base_bottom_y
        self.vp_x_offset = 0.0
        self.width_mult = 1.0
        self.scale_mult = 1.0
        self.truck_visible = True
        self.truck_draw_mode = "rear"  # "rear", "front", or "hidden"

        # Slow breathing motion used by the second-person "chase drone" so
        # the truck doesn't look like a static cut-out glued to the screen.
        self._lead_wave_t = 0.0

        # Small lag buffer so lateral camera sway feels like it's actually
        # trailing the truck instead of teleporting with it (third person).
        self._sway_lag = 0.0

    # ---- input -------------------------------------------------------
    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_1, pygame.K_KP1):
            self.mode = self.FIRST_PERSON
        elif event.key in (pygame.K_2, pygame.K_KP2):
            self.mode = self.SECOND_PERSON
        elif event.key in (pygame.K_3, pygame.K_KP3):
            self.mode = self.THIRD_PERSON

    # ---- target parameters per mode -----------------------------------
    def _targets_for_mode(self):
        """Returns the parameters this mode is trying to reach:
        (horizon_y, bottom_y, vp_x_offset, width_mult, scale_mult,
        truck_visible, truck_draw_mode)."""
        if self.mode == self.FIRST_PERSON:
            # Sitting low, right behind the windshield. The crop used to
            # be very aggressive (horizon pushed down, bottom pulled way
            # up) which made the visible sliver of road/sky tiny and flat
            # next to a huge plain dashboard. Loosened both so more of
            # the road, horizon and sky are actually visible above the
            # (now much more detailed) dash, while still keeping a
            # slightly zoomed-in "close to the glass" feel.
            horizon_y = self.base_horizon_y - 4
            bottom_y = self.base_bottom_y - 20
            vp_x_offset = 0.0
            width_mult = 0.88
            scale_mult = 1.14
            truck_visible = False
            truck_draw_mode = "hidden"
        elif self.mode == self.SECOND_PERSON:
            # A drone hovering a fixed distance ahead, facing back at the
            # truck. The road/scenery keep scrolling exactly as normal
            # (still the same forward direction of travel), but the truck
            # is re-drawn as a distinct "front view" sprite sitting low
            # and large in frame, as if driving straight at the viewer.
            horizon_y = self.base_horizon_y - 6
            bottom_y = self.base_bottom_y
            vp_x_offset = 0.0
            width_mult = 1.0
            scale_mult = 1.0
            truck_visible = True
            truck_draw_mode = "front"
        else:  # THIRD_PERSON
            horizon_y = self.base_horizon_y
            bottom_y = self.base_bottom_y
            vp_x_offset = 0.0
            width_mult = 1.0
            scale_mult = 1.0
            truck_visible = True
            truck_draw_mode = "rear"
        return horizon_y, bottom_y, vp_x_offset, width_mult, scale_mult, truck_visible, truck_draw_mode

    # ---- per-frame update ----------------------------------------------
    def update(self, dt, truck):
        (t_horizon, t_bottom, t_vpx, t_width, t_scale,
         t_visible, t_draw_mode) = self._targets_for_mode()

        # Smoothly interpolate every continuous parameter toward its
        # target instead of snapping, so switching camera modes reads as
        # a deliberate transition rather than a jump-cut.
        pos_a = 1.0 - math.exp(-self.SMOOTH_POSITION * dt)
        fov_a = 1.0 - math.exp(-self.SMOOTH_FOV * dt)

        self.horizon_y = _lerp(self.horizon_y, t_horizon, pos_a)
        self.bottom_y = _lerp(self.bottom_y, t_bottom, pos_a)
        self.width_mult = _lerp(self.width_mult, t_width, fov_a)
        self.scale_mult = _lerp(self.scale_mult, t_scale, fov_a)

        # Booleans/enums just switch instantly - only numeric params blend.
        self.truck_visible = t_visible
        self.truck_draw_mode = t_draw_mode

        # Lateral sway: in third-person the camera trails the truck's own
        # side-to-side sway with a short lag for a "modern chase-cam"
        # feel; in the other modes the camera is rigidly mounted, so it
        # matches the truck's sway 1:1 (no lag).
        if self.mode == self.THIRD_PERSON:
            sway_a = 1.0 - math.exp(-self.SMOOTH_SWAY * dt)
            self._sway_lag = _lerp(self._sway_lag, truck.sway, sway_a)
            self.vp_x_offset = self._sway_lag * 0.5
        else:
            self._sway_lag = truck.sway
            self.vp_x_offset = 0.0

        self._lead_wave_t += dt

    # ---- convenience getters used by the drawing code -------------------
    def lead_distance_wave(self):
        """Slow breathing distance offset for the second-person chase
        drone, in world units. Keeps that view feeling alive."""
        return math.sin(self._lead_wave_t * 0.6) * 14.0

    def vp_x(self):
        return self.base_vp_x + self.vp_x_offset


# ==========================================
# FADE TRANSITION
# ==========================================
class FadeTransition:
    def __init__(self, duration=0.7):
        self.duration = duration
        self.timer = 0.0
        self.state = "in"

    def start(self):
        self.timer = 0.0
        self.state = "in"

    def begin_out(self):
        self.timer = 0.0
        self.state = "out"

    def update(self, dt):
        if self.state in ("in", "out"):
            self.timer += dt
            if self.timer >= self.duration:
                self.timer = self.duration
                self.state = "held" if self.state == "in" else "done"

    def get_alpha(self):
        if self.state == "in":
            return int(255 * (1 - self.timer / self.duration))
        elif self.state == "held":
            return 0
        elif self.state == "out":
            return int(255 * (self.timer / self.duration))
        return 255

    def is_done_fading_out(self):
        return self.state == "done"

    def draw(self, surf):
        a = self.get_alpha()
        if a > 0:
            overlay = pygame.Surface(surf.get_size())
            overlay.fill((0, 0, 0))
            overlay.set_alpha(a)
            surf.blit(overlay, (0, 0))


# ==========================================
# SOUND MANAGER
# ==========================================
class SoundManager:
    def __init__(self):
        self.enabled = True
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2)
            self.sample_rate = 44100
            self.sounds["correct"] = self._tone_sequence([(523, 90), (659, 90), (784, 140)], 0.25)
            self.sounds["wrong"] = self._tone_sequence([(220, 160), (180, 200)], 0.22)
            self.sounds["light"] = self._tone_sequence([(392, 120)], 0.18)
            self.sounds["arrive"] = self._tone_sequence(
                [(523, 100), (659, 100), (784, 100), (988, 220)], 0.25
            )
            self.sounds["camera"] = self._tone_sequence([(660, 60), (880, 70)], 0.16)
        except Exception:
            self.enabled = False

    def _tone(self, freq, duration_ms, volume):
        n = int(self.sample_rate * duration_ms / 1000)
        buf = array.array('h', [0] * n * 2)
        amp = int(32767 * volume)
        for i in range(n):
            t = i / self.sample_rate
            env = 1.0
            fade = max(1, int(n * 0.12))
            if i < fade:
                env = i / fade
            elif i > n - fade:
                env = (n - i) / fade
            s = int(amp * env * math.sin(2 * math.pi * freq * t))
            buf[2 * i] = s
            buf[2 * i + 1] = s
        return buf

    def _tone_sequence(self, notes, volume):
        full = array.array('h', [])
        for freq, dur in notes:
            full.extend(self._tone(freq, dur, volume))
        return pygame.mixer.Sound(buffer=full)

    def play(self, name):
        if self.enabled and name in self.sounds:
            try:
                self.sounds[name].play()
            except Exception:
                pass


# ==========================================
# CAMERA (world scroll position - unrelated to CameraManager's view mode)
# ==========================================
class Camera:
    """Tracks how far along the road the truck has traveled. Kept
    separate from CameraManager on purpose: this is *simulation* state
    (where the truck physically is), while CameraManager is purely a
    *presentation* concern (how we're looking at that state)."""
    def __init__(self):
        self.distance = 0.0


# ==========================================
# CLOUD
# ==========================================
class Cloud:
    def __init__(self, x, y, scale, speed):
        self.x = x
        self.y = y
        self.scale = scale
        self.speed = speed

    def update(self, dt):
        self.x -= self.speed * dt

    def draw(self, surf, screen_w):
        sx = self.x % (screen_w + 300) - 150
        s = self.scale
        col = (255, 255, 255)
        pygame.draw.ellipse(surf, col, (sx, self.y, 60 * s, 22 * s))
        pygame.draw.ellipse(surf, col, (sx + 18 * s, self.y - 9 * s, 44 * s, 22 * s))
        pygame.draw.ellipse(surf, col, (sx + 36 * s, self.y, 50 * s, 18 * s))


# ==========================================
# CITY BACKGROUND (sky, clouds, skyline, rolling hills)
# ==========================================
class CityBackground:
    def __init__(self, screen_w, screen_h, horizon_y):
        self.w = screen_w
        self.h = screen_h
        self.horizon_y = horizon_y
        self.drift = 0.0

        self.clouds = [
            Cloud(random.randint(0, screen_w), random.randint(15, int(horizon_y * 0.4)),
                  random.uniform(0.8, 1.4), random.uniform(4, 10))
            for _ in range(5)
        ]

        random.seed(55)
        self.buildings_far = self._make_skyline(screen_w * 1.6, 90, 190, 26, 46, SKYLINE_FAR)
        self.buildings_near = self._make_skyline(screen_w * 1.6, 60, 260, 22, 40, SKYLINE_NEAR)
        random.seed()

        random.seed(88)
        self.hill_far_pts = self._wavy_points(screen_w * 1.6, horizon_y - 6, 16, 140)
        self.hill_near_pts = self._wavy_points(screen_w * 1.6, horizon_y + 18, 20, 170)
        random.seed()

    def _make_skyline(self, span, min_h, max_h, min_w, max_w, color):
        buildings = []
        x = 0
        while x < span:
            w = random.randint(min_w, max_w)
            h = random.randint(min_h, max_h)
            buildings.append((x, w, h, color))
            x += w + random.randint(4, 14)
        return buildings

    def _wavy_points(self, span, base_y, amplitude, wavelength):
        pts = []
        x = 0
        while x <= span:
            y = base_y + math.sin(x / wavelength) * amplitude
            pts.append((x, y))
            x += 18
        return pts

    def update(self, dt):
        for c in self.clouds:
            c.update(dt)
        self.drift += dt * 3.0

    def _draw_skyline(self, surf, buildings, span, base_y):
        offset = self.drift % span
        for x, w, h, color in buildings:
            for sx in (x - offset, x - offset + span):
                if -w <= sx <= self.w + w:
                    rect = pygame.Rect(sx, base_y - h, w, h)
                    pygame.draw.rect(surf, color, rect)
                    lit = tuple(min(255, c + 18) for c in color)
                    for wy in range(int(base_y - h) + 8, int(base_y) - 6, 14):
                        for wx in range(int(sx) + 6, int(sx + w) - 6, 12):
                            if _hash01(int(wx * 3 + wy * 7)) > 0.55:
                                pygame.draw.rect(surf, lit, (wx, wy, 4, 6))

    def _draw_hill(self, surf, pts, span, color, y_extra=0):
        offset = self.drift % span
        for base_off in (-offset, -offset + span):
            shifted = [(x + base_off, y + y_extra) for x, y in pts]
            poly = [(shifted[0][0], self.h)] + shifted + [(shifted[-1][0], self.h)]
            pygame.draw.polygon(surf, color, poly)

    def draw(self, surf, camera, progress, horizon_y=None):
        """`horizon_y` lets the active CameraManager perspective nudge the
        sky/hill/skyline horizon line up or down to match the road's
        horizon without needing a second copy of this class."""
        hy = self.horizon_y if horizon_y is None else int(horizon_y)
        hy = max(1, min(self.h - 1, hy))

        for i in range(hy):
            t = i / max(1, hy)
            r = int(SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * t)
            g = int(SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * t)
            b = int(SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * t)
            pygame.draw.line(surf, (r, g, b), (0, i), (self.w, i))
        if hy < self.h:
            pygame.draw.rect(surf, SKY_BOTTOM, (0, hy, self.w, self.h - hy))

        for c in self.clouds:
            c.draw(surf, self.w)

        y_shift = hy - self.horizon_y
        scale_boost = 1.0 + 0.35 * progress
        base_far = hy + 2
        base_near = hy + 6

        self._draw_skyline(surf, self.buildings_far, self.w * 1.6, base_far)
        self._draw_skyline(surf, self.buildings_near, self.w * 1.6, base_near + 6 * scale_boost)

        self._draw_hill(surf, self.hill_far_pts, self.w * 1.6, HILL_FAR, y_extra=y_shift)
        self._draw_hill(surf, self.hill_near_pts, self.w * 1.6, HILL_NEAR, y_extra=y_shift)


# ==========================================
# PERSPECTIVE ROAD (road surface + roadside trees)
# ==========================================
class PerspectiveRoad:
    def __init__(self, screen_w, screen_h, horizon_y):
        self.w = screen_w
        self.h = screen_h
        self.horizon_y = horizon_y
        self.bottom_y = int(screen_h * 0.99)
        self.top_half = 8
        self.bottom_half = int(screen_w * 0.40)
        self.vp_x = screen_w // 2
        self.tree_spacing = 85.0

    def half_width(self, depth, bottom_half=None):
        bh = self.bottom_half if bottom_half is None else bottom_half
        return self.top_half + (bh - self.top_half) * depth

    def draw_road(self, surf, camera, horizon_y=None, bottom_y=None, vp_x=None, width_mult=1.0):
        """All four optional overrides come from the active CameraManager
        perspective; when omitted the road renders exactly as it did in
        the original single-view build (third-person defaults)."""
        hy = self.horizon_y if horizon_y is None else horizon_y
        by = self.bottom_y if bottom_y is None else bottom_y
        vx = self.vp_x if vp_x is None else vp_x
        bottom_half = self.bottom_half * width_mult

        top_pts = [(vx - self.top_half, hy), (vx + self.top_half, hy)]
        bottom_pts = [(vx + bottom_half, by), (vx - bottom_half, by)]
        pygame.draw.polygon(surf, ROAD_COLOR, top_pts + bottom_pts)

        pygame.draw.line(surf, ROAD_EDGE_COLOR, top_pts[0], bottom_pts[1], 3)
        pygame.draw.line(surf, ROAD_EDGE_COLOR, top_pts[1], bottom_pts[0], 3)

        dash_spacing = 70.0
        offset = camera.distance % dash_spacing
        n_dashes = 26
        for i in range(n_dashes):
            rd_far = i * dash_spacing - offset + dash_spacing * 0.35
            rd_near = i * dash_spacing - offset
            if rd_near < 0 or rd_near > RENDER_DISTANCE:
                continue
            _, _, y_near = project(max(0, rd_near), hy, by)
            _, _, y_far = project(max(0, rd_far), hy, by)
            if y_far >= y_near:
                continue
            w_near = max(2, int(6 * (1 - rd_near / RENDER_DISTANCE)))
            pygame.draw.polygon(surf, CENTER_LINE_COLOR, [
                (vx - w_near // 2, y_near), (vx + w_near // 2, y_near),
                (vx + 1, y_far), (vx - 1, y_far)
            ])

    def _draw_tree(self, surf, sx, sy, scale, color_a, color_b):
        trunk_h = max(2, int(14 * scale))
        trunk_w = max(1, int(4 * scale))
        pygame.draw.rect(surf, (100, 68, 42), (sx - trunk_w // 2, sy - trunk_h, trunk_w, trunk_h))
        r = max(2, int(16 * scale))
        pygame.draw.circle(surf, color_a, (int(sx), int(sy - trunk_h - r * 0.55)), r)
        pygame.draw.circle(surf, color_b, (int(sx - r * 0.3), int(sy - trunk_h - r * 0.85)), int(r * 0.65))

    def _draw_pine(self, surf, sx, sy, scale, color_a, color_b):
        trunk_h = max(2, int(6 * scale))
        pygame.draw.rect(surf, (90, 60, 40), (sx - max(1, int(2 * scale)), sy - trunk_h, max(2, int(4 * scale)), trunk_h))
        h = max(6, int(34 * scale))
        w = max(4, int(20 * scale))
        top_y = sy - trunk_h - h
        for i, frac in enumerate((1.0, 0.68, 0.36)):
            tier_w = w * frac
            tier_y = top_y + h * (1 - frac) * 0.9
            col = color_a if i % 2 == 0 else color_b
            pygame.draw.polygon(surf, col, [
                (sx, tier_y), (sx - tier_w / 2, tier_y + h * 0.42), (sx + tier_w / 2, tier_y + h * 0.42)
            ])

    def draw_roadside(self, surf, camera, horizon_y=None, bottom_y=None, vp_x=None,
                       width_mult=1.0, scale_mult=1.0):
        hy = self.horizon_y if horizon_y is None else horizon_y
        by = self.bottom_y if bottom_y is None else bottom_y
        vx = self.vp_x if vp_x is None else vp_x
        bottom_half = self.bottom_half * width_mult

        start_i = int((camera.distance) // self.tree_spacing) - 1
        end_i = int((camera.distance + RENDER_DISTANCE) // self.tree_spacing) + 1
        entries = []
        for i in range(start_i, end_i):
            world_x = i * self.tree_spacing
            rd = world_x - camera.distance
            if rd < -20 or rd > RENDER_DISTANCE:
                continue
            depth, scale, y = project(max(0, rd), hy, by, scale_mult)
            half_w = self.half_width(depth, bottom_half)
            for side, seed_off in ((-1, 0), (1, 500)):
                h = _hash01(i * 7919 + seed_off)
                lane = 1.15 + h * 0.55
                sx = vx + side * half_w * lane
                jitter_y = (_hash01(i * 131 + seed_off) - 0.5) * 6 * scale
                sy = y + jitter_y
                kind_roll = _hash01(i * 37 + seed_off)
                tscale = scale * (0.75 + _hash01(i * 971 + seed_off) * 0.6)
                entries.append((depth, sx, sy, tscale, kind_roll))

        entries.sort(key=lambda e: e[0])
        for depth, sx, sy, tscale, kind_roll in entries:
            if kind_roll > 0.5:
                self._draw_pine(surf, sx, sy, tscale, (44, 118, 58), (58, 138, 70))
            else:
                self._draw_tree(surf, sx, sy, tscale, (56, 140, 66), (70, 158, 78))


# ==========================================
# TRAFFIC LIGHT
# ==========================================
class TrafficLight:
    def __init__(self, index, world_x):
        self.index = index
        self.world_x = world_x
        self.state = "red"
        self.solved = False

    def set_green(self):
        self.state = "green"
        self.solved = True

    def draw(self, surf, camera, road, horizon_y=None, bottom_y=None, vp_x=None,
              width_mult=1.0, scale_mult=1.0):
        hy = road.horizon_y if horizon_y is None else horizon_y
        by = road.bottom_y if bottom_y is None else bottom_y
        vx = road.vp_x if vp_x is None else vp_x
        bottom_half = road.bottom_half * width_mult

        rd = self.world_x - camera.distance
        if rd < -40 or rd > RENDER_DISTANCE:
            return
        depth, scale, y = project(max(0, rd), hy, by, scale_mult)
        half_w = road.half_width(depth, bottom_half)
        sx = vx + half_w * 1.05

        pole_h = max(10, int(90 * scale))
        pygame.draw.line(surf, (70, 74, 80), (sx, y), (sx, y - pole_h), max(1, int(4 * scale)))
        box_w = max(6, int(22 * scale))
        box_h = max(8, int(34 * scale))
        box = pygame.Rect(sx - box_w / 2, y - pole_h - box_h + 4, box_w, box_h)
        pygame.draw.rect(surf, (45, 48, 54), box, border_radius=max(1, int(4 * scale)))
        red_on = self.state == "red"
        green_on = self.state == "green"
        r_rad = max(1, int(box_w * 0.28))
        pygame.draw.circle(surf, (250, 70, 60) if red_on else (100, 45, 45),
                            (int(sx), int(box.y + box_h * 0.3)), r_rad)
        pygame.draw.circle(surf, (70, 220, 100) if green_on else (50, 90, 60),
                            (int(sx), int(box.y + box_h * 0.72)), r_rad)

        if depth > 0.02:
            line_w = max(2, int(6 * scale))
            pygame.draw.line(surf, (255, 255, 255),
                              (vx - half_w, y), (vx + half_w, y), line_w)


# ==========================================
# MATH QUIZ
# ==========================================
class MathQuiz:
    def __init__(self, sound_manager):
        self.sound = sound_manager
        self.active = False
        self.checkpoint_index = 0
        self.total_checkpoints = len(CHECKPOINT_DISTANCES)
        self.question_text = ""
        self.answer_value = 0.0
        self.input_text = ""
        self.feedback = None
        self.feedback_timer = 0.0
        self.shake_timer = 0.0
        self.shake_offset = 0.0
        self.on_success = None
        self.submit_button_rect = pygame.Rect(0, 0, 0, 0)

    def generate(self, level, checkpoint_index, on_success):
        self.checkpoint_index = checkpoint_index
        self.on_success = on_success
        self.input_text = ""
        self.feedback = None
        self.feedback_timer = 0.0
        self.active = True

        level = max(1, min(4, level))
        pools = {
            1: ["add_sub"],
            2: ["mul_div", "add_sub"],
            3: ["percent", "fraction", "geometry"],
            4: ["algebra", "geometry", "measurement", "percent"],
        }
        kind = random.choice(pools[level])

        if kind == "add_sub":
            a = random.randint(5, 45)
            b = random.randint(2, 40)
            if random.random() < 0.5:
                self.question_text = f"{a} + {b} = ?"
                self.answer_value = a + b
            else:
                a, b = max(a, b), min(a, b)
                self.question_text = f"{a} - {b} = ?"
                self.answer_value = a - b

        elif kind == "mul_div":
            a = random.randint(2, 12)
            b = random.randint(2, 12)
            if random.random() < 0.5:
                self.question_text = f"{a} × {b} = ?"
                self.answer_value = a * b
            else:
                product = a * b
                self.question_text = f"{product} ÷ {b} = ?"
                self.answer_value = a

        elif kind == "percent":
            p = random.choice([10, 20, 25, 50, 75])
            n = random.choice([20, 40, 60, 80, 120, 160, 200])
            self.question_text = f"What is {p}% of {n}?"
            self.answer_value = round(p * n / 100, 2)

        elif kind == "fraction":
            d = random.choice([4, 5, 6, 8])
            n1 = random.randint(1, d - 1)
            n2 = random.randint(1, d - 1)
            self.question_text = f"{n1}/{d} + {n2}/{d} = ? (as decimal)"
            self.answer_value = round((n1 + n2) / d, 2)

        elif kind == "geometry":
            shape = random.choice(["rect_area", "rect_perimeter", "triangle_area"])
            if shape == "rect_area":
                w = random.randint(3, 12)
                h = random.randint(3, 12)
                self.question_text = f"Rectangle: width {w}, height {h}.\nWhat is its area?"
                self.answer_value = w * h
            elif shape == "rect_perimeter":
                w = random.randint(3, 15)
                h = random.randint(3, 15)
                self.question_text = f"Rectangle: width {w}, height {h}.\nWhat is its perimeter?"
                self.answer_value = 2 * (w + h)
            else:
                b = random.randint(4, 16)
                h = random.randint(3, 12)
                self.question_text = f"Triangle: base {b}, height {h}.\nWhat is its area?"
                self.answer_value = round(0.5 * b * h, 2)

        elif kind == "algebra":
            a = random.randint(2, 9)
            x_val = random.randint(1, 12)
            b = random.randint(1, 20)
            c = a * x_val + b
            self.question_text = f"Solve for x:\n{a}x + {b} = {c}"
            self.answer_value = x_val

        elif kind == "measurement":
            choice = random.choice(["cm_to_m", "m_to_cm", "min_to_sec"])
            if choice == "cm_to_m":
                cm = random.randint(1, 20) * 100
                self.question_text = f"{cm} cm = ? meters"
                self.answer_value = cm / 100
            elif choice == "m_to_cm":
                m = random.randint(1, 20)
                self.question_text = f"{m} meters = ? cm"
                self.answer_value = m * 100
            else:
                mins = random.randint(1, 10)
                self.question_text = f"{mins} minutes = ? seconds"
                self.answer_value = mins * 60

    def handle_event(self, event):
        if not self.active or self.feedback == "correct":
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                self.submit()
            elif event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
            else:
                ch = event.unicode
                if ch and (ch.isdigit() or ch in ".-/") and len(self.input_text) < 12:
                    self.input_text += ch

    def _parse(self, text):
        text = text.strip()
        if not text:
            return None
        try:
            if "/" in text:
                num, den = text.split("/")
                return float(num) / float(den)
            return float(text)
        except (ValueError, ZeroDivisionError):
            return None

    def submit(self):
        val = self._parse(self.input_text)
        if val is None:
            self.feedback = "wrong"
            self.feedback_timer = 0.9
            self.shake_timer = 0.4
            self.sound.play("wrong")
            return
        if abs(val - self.answer_value) <= 0.05:
            self.feedback = "correct"
            self.feedback_timer = 0.9
            self.sound.play("correct")
        else:
            self.feedback = "wrong"
            self.feedback_timer = 0.9
            self.shake_timer = 0.4
            self.input_text = ""
            self.sound.play("wrong")

    def update(self, dt):
        if not self.active:
            return
        if self.shake_timer > 0:
            self.shake_timer -= dt
            self.shake_offset = math.sin(self.shake_timer * 60) * 6
        else:
            self.shake_offset = 0
        if self.feedback:
            self.feedback_timer -= dt
            if self.feedback_timer <= 0:
                if self.feedback == "correct":
                    self.active = False
                    cb = self.on_success
                    self.on_success = None
                    if cb:
                        cb()
                else:
                    self.feedback = None

    def draw(self, surf, screen_w, screen_h):
        if not self.active:
            return
        overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        surf.blit(overlay, (0, 0))

        panel_w, panel_h = 560, 340
        px = screen_w // 2 - panel_w // 2 + int(self.shake_offset)
        py = screen_h // 2 - panel_h // 2

        panel_color = (250, 248, 240)
        if self.feedback == "correct":
            panel_color = (225, 250, 225)
        elif self.feedback == "wrong":
            panel_color = (250, 225, 225)

        pygame.draw.rect(surf, panel_color, (px, py, panel_w, panel_h), border_radius=18)
        pygame.draw.rect(surf, (60, 140, 90), (px, py, panel_w, panel_h), 4, border_radius=18)

        font_small = pygame.font.Font(None, 22)
        label = font_small.render(
            f"Checkpoint {self.checkpoint_index + 1} of {self.total_checkpoints}", True, (70, 70, 70)
        )
        surf.blit(label, (px + panel_w // 2 - label.get_width() // 2, py + 18))
        dot_r = 8
        total_w = self.total_checkpoints * (dot_r * 2 + 10) - 10
        dot_x = px + panel_w // 2 - total_w // 2 + dot_r
        for i in range(self.total_checkpoints):
            color = (60, 180, 90) if i < self.checkpoint_index else \
                    (255, 200, 60) if i == self.checkpoint_index else (210, 210, 210)
            pygame.draw.circle(surf, color, (dot_x, py + 46), dot_r)
            dot_x += dot_r * 2 + 10

        font_title = pygame.font.Font(None, 34)
        title = font_title.render("🚦 Traffic Light Math Challenge", True, (40, 110, 75))
        surf.blit(title, (px + panel_w // 2 - title.get_width() // 2, py + 66))

        font_q = pygame.font.Font(None, 30)
        lines = self.question_text.split("\n")
        qy = py + 120
        for line in lines:
            qs = font_q.render(line, True, (40, 40, 45))
            surf.blit(qs, (px + panel_w // 2 - qs.get_width() // 2, qy))
            qy += 34

        box_w, box_h = 220, 46
        box_x = px + panel_w // 2 - box_w // 2
        box_y = qy + 14
        box_color = (255, 255, 255)
        border_color = (110, 170, 130)
        if self.feedback == "wrong":
            border_color = (210, 90, 90)
        elif self.feedback == "correct":
            border_color = (70, 180, 100)
        pygame.draw.rect(surf, box_color, (box_x, box_y, box_w, box_h), border_radius=10)
        pygame.draw.rect(surf, border_color, (box_x, box_y, box_w, box_h), 3, border_radius=10)
        font_input = pygame.font.Font(None, 32)
        txt = font_input.render(self.input_text or " ", True, (30, 30, 30))
        surf.blit(txt, (box_x + 14, box_y + 8))

        btn_w, btn_h = 150, 42
        btn_x = px + panel_w // 2 - btn_w // 2
        btn_y = box_y + box_h + 16
        pygame.draw.rect(surf, (80, 165, 110), (btn_x, btn_y, btn_w, btn_h), border_radius=12)
        pygame.draw.rect(surf, (40, 110, 75), (btn_x, btn_y, btn_w, btn_h), 2, border_radius=12)
        font_btn = pygame.font.Font(None, 26)
        btn_txt = font_btn.render("Submit (Enter)", True, (255, 255, 255))
        surf.blit(btn_txt, (btn_x + btn_w // 2 - btn_txt.get_width() // 2, btn_y + 10))

        if self.feedback == "correct":
            fb = font_q.render("✓ Correct! Light turning green...", True, (40, 150, 80))
            surf.blit(fb, (px + panel_w // 2 - fb.get_width() // 2, py + panel_h - 34))
        elif self.feedback == "wrong":
            fb = font_q.render("✗ Not quite — try again!", True, (190, 70, 70))
            surf.blit(fb, (px + panel_w // 2 - fb.get_width() // 2, py + panel_h - 34))

        self.submit_button_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

    def handle_click(self, pos):
        if self.active and self.feedback != "correct":
            if self.submit_button_rect.collidepoint(pos):
                self.submit()


# ==========================================
# TRUCK CONTROLLER (drives the physics + exposes multiple sprite views)
# ==========================================
class TruckController:
    """
    Holds the truck's motion state (speed, bounce, sway) and knows how to
    draw itself in three different ways so the CameraManager can pick
    whichever fits the active perspective:

        draw_rear()  - the original tailgate/bed view (third-person)
        draw_front() - a front-on grille/headlights view (second-person)
        draw_dashboard() - a cockpit overlay, not the truck itself, used
                           for first-person (the truck is invisible from
                           inside its own cab)

    `self.sway` is exposed (not just used internally) so CameraManager
    can read it to drive the third-person camera's lagged follow sway.
    """

    def __init__(self, screen_h, truck_surface=None):
        self.screen_h = screen_h
        self.speed = 0.0
        self.target_speed = CRUISE_SPEED
        self.bounce_t = 0.0
        self.sway_t = 0.0
        self.bounce = 0.0
        self.sway = 0.0

    def update(self, dt):
        if self.speed < self.target_speed:
            self.speed = min(self.target_speed, self.speed + ACCEL * dt)
        elif self.speed > self.target_speed:
            self.speed = max(self.target_speed, self.speed - ACCEL * 1.6 * dt)
        self.bounce_t += dt * (2 + self.speed / 55.0)
        self.sway_t += dt * 0.6
        self.bounce = math.sin(self.bounce_t * 6) * (1.6 if self.speed > 5 else 0.2)
        self.sway = math.sin(self.sway_t) * (4 if self.speed > 5 else 0)

    def draw(self, surf, vp_x, bottom_y):
        """Kept for backward compatibility - identical to draw_rear()."""
        self.draw_rear(surf, vp_x, bottom_y)

    def draw_rear(self, surf, vp_x, bottom_y):
        """Original rear/three-quarter view: what a chase camera behind
        the truck (third-person) sees - tailgate, cargo bed, taillights."""
        cx = vp_x + self.sway
        cy = bottom_y - 6 + self.bounce

        outline = (32, 42, 28)
        body = (58, 108, 64)
        dark = (40, 82, 46)

        pygame.draw.ellipse(surf, (25, 35, 20), (cx - 62, cy + 14, 124, 16))

        bed = pygame.Rect(cx - 58, cy - 62, 116, 50)
        pygame.draw.rect(surf, (128, 92, 50), bed, border_radius=4)
        pygame.draw.rect(surf, outline, bed, 3, border_radius=4)
        for i in range(4):
            gx = bed.x + 10 + i * (bed.w - 20) / 3
            pygame.draw.line(surf, (100, 70, 38), (gx, bed.y + 4), (gx, bed.bottom - 4), 2)

        for fx, fy, col in [(-30, -14, (210, 60, 55)), (-8, -20, (235, 150, 40)),
                             (14, -14, (90, 165, 70)), (34, -20, (210, 60, 55))]:
            pygame.draw.circle(surf, col, (int(cx + fx), int(bed.y + fy)), 10)
            pygame.draw.circle(surf, tuple(min(255, c + 30) for c in col), (int(cx + fx - 3), int(bed.y + fy - 3)), 4)

        cab = pygame.Rect(cx - 46, cy - 12, 92, 26)
        pygame.draw.rect(surf, body, cab, border_radius=6)
        pygame.draw.rect(surf, outline, cab, 3, border_radius=6)

        for wx in (cx - 24, cx + 24):
            pygame.draw.circle(surf, (170, 40, 35), (int(wx), int(cy - 2)), 5)

        for wx in (cx - 46, cx + 40):
            pygame.draw.circle(surf, (25, 25, 25), (int(wx), int(cy + 16)), 13)
            pygame.draw.circle(surf, (195, 195, 200), (int(wx), int(cy + 16)), 5)

        plate = pygame.Rect(cx - 22, cy + 6, 44, 12)
        pygame.draw.rect(surf, (240, 235, 220), plate, border_radius=2)
        pygame.draw.rect(surf, dark, plate, 1, border_radius=2)

    def draw_front(self, surf, vp_x, bottom_y, extra_scale=1.0):
        """Front-on view: grille, headlights, windshield - what a chase
        drone hovering ahead of the truck (second-person) sees as the
        truck 'approaches'. `extra_scale` lets the CameraManager's
        lead-distance breathing wave make it grow/shrink subtly."""
        s = extra_scale
        cx = vp_x + self.sway
        cy = bottom_y - 6 + self.bounce

        outline = (32, 42, 28)
        body = (58, 108, 64)
        light = (255, 244, 190)

        pygame.draw.ellipse(surf, (25, 35, 20), (cx - 60 * s, cy + 12 * s, 120 * s, 15 * s))

        # Front bumper / grille
        bumper = pygame.Rect(cx - 54 * s, cy - 6 * s, 108 * s, 20 * s)
        pygame.draw.rect(surf, (70, 70, 74), bumper, border_radius=int(4 * s))
        grille = pygame.Rect(cx - 30 * s, cy - 2 * s, 60 * s, 10 * s)
        pygame.draw.rect(surf, (35, 38, 40), grille, border_radius=int(2 * s))
        for gx in range(3):
            lx = grille.x + 8 * s + gx * 20 * s
            pygame.draw.line(surf, (60, 63, 66), (lx, grille.y + 2 * s), (lx, grille.bottom - 2 * s), max(1, int(2 * s)))

        # Cab / windshield facing the viewer
        cab = pygame.Rect(cx - 48 * s, cy - 46 * s, 96 * s, 42 * s)
        pygame.draw.rect(surf, body, cab, border_radius=int(8 * s))
        pygame.draw.rect(surf, outline, cab, max(1, int(3 * s)), border_radius=int(8 * s))
        windshield = pygame.Rect(cx - 38 * s, cy - 40 * s, 76 * s, 22 * s)
        pygame.draw.rect(surf, (180, 214, 224), windshield, border_radius=int(5 * s))
        pygame.draw.line(surf, outline, (cx, windshield.y), (cx, windshield.bottom), max(1, int(2 * s)))

        # Headlights
        for hx in (cx - 40 * s, cx + 40 * s):
            pygame.draw.circle(surf, light, (int(hx), int(cy - 4 * s)), max(3, int(9 * s)))
            pygame.draw.circle(surf, (255, 255, 255), (int(hx), int(cy - 4 * s)), max(1, int(4 * s)))

        # Wheels peeking out either side
        for wx in (cx - 56 * s, cx + 50 * s):
            pygame.draw.circle(surf, (25, 25, 25), (int(wx), int(cy + 14 * s)), max(4, int(12 * s)))
            pygame.draw.circle(surf, (195, 195, 200), (int(wx), int(cy + 14 * s)), max(2, int(5 * s)))

        # Front license plate
        plate = pygame.Rect(cx - 20 * s, cy + 4 * s, 40 * s, 11 * s)
        pygame.draw.rect(surf, (240, 235, 220), plate, border_radius=int(2 * s))
        pygame.draw.rect(surf, outline, plate, max(1, int(1 * s)), border_radius=int(2 * s))

    def draw_dashboard(self, surf, screen_w, screen_h):
        """First-person cockpit overlay: a real instrument cluster with
        live speedometer + tachometer needles, a warning-light strip, a
        two-tone steering wheel with hands on the rim, tinted A-pillars
        with a wing mirror, a rear-view mirror with a small painted
        reflection, sun visors, and an animated glass-glare band across
        the top of the dash. Everything bobs gently with the truck's own
        suspension motion (self.sway / self.bounce) so it stays feeling
        physically connected to the vehicle instead of a flat sticker."""
        bob_x = self.sway * 0.6
        bob_y = self.bounce * 0.8

        dash_h = int(screen_h * 0.25)
        dash_y = screen_h - dash_h
        dash_rect = pygame.Rect(0, dash_y, screen_w, dash_h).move(int(bob_x), int(bob_y))

        # --- animated glass-glare band, sitting just above the dash on
        # what would be the lower windshield, so the glass doesn't read
        # as a flat, lifeless boundary between world and cockpit.
        glare_h = 46
        glare_y = dash_rect.y - glare_h
        if glare_y + glare_h > 0:
            glare = pygame.Surface((screen_w, glare_h), pygame.SRCALPHA)
            shift = (math.sin(self.bounce_t * 0.15) * 0.5 + 0.5) * screen_w
            for gx in range(0, screen_w, 4):
                d = abs(((gx - shift + screen_w) % (screen_w * 2)) - screen_w)
                a = max(0, 34 - int(d * 34 / (screen_w * 0.5)))
                if a > 0:
                    pygame.draw.line(glare, (255, 255, 255, a), (gx, 0), (gx, glare_h))
            surf.blit(glare, (0, max(0, glare_y)))

        # --- dashboard body: vertical gradient + beveled top edge + trim ---
        for i in range(dash_rect.height):
            t = i / max(1, dash_rect.height - 1)
            r = int(_lerp(74, 26, t))
            g = int(_lerp(64, 22, t))
            b = int(_lerp(54, 19, t))
            pygame.draw.line(surf, (r, g, b), (dash_rect.x, dash_rect.y + i), (dash_rect.right, dash_rect.y + i))
        pygame.draw.rect(surf, (108, 94, 78), (dash_rect.x, dash_rect.y, dash_rect.w, 3))
        pygame.draw.rect(surf, (18, 15, 12), (dash_rect.x, dash_rect.y + 3, dash_rect.w, 3))
        for sx in range(0, screen_w, 14):
            pygame.draw.line(surf, (90, 78, 64),
                              (sx + bob_x, dash_rect.y + 10), (sx + 6 + bob_x, dash_rect.y + 10), 1)

        wheel_cx = screen_w / 2 + bob_x
        wheel_cy = screen_h - dash_h * 0.06 + bob_y
        wheel_r = int(screen_w * 0.11)

        # --- steering wheel: dark rubber ring, lighter inner grip, hub
        # emblem, three spokes with a metallic highlight line each.
        pygame.draw.circle(surf, (16, 14, 13), (int(wheel_cx), int(wheel_cy)), wheel_r + 3)
        pygame.draw.circle(surf, (32, 29, 27), (int(wheel_cx), int(wheel_cy)), wheel_r, width=max(7, wheel_r // 5))
        pygame.draw.circle(surf, (52, 47, 43), (int(wheel_cx), int(wheel_cy)), wheel_r - 3,
                            width=max(2, wheel_r // 16))
        for ang in (200, 340, 90):
            rad = math.radians(ang)
            end = (wheel_cx + math.cos(rad) * wheel_r * 0.92, wheel_cy + math.sin(rad) * wheel_r * 0.92)
            pygame.draw.line(surf, (24, 22, 20), (wheel_cx, wheel_cy), end, max(4, wheel_r // 9))
            pygame.draw.line(surf, (58, 52, 46), (wheel_cx, wheel_cy), end, max(1, wheel_r // 24))
        hub_r = max(5, wheel_r // 6)
        pygame.draw.circle(surf, (40, 36, 32), (int(wheel_cx), int(wheel_cy)), hub_r)
        pygame.draw.circle(surf, (205, 165, 60), (int(wheel_cx), int(wheel_cy)), max(2, hub_r // 2))

        # gloved hands resting on the rim at roughly 9 and 3 o'clock
        for side in (-1, 1):
            hx = wheel_cx + side * wheel_r * 0.97
            hy = wheel_cy + wheel_r * 0.12
            pygame.draw.ellipse(surf, (52, 40, 30), (hx - 15, hy - 11, 30, 24))
            pygame.draw.ellipse(surf, (66, 52, 40), (hx - 15 + side * 2, hy - 13, 20, 16))
            for k in range(3):
                lx = hx - 8 + k * 7
                pygame.draw.line(surf, (30, 22, 16), (lx, hy - 4), (lx, hy + 8), 2)

        # --- instrument cluster: analog speedometer (left of the wheel)
        # and tachometer (right), both driven by the truck's live speed
        # so the needle actually moves as you accelerate/brake/stop.
        speed_cx = wheel_cx - wheel_r * 2.15
        tach_cx = wheel_cx + wheel_r * 2.15
        gauge_cy = wheel_cy - wheel_r * 0.05
        gauge_r = max(28, int(wheel_r * 0.78))

        def draw_gauge(cx, cy, r, value, max_value, unit, needle_color):
            if cx < r or cx > screen_w - r:
                return
            pygame.draw.circle(surf, (14, 13, 12), (int(cx), int(cy)), r + 4)
            pygame.draw.circle(surf, (22, 24, 24), (int(cx), int(cy)), r)
            pygame.draw.circle(surf, (70, 210, 150), (int(cx), int(cy)), r, 2)
            start_ang, end_ang = 135, 405  # degrees, sweeping clockwise
            for tick in range(6):
                a = math.radians(start_ang + (end_ang - start_ang) * tick / 5)
                x1 = cx + math.cos(a) * r * 0.82
                y1 = cy + math.sin(a) * r * 0.82
                x2 = cx + math.cos(a) * r * 0.95
                y2 = cy + math.sin(a) * r * 0.95
                pygame.draw.line(surf, (200, 205, 205), (x1, y1), (x2, y2), 2)
            frac = max(0.0, min(1.0, value / max_value))
            needle_ang = math.radians(start_ang + (end_ang - start_ang) * frac)
            nx = cx + math.cos(needle_ang) * r * 0.72
            ny = cy + math.sin(needle_ang) * r * 0.72
            pygame.draw.line(surf, needle_color, (cx, cy), (nx, ny), 3)
            pygame.draw.circle(surf, (200, 200, 200), (int(cx), int(cy)), 4)
            font_g = pygame.font.Font(None, max(14, int(r * 0.5)))
            val_txt = font_g.render(str(int(value)), True, (230, 230, 230))
            surf.blit(val_txt, (cx - val_txt.get_width() / 2, cy + r * 0.28))
            font_lbl = pygame.font.Font(None, 14)
            lbl_txt = font_lbl.render(unit, True, (140, 200, 170))
            surf.blit(lbl_txt, (cx - lbl_txt.get_width() / 2, cy + r * 0.28 + val_txt.get_height() - 2))

        draw_gauge(speed_cx, gauge_cy, gauge_r, self.speed, max(CRUISE_SPEED * 1.3, 60), "km/h", (240, 90, 70))
        rpm = 1000 + (self.speed / max(1.0, CRUISE_SPEED)) * 4500
        draw_gauge(tach_cx, gauge_cy, gauge_r, rpm, 6000, "rpm x1000", (90, 170, 240))

        # warning-light strip between the gauges, just under the wheel
        lights = [("READY", (70, 220, 120), True), ("BATT", (90, 90, 95), False),
                  ("TEMP", (90, 90, 95), False), ("BELT", (90, 90, 95), False)]
        lx = wheel_cx - (len(lights) - 1) * 18
        ly = wheel_cy + wheel_r + 14
        if ly < screen_h - 4:
            for name, color, lit in lights:
                pygame.draw.circle(surf, color, (int(lx), int(ly)), 5)
                if lit:
                    pygame.draw.circle(surf, (200, 255, 220), (int(lx), int(ly)), 7, 1)
                lx += 36

        # --- A-pillars with an accent stripe matching the truck's body
        # color, plus a wing mirror mounted on the left pillar.
        pillar_w = int(screen_w * 0.05)
        pillar_col = (36, 32, 27)
        accent = (58, 108, 64)
        left_pillar = [(0, 0), (pillar_w, 0), (pillar_w * 0.42, dash_rect.y), (0, dash_rect.y)]
        right_pillar = [(screen_w - pillar_w, 0), (screen_w, 0),
                         (screen_w, dash_rect.y), (screen_w - pillar_w * 0.42, dash_rect.y)]
        pygame.draw.polygon(surf, pillar_col, left_pillar)
        pygame.draw.polygon(surf, pillar_col, right_pillar)
        pygame.draw.line(surf, accent, (pillar_w * 0.15, 8), (pillar_w * 0.55, dash_rect.y - 8), 4)
        pygame.draw.line(surf, accent, (screen_w - pillar_w * 0.15, 8), (screen_w - pillar_w * 0.55, dash_rect.y - 8), 4)

        mirror_arm_x = pillar_w * 0.3
        pygame.draw.line(surf, (30, 28, 25), (mirror_arm_x, 40), (mirror_arm_x - 14, 58), 3)
        pygame.draw.ellipse(surf, (40, 38, 35), (mirror_arm_x - 34, 50, 30, 20))
        pygame.draw.ellipse(surf, (170, 195, 205), (mirror_arm_x - 31, 53, 24, 14))

        # --- rear-view mirror with a tiny painted "reflection" so it
        # doesn't read as a blank grey rectangle.
        mirror_w, mirror_h = int(screen_w * 0.13), 30
        mirror_rect = pygame.Rect(screen_w // 2 - mirror_w // 2 + bob_x, 12 + bob_y, mirror_w, mirror_h)
        pygame.draw.line(surf, (30, 28, 25), (screen_w // 2 + bob_x, 0), (screen_w // 2 + bob_x, mirror_rect.y), 3)
        pygame.draw.rect(surf, (30, 28, 25), mirror_rect, border_radius=6)
        glass_rect = mirror_rect.inflate(-6, -8)
        if glass_rect.width > 0 and glass_rect.height > 0:
            for i in range(glass_rect.height):
                t = i / max(1, glass_rect.height - 1)
                r = int(_lerp(150, 195, t))
                g = int(_lerp(180, 215, t))
                b = int(_lerp(195, 225, t))
                pygame.draw.line(surf, (r, g, b), (glass_rect.x, glass_rect.y + i), (glass_rect.right, glass_rect.y + i))
            pygame.draw.line(surf, (90, 150, 100), (glass_rect.x, glass_rect.bottom - 4),
                              (glass_rect.right, glass_rect.bottom - 4), 2)
        pygame.draw.rect(surf, (15, 14, 13), mirror_rect, 2, border_radius=6)

        # sun visors tucked into the top corners
        for side in (-1, 1):
            vx = screen_w / 2 + side * screen_w * 0.30 + bob_x
            visor = pygame.Rect(vx - 30, 2 + bob_y, 60, 10)
            pygame.draw.rect(surf, (52, 46, 40), visor, border_radius=3)


# ==========================================
# UI (progress bar / status text)
# ==========================================
class UI:
    def __init__(self, screen_w):
        self.screen_w = screen_w
        self.font = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 20)

    def draw(self, surf, distance, total_distance, checkpoints, phase, camera_mode_label=None):
        bar_w = self.screen_w - 80
        bar_x, bar_y = 40, 20
        pygame.draw.rect(surf, (255, 255, 255), (bar_x, bar_y, bar_w, 14), border_radius=7)
        pygame.draw.rect(surf, (100, 110, 120), (bar_x, bar_y, bar_w, 14), 2, border_radius=7)
        progress = max(0.0, min(1.0, distance / total_distance))
        pygame.draw.rect(surf, (90, 200, 120), (bar_x, bar_y, int(bar_w * progress), 14), border_radius=7)

        for cp in checkpoints:
            cp_progress = cp.world_x / total_distance
            cx = bar_x + int(bar_w * cp_progress)
            color = (60, 200, 90) if cp.solved else (230, 230, 230)
            pygame.draw.circle(surf, color, (cx, bar_y + 7), 7)
            pygame.draw.circle(surf, (90, 90, 95), (cx, bar_y + 7), 7, 2)

        label_text = {
            "entering": "Pulling onto the highway...",
            "cruising": "Driving to the city market",
            "braking": "Slowing for a checkpoint...",
            "stopped": "Stopped at checkpoint",
            "resuming": "Light green — moving on!",
            "arriving": "Almost at the city...",
        }.get(phase, "")
        if label_text:
            txt = self.font.render(label_text, True, (40, 40, 45))
            bg = pygame.Surface((txt.get_width() + 20, txt.get_height() + 10))
            bg.fill((255, 255, 255))
            bg.set_alpha(210)
            surf.blit(bg, (self.screen_w // 2 - bg.get_width() // 2, 44))
            surf.blit(txt, (self.screen_w // 2 - txt.get_width() // 2, 49))

        if camera_mode_label:
            ctxt = self.font_small.render(camera_mode_label, True, (255, 255, 255))
            cbg = pygame.Surface((ctxt.get_width() + 16, ctxt.get_height() + 8), pygame.SRCALPHA)
            cbg.fill((20, 20, 25, 170))
            surf.blit(cbg, (self.screen_w - cbg.get_width() - 16, 16))
            surf.blit(ctxt, (self.screen_w - ctxt.get_width() - 8, 20))


# ==========================================
# HIGHWAY SCENE (orchestrator)
# ==========================================
class HighwayScene:
    def __init__(self, screen_w, screen_h, truck_surface=None):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.horizon_y = int(screen_h * 0.42)

        self.camera = Camera()
        self.camera.distance = -260.0
        self.background = CityBackground(screen_w, screen_h, self.horizon_y)
        self.road = PerspectiveRoad(screen_w, screen_h, self.horizon_y)
        self.truck = TruckController(screen_h, truck_surface)
        self.sound = SoundManager()
        self.quiz = MathQuiz(self.sound)
        self.ui = UI(screen_w)
        self.fade = FadeTransition(0.7)

        # --- Camera / perspective system -------------------------------
        # Handles ONLY presentation (which of the 3 views is active and
        # the smoothed parameters that feed the renderer below). It knows
        # nothing about quiz state, phases, or scoring, so it can never
        # interfere with gameplay logic.
        self.camera_manager = CameraManager(
            screen_w, screen_h, self.horizon_y, self.road.bottom_y, self.road.vp_x
        )
        self._camera_mode_labels = {
            CameraManager.FIRST_PERSON: "1st Person [1]",
            CameraManager.SECOND_PERSON: "2nd Person [2]",
            CameraManager.THIRD_PERSON: "3rd Person [3]",
        }

        self.checkpoints = [TrafficLight(i, d) for i, d in enumerate(CHECKPOINT_DISTANCES)]
        self.total_distance = FINAL_DISTANCE
        self.phase = "entering"
        self.finished = False
        self._arrive_timer = 0.0

    def start(self):
        self.fade.start()

    def _next_unsolved_checkpoint(self):
        for cp in self.checkpoints:
            if not cp.solved:
                return cp
        return None

    def _on_quiz_success(self):
        cp = self._next_unsolved_checkpoint()
        if cp:
            cp.set_green()
            self.sound.play("light")
        self.phase = "resuming"

    def handle_event(self, event):
        # Camera switching works in every phase (including mid-quiz and
        # while stopped) so the player is never locked out of it, and it
        # never touches quiz/gameplay state - purely a view change.
        prev_mode = self.camera_manager.mode
        self.camera_manager.handle_event(event)
        if self.camera_manager.mode != prev_mode:
            self.sound.play("camera")

        if self.phase == "stopped" and self.quiz.active:
            self.quiz.handle_event(event)
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.quiz.handle_click(event.pos)

    def update(self, dt):
        self.fade.update(dt)
        self.background.update(dt)

        if self.fade.state == "out" and self.fade.is_done_fading_out():
            self.finished = True
            return "arrived"

        if self.phase == "arriving" and self.fade.state != "out":
            self._arrive_timer -= dt
            if self._arrive_timer <= 0:
                self.fade.begin_out()
            self.truck.update(dt)
            self.camera_manager.update(dt, self.truck)
            return "running"

        if self.quiz.active:
            self.quiz.update(dt)
            self.truck.target_speed = 0.0
            self.truck.update(dt)
            self.camera_manager.update(dt, self.truck)
            return "running"

        next_cp = self._next_unsolved_checkpoint()

        if next_cp:
            dist_to_cp = next_cp.world_x - self.camera.distance
            if 0 < dist_to_cp < SLOWDOWN_DISTANCE:
                self.phase = "braking"
                factor = max(0.0, min(1.0, dist_to_cp / SLOWDOWN_DISTANCE))
                self.truck.target_speed = CRUISE_SPEED * factor
                if dist_to_cp <= STOP_MARGIN + self.truck.speed * dt:
                    self.camera.distance = next_cp.world_x - STOP_MARGIN
                    self.truck.speed = 0.0
                    self.truck.target_speed = 0.0
                    self.phase = "stopped"
                    level = next_cp.index + 1
                    self.quiz.generate(level, next_cp.index, self._on_quiz_success)
                    self.truck.update(dt)
                    self.camera_manager.update(dt, self.truck)
                    return "running"
            else:
                self.phase = "cruising" if self.phase not in ("entering",) else self.phase
                self.truck.target_speed = CRUISE_SPEED
        else:
            self.truck.target_speed = CRUISE_SPEED
            if self.camera.distance >= self.total_distance and self.phase != "arriving":
                self.phase = "arriving"
                self._arrive_timer = 1.6
                self.sound.play("arrive")

        if self.phase == "entering" and self.camera.distance >= 0:
            self.phase = "cruising"

        self.truck.update(dt)
        self.camera.distance += self.truck.speed * dt
        self.camera_manager.update(dt, self.truck)
        return "running"

    def draw(self, surf):
        progress = max(0.0, min(1.0, self.camera.distance / self.total_distance))

        # Pull the smoothed perspective parameters once per frame instead
        # of recomputing them per-object - keeps the draw pass cheap and
        # guarantees every layer (sky, road, trees, lights, truck) agrees
        # on exactly the same camera for this frame.
        cm = self.camera_manager
        horizon_y = cm.horizon_y
        bottom_y = cm.bottom_y
        vp_x = cm.vp_x()
        width_mult = cm.width_mult
        scale_mult = cm.scale_mult

        self.background.draw(surf, self.camera, progress, horizon_y=horizon_y)
        self.road.draw_roadside(surf, self.camera, horizon_y=horizon_y, bottom_y=bottom_y,
                                 vp_x=vp_x, width_mult=width_mult, scale_mult=scale_mult)
        self.road.draw_road(surf, self.camera, horizon_y=horizon_y, bottom_y=bottom_y,
                             vp_x=vp_x, width_mult=width_mult)

        for cp in self.checkpoints:
            cp.draw(surf, self.camera, self.road, horizon_y=horizon_y, bottom_y=bottom_y,
                    vp_x=vp_x, width_mult=width_mult, scale_mult=scale_mult)

        # Truck rendering depends entirely on the active perspective:
        #   - third person: rear view, sitting on the road like before
        #   - second person: front view "approaching" the chase drone,
        #     with a slow breathing scale so it isn't a static cut-out
        #   - first person: the truck body is invisible (we're inside
        #     it) - only the cockpit overlay is drawn, after everything
        #     else, so it sits on top of the scene like a real dashboard
        if cm.truck_draw_mode == "rear":
            self.truck.draw_rear(surf, vp_x, bottom_y)
        elif cm.truck_draw_mode == "front":
            wave = cm.lead_distance_wave()
            breathe_scale = 1.0 + (wave / 200.0)
            self.truck.draw_front(surf, vp_x, bottom_y, extra_scale=breathe_scale)
        # "hidden" -> nothing drawn here; draw_dashboard() below instead.

        self.ui.draw(surf, max(0, self.camera.distance), self.total_distance, self.checkpoints,
                     self.phase, camera_mode_label=self._camera_mode_labels.get(cm.mode))

        # Dashboard overlay (first-person only) is drawn on top of the
        # world but BEFORE the quiz panel/"arrived" banner, so those UI
        # elements always stay fully visible and clickable regardless of
        # camera mode - only the world geometry gets occluded by the cab.
        if cm.truck_draw_mode == "hidden":
            self.truck.draw_dashboard(surf, self.screen_w, self.screen_h)

        if self.phase == "arriving":
            font_big = pygame.font.Font(None, 54)
            txt = font_big.render("Welcome to the City Market!", True, (255, 255, 255))
            bg = pygame.Surface((txt.get_width() + 40, txt.get_height() + 24), pygame.SRCALPHA)
            bg.fill((50, 130, 90, 210))
            surf.blit(bg, (self.screen_w // 2 - bg.get_width() // 2, self.screen_h // 2 - 60))
            surf.blit(txt, (self.screen_w // 2 - txt.get_width() // 2, self.screen_h // 2 - 46))

        if self.quiz.active:
            self.quiz.draw(surf, self.screen_w, self.screen_h)

        self.fade.draw(surf)