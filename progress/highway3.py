import pygame
import random
import math
import array

# ==========================================
# CONSTANTS
# ==========================================
SKY_TOP = (100, 165, 215)
SKY_BOTTOM = (195, 220, 235)
HILL_FAR = (135, 190, 105)
HILL_NEAR = (90, 160, 80)
ROAD_COLOR = (85, 88, 95)
ROAD_LIGHT = (95, 98, 105)
ROAD_EDGE_COLOR = (235, 235, 235)
CENTER_LINE_COLOR = (245, 200, 55)
LANE_COLOR = (190, 190, 195)
MEDIAN_COLOR = (160, 160, 165)
GUARDRAIL_COLOR = (200, 200, 210)
SKYLINE_FAR = (155, 175, 200)
SKYLINE_NEAR = (115, 140, 170)

SEGMENT_LENGTH = 16.0
RENDER_DISTANCE = 1400.0
ROAD_WIDTH = 2400.0
HALF_ROAD = ROAD_WIDTH / 2
NUM_LANES = 3
LANE_WIDTH = ROAD_WIDTH / NUM_LANES
MEDIAN_WIDTH = 120.0

ACCEL = 260.0
BRAKE = 480.0
FRICTION = 100.0
STEER_SPEED = 850.0
STEER_RETURN = 3.5
CENTRIFUGAL = 0.00028
OFFROAD_FRICTION = 320.0

CHECKPOINT_DISTANCES = [1500, 3100, 4700, 6300]
FINAL_DISTANCE = 7400


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
    scale = (0.03 + 0.97 * depth) * scale_mult
    return depth, scale, y


