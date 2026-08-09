import pygame
import random
import math
import array

# ==========================================
# CONSTANTS
# ==========================================
SKY_TOP = (82, 142, 205)
SKY_MID = (150, 196, 228)
SKY_BOTTOM = (205, 226, 232)
SKY_HORIZON_WARM = (255, 236, 200)
HILL_FAR = (118, 168, 96)
HILL_MID = (96, 152, 82)
HILL_NEAR = (66, 132, 70)
SNOW_PEAK = (235, 240, 248)
SNOW_SHADOW = (176, 196, 214)
MOUNTAIN_HAZE = (195, 210, 222)
ROAD_DARK = (66, 69, 76)
ROAD_MID = (76, 79, 86)
ROAD_LIGHT = (86, 89, 96)
ROAD_EDGE_COLOR = (238, 238, 238)
CENTER_LINE_COLOR = (245, 205, 55)
LANE_COLOR = (200, 200, 205)
MEDIAN_COLOR = (168, 168, 172)
GUARDRAIL_POST = (70, 74, 80)
GUARDRAIL_BEAM = (196, 200, 206)
GUARDRAIL_SHADOW = (120, 124, 132)
REFLECTOR_COLOR = (255, 255, 255)
SKYLINE_FAR = (152, 175, 200)
SKYLINE_NEAR = (112, 138, 168)

# Fonts cached once (avoids per-frame allocation in draw loops)
_FONT_CACHE = {}

SEGMENT_LENGTH = 16.0
RENDER_DISTANCE = 1500.0
ROAD_WIDTH = 2600.0
HALF_ROAD = ROAD_WIDTH / 2
NUM_LANES = 3
LANE_WIDTH = ROAD_WIDTH / NUM_LANES
MEDIAN_WIDTH = 140.0
RIGHT_OUTER_EDGE = HALF_ROAD + MEDIAN_WIDTH + ROAD_WIDTH

ACCEL = 280.0
BRAKE = 520.0
FRICTION = 90.0
STEER_SPEED = 900.0
STEER_RETURN = 3.2
CENTRIFUGAL = 0.00032
OFFROAD_FRICTION = 280.0

CHECKPOINT_DISTANCES = [1500, 3100, 4700, 6300]
FINAL_DISTANCE = 7400

CAM_MOTION_OFF = 0
CAM_MOTION_LOW = 1
CAM_MOTION_NORMAL = 2


def _hash01(n):
    n = (n * 2654435761) & 0xFFFFFFFF
    return (n % 10000) / 10000.0


def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp_color(c1, c2, t):
    return (int(_lerp(c1[0], c2[0], t)),
            int(_lerp(c1[1], c2[1], t)),
            int(_lerp(c1[2], c2[2], t)))


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def project(rd, horizon_y, bottom_y, scale_mult=1.0):
    t = _clamp(1.0 - rd / RENDER_DISTANCE, 0.0, 1.0)
    depth = t * t
    y = horizon_y + (bottom_y - horizon_y) * depth
    scale = (0.025 + 0.975 * depth) * scale_mult
    return depth, scale, y


def project_world(world_x, world_y, world_z, camera_x, camera_y, camera_z,
                  horizon_y, bottom_y, vp_x, bottom_half, width_mult, scale_mult):
    rel_z = world_z - camera_z
    if rel_z <= 0.3:
        return None
    depth, scale, screen_y = project(rel_z, horizon_y, bottom_y, scale_mult)
    scale_x = bottom_half * width_mult / HALF_ROAD
    screen_x = vp_x + (world_x - camera_x) * scale * scale_x
    screen_y -= (world_y - camera_y) * scale * 0.22
    return screen_x, screen_y, scale, depth


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
            self.sounds["crash"] = self._tone_sequence([(150, 120), (100, 180)], 0.35)
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
# CLOUD & BIRD
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
        pygame.draw.ellipse(surf, (208, 222, 236), (sx, self.y + 5*s, 62*s, 20*s))
        pygame.draw.ellipse(surf, (233, 240, 248), (sx + 4*s, self.y + 2*s, 58*s, 20*s))
        pygame.draw.ellipse(surf, (255, 255, 255), (sx + 16*s, self.y - 9*s, 46*s, 24*s))
        pygame.draw.ellipse(surf, (250, 252, 255), (sx + 36*s, self.y, 50*s, 18*s))
        pygame.draw.ellipse(surf, (255, 255, 255), (sx + 8*s, self.y - 4*s, 30*s, 15*s))
        pygame.draw.ellipse(surf, (255, 255, 255), (sx + 24*s, self.y - 2*s, 20*s, 10*s))


class Bird:
    def __init__(self, x, y, speed, phase):
        self.x = x
        self.y = y
        self.speed = speed
        self.phase = phase

    def update(self, dt):
        self.x -= self.speed * dt
        self.phase += dt * 7

    def draw(self, surf, screen_w):
        sx = self.x % (screen_w + 200) - 100
        flap = math.sin(self.phase) * 3
        pygame.draw.line(surf, (45, 45, 58), (sx - 6, self.y + flap), (sx, self.y), 2)
        pygame.draw.line(surf, (45, 45, 58), (sx, self.y), (sx + 6, self.y + flap), 2)


# ==========================================
# CITY BACKGROUND
# ==========================================
class CityBackground:
    def __init__(self, screen_w, screen_h, horizon_y):
        self.w = screen_w
        self.h = screen_h
        self.horizon_y = horizon_y
        self.drift = 0.0
        self.clouds = [
            Cloud(random.randint(0, screen_w), random.randint(15, int(horizon_y * 0.35)),
                  random.uniform(0.8, 1.4), random.uniform(4, 10))
            for _ in range(6)
        ]
        self.birds = [
            Bird(random.randint(0, screen_w), random.randint(20, int(horizon_y * 0.45)),
                 random.uniform(14, 28), random.uniform(0, 6))
            for _ in range(5)
        ]
        self.sun_x = int(screen_w * 0.72)
        self.sun_y = int(horizon_y * 0.38)
        
        random.seed(77)
        self.mountain_far = self._wavy_points(screen_w * 1.6, horizon_y - 65, 55, 350)
        self.mountain_near = self._wavy_points(screen_w * 1.6, horizon_y - 35, 35, 240)
        # Additional Himalayan depth layers: distant blue range + snowy peaks
        self.mountain_back = self._wavy_points(screen_w * 1.6, horizon_y - 92, 40, 420)
        self.mountain_snow = self._wavy_points(screen_w * 1.6, horizon_y - 118, 30, 520)
        
        self.buildings_far = self._make_skyline(screen_w * 1.6, 80, 180, 24, 44, SKYLINE_FAR)
        self.buildings_near = self._make_skyline(screen_w * 1.6, 50, 240, 20, 38, SKYLINE_NEAR)
        
        random.seed(88)
        self.terraced_hill_1 = self._wavy_points(screen_w * 1.6, horizon_y - 10, 20, 280)
        self.terraced_hill_2 = self._wavy_points(screen_w * 1.6, horizon_y + 5, 15, 200)
        self.hill_far_pts = self._wavy_points(screen_w * 1.6, horizon_y - 8, 14, 150)
        self.hill_near_pts = self._wavy_points(screen_w * 1.6, horizon_y + 14, 18, 180)
        
        self.dzong_positions = [
            random.randint(int(screen_w * 0.2), int(screen_w * 0.4)),
            random.randint(int(screen_w * 1.1), int(screen_w * 1.4))
        ]
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
        for b in self.birds:
            b.update(dt)
        self.drift += dt * 2.5

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

    def _draw_distant_dzong(self, surf, x, y):
        col = (95, 115, 105)
        pygame.draw.rect(surf, col, (x - 20, y - 15, 40, 15))
        pygame.draw.rect(surf, col, (x - 8, y - 28, 16, 13))
        roof_col = (75, 45, 35)
        pygame.draw.polygon(surf, roof_col, [(x - 22, y - 15), (x - 18, y - 19), (x + 18, y - 19), (x + 22, y - 15)])
        pygame.draw.polygon(surf, roof_col, [(x - 10, y - 28), (x - 6, y - 34), (x + 6, y - 34), (x + 10, y - 28)])
        pygame.draw.circle(surf, (200, 160, 50), (x, y - 36), 2)

    def _draw_terraced_hill(self, surf, pts, span, base_y):
        offset = self.drift % span
        for layer in range(3):
            col = (105, 155, 85) if layer % 2 == 0 else (120, 170, 95)
            for base_off in (-offset, -offset + span):
                shifted = [(x + base_off, y + layer * 3) for x, y in pts]
                poly = [(shifted[0][0], self.h)] + shifted + [(shifted[-1][0], self.h)]
                pygame.draw.polygon(surf, col, poly)
                if layer < 2:
                    line_pts = [(p[0], p[1] + 3) for p in shifted]
                    if len(line_pts) > 1:
                        pygame.draw.lines(surf, (85, 115, 65), False, line_pts, 1)

    def draw(self, surf, camera_z, progress, horizon_y=None):
        hy = self.horizon_y if horizon_y is None else int(horizon_y)
        hy = max(1, min(self.h - 1, hy))
        WARM = (255, 215, 165)
        for i in range(hy):
            t = i / max(1, hy)
            if t < 0.6:
                k = t / 0.6
                r = int(SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * k)
                g = int(SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * k)
                b = int(SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * k)
            else:
                k = (t - 0.6) / 0.4
                r = int(SKY_BOTTOM[0] + (WARM[0] - SKY_BOTTOM[0]) * k)
                g = int(SKY_BOTTOM[1] + (WARM[1] - SKY_BOTTOM[1]) * k)
                b = int(SKY_BOTTOM[2] + (WARM[2] - SKY_BOTTOM[2]) * k)
            pygame.draw.line(surf, (r, g, b), (0, i), (self.w, i))
        if hy < self.h:
            pygame.draw.rect(surf, SKY_BOTTOM, (0, hy, self.w, self.h - hy))
        for r, a in ((96, 14), (66, 24), (44, 38)):
            glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 218, 140, a), (r, r), r)
            surf.blit(glow, (self.sun_x - r, self.sun_y - r))
        pygame.draw.circle(surf, (255, 246, 210), (self.sun_x, self.sun_y), 24)
        pygame.draw.circle(surf, (255, 255, 240), (self.sun_x - 7, self.sun_y - 7), 9)
        for c in self.clouds:
            c.draw(surf, self.w)
        for b in self.birds:
            b.draw(surf, self.w)
        y_shift = hy - self.horizon_y
        scale_boost = 1.0 + 0.3 * progress
        
        self._draw_hill(surf, self.mountain_far, self.w * 1.6, (140, 165, 195), y_extra=y_shift)
        self._draw_hill(surf, self.mountain_near, self.w * 1.6, (110, 145, 130), y_extra=y_shift)
        
        offset = self.drift % (self.w * 1.6)
        for dx in self.dzong_positions:
            for base_off in (-offset, -offset + self.w * 1.6):
                adjusted_dx = dx + base_off
                if -100 <= adjusted_dx <= self.w + 100:
                    self._draw_distant_dzong(surf, adjusted_dx, hy - 45 + y_shift)

        base_far = hy + 2
        base_near = hy + 6
        self._draw_skyline(surf, self.buildings_far, self.w * 1.6, base_far)
        self._draw_skyline(surf, self.buildings_near, self.w * 1.6, base_near + 6 * scale_boost)
        
        self._draw_terraced_hill(surf, self.terraced_hill_1, self.w * 1.6, hy + y_shift)
        self._draw_terraced_hill(surf, self.terraced_hill_2, self.w * 1.6, hy + 8 + y_shift)
        
        self._draw_hill(surf, self.hill_far_pts, self.w * 1.6, HILL_FAR, y_extra=y_shift)
        self._draw_hill(surf, self.hill_near_pts, self.w * 1.6, HILL_NEAR, y_extra=y_shift)


# ==========================================
# ROAD SEGMENT
# ==========================================
class RoadSegment:
    def __init__(self, index, z, curve=0.0, y=0.0, length=SEGMENT_LENGTH):
        self.index = index
        self.z = z
        self.curve = curve
        self.y = y
        self.length = length
        self.sprites = []
        self.has_checkpoint = False
        self.checkpoint_id = -1
        self.light_state = "green"
        self.solved = False
        self.heading = 0.0
        self.road_x = 0.0
        self.is_bridge = False
        self.asphalt_noise = random.random()
        self.grass_noise = random.random()


