"""
highway_scene.py
"Highway to the Urban Market" — a perspective road driving sequence.

VISUAL REDESIGN NOTE
---------------------
This is a presentation-layer overhaul of the original prototype. Every
class name, method name, method signature, and piece of gameplay/physics
logic (truck acceleration, braking thresholds, checkpoint distances, quiz
generation/scoring, phase transitions, camera-manager blending math) is
UNCHANGED from the original build. Only *how things are drawn* changed:
richer color palettes, gradients, glow, layered scenery, decorative
ambient traffic, guard rails, signage, and a restyled HUD/cockpit.

A new purely-cosmetic `AmbientTraffic` layer was added. It reads the
camera's scroll distance but writes nothing back and never touches the
player, phases, or quiz — it cannot affect gameplay, only add life to
the world.

CAMERA SYSTEM
-------------
Unchanged from the original: CameraManager lets the player switch
between three perspectives at any time with the 1 / 2 / 3 keys:

    1 - First-person  (inside the cab, looking through the windshield)
    2 - Second-person  (a chase drone hovering ahead of the truck, looking
                         back at its front end as it "approaches" you)
    3 - Third-person   (classic behind-and-above chase camera)

The road/scenery renderer is a pseudo-3D "scaling sprite" projector; the
camera system works by smoothly interpolating the parameters that feed
`project()` every frame (horizon_y, bottom_y, vp_x_offset, width_mult,
scale_mult). All drawing classes accept these as optional overrides.
"""

import pygame
import random
import math
import array

# ==========================================
# CONSTANTS — modern, vibrant palette
# ==========================================
# Sky: warm, high-contrast gradient with a sunlit horizon band instead of
# a flat cool-blue wash.
SKY_TOP = (64, 138, 214)
SKY_MID = (150, 196, 232)
SKY_HORIZON = (255, 226, 178)
SKY_BOTTOM = (255, 244, 220)
SUN_COLOR = (255, 244, 200)
SUN_GLOW = (255, 214, 140)

MOUNTAIN_FAR = (150, 160, 196)
HILL_FAR = (86, 168, 108)
HILL_NEAR = (54, 140, 84)

ROAD_COLOR = (46, 48, 56)
ROAD_COLOR_LIGHT = (60, 63, 72)
ROAD_SHOULDER = (94, 92, 88)
ROAD_EDGE_COLOR = (250, 250, 245)
RUMBLE_COLOR = (232, 90, 60)
CENTER_LINE_COLOR = (255, 214, 60)
LANE_LINE_COLOR = (240, 240, 235)

SKYLINE_FAR = (150, 168, 198)
SKYLINE_NEAR = (108, 128, 166)
SKYLINE_WINDOW = (255, 226, 150)

GUARDRAIL_COLOR = (196, 200, 206)
GUARDRAIL_SHADOW = (120, 124, 132)
POLE_COLOR = (70, 74, 82)

