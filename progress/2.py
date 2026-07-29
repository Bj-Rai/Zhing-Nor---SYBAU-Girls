import pygame
import sys
import math
import random
import json
import os
from enum import Enum

os.environ['SDL_VIDEO_CENTERED'] = '1'  # center the window on screen

# Initialize pygame and font BEFORE generating textures
pygame.init()
pygame.font.init()

# ==========================================
# CONFIGURATION
# ==========================================
TILE_SIZE = 48

# Fit the window inside the actual screen (minus room for taskbar/title bar)
_display_info = pygame.display.Info()
SCREEN_WIDTH = min(1280, _display_info.current_w - 60)
SCREEN_HEIGHT = min(800, _display_info.current_h - 100)
FPS = 60
SAVE_FILE = "farm_save.json"
DAY_LENGTH = 720
CROP_GROWTH_BASE = 0.15
WEATHER_TYPES = ["sunny", "rainy", "stormy"]

# Zoom settings
MIN_ZOOM = 0.7
MAX_ZOOM = 2.0
ZOOM_SPEED = 0.1

# Colors
COLOR_WHITE = (255,255,255)
COLOR_BLACK = (0,0,0)
COLOR_UI_BG = (30,30,40)  # Removed alpha - will handle separately
COLOR_ENERGY = (52, 152, 219)
COLOR_ENERGY_BG = (44, 62, 80)
COLOR_HEALTH = (46, 204, 113)
COLOR_HEALTH_BG = (30, 40, 35)
COLOR_EXP = (241, 196, 15)
COLOR_GOLD = (241,196,15)

