import pygame
import math
import random


class WaterTap:
    """Rural concrete water point: tap + stream + carryable bucket.
    Self-contained addition; does not modify any existing game system."""

    def __init__(self, tile_x, tile_y, tile_size):
        self.tx = tile_x
        self.ty = tile_y
        self.tile_size = tile_size
        self.w, self.h = 72, 110

        self.open = False
        self.open_anim = 0.0
        self.fill = 0.3            # bucket water level (travels with bucket)
        self.wet = 0.0
        self.time = 0.0
        self.ripple_timer = 0.0
        self.ripples = []
        self.splash = []

        self.spout_x = 52
        self.spout_y = 57
        self.bucket_cx = 53
        self.bucket_top = 70
        self.bucket_bot = 94

        # ---- bucket carry system state ----
        self.bucket_carried = False
        tex_x = tile_x * tile_size - (self.w - tile_size) // 2
        tex_y = tile_y * tile_size + tile_size - self.h
        self.bucket_home = (tex_x + self.bucket_cx, tex_y + self.bucket_bot)
        self.bucket_x, self.bucket_y = self.bucket_home

        self.static = self._build_static()

    # ---------------- static structure (bucket NOT baked in) ----------------
    def _build_static(self):
        rng = random.Random(7)
        s = pygame.Surface((self.w, self.h), pygame.SRCALPHA)

        conc, conc_d, conc_l = (152, 152, 146), (112, 112, 108), (178, 178, 172)
        crack, damp = (88, 88, 84), (98, 106, 104)
        metal, metal_d, metal_l = (72, 78, 84), (46, 50, 56), (112, 120, 126)
        rust = (122, 80, 48)
        buck_d = (64, 74, 86)
        rim = (52, 60, 70)

        pygame.draw.ellipse(s, (15, 20, 12, 110), (8, 98, 58, 10))

        # tall weathered concrete column
        pygame.draw.rect(s, conc, (12, 16, 26, 80), border_radius=2)
        pygame.draw.rect(s, conc_d, (12, 16, 26, 80), 2, border_radius=2)
        pygame.draw.rect(s, conc_l, (14, 18, 6, 76))
        pygame.draw.rect(s, conc_d, (32, 18, 5, 76))
        pygame.draw.rect(s, conc_l, (10, 12, 30, 7), border_radius=2)
        pygame.draw.rect(s, conc_d, (10, 12, 30, 7), 1, border_radius=2)
        s.set_at((9, 14), conc_d)
        s.set_at((40, 13), conc_d)
        pygame.draw.line(s, crack, (20, 26), (22, 34), 1)
        pygame.draw.line(s, crack, (22, 34), (21, 42), 1)
        pygame.draw.line(s, crack, (29, 62), (27, 70), 1)
        for _ in range(8):
            c = (135, 135, 128) if rng.random() < 0.5 else conc_d
            pygame.draw.circle(s, c, (rng.randint(15, 35), rng.randint(20, 90)),
                               rng.randint(1, 2))
        pygame.draw.ellipse(s, damp, (28, 44, 14, 20))

        # concrete platform extending forward
        pygame.draw.rect(s, conc, (12, 92, 52, 10), border_radius=2)
        pygame.draw.rect(s, conc_d, (12, 92, 52, 10), 1, border_radius=2)
        pygame.draw.line(s, conc_l, (13, 93), (62, 93), 1)
        s.set_at((63, 96), conc_d)
        s.set_at((14, 100), conc_d)

        # weathered metal tap
        pygame.draw.rect(s, metal_d, (34, 43, 4, 11), border_radius=1)
        pygame.draw.rect(s, metal, (36, 44, 8, 9), border_radius=2)
        pygame.draw.rect(s, metal, (44, 47, 9, 5), border_radius=1)
        pygame.draw.line(s, metal_l, (44, 47), (52, 47), 1)
        pygame.draw.rect(s, metal, (50, 51, 5, 6), border_radius=1)
        pygame.draw.rect(s, metal_d, (50, 56, 5, 2))
        s.set_at((38, 52), rust)
        s.set_at((45, 51), rust)
        s.set_at((51, 54), rust)
        s.set_at((37, 45), metal_l)

        # second small decorative bucket near column base (stays put)
        pts2 = [(16, 86), (26, 86), (25, 94), (17, 94)]
        pygame.draw.polygon(s, (85, 95, 105), pts2)
        pygame.draw.polygon(s, buck_d, pts2, 1)
        pygame.draw.line(s, rim, (15, 86), (27, 86), 1)
        return s

    # ---------------- helpers ----------------
    def _surface_y(self):
        return self.bucket_bot - 2 - int(self.fill * 8)

    def player_near(self, tx, ty):
        return abs(tx - self.tx) <= 1 and abs(ty - self.ty) <= 1

    def toggle(self):                       # E: tap only
        self.open = not self.open

    def _bucket_at_home(self):
        return (abs(self.bucket_x - self.bucket_home[0]) < 6 and
                abs(self.bucket_y - self.bucket_home[1]) < 6)

    def can_bucket(self, tx, ty):           # F: bucket only
        if self.bucket_carried:
            return True
        px = tx * self.tile_size + self.tile_size // 2
        py = ty * self.tile_size + self.tile_size // 2
        return math.hypot(px - self.bucket_x,
                          py - (self.bucket_y - 8)) <= self.tile_size * 1.5

    def toggle_carry(self, player=None):
        if self.bucket_carried:
            # PUT DOWN: detach and place beside/in front of the feet,
            # clear of the player's sprite, sitting on the ground
            self.bucket_carried = False
            if player is not None:
                self.bucket_x = player.x + 30
                self.bucket_y = player.y + 40
        else:
            # PICK UP: fully lifted; from now on it is rigidly hand-attached
            self.bucket_carried = True

    # ---------------- simulation ----------------
    def update(self, dt, player=None):
        self.time += dt
        target = 1.0 if self.open else 0.0
        if self.open_anim < target:
            self.open_anim = min(target, self.open_anim + dt * 3)
        elif self.open_anim > target:
            self.open_anim = max(target, self.open_anim - dt * 3)

        bucket_here = (not self.bucket_carried) and self._bucket_at_home()
        if self.open:
            if bucket_here:
                self.fill = min(1.0, self.fill + dt / 25.0)
                self.ripple_timer -= dt
                if self.ripple_timer <= 0:
                    self.ripple_timer = 0.35
                    self.ripples.append(0.0)
            self.wet = min(1.0, self.wet + dt / 8.0)
            if len(self.splash) < 30 and random.random() < 0.5:
                sy = self._surface_y() if bucket_here else 92
                self.splash.append({
                    'x': self.spout_x + random.uniform(-2, 2),
                    'y': float(sy),
                    'vx': random.uniform(-25, 25),
                    'vy': random.uniform(-60, -20),
                    'life': random.uniform(0.15, 0.35)})
        if not bucket_here:
            self.ripples = []
        self.ripples = [r + dt for r in self.ripples if r + dt < 0.8]
        for p in self.splash[:]:
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['vy'] += 180 * dt
            p['life'] -= dt
            if p['life'] <= 0:
                self.splash.remove(p)
        # NOTE: no bucket physics/lerp here while carried - the carried
        # bucket is drawn rigidly from the player's hand in draw_carried_bucket.

    # ---------------- bucket sprite: realistic small size ----------------
    # ~8px tall / ~8px wide at zoom 1 (player is ~39px) => ~30cm household bucket
    def _draw_bucket(self, surf, bx, by, z, fill, ripples=None, handle='side'):
        buck, buck_d, buck_l = (96, 108, 120), (64, 74, 86), (132, 144, 156)
        rim = (52, 60, 70)
        hgt, hw_t, hw_b = 12, 6, 4
        pts = [(int(bx-hw_t*z), int(by-hgt*z)), (int(bx+hw_t*z), int(by-hgt*z)),
               (int(bx+hw_b*z), int(by)), (int(bx-hw_b*z), int(by))]
        pygame.draw.polygon(surf, buck, pts)
        pygame.draw.polygon(surf, buck_d, pts, 1)
        pygame.draw.line(surf, buck_l, (int(bx-4*z), int(by-11*z)),
                         (int(bx-3*z), int(by-1*z)), 1)
        pygame.draw.line(surf, buck_d, (int(bx-5*z), int(by-8*z)),
                         (int(bx+5*z), int(by-8*z)), 1)
        pygame.draw.line(surf, buck_d, (int(bx-5*z), int(by-4*z)),
                         (int(bx+4*z), int(by-4*z)), 1)
        pygame.draw.line(surf, rim, (int(bx-7*z), int(by-hgt*z)),
                         (int(bx+7*z), int(by-hgt*z)), max(1, int(2*z)))
        if handle == 'side':
            pygame.draw.arc(surf, buck_d, (int(bx-11*z), int(by-11*z),
                                           int(6*z), int(9*z)),
                            math.pi / 2, 3 * math.pi / 2, 1)
        else:
            pygame.draw.arc(surf, buck_d, (int(bx-6*z), int(by-18*z),
                                           int(12*z), int(12*z)),
                            math.pi, 2 * math.pi, max(1, int(1.5*z)))
        if fill > 0.02:
            wy = by - (2 + fill * 8) * z
            pygame.draw.polygon(surf, (150, 200, 235, 170),
                                [(int(bx-5*z), int(wy)), (int(bx+5*z), int(wy)),
                                 (int(bx+3*z), int(by-1*z)), (int(bx-3*z), int(by-1*z))])
            pygame.draw.ellipse(surf, (205, 235, 250, 210),
                                (int(bx-5*z), int(wy-1*z), int(10*z), int(2*z)))
            if ripples:
                for r in ripples:
                    rad = (1.5 + r * 4) * z
                    a = max(0, min(255, int(160 * (1 - r / 0.8))))
                    rw = max(2, int(rad * 2))
                    rh = max(2, int(rad * 2 / 3))
                    pygame.draw.ellipse(surf, (230, 245, 255, a),
                                        (int(bx - rad), int(wy - rad / 3), rw, rh), 1)
    def _hint(self, surf, cx, cy, zoom, label):
        font = pygame.font.Font(None, max(14, int(18 * zoom)))
        txt = font.render(label, True, (255, 255, 255))
        bg = pygame.Surface((txt.get_width() + 12, txt.get_height() + 6))
        bg.fill((0, 0, 0))
        bg.set_alpha(180)
        surf.blit(bg, (cx - txt.get_width() / 2 - 6, cy))
        surf.blit(txt, (cx - txt.get_width() / 2, cy + 3))

    # ---------------- drawing ----------------
    def draw(self, surf, cam_x, cam_y, zoom, player):
        ts = self.tile_size
        sx = (self.tx * ts - cam_x) * zoom
        sy = (self.ty * ts - cam_y) * zoom
        sw, sh = int(self.w * zoom), int(self.h * zoom)
        bx = sx + (ts * zoom - sw) / 2
        by = sy + ts * zoom - sh

        frame = self.static.copy()
        bucket_here = (not self.bucket_carried) and self._bucket_at_home()
        syf = self._surface_y() if bucket_here else 92

        if self.wet > 0.05:
            pygame.draw.ellipse(frame, (55, 65, 68, int(70 * self.wet)),
                                (38, 90, 30, 8))

        # narrow semi-transparent animated stream
        if self.open_anim > 0.1:
            alpha = int(150 * self.open_anim)
            y = self.spout_y
            while y < syf:
                xoff = round(math.sin(self.time * 9 + y * 0.35))
                pygame.draw.line(frame, (190, 225, 250, alpha),
                                 (self.spout_x + xoff, y),
                                 (self.spout_x + xoff, min(y + 2, syf)), 2)
                if y % 6 < 3:
                    pygame.draw.line(frame, (235, 248, 255, min(255, alpha + 40)),
                                     (self.spout_x + xoff, y),
                                     (self.spout_x + xoff, min(y + 1, syf)), 1)
                y += 3
            span = max(1, syf - self.spout_y)
            for off in (0.0, 0.5):
                dy = int((self.time * 80 + off * span) % span)
                pygame.draw.rect(frame, (240, 250, 255, 200),
                                 (self.spout_x - 1, self.spout_y + dy, 1, 2))

        for p in self.splash:
            a = max(0, int(255 * p['life'] / 0.35))
            pygame.draw.rect(frame, (215, 240, 255, min(255, a)),
                             (int(p['x']), int(p['y']), 1, 1))

        # rotating tap handle
        ang = math.radians(15 + 85 * self.open_anim)
        px, py = 40, 43
        ex = px + int(round(math.cos(ang) * 7))
        ey = py - int(round(math.sin(ang) * 7))
        pygame.draw.line(frame, (46, 50, 56), (px, py), (ex, ey), 2)
        pygame.draw.circle(frame, (112, 120, 126), (ex, ey), 2)
        pygame.draw.circle(frame, (72, 78, 84), (px, py), 2)

        surf.blit(pygame.transform.scale(frame, (sw, sh)), (bx, by))

        # bucket resting on the ground (only when NOT carried)
        if not self.bucket_carried:
            gbx = (self.bucket_x - cam_x) * zoom
            gby = (self.bucket_y - cam_y) * zoom
            pygame.draw.ellipse(surf, (15, 20, 12, 90),
                                (int(gbx - 5*zoom), int(gby - 2*zoom),
                                 int(10*zoom), int(3*zoom)))
            self._draw_bucket(surf, gbx, gby, zoom, self.fill,
                              self.ripples if (bucket_here and self.open) else None,
                              handle='side')
            if player is not None and self.can_bucket(player.tx, player.ty):
                self._hint(surf, gbx, gby - 20 * zoom, zoom,
                           "Press F to Pick Up Bucket")

        # E hint above the structure (tap only)
        if player is not None and self.player_near(player.tx, player.ty):
            label = "Press E to Close Tap" if self.open else "Press E to Open Tap"
            self._hint(surf, bx + sw / 2, by - 14 * zoom, zoom, label)

    def draw_carried_bucket(self, surf, cam_x, cam_y, zoom, player):
        """Rigid hand attachment: position computed DIRECTLY from the exact
        hand coordinates Player.draw uses - no smoothing, no lag, no drag."""
        if not self.bucket_carried or player is None:
            return
        walk = math.sin(player.anim_frame * 0.35) * 3 if player.moving else 0
        arm = math.sin(player.anim_frame * 0.35) * 5.5 if player.moving else 0
        hand_x = player.x + 20                 # same as player's right hand
        hand_y = player.y + 6 + walk - arm
        bx = (hand_x + 5 - cam_x) * zoom
        by = (hand_y + 15 - cam_y) * zoom      # hangs from hand, upright
        self._draw_bucket(surf, bx, by, zoom, self.fill, None, handle='top')
        px = (player.x + 12 - cam_x) * zoom
        py = (player.y - 30 - cam_y) * zoom
        self._hint(surf, px, py, zoom, "Press F to Put Down Bucket")