UI_PANEL = (18, 22, 30)
UI_ACCENT = (86, 214, 156)
UI_ACCENT_2 = (255, 176, 68)
UI_TEXT = (240, 244, 248)

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
    Returns (depth 0..1, scale, screen_y)."""
    t = max(0.0, min(1.0, 1.0 - rd / RENDER_DISTANCE))
    depth = t * t
    y = horizon_y + (bottom_y - horizon_y) * depth
    scale = (0.045 + 0.955 * depth) * scale_mult
    return depth, scale, y


def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp_color(c1, c2, t):
    return (int(_lerp(c1[0], c2[0], t)), int(_lerp(c1[1], c2[1], t)), int(_lerp(c1[2], c2[2], t)))


def _clamp_color(c):
    return tuple(max(0, min(255, int(v))) for v in c)


def _shade(color, amount):
    """amount > 0 lightens, < 0 darkens."""
    if amount >= 0:
        return _clamp_color(tuple(c + (255 - c) * amount for c in color))
    return _clamp_color(tuple(c * (1 + amount) for c in color))


def _soft_glow(surf, center, radius, color, max_alpha=120, steps=5):
    """Cheap bloom: a handful of alpha-fading circles instead of a real
    blur — fast, and reads as a soft light bleed at game resolution."""
    cx, cy = int(center[0]), int(center[1])
    for i in range(steps, 0, -1):
        t = i / steps
        r = max(1, int(radius * t))
        a = int(max_alpha * (1 - t) * 0.9) + int(max_alpha * 0.15)
        glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*color, a), (r, r), r)
        surf.blit(glow, (cx - r, cy - r), special_flags=pygame.BLEND_RGBA_ADD)


# ==========================================
# CAMERA MANAGER  (logic unchanged from original)
# ==========================================
class CameraManager:
    FIRST_PERSON = "first_person"
    SECOND_PERSON = "second_person"
    THIRD_PERSON = "third_person"

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

        self.horizon_y = base_horizon_y
        self.bottom_y = base_bottom_y
        self.vp_x_offset = 0.0
        self.width_mult = 1.0
        self.scale_mult = 1.0
        self.truck_visible = True
        self.truck_draw_mode = "rear"

        self._lead_wave_t = 0.0
        self._sway_lag = 0.0

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_1, pygame.K_KP1):
            self.mode = self.FIRST_PERSON
        elif event.key in (pygame.K_2, pygame.K_KP2):
            self.mode = self.SECOND_PERSON
        elif event.key in (pygame.K_3, pygame.K_KP3):
            self.mode = self.THIRD_PERSON

    def _targets_for_mode(self):
        if self.mode == self.FIRST_PERSON:
            horizon_y = self.base_horizon_y - 4
            bottom_y = self.base_bottom_y - 20
            vp_x_offset = 0.0
            width_mult = 0.88
            scale_mult = 1.14
            truck_visible = False
            truck_draw_mode = "hidden"
        elif self.mode == self.SECOND_PERSON:
            horizon_y = self.base_horizon_y - 6
            bottom_y = self.base_bottom_y
            vp_x_offset = 0.0
            width_mult = 1.0
            scale_mult = 1.0
            truck_visible = True
            truck_draw_mode = "front"
        else:
            horizon_y = self.base_horizon_y
            bottom_y = self.base_bottom_y
            vp_x_offset = 0.0
            width_mult = 1.0
            scale_mult = 1.0
            truck_visible = True
            truck_draw_mode = "rear"
        return horizon_y, bottom_y, vp_x_offset, width_mult, scale_mult, truck_visible, truck_draw_mode

    def update(self, dt, truck):
        (t_horizon, t_bottom, t_vpx, t_width, t_scale,
         t_visible, t_draw_mode) = self._targets_for_mode()

        pos_a = 1.0 - math.exp(-self.SMOOTH_POSITION * dt)
        fov_a = 1.0 - math.exp(-self.SMOOTH_FOV * dt)

        self.horizon_y = _lerp(self.horizon_y, t_horizon, pos_a)
        self.bottom_y = _lerp(self.bottom_y, t_bottom, pos_a)
        self.width_mult = _lerp(self.width_mult, t_width, fov_a)
        self.scale_mult = _lerp(self.scale_mult, t_scale, fov_a)

        self.truck_visible = t_visible
        self.truck_draw_mode = t_draw_mode

        if self.mode == self.THIRD_PERSON:
            sway_a = 1.0 - math.exp(-self.SMOOTH_SWAY * dt)
            self._sway_lag = _lerp(self._sway_lag, truck.sway, sway_a)
            self.vp_x_offset = self._sway_lag * 0.5
        else:
            self._sway_lag = truck.sway
            self.vp_x_offset = 0.0

        self._lead_wave_t += dt

    def lead_distance_wave(self):
        return math.sin(self._lead_wave_t * 0.6) * 14.0

    def vp_x(self):
        return self.base_vp_x + self.vp_x_offset


# ==========================================
# FADE TRANSITION  (unchanged)
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
# SOUND MANAGER  (unchanged)
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
# CAMERA (world scroll position)
# ==========================================
class Camera:
    def __init__(self):
        self.distance = 0.0


# ==========================================
# CLOUD — softer, layered, gently lit from below by the sun
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
        top = (255, 255, 255)
        under = (238, 228, 232)
        lumps = [(0, 0, 60, 22), (18, -9, 44, 22), (36, 0, 50, 18), (8, 4, 34, 16)]
        for lx, ly, lw, lh in lumps:
            rect = (sx + lx * s, self.y + ly * s, lw * s, lh * s)
            pygame.draw.ellipse(surf, under, (rect[0], rect[1] + 3, rect[2], rect[3]))
        for lx, ly, lw, lh in lumps:
            rect = (sx + lx * s, self.y + ly * s, lw * s, lh * s)
            pygame.draw.ellipse(surf, top, rect)


# ==========================================
# CITY BACKGROUND (sky, sun, mountains, hills, skyline, clouds)
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
            for _ in range(6)
        ]

        random.seed(55)
        self.buildings_far = self._make_skyline(screen_w * 1.6, 90, 190, 26, 46, SKYLINE_FAR)
        self.buildings_near = self._make_skyline(screen_w * 1.6, 60, 260, 22, 40, SKYLINE_NEAR)
        random.seed()

        random.seed(31)
        self.mountain_pts = self._wavy_points(screen_w * 1.6, horizon_y - 34, 30, 240)
        random.seed()

        random.seed(88)
        self.hill_far_pts = self._wavy_points(screen_w * 1.6, horizon_y - 6, 16, 140)
        self.hill_near_pts = self._wavy_points(screen_w * 1.6, horizon_y + 18, 20, 170)
        random.seed()

        # A couple of decorative wind turbines on the far hillside.
        random.seed(14)
        self.turbines = [(random.uniform(0, screen_w * 1.6), random.uniform(0.7, 1.1))
                          for _ in range(3)]
        random.seed()

        self.sun_x_frac = 0.74  # fixed sun position (parallax-free, distant)

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

    def _draw_skyline(self, surf, buildings, span, base_y, flicker_phase=0.0):
        offset = self.drift % span
        for x, w, h, color in buildings:
            for sx in (x - offset, x - offset + span):
                if -w <= sx <= self.w + w:
                    rect = pygame.Rect(sx, base_y - h, w, h)
                    top = _shade(color, 0.12)
                    for i in range(int(rect.height)):
                        t = i / max(1, rect.height)
                        col = _lerp_color(top, color, t)
                        pygame.draw.line(surf, col, (rect.x, rect.y + i), (rect.right, rect.y + i))
                    for wy in range(int(base_y - h) + 8, int(base_y) - 6, 13):
                        for wx in range(int(sx) + 6, int(sx + w) - 6, 11):
                            hh = _hash01(int(wx * 3 + wy * 7))
                            if hh > 0.52:
                                lit = hh > 0.78
                                col = SKYLINE_WINDOW if lit else (70, 84, 104)
                                pygame.draw.rect(surf, col, (wx, wy, 4, 6))

    def _draw_hill(self, surf, pts, span, color, y_extra=0, shade_top=None):
        offset = self.drift % span
        for base_off in (-offset, -offset + span):
            shifted = [(x + base_off, y + y_extra) for x, y in pts]
            poly = [(shifted[0][0], self.h)] + shifted + [(shifted[-1][0], self.h)]
            pygame.draw.polygon(surf, color, poly)
            if shade_top:
                highlight = [(x, y - 3) for x, y in shifted]
                if len(highlight) > 1:
                    pygame.draw.lines(surf, shade_top, False, highlight, 3)

    def _draw_turbine(self, surf, sx, sy, scale, spin):
        tower_h = 46 * scale
        pygame.draw.line(surf, (232, 236, 240), (sx, sy), (sx, sy - tower_h), max(1, int(3 * scale)))
        hub = (sx, sy - tower_h)
        blade_len = 20 * scale
        for i in range(3):
            ang = spin + i * (2 * math.pi / 3)
            ex = hub[0] + math.cos(ang) * blade_len
            ey = hub[1] + math.sin(ang) * blade_len
            pygame.draw.line(surf, (245, 248, 250), hub, (ex, ey), max(1, int(2.4 * scale)))
        pygame.draw.circle(surf, (210, 214, 218), (int(hub[0]), int(hub[1])), max(1, int(2 * scale)))

    def draw(self, surf, camera, progress, horizon_y=None):
        hy = self.horizon_y if horizon_y is None else int(horizon_y)
        hy = max(1, min(self.h - 1, hy))

        # --- layered gradient sky: cool zenith -> warm horizon glow ---
        band1 = int(hy * 0.55)
        for i in range(band1):
            t = i / max(1, band1)
            col = _lerp_color(SKY_TOP, SKY_MID, t)
            pygame.draw.line(surf, col, (0, i), (self.w, i))
        for i in range(band1, hy):
            t = (i - band1) / max(1, hy - band1)
            col = _lerp_color(SKY_MID, SKY_HORIZON, t)
            pygame.draw.line(surf, col, (0, i), (self.w, i))
        if hy < self.h:
            for i in range(hy, min(self.h, hy + 40)):
                t = (i - hy) / 40.0
                col = _lerp_color(SKY_HORIZON, SKY_BOTTOM, min(1.0, t))
                pygame.draw.line(surf, col, (0, i), (self.w, i))
            if hy + 40 < self.h:
                pygame.draw.rect(surf, SKY_BOTTOM, (0, hy + 40, self.w, self.h - hy - 40))

        # --- sun with soft bloom, sitting low near the horizon ---
        sun_x = self.w * self.sun_x_frac
        sun_y = hy * 0.52
        _soft_glow(surf, (sun_x, sun_y), 70, SUN_GLOW, max_alpha=70, steps=6)
        pygame.draw.circle(surf, SUN_COLOR, (int(sun_x), int(sun_y)), 22)
        pygame.draw.circle(surf, (255, 255, 255), (int(sun_x), int(sun_y)), 10)

        for c in self.clouds:
            c.draw(surf, self.w)

        y_shift = hy - self.horizon_y
        scale_boost = 1.0 + 0.35 * progress
        base_far = hy + 2
        base_near = hy + 6

        # distant hazy mountain silhouette behind everything else
        self._draw_hill(surf, self.mountain_pts, self.w * 1.6, MOUNTAIN_FAR, y_extra=y_shift)

        self._draw_skyline(surf, self.buildings_far, self.w * 1.6, base_far)
        self._draw_skyline(surf, self.buildings_near, self.w * 1.6, base_near + 6 * scale_boost)

        self._draw_hill(surf, self.hill_far_pts, self.w * 1.6, HILL_FAR, y_extra=y_shift,
                         shade_top=_shade(HILL_FAR, 0.18))
        self._draw_hill(surf, self.hill_near_pts, self.w * 1.6, HILL_NEAR, y_extra=y_shift,
                         shade_top=_shade(HILL_NEAR, 0.16))

        # wind turbines riding the far hill line
        offset = self.drift % (self.w * 1.6)
        spin = self.drift * 0.9
        for wx, wscale in self.turbines:
            for sxb in (wx - offset, wx - offset + self.w * 1.6):
                if -20 <= sxb <= self.w + 20:
                    hy_local = self.hill_far_pts[min(len(self.hill_far_pts) - 1,
                                                       int((wx % (self.w * 1.6)) / 18))][1] + y_shift
                    self._draw_turbine(surf, sxb, hy_local, wscale, spin)


# ==========================================
# AMBIENT TRAFFIC — purely decorative, no gameplay effect
# ==========================================
class AmbientTraffic:
    """A handful of background vehicle silhouettes that drift along
    virtual side lanes to make the world feel alive. They read
    `camera.distance` for parallax scroll only; nothing here is queried
    by gameplay, checkpoints, or the quiz, and nothing here can block or
    slow the player."""

    KINDS = ["sedan", "suv", "pickup", "van", "bus", "sports"]
    COLORS = [(196, 60, 60), (60, 96, 196), (230, 230, 230), (40, 40, 46),
              (224, 180, 40), (70, 150, 130), (150, 90, 190)]

    def __init__(self, count=10):
        self.entries = []
        random.seed(202)
        for i in range(count):
            self.entries.append({
                "seed": i,
                "kind": random.choice(self.KINDS),
                "color": random.choice(self.COLORS),
                "lane_sign": random.choice([-1, 1]),
                "speed_mult": random.uniform(0.6, 1.3),
                "spacing_phase": random.uniform(0, 1),
            })
        random.seed()
        self.spacing = 260.0

    def _draw_vehicle(self, surf, kind, color, sx, sy, scale, facing):
        """facing: 1 = nose toward camera (oncoming), -1 = tail toward camera."""
        s = max(0.05, scale)
        w = {"sedan": 30, "suv": 34, "pickup": 34, "van": 34, "bus": 46, "sports": 28}[kind] * s
        h = {"sedan": 14, "suv": 18, "pickup": 17, "van": 20, "bus": 24, "sports": 11}[kind] * s
        body = pygame.Rect(sx - w / 2, sy - h, w, h)
        dark = _shade(color, -0.35)
        light = _shade(color, 0.22)

        pygame.draw.ellipse(surf, (20, 20, 20), (sx - w * 0.48, sy + h * 0.06, w * 0.96, h * 0.22))

        body_rect = pygame.Rect(body.x, body.y, body.w, body.h * 0.62)
        pygame.draw.rect(surf, color, body_rect, border_radius=max(1, int(h * 0.18)))
        pygame.draw.rect(surf, light, (body_rect.x, body_rect.y, body_rect.w, max(1, body_rect.h * 0.35)),
                          border_radius=max(1, int(h * 0.18)))
        pygame.draw.rect(surf, dark, body_rect, max(1, int(s)), border_radius=max(1, int(h * 0.18)))

        if kind != "sports":
            cabin = pygame.Rect(body.x + w * 0.2, body.y - h * 0.42, w * 0.6, h * 0.5)
            pygame.draw.rect(surf, dark, cabin, border_radius=max(1, int(h * 0.14)))
            glass = cabin.inflate(-max(1, int(w * 0.06)), -max(1, int(h * 0.08)))
            pygame.draw.rect(surf, (170, 200, 214), glass, border_radius=max(1, int(h * 0.1)))
        else:
            cabin = pygame.Rect(body.x + w * 0.32, body.y - h * 0.22, w * 0.42, h * 0.3)
            pygame.draw.rect(surf, (170, 200, 214), cabin, border_radius=max(1, int(h * 0.1)))

        lamp_col = (255, 235, 190) if facing == 1 else (230, 60, 55)
        for lx in (body.x + w * 0.08, body.x + w * 0.92 - 4 * s):
            pygame.draw.circle(surf, lamp_col, (int(lx), int(body.y + body_rect.h * 0.5)), max(1, int(2.6 * s)))

        for wx in (body.x + w * 0.2, body.x + w * 0.8):
            pygame.draw.circle(surf, (18, 18, 18), (int(wx), int(sy + h * 0.05)), max(1, int(3.6 * s)))

    def draw(self, surf, camera, road, horizon_y, bottom_y, vp_x, width_mult, scale_mult):
        start_i = int(camera.distance // self.spacing) - 2
        end_i = int((camera.distance + RENDER_DISTANCE) // self.spacing) + 2
        bottom_half = road.bottom_half * width_mult

        drawn = []
        for e in self.entries:
            for i in range(start_i, end_i):
                world_x = (i + e["spacing_phase"]) * self.spacing * e["speed_mult"] + e["seed"] * 733
                rd = world_x - camera.distance * (0.4 + 0.6 * e["speed_mult"])
                rd = rd % RENDER_DISTANCE
                if rd < 15 or rd > RENDER_DISTANCE - 5:
                    continue
                depth, scale, y = project(rd, horizon_y, bottom_y, scale_mult)
                half_w = road.half_width(depth, bottom_half)
                lane_frac = 0.58 if e["lane_sign"] < 0 else -0.30
                sx = vp_x + e["lane_sign"] * half_w * 0.001 + (vp_x - vp_x) + half_w * lane_frac
                drawn.append((depth, e, sx, y, scale))

        drawn.sort(key=lambda d: d[0])
        for depth, e, sx, y, scale in drawn[:24]:
            facing = 1 if e["lane_sign"] < 0 else -1
            self._draw_vehicle(surf, e["kind"], e["color"], sx, y, scale * 1.05, facing)


# ==========================================
# PERSPECTIVE ROAD (surface, shoulders, guard rails, roadside scenery, signage)
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
        self.pole_spacing = 260.0
        self.sign_spacing = 900.0
        self.marker_spacing = 400.0

    def half_width(self, depth, bottom_half=None):
        bh = self.bottom_half if bottom_half is None else bottom_half
        return self.top_half + (bh - self.top_half) * depth

    # ---- road surface --------------------------------------------------
    def draw_road(self, surf, camera, horizon_y=None, bottom_y=None, vp_x=None, width_mult=1.0):
        hy = self.horizon_y if horizon_y is None else horizon_y
        by = self.bottom_y if bottom_y is None else bottom_y
        vx = self.vp_x if vp_x is None else vp_x
        bottom_half = self.bottom_half * width_mult
        shoulder_w = bottom_half * 0.16

        top_pts = [(vx - self.top_half, hy), (vx + self.top_half, hy)]
        bottom_pts = [(vx + bottom_half, by), (vx - bottom_half, by)]

        # shoulders (drawn slightly wider than the asphalt, underneath it)
        sh_top = [(vx - self.top_half * 1.3, hy), (vx + self.top_half * 1.3, hy)]
        sh_bottom = [(vx + bottom_half + shoulder_w, by), (vx - bottom_half - shoulder_w, by)]
        pygame.draw.polygon(surf, ROAD_SHOULDER, sh_top + sh_bottom)

        # asphalt with a soft lateral gradient (lighter center, darker edges)
        poly = top_pts + bottom_pts
        pygame.draw.polygon(surf, ROAD_COLOR, poly)
        mid_top = [(vx - self.top_half * 0.3, hy), (vx + self.top_half * 0.3, hy)]
        mid_bottom = [(vx + bottom_half * 0.35, by), (vx - bottom_half * 0.35, by)]
        pygame.draw.polygon(surf, ROAD_COLOR_LIGHT, mid_top + mid_bottom)

        # subtle asphalt speckle texture (cheap, hash-based, no per-frame cost spike)
        offset = camera.distance % 40.0
        for i in range(18):
            rd = i * 55.0 - offset
            if rd < 0 or rd > RENDER_DISTANCE * 0.6:
                continue
            depth, _, y = project(rd, hy, by)
            hw = self.half_width(depth, bottom_half)
            for k in range(3):
                hh = _hash01(int(rd) * 13 + k * 97)
                sx = vx + (hh - 0.5) * hw * 1.7
                if abs(sx - vx) < hw:
                    dot_r = max(1, int(2.4 * (1 - depth) + 0.6))
                    pygame.draw.circle(surf, (36, 38, 44), (int(sx), int(y)), dot_r)

        # outer edge lines (bright, reflective white)
        pygame.draw.line(surf, ROAD_EDGE_COLOR, top_pts[0], bottom_pts[1], 3)
        pygame.draw.line(surf, ROAD_EDGE_COLOR, top_pts[1], bottom_pts[0], 3)

        # rumble strip ticks just inside the edge lines
        n_ticks = 20
        rumble_offset = camera.distance % 30.0
        for i in range(n_ticks):
            rd = i * 30.0 - rumble_offset
            if rd < 0 or rd > RENDER_DISTANCE * 0.7:
                continue
            depth, _, y = project(rd, hy, by)
            hw = self.half_width(depth, bottom_half)
            tick_w = max(1, int(4 * (1 - depth) + 1))
            for side in (-1, 1):
                sx = vx + side * hw * 0.94
                pygame.draw.line(surf, RUMBLE_COLOR, (sx - tick_w, y), (sx + tick_w, y), max(1, int(2 * (1 - depth) + 1)))

        # dashed center line with a faint glow so it reads as reflective paint
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
            dash_poly = [
                (vx - w_near // 2, y_near), (vx + w_near // 2, y_near),
                (vx + 1, y_far), (vx - 1, y_far)
            ]
            if rd_near < 220:
                glow = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
                pygame.draw.polygon(glow, (*CENTER_LINE_COLOR, 70),
                                     [(p[0], p[1]) for p in dash_poly])
                surf.blit(glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            pygame.draw.polygon(surf, CENTER_LINE_COLOR, dash_poly)

        # secondary lane divider lines (thin white) between center and edges,
        # signalling this is a multi-lane highway rather than a single strip
        for side in (-1, 1):
            lane_off_top = vx + side * self.top_half * 0.6
            lane_off_bottom = vx + side * bottom_half * 0.5
            offset2 = camera.distance % 50.0
            for i in range(22):
                rd_near = i * 50.0 - offset2
                rd_far = rd_near + 18
                if rd_near < 0 or rd_near > RENDER_DISTANCE:
                    continue
                d_near, _, y_near = project(max(0, rd_near), hy, by)
                d_far, _, y_far = project(max(0, rd_far), hy, by)
                if y_far >= y_near:
                    continue
                x_near = _lerp(vx, lane_off_bottom, d_near)
                x_far = _lerp(vx, lane_off_bottom, d_far)
                w_line = max(1, int(3 * (1 - d_near)))
                pygame.draw.line(surf, LANE_LINE_COLOR, (x_near, y_near), (x_far, y_far), w_line)

    # ---- guard rails ------------------------------------------------
    def draw_guardrails(self, surf, camera, horizon_y=None, bottom_y=None, vp_x=None, width_mult=1.0):
        hy = self.horizon_y if horizon_y is None else horizon_y
        by = self.bottom_y if bottom_y is None else bottom_y
        vx = self.vp_x if vp_x is None else vp_x
        bottom_half = self.bottom_half * width_mult

        post_spacing = 46.0
        offset = camera.distance % post_spacing
        n_posts = 32
        for side in (-1, 1):
            beam_pts = []
            for i in range(n_posts):
                rd = i * post_spacing - offset
                if rd < 0 or rd > RENDER_DISTANCE * 0.55:
                    if beam_pts:
                        break
                    continue
                depth, scale, y = project(rd, hy, by)
                hw = self.half_width(depth, bottom_half)
                sx = vx + side * (hw * 1.09)
                post_h = max(3, int(20 * (0.15 + depth)))
                pygame.draw.line(surf, POLE_COLOR, (sx, y), (sx, y - post_h), max(1, int(3 * (0.2 + depth))))
                beam_pts.append((sx, y - post_h * 0.62))
            if len(beam_pts) > 1:
                pygame.draw.lines(surf, GUARDRAIL_SHADOW, False, beam_pts, 5)
                pygame.draw.lines(surf, GUARDRAIL_COLOR, False, beam_pts, 3)

    # ---- roadside scenery: trees, bushes, wildflowers, rocks, poles ----
    def _draw_tree(self, surf, sx, sy, scale, color_a, color_b):
        trunk_h = max(2, int(14 * scale))
        trunk_w = max(1, int(4 * scale))
        pygame.draw.rect(surf, (108, 74, 46), (sx - trunk_w // 2, sy - trunk_h, trunk_w, trunk_h))
        r = max(2, int(17 * scale))
        pygame.draw.circle(surf, _shade(color_a, -0.12), (int(sx), int(sy - trunk_h - r * 0.5)), r)
        pygame.draw.circle(surf, color_a, (int(sx + r * 0.15), int(sy - trunk_h - r * 0.6)), int(r * 0.9))
        pygame.draw.circle(surf, color_b, (int(sx - r * 0.32), int(sy - trunk_h - r * 0.9)), int(r * 0.62))

    def _draw_pine(self, surf, sx, sy, scale, color_a, color_b):
        trunk_h = max(2, int(6 * scale))
        pygame.draw.rect(surf, (96, 64, 42), (sx - max(1, int(2 * scale)), sy - trunk_h, max(2, int(4 * scale)), trunk_h))
        h = max(6, int(36 * scale))
        w = max(4, int(21 * scale))
        top_y = sy - trunk_h - h
        for i, frac in enumerate((1.0, 0.68, 0.36)):
            tier_w = w * frac
            tier_y = top_y + h * (1 - frac) * 0.9
            col = color_a if i % 2 == 0 else color_b
            pygame.draw.polygon(surf, col, [
                (sx, tier_y), (sx - tier_w / 2, tier_y + h * 0.42), (sx + tier_w / 2, tier_y + h * 0.42)
            ])

    def _draw_bush(self, surf, sx, sy, scale, color):
        r = max(2, int(9 * scale))
        for dx, dy, rr in ((-r * 0.5, 0, r * 0.75), (r * 0.5, 0, r * 0.75), (0, -r * 0.35, r)):
            pygame.draw.circle(surf, color, (int(sx + dx), int(sy + dy)), max(1, int(rr)))

    def _draw_wildflowers(self, surf, sx, sy, scale, hue):
        colors = {0: (240, 210, 60), 1: (230, 120, 150), 2: (200, 150, 230)}
        col = colors[hue % 3]
        for k in range(3):
            fx = sx + (k - 1) * 3 * scale
            fy = sy - abs(k - 1) * 1.5 * scale
            pygame.draw.circle(surf, (86, 140, 70), (int(fx), int(fy + 2 * scale)), max(1, int(1 * scale)))
            pygame.draw.circle(surf, col, (int(fx), int(fy)), max(1, int(1.6 * scale)))

    def _draw_rock(self, surf, sx, sy, scale):
        r = max(2, int(6 * scale))
        pygame.draw.ellipse(surf, (128, 126, 122), (sx - r, sy - r * 0.7, r * 2, r * 1.3))
        pygame.draw.ellipse(surf, (150, 148, 144), (sx - r * 0.5, sy - r * 0.85, r * 1.1, r * 0.7))

    def _draw_pole(self, surf, sx, sy, scale):
        h = max(6, int(48 * scale))
        pygame.draw.line(surf, (80, 78, 76), (sx, sy), (sx, sy - h), max(1, int(2.4 * scale)))
        arm = max(3, int(14 * scale))
        pygame.draw.line(surf, (80, 78, 76), (sx, sy - h), (sx + arm, sy - h + arm * 0.3), max(1, int(2 * scale)))
        for k in range(3):
            wy = sy - h + k * (h * 0.16)
            pygame.draw.line(surf, (60, 60, 62), (sx - arm * 0.7, wy), (sx + arm * 1.1, wy + arm * 0.1), 1)

    def _draw_lamp(self, surf, sx, sy, scale):
        h = max(8, int(56 * scale))
        pygame.draw.line(surf, (60, 62, 68), (sx, sy), (sx, sy - h), max(1, int(3 * scale)))
        head_w = max(4, int(12 * scale))
        pygame.draw.line(surf, (60, 62, 68), (sx, sy - h), (sx + head_w, sy - h - head_w * 0.4), max(1, int(3 * scale)))
        lamp_pos = (sx + head_w, sy - h - head_w * 0.4)
        _soft_glow(surf, lamp_pos, max(6, int(16 * scale)), (255, 224, 150), max_alpha=60, steps=3)
        pygame.draw.circle(surf, (255, 240, 200), (int(lamp_pos[0]), int(lamp_pos[1])), max(2, int(4 * scale)))

    def draw_roadside(self, surf, camera, horizon_y=None, bottom_y=None, vp_x=None,
                       width_mult=1.0, scale_mult=1.0):
        hy = self.horizon_y if horizon_y is None else horizon_y
        by = self.bottom_y if bottom_y is None else bottom_y
        vx = self.vp_x if vp_x is None else vp_x
        bottom_half = self.bottom_half * width_mult

        # ground fill between the road shoulder and the horizon so the
        # scenery doesn't float over bare sky (rich green field strip).
        ground_poly = [
            (0, hy), (self.w, hy), (self.w, by + 40), (0, by + 40)
        ]
        pygame.draw.polygon(surf, HILL_NEAR, ground_poly)

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
                entries.append((depth, sx, sy, tscale, kind_roll, i, seed_off))

        entries.sort(key=lambda e: e[0])
        for depth, sx, sy, tscale, kind_roll, i, seed_off in entries:
            if kind_roll > 0.62:
                self._draw_pine(surf, sx, sy, tscale, (36, 122, 62), (52, 144, 76))
            elif kind_roll > 0.30:
                self._draw_tree(surf, sx, sy, tscale, (64, 156, 74), (82, 172, 88))
            elif kind_roll > 0.18:
                self._draw_bush(surf, sx, sy, tscale, (58, 140, 68))
            elif kind_roll > 0.10:
                self._draw_rock(surf, sx, sy, tscale)
            else:
                self._draw_wildflowers(surf, sx, sy, tscale, i % 3)

        # utility poles + street lamps, sparser than trees, alternating sides
        pole_start = int(camera.distance // self.pole_spacing) - 1
        pole_end = int((camera.distance + RENDER_DISTANCE) // self.pole_spacing) + 1
        for i in range(pole_start, pole_end):
            world_x = i * self.pole_spacing
            rd = world_x - camera.distance
            if rd < 0 or rd > RENDER_DISTANCE:
                continue
            depth, scale, y = project(rd, hy, by, scale_mult)
            half_w = self.half_width(depth, bottom_half)
            side = -1 if i % 2 == 0 else 1
            sx = vx + side * half_w * 1.28
            if i % 4 == 0:
                self._draw_lamp(surf, sx, y, scale)
            else:
                self._draw_pole(surf, sx, y, scale)

    # ---- signage: distance markers + highway exit signs ----------------
    def draw_signage(self, surf, camera, horizon_y=None, bottom_y=None, vp_x=None,
                      width_mult=1.0, scale_mult=1.0, total_distance=1.0):
        hy = self.horizon_y if horizon_y is None else horizon_y
        by = self.bottom_y if bottom_y is None else bottom_y
        vx = self.vp_x if vp_x is None else vp_x
        bottom_half = self.bottom_half * width_mult

        # small green distance-marker posts every marker_spacing units
        m_start = int(camera.distance // self.marker_spacing) - 1
        m_end = int((camera.distance + RENDER_DISTANCE) // self.marker_spacing) + 1
        font_tiny = pygame.font.Font(None, 16)
        for i in range(m_start, m_end):
            world_x = i * self.marker_spacing
            if world_x <= 0:
                continue
            rd = world_x - camera.distance
            if rd < 0 or rd > RENDER_DISTANCE:
                continue
            depth, scale, y = project(rd, hy, by, scale_mult)
            half_w = self.half_width(depth, bottom_half)
            sx = vx - half_w * 1.22
            h = max(6, int(26 * scale))
            w = max(4, int(16 * scale))
            pygame.draw.rect(surf, (40, 120, 70), (sx - w / 2, y - h, w, h), border_radius=2)
            pygame.draw.rect(surf, (255, 255, 255), (sx - w / 2, y - h, w, h), max(1, int(scale)), border_radius=2)
            if scale > 0.35:
                km = int(world_x // 100)
                txt = font_tiny.render(str(km), True, (255, 255, 255))
                surf.blit(txt, (sx - txt.get_width() / 2, y - h + 2))

        # bigger overhead-style exit / direction sign every sign_spacing
        s_start = int(camera.distance // self.sign_spacing) - 1
        s_end = int((camera.distance + RENDER_DISTANCE) // self.sign_spacing) + 1
        font_sign = pygame.font.Font(None, 20)
        for i in range(s_start, s_end):
            world_x = i * self.sign_spacing
            if world_x <= 0:
                continue
            rd = world_x - camera.distance
            if rd < 40 or rd > RENDER_DISTANCE * 0.85:
                continue
            depth, scale, y = project(rd, hy, by, scale_mult)
            half_w = self.half_width(depth, bottom_half)
            sx = vx + half_w * 1.35
            post_h = max(10, int(80 * scale))
            pygame.draw.line(surf, (70, 74, 80), (sx, y), (sx, y - post_h), max(1, int(4 * scale)))
            board_w = max(10, int(70 * scale))
            board_h = max(6, int(30 * scale))
            board = pygame.Rect(sx - board_w * 0.15, y - post_h - board_h, board_w, board_h)
            pygame.draw.rect(surf, (40, 120, 70), board, border_radius=max(1, int(3 * scale)))
            pygame.draw.rect(surf, (255, 255, 255), board, max(1, int(2 * scale)), border_radius=max(1, int(3 * scale)))
            if scale > 0.4:
                label = "CITY MARKET" if world_x >= total_distance - self.sign_spacing else f"EXIT {i}"
                txt = font_sign.render(label, True, (255, 255, 255))
                if txt.get_width() < board.w - 4:
                    surf.blit(txt, (board.centerx - txt.get_width() / 2, board.centery - txt.get_height() / 2))


# ==========================================
# TRAFFIC LIGHT — modern pole, LED glow, pedestrian signal, control box
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

        # modern tapered pole with a metallic gradient
        pole_h = max(10, int(96 * scale))
        pole_w = max(1, int(4.5 * scale))
        pygame.draw.line(surf, (48, 52, 58), (sx, y), (sx, y - pole_h), pole_w)
        pygame.draw.line(surf, (96, 100, 108), (sx - pole_w * 0.2, y), (sx - pole_w * 0.2, y - pole_h), max(1, int(pole_w * 0.35)))

        # small control box at the base
        box_base_w = max(3, int(10 * scale))
        box_base_h = max(4, int(12 * scale))
        pygame.draw.rect(surf, (58, 62, 68), (sx + pole_w, y - box_base_h, box_base_w, box_base_h), border_radius=1)

        box_w = max(7, int(24 * scale))
        box_h = max(9, int(36 * scale))
        box = pygame.Rect(sx - box_w / 2, y - pole_h - box_h + 4, box_w, box_h)
        pygame.draw.rect(surf, (30, 33, 38), box, border_radius=max(1, int(4 * scale)))
        pygame.draw.rect(surf, (58, 62, 68), box, max(1, int(scale)), border_radius=max(1, int(4 * scale)))

        red_on = self.state == "red"
        green_on = self.state == "green"
        r_rad = max(1, int(box_w * 0.28))
        red_pos = (int(sx), int(box.y + box_h * 0.3))
        green_pos = (int(sx), int(box.y + box_h * 0.72))

        if red_on:
            _soft_glow(surf, red_pos, r_rad * 3, (255, 70, 60), max_alpha=90, steps=4)
        if green_on:
            _soft_glow(surf, green_pos, r_rad * 3, (70, 230, 110), max_alpha=90, steps=4)

        pygame.draw.circle(surf, (255, 90, 75) if red_on else (90, 40, 40), red_pos, r_rad)
        pygame.draw.circle(surf, (80, 235, 120) if green_on else (45, 80, 55), green_pos, r_rad)
        # LED highlight dot
        pygame.draw.circle(surf, (255, 255, 255), (red_pos[0] - int(r_rad * 0.3), red_pos[1] - int(r_rad * 0.3)), max(1, int(r_rad * 0.25)))
        pygame.draw.circle(surf, (255, 255, 255), (green_pos[0] - int(r_rad * 0.3), green_pos[1] - int(r_rad * 0.3)), max(1, int(r_rad * 0.25)))

        # small pedestrian signal mounted lower on the pole
        if scale > 0.25:
            ped_y = y - pole_h * 0.42
            ped_w = max(4, int(10 * scale))
            ped_h = max(5, int(12 * scale))
            ped_box = pygame.Rect(sx - ped_w / 2, ped_y - ped_h / 2, ped_w, ped_h)
            pygame.draw.rect(surf, (25, 28, 32), ped_box, border_radius=1)
            ped_color = (255, 140, 60) if red_on else (120, 220, 140)
            pygame.draw.rect(surf, ped_color, ped_box.inflate(-max(1, int(2 * scale)), -max(1, int(2 * scale))), border_radius=1)

        if depth > 0.02:
            line_w = max(2, int(6 * scale))
            pygame.draw.line(surf, (255, 255, 255),
                              (vx - half_w, y), (vx + half_w, y), line_w)


# ==========================================
# MATH QUIZ — same logic, restyled modern panel
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
        overlay.fill((8, 10, 16, 150))
        surf.blit(overlay, (0, 0))

        panel_w, panel_h = 560, 340
        px = screen_w // 2 - panel_w // 2 + int(self.shake_offset)
        py = screen_h // 2 - panel_h // 2

        panel_top = (36, 40, 50)
        panel_bottom = (22, 25, 33)
        if self.feedback == "correct":
            panel_top, panel_bottom = (34, 66, 52), (20, 42, 34)
        elif self.feedback == "wrong":
            panel_top, panel_bottom = (66, 34, 38), (42, 20, 24)

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        for i in range(panel_h):
            t = i / panel_h
            col = _lerp_color(panel_top, panel_bottom, t)
            pygame.draw.line(panel_surf, (*col, 235), (0, i), (panel_w, i))
        mask = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, panel_w, panel_h), border_radius=20)
        panel_surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(panel_surf, (px, py))
        pygame.draw.rect(surf, UI_ACCENT, (px, py, panel_w, panel_h), 3, border_radius=20)

        font_small = pygame.font.Font(None, 22)
        label = font_small.render(
            f"CHECKPOINT {self.checkpoint_index + 1} / {self.total_checkpoints}", True, (200, 210, 220)
        )
        surf.blit(label, (px + panel_w // 2 - label.get_width() // 2, py + 18))
        dot_r = 8
        total_w = self.total_checkpoints * (dot_r * 2 + 10) - 10
        dot_x = px + panel_w // 2 - total_w // 2 + dot_r
        for i in range(self.total_checkpoints):
            color = UI_ACCENT if i < self.checkpoint_index else \
                    UI_ACCENT_2 if i == self.checkpoint_index else (80, 84, 92)
            pygame.draw.circle(surf, color, (dot_x, py + 46), dot_r)
            dot_x += dot_r * 2 + 10

        font_title = pygame.font.Font(None, 34)
        title = font_title.render("Traffic Light Math Challenge", True, UI_TEXT)
        surf.blit(title, (px + panel_w // 2 - title.get_width() // 2, py + 66))

        font_q = pygame.font.Font(None, 30)
        lines = self.question_text.split("\n")
        qy = py + 120
        for line in lines:
            qs = font_q.render(line, True, (230, 232, 236))
            surf.blit(qs, (px + panel_w // 2 - qs.get_width() // 2, qy))
            qy += 34

        box_w, box_h = 220, 46
        box_x = px + panel_w // 2 - box_w // 2
        box_y = qy + 14
        box_color = (250, 250, 252)
        border_color = UI_ACCENT
        if self.feedback == "wrong":
            border_color = (230, 90, 90)
        elif self.feedback == "correct":
            border_color = (90, 220, 140)
        pygame.draw.rect(surf, box_color, (box_x, box_y, box_w, box_h), border_radius=12)
        pygame.draw.rect(surf, border_color, (box_x, box_y, box_w, box_h), 3, border_radius=12)
        font_input = pygame.font.Font(None, 32)
        txt = font_input.render(self.input_text or " ", True, (25, 25, 28))
        surf.blit(txt, (box_x + 14, box_y + 8))

        btn_w, btn_h = 160, 44
        btn_x = px + panel_w // 2 - btn_w // 2
        btn_y = box_y + box_h + 16
        pygame.draw.rect(surf, UI_ACCENT, (btn_x, btn_y, btn_w, btn_h), border_radius=14)
        pygame.draw.rect(surf, _shade(UI_ACCENT, -0.25), (btn_x, btn_y, btn_w, btn_h), 2, border_radius=14)
        font_btn = pygame.font.Font(None, 26)
        btn_txt = font_btn.render("SUBMIT (Enter)", True, (14, 24, 20))
        surf.blit(btn_txt, (btn_x + btn_w // 2 - btn_txt.get_width() // 2, btn_y + 10))

        if self.feedback == "correct":
            fb = font_q.render("Correct! Light turning green...", True, (110, 230, 160))
            surf.blit(fb, (px + panel_w // 2 - fb.get_width() // 2, py + panel_h - 34))
        elif self.feedback == "wrong":
            fb = font_q.render("Not quite — try again!", True, (240, 130, 130))
            surf.blit(fb, (px + panel_w // 2 - fb.get_width() // 2, py + panel_h - 34))

        self.submit_button_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

    def handle_click(self, pos):
        if self.active and self.feedback != "correct":
            if self.submit_button_rect.collidepoint(pos):
                self.submit()


# ==========================================
# TRUCK CONTROLLER — physics unchanged, visuals fully redesigned
# ==========================================
class TruckController:
    """Physics/state (self.speed, self.bounce, self.sway, update()) is
    byte-for-byte identical to the original. Only the draw_* methods
    below were redesigned: glossy modern paint, real headlight/taillight
    glow, alloy wheel rims, mirrors, brake-light state, and a cockpit
    with a proper instrument cluster."""

    BODY_COLOR = (32, 108, 196)      # glossy modern blue
    BODY_COLOR_LIGHT = (96, 168, 232)
    BODY_COLOR_DARK = (18, 66, 128)

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

    @property
    def is_braking(self):
        """Purely a visual read of existing state (speed vs target) used
        to light up the brake lamps — does not change or feed back into
        physics."""
        return self.speed > self.target_speed + 2.0

    def draw(self, surf, vp_x, bottom_y):
        self.draw_rear(surf, vp_x, bottom_y)

    def _wheel(self, surf, cx, cy, r):
        pygame.draw.circle(surf, (18, 18, 20), (int(cx), int(cy)), r)
        pygame.draw.circle(surf, (60, 62, 66), (int(cx), int(cy)), max(1, int(r * 0.72)))
        for k in range(5):
            ang = k * (2 * math.pi / 5) + 0.3
            ex = cx + math.cos(ang) * r * 0.55
            ey = cy + math.sin(ang) * r * 0.55
            pygame.draw.line(surf, (205, 208, 214), (cx, cy), (ex, ey), max(1, int(r * 0.18)))
        pygame.draw.circle(surf, (150, 152, 158), (int(cx), int(cy)), max(1, int(r * 0.22)))

    def draw_rear(self, surf, vp_x, bottom_y):
        """Modern glossy rear/three-quarter view: sculpted cab, tinted
        rear glass, LED taillight bar (brightens when braking), alloy
        wheels, mirrors, and a soft blurred ground shadow."""
        cx = vp_x + self.sway
        cy = bottom_y - 6 + self.bounce

        outline = (14, 20, 30)
        body = self.BODY_COLOR
        light = self.BODY_COLOR_LIGHT
        dark = self.BODY_COLOR_DARK

        # soft layered ground shadow (cheap blur look)
        for i, a in enumerate((60, 90, 140)):
            w = 132 - i * 14
            h = 20 - i * 4
            shadow = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (10, 12, 10, a), (0, 0, w, h))
            surf.blit(shadow, (cx - w / 2, cy + 12 + i * 1.5))

        # cargo bed with metallic gradient walls
        bed = pygame.Rect(cx - 58, cy - 62, 116, 50)
        for i in range(bed.height):
            t = i / bed.height
            col = _lerp_color((150, 108, 60), (108, 76, 40), t)
            pygame.draw.line(surf, col, (bed.x, bed.y + i), (bed.right, bed.y + i))
        pygame.draw.rect(surf, outline, bed, 3, border_radius=4)
        for i in range(4):
            gx = bed.x + 10 + i * (bed.w - 20) / 3
            pygame.draw.line(surf, (92, 64, 34), (gx, bed.y + 4), (gx, bed.bottom - 4), 2)

        # produce crates (glossy dots -> fruit-market flavor, purely cosmetic)
        for fx, fy, col in [(-30, -14, (214, 66, 58)), (-8, -20, (240, 158, 46)),
                             (14, -14, (96, 172, 76)), (34, -20, (214, 66, 58))]:
            pygame.draw.circle(surf, col, (int(cx + fx), int(bed.y + fy)), 10)
            pygame.draw.circle(surf, tuple(min(255, c + 40) for c in col), (int(cx + fx - 3), int(bed.y + fy - 3)), 4)

        # cab with a glossy vertical-gradient paint job
        cab = pygame.Rect(cx - 46, cy - 12, 92, 26)
        cab_surf = pygame.Surface((cab.w, cab.h), pygame.SRCALPHA)
        for i in range(cab.h):
            t = i / cab.h
            col = _lerp_color(light, dark, t)
            pygame.draw.line(cab_surf, col, (0, i), (cab.w, i))
        surf.blit(cab_surf, (cab.x, cab.y))
        pygame.draw.rect(surf, outline, cab, 3, border_radius=6)
        # gloss highlight streak
        pygame.draw.line(surf, (255, 255, 255, 120), (cab.x + 6, cab.y + 4), (cab.right - 10, cab.y + 4), 2)

        # tinted rear windows
        for wx in (cx - 24, cx + 24):
            win = pygame.Rect(wx - 9, cy - 10, 18, 9)
            pygame.draw.rect(surf, (46, 60, 78), win, border_radius=2)
            pygame.draw.line(surf, (120, 150, 176), (win.x + 2, win.y + 2), (win.right - 4, win.y + 2), 1)

        # side mirrors
        for side in (-1, 1):
            mx = cx + side * 50
            pygame.draw.line(surf, outline, (mx, cy - 8), (mx + side * 6, cy - 12), 2)
            pygame.draw.ellipse(surf, (40, 44, 50), (mx + side * 4, cy - 15, 10, 7))

        # LED taillight bar — glows red normally, brighter/pulsing when braking
        brake = self.is_braking
        tail_glow_alpha = 150 if brake else 70
        for fx, fy, col in [(-30, -14, None), (-8, -20, None),
                             (14, -14, None), (34, -20, None)]:
            pos = (int(cx + fx), int(bed.y + fy))
            glow_color = (255, 70, 60) if brake else (220, 60, 55)
            _soft_glow(surf, pos, 14 if brake else 9, glow_color, max_alpha=tail_glow_alpha, steps=3)

        for wx in (cx - 24, cx + 24):
            pygame.draw.circle(surf, (170, 45, 40), (int(wx), int(cy - 2)), 5)
            pygame.draw.circle(surf, (255, 130, 120), (int(wx - 1), int(cy - 3)), 2)

        # alloy wheels
        for wx in (cx - 46, cx + 40):
            self._wheel(surf, wx, cy + 16, 13)

        # rear bumper + reflective license plate
        pygame.draw.rect(surf, (60, 64, 70), (cx - 40, cy + 4, 80, 6), border_radius=2)
        plate = pygame.Rect(cx - 22, cy + 6, 44, 12)
        pygame.draw.rect(surf, (245, 242, 232), plate, border_radius=2)
        pygame.draw.rect(surf, dark, plate, 1, border_radius=2)

    def draw_front(self, surf, vp_x, bottom_y, extra_scale=1.0):
        """Modern front-on view: sculpted glossy hood, chrome grille,
        projector-style headlights with real glow, tinted windshield with
        a highlight sweep, alloy wheels."""
        s = extra_scale
        cx = vp_x + self.sway
        cy = bottom_y - 6 + self.bounce

        outline = (14, 20, 30)
        body = self.BODY_COLOR
        light = self.BODY_COLOR_LIGHT
        dark = self.BODY_COLOR_DARK

        for i, a in enumerate((60, 90, 140)):
            w = (128 - i * 14) * s
            h = (18 - i * 4) * s
            shadow = pygame.Surface((max(1, int(w)), max(1, int(h))), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (10, 12, 10, a), (0, 0, w, h))
            surf.blit(shadow, (cx - w / 2, cy + 10 * s + i * 1.5))

        # front bumper / chrome grille
        bumper = pygame.Rect(cx - 54 * s, cy - 6 * s, 108 * s, 20 * s)
        pygame.draw.rect(surf, (74, 78, 84), bumper, border_radius=int(4 * s))
        grille = pygame.Rect(cx - 30 * s, cy - 2 * s, 60 * s, 10 * s)
        chrome_top = (220, 224, 228)
        chrome_bot = (130, 134, 140)
        grille_surf = pygame.Surface((max(1, grille.w), max(1, grille.h)))
        for i in range(grille.h):
            t = i / max(1, grille.h)
            grille_surf.fill(_lerp_color(chrome_top, chrome_bot, t), (0, i, grille.w, 1))
        surf.blit(grille_surf, (grille.x, grille.y))
        for gx in range(4):
            lx = grille.x + 6 * s + gx * 16 * s
            pygame.draw.line(surf, (70, 74, 78), (lx, grille.y + 2 * s), (lx, grille.bottom - 2 * s), max(1, int(1.6 * s)))

        # glossy hood/cab with gradient + highlight sweep
        cab = pygame.Rect(cx - 48 * s, cy - 46 * s, 96 * s, 42 * s)
        cab_surf = pygame.Surface((max(1, cab.w), max(1, cab.h)), pygame.SRCALPHA)
        for i in range(cab.h):
            t = i / max(1, cab.h)
            col = _lerp_color(light, body, t)
            pygame.draw.line(cab_surf, col, (0, i), (cab.w, i))
        surf.blit(cab_surf, (cab.x, cab.y))
        pygame.draw.rect(surf, outline, cab, max(1, int(3 * s)), border_radius=int(8 * s))
        pygame.draw.line(surf, (255, 255, 255), (cab.x + 8 * s, cab.y + 5 * s),
                          (cab.right - 10 * s, cab.y + 5 * s), max(1, int(2 * s)))

        windshield = pygame.Rect(cx - 38 * s, cy - 40 * s, 76 * s, 22 * s)
        wglass_surf = pygame.Surface((max(1, windshield.w), max(1, windshield.h)))
        for i in range(windshield.h):
            t = i / max(1, windshield.h)
            col = _lerp_color((160, 202, 222), (100, 150, 176), t)
            wglass_surf.fill(col, (0, i, windshield.w, 1))
        surf.blit(wglass_surf, (windshield.x, windshield.y))
        pygame.draw.rect(surf, outline, windshield, max(1, int(2 * s)), border_radius=int(5 * s))
        pygame.draw.line(surf, outline, (cx, windshield.y), (cx, windshield.bottom), max(1, int(2 * s)))
        pygame.draw.line(surf, (255, 255, 255), (windshield.x + 4 * s, windshield.y + 3 * s),
                          (windshield.x + windshield.w * 0.4, windshield.y + 3 * s), max(1, int(1.6 * s)))

        # projector headlights with strong bloom
        for hx in (cx - 40 * s, cx + 40 * s):
            _soft_glow(surf, (hx, cy - 4 * s), max(8, 20 * s), (255, 250, 210), max_alpha=140, steps=4)
            pygame.draw.circle(surf, (255, 250, 220), (int(hx), int(cy - 4 * s)), max(3, int(9 * s)))
            pygame.draw.circle(surf, (255, 255, 255), (int(hx), int(cy - 4 * s)), max(1, int(4 * s)))
            pygame.draw.circle(surf, (120, 140, 160), (int(hx), int(cy - 4 * s)), max(1, int(2 * s)))

        # turn-signal indicators beside the headlights
        for hx, side in ((cx - 52 * s, -1), (cx + 52 * s, 1)):
            pygame.draw.circle(surf, (255, 176, 60), (int(hx), int(cy - 2 * s)), max(2, int(4 * s)))

        for wx in (cx - 56 * s, cx + 50 * s):
            self._wheel(surf, wx, cy + 14 * s, max(4, int(12 * s)))

        plate = pygame.Rect(cx - 20 * s, cy + 4 * s, 40 * s, 11 * s)
        pygame.draw.rect(surf, (245, 242, 232), plate, border_radius=int(2 * s))
        pygame.draw.rect(surf, outline, plate, max(1, int(1 * s)), border_radius=int(2 * s))

    def draw_dashboard(self, surf, screen_w, screen_h):
        """Modernized cockpit: brushed-metal dash, backlit gauge cluster
        with live speed/tach needles, gear indicator (derived from
        existing speed/target state, no new state added), warning strip,
        two-tone wheel with hands, tinted A-pillars + wing mirror,
        rear-view mirror, sun visors, animated glass glare."""
        bob_x = self.sway * 0.6
        bob_y = self.bounce * 0.8

        dash_h = int(screen_h * 0.25)
        dash_y = screen_h - dash_h
        dash_rect = pygame.Rect(0, dash_y, screen_w, dash_h).move(int(bob_x), int(bob_y))

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

        for i in range(dash_rect.height):
            t = i / max(1, dash_rect.height - 1)
            col = _lerp_color((58, 62, 70), (20, 22, 26), t)
            pygame.draw.line(surf, col, (dash_rect.x, dash_rect.y + i), (dash_rect.right, dash_rect.y + i))
        pygame.draw.rect(surf, UI_ACCENT, (dash_rect.x, dash_rect.y, dash_rect.w, 2))
        pygame.draw.rect(surf, (10, 11, 13), (dash_rect.x, dash_rect.y + 2, dash_rect.w, 3))
        for sx in range(0, screen_w, 14):
            pygame.draw.line(surf, (74, 78, 86),
                              (sx + bob_x, dash_rect.y + 10), (sx + 6 + bob_x, dash_rect.y + 10), 1)

        wheel_cx = screen_w / 2 + bob_x
        wheel_cy = screen_h - dash_h * 0.06 + bob_y
        wheel_r = int(screen_w * 0.11)

        pygame.draw.circle(surf, (14, 14, 15), (int(wheel_cx), int(wheel_cy)), wheel_r + 3)
        pygame.draw.circle(surf, (30, 31, 33), (int(wheel_cx), int(wheel_cy)), wheel_r, width=max(7, wheel_r // 5))
        pygame.draw.circle(surf, (52, 54, 58), (int(wheel_cx), int(wheel_cy)), wheel_r - 3,
                            width=max(2, wheel_r // 16))
        for ang in (200, 340, 90):
            rad = math.radians(ang)
            end = (wheel_cx + math.cos(rad) * wheel_r * 0.92, wheel_cy + math.sin(rad) * wheel_r * 0.92)
            pygame.draw.line(surf, (22, 23, 25), (wheel_cx, wheel_cy), end, max(4, wheel_r // 9))
            pygame.draw.line(surf, (70, 74, 80), (wheel_cx, wheel_cy), end, max(1, wheel_r // 24))
        hub_r = max(5, wheel_r // 6)
        pygame.draw.circle(surf, (36, 38, 42), (int(wheel_cx), int(wheel_cy)), hub_r)
        pygame.draw.circle(surf, UI_ACCENT_2, (int(wheel_cx), int(wheel_cy)), max(2, hub_r // 2))

        for side in (-1, 1):
            hx = wheel_cx + side * wheel_r * 0.97
            hy = wheel_cy + wheel_r * 0.12
            pygame.draw.ellipse(surf, (48, 38, 30), (hx - 15, hy - 11, 30, 24))
            pygame.draw.ellipse(surf, (62, 50, 40), (hx - 15 + side * 2, hy - 13, 20, 16))
            for k in range(3):
                lx = hx - 8 + k * 7
                pygame.draw.line(surf, (26, 20, 15), (lx, hy - 4), (lx, hy + 8), 2)

        speed_cx = wheel_cx - wheel_r * 2.15
        tach_cx = wheel_cx + wheel_r * 2.15
        gauge_cy = wheel_cy - wheel_r * 0.05
        gauge_r = max(28, int(wheel_r * 0.78))

        def draw_gauge(cx, cy, r, value, max_value, unit, needle_color):
            if cx < r or cx > screen_w - r:
                return
            pygame.draw.circle(surf, (8, 8, 8), (int(cx), int(cy)), r + 4)
            for i in range(r):
                t = i / r
                col = _lerp_color((30, 32, 32), (14, 15, 15), t)
                pygame.draw.circle(surf, col, (int(cx), int(cy)), r - i, 1)
            pygame.draw.circle(surf, UI_ACCENT, (int(cx), int(cy)), r, 2)
            start_ang, end_ang = 135, 405
            for tick in range(6):
                a = math.radians(start_ang + (end_ang - start_ang) * tick / 5)
                x1 = cx + math.cos(a) * r * 0.82
                y1 = cy + math.sin(a) * r * 0.82
                x2 = cx + math.cos(a) * r * 0.95
                y2 = cy + math.sin(a) * r * 0.95
                pygame.draw.line(surf, (210, 214, 214), (x1, y1), (x2, y2), 2)
            frac = max(0.0, min(1.0, value / max_value))
            needle_ang = math.radians(start_ang + (end_ang - start_ang) * frac)
            nx = cx + math.cos(needle_ang) * r * 0.72
            ny = cy + math.sin(needle_ang) * r * 0.72
            pygame.draw.line(surf, needle_color, (cx, cy), (nx, ny), 3)
            pygame.draw.circle(surf, (220, 220, 220), (int(cx), int(cy)), 4)
            font_g = pygame.font.Font(None, max(14, int(r * 0.5)))
            val_txt = font_g.render(str(int(value)), True, UI_TEXT)
            surf.blit(val_txt, (cx - val_txt.get_width() / 2, cy + r * 0.28))
            font_lbl = pygame.font.Font(None, 14)
            lbl_txt = font_lbl.render(unit, True, UI_ACCENT)
            surf.blit(lbl_txt, (cx - lbl_txt.get_width() / 2, cy + r * 0.28 + val_txt.get_height() - 2))

        draw_gauge(speed_cx, gauge_cy, gauge_r, self.speed, max(CRUISE_SPEED * 1.3, 60), "km/h", (240, 90, 70))
        rpm = 1000 + (self.speed / max(1.0, CRUISE_SPEED)) * 4500
        draw_gauge(tach_cx, gauge_cy, gauge_r, rpm, 6000, "rpm x1000", (90, 170, 240))

        # gear indicator between the gauges (derived purely from existing
        # speed state: P while stationary, D while moving/braking — no
        # new gameplay state introduced)
        gear = "P" if self.speed < 1.0 else "D"
        font_gear = pygame.font.Font(None, 26)
        gtxt = font_gear.render(gear, True, UI_ACCENT_2)
        surf.blit(gtxt, (wheel_cx - gtxt.get_width() / 2, wheel_cy - wheel_r - 22))

        lights = [("READY", UI_ACCENT, True), ("BATT", (70, 72, 76), False),
                  ("TEMP", (70, 72, 76), False), ("BELT", (70, 72, 76), False)]
        lx = wheel_cx - (len(lights) - 1) * 18
        ly = wheel_cy + wheel_r + 14
        if ly < screen_h - 4:
            for name, color, lit in lights:
                pygame.draw.circle(surf, color, (int(lx), int(ly)), 5)
                if lit:
                    pygame.draw.circle(surf, (200, 255, 220), (int(lx), int(ly)), 7, 1)
                lx += 36

        pillar_w = int(screen_w * 0.05)
        pillar_col = (24, 26, 30)
        accent = self.BODY_COLOR
        left_pillar = [(0, 0), (pillar_w, 0), (pillar_w * 0.42, dash_rect.y), (0, dash_rect.y)]
        right_pillar = [(screen_w - pillar_w, 0), (screen_w, 0),
                         (screen_w, dash_rect.y), (screen_w - pillar_w * 0.42, dash_rect.y)]
        pygame.draw.polygon(surf, pillar_col, left_pillar)
        pygame.draw.polygon(surf, pillar_col, right_pillar)
        pygame.draw.line(surf, accent, (pillar_w * 0.15, 8), (pillar_w * 0.55, dash_rect.y - 8), 4)
        pygame.draw.line(surf, accent, (screen_w - pillar_w * 0.15, 8), (screen_w - pillar_w * 0.55, dash_rect.y - 8), 4)

        mirror_arm_x = pillar_w * 0.3
        pygame.draw.line(surf, (26, 27, 30), (mirror_arm_x, 40), (mirror_arm_x - 14, 58), 3)
        pygame.draw.ellipse(surf, (36, 38, 42), (mirror_arm_x - 34, 50, 30, 20))
        pygame.draw.ellipse(surf, (150, 190, 205), (mirror_arm_x - 31, 53, 24, 14))

        mirror_w, mirror_h = int(screen_w * 0.13), 30
        mirror_rect = pygame.Rect(screen_w // 2 - mirror_w // 2 + bob_x, 12 + bob_y, mirror_w, mirror_h)
        pygame.draw.line(surf, (26, 27, 30), (screen_w // 2 + bob_x, 0), (screen_w // 2 + bob_x, mirror_rect.y), 3)
        pygame.draw.rect(surf, (26, 27, 30), mirror_rect, border_radius=6)
        glass_rect = mirror_rect.inflate(-6, -8)
        if glass_rect.width > 0 and glass_rect.height > 0:
            for i in range(glass_rect.height):
                t = i / max(1, glass_rect.height - 1)
                col = _lerp_color((140, 178, 190), (190, 216, 224), t)
                pygame.draw.line(surf, col, (glass_rect.x, glass_rect.y + i), (glass_rect.right, glass_rect.y + i))
            pygame.draw.line(surf, UI_ACCENT, (glass_rect.x, glass_rect.bottom - 4),
                              (glass_rect.right, glass_rect.bottom - 4), 2)
        pygame.draw.rect(surf, (12, 12, 13), mirror_rect, 2, border_radius=6)

        for side in (-1, 1):
            vx = screen_w / 2 + side * screen_w * 0.30 + bob_x
            visor = pygame.Rect(vx - 30, 2 + bob_y, 60, 10)
            pygame.draw.rect(surf, (40, 42, 46), visor, border_radius=3)


# ==========================================
# UI (progress bar / status text) — modern transparent HUD
# ==========================================
class UI:
    def __init__(self, screen_w):
        self.screen_w = screen_w
        self.font = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 20)
        self.font_tiny = pygame.font.Font(None, 16)

    def _panel(self, surf, rect, radius=12, fill=(*UI_PANEL, 190)):
        panel = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(panel, fill, (0, 0, rect.w, rect.h), border_radius=radius)
        pygame.draw.rect(panel, (*UI_ACCENT, 130), (0, 0, rect.w, rect.h), 1, border_radius=radius)
        surf.blit(panel, (rect.x, rect.y))

    def draw(self, surf, distance, total_distance, checkpoints, phase, camera_mode_label=None,
              truck_speed=None):
        bar_w = self.screen_w - 80
        bar_x, bar_y = 40, 20
        bar_rect = pygame.Rect(bar_x - 6, bar_y - 6, bar_w + 12, 26)
        self._panel(surf, bar_rect, radius=13)

        pygame.draw.rect(surf, (54, 58, 66), (bar_x, bar_y, bar_w, 14), border_radius=7)
        progress = max(0.0, min(1.0, distance / total_distance))
        fill_w = int(bar_w * progress)
        if fill_w > 0:
            fill_surf = pygame.Surface((fill_w, 14), pygame.SRCALPHA)
            for i in range(fill_w):
                t = i / max(1, bar_w)
                col = _lerp_color(UI_ACCENT_2, UI_ACCENT, t)
                pygame.draw.line(fill_surf, col, (i, 0), (i, 14))
            mask = pygame.Surface((fill_w, 14), pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, fill_w, 14), border_radius=7)
            fill_surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(fill_surf, (bar_x, bar_y))

        for cp in checkpoints:
            cp_progress = cp.world_x / total_distance
            cx = bar_x + int(bar_w * cp_progress)
            color = UI_ACCENT if cp.solved else (210, 214, 220)
            pygame.draw.circle(surf, color, (cx, bar_y + 7), 7)
            pygame.draw.circle(surf, (30, 32, 38), (cx, bar_y + 7), 7, 2)

        label_text = {
            "entering": "Pulling onto the highway...",
            "cruising": "Driving to the city market",
            "braking": "Slowing for a checkpoint...",
            "stopped": "Stopped at checkpoint",
            "resuming": "Light green — moving on!",
            "arriving": "Almost at the city...",
        }.get(phase, "")
        if label_text:
            txt = self.font.render(label_text, True, UI_TEXT)
            pad_rect = pygame.Rect(self.screen_w // 2 - txt.get_width() // 2 - 14, 46,
                                    txt.get_width() + 28, txt.get_height() + 12)
            self._panel(surf, pad_rect, radius=14)
            surf.blit(txt, (self.screen_w // 2 - txt.get_width() // 2, 46 + 6))

        if camera_mode_label:
            ctxt = self.font_small.render(camera_mode_label, True, UI_TEXT)
            crect = pygame.Rect(self.screen_w - ctxt.get_width() - 32, 16,
                                 ctxt.get_width() + 24, ctxt.get_height() + 12)
            self._panel(surf, crect, radius=12)
            surf.blit(ctxt, (crect.x + 12, crect.y + 6))

        if truck_speed is not None:
            spd_txt = self.font_small.render(f"{int(truck_speed)} km/h", True, UI_ACCENT)
            srect = pygame.Rect(40, 54, spd_txt.get_width() + 24, spd_txt.get_height() + 12)
            self._panel(surf, srect, radius=12)
            surf.blit(spd_txt, (srect.x + 12, srect.y + 6))


# ==========================================
# HIGHWAY SCENE (orchestrator) — logic unchanged, richer draw pass
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
        self.ambient_traffic = AmbientTraffic(count=10)
        self.truck = TruckController(screen_h, truck_surface)
        self.sound = SoundManager()
        self.quiz = MathQuiz(self.sound)
        self.ui = UI(screen_w)
        self.fade = FadeTransition(0.7)

        self.camera_manager = CameraManager(
            screen_w, screen_h, self.horizon_y, self.road.bottom_y, self.road.vp_x
        )
        self._camera_mode_labels = {
            CameraManager.FIRST_PERSON: "1ST PERSON [1]",
            CameraManager.SECOND_PERSON: "2ND PERSON [2]",
            CameraManager.THIRD_PERSON: "3RD PERSON [3]",
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

        cm = self.camera_manager
        horizon_y = cm.horizon_y
        bottom_y = cm.bottom_y
        vp_x = cm.vp_x()
        width_mult = cm.width_mult
        scale_mult = cm.scale_mult

        self.background.draw(surf, self.camera, progress, horizon_y=horizon_y)
        self.road.draw_roadside(surf, self.camera, horizon_y=horizon_y, bottom_y=bottom_y,
                                 vp_x=vp_x, width_mult=width_mult, scale_mult=scale_mult)
        self.ambient_traffic.draw(surf, self.camera, self.road, horizon_y, bottom_y, vp_x,
                                   width_mult, scale_mult)
        self.road.draw_guardrails(surf, self.camera, horizon_y=horizon_y, bottom_y=bottom_y,
                                   vp_x=vp_x, width_mult=width_mult)
        self.road.draw_road(surf, self.camera, horizon_y=horizon_y, bottom_y=bottom_y,
                             vp_x=vp_x, width_mult=width_mult)
        self.road.draw_signage(surf, self.camera, horizon_y=horizon_y, bottom_y=bottom_y,
                                vp_x=vp_x, width_mult=width_mult, scale_mult=scale_mult,
                                total_distance=self.total_distance)

        for cp in self.checkpoints:
            cp.draw(surf, self.camera, self.road, horizon_y=horizon_y, bottom_y=bottom_y,
                    vp_x=vp_x, width_mult=width_mult, scale_mult=scale_mult)

        if cm.truck_draw_mode == "rear":
            self.truck.draw_rear(surf, vp_x, bottom_y)
        elif cm.truck_draw_mode == "front":
            wave = cm.lead_distance_wave()
            breathe_scale = 1.0 + (wave / 200.0)
            self.truck.draw_front(surf, vp_x, bottom_y, extra_scale=breathe_scale)

        self.ui.draw(surf, max(0, self.camera.distance), self.total_distance, self.checkpoints,
                     self.phase, camera_mode_label=self._camera_mode_labels.get(cm.mode),
                     truck_speed=self.truck.speed)

        if cm.truck_draw_mode == "hidden":
            self.truck.draw_dashboard(surf, self.screen_w, self.screen_h)

        if self.phase == "arriving":
            font_big = pygame.font.Font(None, 54)
            txt = font_big.render("Welcome to the City Market!", True, UI_TEXT)
            bg = pygame.Surface((txt.get_width() + 44, txt.get_height() + 28), pygame.SRCALPHA)
            for i in range(bg.get_height()):
                t = i / bg.get_height()
                col = _lerp_color((36, 120, 84), (20, 70, 52), t)
                pygame.draw.line(bg, (*col, 225), (0, i), (bg.get_width(), i))
            pygame.draw.rect(bg, (*UI_ACCENT, 255), (0, 0, bg.get_width(), bg.get_height()), 3, border_radius=16)
            surf.blit(bg, (self.screen_w // 2 - bg.get_width() // 2, self.screen_h // 2 - 60))
            surf.blit(txt, (self.screen_w // 2 - txt.get_width() // 2, self.screen_h // 2 - 46))

        if self.quiz.active:
            self.quiz.draw(surf, self.screen_w, self.screen_h)

        self.fade.draw(surf)