# ==========================================
# ART ENGINE
# ==========================================
class ArtEngine:
    @staticmethod
    def create_grass_seasonal(season):
        size = TILE_SIZE
        surf = pygame.Surface((size, size))
        if season == "spring":
            surf.fill((106, 182, 52))
            blade_color = (122, 202, 65)
        elif season == "summer":
            surf.fill((86, 152, 42))
            blade_color = (100, 180, 55)
        elif season == "autumn":
            surf.fill((160, 130, 50))
            blade_color = (180, 150, 70)
        else:
            surf.fill((210, 220, 230))
            blade_color = (200, 210, 220)
        for _ in range(40):
            gx = random.randint(0, size-2)
            gy = random.randint(0, size-2)
            pygame.draw.line(surf, blade_color, (gx, gy), (gx+1, gy-random.randint(1,4)))
        return surf

    @staticmethod
    def create_golden_wheat(size):
        surf = pygame.Surface((size, size))
        surf.fill((101, 67, 33))
        for _ in range(200):
            x = random.randint(0, size-1)
            y = random.randint(0, size-1)
            color_var = random.randint(-15, 15)
            pygame.draw.circle(surf, (101+color_var, 67+color_var, 33+color_var), (x, y), random.randint(1, 2))
        for _ in range(30):
            x = random.randint(0, size-1)
            y = random.randint(0, size-1)
            pygame.draw.circle(surf, (70, 50, 30), (x, y), 1)
        for _ in range(50):
            x = random.randint(0, size-1)
            y = random.randint(0, size-1)
            pygame.draw.line(surf, (180, 150, 60), (x, y), (x+2, y-2), 1)
        return surf

    @staticmethod
    def create_soil_texture(size):
        surf = pygame.Surface((size, size))
        base_color = (101, 67, 33)
        surf.fill(base_color)
        for _ in range(200):
            x = random.randint(0, size-1)
            y = random.randint(0, size-1)
            color_var = random.randint(-15, 15)
            pygame.draw.circle(surf, (base_color[0]+color_var, base_color[1]+color_var, base_color[2]+color_var), (x, y), random.randint(1, 2))
        for _ in range(30):
            x = random.randint(0, size-1)
            y = random.randint(0, size-1)
            pygame.draw.circle(surf, (70, 50, 30), (x, y), 1)
        return surf

    @staticmethod
    def draw_tall_vending_machine():
        w, h = TILE_SIZE, TILE_SIZE * 2
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        
        pygame.draw.rect(surf, (70, 75, 80), (3, 5, 42, 90), border_radius=4)
        pygame.draw.rect(surf, (50, 55, 60), (3, 5, 42, 90), 2, border_radius=4)
        pygame.draw.rect(surf, (200, 60, 50), (5, 7, 38, 12), border_radius=2)
        font_small = pygame.font.Font(None, 9)
        try:
            brand_text = font_small.render("ENERGY", True, (255, 255, 255))
            surf.blit(brand_text, (16, 9))
        except:
            pass
        pygame.draw.rect(surf, (0, 200, 0, 150), (12, 21, 24, 8))
        try:
            led_text = font_small.render("READY", True, (0, 255, 0))
            surf.blit(led_text, (14, 22))
        except:
            pass
        pygame.draw.rect(surf, (180, 220, 240, 200), (6, 32, 36, 28), border_radius=2)
        pygame.draw.rect(surf, (100, 105, 110), (6, 32, 36, 28), 1, border_radius=2)
        can_positions = [(10, 35), (22, 35), (34, 35)]
        for cx, cy in can_positions:
            pygame.draw.rect(surf, (50, 180, 90), (cx, cy, 8, 8), border_radius=2)
            pygame.draw.rect(surf, (40, 150, 70), (cx+1, cy+1, 6, 6), border_radius=1)
            pygame.draw.polygon(surf, (255, 255, 100), [(cx+2, cy+2), (cx+4, cy+3), (cx+2, cy+5), (cx+5, cy+3), (cx+3, cy+2)])
        pygame.draw.rect(surf, (180, 220, 240, 200), (6, 62, 36, 28), border_radius=2)
        pygame.draw.rect(surf, (100, 105, 110), (6, 62, 36, 28), 1, border_radius=2)
        can_positions = [(10, 65), (22, 65), (34, 65)]
        for cx, cy in can_positions:
            pygame.draw.rect(surf, (50, 180, 90), (cx, cy, 8, 8), border_radius=2)
            pygame.draw.rect(surf, (40, 150, 70), (cx+1, cy+1, 6, 6), border_radius=1)
            pygame.draw.polygon(surf, (255, 255, 100), [(cx+2, cy+2), (cx+4, cy+3), (cx+2, cy+5), (cx+5, cy+3), (cx+3, cy+2)])
        button_y = 32
        for i, bx in enumerate([10, 22, 34]):
            pygame.draw.circle(surf, (150, 155, 160), (bx+4, button_y+24), 3)
            if i == 0:
                pygame.draw.circle(surf, (0, 255, 0), (bx+4, button_y+24), 1)
            else:
                pygame.draw.circle(surf, (255, 0, 0), (bx+4, button_y+24), 1)
        pygame.draw.rect(surf, (40, 40, 45), (16, 80, 16, 4), border_radius=1)
        pygame.draw.rect(surf, (255, 200, 50), (18, 79, 12, 2))
        pygame.draw.rect(surf, (60, 65, 70), (5, 85, 8, 8), border_radius=1)
        pygame.draw.rect(surf, (30, 30, 35), (26, 83, 12, 6), border_radius=1)
        pygame.draw.rect(surf, (0, 100, 0), (28, 84, 8, 4))
        pygame.draw.rect(surf, (30, 30, 35), (28, 12, 12, 7))
        try:
            price_text = font_small.render("$10", True, (50, 255, 50))
            surf.blit(price_text, (29, 13))
        except:
            pass
        pygame.draw.circle(surf, (255, 100, 50), (24, 6), 2)
        pygame.draw.circle(surf, (255, 200, 100), (24, 6), 1)
        pygame.draw.rect(surf, (50, 55, 60), (2, 92, 44, 3))
        for ly in [45, 75]:
            pygame.draw.circle(surf, (0, 100, 255, 100), (5, ly), 1)
            pygame.draw.circle(surf, (0, 100, 255, 100), (43, ly), 1)
        return surf

    @staticmethod
    def draw_new_premium_truck():
        """Vintage green pickup truck with a wooden crate bed full of veggies."""
        w, h = 256, 140
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        outline = (35, 45, 30)

        # Ground shadow
        pygame.draw.ellipse(surf, (20, 40, 15, 90), (20, 118, 220, 14))

        green_body = (60, 110, 65)
        green_dark = (42, 85, 48)
        green_light = (85, 140, 90)

        # ---- Truck bed floor (open, low-walled) ----
        bed = pygame.Rect(96, 78, 118, 30)
        pygame.draw.rect(surf, green_dark, bed, border_radius=4)
        pygame.draw.rect(surf, outline, bed, 2, border_radius=4)

        # ---- Wooden crate sitting in the bed ----
        crate = pygame.Rect(100, 40, 108, 46)
        wood_dark = (120, 85, 45)
        wood_light = (170, 125, 70)
        pygame.draw.rect(surf, wood_dark, crate, border_radius=3)
        # horizontal slats
        for i in range(4):
            sy = crate.y + 4 + i * 10
            pygame.draw.rect(surf, wood_light, (crate.x + 3, sy, crate.w - 6, 7), border_radius=2)
            pygame.draw.rect(surf, wood_dark, (crate.x + 3, sy, crate.w - 6, 7), 1, border_radius=2)
        # crate corner posts
        for cx in [crate.x + 2, crate.right - 6]:
            pygame.draw.rect(surf, (95, 65, 32), (cx, crate.y, 4, crate.h))
        pygame.draw.rect(surf, outline, crate, 2, border_radius=3)

        # ---- Vegetables piled above the crate rim ----
        veggie_specs = [
            (112, 32, 9, (210, 45, 40)),   # tomato
            (128, 26, 10, (235, 140, 30)), # carrot cluster (round approx)
            (146, 30, 9, (90, 160, 60)),   # broccoli
            (163, 24, 10, (215, 55, 45)),  # tomato
            (180, 30, 9, (100, 170, 70)),  # broccoli
            (196, 27, 9, (230, 150, 35)),  # pumpkin/orange veg
        ]
        for vx, vy, r, color in veggie_specs:
            pygame.draw.circle(surf, tuple(max(0, c - 35) for c in color), (vx, vy), r)
            pygame.draw.circle(surf, color, (vx - 1, vy - 1), r - 2)
            pygame.draw.circle(surf, tuple(min(255, c + 40) for c in color), (vx - r//3, vy - r//3), max(2, r//3))
        # a couple of leafy bits poking out
        for lx, ly in [(120, 20), (152, 18), (188, 20)]:
            pygame.draw.ellipse(surf, (70, 140, 55), (lx - 4, ly - 8, 8, 10))
            pygame.draw.ellipse(surf, (95, 165, 75), (lx - 2, ly - 7, 4, 6))

        # ---- Cab (rounded, vintage-style) ----
        cab = pygame.Rect(28, 46, 78, 42)
        pygame.draw.rect(surf, green_body, cab, border_radius=16)
        pygame.draw.rect(surf, outline, cab, 3, border_radius=16)
        pygame.draw.rect(surf, green_light, (cab.x + 4, cab.y + 3, cab.w - 8, 8), border_radius=6)  # roof sheen

        # rounded hood extending forward
        # rounded hood extending forward, with a subtle center crease
        hood = pygame.Rect(10, 62, 42, 34)
        pygame.draw.rect(surf, green_body, hood, border_radius=16)
        pygame.draw.rect(surf, outline, hood, 3, border_radius=16)
        pygame.draw.rect(surf, green_light, (hood.x + 4, hood.y + 3, hood.w - 8, 7), border_radius=5)  # sheen
        pygame.draw.line(surf, green_dark, (hood.x + 6, hood.centery + 6), (hood.right - 6, hood.centery + 6), 1)

        # Rounded nose with chrome-rimmed grille
        nose = pygame.Rect(0, 66, 26, 36)
        pygame.draw.ellipse(surf, green_dark, nose)
        pygame.draw.ellipse(surf, outline, nose, 2)
        grille = pygame.Rect(4, 72, 16, 24)
        pygame.draw.rect(surf, (60, 60, 65), grille, border_radius=6)
        pygame.draw.rect(surf, (150, 150, 155), grille, 2, border_radius=6)  # chrome rim
        for gy in range(76, 94, 4):
            pygame.draw.line(surf, (110, 110, 115), (grille.x + 2, gy), (grille.right - 2, gy), 2)
        # small hood ornament
        pygame.draw.circle(surf, (200, 200, 205), (13, 65), 2)

        # Windshield
        pygame.draw.rect(surf, (190, 225, 235), (52, 50, 26, 22), border_radius=4)
        pygame.draw.rect(surf, outline, (52, 50, 26, 22), 2, border_radius=4)
        pygame.draw.line(surf, (230, 245, 250), (54, 52), (66, 52), 1)

        # Side window strip on cab
        pygame.draw.rect(surf, (190, 225, 235), (84, 54, 16, 16), border_radius=3)
        pygame.draw.rect(surf, outline, (84, 54, 16, 16), 1, border_radius=3)

        # Door line + handle
        pygame.draw.line(surf, outline, (78, 50), (78, 88), 2)
        pygame.draw.circle(surf, (40, 40, 40), (74, 70), 2)

        # Headlight with chrome rim and highlight
        pygame.draw.circle(surf, (150, 150, 155), (14, 76), 7)   # chrome housing
        pygame.draw.circle(surf, (255, 240, 180), (14, 76), 5)
        pygame.draw.circle(surf, outline, (14, 76), 7, 2)
        pygame.draw.circle(surf, (255, 255, 240), (12, 74), 2)   # glare highlight

        # Chrome front bumper, slightly rounded
        bumper = pygame.Rect(0, 100, 34, 8)
        pygame.draw.rect(surf, (170, 170, 175), bumper, border_radius=4)
        pygame.draw.rect(surf, outline, bumper, 2, border_radius=4)
        pygame.draw.line(surf, (220, 220, 225), (bumper.x + 3, bumper.y + 2), (bumper.right - 3, bumper.y + 2), 1)

        # Running board connecting cab to bed
        pygame.draw.rect(surf, green_dark, (30, 96, 170, 8), border_radius=3)
        pygame.draw.rect(surf, outline, (30, 96, 170, 8), 1, border_radius=3)

        # ---- Wheels ----
        for wx, wy in [(64, 114), (172, 114)]:
            pygame.draw.circle(surf, (30, 30, 30), (wx, wy), 20)
            pygame.draw.circle(surf, outline, (wx, wy), 20, 3)
            pygame.draw.circle(surf, (200, 200, 205), (wx, wy), 9)
            pygame.draw.circle(surf, outline, (wx, wy), 9, 2)
            for angle in range(0, 360, 72):
                rad = math.radians(angle)
                pygame.draw.line(
                    surf, outline,
                    (wx + math.cos(rad)*3, wy + math.sin(rad)*3),
                    (wx + math.cos(rad)*8, wy + math.sin(rad)*8),
                    2
                )
            pygame.draw.circle(surf, (110, 110, 110), (wx, wy), 3)

        return surf
    
    @staticmethod
    def draw_beautiful_fence():
        surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)

        # Ground shadow at the base
        pygame.draw.ellipse(surf, (20, 35, 15, 90), (2, TILE_SIZE-8, TILE_SIZE-4, 8))

        c_main = (150, 100, 55)
        c_light = (185, 140, 90)
        c_dark = (105, 68, 35)
        c_highlight = (210, 165, 110)

        post_w = 8
        post_positions = [4, TILE_SIZE - post_w - 4]

        # Vertical posts with rounded caps and wood-grain shading
        for px in post_positions:
            pygame.draw.rect(surf, c_dark, (px-1, 2, post_w+2, TILE_SIZE-2), border_radius=3)
            pygame.draw.rect(surf, c_main, (px, 3, post_w, TILE_SIZE-5), border_radius=3)
            pygame.draw.rect(surf, c_light, (px, 3, post_w-3, TILE_SIZE-5), border_radius=3)
            for gy in range(6, TILE_SIZE-4, 7):
                pygame.draw.line(surf, c_dark, (px+2, gy), (px+post_w-2, gy+2), 1)
            # Post cap
            cap_pts = [(px-2, 3), (px+post_w//2, -4), (px+post_w+2, 3)]
            pygame.draw.polygon(surf, c_highlight, cap_pts)
            pygame.draw.polygon(surf, c_dark, cap_pts, 1)

        # Two horizontal rails, cleanly drawn with a bevel
        rail_h = 7
        for ry in [12, 30]:
            pygame.draw.rect(surf, c_dark, (0, ry, TILE_SIZE, rail_h+2), border_radius=2)
            pygame.draw.rect(surf, c_main, (0, ry+1, TILE_SIZE, rail_h), border_radius=2)
            pygame.draw.line(surf, c_highlight, (2, ry+1), (TILE_SIZE-2, ry+1), 1)
            pygame.draw.line(surf, c_dark, (2, ry+rail_h), (TILE_SIZE-2, ry+rail_h), 1)
            # subtle wood grain streaks
            for gx in range(4, TILE_SIZE-4, 10):
                pygame.draw.line(surf, c_dark, (gx, ry+2), (gx+5, ry+rail_h-1), 1)

        # Bolts where rails meet posts
        for px in post_positions:
            for ry in [12, 30]:
                bx, by = px + post_w//2, ry + rail_h//2
                pygame.draw.circle(surf, (70, 70, 75), (bx, by), 2)
                pygame.draw.circle(surf, (110, 110, 115), (bx, by), 1)

        return surf
    @staticmethod
    def draw_fence_post_texture():
        """A single vertical post, centered in the tile — no rails."""
        surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (20, 35, 15, 90), (TILE_SIZE//2-10, TILE_SIZE-8, 20, 8))
        c_main = (150, 100, 55)
        c_light = (185, 140, 90)
        c_dark = (105, 68, 35)
        c_highlight = (210, 165, 110)
        post_w = 10
        px = TILE_SIZE//2 - post_w//2
        pygame.draw.rect(surf, c_dark, (px-1, 2, post_w+2, TILE_SIZE-2), border_radius=3)
        pygame.draw.rect(surf, c_main, (px, 3, post_w, TILE_SIZE-5), border_radius=3)
        pygame.draw.rect(surf, c_light, (px, 3, post_w-4, TILE_SIZE-5), border_radius=3)
        for gy in range(6, TILE_SIZE-4, 7):
            pygame.draw.line(surf, c_dark, (px+2, gy), (px+post_w-2, gy+2), 1)
        cap_pts = [(px-2, 3), (px+post_w//2, -4), (px+post_w+2, 3)]
        pygame.draw.polygon(surf, c_highlight, cap_pts)
        pygame.draw.polygon(surf, c_dark, cap_pts, 1)
        return surf

    @staticmethod
    def draw_fence_rail_segment(horizontal=True):
        """A rail segment connecting two posts — drawn separately so it can be
        rotated/oriented per-direction and only shown where a neighbor exists."""
        surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        c_main = (150, 100, 55)
        c_dark = (105, 68, 35)
        c_highlight = (210, 165, 110)
        rail_h = 7
        for ry in [12, 30]:
            pygame.draw.rect(surf, c_dark, (0, ry, TILE_SIZE, rail_h+2), border_radius=2)
            pygame.draw.rect(surf, c_main, (0, ry+1, TILE_SIZE, rail_h), border_radius=2)
            pygame.draw.line(surf, c_highlight, (2, ry+1), (TILE_SIZE-2, ry+1), 1)
            pygame.draw.line(surf, c_dark, (2, ry+rail_h), (TILE_SIZE-2, ry+rail_h), 1)
        if not horizontal:
            surf = pygame.transform.rotate(surf, 90)
        return surf

    @staticmethod
    def draw_cattle_fence_post():
        surf = pygame.Surface((16, 48), pygame.SRCALPHA)
        for i in range(48):
            color = (139 - i//4, 90 - i//5, 43 - i//5)
            pygame.draw.line(surf, color, (2, i), (13, i))
        pygame.draw.rect(surf, (100, 65, 30), (2, 0, 12, 48), 1)
        for i in range(4):
            gy = 6 + i * 12
            pygame.draw.line(surf, (120, 80, 40), (4, gy), (14, gy+4), 1)
        cap_pts = [(0, 0), (8, -6), (16, 0)]
        pygame.draw.polygon(surf, (160, 110, 60), cap_pts)
        pygame.draw.polygon(surf, (100, 65, 30), [(8, -6), (16, 0), (8, 1)])
        pygame.draw.ellipse(surf, (180, 140, 80), (4, -4, 8, 3))
        for by in [4, 42]:
            pygame.draw.rect(surf, (80, 80, 85), (2, by, 12, 3), border_radius=1)
        for ny in [12, 24, 36]:
            pygame.draw.circle(surf, (60, 60, 65), (8, ny), 2)
            pygame.draw.circle(surf, (80, 80, 85), (8, ny), 1)
        return surf

    @staticmethod
    def draw_improved_scarecrow():
        w, h = 48, 48
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (101, 67, 33), (22, 20, 4, 28))
        pygame.draw.rect(surf, (101, 67, 33), (8, 28, 32, 4))
        pygame.draw.ellipse(surf, (210, 180, 100), (10, 6, 28, 8))
        pygame.draw.ellipse(surf, (180, 150, 70), (14, -2, 20, 10))
        pygame.draw.circle(surf, (245, 225, 190), (24, 18), 10)
        pygame.draw.circle(surf, (30, 30, 30), (20, 15), 2)
        pygame.draw.circle(surf, (30, 30, 30), (28, 15), 2)
        pygame.draw.line(surf, (80, 60, 40), (20, 21), (28, 21), 1)
        pygame.draw.line(surf, (80, 60, 40), (18, 19), (20, 21), 1)
        pygame.draw.line(surf, (80, 60, 40), (28, 21), (30, 19), 1)
        pygame.draw.line(surf, (80, 60, 40), (20, 21), (22, 23), 1)
        pygame.draw.line(surf, (80, 60, 40), (28, 21), (26, 23), 1)
        pygame.draw.rect(surf, (180, 150, 110), (14, 10, 6, 5), border_radius=1)
        pygame.draw.line(surf, (100, 70, 40), (14, 10), (20, 15), 1)
        pygame.draw.line(surf, (100, 70, 40), (20, 10), (14, 15), 1)
        pygame.draw.rect(surf, (160, 100, 80), (18, 24, 12, 12), border_radius=2)
        pygame.draw.rect(surf, (100, 150, 200), (20, 26, 4, 3))
        pygame.draw.rect(surf, (200, 100, 100), (24, 30, 4, 3))
        for i in range(5):
            sx = 8 + i * 8
            pygame.draw.line(surf, (200, 180, 80), (sx, 30), (sx-2, 26), 1)
            pygame.draw.line(surf, (200, 180, 80), (sx, 30), (sx+2, 26), 1)
        for i in range(4):
            sx = 16 + i * 5
            pygame.draw.line(surf, (200, 180, 80), (sx, 48), (sx-1, 44), 1)
            pygame.draw.line(surf, (200, 180, 80), (sx, 48), (sx+1, 44), 1)
        pygame.draw.circle(surf, (60, 60, 60), (24, 27), 2)
        pygame.draw.circle(surf, (60, 60, 60), (24, 32), 2)
        return surf

    @staticmethod
    def draw_realistic_barn():
        w, h = TILE_SIZE*5, TILE_SIZE*4
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        c_red = (185, 30, 35)
        c_dark_red = (130, 20, 25)
        c_roof = (70, 65, 75)
        c_white = (245, 245, 245)
        c_shadow = (25, 48, 15, 100)
        pygame.draw.ellipse(surf, c_shadow, (15, h-15, w-30, 15))
        body_w = w - 30
        body_h = h - 60
        body_x = 15
        body_y = h - body_h - 8
        pygame.draw.rect(surf, c_red, (body_x, body_y, body_w, body_h), border_radius=5)
        pygame.draw.rect(surf, c_dark_red, (body_x, body_y, body_w, body_h), 2, border_radius=5)
        for x in range(body_x + 20, body_x + body_w - 20, 20):
            pygame.draw.line(surf, c_dark_red, (x, body_y), (x, body_y + body_h), 3)
            pygame.draw.circle(surf, (80, 70, 60), (x, body_y + 25), 2)
            pygame.draw.circle(surf, (80, 70, 60), (x, body_y + body_h - 25), 2)
        door_w, door_h = 52, 58
        door_x = w//2 - door_w//2
        door_y = h - door_h - 8
        pygame.draw.rect(surf, c_white, (door_x, door_y, door_w, door_h), border_radius=4)
        pygame.draw.rect(surf, c_dark_red, (door_x+3, door_y+3, door_w-6, door_h-6))
        pygame.draw.line(surf, c_white, (door_x+6, door_y+6), (door_x+door_w-7, door_y+door_h-7), 4)
        pygame.draw.line(surf, c_white, (door_x+door_w-7, door_y+6), (door_x+6, door_y+door_h-7), 4)
        pygame.draw.circle(surf, (200, 180, 100), (door_x+door_w//4, door_y+door_h//2), 5)
        pygame.draw.circle(surf, (200, 180, 100), (door_x+door_w*3//4, door_y+door_h//2), 5)
        window_positions = [(body_x + 25, body_y + 30), (body_x + body_w - 55, body_y + 30),
                           (body_x + 25, body_y + 80), (body_x + body_w - 55, body_y + 80)]
        for wx, wy in window_positions:
            pygame.draw.rect(surf, c_white, (wx-2, wy-2, 26, 26), border_radius=4)
            pygame.draw.rect(surf, (135, 206, 235), (wx, wy, 22, 22), border_radius=3)
            pygame.draw.line(surf, c_white, (wx+11, wy), (wx+11, wy+22), 3)
            pygame.draw.line(surf, c_white, (wx, wy+11), (wx+22, wy+11), 3)
        roof_h = 55
        roof_y = body_y - roof_h + 10
        roof_center_x = w//2
        roof_radius = body_w // 2 + 10
        points = []
        for angle in range(180, 360, 5):
            rad = math.radians(angle)
            x = roof_center_x + math.cos(rad) * roof_radius
            y = roof_y + roof_h + math.sin(rad) * roof_h
            points.append((x, y))
        points.append((body_x + body_w, roof_y + roof_h))
        points.append((body_x, roof_y + roof_h))
        pygame.draw.polygon(surf, c_roof, points)
        pygame.draw.polygon(surf, (90, 85, 95), points, 3)
        for i in range(1, 4):
            y_offset = i * 12
            points_curve = []
            for angle in range(180, 360, 5):
                rad = math.radians(angle)
                x = roof_center_x + math.cos(rad) * (roof_radius - i*8)
                y = roof_y + roof_h + math.sin(rad) * (roof_h - i*8)
                points_curve.append((x, y))
            if points_curve:
                pygame.draw.lines(surf, (90, 85, 95), False, points_curve, 2)
        vane_x = w//2
        vane_y = roof_y - 8
        pygame.draw.line(surf, (80, 80, 85), (vane_x, vane_y), (vane_x, vane_y-18), 3)
        pygame.draw.line(surf, (80, 80, 85), (vane_x-12, vane_y-10), (vane_x+12, vane_y-10), 2)
        pygame.draw.polygon(surf, (200, 180, 50), [(vane_x, vane_y-22), (vane_x-4, vane_y-14), (vane_x+4, vane_y-14)])
        pygame.draw.circle(surf, (150, 150, 155), (vane_x, vane_y-18), 3)
        return surf

    @staticmethod
    def draw_cozy_house():
        w, h = TILE_SIZE*4, TILE_SIZE*3
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (230,215,190), (20,40,w-40,h-45), border_radius=4)
        pygame.draw.polygon(surf, (50,55,65), [(w//2,5),(10,42),(w-10,42)])
        pygame.draw.rect(surf, (110,75,45), (w//4-12,60,24,24), border_radius=2)
        pygame.draw.rect(surf, (135,210,240), (w//4-10,62,20,20))
        pygame.draw.rect(surf, (110,75,45), (3*w//4-12,60,24,24), border_radius=2)
        pygame.draw.rect(surf, (135,210,240), (3*w//4-10,62,20,20))
        pygame.draw.rect(surf, (135,85,50), (w//2-15,h-45,30,40), border_radius=2)
        pygame.draw.circle(surf, (235,185,40), (w//2+8, h-25),2)
        return surf

    @staticmethod
    def draw_realistic_wheat_seed():
        surf = pygame.Surface((28, 28), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (210, 185, 120), (6, 10, 16, 12))
        pygame.draw.ellipse(surf, (190, 160, 95), (6, 10, 16, 12), 2)
        pygame.draw.line(surf, (170, 140, 75), (10, 13), (18, 19), 2)
        pygame.draw.line(surf, (170, 140, 75), (10, 19), (18, 13), 1)
        pygame.draw.ellipse(surf, (235, 215, 170), (8, 11, 5, 4))
        pygame.draw.circle(surf, (200, 175, 105), (7, 14), 2)
        pygame.draw.circle(surf, (200, 175, 105), (21, 18), 2)
        for _ in range(8):
            x = random.randint(9, 19)
            y = random.randint(12, 20)
            pygame.draw.circle(surf, (180, 155, 85), (x, y), 1)
        return surf

    @staticmethod
    def draw_realistic_corn_seed():
        surf = pygame.Surface((28, 28), pygame.SRCALPHA)
        points = [(14, 8), (22, 14), (20, 22), (8, 22), (6, 14)]
        pygame.draw.polygon(surf, (255, 210, 100), points)
        pygame.draw.polygon(surf, (230, 180, 70), points, 2)
        pygame.draw.line(surf, (220, 170, 60), (10, 14), (18, 20), 2)
        pygame.draw.line(surf, (220, 170, 60), (18, 14), (10, 20), 1)
        pygame.draw.ellipse(surf, (255, 235, 160), (10, 11, 6, 5))
        pygame.draw.circle(surf, (200, 160, 55), (8, 16), 2)
        for i in range(3):
            pygame.draw.line(surf, (210, 170, 65), (12 + i*3, 12), (12 + i*3, 22), 1)
        return surf

    @staticmethod
    def draw_realistic_harvested_wheat():
        surf = pygame.Surface((36, 36), pygame.SRCALPHA)
        for i in range(6):
            x = 10 + i * 4
            pygame.draw.line(surf, (180, 160, 100), (x, 28), (x, 10), 2)
            for j in range(3):
                pygame.draw.ellipse(surf, (220, 185, 70), (x-3, 6 + j*3, 6, 5))
            pygame.draw.line(surf, (200, 170, 80), (x, 6), (x-4, 2), 1)
            pygame.draw.line(surf, (200, 170, 80), (x, 6), (x+4, 2), 1)
        pygame.draw.ellipse(surf, (150, 100, 60), (8, 24, 20, 6))
        pygame.draw.line(surf, (180, 130, 80), (10, 27), (26, 27), 2)
        pygame.draw.ellipse(surf, (40, 30, 20, 80), (8, 30, 20, 5))
        return surf

    @staticmethod
    def draw_realistic_harvested_corn():
        surf = pygame.Surface((36, 36), pygame.SRCALPHA)
        pygame.draw.rect(surf, (255, 220, 110), (12, 8, 12, 22), border_radius=4)
        pygame.draw.rect(surf, (230, 190, 80), (12, 8, 12, 22), 2, border_radius=4)
        for i in range(4):
            for j in range(5):
                if i % 2 == 0:
                    kx = 14 + i * 2
                    ky = 10 + j * 4
                else:
                    kx = 13 + i * 2
                    ky = 12 + j * 4
                pygame.draw.rect(surf, (255, 200, 80), (kx, ky, 3, 3), border_radius=1)
        for i in range(3):
            pygame.draw.ellipse(surf, (100, 160, 70), (10 + i*3, 4, 6, 10))
        for i in range(5):
            pygame.draw.line(surf, (180, 150, 80), (14 + i*2, 8), (14 + i*2, 2), 1)
            pygame.draw.line(surf, (180, 150, 80), (14 + i*2, 8), (14 + i*2, 2), 1)
        pygame.draw.ellipse(surf, (200, 180, 90), (13, 28, 10, 4))
        return surf

    @staticmethod
    def draw_wheat_plant(growth):
        surf = pygame.Surface((48, 48), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (20, 40, 15, 70), (14, 39, 20, 6))

        if growth < 0.3:
            pygame.draw.line(surf, (55, 115, 42), (24, 40), (24, 30), 3)
            pygame.draw.polygon(surf, (70, 150, 55), [(24, 32), (18, 24), (22, 26), (24, 30)])
            pygame.draw.polygon(surf, (90, 175, 68), [(24, 32), (30, 25), (25, 27), (24, 30)])

        elif growth < 0.7:
            pygame.draw.line(surf, (48, 105, 38), (24, 40), (24, 20), 4)
            pygame.draw.polygon(surf, (62, 130, 48), [(24, 30), (13, 20), (18, 22), (24, 26)])
            pygame.draw.polygon(surf, (78, 155, 60), [(24, 30), (14, 21), (19, 23), (24, 27)])
            pygame.draw.polygon(surf, (62, 130, 48), [(24, 26), (35, 17), (30, 19), (24, 22)])
            pygame.draw.polygon(surf, (78, 155, 60), [(24, 26), (34, 18), (29, 20), (24, 23)])

        else:
            cx = 24
            # Central stem
            pygame.draw.rect(surf, (210, 160, 65), (cx-1, 6, 2, 36))

            # Scattered small kernel blocks jutting out at varying heights,
            # sides, and angles — sparse and irregular, not neat symmetric rows.
            random.seed(hash((growth, "wheat_head")) % 10000)  # stable per-tile look
            blocks = [
                (10, -1, 3), (9, 1, 4),
                (14, -2, 4), (13, 2, 3),
                (18, -3, 5), (17, 1, 4),
                (22, -2, 3), (23, 3, 5),
                (26, -4, 4), (25, 2, 3),
                (30, -3, 5), (31, 3, 4),
                (34, -2, 3), (33, 2, 4),
            ]
            colors = [(238, 160, 60), (228, 138, 45), (218, 118, 35)]
            for i, (y, side, length) in enumerate(blocks):
                color = colors[i % len(colors)]
                dark = tuple(max(0, c - 30) for c in color)
                x_dir = 1 if side > 0 else -1
                bx = cx + (2 * x_dir)
                for j in range(length):
                    bw = 3
                    bh = 3
                    px = bx + j * x_dir * bw - (bw if x_dir < 0 else 0)
                    py = y - j  # angles slightly upward as it extends outward
                    c = color if j < length - 1 else dark
                    pygame.draw.rect(surf, c, (px, py, bw, bh))

            # Small tip at the very top
            pygame.draw.rect(surf, (240, 170, 70), (cx-2, 4, 4, 4))
            pygame.draw.rect(surf, (230, 150, 55), (cx-1, 2, 2, 3))
        return surf

    @staticmethod
    def draw_corn_plant(growth):
        surf = pygame.Surface((48, 48), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (20, 40, 15, 70), (13, 39, 22, 6))

        if growth < 0.3:
            pygame.draw.line(surf, (48, 105, 38), (24, 40), (24, 28), 3)
            pygame.draw.polygon(surf, (62, 130, 48), [(24, 32), (16, 26), (21, 27), (24, 30)])
            pygame.draw.polygon(surf, (80, 155, 62), [(24, 32), (32, 27), (27, 28), (24, 30)])

        elif growth < 0.7:
            pygame.draw.line(surf, (42, 95, 35), (24, 40), (24, 14), 5)
            pygame.draw.polygon(surf, (54, 120, 42), [(24, 30), (9, 24), (16, 26), (24, 27)])
            pygame.draw.polygon(surf, (70, 145, 55), [(24, 30), (10, 25), (17, 27), (24, 28)])
            pygame.draw.polygon(surf, (54, 120, 42), [(24, 24), (39, 18), (32, 20), (24, 21)])
            pygame.draw.polygon(surf, (70, 145, 55), [(24, 24), (38, 19), (31, 21), (24, 22)])
            pygame.draw.polygon(surf, (62, 132, 48), [(24, 18), (18, 10), (22, 13), (24, 16)])

        else:
            pygame.draw.line(surf, (48, 105, 38), (24, 40), (24, 8), 6)
            pygame.draw.polygon(surf, (48, 110, 38), [(24, 30), (7, 24), (15, 26), (24, 27)])
            pygame.draw.polygon(surf, (65, 138, 52), [(24, 30), (8, 25), (16, 27), (24, 28)])
            pygame.draw.polygon(surf, (48, 110, 38), [(24, 22), (42, 15), (34, 18), (24, 19)])
            pygame.draw.polygon(surf, (65, 138, 52), [(24, 22), (41, 16), (33, 19), (24, 20)])

            # Ear of corn with shaded husk and kernel texture
            ear_x, ear_y, ear_w, ear_h = 17, 22, 14, 16
            pygame.draw.rect(surf, (215, 175, 70), (ear_x, ear_y, ear_w, ear_h), border_radius=5)
            pygame.draw.rect(surf, (250, 225, 115), (ear_x+2, ear_y+1, ear_w-5, ear_h-3), border_radius=4)
            for row in range(4):
                for col in range(3):
                    kx = ear_x + 3 + col*3
                    ky = ear_y + 3 + row*3
                    pygame.draw.rect(surf, (255, 205, 85), (kx, ky, 2, 2), border_radius=1)
            # Husk leaves wrapping the ear base
            pygame.draw.polygon(surf, (75, 145, 58), [(ear_x, ear_y+ear_h-2), (ear_x-4, ear_y+ear_h+6), (ear_x+3, ear_y+ear_h-2)])
            pygame.draw.polygon(surf, (60, 128, 48), [(ear_x+ear_w, ear_y+ear_h-2), (ear_x+ear_w+4, ear_y+ear_h+6), (ear_x+ear_w-3, ear_y+ear_h-2)])

            # Tassel at the very top
            tassel_x, tassel_y = 24, 8
            for i in range(5):
                ang = -20 + i*10
                dx = math.sin(math.radians(ang)) * 8
                pygame.draw.line(surf, (200, 175, 90), (tassel_x, tassel_y+6), (tassel_x+dx, tassel_y-4), 1)
            pygame.draw.ellipse(surf, (210, 185, 100), (tassel_x-3, tassel_y+3, 6, 5))

        return surf
    
    @staticmethod
    def draw_orange_tree(with_fruits=True):
        w, h = 96, 130
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        # Ground shadow
        pygame.draw.ellipse(surf, (20, 60, 15, 90), (w//2-30, h-14, 60, 16))

        # Trunk with grain
        pygame.draw.rect(surf, (95, 62, 38), (w//2-11, h-62, 22, 62), border_radius=6)
        pygame.draw.rect(surf, (120, 80, 48), (w//2-9, h-60, 12, 58), border_radius=5)
        for gy in range(h-56, h-6, 9):
            pygame.draw.line(surf, (75, 48, 28), (w//2-6, gy), (w//2-6, gy+5), 1)
            pygame.draw.line(surf, (75, 48, 28), (w//2+4, gy+3), (w//2+4, gy+8), 1)

        # Branches tucked under canopy
        branches = [
            (w//2, h-56, w//2-16, h-72),
            (w//2, h-52, w//2+14, h-74),
            (w//2-3, h-58, w//2-20, h-78),
        ]
        for x1, y1, x2, y2 in branches:
            pygame.draw.line(surf, (85, 55, 32), (x1, y1), (x2, y2), 4)

        # Irregular, lumpy canopy silhouette
        cx, cy = w//2, h-94
        lobes = [
            (cx-2, cy+4, 78, 62),
            (cx-24, cy-6, 46, 42),
            (cx+22, cy-2, 44, 40),
            (cx-6, cy-24, 50, 44),
            (cx+14, cy+16, 40, 32),
        ]
        for lx, ly, lw, lh in lobes:
            pygame.draw.ellipse(surf, (14, 78, 18), (lx-lw//2, ly-lh//2+5, lw, lh))
        for lx, ly, lw, lh in lobes:
            pygame.draw.ellipse(surf, (26, 120, 30), (lx-lw//2, ly-lh//2, lw, lh))
        pygame.draw.ellipse(surf, (58, 160, 58), (cx-40, cy-38, 46, 38))
        pygame.draw.ellipse(surf, (100, 200, 92), (cx-32, cy-32, 26, 22))

        # Fruits nestled within the canopy silhouette
        if with_fruits:
            fruit_positions = [
                (-24, -2), (14, -14), (-6, 8),
                (18, 12), (-28, 18), (6, 24),
                (-4, 30), (-16, -18), (14, -28),
                (26, -4)
            ]
            for fx, fy in fruit_positions:
                size = random.randint(8, 11)
                px = cx + fx
                py = cy + fy
                pygame.draw.circle(surf, (235, 125, 30), (px, py), size)
                pygame.draw.circle(surf, (200, 88, 12), (px, py), size-2)
                pygame.draw.circle(surf, (255, 215, 135), (px - size//3, py - size//3), max(2, size//3))
                pygame.draw.line(surf, (60, 95, 35), (px, py - size), (px, py - size + 3), 1)

        return surf

    @staticmethod
    def draw_apple_tree(with_fruits=True):
        w, h = 96, 130
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        # Ground shadow
        pygame.draw.ellipse(surf, (20, 60, 15, 90), (w//2-30, h-14, 60, 16))

        # Trunk with grain
        pygame.draw.rect(surf, (95, 62, 38), (w//2-11, h-62, 22, 62), border_radius=6)
        pygame.draw.rect(surf, (120, 80, 48), (w//2-9, h-60, 12, 58), border_radius=5)
        for gy in range(h-56, h-6, 9):
            pygame.draw.line(surf, (75, 48, 28), (w//2-6, gy), (w//2-6, gy+5), 1)
            pygame.draw.line(surf, (75, 48, 28), (w//2+4, gy+3), (w//2+4, gy+8), 1)

        # Branches tucked under canopy
        branches = [
            (w//2, h-56, w//2-16, h-72),
            (w//2, h-52, w//2+14, h-74),
            (w//2-3, h-58, w//2-20, h-78),
        ]
        for x1, y1, x2, y2 in branches:
            pygame.draw.line(surf, (85, 55, 32), (x1, y1), (x2, y2), 4)

        # Irregular, lumpy canopy silhouette
        cx, cy = w//2, h-94
        lobes = [
            (cx-2, cy+4, 78, 62),
            (cx-24, cy-6, 46, 42),
            (cx+22, cy-2, 44, 40),
            (cx-6, cy-24, 50, 44),
            (cx+14, cy+16, 40, 32),
        ]
        for lx, ly, lw, lh in lobes:
            pygame.draw.ellipse(surf, (16, 82, 20), (lx-lw//2, ly-lh//2+5, lw, lh))
        for lx, ly, lw, lh in lobes:
            pygame.draw.ellipse(surf, (28, 122, 32), (lx-lw//2, ly-lh//2, lw, lh))
        pygame.draw.ellipse(surf, (60, 165, 60), (cx-40, cy-38, 46, 38))
        pygame.draw.ellipse(surf, (105, 205, 95), (cx-32, cy-32, 26, 22))

        # Fruits nestled within the canopy silhouette
        if with_fruits:
            fruit_positions = [
                (-24, -2), (14, -14), (-6, 8),
                (18, 12), (-28, 18), (6, 24),
                (-4, 30), (-16, -18), (14, -28),
                (26, -4)
            ]
            for fx, fy in fruit_positions:
                size = random.randint(8, 10)
                px = cx + fx
                py = cy + fy
                pygame.draw.circle(surf, (200, 30, 30), (px, py), size)
                pygame.draw.circle(surf, (220, 45, 40), (px, py), size-2)
                pygame.draw.circle(surf, (255, 190, 185), (px - size//3, py - size//3), max(2, size//3))
                pygame.draw.line(surf, (60, 95, 35), (px, py - size), (px, py - size + 3), 1)

        return surf

    @staticmethod
    def draw_apple_tree(with_fruits=True):
        w, h = 96, 130
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        # Ground shadow
        pygame.draw.ellipse(surf, (20, 60, 15, 90), (w//2-30, h-14, 60, 16))

        # Trunk with grain
        pygame.draw.rect(surf, (95, 62, 38), (w//2-11, h-62, 22, 62), border_radius=6)
        pygame.draw.rect(surf, (120, 80, 48), (w//2-9, h-60, 12, 58), border_radius=5)
        for gy in range(h-56, h-6, 9):
            pygame.draw.line(surf, (75, 48, 28), (w//2-6, gy), (w//2-6, gy+5), 1)
            pygame.draw.line(surf, (75, 48, 28), (w//2+4, gy+3), (w//2+4, gy+8), 1)

        # Branches tucked under canopy
        branches = [
            (w//2, h-56, w//2-16, h-72),
            (w//2, h-52, w//2+14, h-74),
            (w//2-3, h-58, w//2-20, h-78),
        ]
        for x1, y1, x2, y2 in branches:
            pygame.draw.line(surf, (85, 55, 32), (x1, y1), (x2, y2), 4)

        # Irregular, lumpy canopy silhouette (several overlapping ellipses,
        # varied sizes/offsets, so it doesn't read as one perfect circle)
        cx, cy = w//2, h-94
        lobes = [
            (cx-2, cy+4, 78, 62),      # main mass
            (cx-24, cy-6, 46, 42),     # left lobe
            (cx+22, cy-2, 44, 40),     # right lobe
            (cx-6, cy-24, 50, 44),     # top lobe
            (cx+14, cy+16, 40, 32),    # bottom-right lobe
        ]
        # Dark shadow base
        for lx, ly, lw, lh in lobes:
            pygame.draw.ellipse(surf, (16, 82, 20), (lx-lw//2, ly-lh//2+5, lw, lh))
        # Mid-tone
        for lx, ly, lw, lh in lobes:
            pygame.draw.ellipse(surf, (28, 122, 32), (lx-lw//2, ly-lh//2, lw, lh))
        # Highlight patch, upper-left, noticeably brighter and larger
        pygame.draw.ellipse(surf, (60, 165, 60), (cx-40, cy-38, 46, 38))
        pygame.draw.ellipse(surf, (105, 205, 95), (cx-32, cy-32, 26, 22))

        # Fruits nestled within the canopy silhouette
        if with_fruits:
            fruit_positions = [
                (-24, -2), (14, -14), (-6, 8),
                (18, 12), (-28, 18), (6, 24),
                (-4, 30), (-16, -18), (14, -28),
                (26, -4)
            ]
            for fx, fy in fruit_positions:
                size = random.randint(8, 10)
                px = cx + fx
                py = cy + fy
                pygame.draw.circle(surf, (200, 30, 30), (px, py), size)
                pygame.draw.circle(surf, (220, 45, 40), (px, py), size-2)
                pygame.draw.circle(surf, (255, 190, 185), (px - size//3, py - size//3), max(2, size//3))
                pygame.draw.line(surf, (60, 95, 35), (px, py - size), (px, py - size + 3), 1)

        return surf
    
    @staticmethod
    def draw_chicken_coop():
        w, h = TILE_SIZE*3, TILE_SIZE*2
        surf = pygame.Surface((w,h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (160,110,70), (8,20,w-16,h-25), border_radius=3)
        pygame.draw.rect(surf, (120,80,50), (8,20,w-16,h-25),2)
        roof_pts = [(w//2,2),(0,22),(w,22)]
        pygame.draw.polygon(surf, (90,90,100), roof_pts)
        pygame.draw.polygon(surf, (130,130,140), roof_pts,2)
        for i in range(3):
            bx = 12+i*28
            pygame.draw.rect(surf, (180,130,90), (bx, h-28,24,20), border_radius=2)
            pygame.draw.rect(surf, (100,70,40), (bx+2, h-26,20,16))
            for s in range(4):
                pygame.draw.line(surf, (220,190,120), (bx+4+s*4, h-20), (bx+8+s*2, h-12),1)
        ramp_pts = [(w-20, h-15), (w-5, h-5), (w-20, h-5)]
        pygame.draw.polygon(surf, (140,100,60), ramp_pts)
        for rung in range(3):
            pygame.draw.line(surf, (90,60,30), (w-18, h-12-rung*3), (w-8, h-5-rung*3),1)
        pygame.draw.rect(surf, (80,55,35), (w//2-8, h-22,16,14), border_radius=1)
        pygame.draw.circle(surf, (255,200,100), (w//2, h-16),2)
        run_w, run_h = 48,32
        run_x, run_y = w-10, h-run_h-5
        pygame.draw.rect(surf, (200,200,210,100), (run_x, run_y, run_w, run_h),1)
        for i in range(0, run_w, 6):
            pygame.draw.line(surf, (180,180,190,80), (run_x+i, run_y), (run_x+i, run_y+run_h),1)
        for i in range(0, run_h, 6):
            pygame.draw.line(surf, (180,180,190,80), (run_x, run_y+i), (run_x+run_w, run_y+i),1)
        return surf

# Pre‑generate fixed textures
TEX_WHEAT_FIELD = ArtEngine.create_golden_wheat(TILE_SIZE)
TEX_SOIL = ArtEngine.create_soil_texture(TILE_SIZE)
TEX_BARN = ArtEngine.draw_realistic_barn()
TEX_HOUSE = ArtEngine.draw_cozy_house()
TEX_VENDING_MACHINE = ArtEngine.draw_tall_vending_machine()
TEX_TRUCK = pygame.transform.flip(ArtEngine.draw_new_premium_truck(), True, False)
TEX_SCARECROW = ArtEngine.draw_improved_scarecrow()
TEX_ORANGE_TREE = ArtEngine.draw_orange_tree(True)
TEX_APPLE_TREE = ArtEngine.draw_apple_tree(True)
TEX_ORANGE_TREE_NO_FRUITS = ArtEngine.draw_orange_tree(False)
TEX_APPLE_TREE_NO_FRUITS = ArtEngine.draw_apple_tree(False)
TEX_FENCE = ArtEngine.draw_beautiful_fence()
TEX_FENCE_POST_ONLY = ArtEngine.draw_fence_post_texture()
TEX_FENCE_RAIL_H = ArtEngine.draw_fence_rail_segment(horizontal=True)
TEX_FENCE_RAIL_V = ArtEngine.draw_fence_rail_segment(horizontal=False)
TEX_FENCE_POST = ArtEngine.draw_cattle_fence_post()
TEX_CHICKEN_COOP = ArtEngine.draw_chicken_coop()
TEX_GRASS = ArtEngine.create_grass_seasonal("spring")

# Pre-generate plant textures
WHEAT_PLANTS = {
    "seedling": ArtEngine.draw_wheat_plant(0.2),
    "growing": ArtEngine.draw_wheat_plant(0.5),
    "mature": ArtEngine.draw_wheat_plant(1.0)
}

CORN_PLANTS = {
    "seedling": ArtEngine.draw_corn_plant(0.2),
    "growing": ArtEngine.draw_corn_plant(0.5),
    "mature": ArtEngine.draw_corn_plant(1.0)
}

# Seed textures for toolbar
TEX_WHEAT_SEED = ArtEngine.draw_realistic_wheat_seed()
TEX_CORN_SEED = ArtEngine.draw_realistic_corn_seed()
TEX_HARVESTED_WHEAT = ArtEngine.draw_realistic_harvested_wheat()
TEX_HARVESTED_CORN = ArtEngine.draw_realistic_harvested_corn()

# ==========================================
# INVENTORY SYSTEM
# ==========================================
class Inventory:
    def __init__(self):
        self.items = {
            "wheat_seed": 20,
            "corn_seed": 10,
            "wheat": 0,
            "corn": 0,
            "orange": 0,
            "apple": 0,
            "milk": 0,
            "egg": 0
        }
        self.selected_slot = 0
        self.toolbar = ["wheat_seed", "corn_seed", None, None, None]

    def add(self, item, amt=1):
        if item in self.items:
            self.items[item] += amt
            return True
        return False

    def remove(self, item, amt=1):
        if self.items.get(item, 0) >= amt:
            self.items[item] -= amt
            return True
        return False

    def get_selected_item(self):
        if self.selected_slot < len(self.toolbar):
            return self.toolbar[self.selected_slot]
        return None

# ==========================================
# VENDING MACHINE SYSTEM
# ==========================================
class VendingMachine:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.active = False
        self.energy_drink_price = 10
        self.energy_restore_amount = 50
        
    def open_menu(self):
        self.active = True
        
    def close_menu(self):
        self.active = False
        
    def buy_energy_drink(self, game_state):
        if game_state.money >= self.energy_drink_price:
            game_state.money -= self.energy_drink_price
            game_state.energy = min(game_state.max_energy, game_state.energy + self.energy_restore_amount)
            return True, f"✓ Bought Energy Drink! Restored {self.energy_restore_amount} energy! -${self.energy_drink_price}"
        else:
            return False, f"✗ Not enough money! Need ${self.energy_drink_price}"
    
    def draw_menu(self, surf, game_state):
        if not self.active:
            return None
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill((0,0,0))
        overlay.set_alpha(200)
        surf.blit(overlay, (0,0))
        panel_w, panel_h = 450, 400
        panel_x = (SCREEN_WIDTH - panel_w) // 2
        panel_y = (SCREEN_HEIGHT - panel_h) // 2
        pygame.draw.rect(surf, (50,50,70), (panel_x, panel_y, panel_w, panel_h), border_radius=15)
        pygame.draw.rect(surf, COLOR_GOLD, (panel_x, panel_y, panel_w, panel_h), 3, border_radius=15)
        font_big = pygame.font.Font(None, 36)
        title = font_big.render("🥤 VENDING MACHINE 🥤", True, COLOR_GOLD)
        surf.blit(title, (panel_x + panel_w//2 - title.get_width()//2, panel_y + 15))
        mini_vending = pygame.Surface((100, 120), pygame.SRCALPHA)
        mini_vending.fill((70, 75, 80))
        pygame.draw.rect(mini_vending, (200, 60, 50), (5, 5, 90, 15), border_radius=2)
        pygame.draw.rect(mini_vending, (180, 220, 240, 200), (5, 25, 90, 50), border_radius=2)
        for i in range(3):
            pygame.draw.rect(mini_vending, (50, 180, 90), (10 + i*30, 30, 15, 15), border_radius=2)
            pygame.draw.polygon(mini_vending, (255, 255, 100), [(13 + i*30, 33), (17 + i*30, 35), (13 + i*30, 38), (20 + i*30, 35), (15 + i*30, 33)])
        pygame.draw.rect(mini_vending, (40, 40, 45), (25, 80, 30, 5), border_radius=1)
        pygame.draw.rect(mini_vending, (255, 200, 50), (28, 79, 24, 3))
        surf.blit(mini_vending, (panel_x + 50, panel_y + 60))
        font_med = pygame.font.Font(None, 24)
        name_text = font_med.render("Energy Drink", True, COLOR_WHITE)
        surf.blit(name_text, (panel_x + 170, panel_y + 80))
        price_text = font_med.render(f"Price: ${self.energy_drink_price}", True, COLOR_GOLD)
        surf.blit(price_text, (panel_x + 170, panel_y + 110))
        restore_text = font_med.render(f"Restores: {self.energy_restore_amount} Energy", True, COLOR_ENERGY)
        surf.blit(restore_text, (panel_x + 170, panel_y + 140))
        buy_rect = pygame.Rect(panel_x + 170, panel_y + 180, 120, 45)
        pygame.draw.rect(surf, (60, 140, 60), buy_rect, border_radius=8)
        pygame.draw.rect(surf, COLOR_GOLD, buy_rect, 2, border_radius=8)
        buy_text = font_med.render("💰 BUY NOW", True, COLOR_WHITE)
        surf.blit(buy_text, (buy_rect.x + 15, buy_rect.y + 12))
        close_rect = pygame.Rect(panel_x + panel_w - 80, panel_y + 15, 60, 30)
        pygame.draw.rect(surf, (100, 60, 60), close_rect, border_radius=5)
        close_text = font_med.render("Close", True, COLOR_WHITE)
        surf.blit(close_text, (close_rect.x + 12, close_rect.y + 7))
        money_text = font_med.render(f"💰 Your Money: ${game_state.money}", True, COLOR_GOLD)
        surf.blit(money_text, (panel_x + 30, panel_y + panel_h - 50))
        energy_text = font_med.render(f"⚡ Your Energy: {int(game_state.energy)}/{game_state.max_energy}", True, COLOR_ENERGY)
        surf.blit(energy_text, (panel_x + 30, panel_y + panel_h - 25))
        font_small = pygame.font.Font(None, 16)  # Fixed: properly define font_small
        info_text = font_small.render("Press the button to buy!", True, (200, 200, 200))
        surf.blit(info_text, (panel_x + 30, panel_y + 250))
        return buy_rect, close_rect
    
    def handle_click(self, pos, game_state):
        if not self.active:
            return False
        panel_w, panel_h = 450, 400
        panel_x = (SCREEN_WIDTH - panel_w) // 2
        panel_y = (SCREEN_HEIGHT - panel_h) // 2
        buy_rect = pygame.Rect(panel_x + 170, panel_y + 180, 120, 45)
        close_rect = pygame.Rect(panel_x + panel_w - 80, panel_y + 15, 60, 30)
        if buy_rect.collidepoint(pos):
            success, message = self.buy_energy_drink(game_state)
            return success, message
        elif close_rect.collidepoint(pos):
            self.active = False
            return True, None
        return False, None

# ==========================================
# TRUCK SYSTEM - City Market
# ==========================================
class CityMarket:
    def __init__(self):
        self.active = False
        self.prices = {
            "wheat": 15,
            "corn": 20,
            "orange": 25,
            "apple": 30,
            "milk": 40,
            "egg": 15
        }
        self.selected_item = None
        self.sell_amount = 1
        self.total_sale = 0
        self.message = ""
        self.message_timer = 0
        
    def open_market(self):
        self.active = True
        self.selected_item = None
        self.sell_amount = 1
        self.total_sale = 0
        self.message = ""
        
    def close_market(self):
        self.active = False
        
    def sell_item(self, item, amount, inventory, game_state):
        if item in inventory.items and inventory.items[item] >= amount:
            price_per = self.prices.get(item, 10)
            total = price_per * amount
            inventory.remove(item, amount)
            game_state.money += total
            game_state.add_exp(amount * 2)
            game_state.energy = max(0, game_state.energy - amount * 0.5)
            self.message = f"✓ Sold {amount} {item}(s) for ${total}! +{amount*2} XP, -{int(amount*0.5)} energy"
            self.message_timer = 120
            return True
        else:
            self.message = f"✗ Not enough {item} in inventory!"
            self.message_timer = 120
            return False
    
    def draw_market_ui(self, surf, game_state, inventory):
        if not self.active:
            return None
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill((0,0,0))
        overlay.set_alpha(200)
        surf.blit(overlay, (0,0))
        panel_w, panel_h = 700, 500
        panel_x = (SCREEN_WIDTH - panel_w) // 2
        panel_y = (SCREEN_HEIGHT - panel_h) // 2
        pygame.draw.rect(surf, (50,50,70), (panel_x, panel_y, panel_w, panel_h), border_radius=15)
        pygame.draw.rect(surf, COLOR_GOLD, (panel_x, panel_y, panel_w, panel_h), 3, border_radius=15)
        font_big = pygame.font.Font(None, 36)
        title = font_big.render("🏙️ CITY MARKET - SELL YOUR GOODS! 🏙️", True, COLOR_GOLD)
        surf.blit(title, (panel_x + panel_w//2 - title.get_width()//2, panel_y + 15))
        font_med = pygame.font.Font(None, 24)
        font_small = pygame.font.Font(None, 18)
        items = [
            ("wheat", TEX_HARVESTED_WHEAT, "🌾 Wheat"),
            ("corn", TEX_HARVESTED_CORN, "🌽 Corn"),
            ("orange", TEX_ORANGE_TREE, "🍊 Orange"),
            ("apple", TEX_APPLE_TREE, "🍎 Apple"),
            ("milk", None, "🥛 Milk"),
            ("egg", None, "🥚 Egg")
        ]
        y_offset = panel_y + 70
        for i, (item_key, icon, display_name) in enumerate(items):
            item_rect = pygame.Rect(panel_x + 20, y_offset + i * 55, panel_w - 40, 48)
            color = (80,80,110) if self.selected_item != item_key else (100,180,100)
            pygame.draw.rect(surf, color, item_rect, border_radius=8)
            pygame.draw.rect(surf, COLOR_GOLD if self.selected_item == item_key else (100,100,120), item_rect, 2, border_radius=8)
            if icon:
                scaled_icon = pygame.transform.scale(icon, (28, 28))
                surf.blit(scaled_icon, (item_rect.x + 10, item_rect.y + 10))
            name_text = font_med.render(display_name, True, COLOR_WHITE)
            surf.blit(name_text, (item_rect.x + 50, item_rect.y + 14))
            count = inventory.items.get(item_key, 0)
            count_text = font_med.render(f"x {count}", True, COLOR_WHITE)
            surf.blit(count_text, (item_rect.x + 180, item_rect.y + 14))
            price = self.prices.get(item_key, 10)
            price_text = font_med.render(f"${price}/ea", True, COLOR_GOLD)
            surf.blit(price_text, (item_rect.x + 280, item_rect.y + 14))
            if count > 0:
                sell_rect = pygame.Rect(item_rect.x + 400, item_rect.y + 8, 70, 32)
                pygame.draw.rect(surf, (60, 140, 60), sell_rect, border_radius=5)
                sell_text = font_small.render("SELL", True, COLOR_WHITE)
                surf.blit(sell_text, (sell_rect.x + 20, sell_rect.y + 8))
        if self.selected_item:
            amt_y = panel_y + panel_h - 80
            pygame.draw.rect(surf, (60,60,80), (panel_x + 20, amt_y, panel_w - 40, 50), border_radius=8)
            amt_text = font_med.render(f"Amount to sell: {self.sell_amount}", True, COLOR_WHITE)
            surf.blit(amt_text, (panel_x + 40, amt_y + 15))
            for i, amt in enumerate([1, 5, 10, 25, 50]):
                btn_x = panel_x + 250 + i * 70
                btn_rect = pygame.Rect(btn_x, amt_y + 8, 60, 34)
                color = (100,100,140) if self.sell_amount != amt else (60,180,60)
                pygame.draw.rect(surf, color, btn_rect, border_radius=5)
                amt_btn_text = font_small.render(str(amt), True, COLOR_WHITE)
                surf.blit(amt_btn_text, (btn_x + 22, amt_y + 15))
        if self.selected_item:
            price = self.prices.get(self.selected_item, 10)
            total = price * self.sell_amount
            total_text = font_med.render(f"Total: ${total}", True, COLOR_GOLD)
            surf.blit(total_text, (panel_x + panel_w - 200, panel_y + panel_h - 75))
        close_rect = pygame.Rect(panel_x + panel_w - 80, panel_y + 15, 60, 30)
        pygame.draw.rect(surf, (100, 60, 60), close_rect, border_radius=5)
        close_text = font_small.render("Close", True, COLOR_WHITE)
        surf.blit(close_text, (close_rect.x + 15, close_rect.y + 7))
        money_text = font_med.render(f"💰 Money: ${game_state.money}", True, COLOR_GOLD)
        surf.blit(money_text, (panel_x + 20, panel_y + panel_h - 30))
        if self.message and self.message_timer > 0:
            self.message_timer -= 1
            color = (100,200,100) if "✓" in self.message else (200,100,100)
            msg_surf = font_med.render(self.message, True, color)
            surf.blit(msg_surf, (panel_x + panel_w//2 - msg_surf.get_width()//2, panel_y + panel_h - 55))
        return close_rect
    
    def handle_click(self, pos, game_state, inventory):
        if not self.active:
            return False
        panel_w, panel_h = 700, 500
        panel_x = (SCREEN_WIDTH - panel_w) // 2
        panel_y = (SCREEN_HEIGHT - panel_h) // 2
        close_rect = pygame.Rect(panel_x + panel_w - 80, panel_y + 15, 60, 30)
        if close_rect.collidepoint(pos):
            self.active = False
            return True
        items = ["wheat", "corn", "orange", "apple", "milk", "egg"]
        y_offset = panel_y + 70
        for i, item_key in enumerate(items):
            item_rect = pygame.Rect(panel_x + 20, y_offset + i * 55, panel_w - 40, 48)
            if item_rect.collidepoint(pos):
                self.selected_item = item_key
                self.sell_amount = 1
                return True
            sell_rect = pygame.Rect(item_rect.x + 400, item_rect.y + 8, 70, 32)
            if sell_rect.collidepoint(pos) and inventory.items.get(item_key, 0) > 0:
                self.sell_item(item_key, self.sell_amount, inventory, game_state)
                return True
        if self.selected_item:
            amt_y = panel_y + panel_h - 80
            amounts = [1, 5, 10, 25, 50]
            for i, amt in enumerate(amounts):
                btn_x = panel_x + 250 + i * 70
                btn_rect = pygame.Rect(btn_x, amt_y + 8, 60, 34)
                if btn_rect.collidepoint(pos):
                    max_amt = inventory.items.get(self.selected_item, 0)
                    self.sell_amount = min(amt, max_amt)
                    if self.sell_amount == 0:
                        self.sell_amount = 1
                    return True
        return False

# ==========================================
# BARN STORAGE SYSTEM
# ==========================================
class BarnStorage:
    def __init__(self):
        self.stored_items = {
            "wheat": 0,
            "corn": 0,
            "orange": 0,
            "apple": 0,
            "milk": 0,
            "egg": 0
        }
        self.active = False
        
    def add_item(self, item, amount=1):
        if item in self.stored_items:
            self.stored_items[item] += amount
            return True
        return False
    
    def remove_item(self, item, amount=1):
        if item in self.stored_items and self.stored_items[item] >= amount:
            self.stored_items[item] -= amount
            return True
        return False
    
    def draw_storage_ui(self, surf, game_state, inventory):
        if not self.active:
            return None
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill((0,0,0))
        overlay.set_alpha(200)
        surf.blit(overlay, (0,0))
        panel_w, panel_h = 600, 500
        panel_x = (SCREEN_WIDTH - panel_w) // 2
        panel_y = (SCREEN_HEIGHT - panel_h) // 2
        pygame.draw.rect(surf, (50,50,70), (panel_x, panel_y, panel_w, panel_h), border_radius=15)
        pygame.draw.rect(surf, COLOR_GOLD, (panel_x, panel_y, panel_w, panel_h), 3, border_radius=15)
        font_big = pygame.font.Font(None, 36)
        title = font_big.render("🏠 Barn Storage 🏠", True, COLOR_GOLD)
        surf.blit(title, (panel_x + panel_w//2 - title.get_width()//2, panel_y + 15))
        font_med = pygame.font.Font(None, 24)
        font_small = pygame.font.Font(None, 18)
        inv_text = font_med.render("📦 INVENTORY", True, (200, 200, 200))
        surf.blit(inv_text, (panel_x + 30, panel_y + 60))
        items = [
            ("wheat", TEX_HARVESTED_WHEAT, "🌾 Wheat"),
            ("corn", TEX_HARVESTED_CORN, "🌽 Corn"),
            ("orange", TEX_ORANGE_TREE, "🍊 Orange"),
            ("apple", TEX_APPLE_TREE, "🍎 Apple"),
            ("milk", None, "🥛 Milk"),
            ("egg", None, "🥚 Egg")
        ]
        y_offset = panel_y + 90
        for i, (item_key, icon, display_name) in enumerate(items):
            inv_item_rect = pygame.Rect(panel_x + 20, y_offset + i * 50, 250, 42)
            pygame.draw.rect(surf, (60, 60, 80), inv_item_rect, border_radius=6)
            pygame.draw.rect(surf, (100, 100, 120), inv_item_rect, 1, border_radius=6)
            if icon:
                scaled_icon = pygame.transform.scale(icon, (28, 28))
                surf.blit(scaled_icon, (inv_item_rect.x + 8, inv_item_rect.y + 7))
            name_text = font_small.render(display_name, True, COLOR_WHITE)
            surf.blit(name_text, (inv_item_rect.x + 45, inv_item_rect.y + 14))
            count = inventory.items.get(item_key, 0)
            count_text = font_small.render(f"x {count}", True, COLOR_GOLD)
            surf.blit(count_text, (inv_item_rect.x + 190, inv_item_rect.y + 14))
            if count > 0:
                store_rect = pygame.Rect(inv_item_rect.x + 215, inv_item_rect.y + 6, 30, 30)
                pygame.draw.rect(surf, (60, 140, 60), store_rect, border_radius=5)
                store_text = font_small.render("→", True, COLOR_WHITE)
                surf.blit(store_text, (store_rect.x + 10, store_rect.y + 8))
        barn_text = font_med.render("🏠 BARN STORAGE", True, (200, 200, 200))
        surf.blit(barn_text, (panel_x + 320, panel_y + 60))
        y_offset = panel_y + 90
        for i, (item_key, icon, display_name) in enumerate(items):
            barn_item_rect = pygame.Rect(panel_x + 310, y_offset + i * 50, 250, 42)
            pygame.draw.rect(surf, (40, 60, 40), barn_item_rect, border_radius=6)
            pygame.draw.rect(surf, (80, 120, 80), barn_item_rect, 1, border_radius=6)
            if icon:
                scaled_icon = pygame.transform.scale(icon, (28, 28))
                surf.blit(scaled_icon, (barn_item_rect.x + 8, barn_item_rect.y + 7))
            name_text = font_small.render(display_name, True, COLOR_WHITE)
            surf.blit(name_text, (barn_item_rect.x + 45, barn_item_rect.y + 14))
            count = self.stored_items.get(item_key, 0)
            count_text = font_small.render(f"x {count}", True, COLOR_GOLD)
            surf.blit(count_text, (barn_item_rect.x + 190, barn_item_rect.y + 14))
        close_rect = pygame.Rect(panel_x + panel_w - 80, panel_y + 15, 60, 30)
        pygame.draw.rect(surf, (100, 60, 60), close_rect, border_radius=5)
        close_text = font_small.render("Close", True, COLOR_WHITE)
        surf.blit(close_text, (close_rect.x + 15, close_rect.y + 7))
        return close_rect
    
    def handle_click(self, pos, inventory):
        panel_w, panel_h = 600, 500
        panel_x = (SCREEN_WIDTH - panel_w) // 2
        panel_y = (SCREEN_HEIGHT - panel_h) // 2
        close_rect = pygame.Rect(panel_x + panel_w - 80, panel_y + 15, 60, 30)
        if close_rect.collidepoint(pos):
            self.active = False
            return True
        items = ["wheat", "corn", "orange", "apple", "milk", "egg"]
        y_offset = panel_y + 90
        for i, item_key in enumerate(items):
            inv_item_rect = pygame.Rect(panel_x + 20, y_offset + i * 50, 250, 42)
            store_rect = pygame.Rect(inv_item_rect.x + 215, inv_item_rect.y + 6, 30, 30)
            if store_rect.collidepoint(pos):
                if inventory.items.get(item_key, 0) > 0:
                    inventory.remove(item_key, 1)
                    self.add_item(item_key, 1)
                    return True
        return False

# ==========================================
# GAME SYSTEMS
# ==========================================
class TileType(Enum):
    GRASS=0; SOIL=1; CROP=2; WATER=3; PATH=4

class Season(Enum):
    SPRING=0; SUMMER=1; AUTUMN=2; WINTER=3

class FruitTree:
    def __init__(self, tree_type, x, y):
        self.tree_type = tree_type
        self.x = x
        self.y = y
        self.has_fruits = True
        self.fruit_regrow_timer = 0
        self.fruit_regrow_time = 60

    def update(self, dt):
        if not self.has_fruits:
            self.fruit_regrow_timer += dt
            if self.fruit_regrow_timer >= self.fruit_regrow_time:
                self.has_fruits = True
                self.fruit_regrow_timer = 0

    def harvest(self, game_state, inventory):
        if self.has_fruits:
            self.has_fruits = False
            game_state.energy = max(0, game_state.energy - 10)
            if self.tree_type == "orange":
                inventory.add("orange", 1)
                game_state.add_exp(8)
                return "🍊 Harvested orange! Added to inventory! +8 XP, -10 energy"
            else:
                inventory.add("apple", 1)
                game_state.add_exp(6)
                return "🍎 Harvested apple! Added to inventory! +6 XP, -10 energy"
        return None

    def get_texture(self):
        if self.has_fruits:
            return TEX_ORANGE_TREE if self.tree_type == "orange" else TEX_APPLE_TREE
        else:
            return TEX_ORANGE_TREE_NO_FRUITS if self.tree_type == "orange" else TEX_APPLE_TREE_NO_FRUITS

class QuestionPopup:
    def __init__(self, question_data, on_complete):
        self.active = True
        self.question_data = question_data
        self.on_complete = on_complete
        self.selected_option = -1
        self.show_result = False
        self.result_text = ""
        self.result_success = False

    def draw(self, surf):
        if not self.active:
            return None
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill((0,0,0))
        overlay.set_alpha(200)
        surf.blit(overlay, (0,0))
        panel_w, panel_h = 650, 450
        panel_x = (SCREEN_WIDTH - panel_w)//2
        panel_y = (SCREEN_HEIGHT - panel_h)//2
        pygame.draw.rect(surf, (50,50,70), (panel_x, panel_y, panel_w, panel_h), border_radius=15)
        pygame.draw.rect(surf, COLOR_GOLD, (panel_x, panel_y, panel_w, panel_h), 3, border_radius=15)
        font_big = pygame.font.Font(None, 32)
        title = font_big.render(self.question_data["title"], True, COLOR_GOLD)
        surf.blit(title, (panel_x+panel_w//2-title.get_width()//2, panel_y+20))
        font_quest = pygame.font.Font(None, 24)
        wrapped_question = self.wrap_text(self.question_data["question"], font_quest, panel_w-60)
        for i, line in enumerate(wrapped_question):
            qs = font_quest.render(line, True, COLOR_WHITE)
            surf.blit(qs, (panel_x+30, panel_y+80+i*30))
        option_y = panel_y + 150
        font_option = pygame.font.Font(None, 22)
        for i, opt in enumerate(self.question_data["options"]):
            rect = pygame.Rect(panel_x+30, option_y+i*50, panel_w-60, 42)
            if self.show_result:
                if i == self.question_data["correct"]:
                    color = (60,120,60)
                elif i == self.selected_option and not self.result_success:
                    color = (120,60,60)
                else:
                    color = (70,70,90)
            else:
                color = (80,80,110) if self.selected_option != i else (100,150,100)
            pygame.draw.rect(surf, color, rect, border_radius=8)
            pygame.draw.rect(surf, COLOR_GOLD, rect, 2, border_radius=8)
            prefix = ""
            if self.show_result:
                if i == self.question_data["correct"]:
                    prefix = "✓ "
                elif i == self.selected_option and not self.result_success:
                    prefix = "✗ "
            opt_text = f"{prefix}{chr(65+i)}. {opt}"
            txt = font_option.render(opt_text, True, COLOR_WHITE)
            surf.blit(txt, (rect.x+15, rect.y+12))
        if self.show_result:
            font_result = pygame.font.Font(None, 20)
            lines = self.result_text.split('\n')
            for i, line in enumerate(lines):
                res_surf = font_result.render(line, True, COLOR_WHITE if "CORRECT" in line else (255,200,100))
                surf.blit(res_surf, (panel_x+30, panel_y+panel_h-100+i*25))
            cont_rect = pygame.Rect(panel_x+panel_w//2-70, panel_y+panel_h-60, 140,40)
            pygame.draw.rect(surf, (60,140,60), cont_rect, border_radius=8)
            pygame.draw.rect(surf, COLOR_GOLD, cont_rect, 2, border_radius=8)
            cont_text = font_option.render("Continue →", True, COLOR_WHITE)
            surf.blit(cont_text, (cont_rect.x+15, cont_rect.y+10))
            return cont_rect
        return None

    def wrap_text(self, text, font, max_width):
        words = text.split()
        lines = []
        cur = []
        for w in words:
            cur.append(w)
            if font.size(' '.join(cur))[0] > max_width:
                cur.pop()
                lines.append(' '.join(cur))
                cur = [w]
        if cur:
            lines.append(' '.join(cur))
        return lines or [text]

    def handle_click(self, pos, game_state, inventory):
        if not self.active:
            return False
        panel_w, panel_h = 650, 450
        panel_x = (SCREEN_WIDTH - panel_w)//2
        panel_y = (SCREEN_HEIGHT - panel_h)//2
        if not self.show_result:
            option_y = panel_y + 150
            for i in range(len(self.question_data["options"])):
                rect = pygame.Rect(panel_x+30, option_y+i*50, panel_w-60, 42)
                if rect.collidepoint(pos):
                    self.selected_option = i
                    if i == self.question_data["correct"]:
                        self.result_success = True
                        game_state.money += self.question_data["reward_money"]
                        game_state.add_exp(self.question_data["reward_exp"])
                        self.result_text = f"✓ CORRECT! You earned ${self.question_data['reward_money']} and {self.question_data['reward_exp']} XP!"
                    else:
                        self.result_success = False
                        correct = self.question_data["options"][self.question_data["correct"]]
                        self.result_text = f"✗ WRONG! The correct answer is: {correct}\nBetter luck tomorrow, farmer!"
                    self.show_result = True
                    return True
        elif self.show_result:
            cont_rect = pygame.Rect(panel_x+panel_w//2-70, panel_y+panel_h-60, 140,40)
            if cont_rect.collidepoint(pos):
                if self.on_complete:
                    self.on_complete(self.result_success)
                self.active = False
                return True
        return False

class DailyQuiz:
    def __init__(self):
        self.active = False
        self.quiz_taken_today = False
        self.current_question = None
        self.selected_option = -1
        self.show_result = False
        self.result_text = ""
        self.result_success = False
        self.last_day = -1
        self.questions = [
            {"text": "What part of the plant absorbs water and nutrients from the soil?",
             "options": ["Leaves","Stems","Roots","Flowers"], "correct":2,
             "reward_money":25, "reward_exp":10},
            {"text": "What is the process called when a seed starts to grow into a new plant?",
             "options": ["Photosynthesis","Germination","Fertilization","Pollination"], "correct":1,
             "reward_money":25, "reward_exp":10},
            {"text": "Which gas do plants absorb from the air to make their food?",
             "options": ["Oxygen","Nitrogen","Carbon Dioxide","Hydrogen"], "correct":2,
             "reward_money":25, "reward_exp":10},
            {"text": "What do plants need from sunlight?",
             "options": ["Warmth only","Energy for photosynthesis","Color for leaves","Water evaporation"], "correct":1,
             "reward_money":25, "reward_exp":10},
            {"text": "What part of the wheat plant do farmers harvest for food?",
             "options": ["Roots","Leaves","Stems","Seeds/Grains"], "correct":3,
             "reward_money":30, "reward_exp":15}
        ]

    def try_start_quiz(self, current_day):
        if not self.active and not self.quiz_taken_today and current_day != self.last_day:
            self.last_day = current_day
            self.quiz_taken_today = False
            self.active = True
            self.current_question = random.choice(self.questions)
            self.selected_option = -1
            self.show_result = False
            self.result_text = ""
            return True
        return False

    def check_answer(self, option_index, game_state):
        if option_index == self.current_question["correct"]:
            self.result_success = True
            game_state.money += self.current_question["reward_money"]
            game_state.add_exp(self.current_question["reward_exp"])
            self.result_text = f"✓ CORRECT! You earned ${self.current_question['reward_money']} and {self.current_question['reward_exp']} XP!"
            return True
        else:
            self.result_success = False
            correct = self.current_question["options"][self.current_question["correct"]]
            self.result_text = f"✗ WRONG! The correct answer is: {correct}\nBetter luck tomorrow, farmer!"
            return False

    def draw(self, surf):
        if not self.active:
            return None
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill((0,0,0))
        overlay.set_alpha(200)
        surf.blit(overlay, (0,0))
        panel_w, panel_h = 650, 450
        panel_x = (SCREEN_WIDTH - panel_w)//2
        panel_y = (SCREEN_HEIGHT - panel_h)//2
        pygame.draw.rect(surf, (50,50,70), (panel_x, panel_y, panel_w, panel_h), border_radius=15)
        pygame.draw.rect(surf, COLOR_GOLD, (panel_x, panel_y, panel_w, panel_h), 3, border_radius=15)
        font_big = pygame.font.Font(None, 36)
        title = font_big.render("📚 Daily Farmer Quiz! 📚", True, COLOR_GOLD)
        surf.blit(title, (panel_x+panel_w//2-title.get_width()//2, panel_y+20))
        font_quest = pygame.font.Font(None, 24)
        wrapped = self.wrap_text(self.current_question["text"], font_quest, panel_w-60)
        for i, line in enumerate(wrapped):
            qs = font_quest.render(line, True, COLOR_WHITE)
            surf.blit(qs, (panel_x+30, panel_y+80+i*30))
        option_y = panel_y + 150
        font_opt = pygame.font.Font(None, 22)
        for i, opt in enumerate(self.current_question["options"]):
            rect = pygame.Rect(panel_x+30, option_y+i*50, panel_w-60, 42)
            if self.show_result:
                if i == self.current_question["correct"]:
                    color = (60,120,60)
                elif i == self.selected_option and not self.result_success:
                    color = (120,60,60)
                else:
                    color = (70,70,90)
            else:
                color = (80,80,110) if self.selected_option != i else (100,150,100)
            pygame.draw.rect(surf, color, rect, border_radius=8)
            pygame.draw.rect(surf, COLOR_GOLD, rect, 2, border_radius=8)
            prefix = ""
            if self.show_result:
                if i == self.current_question["correct"]:
                    prefix = "✓ "
                elif i == self.selected_option and not self.result_success:
                    prefix = "✗ "
            txt = font_opt.render(f"{prefix}{chr(65+i)}. {opt}", True, COLOR_WHITE)
            surf.blit(txt, (rect.x+15, rect.y+12))
        if self.show_result:
            font_res = pygame.font.Font(None, 20)
            lines = self.result_text.split('\n')
            for i, line in enumerate(lines):
                res_surf = font_res.render(line, True, COLOR_WHITE if "CORRECT" in line else (255,200,100))
                surf.blit(res_surf, (panel_x+30, panel_y+panel_h-100+i*25))
            cont_rect = pygame.Rect(panel_x+panel_w//2-70, panel_y+panel_h-60, 140,40)
            pygame.draw.rect(surf, (60,140,60), cont_rect, border_radius=8)
            pygame.draw.rect(surf, COLOR_GOLD, cont_rect, 2, border_radius=8)
            cont_text = font_opt.render("Continue Farming →", True, COLOR_WHITE)
            surf.blit(cont_text, (cont_rect.x+15, cont_rect.y+10))
            return cont_rect
        return None

    def wrap_text(self, text, font, max_width):
        words = text.split()
        lines = []
        cur = []
        for w in words:
            cur.append(w)
            if font.size(' '.join(cur))[0] > max_width:
                cur.pop()
                lines.append(' '.join(cur))
                cur = [w]
        if cur:
            lines.append(' '.join(cur))
        return lines or [text]

    def handle_click(self, pos, game_state):
        if not self.active:
            return False
        panel_w, panel_h = 650, 450
        panel_x = (SCREEN_WIDTH - panel_w)//2
        panel_y = (SCREEN_HEIGHT - panel_h)//2
        if not self.show_result:
            option_y = panel_y + 150
            for i in range(len(self.current_question["options"])):
                rect = pygame.Rect(panel_x+30, option_y+i*50, panel_w-60, 42)
                if rect.collidepoint(pos):
                    self.selected_option = i
                    self.check_answer(i, game_state)
                    self.show_result = True
                    return True
        elif self.show_result:
            cont_rect = pygame.Rect(panel_x+panel_w//2-70, panel_y+panel_h-60, 140,40)
            if cont_rect.collidepoint(pos):
                self.active = False
                self.quiz_taken_today = True
                return True
        return False

    def reset_new_day(self):
        self.active = False
        self.quiz_taken_today = False
        self.selected_option = -1
        self.show_result = False

class GameState:
    def __init__(self):
        self.day_time = 8.0
        self.day = 1
        self.weather = "sunny"
        self.weather_timer = random.randint(30,90)
        self.money = 500
        self.exp = 0
        self.level = 1
        self.exp_needed = 100
        self.energy = 100
        self.max_energy = 100
        self.health = 100
        self.max_health = 100
        self.season = Season.SPRING
        self.season_timer = 0
        self.achievements = []
        self.tutorial_shown = False
        self.inventory = None
        self.zoom = 1.0
        self.day_changed = False
        self.last_day = 1
        self.energy_used_today = 0
        self.quiz_reminder_shown = False  # Fixed: Initialize here

    def update(self, dt):
        old_day = int(self.day_time)
        self.day_time += dt/DAY_LENGTH*24
        new_day = int(self.day_time)
        if new_day > old_day and new_day <= 24:
            self.day_changed = True
            self.last_day = self.day
        else:
            self.day_changed = False
        if self.day_time >= 24:
            self.day_time -= 24
            self.day += 1
            self.energy_used_today = 0
            self.season_timer += 1
            if self.season_timer >= 28:
                self.season_timer = 0
                seasons = list(Season)
                self.season = seasons[(self.season.value+1)%len(seasons)]
                self.update_grass_texture()
            self.weather = random.choice(WEATHER_TYPES)
        self.weather_timer -= dt
        if self.weather_timer <= 0:
            self.weather = random.choice(WEATHER_TYPES)
            self.weather_timer = random.randint(30,90)
        if self.health < self.max_health:
            self.health = min(self.max_health, self.health + dt*2)

    def update_grass_texture(self):
        global TEX_GRASS
        TEX_GRASS = ArtEngine.create_grass_seasonal(self.season.name.lower())

    def get_time_str(self):
        h = int(self.day_time)
        m = int((self.day_time%1)*60)
        return f"{h:02d}:{m:02d}"

    def get_light_factor(self):
        if 6 <= self.day_time < 18:
            return 1.0 - abs(self.day_time-12)/12*0.4
        return 0.2

    def add_exp(self, amt):
        self.exp += amt
        while self.exp >= self.exp_needed:
            self.level += 1
            self.exp -= self.exp_needed
            self.exp_needed = int(self.exp_needed * 1.2)
            self.max_energy += 10
            self.max_health += 10
            self.energy = self.max_energy
            self.health = self.max_health
            self.achievements.append(f"🎉 Reached level {self.level}!")

    def zoom_in(self):
        self.zoom = min(MAX_ZOOM, self.zoom + ZOOM_SPEED)

    def zoom_out(self):
        self.zoom = max(MIN_ZOOM, self.zoom - ZOOM_SPEED)

class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit(self, x, y, color, count=5, lifetime=0.5):
        for _ in range(count):
            self.particles.append({
                'x': x, 'y': y,
                'vx': random.uniform(-30,30), 'vy': random.uniform(-30,0),
                'life': lifetime, 'color': color, 'size': random.randint(2,4)
            })

    def update(self, dt):
        for p in self.particles[:]:
            p['x'] += p['vx']*dt
            p['y'] += p['vy']*dt
            p['life'] -= dt
            if p['life'] <= 0:
                self.particles.remove(p)

    def draw(self, surf, cam_x, cam_y, zoom):
        for p in self.particles:
            alpha = int(255 * p['life'] / 0.5)
            try:
                col = (*p['color'], alpha)
                x = (p['x'] - cam_x) * zoom
                y = (p['y'] - cam_y) * zoom
                sz = max(1, int(p['size'] * zoom))
                pygame.draw.circle(surf, col[:3], (int(x), int(y)), sz)
            except:
                pass

class World:
    def __init__(self, w, h):
        self.width = w
        self.height = h
        self.tiles = [[TileType.GRASS]*w for _ in range(h)]
        self.crops = {}
        self.collision = [[False]*w for _ in range(h)]
        self.decor = []
        self.fence_tiles = set()
        self.pasture_rect = None
        self.coop_rect = None
        self.fruit_trees = []
        self.vending_machines = []
        self.animal_products = {"cow_milk_timer":0, "chicken_egg_timer":0}
        self.particle_system = ParticleSystem()
        self.game_state = None
        self._generate_terrain()
        self._place_structures()
        self._setup_fenced_pasture()
        self._setup_chicken_area()
        self._add_fruit_trees()
        self._add_scarecrow()
        self._add_vending_machine()
        self._add_truck()

    def _generate_terrain(self):
        for y in range(10, 18):
            for x in range(3, 12):
                self.tiles[y][x] = TileType.SOIL

    def _place_structures(self):
        for y in range(2, 6):
            for x in range(15, 20):
                self.collision[y][x] = True
        for y in range(1, 4):
            for x in range(30, 34):
                self.collision[y][x] = True

    def _setup_fenced_pasture(self):
        px1, py1, px2, py2 = 28, 20, 38, 28
        self.pasture_rect = (px1, py1, px2, py2)
        for x in range(px1, px2+1):
            for y in range(py1, py2+1):
                if x == px1 or x == px2 or y == py1 or y == py2:
                    self.fence_tiles.add((x, y))
                    self.collision[y][x] = True
                else:
                    self.collision[y][x] = False

    def _setup_chicken_area(self):
        coop_x, coop_y = 22, 22
        run_x1, run_y1 = coop_x - 2, coop_y + 1
        run_x2, run_y2 = coop_x + 4, coop_y + 5
        self.coop_rect = (run_x1, run_y1, run_x2, run_y2)
        for x in range(run_x1, run_x2+1):
            for y in range(run_y1, run_y2+1):
                if x == run_x1 or x == run_x2 or y == run_y1 or y == run_y2:
                    self.fence_tiles.add((x, y))
                    self.collision[y][x] = True

    def _add_fruit_trees(self):
        tree_positions = [
            (5,3,"orange"), (32,5,"apple"), (3,30,"apple"),
            (36,28,"orange"), (12,34,"orange"), (25,2,"apple")
        ]
        for x, y, t in tree_positions:
            if 0 <= x < self.width and 0 <= y < self.height and self.tiles[y][x] == TileType.GRASS:
                tree = FruitTree(t, x, y)
                self.fruit_trees.append(tree)
                # Only block the tree's own tile, so the player can stand adjacent to harvest
                self.collision[y][x] = True

    def _add_scarecrow(self):
        scarecrow_x = 7
        scarecrow_y = 13
        self.decor.append(("scarecrow", scarecrow_x, scarecrow_y))

    def _add_vending_machine(self):
        vending_x, vending_y = 21, 4
        for dy in range(0, 2):
            for dx in range(0, 1):
                nx, ny = vending_x + dx, vending_y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    self.tiles[ny][nx] = TileType.PATH
        vending = VendingMachine(vending_x, vending_y)
        self.vending_machines.append(vending)
        # Only block the machine's own tile so the player can stand next to it
        if 0 <= vending_x < self.width and 0 <= vending_y < self.height:
            self.collision[vending_y][vending_x] = True
    def _add_truck(self):
        """Add the vegetable truck to the map, parked beside the house."""
        self.decor.append(("truck", 35, 3))

    def is_collision(self, x, y):
        if x<0 or y<0 or x>=self.width or y>=self.height:
            return True
        return self.collision[y][x]

    def is_inside_pasture(self, x, y):
        if not self.pasture_rect:
            return False
        px1, py1, px2, py2 = self.pasture_rect
        return px1 <= x <= px2 and py1 <= y <= py2

    def is_inside_chicken_area(self, x, y):
        if not self.coop_rect:
            return False
        cx1, cy1, cx2, cy2 = self.coop_rect
        return cx1 <= x <= cx2 and cy1 <= y <= cy2

    def plant_crop(self, x, y, seed_type, game_state):
        if self.tiles[y][x] == TileType.SOIL and (x,y) not in self.crops:
            if game_state.energy >= 8:
                self.crops[(x,y)] = {"type": seed_type.replace("_seed",""), "growth":0.0}
                self.tiles[y][x] = TileType.CROP
                game_state.energy = max(0, game_state.energy - 8)
                game_state.energy_used_today += 8
                return True
        return False

    def harvest_crop(self, x, y, inventory, game_state):
        if (x,y) in self.crops and self.crops[(x,y)]["growth"] >= 1.0:
            if game_state.energy >= 5:
                crop = self.crops[(x,y)]
                crop_type = crop["type"]
                self.tiles[y][x] = TileType.SOIL
                del self.crops[(x,y)]
                inventory.add(crop_type, 2)
                game_state.energy = max(0, game_state.energy - 5)
                game_state.energy_used_today += 5
                return crop_type
        return None

    def harvest_fruit_tree(self, x, y, game_state, inventory):
        for tree in self.fruit_trees:
            if tree.x == x and tree.y == y:
                return tree.harvest(game_state, inventory)
        return None

    def update_fruit_trees(self, dt):
        for tree in self.fruit_trees:
            tree.update(dt)

    def update_crops(self, dt, weather_factor, season_factor):
        for pos, data in self.crops.items():
            growth = CROP_GROWTH_BASE * dt * weather_factor * season_factor
            if self.game_state and not (6 <= self.game_state.day_time < 20):
                growth *= 0.3
            data["growth"] = min(1.0, data["growth"] + growth)

    def update_animal_products(self, dt, inventory):
        self.animal_products["cow_milk_timer"] += dt
        if self.animal_products["cow_milk_timer"] >= 30:
            self.animal_products["cow_milk_timer"] = 0
            inventory.add("milk", 1)
        self.animal_products["chicken_egg_timer"] += dt
        if self.animal_products["chicken_egg_timer"] >= 20:
            self.animal_products["chicken_egg_timer"] = 0
            inventory.add("egg", 1)

    def draw(self, surf, cam_x, cam_y, game_state, zoom):
        scaled_tile_size = int(TILE_SIZE * zoom)
        bg_color = (70,130,70)
        surf.fill(bg_color)

        for y in range(self.height):
            for x in range(self.width):
                sx = (x*TILE_SIZE - cam_x) * zoom
                sy = (y*TILE_SIZE - cam_y) * zoom
                if -scaled_tile_size <= sx < SCREEN_WIDTH+scaled_tile_size and -scaled_tile_size <= sy < SCREEN_HEIGHT+scaled_tile_size:
                    tile = self.tiles[y][x]
                    if tile == TileType.GRASS:
                        scaled = pygame.transform.scale(TEX_GRASS, (scaled_tile_size, scaled_tile_size))
                        surf.blit(scaled, (sx,sy))
                    elif tile == TileType.SOIL:
                        scaled = pygame.transform.scale(TEX_SOIL, (scaled_tile_size, scaled_tile_size))
                        surf.blit(scaled, (sx,sy))
                    elif tile == TileType.CROP:
                        scaled = pygame.transform.scale(TEX_SOIL, (scaled_tile_size, scaled_tile_size))
                        surf.blit(scaled, (sx,sy))
                        if (x,y) in self.crops:
                            crop = self.crops[(x,y)]
                            g = crop["growth"]
                            if crop["type"] == "wheat":
                                if g < 0.3:
                                    plant_tex = WHEAT_PLANTS["seedling"]
                                elif g < 0.7:
                                    plant_tex = WHEAT_PLANTS["growing"]
                                else:
                                    plant_tex = WHEAT_PLANTS["mature"]
                            else:
                                if g < 0.3:
                                    plant_tex = CORN_PLANTS["seedling"]
                                elif g < 0.7:
                                    plant_tex = CORN_PLANTS["growing"]
                                else:
                                    plant_tex = CORN_PLANTS["mature"]
                            scaled_plant = pygame.transform.scale(plant_tex, (scaled_tile_size, scaled_tile_size))
                            surf.blit(scaled_plant, (sx, sy))

        for fx,fy in self.fence_tiles:
            sx = (fx*TILE_SIZE - cam_x)*zoom
            sy = (fy*TILE_SIZE - cam_y)*zoom
            has_left = (fx-1, fy) in self.fence_tiles
            has_right = (fx+1, fy) in self.fence_tiles
            has_up = (fx, fy-1) in self.fence_tiles
            has_down = (fx, fy+1) in self.fence_tiles

            # Rail toward the right neighbor
            if has_right:
                scaled_rail = pygame.transform.scale(TEX_FENCE_RAIL_H, (scaled_tile_size, scaled_tile_size))
                surf.blit(scaled_rail, (sx + scaled_tile_size//2, sy))
            # Rail toward the down neighbor
            if has_down:
                scaled_rail = pygame.transform.scale(TEX_FENCE_RAIL_V, (scaled_tile_size, scaled_tile_size))
                surf.blit(scaled_rail, (sx, sy + scaled_tile_size//2))

            # Always draw the post on top
            scaled_post = pygame.transform.scale(TEX_FENCE_POST_ONLY, (scaled_tile_size, scaled_tile_size))
            surf.blit(scaled_post, (sx, sy))

        for tree in self.fruit_trees:
            sx = (tree.x * TILE_SIZE - cam_x)*zoom
            sy = (tree.y * TILE_SIZE - cam_y)*zoom
            scaled = pygame.transform.scale(tree.get_texture(), (int(96*zoom), int(130*zoom)))
            surf.blit(scaled, (sx-24*zoom, sy-45*zoom))

        for typ, x, y in self.decor:
            sx = (x*TILE_SIZE - cam_x)*zoom
            sy = (y*TILE_SIZE - cam_y)*zoom
            if typ == "coop":
                scaled = pygame.transform.scale(TEX_CHICKEN_COOP, (int(TILE_SIZE*3*zoom), int(TILE_SIZE*2*zoom)))
                surf.blit(scaled, (sx,sy))
            elif typ == "scarecrow":
                scaled = pygame.transform.scale(TEX_SCARECROW, (scaled_tile_size, scaled_tile_size))
                surf.blit(scaled, (sx, sy-8*zoom))
            elif typ == "truck":
                scaled = pygame.transform.scale(TEX_TRUCK, (int(TILE_SIZE*4*zoom), int(TILE_SIZE*2.2*zoom)))
                surf.blit(scaled, (sx-18*zoom, sy-20*zoom))

        for vending in self.vending_machines:
            sx = (vending.x * TILE_SIZE - cam_x) * zoom
            sy = (vending.y * TILE_SIZE - cam_y) * zoom
            scaled = pygame.transform.scale(TEX_VENDING_MACHINE, (scaled_tile_size, scaled_tile_size * 2))
            surf.blit(scaled, (sx, sy - scaled_tile_size))

        scaled_barn = pygame.transform.scale(TEX_BARN, (int(TILE_SIZE*5*zoom), int(TILE_SIZE*4*zoom)))
        scaled_house = pygame.transform.scale(TEX_HOUSE, (int(TILE_SIZE*4*zoom), int(TILE_SIZE*3*zoom)))
        surf.blit(scaled_barn, ((15*TILE_SIZE - cam_x)*zoom, (2*TILE_SIZE - cam_y)*zoom))
        surf.blit(scaled_house, ((30*TILE_SIZE - cam_x)*zoom, (1*TILE_SIZE - cam_y)*zoom))

class Player:
    def __init__(self, x, y):
        self.x = x * TILE_SIZE
        self.y = y * TILE_SIZE
        self.tx = x
        self.ty = y
        self.base_speed = 300
        self.run_speed = 500
        self.moving = False
        self.running = False
        self.move_start_x = 0
        self.move_start_y = 0
        self.move_target_x = 0
        self.move_target_y = 0
        self.move_progress = 0
        self.move_duration = 0.16
        self.run_duration = 0.10
        self.current_duration = 0.16
        self.move_timer = 0
        self.anim_frame = 0
        self.dust_timer = 0

    def start_move(self, dx, dy, world, is_running=False):
        if not self.moving:
            nx = self.tx + dx
            ny = self.ty + dy
            if 0 <= nx < world.width and 0 <= ny < world.height and not world.is_collision(nx, ny):
                self.move_start_x = self.x
                self.move_start_y = self.y
                self.move_target_x = nx * TILE_SIZE
                self.move_target_y = ny * TILE_SIZE
                self.tx = nx
                self.ty = ny
                self.moving = True
                self.move_progress = 0
                self.move_timer = 0
                self.running = is_running
                self.current_duration = self.run_duration if is_running else self.move_duration
                return True
        return False

    def update(self, dt, world):
        if self.moving:
            self.move_timer += dt
            self.move_progress = min(1.0, self.move_timer / self.current_duration)
            t = self.move_progress
            t = t*t*(3-2*t)
            self.x = self.move_start_x + (self.move_target_x - self.move_start_x)*t
            self.y = self.move_start_y + (self.move_target_y - self.move_start_y)*t
            self.anim_frame += dt * (16 if self.running else 12)
            self.dust_timer += dt
            if self.dust_timer > (0.08 if self.running else 0.1):
                self.dust_timer = 0
                cnt = 4 if self.running else 2
                world.particle_system.emit(self.x+12, self.y+24, (180,180,160), cnt, 0.2)
            if self.move_progress >= 1.0:
                self.x = self.move_target_x
                self.y = self.move_target_y
                self.moving = False
                self.running = False
        else:
            self.anim_frame = 0

    def draw(self, surf, cam_x, cam_y, zoom):
        sx = (self.x - cam_x) * zoom
        sy = (self.y - cam_y) * zoom
        walk = math.sin(self.anim_frame*0.35)*3 if self.moving else 0
        leg = math.cos(self.anim_frame*0.35)*4.5 if self.moving else 0
        arm = math.sin(self.anim_frame*0.35)*5.5 if self.moving else 0
        pygame.draw.ellipse(surf, (30,60,15,140), (sx+12*zoom, sy+13*zoom, 24*zoom, 6*zoom))
        pygame.draw.rect(surf, (35,80,150), (sx+8*zoom, sy+8*zoom+int(leg), 3*zoom, 7*zoom), border_radius=1)
        pygame.draw.rect(surf, (35,80,150), (sx+13*zoom, sy+8*zoom-int(leg), 3*zoom, 7*zoom), border_radius=1)
        pygame.draw.rect(surf, (60,45,35), (sx+7*zoom, sy+14*zoom+int(leg), 4*zoom, 3*zoom), border_radius=1)
        pygame.draw.rect(surf, (60,45,35), (sx+12*zoom, sy+14*zoom-int(leg), 4*zoom, 3*zoom), border_radius=1)
        pygame.draw.line(surf, (180,40,40), (sx+7*zoom, sy+int(walk)), (sx+4*zoom, sy+6*zoom+int(walk)+int(arm)), max(1,int(3*zoom)))
        pygame.draw.circle(surf, (245,205,170), (sx+4*zoom, sy+6*zoom+int(walk)+int(arm)), max(1,int(2*zoom)))
        pygame.draw.line(surf, (180,40,40), (sx+17*zoom, sy+int(walk)), (sx+20*zoom, sy+6*zoom+int(walk)-int(arm)), max(1,int(3*zoom)))
        pygame.draw.circle(surf, (245,205,170), (sx+20*zoom, sy+6*zoom+int(walk)-int(arm)), max(1,int(2*zoom)))
        pygame.draw.rect(surf, (40,100,180), (sx+7*zoom, sy-3*zoom+int(walk), 10*zoom, 12*zoom), border_radius=max(1,int(3*zoom)))
        pygame.draw.rect(surf, (180,40,40), (sx+7*zoom, sy-5*zoom+int(walk), 10*zoom, 3*zoom), border_radius=1)
        pygame.draw.circle(surf, (245,205,170), (sx+12*zoom, sy-10*zoom+int(walk)), max(1,int(6*zoom)))
        pygame.draw.ellipse(surf, (235,200,110), (sx-3*zoom, sy-16*zoom+int(walk), 30*zoom, 5*zoom))
        pygame.draw.rect(surf, (215,180,90), (sx+6*zoom, sy-22*zoom+int(walk), 12*zoom, 7*zoom), border_radius=max(1,int(2*zoom)))

class Animal:
    def __init__(self, species, x, y, world):
        self.species = species
        self.x = x
        self.y = y
        self.vx = random.uniform(-5,5)
        self.vy = random.uniform(-5,5)
        self.world = world
        self.anim_frame = random.uniform(0,10)

        # keeps the animal's sprite from overlapping the fence visually
        inset = 30 if species == "cow" else 15  # keeps the animal's sprite from overlapping the fence visually
        if species == "cow" and world.pasture_rect:
            px1, py1, px2, py2 = world.pasture_rect
            self.boundary_min_x = (px1 + 1) * TILE_SIZE + inset
            self.boundary_max_x = px2 * TILE_SIZE - inset
            self.boundary_min_y = (py1 + 1) * TILE_SIZE + inset
            self.boundary_max_y = py2 * TILE_SIZE - inset
        elif species == "chicken" and world.coop_rect:
            cx1, cy1, cx2, cy2 = world.coop_rect
            self.boundary_min_x = (cx1 + 1) * TILE_SIZE + inset
            self.boundary_max_x = cx2 * TILE_SIZE - inset
            self.boundary_min_y = (cy1 + 1) * TILE_SIZE + inset
            self.boundary_max_y = cy2 * TILE_SIZE - inset
        else:
            # Fallback in case a rect isn't set up yet
            self.boundary_min_x = x - 50
            self.boundary_max_x = x + 50
            self.boundary_min_y = y - 50
            self.boundary_max_y = y + 50

    def update(self, dt):
        if random.random() < 0.01:
            self.vx += random.uniform(-8, 8)
            self.vy += random.uniform(-8, 8)
            speed = math.sqrt(self.vx**2 + self.vy**2)
            if speed > 25:
                self.vx = (self.vx / speed) * 25
                self.vy = (self.vy / speed) * 25
        new_x = self.x + self.vx * dt
        new_y = self.y + self.vy * dt
        if new_x < self.boundary_min_x:
            new_x = self.boundary_min_x
            self.vx = abs(self.vx) * 0.5
        elif new_x > self.boundary_max_x:
            new_x = self.boundary_max_x
            self.vx = -abs(self.vx) * 0.5
        if new_y < self.boundary_min_y:
            new_y = self.boundary_min_y
            self.vy = abs(self.vy) * 0.5
        elif new_y > self.boundary_max_y:
            new_y = self.boundary_max_y
            self.vy = -abs(self.vy) * 0.5
        self.x = new_x
        self.y = new_y
        self.anim_frame += dt * 5

    def draw(self, surf, cam_x, cam_y, zoom):
        sx = (self.x - cam_x)*zoom
        sy = (self.y - cam_y)*zoom
        if self.species == "cow":
            bob = abs(math.sin(self.anim_frame*0.12))*3*zoom
            leg = math.sin(self.anim_frame*0.22)*5*zoom
            pygame.draw.ellipse(surf, (30,55,20,100), (sx-24*zoom, sy+14*zoom, 48*zoom, 10*zoom))
            pygame.draw.rect(surf, (45,40,40), (sx-15*zoom, sy+6*zoom+int(leg), max(1,int(6*zoom)), max(1,int(12*zoom))), border_radius=1)
            pygame.draw.rect(surf, (45,40,40), (sx+8*zoom, sy+6*zoom-int(leg), max(1,int(6*zoom)), max(1,int(12*zoom))), border_radius=1)
            pygame.draw.rect(surf, (235,230,225), (sx-9*zoom, sy+8*zoom-int(leg), max(1,int(6*zoom)), max(1,int(12*zoom))), border_radius=1)
            pygame.draw.rect(surf, (235,230,225), (sx+2*zoom, sy+8*zoom+int(leg), max(1,int(6*zoom)), max(1,int(12*zoom))), border_radius=1)
            pygame.draw.ellipse(surf, (245,242,238), (sx-22*zoom, sy-14*zoom-int(bob), 44*zoom, 26*zoom))
            pygame.draw.ellipse(surf, (242,180,192), (sx-4*zoom, sy+7*zoom-int(bob), 12*zoom, 6*zoom))
            pygame.draw.circle(surf, (35,32,33), (sx-12*zoom, sy-4*zoom-int(bob)), max(1,int(9*zoom)))
            pygame.draw.circle(surf, (35,32,33), (sx+6*zoom, sy-6*zoom-int(bob)), max(1,int(8*zoom)))
            pygame.draw.ellipse(surf, (35,32,33), (sx-3*zoom, sy-12*zoom-int(bob), 14*zoom, 8*zoom))
            pygame.draw.circle(surf, (35,32,33), (sx+14*zoom, sy+2*zoom-int(bob)), max(1,int(6*zoom)))
            hx = sx+16*zoom
            pygame.draw.rect(surf, (245,242,238), (hx, sy-22*zoom-int(bob), 16*zoom, 18*zoom), border_radius=max(1,int(4*zoom)))
            pygame.draw.circle(surf, (35,32,33), (hx+4*zoom, sy-18*zoom-int(bob)), max(1,int(5*zoom)))
            pygame.draw.circle(surf, (10,10,15), (hx+11*zoom, sy-15*zoom-int(bob)), max(1,int(2*zoom)))
            pygame.draw.ellipse(surf, (242,175,188), (hx+10*zoom, sy-11*zoom-int(bob), 12*zoom, 8*zoom))
            pygame.draw.circle(surf, (235,230,225), (hx+2*zoom, sy-24*zoom-int(bob)), max(1,int(3*zoom)))
        else:
            pygame.draw.ellipse(surf, (30,55,20,90), (sx-8*zoom, sy+10*zoom, 16*zoom, 5*zoom))
            pygame.draw.line(surf, (245,170,15), (sx-3*zoom, sy+4*zoom), (sx-4*zoom, sy+11*zoom), max(1,int(2*zoom)))
            pygame.draw.line(surf, (245,170,15), (sx+3*zoom, sy+4*zoom), (sx+4*zoom, sy+11*zoom), max(1,int(2*zoom)))
            pygame.draw.circle(surf, (245,245,245), (sx, sy), max(1,int(11*zoom)))
            pygame.draw.ellipse(surf, (225,225,225), (sx-7*zoom, sy-3*zoom, 8*zoom, 7*zoom))
            pygame.draw.circle(surf, (250,250,250), (sx+8*zoom, sy-9*zoom), max(1,int(6.5*zoom)))
            pygame.draw.circle(surf, (225,30,30), (sx+8*zoom, sy-16*zoom), max(1,int(3*zoom)))
            pygame.draw.circle(surf, (225,30,30), (sx+9*zoom, sy-4*zoom), max(1,int(2.5*zoom)))
            pygame.draw.circle(surf, (15,15,15), (sx+10*zoom, sy-10*zoom), max(1,int(1.5*zoom)))
            pygame.draw.polygon(surf, (250,160,10), [(sx+12*zoom, sy-9*zoom), (sx+18*zoom, sy-7*zoom), (sx+12*zoom, sy-5*zoom)])

# ==========================================
# TUTORIAL CLASS
# ==========================================
class Tutorial:
    def __init__(self):
        self.steps = [
            {"title":"Welcome to AgriQuest!","text":"This tutorial will teach you the basics of farming.\nPress SPACE to continue.","controls":[]},
            {"title":"Movement","text":"Use WASD or Arrow Keys to move your farmer.\nHold SHIFT to run!","controls":["WASD / Arrows","Hold SHIFT: Run"]},
            {"title":"Energy System","text":"Every action costs energy!\n- Planting: 8 energy\n- Harvesting: 5 energy\n- Fruit trees: 10 energy\n- Selling: 1 energy per item\nUse the Vending Machine (V) to restore energy!","controls":["Buy energy drinks from vending machine"]},
            {"title":"Zoom Controls","text":"Press Q to zoom in, E to zoom out.","controls":["Q: Zoom In","E: Zoom Out"]},
            {"title":"Inventory & Barn Storage","text":"Harvested crops go to your INVENTORY.\nPress B near the barn to open storage!\nClick the → button to move items from inventory to barn.","controls":["B: Open Barn Storage","→: Transfer to barn"]},
            {"title":"Truck & City Market","text":"Stand near the truck (near the house area) and press M to travel to the city market!\nSell your goods from inventory for high prices!","controls":["M: Open City Market"]},
            {"title":"Vending Machine","text":"There's a tall vending machine beside the barn! Press V to buy energy drinks!\nStand next to it and press V to open the menu.","controls":["V: Open Vending Machine"]},
            {"title":"Harvest Fruit Trees","text":"Stand next to orange or apple trees and press F to harvest fruits!\nFruits go to your inventory. Costs 10 energy.","controls":["F: Harvest fruits from trees"]},
            {"title":"Educational Questions","text":"You'll get plant biology questions when planting and harvesting crops!\nAnswer correctly for bonus rewards.","controls":["Learn while you farm!"]},
            {"title":"Daily Quiz","text":"Every morning, you'll get a special daily quiz!\nAnswer correctly for bonus money and XP.","controls":["Click on answers"]},
            {"title":"Planting Crops","text":"Stand on brown soil tiles. Press 1 or 2 to select seeds,\nthen press P to plant. Costs 8 energy. Answer the question to plant!","controls":["1,2: Select seed","P: Plant with quiz"]},
            {"title":"Harvesting Crops","text":"When crops are fully grown, press H to harvest.\nCrops go to your inventory! Costs 5 energy.","controls":["H: Harvest crops with quiz"]},
            {"title":"Animals","text":"Cows and chickens live in fenced areas. They produce\nmilk and eggs automatically, stored in your inventory.","controls":[]},
            {"title":"Save & Load","text":"Press F5 to save your game. Press F9 to load.","controls":["F5: Save","F9: Load"]},
            {"title":"Tutorial End","text":"You're ready to farm! Press T anytime to replay this tutorial.\nGood luck!","controls":["T: Replay Tutorial"]}
        ]
        self.active = False
        self.current_step = 0
        self.font_large = pygame.font.Font(None,36)
        self.font_medium = pygame.font.Font(None,28)
        self.font_small = pygame.font.Font(None,20)

    def start(self):
        self.active = True
        self.current_step = 0

    def next_step(self):
        if self.current_step < len(self.steps)-1:
            self.current_step += 1
        else:
            self.active = False

    def draw(self, surf):
        if not self.active:
            return
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill((0,0,0))
        overlay.set_alpha(200)
        surf.blit(overlay, (0,0))
        panel_w, panel_h = 700, 520
        panel_x = (SCREEN_WIDTH - panel_w)//2
        panel_y = (SCREEN_HEIGHT - panel_h)//2
        pygame.draw.rect(surf, (50,50,70), (panel_x, panel_y, panel_w, panel_h), border_radius=15)
        pygame.draw.rect(surf, COLOR_GOLD, (panel_x, panel_y, panel_w, panel_h), 3, border_radius=15)
        step = self.steps[self.current_step]
        title = self.font_large.render(step["title"], True, COLOR_WHITE)
        surf.blit(title, (panel_x+panel_w//2-title.get_width()//2, panel_y+30))
        lines = step["text"].split("\n")
        y_offset = panel_y + 90
        for line in lines:
            txt = self.font_medium.render(line, True, (220,220,220))
            surf.blit(txt, (panel_x+50, y_offset))
            y_offset += 35
        if step["controls"]:
            ctrl_title = self.font_small.render("Controls:", True, COLOR_GOLD)
            surf.blit(ctrl_title, (panel_x+50, y_offset+10))
            y_offset += 40
            for ctrl in step["controls"]:
                ctrl_txt = self.font_small.render(f"• {ctrl}", True, (200,200,200))
                surf.blit(ctrl_txt, (panel_x+70, y_offset))
                y_offset += 28
        prog = self.font_small.render(f"Step {self.current_step+1}/{len(self.steps)}", True, (180,180,180))
        surf.blit(prog, (panel_x+20, panel_y+panel_h-40))
        button_w, button_h = 120, 40
        button_x = panel_x+panel_w-button_w-20
        button_y = panel_y+panel_h-button_h-20
        pygame.draw.rect(surf, (60,100,60), (button_x, button_y, button_w, button_h), border_radius=5)
        btn_txt = "Next →" if self.current_step < len(self.steps)-1 else "Finish"
        btn_surf = self.font_medium.render(btn_txt, True, COLOR_WHITE)
        surf.blit(btn_surf, (button_x+button_w//2-btn_surf.get_width()//2, button_y+button_h//2-btn_surf.get_height()//2))

    def handle_event(self, event):
        if not self.active: return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.next_step()
            elif event.key == pygame.K_ESCAPE:
                self.active = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            panel_w, panel_h = 700, 520
            panel_x = (SCREEN_WIDTH - panel_w)//2
            panel_y = (SCREEN_HEIGHT - panel_h)//2
            button_w, button_h = 120, 40
            button_x = panel_x+panel_w-button_w-20
            button_y = panel_y+panel_h-button_h-20
            if button_x <= mx <= button_x+button_w and button_y <= my <= button_y+button_h:
                self.next_step()

# ==========================================
# UI
# ==========================================
class UI:
    def __init__(self):
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
        # Define exit button rect for click handling
        self.exit_rect = pygame.Rect(SCREEN_WIDTH - 70, 5, 60, 30)

    def draw(self, surf, game_state, inventory, player, world, quiz_active, question_active, barn_storage_active, vending_machine_active, city_market_active):
        # Draw top bar background (taller, to fit everything cleanly)
        TOP_BAR_HEIGHT = 110
        top_bar = pygame.Surface((SCREEN_WIDTH, TOP_BAR_HEIGHT))
        top_bar.fill(COLOR_UI_BG)
        top_bar.set_alpha(230)
        surf.blit(top_bar, (0,0))

        # Exit button (top-right corner, fixed spot)
        exit_rect = pygame.Rect(SCREEN_WIDTH - 65, 5, 55, 30)
        pygame.draw.rect(surf, (150, 60, 60), exit_rect, border_radius=5)
        pygame.draw.rect(surf, (200, 100, 100), exit_rect, 2, border_radius=5)
        exit_text = self.small_font.render("✕ Exit", True, COLOR_WHITE)
        surf.blit(exit_text, (exit_rect.x + 10, exit_rect.y + 8))

        # Time and weather (top-left)
        time_text = self.font.render(f"Day {game_state.day}  {game_state.get_time_str()}  {game_state.weather.upper()}  {game_state.season.name}", True, COLOR_WHITE)
        surf.blit(time_text, (10, 8))

        # Energy bar (left column, row 2)
        energy_width = 200
        energy_x = 10
        energy_y = 35
        pygame.draw.rect(surf, COLOR_ENERGY_BG, (energy_x, energy_y, energy_width, 20), border_radius=10)
        energy_percent = game_state.energy / game_state.max_energy
        energy_color = COLOR_ENERGY if energy_percent > 0.3 else (255,50,50)
        pygame.draw.rect(surf, energy_color, (energy_x, energy_y, int(energy_width*energy_percent), 20), border_radius=10)
        energy_text = self.small_font.render(f"⚡ ENERGY: {int(game_state.energy)}/{game_state.max_energy}", True, COLOR_WHITE)
        surf.blit(energy_text, (energy_x+5, energy_y+4))

        # Health bar (left column, row 3)
        health_width = 200
        health_x = 10
        health_y = 60
        pygame.draw.rect(surf, COLOR_HEALTH_BG, (health_x, health_y, health_width, 20), border_radius=10)
        hp_percent = game_state.health / game_state.max_health
        hp_color = (46,204,113) if hp_percent>0.5 else (241,196,15) if hp_percent>0.2 else (231,76,60)
        pygame.draw.rect(surf, hp_color, (health_x, health_y, int(health_width*hp_percent), 20), border_radius=10)
        health_text = self.small_font.render(f"❤️ HEALTH: {int(game_state.health)}/{game_state.max_health}", True, COLOR_WHITE)
        surf.blit(health_text, (health_x+5, health_y+4))

        # --- Right-hand column: everything stacked in its own row, right-aligned ---
        right_margin = 150  # keeps clear of the Exit button
        row_h = 24

        def blit_right(text_surf, row):
            surf.blit(text_surf, (SCREEN_WIDTH - right_margin - text_surf.get_width(), 8 + row*row_h))

        # Row 0: Money
        money_text = self.font.render(f"💰 ${game_state.money}", True, COLOR_GOLD)
        blit_right(money_text, 0)

        # Row 1: XP bar (drawn as a bar, not just text, so build it manually)
        exp_width = 220
        exp_x = SCREEN_WIDTH - right_margin - exp_width
        exp_y = 8 + 1*row_h
        pygame.draw.rect(surf, (50,50,60), (exp_x, exp_y, exp_width, 20), border_radius=10)
        exp_percent = game_state.exp / game_state.exp_needed if game_state.exp_needed>0 else 1
        pygame.draw.rect(surf, COLOR_EXP, (exp_x, exp_y, int(exp_width*exp_percent), 20), border_radius=10)
        exp_text = self.small_font.render(f"⭐ LV.{game_state.level} ({game_state.exp}/{game_state.exp_needed} XP)", True, COLOR_WHITE)
        surf.blit(exp_text, (exp_x+5, exp_y+3))

        # Below the XP bar: Zoom, Inventory, Used Today — left-aligned to the bar, extra gap first
        below_x = exp_x
        below_y = exp_y + 28  # clear gap below the bar

        zoom_percent = int((game_state.zoom - MIN_ZOOM) / (MAX_ZOOM - MIN_ZOOM) * 100)
        zoom_text = self.small_font.render(f"🔍 ZOOM: {zoom_percent}%", True, COLOR_WHITE)
        surf.blit(zoom_text, (below_x, below_y))

        inv_count = sum(1 for v in inventory.items.values() if v > 0)
        inv_text = self.small_font.render(f"📦 Inventory: {inv_count} types", True, (200,200,200))
        surf.blit(inv_text, (below_x, below_y + row_h))

        energy_used = self.small_font.render(f"⚡ Used today: {int(game_state.energy_used_today)}", True, (200,200,200))
        surf.blit(energy_used, (below_x, below_y + row_h*2))

        # Daily quiz reminder
        if not quiz_active and not question_active and not barn_storage_active and not vending_machine_active and not city_market_active and game_state.day_changed and not hasattr(game_state, 'quiz_reminder_shown'):
            game_state.quiz_reminder_shown = True
            reminder = self.small_font.render("📚 NEW DAY! Answer the Daily Quiz for bonus rewards! 📚", True, COLOR_GOLD)
            rem_rect = reminder.get_rect(center=(SCREEN_WIDTH//2, 90))
            bg = pygame.Surface((reminder.get_width()+20, 25))
            bg.fill((0,0,0))
            bg.set_alpha(180)
            surf.blit(bg, (rem_rect.x-10, rem_rect.y-2))
            surf.blit(reminder, rem_rect)
        
        # Toolbar
        toolbar_y = SCREEN_HEIGHT - 70
        slot_w = 90
        slot_spacing = 15
        total_w = len(inventory.toolbar)*slot_w + (len(inventory.toolbar)-1)*slot_spacing
        start_x = (SCREEN_WIDTH - total_w)//2
        pygame.draw.rect(surf, (20,20,30,200), (start_x-10, toolbar_y-5, total_w+20, 70), border_radius=10)
        for i,item in enumerate(inventory.toolbar):
            x = start_x + i*(slot_w+slot_spacing)
            bg = (60,60,80) if i != inventory.selected_slot else (100,100,140)
            pygame.draw.rect(surf, bg, (x, toolbar_y, slot_w, 60), border_radius=8)
            pygame.draw.rect(surf, COLOR_GOLD if i==inventory.selected_slot else (100,100,120), (x, toolbar_y, slot_w, 60), 2, border_radius=8)
            if item:
                if item == "wheat_seed":
                    scaled_seed = pygame.transform.scale(TEX_WHEAT_SEED, (28, 28))
                    surf.blit(scaled_seed, (x+slot_w//2-14, toolbar_y+16))
                elif item == "corn_seed":
                    scaled_seed = pygame.transform.scale(TEX_CORN_SEED, (28, 28))
                    surf.blit(scaled_seed, (x+slot_w//2-14, toolbar_y+16))
                count = inventory.items.get(item,0)
                if count>0:
                    cnt_surf = self.small_font.render(str(count), True, COLOR_WHITE)
                    pygame.draw.circle(surf, (50,50,70), (x+slot_w-15, toolbar_y+50), 10)
                    surf.blit(cnt_surf, (x+slot_w-19, toolbar_y+46))
        
        # Bottom hints
        save_hint = self.small_font.render("F5:Save  F9:Load  T:Tutorial  Q/E:Zoom  Shift+Arrow:Run  F:Harvest Trees  B:Barn Storage  V:Vending Machine  M:City Market", True, (200,200,200))
        surf.blit(save_hint, (10, SCREEN_HEIGHT-25))
        
        # Context-sensitive hints
        pt = (player.tx, player.ty)
        hint = ""
        truck_found = False
        for typ, x, y in world.decor:
            if typ == "truck":
                if abs(x - player.tx) <= 2 and abs(y - player.ty) <= 1:
                    hint = "🚛 Press M to go to the City Market! Sell your harvest! 🚛"
                    truck_found = True
                    break
        if not hint:
            for vending in world.vending_machines:
                if abs(vending.x - player.tx) <= 1 and abs(vending.y - player.ty) <= 1:
                    hint = "Press V to buy Energy Drinks! (Restores 50 energy - $10)"
                    break
        if not hint:
            if 14 <= player.tx <= 20 and 1 <= player.ty <= 6:
                hint = "Press B to open Barn Storage! (Move items from inventory to barn)"
            else:
                for tree in world.fruit_trees:
                    if abs(tree.x - player.tx) <= 1 and abs(tree.y - player.ty) <= 1 and tree.has_fruits:
                        hint = "🍊 Press F to harvest fruit! (Costs 10 energy, goes to inventory)"
                        break
        if not hint:
            if pt in world.crops:
                crop = world.crops[pt]
                if crop["growth"] >= 1.0:
                    hint = "🌾 Press H to Harvest! (Costs 5 energy, goes to inventory!)"
                else:
                    hint = f"🌱 Growing: {int(crop['growth']*100)}%"
            elif world.tiles[player.ty][player.tx] == TileType.SOIL:
                hint = "🌾 Press P to Plant! (Costs 8 energy, with quiz!)"
        if hint:
            hint_surf = self.small_font.render(hint, True, COLOR_WHITE)
            bg = pygame.Surface((hint_surf.get_width()+20, 28))
            bg.fill((0,0,0)); bg.set_alpha(180)
            surf.blit(bg, (SCREEN_WIDTH//2 - hint_surf.get_width()//2 -10, SCREEN_HEIGHT-55))
            surf.blit(hint_surf, (SCREEN_WIDTH//2 - hint_surf.get_width()//2, SCREEN_HEIGHT-50))

# ==========================================
# SAVE/LOAD FUNCTIONS
# ==========================================
def save_game(game_state, world, inventory, player, quiz, barn_storage):
    fruit_data = [{"type":t.tree_type, "x":t.x, "y":t.y, "has_fruits":t.has_fruits, "fruit_regrow_timer":t.fruit_regrow_timer} for t in world.fruit_trees]
    vending_data = [{"x":v.x, "y":v.y} for v in world.vending_machines]
    data = {
        "game_state": {
            "day_time": game_state.day_time, "day": game_state.day,
            "weather": game_state.weather, "weather_timer": game_state.weather_timer,
            "money": game_state.money, "exp": game_state.exp, "level": game_state.level,
            "exp_needed": game_state.exp_needed, "energy": game_state.energy, "max_energy": game_state.max_energy,
            "health": game_state.health, "max_health": game_state.max_health,
            "season": game_state.season.value, "season_timer": game_state.season_timer,
            "achievements": game_state.achievements, "tutorial_shown": game_state.tutorial_shown,
            "zoom": game_state.zoom, "last_day": game_state.last_day,
            "energy_used_today": game_state.energy_used_today
        },
        "inventory": inventory.items,
        "player": {"x": player.tx, "y": player.ty},
        "quiz": {"quiz_taken_today": quiz.quiz_taken_today, "last_day": quiz.last_day},
        "fruit_trees": fruit_data,
        "vending_machines": vending_data,
        "barn_storage": barn_storage.stored_items,
        "world": {
            "crops": {f"{x},{y}": d for (x,y),d in world.crops.items()},
            "animal_products_timers": world.animal_products
        }
    }
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_game(game_state, world, inventory, player, quiz, barn_storage):
    if not os.path.exists(SAVE_FILE):
        return False
    with open(SAVE_FILE, "r") as f:
        data = json.load(f)
    gs = data["game_state"]
    game_state.day_time = gs["day_time"]
    game_state.day = gs["day"]
    game_state.weather = gs["weather"]
    game_state.weather_timer = gs["weather_timer"]
    game_state.money = gs["money"]
    game_state.exp = gs["exp"]
    game_state.level = gs["level"]
    game_state.exp_needed = gs["exp_needed"]
    game_state.energy = gs["energy"]
    game_state.max_energy = gs["max_energy"]
    game_state.health = gs.get("health", 100)
    game_state.max_health = gs.get("max_health", 100)
    game_state.season = Season(gs["season"])
    game_state.season_timer = gs["season_timer"]
    game_state.achievements = gs["achievements"]
    game_state.tutorial_shown = gs.get("tutorial_shown", False)
    game_state.zoom = gs.get("zoom", 1.0)
    game_state.last_day = gs.get("last_day", 1)
    game_state.energy_used_today = gs.get("energy_used_today", 0)
    game_state.quiz_reminder_shown = False  # Reset reminder when loading
    game_state.update_grass_texture()
    inventory.items = data["inventory"]
    player.tx, player.ty = data["player"]["x"], data["player"]["y"]
    player.x = player.tx * TILE_SIZE
    player.y = player.ty * TILE_SIZE
    player.moving = False
    for td in data.get("fruit_trees", []):
        for tree in world.fruit_trees:
            if tree.x == td["x"] and tree.y == td["y"]:
                tree.has_fruits = td["has_fruits"]
                tree.fruit_regrow_timer = td["fruit_regrow_timer"]
                break
    barn_data = data.get("barn_storage", {})
    for item, amount in barn_data.items():
        if item in barn_storage.stored_items:
            barn_storage.stored_items[item] = amount
    qd = data.get("quiz", {})
    quiz.quiz_taken_today = qd.get("quiz_taken_today", False)
    quiz.last_day = qd.get("last_day", game_state.day)
    quiz.active = False
    quiz.selected_option = -1
    quiz.show_result = False
    world.crops.clear()
    for key, cd in data["world"]["crops"].items():
        x,y = map(int, key.split(","))
        world.crops[(x,y)] = cd
        world.tiles[y][x] = TileType.CROP
    world.animal_products = data["world"]["animal_products_timers"]
    return True

# ==========================================
# MAIN GAME CLASS
# ==========================================
class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Zhing Nor")
        self.clock = pygame.time.Clock()
        self.running = True
        self.dt = 0
        self.world = World(40, 38)
        self.game_state = GameState()
        self.inventory = Inventory()
        self.player = Player(8, 14)
        self.quiz = DailyQuiz()
        self.barn_storage = BarnStorage()
        self.city_market = CityMarket()
        self.current_question = None
        self.pending_action = None
        self.active_vending_machine = None
        self.temp_message = None
        self.temp_message_timer = 0
        self.tutorial = Tutorial()
        self.game_state.inventory = self.inventory
        self.world.game_state = self.game_state
        self.animals = [
            Animal("cow", 31*TILE_SIZE + 15, 24*TILE_SIZE + 15, self.world),
            Animal("cow", 34*TILE_SIZE + 10, 25*TILE_SIZE + 10, self.world),
            Animal("cow", 29*TILE_SIZE + 20, 26*TILE_SIZE + 15, self.world),
            Animal("chicken", 23*TILE_SIZE + 20, 24*TILE_SIZE + 15, self.world),
            Animal("chicken", 25*TILE_SIZE + 15, 25*TILE_SIZE + 20, self.world),
            Animal("chicken", 22*TILE_SIZE + 30, 23*TILE_SIZE + 30, self.world),
        ]
        self.plant_questions = {
            "wheat_seed": {"title":"🌾 Planting Wheat - Quick Quiz! 🌾",
                "question":"What do wheat seeds need to germinate properly?",
                "options":["Only sunlight","Water, warmth, and oxygen","Only fertilizer","Only soil"],
                "correct":1, "reward_money":5, "reward_exp":3},
            "corn_seed": {"title":"🌽 Planting Corn - Quick Quiz! 🌽",
                "question":"What is the ideal temperature range for corn germination?",
                "options":["40-50°F","60-95°F","32-40°F","100-120°F"],
                "correct":1, "reward_money":5, "reward_exp":3}
        }
        self.harvest_questions = {
            "wheat": {"title":"🌾 Harvesting Wheat - Quick Quiz! 🌾",
                "question":"What part of the wheat plant is harvested for food?",
                "options":["The roots","The leaves","The seeds (grains)","The stems"],
                "correct":2, "reward_money":10, "reward_exp":5},
            "corn": {"title":"🌽 Harvesting Corn - Quick Quiz! 🌽",
                "question":"Each corn kernel is actually what?",
                "options":["A seed","A fruit","A vegetable","A root"],
                "correct":0, "reward_money":10, "reward_exp":5}
        }
        self.ui = UI()
        self.camera_x, self.camera_y = 0,0
        self.game_state.quiz_reminder_shown = False

    def update_camera(self):
        self.camera_x = self.player.x + TILE_SIZE//2 - SCREEN_WIDTH//(2*self.game_state.zoom)
        self.camera_y = self.player.y + TILE_SIZE//2 - SCREEN_HEIGHT//(2*self.game_state.zoom)
        max_x = self.world.width * TILE_SIZE - SCREEN_WIDTH / self.game_state.zoom
        max_y = self.world.height * TILE_SIZE - SCREEN_HEIGHT / self.game_state.zoom
        self.camera_x = max(0, min(self.camera_x, max_x))
        self.camera_y = max(0, min(self.camera_y, max_y))

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE:
                global SCREEN_WIDTH, SCREEN_HEIGHT
                SCREEN_WIDTH, SCREEN_HEIGHT = event.w, event.h
                self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
                self.update_camera()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Check exit button first
                exit_rect = pygame.Rect(SCREEN_WIDTH - 65, 5, 55, 30)
                if exit_rect.collidepoint(event.pos):
                    self.running = False
                    return
                
                if self.barn_storage.active:
                    if self.barn_storage.handle_click(event.pos, self.inventory):
                        pass
                elif self.active_vending_machine:
                    success, message = self.active_vending_machine.handle_click(event.pos, self.game_state)
                    if message:
                        self.show_temporary_message(message, (100,200,100) if success else (200,100,100))
                    if not self.active_vending_machine.active:
                        self.active_vending_machine = None
                elif self.city_market.active:
                    if self.city_market.handle_click(event.pos, self.game_state, self.inventory):
                        pass
                elif self.current_question and self.current_question.active:
                    if self.current_question.handle_click(event.pos, self.game_state, self.inventory):
                        pass
                elif self.quiz.active:
                    if self.quiz.handle_click(event.pos, self.game_state):
                        pass
                elif self.tutorial.active:
                    panel_w, panel_h = 700, 520
                    panel_x = (SCREEN_WIDTH - panel_w)//2
                    panel_y = (SCREEN_HEIGHT - panel_h)//2
                    button_w, button_h = 120, 40
                    button_x = panel_x+panel_w-button_w-20
                    button_y = panel_y+panel_h-button_h-20
                    if button_x <= event.pos[0] <= button_x+button_w and button_y <= event.pos[1] <= button_y+button_h:
                        self.tutorial.next_step()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_t:
                    if not self.tutorial.active:
                        self.tutorial.start()
                    else:
                        self.tutorial.active = False
                elif event.key == pygame.K_q:
                    self.game_state.zoom_in()
                elif event.key == pygame.K_e:
                    self.game_state.zoom_out()
                elif event.key == pygame.K_b:
                    if not self.tutorial.active and not self.quiz.active and not self.current_question and not self.active_vending_machine and not self.city_market.active:
                        if 14 <= self.player.tx <= 20 and 1 <= self.player.ty <= 6:
                            self.barn_storage.active = not self.barn_storage.active
                elif event.key == pygame.K_m:
                    if not self.tutorial.active and not self.quiz.active and not self.current_question and not self.barn_storage.active and not self.active_vending_machine:
                        truck_found = False
                        for typ, x, y in self.world.decor:
                            if typ == "truck":
                                if abs(x - self.player.tx) <= 2 and abs(y - self.player.ty) <= 1:
                                    self.city_market.open_market()
                                    self.show_temporary_message("🏙️ Welcome to the City Market! Sell your goods from inventory!", (100,200,100))
                                    truck_found = True
                                    break
                        if not truck_found:
                            self.show_temporary_message("🚛 Stand near the truck (near the house) to go to the city market!", (200,200,100))
                elif event.key == pygame.K_v:
                    if not self.tutorial.active and not self.quiz.active and not self.current_question and not self.barn_storage.active and not self.city_market.active:
                        for vending in self.world.vending_machines:
                            if abs(vending.x - self.player.tx) <= 1 and abs(vending.y - self.player.ty) <= 1:
                                self.active_vending_machine = vending
                                self.active_vending_machine.open_menu()
                                self.show_temporary_message("Vending Machine Opened! Buy energy drinks!", (100,200,100))
                                break
                        else:
                            self.show_temporary_message("Stand next to the vending machine!", (200,200,100))
                elif event.key == pygame.K_f:
                    if not self.tutorial.active and not self.quiz.active and not self.current_question and not self.barn_storage.active and not self.active_vending_machine and not self.city_market.active:
                        for tree in self.world.fruit_trees:
                            if abs(tree.x - self.player.tx) <= 1 and abs(tree.y - self.player.ty) <= 1:
                                if self.game_state.energy >= 10:
                                    res = tree.harvest(self.game_state, self.inventory)
                                    if res:
                                        self.show_temporary_message(res, (100,200,100))
                                        self.world.particle_system.emit(tree.x*TILE_SIZE+TILE_SIZE//2, tree.y*TILE_SIZE+TILE_SIZE//2, (255,200,100), 10, 0.5)
                                        break
                                else:
                                    self.show_temporary_message("Not enough energy! Need 10 energy!", (200,100,100))
                elif event.key == pygame.K_F5:
                    save_game(self.game_state, self.world, self.inventory, self.player, self.quiz, self.barn_storage)
                    self.show_temporary_message("Game Saved!", (100,200,100))
                elif event.key == pygame.K_F9:
                    if load_game(self.game_state, self.world, self.inventory, self.player, self.quiz, self.barn_storage):
                        self.world.game_state = self.game_state
                        self.game_state.inventory = self.inventory
                        self.world.update_grass_texture()
                        self.show_temporary_message("Game Loaded!", (100,200,100))
                elif not self.tutorial.active and not self.quiz.active and not self.current_question and not self.barn_storage.active and not self.active_vending_machine and not self.city_market.active and not self.player.moving:
                    
                    if event.key == pygame.K_p:
                        sel = self.inventory.get_selected_item()
                        if sel and "seed" in sel and sel in self.plant_questions:
                            if self.game_state.energy >= 8:
                                self.pending_action = {"type":"plant","seed":sel}
                                qd = self.plant_questions[sel].copy()
                                self.current_question = QuestionPopup(qd, self.on_question_complete)
                            else:
                                self.show_temporary_message("Not enough energy! Need 8 energy!", (200,100,100))
                    elif event.key == pygame.K_h:
                        if self.game_state.energy >= 5:
                            harvested = self.world.harvest_crop(self.player.tx, self.player.ty, self.inventory, self.game_state)
                            if harvested and harvested in self.harvest_questions:
                                self.pending_action = {"type":"harvest","crop":harvested}
                                qd = self.harvest_questions[harvested].copy()
                                self.current_question = QuestionPopup(qd, self.on_question_complete)
                            elif harvested:
                                self.show_temporary_message(f"✓ {harvested.capitalize()} harvested! Added to inventory! -5 energy", (100,200,100))
                        else:
                            self.show_temporary_message("Not enough energy! Need 5 energy!", (200,100,100))
                    elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                        slot = event.key - pygame.K_1
                        if slot < len(self.inventory.toolbar):
                            self.inventory.selected_slot = slot
            if self.tutorial.active:
                self.tutorial.handle_event(event)

    def on_question_complete(self, success):
        if self.pending_action and success:
            if self.pending_action["type"] == "plant":
                seed = self.pending_action["seed"]
                if self.world.plant_crop(self.player.tx, self.player.ty, seed, self.game_state):
                    self.inventory.remove(seed,1)
                    self.game_state.add_exp(5)
                    self.show_temporary_message(f"✓ {seed.replace('_seed','').capitalize()} planted! -8 energy", (100,200,100))
            elif self.pending_action["type"] == "harvest":
                crop = self.pending_action["crop"]
                self.game_state.add_exp(20)
                self.show_temporary_message(f"✓ {crop.capitalize()} harvested! Added to inventory! -5 energy", (100,200,100))
        elif self.pending_action and not success:
            self.show_temporary_message("✗ Wrong answer! Try again!", (200,100,100))
        self.current_question = None
        self.pending_action = None

    def show_temporary_message(self, msg, color):
        self.temp_message = {"text": msg, "color": color, "timer": 120}
    
    def update(self):
        if self.temp_message:
            self.temp_message["timer"] -= 1
            if self.temp_message["timer"] <= 0:
                self.temp_message = None

        if not self.tutorial.active and not self.quiz.active and not self.current_question:
            self.game_state.update(self.dt)
            self.player.update(self.dt, self.world)

            # Continuous movement while a direction key is held down
            if (not self.barn_storage.active and not self.active_vending_machine
                    and not self.city_market.active and not self.player.moving):
                keys = pygame.key.get_pressed()
                is_run = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
                if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                    self.player.start_move(-1, 0, self.world, is_run)
                elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                    self.player.start_move(1, 0, self.world, is_run)
                elif keys[pygame.K_UP] or keys[pygame.K_w]:
                    self.player.start_move(0, -1, self.world, is_run)
                elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                    self.player.start_move(0, 1, self.world, is_run)

            for a in self.animals:
                a.update(self.dt)
            self.world.update_animal_products(self.dt, self.inventory)
            self.world.update_fruit_trees(self.dt)
            season_factor = 1.2 if self.game_state.season == Season.SUMMER else 0.5 if self.game_state.season == Season.WINTER else 1.0
            weather_factor = 1.2 if self.game_state.weather == "rainy" else 0.8 if self.game_state.weather == "stormy" else 1.0
            self.world.update_crops(self.dt, weather_factor, season_factor)
            self.world.particle_system.update(self.dt)
            if self.game_state.season == Season.AUTUMN and random.random()<0.02:
                fx = random.randint(0, self.world.width*TILE_SIZE)
                fy = random.randint(0, self.world.height*TILE_SIZE)
                self.world.particle_system.emit(fx, fy, (200,120,40), 1, 1.0)
            self.update_camera()
            if self.game_state.day_changed and self.game_state.day_time < 0.5:
                if self.quiz.try_start_quiz(self.game_state.day):
                    self.game_state.quiz_reminder_shown = False

    def draw(self):
        self.world.draw(self.screen, self.camera_x, self.camera_y, self.game_state, self.game_state.zoom)
        for a in self.animals:
            a.draw(self.screen, self.camera_x, self.camera_y, self.game_state.zoom)
        self.player.draw(self.screen, self.camera_x, self.camera_y, self.game_state.zoom)
        self.world.particle_system.draw(self.screen, self.camera_x, self.camera_y, self.game_state.zoom)
        self.ui.draw(self.screen, self.game_state, self.inventory, self.player, self.world, self.quiz.active, self.current_question is not None, self.barn_storage.active, self.active_vending_machine is not None, self.city_market.active)
        if self.barn_storage.active:
            self.barn_storage.draw_storage_ui(self.screen, self.game_state, self.inventory)
        if self.active_vending_machine:
            self.active_vending_machine.draw_menu(self.screen, self.game_state)
        if self.city_market.active:
            self.city_market.draw_market_ui(self.screen, self.game_state, self.inventory)
        if self.temp_message:
            font = pygame.font.Font(None, 28)
            msg_surf = font.render(self.temp_message["text"], True, self.temp_message["color"])
            msg_rect = msg_surf.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//3))
            bg = pygame.Surface((msg_surf.get_width()+40, msg_surf.get_height()+20))
            bg.fill((0,0,0)); bg.set_alpha(200)
            self.screen.blit(bg, (msg_rect.x-20, msg_rect.y-10))
            self.screen.blit(msg_surf, msg_rect)
        if self.current_question and self.current_question.active:
            self.current_question.draw(self.screen)
        elif self.quiz.active:
            self.quiz.draw(self.screen)
        if self.tutorial.active:
            self.tutorial.draw(self.screen)
        light = self.game_state.get_light_factor()
        if light < 0.8:
            dark = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            dark.fill((0,0,0, int((1-light)*150)))
            self.screen.blit(dark, (0,0))
        if self.game_state.weather == "rainy":
            for _ in range(100):
                x = random.randint(0, SCREEN_WIDTH)
                y = random.randint(0, SCREEN_HEIGHT)
                pygame.draw.line(self.screen, (180,220,255), (x,y), (x-2,y+4), 1)
        pygame.display.flip()

    def run(self):
        while self.running:
            self.dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update()
            self.draw()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    game = Game()
    game.run()