# ==========================================
# ROAD
# ==========================================
class Road:
    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.horizon_y = int(screen_h * 0.40)
        self.bottom_y = int(screen_h * 0.98)
        self.vp_x = screen_w // 2
        self.bottom_half = int(screen_w * 0.38)
        self.segments = []
        self.total_length = 0.0
        self._generate_road()
        self._precompute()
        self._add_sprites()

    def get_lane_x(self, lane, direction="player"):
        if direction == "player":
            return (lane - 1.0) * LANE_WIDTH
        else:
            opp_center = HALF_ROAD + MEDIAN_WIDTH + HALF_ROAD
            return opp_center + (lane - 1.0) * LANE_WIDTH

    def _safe_offset(self, side, clearance):
        if side < 0:
            return -(HALF_ROAD + clearance)
        return (RIGHT_OUTER_EDGE + clearance)

    def _world_half_width(self, stype, scale):
        base_px = {
            'house': 80, 'warehouse': 90, 'gas_station': 80, 'shop': 50,
            'pine': 12, 'tree': 18, 'bush': 11, 'rock': 10,
            'streetlight': 6, 'utility_pole': 9, 'reflector_post': 2,
            'sign_curve': 18, 'sign_speed': 16, 'sign_exit': 20,
            'bridge_railing': 5, 'guardrail': 4,
            'blue_pine': 35, 'broadleaf': 45, 'cypress': 25,
            'bhutan_house': 70, 'farmhouse': 85,
            'tea_stall': 50, 'fruit_stall': 40, 'craft_shop': 60,
            'general_store': 75, 'restaurant': 80, 'urban_shop': 85,
            'bus_stop': 50, 'rice_field': 120,
            'chorten': 35, 'prayer_flags': 25,
            'stone_wall': 70, 'wooden_fence': 70
        }.get(stype, 40)
        px_half = base_px * scale
        return px_half * HALF_ROAD / max(1, self.bottom_half)

    def _add_segment(self, curve=0.0, y=0.0, seg_type="straight"):
        idx = len(self.segments)
        z = idx * SEGMENT_LENGTH
        seg = RoadSegment(idx, z, curve=curve, y=y)
        seg.type = seg_type
        self.segments.append(seg)

    def _add_curve(self, count, max_curve, seg_type="curve"):
        for i in range(count):
            t = i / max(1, count - 1)
            taper = math.sin(t * math.pi)
            curve = max_curve * (0.25 + 0.75 * taper)
            self._add_segment(curve, 0, seg_type)

    def _generate_road(self):
        def add(count, curve=0.0, y=0.0, seg_type="straight"):
            for _ in range(count):
                self._add_segment(curve, y, seg_type)

        add(40, 0, 0, "straight")
        self._add_curve(30, 0.8, "curve_right")
        add(20, 0, 0, "straight")
        add(14, 0, 0, "straight")
        self.segments[-7].has_checkpoint = True
        self.segments[-7].checkpoint_id = 0

        self._add_curve(35, -1.0, "curve_left")
        add(20, 0, 0, "straight")
        for i in range(30):
            t = i / 30.0
            h = math.sin(t * math.pi) * 140
            add(1, 0, h, "hill")
        add(15, 0, 0, "straight")

        for i in range(12):
            seg = RoadSegment(len(self.segments), len(self.segments) * SEGMENT_LENGTH, curve=0.0, y=-20 + i * 2)
            seg.type = "bridge"
            seg.is_bridge = True
            self.segments.append(seg)
        add(10, 0, 0, "straight")

        add(16, 0, 0, "straight")
        self.segments[-7].has_checkpoint = True
        self.segments[-7].checkpoint_id = 1

        self._add_curve(28, 1.2, "curve_right")
        self._add_curve(28, -1.2, "curve_left")
        add(20, 0, 0, "straight")

        for i in range(8):
            seg = RoadSegment(len(self.segments), len(self.segments) * SEGMENT_LENGTH, curve=0.0, y=0)
            seg.type = "overpass"
            seg.is_bridge = True
            self.segments.append(seg)
        add(12, 0, 0, "straight")

        add(16, 0, 0, "straight")
        self.segments[-7].has_checkpoint = True
        self.segments[-7].checkpoint_id = 2

        for i in range(20):
            h = math.sin(i * 0.3) * 40
            add(1, 0.5, h, "curve_right")
        add(15, 0, 0, "straight")
        self._add_curve(28, -1.8, "curve_left")
        add(20, 0, 0, "straight")

        add(16, 0, 0, "straight")
        self.segments[-7].has_checkpoint = True
        self.segments[-7].checkpoint_id = 3

        self._add_curve(25, 0.7, "curve_right")
        self._add_curve(20, -0.7, "curve_left")
        add(45, 0, 0, "straight")
        self.total_length = len(self.segments) * SEGMENT_LENGTH

    def _precompute(self):
        heading = 0.0
        road_x = 0.0
        for seg in self.segments:
            seg.heading = heading
            seg.road_x = road_x
            heading += seg.curve
            road_x += heading

    def _add_sprites(self):
        """Generates static world objects ONCE. Positions are stored as offsets
        relative to the road centerline and never modified at runtime."""
        for seg in self.segments:
            progress = seg.z / FINAL_DISTANCE
            is_rural = progress < 0.5
            is_suburban = 0.5 <= progress < 0.8
            is_urban = progress >= 0.8

            if seg.curve != 0 and seg.index > 0:
                prev = self.segments[seg.index - 1]
                if prev.curve == 0:
                    seg.sprites.append({'type': 'sign_curve', 'side': -1, 'offset': self._safe_offset(-1, self._world_half_width('sign_curve', 1.0) + 120), 'curve_dir': 'left' if seg.curve < 0 else 'right'})

            if seg.index % 90 == 0 and seg.index > 10:
                seg.sprites.append({'type': 'sign_speed', 'side': -1, 'offset': self._safe_offset(-1, self._world_half_width('sign_speed', 1.0) + 120), 'speed': random.choice([60, 80, 100])})

            if seg.has_checkpoint:
                seg.sprites.append({'type': 'sign_exit', 'side': -1, 'offset': self._safe_offset(-1, self._world_half_width('sign_exit', 1.0) + 130)})

            if seg.index % 40 == 0 and not seg.is_bridge:
                side = -1 if (seg.index // 40) % 2 == 0 else 1
                seg.sprites.append({'type': 'streetlight', 'side': side, 'offset': self._safe_offset(side, self._world_half_width('streetlight', 1.0) + 90)})

            if seg.index % 55 == 0 and not seg.is_bridge:
                side = -1 if (seg.index // 55) % 2 == 0 else 1
                seg.sprites.append({'type': 'utility_pole', 'side': side, 'offset': self._safe_offset(side, self._world_half_width('utility_pole', 1.0) + 400)})

            if seg.index % 6 == 0:
                for side in (-1, 1):
                    seg.sprites.append({'type': 'reflector_post', 'side': side, 'offset': self._safe_offset(side, 60)})

            if seg.is_bridge:
                for side in (-1, 1):
                    seg.sprites.append({'type': 'bridge_railing', 'side': side, 'offset': self._safe_offset(side, 20)})

            if not seg.is_bridge:
                # Retaining walls & Fences
                if seg.index % 4 == 0:
                    if abs(seg.curve) > 0.5 or (is_rural and random.random() < 0.3):
                        side = -1 if random.random() < 0.5 else 1
                        seg.sprites.append({'type': 'stone_wall', 'side': side, 'offset': self._safe_offset(side, 120), 'scale': 1.0})
                    elif is_rural and random.random() < 0.2:
                        side = -1 if random.random() < 0.5 else 1
                        seg.sprites.append({'type': 'wooden_fence', 'side': side, 'offset': self._safe_offset(side, 140), 'scale': 1.0})

                # Prayer Flags
                if seg.index % 45 == 0:
                    side = 1 if random.random() < 0.5 else -1
                    seg.sprites.append({'type': 'prayer_flags', 'side': side, 'offset': self._safe_offset(side, 200 + random.random() * 100), 'scale': 1.0})

                # Chortens
                if seg.index % 120 == 0:
                    side = -1 if random.random() < 0.5 else 1
                    seg.sprites.append({'type': 'chorten', 'side': side, 'offset': self._safe_offset(side, 250 + random.random() * 150), 'scale': 1.2})

                # TREES (Dense, layered, clustered)
                # Background forest layer
                if random.random() < 0.7:
                    side = -1 if random.random() < 0.5 else 1
                    dist = 400 + random.random() * 600
                    ttype = random.choice(['blue_pine', 'blue_pine', 'broadleaf', 'cypress'])
                    tscale = 1.5 + random.random() * 2.0
                    seg.sprites.append({'type': ttype, 'side': side, 'offset': self._safe_offset(side, dist), 'scale': tscale, 'bg': True})
                
                # Midground trees (Clustered)
                if random.random() < 0.45:
                    cluster_size = random.randint(2, 4)
                    for _ in range(cluster_size):
                        side = -1 if random.random() < 0.5 else 1
                        ttype = random.choice(['blue_pine', 'broadleaf', 'pine'])
                        tscale = 0.9 + random.random() * 0.9
                        dist = 200 + random.random() * 250
                        seg.sprites.append({'type': ttype, 'side': side, 'offset': self._safe_offset(side, dist), 'scale': tscale})
                        
                # Foreground trees (Large, near road)
                if random.random() < 0.15:
                    side = -1 if random.random() < 0.5 else 1
                    ttype = random.choice(['blue_pine', 'broadleaf'])
                    tscale = 1.5 + random.random() * 1.0
                    dist = 140 + random.random() * 60
                    seg.sprites.append({'type': ttype, 'side': side, 'offset': self._safe_offset(side, dist), 'scale': tscale})

                # BUILDINGS & ROADSIDE ACTIVITY (Transition from rural to urban)
                if seg.index % 2 == 0:
                    side = -1 if random.random() < 0.8 else 1
                    
                    if is_rural:
                        if random.random() < 0.18:
                            btype = random.choice(['bhutan_house', 'bhutan_house', 'farmhouse'])
                            bscale = 0.9 + random.random() * 0.5
                            dist = 300 + random.random() * 200
                            seg.sprites.append({'type': btype, 'side': side, 'offset': self._safe_offset(side, dist), 'scale': bscale, 'variant': random.randint(0, 2)})
                        if random.random() < 0.08:
                            seg.sprites.append({'type': 'rice_field', 'side': side, 'offset': self._safe_offset(side, 350 + random.random() * 200), 'scale': 1.0})
                            
                    elif is_suburban:
                        if random.random() < 0.40:
                            btype = random.choice(['tea_stall', 'fruit_stall', 'craft_shop', 'general_store', 'restaurant'])
                            bscale = 0.8 + random.random() * 0.5
                            dist = 200 + random.random() * 150
                            seg.sprites.append({'type': btype, 'side': side, 'offset': self._safe_offset(side, dist), 'scale': bscale, 'variant': random.randint(0, 2)})
                        if random.random() < 0.15:
                            seg.sprites.append({'type': 'bhutan_house', 'side': side, 'offset': self._safe_offset(side, 350 + random.random() * 150), 'scale': 0.9 + random.random() * 0.5, 'variant': random.randint(0, 2)})
                            
                    elif is_urban:
                        if random.random() < 0.65:
                            btype = random.choice(['urban_shop', 'urban_shop', 'restaurant', 'general_store', 'bus_stop'])
                            bscale = 1.0 + random.random() * 0.6
                            dist = 180 + random.random() * 120
                            seg.sprites.append({'type': btype, 'side': side, 'offset': self._safe_offset(side, dist), 'scale': bscale, 'variant': random.randint(0, 2)})

    def find_segment(self, z):
        idx = int(z // SEGMENT_LENGTH)
        idx = _clamp(idx, 0, len(self.segments) - 1)
        return self.segments[idx]

    def get_road_x(self, z):
        seg = self.find_segment(z)
        if seg.index + 1 < len(self.segments):
            next_seg = self.segments[seg.index + 1]
            t = (z - seg.z) / SEGMENT_LENGTH
            return seg.road_x + (next_seg.road_x - seg.road_x) * t
        return seg.road_x

    def get_road_y(self, z):
        seg = self.find_segment(z)
        if seg.index + 1 < len(self.segments):
            next_seg = self.segments[seg.index + 1]
            t = (z - seg.z) / SEGMENT_LENGTH
            return seg.y + (next_seg.y - seg.y) * t
        return seg.y

    def render(self, surf, camera_x, camera_y, camera_z, horizon_y, bottom_y, vp_x, width_mult, scale_mult):
        if not self.segments:
            return
        cam_idx = int(camera_z // SEGMENT_LENGTH)
        cam_idx = _clamp(cam_idx, 0, len(self.segments) - 1)
        cam_road_x = self.get_road_x(camera_z)
        num_draw = min(int(RENDER_DISTANCE // SEGMENT_LENGTH) + 8, len(self.segments) - cam_idx)

        seg_data = []
        for n in range(num_draw):
            idx = cam_idx + n
            if idx >= len(self.segments):
                break
            seg = self.segments[idx]
            next_seg = self.segments[min(idx + 1, len(self.segments) - 1)]
            near_z = max(seg.z, camera_z + 0.3)
            far_z = seg.z + SEGMENT_LENGTH
            if far_z <= camera_z + 0.3:
                continue
            near_x = seg.road_x - cam_road_x
            far_x = next_seg.road_x - cam_road_x
            p_near = project_world(near_x, seg.y, near_z, camera_x, camera_y, camera_z,
                                   horizon_y, bottom_y, vp_x, self.bottom_half, width_mult, scale_mult)
            p_far = project_world(far_x, next_seg.y, far_z, camera_x, camera_y, camera_z,
                                  horizon_y, bottom_y, vp_x, self.bottom_half, width_mult, scale_mult)
            if p_near is None or p_far is None:
                continue
            sx_near, sy_near, sc_near, depth_near = p_near
            sx_far, sy_far, sc_far, depth_far = p_far
            w_near = self.bottom_half * width_mult * sc_near
            w_far = self.bottom_half * width_mult * sc_far
            seg_data.append({
                'seg': seg,
                'sx_near': sx_near, 'sy_near': sy_near, 'w_near': w_near, 'sc_near': sc_near, 'depth_near': depth_near,
                'sx_far': sx_far, 'sy_far': sy_far, 'w_far': w_far, 'sc_far': sc_far, 'depth_far': depth_far,
            })

        if not seg_data:
            return

        for data in reversed(seg_data):
            sn, sf = data['sx_near'], data['sx_far']
            yn, yf = data['sy_near'], data['sy_far']
            wn, wf = data['w_near'], data['w_far']
            seg = data['seg']
            dn = data['depth_near']
            scn = data['sc_near']
            sc_far = data['sc_far']

            haze_t = dn * 0.45
            gv = int((seg.grass_noise - 0.5) * 16)
            g_base = (95 + gv, 165 + gv, 78 + gv // 2)
            grass_col = _lerp_color(g_base, (175, 195, 205), haze_t)

            median_w_near = max(3, int(5 * scn))
            median_w_far = max(1, int(2.5 * sc_far))
            opp_center_near = sn + wn + median_w_near + wn
            opp_center_far = sf + wf + median_w_far + wf

            if seg.is_bridge:
                bridge_ground = _lerp_color((55, 75, 95), (120, 140, 155), haze_t)
                pygame.draw.polygon(surf, bridge_ground, [(0, yn), (sn - wn, yn), (sf - wf, yf), (0, yf)])
                pygame.draw.polygon(surf, bridge_ground, [(opp_center_near + wn, yn), (self.screen_w, yn), (self.screen_w, yf), (opp_center_far + wf, yf)])
            else:
                grass_left = [(0, yn), (sn - wn, yn), (sf - wf, yf), (0, yf)]
                grass_right = [(opp_center_near + wn, yn), (self.screen_w, yn), (self.screen_w, yf), (opp_center_far + wf, yf)]
                pygame.draw.polygon(surf, grass_col, grass_left)
                pygame.draw.polygon(surf, grass_col, grass_right)

            base_road = ROAD_DARK if seg.asphalt_noise < 0.33 else ROAD_MID if seg.asphalt_noise < 0.66 else ROAD_LIGHT
            road_col = _lerp_color(base_road, (145, 150, 155), haze_t)
            shoulder_col = _lerp_color((150, 145, 135), (185, 180, 170), haze_t)
            median_col = _lerp_color((168, 168, 172), (185, 185, 188), haze_t)

            shoulder_w_near = wn * 0.09
            shoulder_w_far = wf * 0.09
            pygame.draw.polygon(surf, shoulder_col, [(sn - wn, yn), (sn - wn + shoulder_w_near, yn), (sf - wf + shoulder_w_far, yf), (sf - wf, yf)])
            pygame.draw.polygon(surf, shoulder_col, [(sn + wn - shoulder_w_near, yn), (sn + wn, yn), (sf + wf, yf), (sf + wf - shoulder_w_far, yf)])

            road_poly = [(sn - wn + shoulder_w_near, yn), (sn + wn - shoulder_w_near, yn), (sf + wf - shoulder_w_far, yf), (sf - wf + shoulder_w_near, yf)]
            pygame.draw.polygon(surf, road_col, road_poly)

            if seg.asphalt_noise > 0.8 and scn > 0.12:
                patch_col = _lerp_color((base_road[0] - 10, base_road[1] - 10, base_road[2] - 10), (145, 150, 155), haze_t)
                lane = seg.index % NUM_LANES
                px0 = sn - wn + shoulder_w_near + (2 * wn - 2 * shoulder_w_near) * (lane / NUM_LANES)
                px1 = sn - wn + shoulder_w_near + (2 * wn - 2 * shoulder_w_near) * ((lane + 1) / NUM_LANES)
                fx0 = sf - wf + shoulder_w_far + (2 * wf - 2 * shoulder_w_far) * (lane / NUM_LANES)
                fx1 = sf - wf + shoulder_w_far + (2 * wf - 2 * shoulder_w_far) * ((lane + 1) / NUM_LANES)
                pygame.draw.polygon(surf, patch_col, [(px0, yn), (px1, yn), (fx1, yf), (fx0, yf)])

            pygame.draw.polygon(surf, median_col, [(sn + wn, yn), (sn + wn + median_w_near, yn), (sf + wf + median_w_far, yf), (sf + wf, yf)])
            pygame.draw.line(surf, (200, 200, 205), (sn + wn + median_w_near * 0.5, yn), (sf + wf + median_w_far * 0.5, yf), max(1, int(1.5 * scn)))

            pygame.draw.polygon(surf, shoulder_col, [(opp_center_near - wn, yn), (opp_center_near - wn + shoulder_w_near, yn), (opp_center_far - wf + shoulder_w_far, yf), (opp_center_far - wf, yf)])
            pygame.draw.polygon(surf, shoulder_col, [(opp_center_near + wn - shoulder_w_near, yn), (opp_center_near + wn, yn), (opp_center_far + wn, yf), (opp_center_far + wn - shoulder_w_far, yf)])
            opp_road_poly = [(opp_center_near - wn + shoulder_w_near, yn), (opp_center_near + wn - shoulder_w_near, yn), (opp_center_far + wn - shoulder_w_far, yf), (opp_center_far - wn + shoulder_w_near, yf)]
            pygame.draw.polygon(surf, road_col, opp_road_poly)

            if seg.index % 7 == 0 and scn > 0.12:
                crack_col = _lerp_color((65, 68, 72), (120, 125, 128), haze_t)
                for lane in range(NUM_LANES):
                    lx = sn - wn + shoulder_w_near + (2 * wn - 2 * shoulder_w_near) * ((lane + 0.5) / NUM_LANES)
                    lx_far = sf - wf + shoulder_w_far + (2 * wf - 2 * shoulder_w_far) * ((lane + 0.5) / NUM_LANES)
                    pygame.draw.line(surf, crack_col, (lx - 2, yn), (lx_far - 1, yf), max(1, int(1.5 * scn)))

            if seg.index % 2 == 0:
                for lane in range(1, NUM_LANES):
                    lx_near = sn - wn + shoulder_w_near + (2 * wn - 2 * shoulder_w_near) * (lane / NUM_LANES)
                    lx_far = sf - wf + shoulder_w_far + (2 * wf - 2 * shoulder_w_far) * (lane / NUM_LANES)
                    mark_w = max(1, int(2.2 * scn))
                    pygame.draw.line(surf, LANE_COLOR, (lx_near, yn), (lx_far, yf), mark_w)
                    opp_lx_near = opp_center_near - wn + shoulder_w_near + (2 * wn - 2 * shoulder_w_near) * (lane / NUM_LANES)
                    opp_lx_far = opp_center_far - wf + shoulder_w_far + (2 * wf - 2 * shoulder_w_far) * (lane / NUM_LANES)
                    pygame.draw.line(surf, LANE_COLOR, (opp_lx_near, yn), (opp_lx_far, yf), mark_w)

            edge_w = max(2, int(3.5 * scn))
            center_w = max(2, int(2.5 * scn))
            pygame.draw.line(surf, ROAD_EDGE_COLOR, (sn - wn, yn), (sf - wf, yf), edge_w)
            pygame.draw.line(surf, ROAD_EDGE_COLOR, (opp_center_near + wn, yn), (opp_center_far + wf, yf), edge_w)
            pygame.draw.line(surf, CENTER_LINE_COLOR, (sn + wn - 2, yn), (sf + wf - 1, yf), center_w)
            pygame.draw.line(surf, CENTER_LINE_COLOR, (opp_center_near - wn + 2, yn), (opp_center_far - wf + 1, yf), center_w)

            # ADD CONCRETE GUTTER ON OUTER EDGES
            gutter_col = _lerp_color((140, 145, 150), (180, 185, 190), haze_t)
            gutter_w_near = max(1, int(4 * scn))
            gutter_w_far = max(1, int(2 * sc_far))
            pygame.draw.polygon(surf, gutter_col, [
                (sn - wn - gutter_w_near, yn), (sn - wn, yn),
                (sf - wf, yf), (sf - wf - gutter_w_far, yf)
            ])
            pygame.draw.polygon(surf, gutter_col, [
                (opp_center_near + wn, yn), (opp_center_near + wn + gutter_w_near, yn),
                (opp_center_far + wn + gutter_w_far, yf), (opp_center_far + wn, yf)
            ])

            if seg.index % 3 == 0 and scn > 0.12:
                for lane in range(1, NUM_LANES):
                    lx = sn - wn + shoulder_w_near + (2 * wn - 2 * shoulder_w_near) * (lane / NUM_LANES)
                    dot_r = max(1, int(2.2 * scn))
                    pygame.draw.circle(surf, REFLECTOR_COLOR, (int(lx), int(yn)), dot_r)
                    opp_lx = opp_center_near - wn + shoulder_w_near + (2 * wn - 2 * shoulder_w_near) * (lane / NUM_LANES)
                    pygame.draw.circle(surf, REFLECTOR_COLOR, (int(opp_lx), int(yn)), dot_r)

            if seg.index % 40 == 0 and scn > 0.25:
                for lane in range(NUM_LANES):
                    ax = sn - wn + shoulder_w_near + (2 * wn - 2 * shoulder_w_near) * ((lane + 0.5) / NUM_LANES)
                    arrow_s = scn * 0.8
                    pygame.draw.polygon(surf, (200, 200, 200), [(ax, yn - 8 * arrow_s), (ax - 5 * arrow_s, yn + 2 * arrow_s), (ax + 5 * arrow_s, yn + 2 * arrow_s)])
                    opp_ax = opp_center_near - wn + shoulder_w_near + (2 * wn - 2 * shoulder_w_near) * ((lane + 0.5) / NUM_LANES)
                    pygame.draw.polygon(surf, (200, 200, 200), [(opp_ax, yn - 8 * arrow_s), (opp_ax - 5 * arrow_s, yn + 2 * arrow_s), (opp_ax + 5 * arrow_s, yn + 2 * arrow_s)])

            curve_dir = 0
            for look_ahead in range(1, 22):
                future_idx = seg.index + look_ahead
                if future_idx < len(self.segments):
                    f_seg = self.segments[future_idx]
                    if abs(f_seg.curve) > 0.8:
                        curve_dir = 1 if f_seg.curve > 0 else -1
                        break
            if curve_dir != 0 and seg.index % 10 == 0 and scn > 0.15:
                ax = sn - wn + shoulder_w_near + (2 * wn - 2 * shoulder_w_near) * 0.5
                arrow_s = scn * 1.2
                if curve_dir == 1:
                    pygame.draw.polygon(surf, (220, 180, 60), [(ax, yn - 10 * arrow_s), (ax + 15 * arrow_s, yn), (ax, yn + 10 * arrow_s), (ax + 5 * arrow_s, yn)])
                else:
                    pygame.draw.polygon(surf, (220, 180, 60), [(ax, yn - 10 * arrow_s), (ax - 15 * arrow_s, yn), (ax, yn + 10 * arrow_s), (ax - 5 * arrow_s, yn)])

            if (abs(seg.curve) > 1.2 or seg.is_bridge) and scn > 0.08:
                rail_h = max(2, int(9 * scn))
                for side, base_near, base_far in [(-1, sn, sf), (1, opp_center_near, opp_center_far)]:
                    rx = base_near + side * (wn + 8)
                    rx_far = base_far + side * (wf + 5)
                    pygame.draw.line(surf, GUARDRAIL_COLOR, (rx, yn - rail_h), (rx, yn), max(1, int(2.5 * scn)))

            # Draw static roadside sprites
            for spr in seg.sprites:
                sx = sn + (spr['offset'] / HALF_ROAD) * wn
                sy = yn
                sc = scn
                self._draw_sprite(surf, spr, sx, sy, sc, dn)

            if seg.has_checkpoint and not seg.solved:
                self._draw_traffic_light(surf, sn + wn * 1.12, yn, scn, seg.light_state)

    def _draw_sprite(self, surf, spr, sx, sy, scale, depth):
        if depth > 0.88: return # Increased culling depth for distant mountains/trees
        t = spr['type']
        s = scale
        if t == 'pine': self._draw_pine(surf, sx, sy, s * spr['scale'])
        elif t == 'tree': self._draw_tree(surf, sx, sy, s * spr['scale'])
        elif t == 'blue_pine': self._draw_blue_pine(surf, sx, sy, s * spr['scale'])
        elif t == 'broadleaf': self._draw_broadleaf(surf, sx, sy, s * spr['scale'])
        elif t == 'bush': self._draw_bush(surf, sx, sy, s * spr['scale'])
        elif t == 'rock': self._draw_rock(surf, sx, sy, s * spr['scale'])
        elif t == 'sign_curve': self._draw_sign_curve(surf, sx, sy, s, spr['curve_dir'])
        elif t == 'sign_speed': self._draw_sign_speed(surf, sx, sy, s, spr['speed'])
        elif t == 'sign_exit': self._draw_sign_exit(surf, sx, sy, s)
        elif t == 'streetlight': self._draw_streetlight(surf, sx, sy, s)
        elif t == 'reflector_post': self._draw_reflector_post(surf, sx, sy, s)
        elif t == 'utility_pole': self._draw_utility_pole(surf, sx, sy, s)
        elif t == 'house': self._draw_house(surf, sx, sy, s * spr['scale'], spr.get('variant', 0), spr.get('side', -1))
        elif t == 'bhutan_house': self._draw_bhutan_house(surf, sx, sy, s * spr['scale'], spr.get('variant', 0), spr.get('side', -1))
        elif t == 'farmhouse': self._draw_bhutan_house(surf, sx, sy, s * spr['scale'] * 1.2, spr.get('variant', 0), spr.get('side', -1))
        elif t == 'tea_stall': self._draw_tea_stall(surf, sx, sy, s * spr['scale'], spr.get('variant', 0), spr.get('side', -1))
        elif t == 'fruit_stall': self._draw_fruit_stall(surf, sx, sy, s * spr['scale'], spr.get('variant', 0), spr.get('side', -1))
        elif t == 'craft_shop': self._draw_craft_shop(surf, sx, sy, s * spr['scale'], spr.get('variant', 0), spr.get('side', -1))
        elif t == 'general_store': self._draw_general_store(surf, sx, sy, s * spr['scale'], spr.get('variant', 0), spr.get('side', -1))
        elif t == 'restaurant': self._draw_restaurant(surf, sx, sy, s * spr['scale'], spr.get('variant', 0), spr.get('side', -1))
        elif t == 'urban_shop': self._draw_urban_shop(surf, sx, sy, s * spr['scale'], spr.get('variant', 0), spr.get('side', -1))
        elif t == 'bus_stop': self._draw_bus_stop(surf, sx, sy, s * spr['scale'])
        elif t == 'rice_field': self._draw_rice_field(surf, sx, sy, s * spr['scale'])
        elif t == 'chorten': self._draw_chorten(surf, sx, sy, s * spr['scale'])
        elif t == 'prayer_flags': self._draw_prayer_flags(surf, sx, sy, s * spr['scale'])
        elif t == 'stone_wall': self._draw_stone_wall(surf, sx, sy, s * spr['scale'])
        elif t == 'wooden_fence': self._draw_wooden_fence(surf, sx, sy, s * spr['scale'])
        elif t == 'warehouse': self._draw_warehouse(surf, sx, sy, s * spr['scale'])
        elif t == 'gas_station': self._draw_gas_station(surf, sx, sy, s * spr['scale'])
        elif t == 'shop': self._draw_shop(surf, sx, sy, s * spr['scale'])
        elif t == 'bridge_railing': self._draw_bridge_railing(surf, sx, sy, s)

    def _draw_pine(self, surf, sx, sy, scale):
        trunk_h = max(2, int(7 * scale))
        pygame.draw.rect(surf, (95, 65, 42), (sx - max(1, int(2*scale)), sy - trunk_h, max(2, int(5*scale)), trunk_h))
        h = max(7, int(38 * scale)); w = max(5, int(22 * scale)); top_y = sy - trunk_h - h
        for i, frac in enumerate((1.0, 0.7, 0.4)):
            tier_w = w * frac; tier_y = top_y + h * (1 - frac) * 0.85
            col = (48, 125, 62) if i % 2 == 0 else (62, 145, 75)
            pygame.draw.polygon(surf, col, [(sx, tier_y), (sx - tier_w/2, tier_y + h*0.4), (sx + tier_w/2, tier_y + h*0.4)])

    def _draw_blue_pine(self, surf, sx, sy, scale):
        trunk_h = max(10, int(60 * scale))
        trunk_w = max(3, int(8 * scale))
        pygame.draw.rect(surf, (70, 50, 35), (sx - trunk_w//2, sy - trunk_h, trunk_w, trunk_h))
        
        h = max(40, int(120 * scale))
        w = max(20, int(60 * scale))
        top_y = sy - trunk_h - h
        
        for i in range(5):
            t = i / 4.0
            layer_w = w * (1.0 - t * 0.6)
            layer_y = top_y + h * t
            layer_h = h * 0.35
            col = (35, 75, 55) if i % 2 == 0 else (45, 90, 65)
            pygame.draw.polygon(surf, col, [
                (sx, layer_y), 
                (sx - layer_w, layer_y + layer_h), 
                (sx + layer_w, layer_y + layer_h)
            ])

    def _draw_broadleaf(self, surf, sx, sy, scale):
        trunk_h = max(8, int(35 * scale))
        trunk_w = max(2, int(6 * scale))
        pygame.draw.rect(surf, (85, 60, 40), (sx - trunk_w//2, sy - trunk_h, trunk_w, trunk_h))
        
        r = max(15, int(45 * scale))
        cy_base = sy - trunk_h - r * 0.6
        pygame.draw.circle(surf, (50, 105, 55), (int(sx - r*0.4), int(cy_base)), int(r * 0.8))
        pygame.draw.circle(surf, (60, 120, 65), (int(sx + r*0.4), int(cy_base)), int(r * 0.7))
        pygame.draw.circle(surf, (70, 135, 75), (int(sx), int(cy_base - r*0.4)), int(r * 0.9))

    def _draw_tree(self, surf, sx, sy, scale):
        trunk_h = max(2, int(16 * scale)); trunk_w = max(1, int(5 * scale))
        pygame.draw.rect(surf, (105, 72, 45), (sx - trunk_w//2, sy - trunk_h, trunk_w, trunk_h))
        r = max(3, int(18 * scale))
        pygame.draw.circle(surf, (58, 145, 68), (int(sx), int(sy - trunk_h - r*0.55)), r)
        pygame.draw.circle(surf, (72, 162, 78), (int(sx - r*0.3), int(sy - trunk_h - r*0.85)), int(r*0.65))

    def _draw_bush(self, surf, sx, sy, scale):
        r = max(2, int(11 * scale))
        pygame.draw.circle(surf, (55, 132, 62), (int(sx), int(sy - r*0.6)), r)
        pygame.draw.circle(surf, (68, 150, 74), (int(sx - r*0.4), int(sy - r*0.9)), int(r*0.7))
        pygame.draw.circle(surf, (85, 168, 90), (int(sx + r*0.35), int(sy - r*0.8)), int(r*0.6))

    def _draw_rock(self, surf, sx, sy, scale):
        w = max(3, int(10 * scale)); h = max(2, int(6 * scale))
        pygame.draw.polygon(surf, (150, 150, 155), [(sx - w, sy), (sx - w*0.3, sy - h), (sx + w*0.5, sy - h*0.8), (sx + w, sy)])

    def _draw_sign_curve(self, surf, sx, sy, scale, direction):
        w = max(5, int(18 * scale)); h = max(6, int(22 * scale))
        pygame.draw.rect(surf, (255, 210, 60), (sx - w, sy - h*2.2, w*2, h), border_radius=max(2, int(3*scale)))
        pygame.draw.rect(surf, (30, 30, 35), (sx - w, sy - h*2.2, w*2, h), max(1, int(1.5*scale)), border_radius=max(2, int(3*scale)))
        if direction == 'left': pygame.draw.polygon(surf, (30, 30, 35), [(sx + w*0.5, sy - h*2.0), (sx - w*0.3, sy - h*1.6), (sx + w*0.5, sy - h*1.2)])
        else: pygame.draw.polygon(surf, (30, 30, 35), [(sx - w*0.5, sy - h*2.0), (sx + w*0.3, sy - h*1.6), (sx - w*0.5, sy - h*1.2)])

    def _draw_sign_speed(self, surf, sx, sy, scale, speed):
        w = max(5, int(16 * scale)); h = max(6, int(20 * scale))
        pygame.draw.rect(surf, (255, 255, 255), (sx - w, sy - h*2.2, w*2, h), border_radius=max(2, int(3*scale)))
        pygame.draw.rect(surf, (200, 50, 50), (sx - w, sy - h*2.2, w*2, h), max(1, int(2*scale)), border_radius=max(2, int(3*scale)))
        if scale > 0.35:
            font = pygame.font.Font(None, max(10, int(14 * scale)))
            txt = font.render(str(speed), True, (30, 30, 35))
            surf.blit(txt, (sx - txt.get_width()//2, int(sy - h*1.9)))

    def _draw_sign_exit(self, surf, sx, sy, scale):
        w = max(6, int(20 * scale)); h = max(5, int(16 * scale))
        pygame.draw.rect(surf, (50, 100, 60), (sx - w, sy - h*2.2, w*2, h), border_radius=max(2, int(3*scale)))
        pygame.draw.rect(surf, (255, 255, 255), (sx - w, sy - h*2.2, w*2, h), max(1, int(1.5*scale)), border_radius=max(2, int(3*scale)))
        if scale > 0.35:
            font = pygame.font.Font(None, max(9, int(12 * scale)))
            txt = font.render("EXIT", True, (255, 255, 255))
            surf.blit(txt, (sx - txt.get_width()//2, int(sy - h*1.9)))

    def _draw_streetlight(self, surf, sx, sy, scale):
        h = max(10, int(45 * scale))
        pygame.draw.line(surf, (115, 115, 125), (sx, sy), (sx, sy - h), max(1, int(2.5*scale)))
        pygame.draw.ellipse(surf, (255, 250, 220), (sx - 5*scale, sy - h - 4*scale, 10*scale, 6*scale))

    def _draw_reflector_post(self, surf, sx, sy, scale):
        h = max(4, int(12 * scale))
        pygame.draw.line(surf, (180, 180, 185), (sx, sy - h), (sx, sy), max(1, int(2*scale)))
        pygame.draw.circle(surf, (255, 255, 255), (int(sx), int(sy - h)), max(1, int(2.5*scale)))

    def _draw_utility_pole(self, surf, sx, sy, scale):
        h = max(15, int(70 * scale))
        pygame.draw.line(surf, (125, 115, 95), (sx, sy), (sx, sy - h), max(1, int(3*scale)))
        pygame.draw.line(surf, (125, 115, 95), (sx - 8*scale, sy - h*0.75), (sx + 8*scale, sy - h*0.75), max(1, int(2*scale)))

    def _draw_house(self, surf, sx, sy, scale, variant=0, side=-1):
        w = max(30, int(80 * scale)); h = max(25, int(60 * scale))
        walls = [(200, 190, 175), (210, 200, 180), (190, 180, 170)][variant % 3]
        roofs = [(165, 75, 55), (120, 90, 70), (95, 100, 110)][variant % 3]
        pygame.draw.ellipse(surf, (70, 110, 60), (sx - w - 6, sy - 4, w * 2 + 12, 8))
        body = pygame.Rect(sx - w, sy - h, w * 2, h)
        pygame.draw.rect(surf, walls, body)
        pygame.draw.rect(surf, (120, 110, 100), body, max(1, int(2 * scale)))
        pygame.draw.polygon(surf, roofs, [(sx - w - 6, sy - h), (sx, sy - h * 1.5), (sx + w + 6, sy - h)])
        for i in range(2):
            wx = sx - w * 0.6 + i * w * 0.8
            pygame.draw.rect(surf, (130, 170, 205), (wx, sy - h * 0.65, w * 0.3, h * 0.3))
            pygame.draw.rect(surf, (90, 120, 150), (wx, sy - h * 0.65, w * 0.3, h * 0.3), 1)
        pygame.draw.rect(surf, (110, 70, 45), (sx - w * 0.15, sy - h * 0.45, w * 0.3, h * 0.45))
        dirn = -side
        dw_len = max(12, int(34 * scale))
        dx0 = sx + dirn * w; dx1 = sx + dirn * (w + dw_len)
        pygame.draw.rect(surf, (150, 150, 150), (min(dx0, dx1), sy - max(2, int(4 * scale)), abs(dx1 - dx0), max(3, int(6 * scale))))
        pygame.draw.line(surf, (170, 160, 140), (sx - w, sy), (sx - w - max(6, int(16 * scale)), sy), max(1, int(2 * scale)))

    def _draw_bhutan_house(self, surf, sx, sy, scale, variant=0, side=-1):
        w = max(40, int(90 * scale))
        h = max(30, int(70 * scale))
        
        walls = [(245, 240, 230), (235, 230, 220), (250, 245, 235)][variant % 3]
        body = pygame.Rect(sx - w, sy - h, w * 2, h)
        pygame.draw.rect(surf, walls, body)
        
        trim_col = (120, 35, 25) if variant % 2 == 0 else (140, 90, 40)
        pygame.draw.rect(surf, trim_col, (sx - w, sy - h, w * 2, max(2, int(5 * scale))))
        pygame.draw.rect(surf, trim_col, (sx - w, sy - max(2, int(4 * scale)), w * 2, max(2, int(4 * scale))))
        
        roof_col = (70, 45, 30)
        roof_h = max(15, int(30 * scale))
        pygame.draw.polygon(surf, roof_col, [
            (sx - w - 5, sy - h), 
            (sx, sy - h - roof_h), 
            (sx + w + 5, sy - h)
        ])
        pygame.draw.polygon(surf, trim_col, [
            (sx - w - 5, sy - h), 
            (sx, sy - h - roof_h), 
            (sx + w + 5, sy - h)
        ], width=max(1, int(2 * scale)))
        
        win_w = max(6, int(16 * scale))
        win_h = max(8, int(22 * scale))
        num_win = 3 if scale > 0.6 else 2
        spacing = (w * 2) / (num_win + 1)
        
        for i in range(num_win):
            wx = sx - w + spacing * (i + 1) - win_w // 2
            wy = sy - h + max(8, int(15 * scale))
            pygame.draw.rect(surf, (60, 35, 20), (wx - 2, wy - 2, win_w + 4, win_h + 4))
            pygame.draw.rect(surf, (80, 110, 140), (wx, wy, win_w, win_h))
            pygame.draw.line(surf, (60, 35, 20), (wx + win_w//2, wy), (wx + win_w//2, wy + win_h), 1)
            pygame.draw.line(surf, (60, 35, 20), (wx, wy + win_h//2), (wx + win_w, wy + win_h//2), 1)
            
        dw = max(8, int(20 * scale))
        dh = max(12, int(35 * scale))
        pygame.draw.rect(surf, (90, 50, 30), (sx - dw//2, sy - dh, dw, dh))

    def _draw_tea_stall(self, surf, sx, sy, scale, variant=0, side=-1):
        w = max(25, int(60 * scale))
        h = max(20, int(45 * scale))
        pygame.draw.rect(surf, (210, 200, 180), (sx - w, sy - h, w * 2, h))
        
        awning_cols = [(200, 50, 40), (40, 110, 180), (220, 160, 30)]
        awning_col = awning_cols[variant % 3]
        awning_h = max(6, int(15 * scale))
        pygame.draw.polygon(surf, awning_col, [
            (sx - w - 5, sy - h),
            (sx + w + 5, sy - h),
            (sx + w + 5, sy - h + awning_h),
            (sx - w - 5, sy - h + awning_h)
        ])
        for i in range(4):
            sc_x = sx - w + (w * 2) * (i + 0.5) / 4
            pygame.draw.circle(surf, awning_col, (int(sc_x), int(sy - h + awning_h)), max(2, int(5 * scale)))
            
        table_w = max(15, int(40 * scale))
        table_h = max(6, int(15 * scale))
        pygame.draw.rect(surf, (110, 75, 45), (sx - table_w, sy - h + max(10, int(20 * scale)), table_w * 2, table_h))
        
        if scale > 0.4:
            pygame.draw.rect(surf, (180, 40, 40), (sx - 5*scale, sy - h + max(10, int(20 * scale)) - 6*scale, 4*scale, 6*scale))
            for i in range(3):
                cx = sx + i * 5 * scale
                pygame.draw.rect(surf, (240, 240, 240), (cx, sy - h + max(10, int(20 * scale)) - 3*scale, 3*scale, 3*scale))
                
        bench_y = sy - max(4, int(10 * scale))
        pygame.draw.rect(surf, (90, 60, 40), (sx - w * 0.8, bench_y, w * 1.6, max(2, int(4 * scale))))

    def _draw_fruit_stall(self, surf, sx, sy, scale, variant=0, side=-1):
        w = max(20, int(50 * scale))
        h = max(15, int(35 * scale))
        pygame.draw.polygon(surf, (120, 80, 50), [
            (sx - w, sy), (sx - w*0.8, sy - h), (sx + w*0.8, sy - h), (sx + w, sy)
        ])
        
        um_col = [(220, 60, 50), (50, 150, 80), (240, 180, 40)][variant % 3]
        um_h = max(15, int(40 * scale))
        um_w = max(25, int(60 * scale))
        pygame.draw.line(surf, (60, 60, 60), (sx, sy - h), (sx, sy - h - um_h), max(1, int(2 * scale)))
        pygame.draw.polygon(surf, um_col, [
            (sx - um_w, sy - h - um_h + max(5, int(10*scale))),
            (sx, sy - h - um_h),
            (sx + um_w, sy - h - um_h + max(5, int(10*scale)))
        ])
        
        if scale > 0.3:
            fruit_cols = [(255, 50, 50), (255, 200, 0), (255, 120, 0), (150, 200, 50)]
            for i in range(8):
                fx = sx - w * 0.6 + (_hash01(int(sx + i * 11)) - 0.5) * 4 * scale + (i % 4) * (w * 1.2 / 4)
                fy = sy - h + max(3, int(8 * scale)) + (i // 4) * max(4, int(10 * scale))
                pygame.draw.circle(surf, fruit_cols[i % 4], (int(fx), int(fy)), max(2, int(5 * scale)))

    def _draw_craft_shop(self, surf, sx, sy, scale, variant=0, side=-1):
        w = max(35, int(80 * scale))
        h = max(30, int(65 * scale))
        pygame.draw.rect(surf, (230, 220, 200), (sx - w, sy - h, w * 2, h))
        pygame.draw.rect(surf, (100, 50, 30), (sx - w, sy - h, w * 2, max(3, int(6 * scale))))
        
        win_w = w * 1.4
        win_h = h * 0.5
        pygame.draw.rect(surf, (150, 180, 200), (sx - win_w//2, sy - h + max(8, int(15*scale)), win_w, win_h))
        pygame.draw.rect(surf, (180, 40, 40), (sx - win_w//2 + 5*scale, sy - h + max(12, int(20*scale)), 10*scale, 15*scale))
        pygame.draw.circle(surf, (220, 180, 50), (int(sx + 8*scale), int(sy - h + max(20, int(35*scale)))), max(3, int(8*scale)))
        
        pygame.draw.polygon(surf, (60, 40, 25), [
            (sx - w - 5, sy - h), (sx, sy - h - max(10, int(25*scale))), (sx + w + 5, sy - h)
        ])

    def _draw_general_store(self, surf, sx, sy, scale, variant=0, side=-1):
        w = max(40, int(95 * scale))
        h = max(35, int(80 * scale))
        pygame.draw.rect(surf, (210, 200, 185), (sx - w, sy - h, w * 2, h))
        pygame.draw.polygon(surf, (110, 115, 120), [
            (sx - w - 5, sy - h), (sx, sy - h - max(12, int(30*scale))), (sx + w + 5, sy - h)
        ])
        pygame.draw.rect(surf, (40, 80, 140), (sx - w*0.8, sy - h + max(5, int(12*scale)), w*1.6, max(8, int(18*scale))))
        pygame.draw.rect(surf, (70, 45, 30), (sx - max(6, int(15*scale)), sy - max(15, int(35*scale)), max(12, int(30*scale)), max(15, int(35*scale))))
        for side_win in [-1, 1]:
            wx = sx + side_win * w * 0.6
            pygame.draw.rect(surf, (140, 170, 190), (wx - max(5, int(12*scale)), sy - h + max(25, int(45*scale)), max(10, int(24*scale)), max(12, int(28*scale))))
        if scale > 0.4:
            for i in range(3):
                bx = sx - w*0.7 + i * 15 * scale
                by = sy - max(4, int(10*scale))
                pygame.draw.rect(surf, (180, 150, 90), (bx, by - 8*scale, 10*scale, 8*scale))

    def _draw_restaurant(self, surf, sx, sy, scale, variant=0, side=-1):
        w = max(45, int(100 * scale))
        h = max(35, int(85 * scale))
        pygame.draw.rect(surf, (225, 215, 195), (sx - w, sy - h, w * 2, h))
        pygame.draw.rect(surf, (110, 40, 30), (sx - w, sy - h, w * 2, max(4, int(8 * scale))))
        pygame.draw.rect(surf, (110, 40, 30), (sx - w, sy - h//2, w * 2, max(2, int(4 * scale))))
        
        for i in range(3):
            wx = sx - w * 0.7 + i * (w * 1.4 / 3)
            wy = sy - h + max(15, int(35 * scale))
            pygame.draw.rect(surf, (90, 130, 160), (wx, wy, max(12, int(25 * scale)), max(15, int(35 * scale))))
            pygame.draw.rect(surf, (110, 40, 30), (wx, wy, max(12, int(25 * scale)), max(15, int(35 * scale))), max(1, int(2*scale)))
            
        pygame.draw.polygon(surf, (50, 35, 25), [
            (sx - w - 10, sy - h), (sx, sy - h - max(15, int(35 * scale))), (sx + w + 10, sy - h)
        ])
        if scale > 0.4:
            for i in range(2):
                tx = sx + (i - 0.5) * w * 0.8
                ty = sy - max(4, int(10 * scale))
                pygame.draw.rect(surf, (160, 160, 165), (tx - 6*scale, ty - 6*scale, 12*scale, 6*scale))
                pygame.draw.line(surf, (80, 80, 80), (tx, ty), (tx, ty + 6*scale), max(1, int(2*scale)))

    def _draw_urban_shop(self, surf, sx, sy, scale, variant=0, side=-1):
        w = max(45, int(110 * scale))
        h = max(50, int(120 * scale))
        pygame.draw.rect(surf, (200, 195, 185), (sx - w, sy - h, w * 2, h))
        
        for floor in range(3):
            fy = sy - h + floor * (h / 3)
            pygame.draw.line(surf, (120, 115, 105), (sx - w, fy), (sx + w, fy), max(1, int(2*scale)))
            for i in range(4):
                wx = sx - w * 0.8 + i * (w * 1.6 / 4)
                pygame.draw.rect(surf, (100, 140, 170), (wx, fy + max(5, int(12*scale)), max(10, int(20*scale)), max(12, int(25*scale))))
                
        pygame.draw.rect(surf, (40, 80, 130), (sx - w, sy - max(20, int(45*scale)), w * 2, max(20, int(45*scale))))
        pygame.draw.rect(surf, (220, 50, 40), (sx - w*0.9, sy - max(25, int(55*scale)), w*1.8, max(6, int(12*scale))))
        pygame.draw.polygon(surf, (80, 85, 90), [
            (sx - w - 5, sy - h), (sx, sy - h - max(10, int(25*scale))), (sx + w + 5, sy - h)
        ])

    def _draw_bus_stop(self, surf, sx, sy, scale):
        w = max(25, int(60 * scale))
        h = max(25, int(60 * scale))
        pygame.draw.rect(surf, (200, 205, 210), (sx - w, sy - h, w * 2, h))
        pygame.draw.polygon(surf, (70, 75, 80), [
            (sx - w - 5, sy - h), (sx + w + 5, sy - h), (sx + w + 5, sy - h + 5), (sx - w - 5, sy - h + 5)
        ])
        bench_y = sy - max(8, int(20 * scale))
        pygame.draw.rect(surf, (140, 100, 60), (sx - w * 0.8, bench_y, w * 1.6, max(3, int(8 * scale))))
        pygame.draw.rect(surf, (40, 120, 180), (sx - w * 0.4, sy - h + max(5, int(12 * scale)), w * 0.8, max(8, int(18 * scale))))
        if scale > 0.4:
            pygame.draw.rect(surf, (240, 240, 240), (sx - w * 0.3, sy - h + max(8, int(16 * scale)), w * 0.6, max(4, int(10 * scale))))

    def _draw_rice_field(self, surf, sx, sy, scale):
        w = max(60, int(150 * scale))
        h = max(20, int(50 * scale))
        for i in range(4):
            t_y = sy - i * (h / 4)
            t_w = w * (1.0 - i * 0.1)
            col = (110, 160, 70) if i % 2 == 0 else (130, 180, 85)
            pygame.draw.polygon(surf, col, [
                (sx - t_w, t_y), (sx + t_w, t_y),
                (sx + t_w * 0.9, t_y - h/4), (sx - t_w * 0.9, t_y - h/4)
            ])
            pygame.draw.line(surf, (90, 80, 60), (sx - t_w, t_y), (sx + t_w, t_y), max(1, int(2*scale)))

    def _draw_chorten(self, surf, sx, sy, scale):
        w = max(20, int(45 * scale))
        h = max(10, int(25 * scale))
        for i in range(3):
            bw = w * (1.0 - i * 0.2)
            by = sy - i * (h / 3)
            pygame.draw.rect(surf, (235, 235, 235), (sx - bw, by - h/3, bw * 2, h/3))
            pygame.draw.rect(surf, (180, 40, 30), (sx - bw, by - h/3, bw * 2, max(1, int(2*scale))))
            
        dome_r = max(10, int(25 * scale))
        dome_y = sy - h
        pygame.draw.circle(surf, (245, 245, 245), (int(sx), int(dome_y - dome_r * 0.8)), dome_r)
        
        hw = max(6, int(15 * scale))
        hh = max(6, int(15 * scale))
        pygame.draw.rect(surf, (235, 235, 235), (sx - hw, dome_y - dome_r * 1.6 - hh, hw * 2, hh))
        pygame.draw.circle(surf, (30, 30, 30), (int(sx - hw*0.4), int(dome_y - dome_r * 1.6 - hh*0.5)), max(1, int(2*scale)))
        pygame.draw.circle(surf, (30, 30, 30), (int(sx + hw*0.4), int(dome_y - dome_r * 1.6 - hh*0.5)), max(1, int(2*scale)))
        
        spire_h = max(15, int(35 * scale))
        spire_y = dome_y - dome_r * 1.6 - hh
        pygame.draw.polygon(surf, (220, 180, 50), [
            (sx - hw * 0.8, spire_y), (sx + hw * 0.8, spire_y), (sx, spire_y - spire_h)
        ])
        for i in range(4):
            ry = spire_y - (spire_h * (i + 1) / 5)
            rw = hw * 0.8 * (1.0 - (i + 1) / 5)
            pygame.draw.line(surf, (180, 140, 30), (sx - rw, ry), (sx + rw, ry), max(1, int(2*scale)))

    def _draw_prayer_flags(self, surf, sx, sy, scale):
        pole_h = max(20, int(60 * scale))
        pygame.draw.line(surf, (80, 60, 40), (sx - 15*scale, sy), (sx - 15*scale, sy - pole_h), max(1, int(2*scale)))
        pygame.draw.line(surf, (80, 60, 40), (sx + 15*scale, sy), (sx + 15*scale, sy - pole_h), max(1, int(2*scale)))
        pygame.draw.line(surf, (50, 50, 50), (sx - 15*scale, sy - pole_h + 5*scale), (sx + 15*scale, sy - pole_h + 5*scale), 1)
        
        flag_cols = [(50, 100, 180), (240, 240, 240), (200, 50, 40), (60, 150, 70), (220, 190, 50)]
        flag_w = max(4, int(10 * scale))
        flag_h = max(6, int(15 * scale))
        num_flags = 5
        spacing = (30 * scale) / num_flags
        
        for i in range(num_flags):
            fx = sx - 15*scale + spacing * (i + 0.5)
            fy = sy - pole_h + 5*scale
            pygame.draw.polygon(surf, flag_cols[i % 5], [
                (fx, fy), (fx + flag_w, fy), (fx + flag_w, fy + flag_h), (fx, fy + flag_h)
            ])

    def _draw_stone_wall(self, surf, sx, sy, scale):
        w = max(40, int(100 * scale))
        h = max(10, int(25 * scale))
        pygame.draw.rect(surf, (130, 130, 135), (sx - w, sy - h, w * 2, h))
        if scale > 0.3:
            for i in range(4):
                ry = sy - h + i * (h / 4)
                pygame.draw.line(surf, (100, 100, 105), (sx - w, ry), (sx + w, ry), 1)
            for i in range(10):
                rx = sx - w + _hash01(int(sx + i * 31)) * w * 2
                ry = sy - h + _hash01(int(sy + i * 17)) * h
                pygame.draw.rect(surf, (110, 110, 115), (rx, ry, max(4, 8*scale), max(3, 5*scale)))
        pygame.draw.line(surf, (90, 140, 70), (sx - w, sy - h), (sx + w, sy - h), max(1, int(2*scale)))

    def _draw_wooden_fence(self, surf, sx, sy, scale):
        w = max(40, int(100 * scale))
        h = max(12, int(30 * scale))
        pygame.draw.line(surf, (110, 80, 50), (sx - w, sy - h * 0.7), (sx + w, sy - h * 0.7), max(1, int(3*scale)))
        pygame.draw.line(surf, (110, 80, 50), (sx - w, sy - h * 0.3), (sx + w, sy - h * 0.3), max(1, int(3*scale)))
        num_posts = 6
        spacing = (w * 2) / num_posts
        for i in range(num_posts + 1):
            px = sx - w + i * spacing
            pygame.draw.line(surf, (90, 65, 40), (px, sy), (px, sy - h), max(1, int(3*scale)))

    def _draw_warehouse(self, surf, sx, sy, scale):
        w = max(30, int(90 * scale)); h = max(20, int(60 * scale))
        pygame.draw.ellipse(surf, (70, 110, 60), (sx - w - 6, sy - 4, w * 2 + 12, 8))
        body = pygame.Rect(sx - w, sy - h, w * 2, h)
        pygame.draw.rect(surf, (165, 165, 170), body)
        pygame.draw.rect(surf, (120, 120, 125), body, max(1, int(2 * scale)))
        for i in range(3):
            pygame.draw.rect(surf, (80, 80, 85), (sx - w + 10 + i * (w * 2 - 20) / 3, sy - h * 0.6, w * 0.4, h * 0.6))

    def _draw_gas_station(self, surf, sx, sy, scale):
        w = max(30, int(80 * scale)); h = max(15, int(40 * scale))
        pygame.draw.ellipse(surf, (70, 110, 60), (sx - w - 6, sy - 4, w * 2 + 12, 8))
        pygame.draw.rect(surf, (225, 220, 210), (sx - w, sy - h * 1.5, w * 2, h * 0.2))
        pygame.draw.rect(surf, (150, 150, 150), (sx - w * 0.8, sy - h * 1.3, w * 0.1, h * 1.3))
        pygame.draw.rect(surf, (150, 150, 150), (sx + w * 0.7, sy - h * 1.3, w * 0.1, h * 1.3))
        pygame.draw.rect(surf, (200, 55, 45), (sx - w * 0.4, sy - h * 0.8, w * 0.2, h * 0.8))
        pygame.draw.rect(surf, (200, 55, 45), (sx + w * 0.2, sy - h * 0.8, w * 0.2, h * 0.8))
        pygame.draw.rect(surf, (180, 170, 150), (sx - w * 0.5, sy - h, w, h))

    def _draw_shop(self, surf, sx, sy, scale):
        w = max(20, int(50 * scale)); h = max(15, int(35 * scale))
        pygame.draw.ellipse(surf, (70, 110, 60), (sx - w - 6, sy - 4, w * 2 + 12, 8))
        pygame.draw.rect(surf, (210, 200, 185), (sx - w, sy - h, w * 2, h))
        pygame.draw.rect(surf, (85, 125, 165), (sx - w * 0.8, sy - h * 0.5, w * 1.6, h * 0.3))
        pygame.draw.line(surf, (140, 130, 120), (sx, sy - h), (sx, sy), max(1, int(1.5 * scale)))

    def _draw_bridge_railing(self, surf, sx, sy, scale):
        h = max(4, int(14 * scale))
        pygame.draw.line(surf, (160, 160, 168), (sx, sy - h), (sx, sy), max(1, int(3 * scale)))
        pygame.draw.line(surf, (140, 140, 148), (sx - 4 * scale, sy - h), (sx + 4 * scale, sy - h), max(1, int(2 * scale)))

    def _draw_traffic_light(self, surf, sx, sy, scale, state):
        pole_h = max(12, int(70 * scale))
        pygame.draw.line(surf, (70, 74, 80), (sx, sy), (sx, sy - pole_h), max(1, int(3.5 * scale)))
        box_w = max(6, int(18 * scale)); box_h = max(7, int(30 * scale))
        box = pygame.Rect(sx - box_w / 2, sy - pole_h - box_h + 4, box_w, box_h)
        pygame.draw.rect(surf, (40, 43, 48), box, border_radius=max(2, int(4 * scale)))
        r_rad = max(2, int(box_w * 0.28))
        pygame.draw.circle(surf, (250, 60, 50) if state == "red" else (90, 40, 40), (int(sx), int(box.y + box_h * 0.3)), r_rad)
        pygame.draw.circle(surf, (60, 220, 90) if state == "green" else (45, 85, 55), (int(sx), int(box.y + box_h * 0.72)), r_rad)


# ==========================================
# VEHICLE BASE
# ==========================================
class Vehicle:
    def __init__(self, x, z, speed, color, car_type="sedan"):
        self.x = x; self.z = z; self.y = 0; self.speed = speed
        self.color = color; self.car_type = car_type
        self.width = 360.0; self.length = 42.0
        self.bounce_t = 0.0; self.bounce = 0.0; self.braking = False

    def update_physics(self, dt, road):
        self.y = road.get_road_y(self.z)
        self.bounce_t += dt * (1.5 + self.speed / 70.0)
        self.bounce = math.sin(self.bounce_t * 5) * (1.2 if self.speed > 5 else 0.15)

    def draw_shadow(self, surf, cx, cy, scale):
        sh_w = max(5, int(36 * scale)); sh_h = max(3, int(14 * scale))
        shadow = pygame.Surface((sh_w * 2, sh_h * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (8, 12, 8, 85), (0, 0, sh_w * 2, sh_h * 2))
        surf.blit(shadow, (cx - sh_w, cy - sh_h // 2 + 2))

    def draw_rear(self, surf, cx, cy, scale, color_override=None, depth=0.0):
        if scale < 0.22: return
        col = color_override or self.color; s = scale * 1.7
        self.draw_shadow(surf, cx, cy, s)
        if self.car_type == "sedan": self._draw_sedan_rear(surf, cx, cy, s, col, depth)
        elif self.car_type == "suv": self._draw_suv_rear(surf, cx, cy, s, col, depth)
        elif self.car_type == "truck": self._draw_truck_rear(surf, cx, cy, s, col, depth)
        elif self.car_type == "van": self._draw_van_rear(surf, cx, cy, s, col, depth)
        elif self.car_type == "bus": self._draw_bus_rear(surf, cx, cy, s, col, depth)
        elif self.car_type == "motorcycle": self._draw_motorcycle_rear(surf, cx, cy, s, col, depth)
        else: self._draw_sedan_rear(surf, cx, cy, s, col, depth)

    def _draw_sedan_rear(self, surf, cx, cy, s, col, depth):
        body_w = max(10, int(44 * s)); body_h = max(6, int(26 * s))
        body = pygame.Rect(cx - body_w//2, cy - body_h, body_w, body_h)
        pygame.draw.rect(surf, col, body, border_radius=max(3, int(5*s)))
        pygame.draw.rect(surf, (22, 25, 28), body, max(1, int(2*s)), border_radius=max(3, int(5*s)))
        roof = pygame.Rect(cx - body_w//3, cy - body_h + 2, body_w*2//3, max(4, int(10*s)))
        pygame.draw.rect(surf, (48, 58, 70), roof, border_radius=max(2, int(3*s)))
        glow = pygame.Surface((body_w * 2 + 10, body_h + 10), pygame.SRCALPHA)
        for side in (-1, 1):
            lx = cx + side * body_w * 0.38; ly = cy - body_h * 0.3
            pygame.draw.ellipse(glow, (255, 55, 35, 85), (int(lx - cx + body_w + 5 - 8*s), int(ly - cy + 5), int(16*s), int(12*s)))
            pygame.draw.circle(surf, (255, 55, 35), (int(lx), int(ly)), max(3, int(7*s)))
            pygame.draw.circle(surf, (255, 200, 180), (int(lx), int(ly)), max(2, int(3*s)))
        surf.blit(glow, (cx - body_w - 5, cy - 5))
        if self.braking:
            for side in (-1, 1):
                lx = cx + side * body_w * 0.38
                pygame.draw.circle(surf, (255, 255, 255), (int(lx), int(cy - body_h * 0.3)), max(2, int(4*s)))
        for side in (-1, 1):
            wx = cx + side * body_w * 0.44
            pygame.draw.circle(surf, (18, 18, 22), (int(wx), int(cy + 2)), max(3, int(8*s)))
            pygame.draw.circle(surf, (165, 165, 172), (int(wx), int(cy + 2)), max(2, int(3.5*s)))
        plate = pygame.Rect(cx - int(9*s), cy - 1, int(18*s), int(6*s))
        pygame.draw.rect(surf, (240, 235, 220), plate, border_radius=2)

    def _draw_suv_rear(self, surf, cx, cy, s, col, depth):
        body_w = max(12, int(50 * s)); body_h = max(8, int(32 * s))
        body = pygame.Rect(cx - body_w//2, cy - body_h, body_w, body_h)
        pygame.draw.rect(surf, col, body, border_radius=max(3, int(5*s)))
        pygame.draw.rect(surf, (22, 25, 28), body, max(1, int(2*s)), border_radius=max(3, int(5*s)))
        win = pygame.Rect(cx - body_w//3, cy - body_h + 3, body_w*2//3, max(5, int(12*s)))
        pygame.draw.rect(surf, (50, 60, 72), win, border_radius=max(2, int(3*s)))
        for side in (-1, 1):
            lx = cx + side * body_w * 0.38
            pygame.draw.circle(surf, (255, 55, 35), (int(lx), int(cy - body_h * 0.25)), max(3, int(7*s)))
            pygame.draw.circle(surf, (255, 200, 180), (int(lx), int(cy - body_h * 0.25)), max(2, int(3*s)))
        if self.braking:
            for side in (-1, 1):
                lx = cx + side * body_w * 0.38
                pygame.draw.circle(surf, (255, 255, 255), (int(lx), int(cy - body_h * 0.25)), max(2, int(4*s)))
        for side in (-1, 1):
            wx = cx + side * body_w * 0.44
            pygame.draw.circle(surf, (18, 18, 22), (int(wx), int(cy + 2)), max(4, int(9*s)))
            pygame.draw.circle(surf, (165, 165, 172), (int(wx), int(cy + 2)), max(2, int(4*s)))
        plate = pygame.Rect(cx - int(10*s), cy - 1, int(20*s), int(6*s))
        pygame.draw.rect(surf, (240, 235, 220), plate, border_radius=2)

    def _draw_truck_rear(self, surf, cx, cy, s, col, depth):
        box_w = max(12, int(50 * s)); box_h = max(8, int(34 * s))
        box = pygame.Rect(cx - box_w//2, cy - box_h, box_w, box_h)
        pygame.draw.rect(surf, (125, 90, 52), box, border_radius=max(2, int(4*s)))
        pygame.draw.rect(surf, (32, 28, 24), box, max(1, int(2*s)), border_radius=max(2, int(4*s)))
        for i in range(3):
            gx = box.x + 10 + i * (box.w - 20) / 2
            pygame.draw.line(surf, (92, 65, 35), (gx, box.y + 4), (gx, box.bottom - 4), max(1, int(2*s)))
        cab = pygame.Rect(cx - int(24*s), cy - int(10*s), int(48*s), int(16*s))
        pygame.draw.rect(surf, col, cab, border_radius=max(2, int(4*s)))
        pygame.draw.rect(surf, (25, 28, 32), cab, max(1, int(2*s)), border_radius=max(2, int(4*s)))
        for side in (-1, 1):
            lx = cx + side * int(16*s)
            pygame.draw.circle(surf, (255, 50, 30), (int(lx), int(cy - int(4*s))), max(3, int(7*s)))
            pygame.draw.circle(surf, (255, 200, 180), (int(lx), int(cy - int(4*s))), max(2, int(3*s)))
        if self.braking:
            for side in (-1, 1):
                lx = cx + side * int(16*s)
                pygame.draw.circle(surf, (255, 255, 255), (int(lx), int(cy - int(4*s))), max(2, int(4*s)))
        for side in (-1, 1):
            wx = cx + side * int(26*s)
            pygame.draw.circle(surf, (18, 18, 22), (int(wx), int(cy + int(7*s))), max(4, int(10*s)))
            pygame.draw.circle(surf, (170, 170, 178), (int(wx), int(cy + int(7*s))), max(2, int(4*s)))

    def _draw_van_rear(self, surf, cx, cy, s, col, depth):
        body_w = max(10, int(44 * s)); body_h = max(7, int(34 * s))
        body = pygame.Rect(cx - body_w//2, cy - body_h, body_w, body_h)
        pygame.draw.rect(surf, col, body, border_radius=max(2, int(4*s)))
        pygame.draw.rect(surf, (22, 25, 28), body, max(1, int(2*s)), border_radius=max(2, int(4*s)))
        win = pygame.Rect(cx - body_w//3, cy - body_h + 3, body_w*2//3, max(5, int(12*s)))
        pygame.draw.rect(surf, (52, 62, 75), win, border_radius=max(2, int(3*s)))
        for side in (-1, 1):
            lx = cx + side * body_w * 0.38
            pygame.draw.circle(surf, (255, 50, 30), (int(lx), int(cy - body_h * 0.22)), max(3, int(7*s)))
            pygame.draw.circle(surf, (255, 200, 180), (int(lx), int(cy - body_h * 0.22)), max(2, int(3*s)))
        if self.braking:
            for side in (-1, 1):
                lx = cx + side * body_w * 0.38
                pygame.draw.circle(surf, (255, 255, 255), (int(lx), int(cy - body_h * 0.22)), max(2, int(4*s)))
        for side in (-1, 1):
            wx = cx + side * body_w * 0.42
            pygame.draw.circle(surf, (18, 18, 22), (int(wx), int(cy + 2)), max(3, int(8*s)))
            pygame.draw.circle(surf, (165, 165, 172), (int(wx), int(cy + 2)), max(2, int(3.5*s)))
        plate = pygame.Rect(cx - int(10*s), cy - 1, int(20*s), int(6*s))
        pygame.draw.rect(surf, (240, 235, 220), plate, border_radius=2)

    def _draw_bus_rear(self, surf, cx, cy, s, col, depth):
        body_w = max(14, int(56 * s)); body_h = max(10, int(42 * s))
        body = pygame.Rect(cx - body_w//2, cy - body_h, body_w, body_h)
        pygame.draw.rect(surf, (225, 220, 210), body, border_radius=max(2, int(4*s)))
        pygame.draw.rect(surf, (25, 28, 32), body, max(1, int(2*s)), border_radius=max(2, int(4*s)))
        for i in range(4):
            wy = body.y + 6 + i * (body.h - 12) / 3
            pygame.draw.line(surf, (65, 105, 155), (body.x + 4, wy), (body.right - 4, wy), max(1, int(2*s)))
        for side in (-1, 1):
            lx = cx + side * body_w * 0.4
            pygame.draw.circle(surf, (255, 50, 30), (int(lx), int(cy - body_h * 0.15)), max(3, int(7*s)))
            pygame.draw.circle(surf, (255, 200, 180), (int(lx), int(cy - body_h * 0.15)), max(2, int(3*s)))
        if self.braking:
            for side in (-1, 1):
                lx = cx + side * body_w * 0.4
                pygame.draw.circle(surf, (255, 255, 255), (int(lx), int(cy - body_h * 0.15)), max(2, int(4*s)))
        for side in (-1, 1):
            wx = cx + side * body_w * 0.42
            pygame.draw.circle(surf, (18, 18, 22), (int(wx), int(cy + 3)), max(4, int(9*s)))
            pygame.draw.circle(surf, (165, 165, 172), (int(wx), int(cy + 3)), max(2, int(4*s)))

    def _draw_motorcycle_rear(self, surf, cx, cy, s, col, depth):
        body_w = max(4, int(14 * s)); body_h = max(3, int(12 * s))
        body = pygame.Rect(cx - body_w//2, cy - body_h, body_w, body_h)
        pygame.draw.rect(surf, col, body, border_radius=max(2, int(3*s)))
        pygame.draw.circle(surf, (255, 55, 35), (int(cx - body_w*0.6), int(cy - body_h*0.4)), max(2, int(4*s)))
        pygame.draw.circle(surf, (255, 55, 35), (int(cx + body_w*0.6), int(cy - body_h*0.4)), max(2, int(4*s)))
        pygame.draw.circle(surf, (18, 18, 22), (int(cx - body_w), int(cy + 1)), max(2, int(4*s)))
        pygame.draw.circle(surf, (18, 18, 22), (int(cx + body_w), int(cy + 1)), max(2, int(4*s)))


# ==========================================
# PLAYER VEHICLE
# ==========================================
class PlayerVehicle(Vehicle):
    def __init__(self):
        super().__init__(0, 0, 0, (52, 112, 62), "truck")
        self.max_speed = 300
        self.steer_angle = 0.0
        self.steer_target = 0.0
        self.steer_manual = False
        self.offroad = False
        self.crash_timer = 0.0
        self.suspension_y = 0.0
        self.distance_travelled = 0.0
        self._last_z = 0.0

    def handle_input(self, keys, dt, road):
        if keys[pygame.K_SPACE]:
            self.speed -= self.max_speed * 2.0 * dt
            self.braking = True
        elif keys[pygame.K_w] or keys[pygame.K_UP]:
            self.speed += ACCEL * dt
            self.braking = False
        elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.speed -= BRAKE * dt
            self.braking = True
        else:
            self.speed -= FRICTION * dt
            self.braking = False
        self.speed = max(-25, min(self.max_speed, self.speed))

        if not self.steer_manual:
            steer_input = 0.0
            if keys[pygame.K_a] or keys[pygame.K_LEFT]: steer_input = -1.0
            elif keys[pygame.K_d] or keys[pygame.K_RIGHT]: steer_input = 1.0
            if steer_input != 0:
                self.steer_target += steer_input * 3.2 * dt
                self.steer_target = max(-1.0, min(1.0, self.steer_target))
            else:
                self.steer_target *= max(0.0, 1.0 - STEER_RETURN * dt)

        self.steer_angle += (self.steer_target - self.steer_angle) * min(1.0, 9.0 * dt)

        speed_factor = min(1.0, self.speed / 90.0) if self.speed > 0 else 0
        self.x += self.steer_angle * STEER_SPEED * speed_factor * dt

        seg = road.find_segment(self.z)
        curve_force = seg.curve * self.speed * CENTRIFUGAL
        self.x -= curve_force * dt

        self.offroad = abs(self.x) > HALF_ROAD
        if self.offroad:
            self.speed -= OFFROAD_FRICTION * dt
            self.speed = max(0, self.speed)

        self.x = max(-HALF_ROAD * 1.6, min(HALF_ROAD * 1.6, self.x))

        if self.crash_timer > 0:
            self.crash_timer -= dt
            self.speed *= 0.96

        self.suspension_y = math.sin(self.bounce_t * 3) * 0.8

    def update(self, dt, road):
        if self.crash_timer <= 0:
            self.z += self.speed * dt
            
        dz = self.z - self._last_z
        if dz > 0:
            self.distance_travelled += dz
        self._last_z = self.z
        
        self.update_physics(dt, road)

    def draw(self, surf, road, camera_x, camera_y, camera_z, horizon_y, bottom_y, vp_x, bottom_half, width_mult, scale_mult):
        p = project_world(self.x, self.y + self.suspension_y, self.z, camera_x, camera_y, camera_z,
                          horizon_y, bottom_y, vp_x, bottom_half, width_mult, scale_mult)
        if p is None: return
        cx, cy, scale, depth = p
        cy += self.bounce
        s = scale * 1.9
        self.draw_shadow(surf, cx, cy, s)

        bed = pygame.Rect(cx - int(32*s), cy - int(44*s), int(64*s), int(36*s))
        pygame.draw.rect(surf, (130, 95, 55), bed, border_radius=max(3, int(5*s)))
        pygame.draw.rect(surf, (28, 26, 22), bed, max(1, int(2.5*s)), border_radius=max(3, int(5*s)))
        for i in range(4):
            gx = bed.x + 10 + i * (bed.w - 20) / 3
            pygame.draw.line(surf, (95, 68, 35), (gx, bed.y + 4), (gx, bed.bottom - 4), max(1, int(2*s)))
        for fx, fy, col in [(-16, -12, (210, 60, 50)), (-4, -16, (235, 150, 40)), (10, -12, (90, 170, 70)), (22, -16, (210, 60, 50))]:
            pygame.draw.circle(surf, col, (int(cx + fx*s), int(bed.y + fy*s)), max(3, int(8*s)))
            pygame.draw.circle(surf, tuple(min(255, c+45) for c in col), (int(cx + (fx-2)*s), int(bed.y + (fy-2)*s)), max(2, int(3.5*s)))
        cab = pygame.Rect(cx - int(24*s), cy - int(12*s), int(48*s), int(20*s))
        pygame.draw.rect(surf, self.color, cab, border_radius=max(3, int(5*s)))
        pygame.draw.rect(surf, (28, 26, 22), cab, max(1, int(2.5*s)), border_radius=max(3, int(5*s)))
        glow = pygame.Surface((int(60*s), int(35*s)), pygame.SRCALPHA)
        for wx in (cx - int(14*s), cx + int(14*s)):
            pygame.draw.ellipse(glow, (255, 45, 25, 95), (int(wx - cx + 30*s - 10*s), int(5*s), int(20*s), int(15*s)))
            pygame.draw.circle(surf, (255, 45, 25), (int(wx), int(cy - int(4*s))), max(3, int(6*s)))
            pygame.draw.circle(surf, (255, 210, 190), (int(wx), int(cy - int(4*s))), max(2, int(3*s)))
        surf.blit(glow, (cx - int(30*s), cy - int(20*s)))
        if self.braking:
            for wx in (cx - int(14*s), cx + int(14*s)):
                pygame.draw.circle(surf, (255, 255, 255), (int(wx), int(cy - int(4*s))), max(2, int(4*s)))
        for wx in (cx - int(26*s), cx + int(22*s)):
            pygame.draw.circle(surf, (18, 18, 22), (int(wx), int(cy + int(8*s))), max(4, int(11*s)))
            pygame.draw.circle(surf, (200, 200, 205), (int(wx), int(cy + int(8*s))), max(2, int(4.5*s)))
        plate = pygame.Rect(cx - int(12*s), cy + int(3*s), int(24*s), int(7*s))
        pygame.draw.rect(surf, (240, 235, 220), plate, border_radius=2)
        pygame.draw.rect(surf, (38, 78, 48), plate, 1, border_radius=2)
        if scale > 0.2:
            beam = pygame.Surface((int(90*s), int(55*s)), pygame.SRCALPHA)
            pygame.draw.ellipse(beam, (255, 250, 200, 22), (0, 0, int(90*s), int(55*s)))
            surf.blit(beam, (cx - int(45*s), cy - int(25*s)))


# ==========================================
# AI VEHICLE (same direction)
# ==========================================
class AIVehicle(Vehicle):
    def __init__(self, z, lane, speed, road):
        self.road = road
        self.lane = lane
        self.target_lane = lane
        self.lane_change_timer = random.uniform(3.0, 8.0)
        self.lane_change_duration = 1.5
        x = road.get_lane_x(lane, "player")
        car_types = ["sedan", "sedan", "suv", "suv", "truck", "van", "bus", "motorcycle"]
        colors = [(195, 50, 50), (50, 90, 195), (205, 180, 45), (160, 65, 175), (58, 165, 145), (220, 110, 40), (75, 75, 82), (180, 180, 185)]
        car_type = random.choice(car_types)
        super().__init__(x, z, speed, random.choice(colors), car_type)
        self.target_speed = speed
        if car_type == "truck": self.length = 50.0; self.width = 400.0; self.target_speed *= 0.75
        elif car_type == "bus": self.length = 55.0; self.width = 420.0; self.target_speed *= 0.7
        elif car_type == "motorcycle": self.length = 25.0; self.width = 180.0; self.target_speed *= 1.2
        elif car_type == "suv": self.length = 42.0; self.width = 380.0
        else: self.length = 38.0; self.width = 340.0
        self.braking_for_light = False
        self.lateral_offset = 0.0 
        self.target_lateral_offset = random.uniform(-40, 40)
        self.offset_timer = random.uniform(2, 5)

    def update(self, dt, road, player, all_cars):
        self.offset_timer -= dt
        if self.offset_timer <= 0:
            self.target_lateral_offset = random.uniform(-60, 60)
            self.offset_timer = random.uniform(3, 6)
        self.lateral_offset += (self.target_lateral_offset - self.lateral_offset) * 2.0 * dt

        self.lane_change_timer -= dt
        if self.lane_change_timer <= 0 and self.lane == self.target_lane:
            if random.random() < 0.1: 
                new_lane = self.lane + random.choice([-1, 1])
                if 0 <= new_lane < NUM_LANES:
                    self.target_lane = new_lane
                    self.lane_change_timer = self.lane_change_duration
                else: self.lane_change_timer = 2.0
            else: self.lane_change_timer = 1.0

        if self.lane != self.target_lane:
            dir = 1 if self.target_lane > self.lane else -1
            self.lane += dir * dt / self.lane_change_duration
            if (dir > 0 and self.lane >= self.target_lane) or (dir < 0 and self.lane <= self.target_lane):
                self.lane = self.target_lane
                self.lane_change_timer = random.uniform(4.0, 9.0)

        target_x = road.get_lane_x(self.lane, "player") + self.lateral_offset
        self.braking = False
        for other in all_cars:
            if other is self: continue
            dz = other.z - self.z
            if 0 < dz < 160 and abs(other.x - target_x) < LANE_WIDTH * 0.8:
                self.speed = max(0, min(self.speed, other.speed - 25))
                self.braking = True

        self.braking_for_light = False
        for s in road.segments:
            if s.has_checkpoint and s.light_state == "red" and not s.solved:
                dz = s.z - self.z
                if 0 < dz < 280:
                    self.speed = max(0, self.speed - 450 * dt)
                    self.braking = True
                    self.braking_for_light = True

        if not self.braking_for_light:
            accel = 80 if self.car_type in ("truck", "bus") else 140
            decel = 35 if self.car_type in ("truck", "bus") else 45
            if self.speed < self.target_speed: self.speed += accel * dt
            elif self.speed > self.target_speed: self.speed -= decel * dt

        self.z += self.speed * dt
        min_x = -HALF_ROAD + 50; max_x = HALF_ROAD - 50
        self.x = max(min_x, min(max_x, target_x))
        self.update_physics(dt, road)
        if self.z < player.z - 900: return False
        return True

    def draw(self, surf, road, camera_x, camera_y, camera_z, horizon_y, bottom_y, vp_x, bottom_half, width_mult, scale_mult):
        cam_road_x = road.get_road_x(camera_z)
        proj_x = self.x - cam_road_x
        p = project_world(proj_x, self.y, self.z, camera_x, camera_y, camera_z, horizon_y, bottom_y, vp_x, bottom_half, width_mult, scale_mult)
        if p is None: return
        cx, cy, scale, depth = p
        cy += self.bounce
        scale_mult = 1.9 if self.car_type in ("truck", "bus") else 1.7 if self.car_type == "suv" else 1.5 if self.car_type == "van" else 1.3
        self.draw_rear(surf, cx, cy, scale * scale_mult, self.color, depth)


# ==========================================
# OPPOSITE TRAFFIC
# ==========================================
class OppositeVehicle(Vehicle):
    def __init__(self, z, speed, road):
        self.road = road
        lane = random.randint(0, NUM_LANES - 1)
        x = road.get_lane_x(lane, "opposite")
        car_types = ["sedan", "sedan", "suv", "truck", "van"]
        colors = [(195, 50, 50), (50, 90, 195), (205, 180, 45), (160, 65, 175), (75, 75, 82)]
        car_type = random.choice(car_types)
        super().__init__(x, z, speed, random.choice(colors), car_type)
        self.lane = lane
        self.target_speed = speed
        if car_type == "truck": self.target_speed *= 0.75
        self.width = 340.0; self.length = 38.0
        self.lateral_offset = random.uniform(-40, 40)

    def update(self, dt, road, player):
        target_x = road.get_lane_x(self.lane, "opposite") + self.lateral_offset
        opp_center = HALF_ROAD + MEDIAN_WIDTH + HALF_ROAD
        min_x = HALF_ROAD + MEDIAN_WIDTH + 50; max_x = opp_center + HALF_ROAD - 50
        self.x = max(min_x, min(max_x, target_x))
        self.z -= self.speed * dt
        self.update_physics(dt, road)
        if self.z > player.z + 800 or self.z < player.z - 1200: return False
        return True

    def draw(self, surf, road, camera_x, camera_y, camera_z, horizon_y, bottom_y, vp_x, bottom_half, width_mult, scale_mult):
        cam_road_x = road.get_road_x(camera_z)
        proj_x = self.x - cam_road_x
        p = project_world(proj_x, self.y, self.z, camera_x, camera_y, camera_z, horizon_y, bottom_y, vp_x, bottom_half, width_mult, scale_mult)
        if p is None: return
        cx, cy, scale, depth = p
        cy += self.bounce
        s = scale * 1.5
        if s < 0.25: return
        self.draw_shadow(surf, cx, cy, s)
        body_w = max(8, int(38 * s)); body_h = max(5, int(22 * s))
        body = pygame.Rect(cx - body_w//2, cy - body_h, body_w, body_h)
        pygame.draw.rect(surf, self.color, body, border_radius=max(2, int(4*s)))
        pygame.draw.rect(surf, (22, 25, 28), body, max(1, int(2*s)), border_radius=max(2, int(4*s)))
        for side in (-1, 1):
            lx = cx + side * body_w * 0.35
            pygame.draw.circle(surf, (255, 255, 240), (int(lx), int(cy - body_h * 0.25)), max(3, int(6*s)))
            pygame.draw.circle(surf, (200, 220, 255), (int(lx), int(cy - body_h * 0.25)), max(2, int(4*s)))
        pygame.draw.rect(surf, (60, 60, 65), (cx - body_w*0.3, cy - body_h*0.5, body_w*0.6, body_h*0.25))
        for side in (-1, 1):
            wx = cx + side * body_w * 0.42
            pygame.draw.circle(surf, (18, 18, 22), (int(wx), int(cy + 2)), max(3, int(7*s)))
            pygame.draw.circle(surf, (165, 165, 172), (int(wx), int(cy + 2)), max(2, int(3*s)))


# ==========================================
# CAMERA SYSTEM (3 POVs)
# ==========================================
class CameraSystem:
    POV_INTERIOR = 0
    POV_HOOD = 1
    POV_THIRD = 2

    def __init__(self):
        self.pov = self.POV_HOOD
        self.x = 0.0; self.y = 0.0; self.z = -200.0
        self.pitch = 0.0; self.shake_timer = 0.0; self.shake_mag = 0.0
        self._pov_label_timer = 0.0
        self._pov_labels = ["FIRST PERSON", "HOOD VIEW", "THIRD PERSON"]
        self.motion = CAM_MOTION_OFF
        self._bob_phase = 0.0

    def cycle_pov(self):
        self.pov = (self.pov + 1) % 3
        self._pov_label_timer = 2.0

    def cycle_motion(self):
        self.motion = (self.motion + 1) % 3

    def get_pov_label(self): return self._pov_labels[self.pov]
    def get_motion_label(self): return ["OFF", "LOW", "NORMAL"][self.motion]

    def add_shake(self, magnitude, duration):
        self.shake_timer = duration; self.shake_mag = magnitude

    def update(self, dt, player):
        if self._pov_label_timer > 0: self._pov_label_timer -= dt
        if self.pov == self.POV_INTERIOR:
            target_z = player.z + 5.0; target_x = player.x; target_y = player.y + 35.0; lag = 14.0
        elif self.pov == self.POV_HOOD:
            target_z = player.z + 15.0; target_x = player.x; target_y = player.y + 45.0; lag = 8.0
        else:
            target_z = player.z - 280.0; target_x = player.x; target_y = player.y + 80.0; lag = 4.0

        self.z += (target_z - self.z) * min(1.0, lag * dt)
        self.x += (target_x - self.x) * min(1.0, lag * 0.7 * dt)
        self.y += (target_y - self.y) * min(1.0, lag * 0.6 * dt)

        if self.motion != CAM_MOTION_OFF and player.speed > 10:
            self._bob_phase += dt * (3.0 if self.motion == CAM_MOTION_NORMAL else 1.5)
            bob_amp = 0.6 if self.motion == CAM_MOTION_NORMAL else 0.25
            self.y += math.sin(self._bob_phase) * bob_amp

        if self.shake_timer > 0:
            self.shake_timer -= dt
            shake = self.shake_mag * (0.5 if self.motion == CAM_MOTION_LOW else 1.0)
            self.x += random.uniform(-shake, shake); self.y += random.uniform(-shake, shake)
            self.shake_mag *= max(0, 1 - 4.0 * dt)

    def is_interior(self): return self.pov == self.POV_INTERIOR
    def is_hood(self): return self.pov == self.POV_HOOD
    def is_third(self): return self.pov == self.POV_THIRD


# ==========================================
# DASHBOARD (Interior View + Integrated GPS)
# ==========================================
class Dashboard:
    def __init__(self):
        pass

    def draw(self, surf, screen_w, screen_h, player, steer_dragging=False, maneuver=None, dest_dist=0):
        dash_h = int(screen_h * 0.22)
        dash_y = screen_h - dash_h

        tint_h = max(30, int(screen_h * 0.07))
        tint = pygame.Surface((screen_w, tint_h), pygame.SRCALPHA)
        for i in range(tint_h):
            a = int(40 * (1 - i / tint_h))
            pygame.draw.line(tint, (42, 62, 82, a), (0, i), (screen_w, i))
        surf.blit(tint, (0, 0))

        glare_cx = int(screen_w * (0.3 + 0.04 * math.sin(player.bounce_t * 0.06)))
        glow = pygame.Surface((280, 90), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255, 240, 200, 15), (0, 0, 280, 90))
        pygame.draw.ellipse(glow, (255, 250, 220, 25), (40, 18, 200, 55))
        surf.blit(glow, (glare_cx - 140, tint_h - 22))

        for i in range(dash_h):
            t = i / max(1, dash_h - 1)
            r = int(_lerp(60, 20, t)); g = int(_lerp(65, 22, t)); b = int(_lerp(70, 25, t))
            pygame.draw.line(surf, (r, g, b), (0, dash_y + i), (screen_w, dash_y + i))

        wood_y = dash_y + 12
        pygame.draw.rect(surf, (40, 35, 30), (0, wood_y, screen_w, 6))
        pygame.draw.line(surf, (80, 70, 60), (0, wood_y + 1), (screen_w, wood_y + 1), 1)
        pygame.draw.line(surf, (25, 22, 20), (0, wood_y + 7), (screen_w, wood_y + 7), 1)

        # --- STEERING WHEEL (Lower Left) ---
        wheel_cx = screen_w * 0.28
        wheel_cy = screen_h - dash_h * 0.35
        wheel_r = int(screen_w * 0.09)

        wheel_surf = pygame.Surface((wheel_r*2 + 20, wheel_r*2 + 20), pygame.SRCALPHA)
        wcx, wcy = wheel_r + 10, wheel_r + 10
        pygame.draw.circle(wheel_surf, (15, 15, 15), (wcx, wcy), wheel_r + 6)
        pygame.draw.circle(wheel_surf, (40, 40, 45), (wcx, wcy), wheel_r, width=max(8, wheel_r // 4))
        for ang in (210, 330, 90):
            rad = math.radians(ang)
            end = (wcx + math.cos(rad) * wheel_r * 0.9, wcy + math.sin(rad) * wheel_r * 0.9)
            pygame.draw.line(wheel_surf, (25, 25, 28), (wcx, wcy), end, max(6, wheel_r // 6))
        hub_r = max(8, wheel_r // 4)
        pygame.draw.circle(wheel_surf, (30, 30, 35), (wcx, wcy), hub_r)
        pygame.draw.circle(wheel_surf, (180, 180, 185), (wcx, wcy), max(4, hub_r // 2))

        rot_angle = -player.steer_angle * 60.0
        rotated_wheel = pygame.transform.rotate(wheel_surf, rot_angle)
        rot_rect = rotated_wheel.get_rect(center=(int(wheel_cx), int(wheel_cy)))
        if steer_dragging:
            pygame.draw.circle(surf, (100, 200, 255), (int(wheel_cx), int(wheel_cy)), wheel_r + 15, 3)
        surf.blit(rotated_wheel, rot_rect)

        # --- GAUGES (Right Side) ---
        gauge_cx = screen_w * 0.82
        gauge_cy = screen_h - dash_h * 0.4
        gauge_r = max(25, int(wheel_r * 0.65))
        self._draw_gauge(surf, gauge_cx - gauge_r*1.2, gauge_cy, gauge_r, player.speed, 350, "km/h", (245, 95, 75))
        rpm = 1000 + (player.speed / max(1.0, 300)) * 4500
        self._draw_gauge(surf, gauge_cx + gauge_r*1.2, gauge_cy, gauge_r, rpm, 6000, "rpm", (82, 162, 230))

        # --- INTEGRATED DASHBOARD GPS (Center Console) ---
        cons_w = int(screen_w * 0.22)
        cons_h = int(dash_h * 0.75)
        cons_x = screen_w // 2 - cons_w // 2
        cons_y = dash_y + int(dash_h * 0.12)
        
        # Bezel
        pygame.draw.rect(surf, (15, 15, 18), (cons_x - 6, cons_y - 6, cons_w + 12, cons_h + 12), border_radius=8)
        gps = pygame.Surface((cons_w, cons_h))
        gps.fill((20, 30, 45))
        
        font_gps_title = pygame.font.Font(None, max(14, int(cons_w * 0.08)))
        font_gps_big = pygame.font.Font(None, max(18, int(cons_w * 0.11)))
        font_gps_instr = pygame.font.Font(None, max(16, int(cons_w * 0.09)))
        
        # Destination Info
        title = font_gps_title.render("CITY MARKET", True, (150, 200, 180))
        gps.blit(title, (10, 8))
        
        dist_txt_str = f"{dest_dist/1000:.1f} km" if dest_dist >= 1000 else f"{int(dest_dist)} m"
        dest_txt = font_gps_big.render(dist_txt_str, True, (255, 255, 255))
        gps.blit(dest_txt, (cons_w - dest_txt.get_width() - 10, 6))
        
        # Maneuver Info
        if maneuver:
            instr, arrow_dir, instr_dist = maneuver
            dist_label = "NOW" if instr_dist < 40 else (f"{instr_dist/1000:.1f} km" if instr_dist >= 1000 else f"{int(instr_dist)} m")
            
            # Arrow
            ax, ay = 15, cons_h // 2 + 5
            if arrow_dir == 1:
                pygame.draw.polygon(gps, (255, 200, 80), [(ax, ay), (ax+12, ay-8), (ax+12, ay-3), (ax+25, ay-3), (ax+25, ay+3), (ax+12, ay+3), (ax+12, ay+8)])
            elif arrow_dir == -1:
                pygame.draw.polygon(gps, (255, 200, 80), [(ax+25, ay), (ax+13, ay-8), (ax+13, ay-3), (ax, ay-3), (ax, ay+3), (ax+13, ay+3), (ax+13, ay+8)])
            else:
                pygame.draw.polygon(gps, (100, 200, 100), [(ax+8, ay-12), (ax+17, ay-12), (ax+17, ay+4), (ax+22, ay+4), (ax+12.5, ay+12), (ax+3, ay+4), (ax+8, ay+4)])
                
            instr_txt = font_gps_instr.render(instr, True, (255, 255, 255))
            gps.blit(instr_txt, (ax + 32, cons_h // 2))
            
            dist_lbl_txt = font_gps_title.render(dist_label, True, (200, 200, 200))
            gps.blit(dist_lbl_txt, (cons_w - dist_lbl_txt.get_width() - 10, cons_h // 2 + 5))
        else:
            straight_txt = font_gps_instr.render("CONTINUE", True, (150, 180, 150))
            gps.blit(straight_txt, (15, cons_h // 2))
            
        # Mini route line decoration
        pygame.draw.line(gps, (60, 120, 90), (cons_w//2, cons_h-5), (cons_w//2, cons_h-25), 3)
        pygame.draw.circle(gps, (100, 200, 100), (cons_w//2, cons_h-25), 3)
        
        surf.blit(gps, (cons_x, cons_y))

        # Pillars
        pillar_w = int(screen_w * 0.042)
        pillar_col = (35, 30, 25); accent = (60, 112, 68)
        left_pillar = [(0, 0), (pillar_w, 0), (pillar_w * 0.35, dash_y), (0, dash_y)]
        right_pillar = [(screen_w - pillar_w, 0), (screen_w, 0), (screen_w, dash_y), (screen_w - pillar_w * 0.35, dash_y)]
        pygame.draw.polygon(surf, pillar_col, left_pillar)
        pygame.draw.polygon(surf, pillar_col, right_pillar)
        pygame.draw.line(surf, accent, (pillar_w * 0.12, 8), (pillar_w * 0.45, dash_y - 8), 4)
        pygame.draw.line(surf, accent, (screen_w - pillar_w * 0.12, 8), (screen_w - pillar_w * 0.45, dash_y - 8), 4)

        self._draw_side_mirror(surf, 0, dash_y - 60, screen_w, screen_h, True)
        self._draw_side_mirror(surf, screen_w - 100, dash_y - 60, screen_w, screen_h, False)

    def _draw_side_mirror(self, surf, x, y, screen_w, screen_h, is_left):
        mw, mh = 90, 60
        pygame.draw.rect(surf, (20, 20, 22), (x, y, mw, mh), border_radius=8)
        glass = pygame.Rect(x+5, y+5, mw-10, mh-10)
        pygame.draw.rect(surf, (120, 140, 150), glass, border_radius=4)
        pygame.draw.line(surf, (80, 90, 100), (glass.centerx, glass.bottom), (glass.centerx, glass.top), 2)

    def draw_hood(self, surf, screen_w, screen_h):
        hood_h = int(screen_h * 0.18)
        hood_y = screen_h - hood_h
        for i in range(hood_h):
            t = i / hood_h
            c = int(52 - 20*t)
            pygame.draw.line(surf, (c, int(112 - 40*t), c), (0, hood_y + i), (screen_w, hood_y + i))
        pygame.draw.rect(surf, (20, 20, 20), (screen_w//2 - 150, hood_y - 5, 300, 15), border_radius=5)
        mw, mh = 80, 50
        pygame.draw.rect(surf, (30, 30, 30), (10, hood_y - 80, mw, mh), border_radius=8)
        pygame.draw.rect(surf, (160, 180, 190), (15, hood_y - 75, mw - 10, mh - 10), border_radius=4)
        pygame.draw.rect(surf, (30, 30, 30), (screen_w - 10 - mw, hood_y - 80, mw, mh), border_radius=8)
        pygame.draw.rect(surf, (160, 180, 190), (screen_w - 5 - mw, hood_y - 75, mw - 10, mh - 10), border_radius=4)

    def _draw_gauge(self, surf, cx, cy, r, value, max_value, unit, needle_color):
        if cx < r + 8 or cx > surf.get_width() - r - 8: return
        g = pygame.Surface((r * 2 + 16, r * 2 + 16), pygame.SRCALPHA)
        pygame.draw.circle(g, (needle_color[0], needle_color[1], needle_color[2], 20), (r + 8, r + 8), r + 8)
        surf.blit(g, (int(cx) - r - 8, int(cy) - r - 8))
        pygame.draw.circle(surf, (10, 9, 8), (int(cx), int(cy)), r + 4)
        pygame.draw.circle(surf, (20, 22, 24), (int(cx), int(cy)), r)
        pygame.draw.circle(surf, (78, 200, 140), (int(cx), int(cy)), r, 2)
        start_ang, end_ang = 135, 405
        for tick in range(6):
            a = math.radians(start_ang + (end_ang - start_ang) * tick / 5)
            pygame.draw.line(surf, (200, 205, 205), (cx + math.cos(a) * r * 0.82, cy + math.sin(a) * r * 0.82), (cx + math.cos(a) * r * 0.95, cy + math.sin(a) * r * 0.95), 2)
        frac = max(0.0, min(1.0, abs(value) / max_value))
        needle_ang = math.radians(start_ang + (end_ang - start_ang) * frac)
        nx = cx + math.cos(needle_ang) * r * 0.72; ny = cy + math.sin(needle_ang) * r * 0.72
        pygame.draw.line(surf, needle_color, (cx, cy), (nx, ny), 3)
        pygame.draw.line(surf, (255, 235, 220), (cx, cy), (nx, ny), 1)
        pygame.draw.circle(surf, (200, 200, 200), (int(cx), int(cy)), 4)
        font_g = pygame.font.Font(None, max(14, int(r * 0.5)))
        val_txt = font_g.render(str(int(abs(value))), True, (232, 232, 232))
        surf.blit(val_txt, (cx - val_txt.get_width() / 2, cy + r * 0.28))
        font_lbl = pygame.font.Font(None, 14)
        lbl_txt = font_lbl.render(unit, True, (132, 192, 162))
        surf.blit(lbl_txt, (cx - lbl_txt.get_width() / 2, cy + r * 0.28 + val_txt.get_height() - 2))


# ==========================================
# MATH QUIZ
# ==========================================
class MathQuiz:
    def __init__(self, sound_manager):
        self.sound = sound_manager; self.active = False; self.checkpoint_index = 0
        self.total_checkpoints = len(CHECKPOINT_DISTANCES); self.question_text = ""; self.answer_value = 0.0
        self.input_text = ""; self.feedback = None; self.feedback_timer = 0.0
        self.shake_timer = 0.0; self.shake_offset = 0.0; self.on_success = None
        self.submit_button_rect = pygame.Rect(0, 0, 0, 0)

    def generate(self, level, checkpoint_index, on_success):
        self.checkpoint_index = checkpoint_index; self.on_success = on_success
        self.input_text = ""; self.feedback = None; self.feedback_timer = 0.0; self.active = True
        level = max(1, min(4, level))
        pools = {1: ["add_sub"], 2: ["mul_div", "add_sub"], 3: ["percent", "fraction", "geometry"], 4: ["algebra", "geometry", "measurement", "percent"]}
        kind = random.choice(pools[level])
        if kind == "add_sub":
            a = random.randint(5, 45); b = random.randint(2, 40)
            if random.random() < 0.5: self.question_text = f"{a} + {b} = ?"; self.answer_value = a + b
            else: a, b = max(a, b), min(a, b); self.question_text = f"{a} - {b} = ?"; self.answer_value = a - b
        elif kind == "mul_div":
            a = random.randint(2, 12); b = random.randint(2, 12)
            if random.random() < 0.5: self.question_text = f"{a} x {b} = ?"; self.answer_value = a * b
            else: product = a * b; self.question_text = f"{product} / {b} = ?"; self.answer_value = a
        elif kind == "percent":
            p = random.choice([10, 20, 25, 50, 75]); n = random.choice([20, 40, 60, 80, 120, 160, 200])
            self.question_text = f"What is {p}% of {n}?"; self.answer_value = round(p * n / 100, 2)
        elif kind == "fraction":
            d = random.choice([4, 5, 6, 8]); n1 = random.randint(1, d - 1); n2 = random.randint(1, d - 1)
            self.question_text = f"{n1}/{d} + {n2}/{d} = ? (as decimal)"; self.answer_value = round((n1 + n2) / d, 2)
        elif kind == "geometry":
            shape = random.choice(["rect_area", "rect_perimeter", "triangle_area"])
            if shape == "rect_area": w = random.randint(3, 12); h = random.randint(3, 12); self.question_text = f"Rectangle: width {w}, height {h}.\nWhat is its area?"; self.answer_value = w * h
            elif shape == "rect_perimeter": w = random.randint(3, 15); h = random.randint(3, 15); self.question_text = f"Rectangle: width {w}, height {h}.\nWhat is its perimeter?"; self.answer_value = 2 * (w + h)
            else: b = random.randint(4, 16); h = random.randint(3, 12); self.question_text = f"Triangle: base {b}, height {h}.\nWhat is its area?"; self.answer_value = round(0.5 * b * h, 2)
        elif kind == "algebra":
            a = random.randint(2, 9); x_val = random.randint(1, 12); b = random.randint(1, 20); c = a * x_val + b
            self.question_text = f"Solve for x:\n{a}x + {b} = {c}"; self.answer_value = x_val
        elif kind == "measurement":
            choice = random.choice(["cm_to_m", "m_to_cm", "min_to_sec"])
            if choice == "cm_to_m": cm = random.randint(1, 20) * 100; self.question_text = f"{cm} cm = ? meters"; self.answer_value = cm / 100
            elif choice == "m_to_cm": m = random.randint(1, 20); self.question_text = f"{m} meters = ? cm"; self.answer_value = m * 100
            else: mins = random.randint(1, 10); self.question_text = f"{mins} minutes = ? seconds"; self.answer_value = mins * 60

    def handle_event(self, event):
        if not self.active or self.feedback == "correct": return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER: self.submit()
            elif event.key == pygame.K_BACKSPACE: self.input_text = self.input_text[:-1]
            else:
                ch = event.unicode
                if ch and (ch.isdigit() or ch in ".-/") and len(self.input_text) < 12: self.input_text += ch

    def _parse(self, text):
        text = text.strip()
        if not text: return None
        try:
            if "/" in text: num, den = text.split("/"); return float(num) / float(den)
            return float(text)
        except (ValueError, ZeroDivisionError): return None

    def submit(self):
        val = self._parse(self.input_text)
        if val is None: self.feedback = "wrong"; self.feedback_timer = 0.9; self.shake_timer = 0.4; self.sound.play("wrong"); return
        if abs(val - self.answer_value) <= 0.05: self.feedback = "correct"; self.feedback_timer = 0.9; self.sound.play("correct")
        else: self.feedback = "wrong"; self.feedback_timer = 0.9; self.shake_timer = 0.4; self.input_text = ""; self.sound.play("wrong")

    def update(self, dt):
        if not self.active: return
        if self.shake_timer > 0: self.shake_timer -= dt; self.shake_offset = math.sin(self.shake_timer * 60) * 6
        else: self.shake_offset = 0
        if self.feedback:
            self.feedback_timer -= dt
            if self.feedback_timer <= 0:
                if self.feedback == "correct":
                    self.active = False; cb = self.on_success; self.on_success = None
                    if cb: cb()
                else: self.feedback = None

    def draw(self, surf, screen_w, screen_h):
        if not self.active: return
        overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA); overlay.fill((0, 0, 0, 130)); surf.blit(overlay, (0, 0))
        panel_w, panel_h = 560, 340; px = screen_w // 2 - panel_w // 2 + int(self.shake_offset); py = screen_h // 2 - panel_h // 2
        panel_color = (250, 248, 240)
        if self.feedback == "correct": panel_color = (225, 250, 225)
        elif self.feedback == "wrong": panel_color = (250, 225, 225)
        pygame.draw.rect(surf, panel_color, (px, py, panel_w, panel_h), border_radius=18)
        pygame.draw.rect(surf, (60, 140, 90), (px, py, panel_w, panel_h), 4, border_radius=18)
        font_small = pygame.font.Font(None, 22)
        label = font_small.render(f"Checkpoint {self.checkpoint_index + 1} of {self.total_checkpoints}", True, (70, 70, 70))
        surf.blit(label, (px + panel_w // 2 - label.get_width() // 2, py + 18))
        dot_r = 8; total_w_dots = self.total_checkpoints * (dot_r * 2 + 10) - 10; dot_x = px + panel_w // 2 - total_w_dots // 2 + dot_r
        for i in range(self.total_checkpoints):
            color = (60, 180, 90) if i < self.checkpoint_index else (255, 200, 60) if i == self.checkpoint_index else (210, 210, 210)
            pygame.draw.circle(surf, color, (dot_x, py + 46), dot_r); dot_x += dot_r * 2 + 10
        font_title = pygame.font.Font(None, 34); title = font_title.render("Traffic Light Math Challenge", True, (40, 110, 75))
        surf.blit(title, (px + panel_w // 2 - title.get_width() // 2, py + 66))
        font_q = pygame.font.Font(None, 30); lines = self.question_text.split("\n"); qy = py + 120
        for line in lines: qs = font_q.render(line, True, (40, 40, 45)); surf.blit(qs, (px + panel_w // 2 - qs.get_width() // 2, qy)); qy += 34
        box_w, box_h = 220, 46; box_x = px + panel_w // 2 - box_w // 2; box_y = qy + 14
        box_color = (255, 255, 255); border_color = (110, 170, 130)
        if self.feedback == "wrong": border_color = (210, 90, 90)
        elif self.feedback == "correct": border_color = (70, 180, 100)
        pygame.draw.rect(surf, box_color, (box_x, box_y, box_w, box_h), border_radius=10)
        pygame.draw.rect(surf, border_color, (box_x, box_y, box_w, box_h), 3, border_radius=10)
        font_input = pygame.font.Font(None, 32); txt = font_input.render(self.input_text or " ", True, (30, 30, 30))
        surf.blit(txt, (box_x + 14, box_y + 8))
        btn_w, btn_h = 150, 42; btn_x = px + panel_w // 2 - btn_w // 2; btn_y = box_y + box_h + 16
        pygame.draw.rect(surf, (80, 165, 110), (btn_x, btn_y, btn_w, btn_h), border_radius=12)
        pygame.draw.rect(surf, (40, 110, 75), (btn_x, btn_y, btn_w, btn_h), 2, border_radius=12)
        font_btn = pygame.font.Font(None, 26); btn_txt = font_btn.render("Submit (Enter)", True, (255, 255, 255))
        surf.blit(btn_txt, (btn_x + btn_w // 2 - btn_txt.get_width() // 2, btn_y + 10))
        if self.feedback == "correct": fb = font_q.render("Correct! Light turning green...", True, (40, 150, 80)); surf.blit(fb, (px + panel_w // 2 - fb.get_width() // 2, py + panel_h - 34))
        elif self.feedback == "wrong": fb = font_q.render("Not quite - try again!", True, (190, 70, 70)); surf.blit(fb, (px + panel_w // 2 - fb.get_width() // 2, py + panel_h - 34))
        self.submit_button_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

    def handle_click(self, pos):
        if self.active and self.feedback != "correct":
            if self.submit_button_rect.collidepoint(pos): self.submit()


# ==========================================
# UI / HUD
# ==========================================
class UI:
    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w; self.screen_h = screen_h
        self.font = pygame.font.Font(None, 26); self.font_big = pygame.font.Font(None, 36); self.font_small = pygame.font.Font(None, 20)
        self.show_help = True; self.help_timer = 12.0

    def _get_maneuver(self, player_z, road):
        segs = road.segments; n = len(segs); cur = int(player_z // SEGMENT_LENGTH)
        for j in range(cur, min(cur + 260, n)):
            seg = segs[j]
            if seg.z <= player_z + 1: continue
            prev = segs[j - 1] if j > 0 else None
            curve_start = abs(seg.curve) > 0.6 and (prev is None or abs(prev.curve) <= 0.6)
            checkpoint = seg.has_checkpoint and not seg.solved
            if curve_start or checkpoint:
                if checkpoint: return ("CHECKPOINT", 0, seg.z - player_z)
                lbl = "RIGHT CURVE" if seg.curve > 0 else "LEFT CURVE"
                ar = 1 if seg.curve > 0 else -1
                return (lbl, ar, seg.z - player_z)
        return None

    def _fmt_dist(self, d):
        if d >= 1000: return f"{d/1000:.1f} km"
        return f"{int(d)} m"

    def draw(self, surf, player, road, cars, opposite_cars, phase, camera, checkpoint_seg=None):
        # TOP LEFT HUD: Speed + KM Travelled (Visible in ALL POVs)
        hud_bg = pygame.Surface((220, 60), pygame.SRCALPHA)
        hud_bg.fill((10, 10, 14, 200))
        surf.blit(hud_bg, (16, 16))
        
        speed_kmh = int(abs(player.speed) * 0.8)
        rev = " R" if player.speed < -1 else ""
        speed_txt = self.font_big.render(f"{speed_kmh} km/h{rev}", True, (255, 255, 255))
        surf.blit(speed_txt, (28, 20))
        
        # Real distance travelled display
        trav_km = player.distance_travelled / 1000.0
        trav_txt = self.font.render(f"TRAVELLED: {trav_km:.1f} km", True, (200, 220, 200))
        surf.blit(trav_txt, (28, 50))

        # Remaining distance logic for non-interior fallback (if needed elsewhere)
        dest_dist = max(0, FINAL_DISTANCE - player.z)
        maneuver = self._get_maneuver(player.z, road)

        bar_w = self.screen_w - 100; bar_x, bar_y = 50, self.screen_h - 32
        pygame.draw.rect(surf, (32, 32, 38), (bar_x, bar_y, bar_w, 16), border_radius=8)
        pygame.draw.rect(surf, (90, 95, 100), (bar_x, bar_y, bar_w, 16), 2, border_radius=8)
        progress = max(0.0, min(1.0, player.z / FINAL_DISTANCE))
        pygame.draw.rect(surf, (72, 200, 118), (bar_x, bar_y, int(bar_w * progress), 16), border_radius=8)

        for cp in CHECKPOINT_DISTANCES:
            cp_prog = cp / FINAL_DISTANCE; cx = bar_x + int(bar_w * cp_prog); col = (215, 215, 215)
            for seg in road.segments:
                if seg.has_checkpoint and abs(seg.z - cp) < SEGMENT_LENGTH and seg.solved: col = (55, 195, 85); break
            pygame.draw.circle(surf, col, (cx, bar_y + 8), 7)
            pygame.draw.circle(surf, (80, 80, 85), (cx, bar_y + 8), 7, 1)

        label_text = {"entering": "Pulling onto the highway...", "cruising": "Drive to the city market", "braking": "Slowing for checkpoint...", "stopped": "Stopped at checkpoint - solve the math problem!", "resuming": "Light green - moving on!", "arriving": "Almost at the city..."}.get(phase, "")
        if label_text:
            txt = self.font.render(label_text, True, (42, 42, 48))
            bg2 = pygame.Surface((txt.get_width() + 24, txt.get_height() + 12)); bg2.fill((255, 255, 255)); bg2.set_alpha(220)
            surf.blit(bg2, (self.screen_w // 2 - bg2.get_width() // 2, 96))
            surf.blit(txt, (self.screen_w // 2 - txt.get_width() // 2, 102))

        if camera._pov_label_timer > 0:
            alpha = int(255 * min(1.0, camera._pov_label_timer / 0.5))
            pov_txt = self.font_big.render(camera.get_pov_label(), True, (255, 255, 255))
            pov_bg = pygame.Surface((pov_txt.get_width() + 30, pov_txt.get_height() + 16), pygame.SRCALPHA); pov_bg.fill((18, 18, 26, alpha))
            surf.blit(pov_bg, (self.screen_w // 2 - pov_bg.get_width() // 2, 136))
            surf.blit(pov_txt, (self.screen_w // 2 - pov_txt.get_width() // 2, 144))

        motion_txt = self.font_small.render(f"Camera Motion: {camera.get_motion_label()}", True, (200, 200, 200))
        mbg = pygame.Surface((motion_txt.get_width() + 12, motion_txt.get_height() + 6), pygame.SRCALPHA); mbg.fill((10, 10, 14, 200))
        surf.blit(mbg, (16, 84)); surf.blit(motion_txt, (22, 87))

        self._draw_minimap(surf, player, road, cars, opposite_cars)

        total_traffic = len(cars) + len(opposite_cars)
        car_txt = self.font_small.render(f"Traffic: {total_traffic} vehicles", True, (190, 190, 190))
        cbg = pygame.Surface((car_txt.get_width() + 12, car_txt.get_height() + 6), pygame.SRCALPHA); cbg.fill((10, 10, 14, 200))
        surf.blit(cbg, (16, 108)); surf.blit(car_txt, (22, 111))

        if self.show_help:
            self.help_timer -= 0.016
            if self.help_timer <= 0: self.show_help = False
            hint = self.font_small.render("W/S = Gas/Brake  |  A/D = Steer  |  1/2/3 = View  |  M = Motion  |  Space = Handbrake", True, (255, 255, 255))
            hbg = pygame.Surface((hint.get_width() + 20, hint.get_height() + 10), pygame.SRCALPHA); hbg.fill((10, 10, 14, 200))
            surf.blit(hbg, (self.screen_w // 2 - hbg.get_width() // 2, self.screen_h - 58))
            surf.blit(hint, (self.screen_w // 2 - hint.get_width() // 2, self.screen_h - 54))
            
        # Return shared nav data so Dashboard can use it without recalculating
        return maneuver, dest_dist

    def _draw_minimap(self, surf, player, road, cars, opposite_cars):
        mw, mh = 170, 170; mx = self.screen_w - mw - 16; my = 16
        map_surf = pygame.Surface((mw, mh), pygame.SRCALPHA)
        pygame.draw.rect(map_surf, (18, 22, 28, 235), (0, 0, mw, mh), border_radius=12)
        px = mw // 2; py = mh - 34; scale_x = 2.2; scale_z = 0.14
        player_world_x = road.get_road_x(player.z) + player.x
        pts = []; cur = int(player.z // SEGMENT_LENGTH)
        for i in range(max(0, cur - 8), min(len(road.segments), cur + 90)):
            seg = road.segments[i]; rx = px + (seg.road_x - player_world_x) * scale_x; rz = py - (seg.z - player.z) * scale_z; pts.append((rx, rz))
        if len(pts) > 1:
            pygame.draw.lines(map_surf, (50, 55, 62), False, pts, 7)
            pygame.draw.lines(map_surf, (90, 190, 130), False, pts, 3)
        dest_idx = min(len(road.segments) - 1, int(FINAL_DISTANCE // SEGMENT_LENGTH)); dseg = road.segments[dest_idx]
        drx = px + (dseg.road_x - player_world_x) * scale_x; drz = py - (dseg.z - player.z) * scale_z
        if 0 <= drx < mw and 0 <= drz < mh:
            pygame.draw.circle(map_surf, (255, 80, 80), (int(drx), int(drz)), 5)
            pygame.draw.circle(map_surf, (255, 255, 255), (int(drx), int(drz)), 2)
        for car in cars:
            if abs(car.z - player.z) < 900:
                cwx = road.get_road_x(car.z) + car.x; cx = px + (cwx - player_world_x) * scale_x; cy = py - (car.z - player.z) * scale_z
                if 0 <= cx < mw and 0 <= cy < mh: pygame.draw.circle(map_surf, (255, 205, 70), (int(cx), int(cy)), 3)
        seg_now = road.find_segment(player.z); nxt = road.segments[seg_now.index + 1] if seg_now.index + 1 < len(road.segments) else seg_now
        dx = nxt.road_x - seg_now.road_x; ang = math.degrees(math.atan2(dx * scale_x, SEGMENT_LENGTH * scale_z))
        arrow = pygame.Surface((22, 22), pygame.SRCALPHA); pygame.draw.polygon(arrow, (120, 235, 140), [(11, 2), (20, 20), (11, 15), (2, 20)])
        rot = pygame.transform.rotate(arrow, -ang); map_surf.blit(rot, rot.get_rect(center=(px, py)))
        surf.blit(map_surf, (mx, my))
        pygame.draw.rect(surf, (70, 80, 95), (mx, my, mw, mh), 2, border_radius=12)


# ==========================================
# HIGHWAY SCENE (main orchestrator)
# ==========================================
class HighwayScene:
    def __init__(self, screen_w, screen_h, truck_surface=None):
        self.screen_w = screen_w; self.screen_h = screen_h
        self.road = Road(screen_w, screen_h); self.player = PlayerVehicle(); self.camera = CameraSystem()
        self.cars = []; self.opposite_cars = []; self.sound = SoundManager(); self.quiz = MathQuiz(self.sound)
        self.ui = UI(screen_w, screen_h); self.fade = FadeTransition(0.7)
        self.background = CityBackground(screen_w, screen_h, self.road.horizon_y); self.dashboard = Dashboard()
        self.phase = "entering"; self.finished = False; self._arrive_timer = 0.0
        self._spawn_timer = 0.0; self._opp_spawn_timer = 0.0; self._next_checkpoint = 0
        self.warm_overlay = pygame.Surface((screen_w, screen_h)); self.warm_overlay.fill((255, 185, 115))
        self.vignette = self._make_vignette(); self._crash_flash = 0.0; self._fog_overlay = None; self.steer_drag = False

    def _make_vignette(self):
        v = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        cx, cy = self.screen_w // 2, self.screen_h // 2; max_r = int(math.hypot(cx, cy))
        for i in range(24):
            t = i / 24; r = int(max_r * (1 - t * 0.85)); a = int(38 * (1 - t) ** 2)
            pygame.draw.ellipse(v, (0, 0, 0, a), (cx - r, cy - r, r * 2, r * 2), max(2, int(max_r / 12)))
        return v

    def _wheel_geom(self):
        dash_h = int(self.screen_h * 0.22); cx = self.screen_w * 0.28; cy = self.screen_h - dash_h * 0.35; r = int(self.screen_w * 0.09)
        return cx, cy, r

    def start(self): self.fade.start()

    def _next_unsolved_checkpoint(self):
        for seg in self.road.segments:
            if seg.has_checkpoint and not seg.solved: return seg
        return None

    def _on_quiz_success(self):
        cp = self._next_unsolved_checkpoint()
        if cp: cp.solved = True; cp.light_state = "green"; self.sound.play("light")
        self.phase = "resuming"

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_c: self.camera.cycle_pov(); self.sound.play("camera")
            elif event.key == pygame.K_m: self.camera.cycle_motion()
            elif event.key == pygame.K_1: self.camera.pov = CameraSystem.POV_INTERIOR; self.camera._pov_label_timer = 2.0
            elif event.key == pygame.K_2: self.camera.pov = CameraSystem.POV_HOOD; self.camera._pov_label_timer = 2.0
            elif event.key == pygame.K_3: self.camera.pov = CameraSystem.POV_THIRD; self.camera._pov_label_timer = 2.0

        if self.camera.is_interior():
            wcx, wcy, wr = self._wheel_geom()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if abs(mx - wcx) < wr * 1.8 and my > self.screen_h * 0.55: self.steer_drag = True
            elif event.type == pygame.MOUSEBUTTONUP:
                if self.steer_drag: self.steer_drag = False; self.player.steer_manual = False
            elif event.type == pygame.MOUSEMOTION and self.steer_drag:
                mx, my = event.pos; self.player.steer_manual = True; self.player.steer_target = max(-1.0, min(1.0, (mx - wcx) / (wr * 1.1)))
            elif event.type == pygame.FINGERDOWN:
                mx, my = event.x * self.screen_w, event.y * self.screen_h
                if abs(mx - wcx) < wr * 1.8 and my > self.screen_h * 0.55: self.steer_drag = True
            elif event.type == pygame.FINGERUP: self.steer_drag = False; self.player.steer_manual = False
            elif event.type == pygame.FINGERMOTION and self.steer_drag:
                mx = event.x * self.screen_w; self.player.steer_manual = True; self.player.steer_target = max(-1.0, min(1.0, (mx - wcx) / (wr * 1.1)))

        if self.phase == "stopped" and self.quiz.active:
            self.quiz.handle_event(event)
            if event.type == pygame.MOUSEBUTTONDOWN: self.quiz.handle_click(event.pos)

    def _manage_traffic(self):
        self._spawn_timer -= 0.016
        if self._spawn_timer <= 0:
            self._spawn_timer = random.uniform(1.2, 2.5)
            if len(self.cars) < 12 and self.player.z < FINAL_DISTANCE - 200:
                spawn_z = self.player.z + random.uniform(400, 1000); lane = random.randint(0, NUM_LANES - 1); speed = random.uniform(140, 270); ok = True
                for seg in self.road.segments:
                    if seg.has_checkpoint and abs(seg.z - spawn_z) < 150: ok = False; break
                if ok: self.cars.append(AIVehicle(spawn_z, lane, speed, self.road))
        new_cars = []
        for car in self.cars:
            if car.update(0.016, self.road, self.player, self.cars): new_cars.append(car)
        self.cars = new_cars

    def _manage_opposite_traffic(self):
        self._opp_spawn_timer -= 0.016
        if self._opp_spawn_timer <= 0:
            self._opp_spawn_timer = random.uniform(1.5, 3.0)
            if len(self.opposite_cars) < 8:
                spawn_z = self.player.z - random.uniform(300, 800); speed = random.uniform(160, 280)
                self.opposite_cars.append(OppositeVehicle(spawn_z, speed, self.road))
        new_opp = []
        for car in self.opposite_cars:
            if car.update(0.016, self.road, self.player): new_opp.append(car)
        self.opposite_cars = new_opp

    def _check_collisions(self):
        if self.player.crash_timer > 0: return
        for car in self.cars:
            dz = abs(self.player.z - car.z); dx = abs(self.player.x - car.x)
            if dz < 45 and dx < 400:
                self.player.speed *= 0.3; self.player.crash_timer = 1.2; self.camera.add_shake(10.0, 0.5); self._crash_flash = 0.35; self.sound.play("crash")
                if self.player.x < car.x: self.player.x -= 200
                else: self.player.x += 200
                break

    def _check_checkpoints(self):
        if self.quiz.active: return
        cp = self._next_unsolved_checkpoint()
        if cp:
            dist = cp.z - self.player.z
            if 0 < dist < 300 and self.player.speed > 0:
                self.phase = "braking"; factor = max(0.0, min(1.0, dist / 300)); target = 260 * factor; self.player.speed = max(0, min(self.player.speed, target))
                if dist < 18:
                    self.player.speed = 0; self.phase = "stopped"; level = cp.checkpoint_id + 1; self.quiz.generate(level, cp.checkpoint_id, self._on_quiz_success)
            else:
                if self.phase not in ("entering", "arriving"): self.phase = "cruising"
        else:
            if self.phase not in ("entering", "arriving"): self.phase = "cruising"

    def update(self, dt):
        keys = pygame.key.get_pressed(); self.fade.update(dt); self.background.update(dt)
        if not self.steer_drag: self.player.steer_manual = False
        if self.fade.state == "out" and self.fade.is_done_fading_out(): self.finished = True; return "arrived"
        if self.phase == "arriving" and self.fade.state != "out":
            self._arrive_timer -= dt
            if self._arrive_timer <= 0: self.fade.begin_out()
            self.player.handle_input(keys, dt, self.road); self.player.update(dt, self.road); self.camera.update(dt, self.player); return "running"
        if self.quiz.active:
            self.quiz.update(dt); self.player.speed = max(0, self.player.speed - 600 * dt); self.player.update(dt, self.road); self.camera.update(dt, self.player); return "running"
        self.player.handle_input(keys, dt, self.road); self.player.update(dt, self.road)
        self._manage_traffic(); self._manage_opposite_traffic(); self._check_checkpoints(); self._check_collisions(); self.camera.update(dt, self.player)
        if self.player.z >= FINAL_DISTANCE and self.phase != "arriving": self.phase = "arriving"; self._arrive_timer = 1.6; self.sound.play("arrive")
        if self.phase == "entering" and self.player.z >= 0: self.phase = "cruising"
        if self._crash_flash > 0: self._crash_flash -= dt
        return "running"

    def draw(self, surf):
        progress = max(0.0, min(1.0, self.player.z / FINAL_DISTANCE))
        self.background.draw(surf, self.camera.z, progress, horizon_y=self.road.horizon_y)
        self.road.render(surf, self.camera.x, self.camera.y, self.camera.z, self.road.horizon_y, self.road.bottom_y, self.road.vp_x, 1.0, 1.0)

        all_drawables = []; cam_road_x = self.road.get_road_x(self.camera.z)
        for car in self.opposite_cars:
            proj_x = car.x - cam_road_x
            p = project_world(proj_x, car.y, car.z, self.camera.x, self.camera.y, self.camera.z, self.road.horizon_y, self.road.bottom_y, self.road.vp_x, self.road.bottom_half, 1.0, 1.0)
            if p: all_drawables.append((p[1], car, p, "opposite"))
        for car in self.cars:
            proj_x = car.x - cam_road_x
            p = project_world(proj_x, car.y, car.z, self.camera.x, self.camera.y, self.camera.z, self.road.horizon_y, self.road.bottom_y, self.road.vp_x, self.road.bottom_half, 1.0, 1.0)
            if p: all_drawables.append((p[1], car, p, "ai"))
        if not self.camera.is_interior():
            p = project_world(self.player.x, self.player.y + self.player.suspension_y, self.player.z, self.camera.x, self.camera.y, self.camera.z, self.road.horizon_y, self.road.bottom_y, self.road.vp_x, self.road.bottom_half, 1.0, 1.0)
            if p: all_drawables.append((p[1], self.player, p, "player"))
        all_drawables.sort(key=lambda x: x[0], reverse=True)
        for _, obj, p, kind in all_drawables:
            if kind == "opposite": obj.draw(surf, self.road, self.camera.x, self.camera.y, self.camera.z, self.road.horizon_y, self.road.bottom_y, self.road.vp_x, self.road.bottom_half, 1.0, 1.0)
            elif kind == "ai": obj.draw(surf, self.road, self.camera.x, self.camera.y, self.camera.z, self.road.horizon_y, self.road.bottom_y, self.road.vp_x, self.road.bottom_half, 1.0, 1.0)
            elif kind == "player": self.player.draw(surf, self.road, self.camera.x, self.camera.y, self.camera.z, self.road.horizon_y, self.road.bottom_y, self.road.vp_x, self.road.bottom_half, 1.0, 1.0)

        # UI draws HUD elements AND returns shared navigation data
        maneuver, dest_dist = self.ui.draw(surf, self.player, self.road, self.cars, self.opposite_cars, self.phase, self.camera)

        # Pass shared navigation data directly into the Dashboard GPS
        if self.camera.is_interior():
            self.dashboard.draw(surf, self.screen_w, self.screen_h, self.player, self.steer_drag, maneuver, dest_dist)
        elif self.camera.is_hood():
            self.dashboard.draw_hood(surf, self.screen_w, self.screen_h)

        if self.phase == "arriving":
            font_big = pygame.font.Font(None, 54); txt = font_big.render("Welcome to the City Market!", True, (255, 255, 255))
            bg = pygame.Surface((txt.get_width() + 40, txt.get_height() + 24), pygame.SRCALPHA); bg.fill((48, 125, 85, 210))
            surf.blit(bg, (self.screen_w // 2 - bg.get_width() // 2, self.screen_h // 2 - 60))
            surf.blit(txt, (self.screen_w // 2 - txt.get_width() // 2, self.screen_h // 2 - 46))

        if self.quiz.active: self.quiz.draw(surf, self.screen_w, self.screen_h)
        if self._fog_overlay is None:
            self._fog_overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
            for i in range(self.screen_h): t = i / self.screen_h; a = int(22 * t * t); pygame.draw.line(self._fog_overlay, (200, 210, 220, a), (0, i), (self.screen_w, i))
        surf.blit(self._fog_overlay, (0, 0))
        self.warm_overlay.set_alpha(int(5 + 9 * progress)); surf.blit(self.warm_overlay, (0, 0)); surf.blit(self.vignette, (0, 0))
        if self._crash_flash > 0:
            flash = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA); flash.fill((255, 80, 60, int(85 * self._crash_flash / 0.35))); surf.blit(flash, (0, 0))
        self.fade.draw(surf)