def project_world(world_x, world_y, world_z, camera_x, camera_y, camera_z,
                  horizon_y, bottom_y, vp_x, bottom_half, width_mult, scale_mult):
    rel_z = world_z - camera_z
    if rel_z <= 0.3:
        return None
    depth, scale, screen_y = project(rel_z, horizon_y, bottom_y, scale_mult)
    scale_x = bottom_half * width_mult / HALF_ROAD
    screen_x = vp_x + (world_x - camera_x) * scale * scale_x
    screen_y -= (world_y - camera_y) * scale * 0.25
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
        pygame.draw.ellipse(surf, (210, 224, 238), (sx, self.y + 5*s, 62*s, 20*s))
        pygame.draw.ellipse(surf, (235, 242, 250), (sx + 4*s, self.y + 2*s, 58*s, 20*s))
        pygame.draw.ellipse(surf, (255, 255, 255), (sx + 16*s, self.y - 9*s, 46*s, 24*s))
        pygame.draw.ellipse(surf, (252, 252, 255), (sx + 36*s, self.y, 50*s, 18*s))
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
        self.mountain_far = self._wavy_points(screen_w * 1.6, horizon_y - 55, 45, 320)
        self.mountain_near = self._wavy_points(screen_w * 1.6, horizon_y - 28, 28, 220)
        self.buildings_far = self._make_skyline(screen_w * 1.6, 80, 180, 24, 44, SKYLINE_FAR)
        self.buildings_near = self._make_skyline(screen_w * 1.6, 50, 240, 20, 38, SKYLINE_NEAR)
        random.seed(88)
        self.hill_far_pts = self._wavy_points(screen_w * 1.6, horizon_y - 8, 14, 150)
        self.hill_near_pts = self._wavy_points(screen_w * 1.6, horizon_y + 14, 18, 180)
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
        self._draw_hill(surf, self.mountain_far, self.w * 1.6, (165, 182, 210), y_extra=y_shift)
        self._draw_hill(surf, self.mountain_near, self.w * 1.6, (138, 158, 192), y_extra=y_shift)
        base_far = hy + 2
        base_near = hy + 6
        self._draw_skyline(surf, self.buildings_far, self.w * 1.6, base_far)
        self._draw_skyline(surf, self.buildings_near, self.w * 1.6, base_near + 6 * scale_boost)
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

    def _add_segment(self, curve=0.0, y=0.0, seg_type="straight"):
        idx = len(self.segments)
        z = idx * SEGMENT_LENGTH
        seg = RoadSegment(idx, z, curve=curve, y=y)
        seg.type = seg_type
        self.segments.append(seg)

    def _generate_road(self):
        def add(count, curve=0.0, y=0.0, seg_type="straight"):
            for _ in range(count):
                self._add_segment(curve, y, seg_type)

        # Entrance straight
        add(35, 0, 0, "straight")
        # Gentle right
        add(30, 0.9, 0, "curve_right")
        add(18, 0, 0, "straight")
        # Checkpoint 1
        add(12, 0, 0, "straight")
        self.segments[-6].has_checkpoint = True
        self.segments[-6].checkpoint_id = 0
        # Gentle left
        add(35, -1.1, 0, "curve_left")
        add(18, 0, 0, "straight")
        # Hill section
        for i in range(25):
            t = i / 25.0
            h = math.sin(t * math.pi) * 160
            add(1, 0, h, "hill")
        add(12, 0, 0, "straight")
        # Checkpoint 2
        add(15, 0, 0, "straight")
        self.segments[-6].has_checkpoint = True
        self.segments[-6].checkpoint_id = 1
        # S-curve (smooth)
        add(25, 1.4, 0, "curve_right")
        add(25, -1.4, 0, "curve_left")
        add(18, 0, 0, "straight")
        # Checkpoint 3
        add(15, 0, 0, "straight")
        self.segments[-6].has_checkpoint = True
        self.segments[-6].checkpoint_id = 2
        # Rolling section
        for i in range(18):
            h = math.sin(i * 0.35) * 50
            add(1, 0.6, h, "curve_right")
        add(12, 0, 0, "straight")
        # Sharp left (guarded)
        add(30, -2.0, 0, "curve_left")
        add(18, 0, 0, "straight")
        # Checkpoint 4
        add(15, 0, 0, "straight")
        self.segments[-6].has_checkpoint = True
        self.segments[-6].checkpoint_id = 3
        # Final approach
        add(25, 0.8, 0, "curve_right")
        add(18, -0.8, 0, "curve_left")
        add(40, 0, 0, "straight")
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
        for seg in self.segments:
            # Trees / bushes - natural spacing, not every segment
            if random.random() < 0.22:
                side = -1 if random.random() < 0.5 else 1
                offset = HALF_ROAD + 250 + random.random() * 600
                seg.sprites.append({
                    'type': random.choice(['pine', 'tree', 'bush', 'rock']),
                    'side': side,
                    'offset': side * offset,
                    'scale': 0.8 + random.random() * 0.5,
                })
            # Curve warning signs before curves
            if seg.curve != 0 and seg.index > 0:
                prev = self.segments[seg.index - 1]
                if prev.curve == 0:
                    side = 1  # Right side of road
                    seg.sprites.append({
                        'type': 'sign_curve',
                        'side': side,
                        'offset': side * (HALF_ROAD + 160),
                        'curve_dir': 'left' if seg.curve < 0 else 'right'
                    })
            # Speed limit signs
            if seg.index % 80 == 0 and seg.index > 10:
                side = 1
                seg.sprites.append({
                    'type': 'sign_speed',
                    'side': side,
                    'offset': side * (HALF_ROAD + 140),
                    'speed': random.choice([60, 80, 100])
                })
            # Streetlights - spaced out
            if seg.index % 35 == 0:
                side = -1 if (seg.index // 35) % 2 == 0 else 1
                seg.sprites.append({
                    'type': 'streetlight',
                    'side': side,
                    'offset': side * (HALF_ROAD + 90)
                })
            # Guardrails on sharp curves
            if abs(seg.curve) > 1.5:
                for side in (-1, 1):
                    seg.sprites.append({
                        'type': 'guardrail',
                        'side': side,
                        'offset': side * (HALF_ROAD + 55)
                    })
            # Exit sign before checkpoint
            if seg.has_checkpoint:
                seg.sprites.append({
                    'type': 'sign_exit',
                    'side': 1,
                    'offset': 1 * (HALF_ROAD + 150),
                })

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
        cam_road_y = self.get_road_y(camera_z)
        num_draw = min(int(RENDER_DISTANCE // SEGMENT_LENGTH) + 6, len(self.segments) - cam_idx)

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
            p_near = project_world(near_x, cam_road_y, near_z, camera_x, camera_y, camera_z,
                                   horizon_y, bottom_y, vp_x, self.bottom_half, width_mult, scale_mult)
            p_far = project_world(far_x, cam_road_y, far_z, camera_x, camera_y, camera_z,
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

        # Draw from far to near
        for data in reversed(seg_data):
            sn, sf = data['sx_near'], data['sx_far']
            yn, yf = data['sy_near'], data['sy_far']
            wn, wf = data['w_near'], data['w_far']
            seg = data['seg']
            dn = data['depth_near']
            scn = data['sc_near']

            # Distance-based atmospheric haze
            haze_t = dn * 0.5
            grass_col = _lerp_color((100, 170, 85), (180, 200, 210), haze_t)
            road_col = _lerp_color(ROAD_COLOR, (150, 155, 160), haze_t)
            median_col = _lerp_color(MEDIAN_COLOR, (170, 170, 175), haze_t)

            # Grass / ground
            grass_left = [(0, yn), (sn - wn, yn), (sf - wf, yf), (0, yf)]
            grass_right = [(sn + wn, yn), (self.screen_w, yn), (self.screen_w, yf), (sf + wf, yf)]
            pygame.draw.polygon(surf, grass_col, grass_left)
            pygame.draw.polygon(surf, grass_col, grass_right)

            # Emergency shoulder (inside edge, before road)
            shoulder_w_near = wn * 0.08
            shoulder_w_far = wf * 0.08
            shoulder_col = _lerp_color((130, 130, 135), (170, 170, 175), haze_t)
            pygame.draw.polygon(surf, shoulder_col, [
                (sn - wn, yn), (sn - wn + shoulder_w_near, yn),
                (sf - wf + shoulder_w_far, yf), (sf - wf, yf)
            ])
            pygame.draw.polygon(surf, shoulder_col, [
                (sn + wn - shoulder_w_near, yn), (sn + wn, yn),
                (sf + wf, yf), (sf + wf - shoulder_w_far, yf)
            ])

            # Road surface
            road_poly = [(sn - wn + shoulder_w_near, yn), (sn + wn - shoulder_w_near, yn),
                         (sf + wf - shoulder_w_far, yf), (sf - wf + shoulder_w_far, yf)]
            pygame.draw.polygon(surf, road_col, road_poly)

            # Lane markings - dashed white, every other segment for stability
            if seg.index % 2 == 0:
                for lane in range(1, NUM_LANES):
                    lx_near = sn - wn + shoulder_w_near + (2 * wn - 2 * shoulder_w_near) * (lane / NUM_LANES)
                    lx_far = sf - wf + shoulder_w_far + (2 * wf - 2 * shoulder_w_far) * (lane / NUM_LANES)
                    mark_w = max(1, int(2.5 * scn))
                    pygame.draw.line(surf, LANE_COLOR, (lx_near, yn), (lx_far, yf), mark_w)

            # Center median / divider
            median_w_near = max(2, int(4 * scn))
            median_w_far = max(1, int(2 * sc_far))
            pygame.draw.polygon(surf, median_col, [
                (sn - median_w_near, yn), (sn + median_w_near, yn),
                (sf + median_w_far, yf), (sf - median_w_far, yf)
            ])

            # Edge lines (solid white, bright)
            edge_w = max(2, int(3.5 * scn))
            pygame.draw.line(surf, ROAD_EDGE_COLOR, (sn - wn, yn), (sf - wf, yf), edge_w)
            pygame.draw.line(surf, ROAD_EDGE_COLOR, (sn + wn, yn), (sf + wf, yf), edge_w)

            # Center double yellow line (highway style)
            if seg.index % 2 == 0:
                center_w = max(2, int(2.5 * scn))
                pygame.draw.line(surf, CENTER_LINE_COLOR, (sn - 2, yn), (sf - 1, yf), center_w)
                pygame.draw.line(surf, CENTER_LINE_COLOR, (sn + 2, yn), (sf + 1, yf), center_w)

            # Reflective road markers (cats eyes) - small dots on lane lines
            if seg.index % 3 == 0 and scn > 0.15:
                for lane in range(1, NUM_LANES):
                    lx = sn - wn + shoulder_w_near + (2 * wn - 2 * shoulder_w_near) * (lane / NUM_LANES)
                    dot_r = max(1, int(2 * scn))
                    pygame.draw.circle(surf, (255, 255, 255), (int(lx), int(yn)), dot_r)

            # Guardrails on sharp curves
            if abs(seg.curve) > 1.5 and scn > 0.1:
                rail_h = max(2, int(8 * scn))
                for side in (-1, 1):
                    rx = sn + side * (wn + 5)
                    rx_far = sf + side * (wf + 3)
                    pygame.draw.line(surf, GUARDRAIL_COLOR, (rx, yn - rail_h), (rx, yn), max(1, int(2 * scn)))

            # Sprites
            for spr in seg.sprites:
                sx = sn + (spr['offset'] / HALF_ROAD) * wn
                sy = yn
                sc = scn
                self._draw_sprite(surf, spr, sx, sy, sc, dn)

            # Checkpoint traffic lights
            if seg.has_checkpoint and not seg.solved:
                self._draw_traffic_light(surf, sn + wn * 1.1, yn, scn, seg.light_state)

    def _draw_sprite(self, surf, spr, sx, sy, scale, depth):
        if depth > 0.75:
            return
        t = spr['type']
        alpha_mod = 1.0 - depth * 0.65
        if alpha_mod < 0.08:
            return
        if t == 'pine':
            self._draw_pine(surf, sx, sy, scale * spr['scale'])
        elif t == 'tree':
            self._draw_tree(surf, sx, sy, scale * spr['scale'])
        elif t == 'bush':
            self._draw_bush(surf, sx, sy, scale * spr['scale'])
        elif t == 'rock':
            self._draw_rock(surf, sx, sy, scale * spr['scale'])
        elif t == 'sign_curve':
            self._draw_sign_curve(surf, sx, sy, scale, spr['curve_dir'])
        elif t == 'sign_speed':
            self._draw_sign_speed(surf, sx, sy, scale, spr['speed'])
        elif t == 'sign_exit':
            self._draw_sign_exit(surf, sx, sy, scale)
        elif t == 'streetlight':
            self._draw_streetlight(surf, sx, sy, scale)
        elif t == 'guardrail':
            self._draw_guardrail_post(surf, sx, sy, scale)

    def _draw_pine(self, surf, sx, sy, scale):
        trunk_h = max(2, int(7 * scale))
        pygame.draw.rect(surf, (95, 65, 42), (sx - max(1, int(2*scale)), sy - trunk_h, max(2, int(5*scale)), trunk_h))
        h = max(7, int(38 * scale))
        w = max(5, int(22 * scale))
        top_y = sy - trunk_h - h
        for i, frac in enumerate((1.0, 0.7, 0.4)):
            tier_w = w * frac
            tier_y = top_y + h * (1 - frac) * 0.85
            col = (48, 125, 62) if i % 2 == 0 else (62, 145, 75)
            pygame.draw.polygon(surf, col, [
                (sx, tier_y), (sx - tier_w/2, tier_y + h*0.4), (sx + tier_w/2, tier_y + h*0.4)
            ])

    def _draw_tree(self, surf, sx, sy, scale):
        trunk_h = max(2, int(16 * scale))
        trunk_w = max(1, int(5 * scale))
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
        w = max(3, int(10 * scale))
        h = max(2, int(6 * scale))
        pygame.draw.polygon(surf, (155, 155, 160), [
            (sx - w, sy), (sx - w*0.3, sy - h), (sx + w*0.5, sy - h*0.8), (sx + w, sy)
        ])

    def _draw_sign_curve(self, surf, sx, sy, scale, direction):
        w = max(5, int(18 * scale))
        h = max(6, int(22 * scale))
        pygame.draw.rect(surf, (255, 210, 60), (sx - w, sy - h*2.2, w*2, h), border_radius=max(2, int(3*scale)))
        pygame.draw.rect(surf, (30, 30, 35), (sx - w, sy - h*2.2, w*2, h), max(1, int(1.5*scale)), border_radius=max(2, int(3*scale)))
        if direction == 'left':
            pygame.draw.polygon(surf, (30, 30, 35), [
                (sx + w*0.5, sy - h*2.0), (sx - w*0.3, sy - h*1.6), (sx + w*0.5, sy - h*1.2)
            ])
        else:
            pygame.draw.polygon(surf, (30, 30, 35), [
                (sx - w*0.5, sy - h*2.0), (sx + w*0.3, sy - h*1.6), (sx - w*0.5, sy - h*1.2)
            ])

    def _draw_sign_speed(self, surf, sx, sy, scale, speed):
        w = max(5, int(16 * scale))
        h = max(6, int(20 * scale))
        pygame.draw.rect(surf, (255, 255, 255), (sx - w, sy - h*2.2, w*2, h), border_radius=max(2, int(3*scale)))
        pygame.draw.rect(surf, (200, 50, 50), (sx - w, sy - h*2.2, w*2, h), max(1, int(2*scale)), border_radius=max(2, int(3*scale)))
        if scale > 0.4:
            font = pygame.font.Font(None, max(10, int(14 * scale)))
            txt = font.render(str(speed), True, (30, 30, 35))
            surf.blit(txt, (sx - txt.get_width()//2, int(sy - h*1.9)))

    def _draw_sign_exit(self, surf, sx, sy, scale):
        w = max(6, int(20 * scale))
        h = max(5, int(16 * scale))
        pygame.draw.rect(surf, (50, 100, 60), (sx - w, sy - h*2.2, w*2, h), border_radius=max(2, int(3*scale)))
        pygame.draw.rect(surf, (255, 255, 255), (sx - w, sy - h*2.2, w*2, h), max(1, int(1.5*scale)), border_radius=max(2, int(3*scale)))
        if scale > 0.4:
            font = pygame.font.Font(None, max(9, int(12 * scale)))
            txt = font.render("EXIT", True, (255, 255, 255))
            surf.blit(txt, (sx - txt.get_width()//2, int(sy - h*1.9)))

    def _draw_streetlight(self, surf, sx, sy, scale):
        h = max(10, int(45 * scale))
        pygame.draw.line(surf, (115, 115, 125), (sx, sy), (sx, sy - h), max(1, int(2.5*scale)))
        pygame.draw.ellipse(surf, (255, 250, 220), (sx - 5*scale, sy - h - 4*scale, 10*scale, 6*scale))

    def _draw_guardrail_post(self, surf, sx, sy, scale):
        h = max(3, int(10 * scale))
        pygame.draw.line(surf, (190, 190, 200), (sx, sy - h), (sx, sy), max(1, int(2.5*scale)))

    def _draw_traffic_light(self, surf, sx, sy, scale, state):
        pole_h = max(12, int(70 * scale))
        pygame.draw.line(surf, (70, 74, 80), (sx, sy), (sx, sy - pole_h), max(1, int(3.5*scale)))
        box_w = max(6, int(18 * scale))
        box_h = max(7, int(30 * scale))
        box = pygame.Rect(sx - box_w/2, sy - pole_h - box_h + 4, box_w, box_h)
        pygame.draw.rect(surf, (40, 43, 48), box, border_radius=max(2, int(4*scale)))
        r_rad = max(2, int(box_w * 0.28))
        pygame.draw.circle(surf, (250, 60, 50) if state == "red" else (90, 40, 40),
                           (int(sx), int(box.y + box_h * 0.3)), r_rad)
        pygame.draw.circle(surf, (60, 220, 90) if state == "green" else (45, 85, 55),
                           (int(sx), int(box.y + box_h * 0.72)), r_rad)


# ==========================================
# VEHICLE BASE
# ==========================================
class Vehicle:
    def __init__(self, x, z, speed, color, car_type="sedan"):
        self.x = x
        self.z = z
        self.y = 0
        self.speed = speed
        self.color = color
        self.car_type = car_type
        self.width = 360.0
        self.length = 42.0
        self.bounce_t = 0.0
        self.bounce = 0.0
        self.braking = False

    def update_physics(self, dt, road):
        self.y = road.get_road_y(self.z)
        self.bounce_t += dt * (1.5 + self.speed / 70.0)
        self.bounce = math.sin(self.bounce_t * 5) * (1.2 if self.speed > 5 else 0.15)

    def draw_shadow(self, surf, cx, cy, scale):
        sh_w = max(5, int(34 * scale))
        sh_h = max(3, int(14 * scale))
        shadow = pygame.Surface((sh_w * 2, sh_h * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (8, 12, 8, 90), (0, 0, sh_w * 2, sh_h * 2))
        surf.blit(shadow, (cx - sh_w, cy - sh_h // 2))

    def draw_rear(self, surf, cx, cy, scale, color_override=None, depth=0.0):
        if scale < 0.25:
            return
        col = color_override or self.color
        s = scale * 1.7
        self.draw_shadow(surf, cx, cy, s)

        if self.car_type == "sedan":
            self._draw_sedan_rear(surf, cx, cy, s, col, depth)
        elif self.car_type == "truck":
            self._draw_truck_rear(surf, cx, cy, s, col, depth)
        elif self.car_type == "van":
            self._draw_van_rear(surf, cx, cy, s, col, depth)
        else:
            self._draw_sedan_rear(surf, cx, cy, s, col, depth)

    def _draw_sedan_rear(self, surf, cx, cy, s, col, depth):
        body_w = max(10, int(44 * s))
        body_h = max(6, int(26 * s))
        body = pygame.Rect(cx - body_w//2, cy - body_h, body_w, body_h)
        pygame.draw.rect(surf, col, body, border_radius=max(3, int(5*s)))
        pygame.draw.rect(surf, (25, 28, 32), body, max(1, int(2*s)), border_radius=max(3, int(5*s)))
        # Roof
        roof = pygame.Rect(cx - body_w//3, cy - body_h + 2, body_w*2//3, max(4, int(10*s)))
        pygame.draw.rect(surf, (45, 55, 68), roof, border_radius=max(2, int(3*s)))
        # Taillights with glow
        glow = pygame.Surface((body_w * 2 + 10, body_h + 10), pygame.SRCALPHA)
        for side in (-1, 1):
            lx = cx + side * body_w * 0.38
            ly = cy - body_h * 0.3
            pygame.draw.ellipse(glow, (255, 50, 30, 90), (int(lx - cx + body_w + 5 - 8*s), int(ly - cy + 5), int(16*s), int(12*s)))
            pygame.draw.circle(surf, (255, 55, 35), (int(lx), int(ly)), max(3, int(7*s)))
            pygame.draw.circle(surf, (255, 200, 180), (int(lx), int(ly)), max(2, int(3*s)))
        surf.blit(glow, (cx - body_w - 5, cy - 5))
        if self.braking:
            for side in (-1, 1):
                lx = cx + side * body_w * 0.38
                pygame.draw.circle(surf, (255, 255, 255), (int(lx), int(cy - body_h * 0.3)), max(2, int(4*s)))
        # Wheels
        for side in (-1, 1):
            wx = cx + side * body_w * 0.44
            pygame.draw.circle(surf, (18, 18, 22), (int(wx), int(cy + 2)), max(3, int(8*s)))
            pygame.draw.circle(surf, (170, 170, 178), (int(wx), int(cy + 2)), max(2, int(3.5*s)))
        # Plate
        plate_w = max(6, int(18 * s))
        plate_h = max(2, int(6 * s))
        plate = pygame.Rect(cx - plate_w//2, cy - 1, plate_w, plate_h)
        pygame.draw.rect(surf, (240, 235, 220), plate, border_radius=2)

    def _draw_truck_rear(self, surf, cx, cy, s, col, depth):
        # Cargo box
        box_w = max(10, int(46 * s))
        box_h = max(6, int(30 * s))
        box = pygame.Rect(cx - box_w//2, cy - box_h, box_w, box_h)
        pygame.draw.rect(surf, (130, 95, 55), box, border_radius=max(2, int(4*s)))
        pygame.draw.rect(surf, (35, 30, 25), box, max(1, int(2*s)), border_radius=max(2, int(4*s)))
        for i in range(3):
            gx = box.x + 10 + i * (box.w - 20) / 2
            pygame.draw.line(surf, (95, 68, 38), (gx, box.y + 4), (gx, box.bottom - 4), max(1, int(2*s)))
        # Cab below
        cab = pygame.Rect(cx - int(22*s), cy - int(8*s), int(44*s), int(14*s))
        pygame.draw.rect(surf, col, cab, border_radius=max(2, int(4*s)))
        pygame.draw.rect(surf, (25, 28, 32), cab, max(1, int(2*s)), border_radius=max(2, int(4*s)))
        # Lights
        for side in (-1, 1):
            lx = cx + side * int(14*s)
            pygame.draw.circle(surf, (255, 50, 30), (int(lx), int(cy - int(4*s))), max(3, int(6*s)))
            pygame.draw.circle(surf, (255, 200, 180), (int(lx), int(cy - int(4*s))), max(2, int(3*s)))
        if self.braking:
            for side in (-1, 1):
                lx = cx + side * int(14*s)
                pygame.draw.circle(surf, (255, 255, 255), (int(lx), int(cy - int(4*s))), max(2, int(4*s)))
        # Wheels
        for side in (-1, 1):
            wx = cx + side * int(24*s)
            pygame.draw.circle(surf, (18, 18, 22), (int(wx), int(cy + int(6*s))), max(4, int(9*s)))
            pygame.draw.circle(surf, (170, 170, 178), (int(wx), int(cy + int(6*s))), max(2, int(4*s)))

    def _draw_van_rear(self, surf, cx, cy, s, col, depth):
        body_w = max(10, int(42 * s))
        body_h = max(7, int(32 * s))
        body = pygame.Rect(cx - body_w//2, cy - body_h, body_w, body_h)
        pygame.draw.rect(surf, col, body, border_radius=max(2, int(4*s)))
        pygame.draw.rect(surf, (25, 28, 32), body, max(1, int(2*s)), border_radius=max(2, int(4*s)))
        # Window
        win = pygame.Rect(cx - body_w//3, cy - body_h + 3, body_w*2//3, max(5, int(12*s)))
        pygame.draw.rect(surf, (55, 65, 78), win, border_radius=max(2, int(3*s)))
        # Lights
        for side in (-1, 1):
            lx = cx + side * body_w * 0.38
            pygame.draw.circle(surf, (255, 50, 30), (int(lx), int(cy - body_h * 0.25)), max(3, int(7*s)))
            pygame.draw.circle(surf, (255, 200, 180), (int(lx), int(cy - body_h * 0.25)), max(2, int(3*s)))
        if self.braking:
            for side in (-1, 1):
                lx = cx + side * body_w * 0.38
                pygame.draw.circle(surf, (255, 255, 255), (int(lx), int(cy - body_h * 0.25)), max(2, int(4*s)))
        # Wheels
        for side in (-1, 1):
            wx = cx + side * body_w * 0.42
            pygame.draw.circle(surf, (18, 18, 22), (int(wx), int(cy + 2)), max(3, int(8*s)))
            pygame.draw.circle(surf, (170, 170, 178), (int(wx), int(cy + 2)), max(2, int(3.5*s)))
        # Plate
        plate = pygame.Rect(cx - int(10*s), cy - 1, int(20*s), int(6*s))
        pygame.draw.rect(surf, (240, 235, 220), plate, border_radius=2)


# ==========================================
# PLAYER VEHICLE
# ==========================================
class PlayerVehicle(Vehicle):
    def __init__(self):
        super().__init__(0, 0, 0, (55, 115, 65), "truck")
        self.max_speed = 300
        self.steer_angle = 0.0
        self.offroad = False
        self.crash_timer = 0.0

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

        steer_input = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            steer_input = -1.0
        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            steer_input = 1.0

        if steer_input != 0:
            self.steer_angle += steer_input * 2.8 * dt
            self.steer_angle = max(-1.0, min(1.0, self.steer_angle))
        else:
            self.steer_angle *= max(0, 1 - STEER_RETURN * dt)

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

    def update(self, dt, road):
        if self.crash_timer <= 0:
            self.z += self.speed * dt
        self.update_physics(dt, road)

    def draw(self, surf, road, camera_x, camera_y, camera_z, horizon_y, bottom_y, vp_x, bottom_half, width_mult, scale_mult):
        p = project_world(self.x, self.y, self.z, camera_x, camera_y, camera_z,
                          horizon_y, bottom_y, vp_x, bottom_half, width_mult, scale_mult)
        if p is None:
            return
        cx, cy, scale, depth = p
        cy += self.bounce
        s = scale * 1.9
        self.draw_shadow(surf, cx, cy, s)

        # Player truck is bigger and more detailed
        # Cargo bed
        bed = pygame.Rect(cx - int(32*s), cy - int(44*s), int(64*s), int(36*s))
        pygame.draw.rect(surf, (135, 100, 58), bed, border_radius=max(3, int(5*s)))
        pygame.draw.rect(surf, (30, 28, 25), bed, max(1, int(2.5*s)), border_radius=max(3, int(5*s)))
        for i in range(4):
            gx = bed.x + 10 + i * (bed.w - 20) / 3
            pygame.draw.line(surf, (100, 72, 40), (gx, bed.y + 4), (gx, bed.bottom - 4), max(1, int(2*s)))
        # Crates
        for fx, fy, col in [(-16, -12, (215, 65, 55)), (-4, -16, (240, 155, 45)),
                             (10, -12, (95, 175, 75)), (22, -16, (215, 65, 55))]:
            pygame.draw.circle(surf, col, (int(cx + fx*s), int(bed.y + fy*s)), max(3, int(8*s)))
            pygame.draw.circle(surf, tuple(min(255, c+45) for c in col), (int(cx + (fx-2)*s), int(bed.y + (fy-2)*s)), max(2, int(3.5*s)))
        # Cab
        cab = pygame.Rect(cx - int(24*s), cy - int(12*s), int(48*s), int(20*s))
        pygame.draw.rect(surf, self.color, cab, border_radius=max(3, int(5*s)))
        pygame.draw.rect(surf, (30, 28, 25), cab, max(1, int(2.5*s)), border_radius=max(3, int(5*s)))
        # Taillights with glow
        glow = pygame.Surface((int(60*s), int(35*s)), pygame.SRCALPHA)
        for wx in (cx - int(14*s), cx + int(14*s)):
            pygame.draw.ellipse(glow, (255, 45, 25, 100), (int(wx - cx + 30*s - 10*s), int(5*s), int(20*s), int(15*s)))
            pygame.draw.circle(surf, (255, 45, 25), (int(wx), int(cy - int(4*s))), max(3, int(6*s)))
            pygame.draw.circle(surf, (255, 210, 190), (int(wx), int(cy - int(4*s))), max(2, int(3*s)))
        surf.blit(glow, (cx - int(30*s), cy - int(20*s)))
        if self.braking:
            for wx in (cx - int(14*s), cx + int(14*s)):
                pygame.draw.circle(surf, (255, 255, 255), (int(wx), int(cy - int(4*s))), max(2, int(4*s)))
        # Wheels
        for wx in (cx - int(26*s), cx + int(22*s)):
            pygame.draw.circle(surf, (18, 18, 22), (int(wx), int(cy + int(8*s))), max(4, int(11*s)))
            pygame.draw.circle(surf, (200, 200, 205), (int(wx), int(cy + int(8*s))), max(2, int(4.5*s)))
        # Plate
        plate = pygame.Rect(cx - int(12*s), cy + int(3*s), int(24*s), int(7*s))
        pygame.draw.rect(surf, (240, 235, 220), plate, border_radius=2)
        pygame.draw.rect(surf, (40, 80, 50), plate, 1, border_radius=2)
        # Headlight beams
        if scale > 0.2:
            beam = pygame.Surface((int(90*s), int(55*s)), pygame.SRCALPHA)
            pygame.draw.ellipse(beam, (255, 250, 200, 22), (0, 0, int(90*s), int(55*s)))
            surf.blit(beam, (cx - int(45*s), cy - int(25*s)))


# ==========================================
# AI VEHICLE
# ==========================================
class AIVehicle(Vehicle):
    def __init__(self, z, lane, speed, road):
        road_x = road.get_road_x(z)
        x = road_x + (lane - 1) * LANE_WIDTH
        car_types = ["sedan", "sedan", "sedan", "truck", "van"]
        colors = [(200, 55, 55), (55, 95, 200), (210, 185, 50), (165, 65, 180), (60, 170, 150), (225, 115, 45), (80, 80, 90)]
        car_type = random.choice(car_types)
        super().__init__(x, z, speed, random.choice(colors), car_type)
        self.lane = lane
        self.target_speed = speed
        self.length = 40.0
        self.width = 350.0
        self.braking_for_light = False

    def update(self, dt, road, player, all_cars):
        seg = road.find_segment(self.z)
        road_x = road.get_road_x(self.z)
        self.x -= seg.curve * self.speed * CENTRIFUGAL * dt
        target_x = road_x + (self.lane - 1) * LANE_WIDTH
        self.x += (target_x - self.x) * 2.5 * dt

        self.braking = False
        for other in all_cars:
            if other is self:
                continue
            dz = other.z - self.z
            if 0 < dz < 160 and abs(other.x - self.x) < 400:
                self.speed = max(0, min(self.speed, other.speed - 25))
                self.braking = True
                if dz < 80:
                    if self.x < other.x and self.lane > 0:
                        self.lane -= 1
                    elif self.x > other.x and self.lane < NUM_LANES - 1:
                        self.lane += 1

        self.braking_for_light = False
        for s in road.segments:
            if s.has_checkpoint and s.light_state == "red" and not s.solved:
                dz = s.z - self.z
                if 0 < dz < 280:
                    self.speed = max(0, self.speed - 450 * dt)
                    self.braking = True
                    self.braking_for_light = True

        if not self.braking_for_light:
            if self.speed < self.target_speed:
                self.speed += 140 * dt
            elif self.speed > self.target_speed:
                self.speed -= 45 * dt

        self.z += self.speed * dt
        self.update_physics(dt, road)

        if self.z < player.z - 900:
            return False
        return True

    def draw(self, surf, road, camera_x, camera_y, camera_z, horizon_y, bottom_y, vp_x, bottom_half, width_mult, scale_mult):
        p = project_world(self.x, self.y, self.z, camera_x, camera_y, camera_z,
                          horizon_y, bottom_y, vp_x, bottom_half, width_mult, scale_mult)
        if p is None:
            return
        cx, cy, scale, depth = p
        cy += self.bounce
        self.draw_rear(surf, cx, cy, scale * 1.6, self.color, depth)


# ==========================================
# CAMERA SYSTEM (3 POVs)
# ==========================================
class CameraSystem:
    POV_FIRST = 0
    POV_CLOSE = 1
    POV_FAR = 2

    def __init__(self):
        self.pov = self.POV_CLOSE
        self.x = 0.0
        self.y = 0.0
        self.z = -200.0
        self.pitch = 0.0
        self.shake_timer = 0.0
        self.shake_mag = 0.0
        self._pov_label_timer = 0.0
        self._pov_labels = ["FIRST PERSON", "CLOSE CHASE", "FAR CHASE"]

    def cycle_pov(self):
        self.pov = (self.pov + 1) % 3
        self._pov_label_timer = 2.0

    def get_pov_label(self):
        return self._pov_labels[self.pov]

    def add_shake(self, magnitude, duration):
        self.shake_timer = duration
        self.shake_mag = magnitude

    def update(self, dt, player):
        if self._pov_label_timer > 0:
            self._pov_label_timer -= dt

        # POV-specific targets
        if self.pov == self.POV_FIRST:
            target_z = player.z + 15.0
            target_x = player.x
            target_y = player.y + 25.0
            lag = 12.0
        elif self.pov == self.POV_CLOSE:
            target_z = player.z - 160.0
            target_x = player.x
            target_y = player.y + 45.0
            lag = 5.5
        else:  # FAR
            target_z = player.z - 340.0
            target_x = player.x
            target_y = player.y + 90.0
            lag = 4.0

        self.z += (target_z - self.z) * min(1.0, lag * dt)
        self.x += (target_x - self.x) * min(1.0, lag * 0.7 * dt)
        self.y += (target_y - self.y) * min(1.0, lag * 0.6 * dt)

        if self.shake_timer > 0:
            self.shake_timer -= dt
            self.x += random.uniform(-self.shake_mag, self.shake_mag)
            self.y += random.uniform(-self.shake_mag, self.shake_mag)
            self.shake_mag *= max(0, 1 - 4.0 * dt)

    def is_first_person(self):
        return self.pov == self.POV_FIRST


# ==========================================
# DASHBOARD (First Person)
# ==========================================
class Dashboard:
    def __init__(self):
        pass

    def draw(self, surf, screen_w, screen_h, player):
        # Dashboard at bottom
        dash_h = int(screen_h * 0.22)
        dash_y = screen_h - dash_h

        # Windshield top tint (subtle)
        tint_h = max(35, int(screen_h * 0.08))
        tint = pygame.Surface((screen_w, tint_h), pygame.SRCALPHA)
        for i in range(tint_h):
            a = int(45 * (1 - i / tint_h))
            pygame.draw.line(tint, (45, 65, 85, a), (0, i), (screen_w, i))
        surf.blit(tint, (0, 0))

        # Sun glare (subtle, moving slowly)
        glare_cx = int(screen_w * (0.3 + 0.04 * math.sin(player.bounce_t * 0.08)))
        glow = pygame.Surface((300, 100), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255, 240, 200, 18), (0, 0, 300, 100))
        pygame.draw.ellipse(glow, (255, 250, 220, 30), (50, 20, 200, 60))
        surf.blit(glow, (glare_cx - 150, tint_h - 25))

        # Dashboard body (warm dark leather)
        for i in range(dash_h):
            t = i / max(1, dash_h - 1)
            r = int(_lerp(105, 42, t))
            g = int(_lerp(82, 32, t))
            b = int(_lerp(62, 24, t))
            pygame.draw.line(surf, (r, g, b), (0, dash_y + i), (screen_w, dash_y + i))

        # Wood trim
        wood_y = dash_y + 14
        pygame.draw.rect(surf, (108, 72, 42), (0, wood_y, screen_w, 7))
        pygame.draw.line(surf, (255, 222, 172), (0, wood_y + 1), (screen_w, wood_y + 1), 1)
        pygame.draw.line(surf, (200, 200, 205), (0, wood_y + 8), (screen_w, wood_y + 8), 1)

        # Steering wheel
        wheel_cx = screen_w / 2
        wheel_cy = screen_h - dash_h * 0.05
        wheel_r = int(screen_w * 0.11)
        pygame.draw.circle(surf, (12, 10, 9), (int(wheel_cx), int(wheel_cy)), wheel_r + 4)
        pygame.draw.circle(surf, (38, 34, 31), (int(wheel_cx), int(wheel_cy)), wheel_r, width=max(7, wheel_r // 5))
        pygame.draw.circle(surf, (68, 61, 55), (int(wheel_cx), int(wheel_cy)), wheel_r - 3, width=max(2, wheel_r // 16))
        for ang in (200, 340, 90):
            rad = math.radians(ang)
            end = (wheel_cx + math.cos(rad) * wheel_r * 0.92, wheel_cy + math.sin(rad) * wheel_r * 0.92)
            pygame.draw.line(surf, (24, 22, 20), (wheel_cx, wheel_cy), end, max(4, wheel_r // 9))
            pygame.draw.line(surf, (165, 165, 172), (wheel_cx, wheel_cy), end, max(1, wheel_r // 24))
        hub_r = max(6, wheel_r // 6)
        pygame.draw.circle(surf, (42, 38, 35), (int(wheel_cx), int(wheel_cy)), hub_r)
        pygame.draw.circle(surf, (210, 170, 65), (int(wheel_cx), int(wheel_cy)), max(3, hub_r // 2))

        # Hands on wheel
        for side in (-1, 1):
            hx = wheel_cx + side * wheel_r * 0.95
            hy = wheel_cy + wheel_r * 0.1
            pygame.draw.ellipse(surf, (58, 45, 34), (hx - 16, hy - 12, 32, 26))
            pygame.draw.ellipse(surf, (72, 58, 44), (hx - 16 + side * 2, hy - 14, 22, 18))

        # Gauges
        self._draw_gauge(surf, wheel_cx - wheel_r * 2.1, wheel_cy - wheel_r * 0.05, max(30, int(wheel_r * 0.8)),
                        player.speed, 350, "km/h", (250, 100, 80))
        rpm = 1000 + (player.speed / max(1.0, 300)) * 4500
        self._draw_gauge(surf, wheel_cx + wheel_r * 2.1, wheel_cy - wheel_r * 0.05, max(30, int(wheel_r * 0.8)),
                        rpm, 6000, "rpm", (90, 170, 240))

        # Center GPS
        cons_w = int(screen_w * 0.14)
        cons_h = int(dash_h * 0.55)
        cons_x = screen_w // 2 - cons_w // 2
        cons_y = dash_y + int(dash_h * 0.2)
        pygame.draw.rect(surf, (22, 20, 18), (cons_x - 4, cons_y - 4, cons_w + 8, cons_h + 8), border_radius=8)
        nav = pygame.Surface((cons_w, cons_h))
        nav.fill((28, 42, 58))
        pygame.draw.line(nav, (85, 195, 115), (cons_w // 2, cons_h - 4), (cons_w // 2, cons_h // 2), 3)
        pygame.draw.line(nav, (85, 195, 115), (cons_w // 2, cons_h // 2), (int(cons_w * 0.75), cons_h // 3), 3)
        pygame.draw.circle(nav, (250, 200, 80), (int(cons_w * 0.75), cons_h // 3), 4)
        ay = cons_h - 10 - ((player.bounce_t * 6) % (cons_h * 0.35))
        pygame.draw.polygon(nav, (255, 255, 255), [
            (cons_w // 2, ay - 6), (cons_w // 2 - 5, ay + 4), (cons_w // 2 + 5, ay + 4)
        ])
        surf.blit(nav, (cons_x, cons_y))

        # A-pillars
        pillar_w = int(screen_w * 0.045)
        pillar_col = (48, 42, 36)
        accent = (65, 118, 72)
        left_pillar = [(0, 0), (pillar_w, 0), (pillar_w * 0.4, dash_y), (0, dash_y)]
        right_pillar = [(screen_w - pillar_w, 0), (screen_w, 0), (screen_w, dash_y), (screen_w - pillar_w * 0.4, dash_y)]
        pygame.draw.polygon(surf, pillar_col, left_pillar)
        pygame.draw.polygon(surf, pillar_col, right_pillar)
        pygame.draw.line(surf, accent, (pillar_w * 0.15, 8), (pillar_w * 0.5, dash_y - 8), 4)
        pygame.draw.line(surf, accent, (screen_w - pillar_w * 0.15, 8), (screen_w - pillar_w * 0.5, dash_y - 8), 4)

        # Rear-view mirror
        mirror_w = int(screen_w * 0.12)
        mirror_h = 28
        mirror_rect = pygame.Rect(screen_w // 2 - mirror_w // 2, 10, mirror_w, mirror_h)
        pygame.draw.line(surf, (28, 26, 23), (screen_w // 2, 0), (screen_w // 2, mirror_rect.y), 3)
        pygame.draw.rect(surf, (28, 26, 23), mirror_rect, border_radius=6)
        glass_rect = mirror_rect.inflate(-6, -8)
        if glass_rect.width > 0 and glass_rect.height > 0:
            for i in range(glass_rect.height):
                t = i / max(1, glass_rect.height - 1)
                r = int(_lerp(145, 190, t))
                g = int(_lerp(175, 210, t))
                b = int(_lerp(190, 220, t))
                pygame.draw.line(surf, (r, g, b), (glass_rect.x, glass_rect.y + i), (glass_rect.right, glass_rect.y + i))
        pygame.draw.rect(surf, (12, 11, 10), mirror_rect, 2, border_radius=6)

    def _draw_gauge(self, surf, cx, cy, r, value, max_value, unit, needle_color):
        if cx < r + 8 or cx > surf.get_width() - r - 8:
            return
        g = pygame.Surface((r * 2 + 16, r * 2 + 16), pygame.SRCALPHA)
        pygame.draw.circle(g, (needle_color[0], needle_color[1], needle_color[2], 22), (r + 8, r + 8), r + 8)
        surf.blit(g, (int(cx) - r - 8, int(cy) - r - 8))
        pygame.draw.circle(surf, (12, 11, 10), (int(cx), int(cy)), r + 4)
        pygame.draw.circle(surf, (22, 24, 26), (int(cx), int(cy)), r)
        pygame.draw.circle(surf, (85, 210, 150), (int(cx), int(cy)), r, 2)
        start_ang, end_ang = 135, 405
        for tick in range(6):
            a = math.radians(start_ang + (end_ang - start_ang) * tick / 5)
            pygame.draw.line(surf, (205, 210, 210),
                             (cx + math.cos(a) * r * 0.82, cy + math.sin(a) * r * 0.82),
                             (cx + math.cos(a) * r * 0.95, cy + math.sin(a) * r * 0.95), 2)
        frac = max(0.0, min(1.0, value / max_value))
        needle_ang = math.radians(start_ang + (end_ang - start_ang) * frac)
        nx = cx + math.cos(needle_ang) * r * 0.72
        ny = cy + math.sin(needle_ang) * r * 0.72
        pygame.draw.line(surf, needle_color, (cx, cy), (nx, ny), 3)
        pygame.draw.line(surf, (255, 235, 220), (cx, cy), (nx, ny), 1)
        pygame.draw.circle(surf, (205, 205, 205), (int(cx), int(cy)), 4)
        font_g = pygame.font.Font(None, max(14, int(r * 0.5)))
        val_txt = font_g.render(str(int(value)), True, (235, 235, 235))
        surf.blit(val_txt, (cx - val_txt.get_width() / 2, cy + r * 0.28))
        font_lbl = pygame.font.Font(None, 14)
        lbl_txt = font_lbl.render(unit, True, (140, 200, 170))
        surf.blit(lbl_txt, (cx - lbl_txt.get_width() / 2, cy + r * 0.28 + val_txt.get_height() - 2))


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
                self.question_text = f"{a} x {b} = ?"
                self.answer_value = a * b
            else:
                product = a * b
                self.question_text = f"{product} / {b} = ?"
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
        overlay.fill((0, 0, 0, 130))
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
        total_w_dots = self.total_checkpoints * (dot_r * 2 + 10) - 10
        dot_x = px + panel_w // 2 - total_w_dots // 2 + dot_r
        for i in range(self.total_checkpoints):
            color = (60, 180, 90) if i < self.checkpoint_index else \
                    (255, 200, 60) if i == self.checkpoint_index else (210, 210, 210)
            pygame.draw.circle(surf, color, (dot_x, py + 46), dot_r)
            dot_x += dot_r * 2 + 10
        font_title = pygame.font.Font(None, 34)
        title = font_title.render("Traffic Light Math Challenge", True, (40, 110, 75))
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
            fb = font_q.render("Correct! Light turning green...", True, (40, 150, 80))
            surf.blit(fb, (px + panel_w // 2 - fb.get_width() // 2, py + panel_h - 34))
        elif self.feedback == "wrong":
            fb = font_q.render("Not quite - try again!", True, (190, 70, 70))
            surf.blit(fb, (px + panel_w // 2 - fb.get_width() // 2, py + panel_h - 34))
        self.submit_button_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

    def handle_click(self, pos):
        if self.active and self.feedback != "correct":
            if self.submit_button_rect.collidepoint(pos):
                self.submit()


# ==========================================
# UI / HUD
# ==========================================
class UI:
    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.font = pygame.font.Font(None, 26)
        self.font_big = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 20)
        self.show_help = True
        self.help_timer = 10.0

    def draw(self, surf, player, road, cars, phase, camera, checkpoint_seg=None):
        # Speedometer
        speed_kmh = int(player.speed * 0.8)
        speed_txt = self.font_big.render(f"{speed_kmh} km/h", True, (255, 255, 255))
        bg = pygame.Surface((speed_txt.get_width() + 24, speed_txt.get_height() + 14), pygame.SRCALPHA)
        bg.fill((12, 12, 16, 200))
        surf.blit(bg, (16, 16))
        surf.blit(speed_txt, (28, 22))

        # Progress bar
        bar_w = self.screen_w - 100
        bar_x, bar_y = 50, self.screen_h - 32
        pygame.draw.rect(surf, (35, 35, 40), (bar_x, bar_y, bar_w, 16), border_radius=8)
        pygame.draw.rect(surf, (95, 100, 105), (bar_x, bar_y, bar_w, 16), 2, border_radius=8)
        progress = max(0.0, min(1.0, player.z / FINAL_DISTANCE))
        pygame.draw.rect(surf, (75, 205, 125), (bar_x, bar_y, int(bar_w * progress), 16), border_radius=8)

        for cp in CHECKPOINT_DISTANCES:
            cp_prog = cp / FINAL_DISTANCE
            cx = bar_x + int(bar_w * cp_prog)
            col = (220, 220, 220)
            for seg in road.segments:
                if seg.has_checkpoint and abs(seg.z - cp) < SEGMENT_LENGTH and seg.solved:
                    col = (60, 200, 90)
                    break
            pygame.draw.circle(surf, col, (cx, bar_y + 8), 7)
            pygame.draw.circle(surf, (85, 85, 90), (cx, bar_y + 8), 7, 1)

        # Phase label
        label_text = {
            "entering": "Pulling onto the highway...",
            "cruising": "Drive to the city market",
            "braking": "Slowing for checkpoint...",
            "stopped": "Stopped at checkpoint - solve the math problem!",
            "resuming": "Light green - moving on!",
            "arriving": "Almost at the city...",
        }.get(phase, "")
        if label_text:
            txt = self.font.render(label_text, True, (45, 45, 50))
            bg2 = pygame.Surface((txt.get_width() + 24, txt.get_height() + 12))
            bg2.fill((255, 255, 255))
            bg2.set_alpha(220)
            surf.blit(bg2, (self.screen_w // 2 - bg2.get_width() // 2, 48))
            surf.blit(txt, (self.screen_w // 2 - txt.get_width() // 2, 54))

        # POV indicator
        if camera._pov_label_timer > 0:
            alpha = int(255 * min(1.0, camera._pov_label_timer / 0.5))
            pov_txt = self.font_big.render(camera.get_pov_label(), True, (255, 255, 255))
            pov_bg = pygame.Surface((pov_txt.get_width() + 30, pov_txt.get_height() + 16), pygame.SRCALPHA)
            pov_bg.fill((20, 20, 28, alpha))
            surf.blit(pov_bg, (self.screen_w // 2 - pov_bg.get_width() // 2, 90))
            surf.blit(pov_txt, (self.screen_w // 2 - pov_txt.get_width() // 2, 98))

        # Mini-map
        self._draw_minimap(surf, player, road, cars)

        # Traffic count
        car_txt = self.font_small.render(f"Traffic: {len(cars)} cars", True, (195, 195, 195))
        cbg = pygame.Surface((car_txt.get_width() + 12, car_txt.get_height() + 6), pygame.SRCALPHA)
        cbg.fill((12, 12, 16, 200))
        surf.blit(cbg, (16, 60))
        surf.blit(car_txt, (22, 63))

        # Controls help
        if self.show_help:
            self.help_timer -= 0.016
            if self.help_timer <= 0:
                self.show_help = False
            hint = self.font_small.render("W/S = Gas/Brake  |  A/D = Steer  |  C = Change View  |  Space = Handbrake", True, (255, 255, 255))
            hbg = pygame.Surface((hint.get_width() + 20, hint.get_height() + 10), pygame.SRCALPHA)
            hbg.fill((12, 12, 16, 200))
            surf.blit(hbg, (self.screen_w // 2 - hbg.get_width() // 2, self.screen_h - 58))
            surf.blit(hint, (self.screen_w // 2 - hint.get_width() // 2, self.screen_h - 54))

    def _draw_minimap(self, surf, player, road, cars):
        mw, mh = 150, 100
        mx = self.screen_w - mw - 16
        my = 16
        pygame.draw.rect(surf, (12, 12, 16, 200), (mx, my, mw, mh), border_radius=8)
        pygame.draw.rect(surf, (75, 75, 85), (mx, my, mw, mh), 2, border_radius=8)

        cam_idx = int(player.z // SEGMENT_LENGTH)
        start_idx = max(0, cam_idx - 25)
        end_idx = min(len(road.segments), cam_idx + 55)
        px = mx + mw // 2
        py = my + mh - 12
        scale_x = 4.0
        scale_z = 0.09

        points = []
        for i in range(start_idx, end_idx):
            seg = road.segments[i]
            rx = px + (seg.road_x - player.x) * scale_x
            rz = py - (seg.z - player.z) * scale_z
            points.append((rx, rz))
        if len(points) > 1:
            for i in range(len(points) - 1):
                pygame.draw.line(surf, (130, 130, 130), points[i], points[i+1], 2)

        # Player
        pygame.draw.circle(surf, (85, 240, 125), (px, py - 25), 5)
        pygame.draw.circle(surf, (35, 110, 55), (px, py - 25), 5, 1)

        # AI cars
        for car in cars:
            if abs(car.z - player.z) < 600:
                cx = px + (car.x - player.x) * scale_x
                cy = py - (car.z - player.z) * scale_z
                if mx <= cx <= mx + mw and my <= cy <= my + mh:
                    pygame.draw.circle(surf, (95, 175, 255), (int(cx), int(cy)), 3)

        # Checkpoints
        for seg in road.segments:
            if seg.has_checkpoint and abs(seg.z - player.z) < 800:
                cx = px + (seg.road_x - player.x) * scale_x
                cy = py - (seg.z - player.z) * scale_z
                col = (55, 195, 85) if seg.solved else (255, 85, 85)
                pygame.draw.circle(surf, col, (int(cx), int(cy)), 4)


# ==========================================
# HIGHWAY SCENE (main orchestrator)
# ==========================================
class HighwayScene:
    def __init__(self, screen_w, screen_h, truck_surface=None):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.road = Road(screen_w, screen_h)
        self.player = PlayerVehicle()
        self.camera = CameraSystem()
        self.cars = []
        self.sound = SoundManager()
        self.quiz = MathQuiz(self.sound)
        self.ui = UI(screen_w, screen_h)
        self.fade = FadeTransition(0.7)
        self.background = CityBackground(screen_w, screen_h, self.road.horizon_y)
        self.dashboard = Dashboard()
        self.phase = "entering"
        self.finished = False
        self._arrive_timer = 0.0
        self._spawn_timer = 0.0
        self._next_checkpoint = 0
        self.warm_overlay = pygame.Surface((screen_w, screen_h))
        self.warm_overlay.fill((255, 185, 115))
        self.vignette = self._make_vignette()
        self._crash_flash = 0.0
        self._fog_overlay = None

    def _make_vignette(self):
        v = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        cx, cy = self.screen_w // 2, self.screen_h // 2
        max_r = int(math.hypot(cx, cy))
        for i in range(24):
            t = i / 24
            r = int(max_r * (1 - t * 0.85))
            a = int(40 * (1 - t) ** 2)
            pygame.draw.ellipse(v, (0, 0, 0, a), (cx - r, cy - r, r * 2, r * 2), max(2, int(max_r / 12)))
        return v

    def start(self):
        self.fade.start()

    def _next_unsolved_checkpoint(self):
        for seg in self.road.segments:
            if seg.has_checkpoint and not seg.solved:
                return seg
        return None

    def _on_quiz_success(self):
        cp = self._next_unsolved_checkpoint()
        if cp:
            cp.solved = True
            cp.light_state = "green"
            self.sound.play("light")
        self.phase = "resuming"

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_c:
                self.camera.cycle_pov()
                self.sound.play("camera")

        if self.phase == "stopped" and self.quiz.active:
            self.quiz.handle_event(event)
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.quiz.handle_click(event.pos)

    def _manage_traffic(self):
        self._spawn_timer -= 0.016
        if self._spawn_timer <= 0:
            self._spawn_timer = random.uniform(1.5, 3.0)
            if len(self.cars) < 10 and self.player.z < FINAL_DISTANCE - 200:
                spawn_z = self.player.z + random.uniform(400, 900)
                lane = random.randint(0, NUM_LANES - 1)
                speed = random.uniform(140, 260)
                ok = True
                for seg in self.road.segments:
                    if seg.has_checkpoint and abs(seg.z - spawn_z) < 150:
                        ok = False
                        break
                if ok:
                    self.cars.append(AIVehicle(spawn_z, lane, speed, self.road))

        new_cars = []
        for car in self.cars:
            if car.update(0.016, self.road, self.player, self.cars):
                new_cars.append(car)
        self.cars = new_cars

    def _check_collisions(self):
        if self.player.crash_timer > 0:
            return
        for car in self.cars:
            dz = abs(self.player.z - car.z)
            dx = abs(self.player.x - car.x)
            if dz < 45 and dx < 400:
                self.player.speed *= 0.3
                self.player.crash_timer = 1.2
                self.camera.add_shake(10.0, 0.5)
                self._crash_flash = 0.35
                self.sound.play("crash")
                if self.player.x < car.x:
                    self.player.x -= 200
                else:
                    self.player.x += 200
                break

    def _check_checkpoints(self):
        if self.quiz.active:
            return
        cp = self._next_unsolved_checkpoint()
        if cp:
            dist = cp.z - self.player.z
            if 0 < dist < 300 and self.player.speed > 0:
                self.phase = "braking"
                factor = max(0.0, min(1.0, dist / 300))
                target = 260 * factor
                self.player.speed = max(0, min(self.player.speed, target))
                if dist < 18:
                    self.player.speed = 0
                    self.phase = "stopped"
                    level = cp.checkpoint_id + 1
                    self.quiz.generate(level, cp.checkpoint_id, self._on_quiz_success)
            else:
                if self.phase not in ("entering", "arriving"):
                    self.phase = "cruising"
        else:
            if self.phase not in ("entering", "arriving"):
                self.phase = "cruising"

    def update(self, dt):
        keys = pygame.key.get_pressed()
        self.fade.update(dt)
        self.background.update(dt)

        if self.fade.state == "out" and self.fade.is_done_fading_out():
            self.finished = True
            return "arrived"

        if self.phase == "arriving" and self.fade.state != "out":
            self._arrive_timer -= dt
            if self._arrive_timer <= 0:
                self.fade.begin_out()
            self.player.handle_input(keys, dt, self.road)
            self.player.update(dt, self.road)
            self.camera.update(dt, self.player)
            return "running"

        if self.quiz.active:
            self.quiz.update(dt)
            self.player.speed = max(0, self.player.speed - 600 * dt)
            self.player.update(dt, self.road)
            self.camera.update(dt, self.player)
            return "running"

        self.player.handle_input(keys, dt, self.road)
        self.player.update(dt, self.road)
        self._manage_traffic()
        self._check_checkpoints()
        self._check_collisions()
        self.camera.update(dt, self.player)

        if self.player.z >= FINAL_DISTANCE and self.phase != "arriving":
            self.phase = "arriving"
            self._arrive_timer = 1.6
            self.sound.play("arrive")

        if self.phase == "entering" and self.player.z >= 0:
            self.phase = "cruising"

        if self._crash_flash > 0:
            self._crash_flash -= dt

        return "running"

    def draw(self, surf):
        progress = max(0.0, min(1.0, self.player.z / FINAL_DISTANCE))
        self.background.draw(surf, self.camera.z, progress, horizon_y=self.road.horizon_y)

        # Render road
        self.road.render(surf, self.camera.x, self.camera.y, self.camera.z,
                        self.road.horizon_y, self.road.bottom_y, self.road.vp_x,
                        1.0, 1.0)

        # Draw AI cars (far to near)
        car_draws = []
        for car in self.cars:
            p = project_world(car.x, car.y, car.z, self.camera.x, self.camera.y, self.camera.z,
                              self.road.horizon_y, self.road.bottom_y, self.road.vp_x,
                              self.road.bottom_half, 1.0, 1.0)
            if p:
                car_draws.append((p[1], car, p))
        car_draws.sort(key=lambda x: x[0], reverse=True)
        for _, car, p in car_draws:
            car.draw(surf, self.road, self.camera.x, self.camera.y, self.camera.z,
                     self.road.horizon_y, self.road.bottom_y, self.road.vp_x,
                     self.road.bottom_half, 1.0, 1.0)

        # Draw player (only in chase modes)
        if not self.camera.is_first_person():
            self.player.draw(surf, self.road, self.camera.x, self.camera.y, self.camera.z,
                            self.road.horizon_y, self.road.bottom_y, self.road.vp_x,
                            self.road.bottom_half, 1.0, 1.0)

        # UI
        self.ui.draw(surf, self.player, self.road, self.cars, self.phase, self.camera)

        # Dashboard (first person only)
        if self.camera.is_first_person():
            self.dashboard.draw(surf, self.screen_w, self.screen_h, self.player)

        # Arrival banner
        if self.phase == "arriving":
            font_big = pygame.font.Font(None, 54)
            txt = font_big.render("Welcome to the City Market!", True, (255, 255, 255))
            bg = pygame.Surface((txt.get_width() + 40, txt.get_height() + 24), pygame.SRCALPHA)
            bg.fill((50, 130, 90, 210))
            surf.blit(bg, (self.screen_w // 2 - bg.get_width() // 2, self.screen_h // 2 - 60))
            surf.blit(txt, (self.screen_w // 2 - txt.get_width() // 2, self.screen_h // 2 - 46))

        # Quiz panel
        if self.quiz.active:
            self.quiz.draw(surf, self.screen_w, self.screen_h)

        # Atmospheric fog (soft, bottom-heavy)
        if self._fog_overlay is None:
            self._fog_overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
            for i in range(self.screen_h):
                t = i / self.screen_h
                a = int(25 * t * t)
                pygame.draw.line(self._fog_overlay, (205, 215, 225, a), (0, i), (self.screen_w, i))
        surf.blit(self._fog_overlay, (0, 0))

        # Warm overlay + vignette
        self.warm_overlay.set_alpha(int(6 + 10 * progress))
        surf.blit(self.warm_overlay, (0, 0))
        surf.blit(self.vignette, (0, 0))

        # Crash flash
        if self._crash_flash > 0:
            flash = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
            flash.fill((255, 80, 60, int(90 * self._crash_flash / 0.35)))
            surf.blit(flash, (0, 0))

        self.fade.draw(surf)