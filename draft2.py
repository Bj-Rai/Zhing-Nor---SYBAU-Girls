import pygame
import sys
import math
import random

# ==========================================
# EXPERT ARTWORK ENGINE (BAKED HIGH-FIDELITY ASSETS)
# ==========================================
class HighFidelityFarmEngine:
    @staticmethod
    def create_vibrant_grass(size):
        surf = pygame.Surface((size, size))
        surf.fill((106, 182, 52)) 
        for _ in range(40):
            gx = random.randint(0, size - 2)
            gy = random.randint(0, size - 2)
            pygame.draw.line(surf, (122, 202, 65), (gx, gy), (gx + 1, gy - random.randint(1, 4)))
        return surf

    @staticmethod
    def create_golden_wheat(size):
        surf = pygame.Surface((size, size))
        surf.fill((220, 150, 60)) 
        for y in range(4, size, 8):
            pygame.draw.line(surf, (175, 105, 30), (0, y), (size, y), 2)
            for _ in range(2):
                pygame.draw.circle(surf, (240, 185, 80), (random.randint(2, size-2), y), 2)
        return surf

    @staticmethod
    def draw_premium_barn():
        w, h = TILE_SIZE * 3, TILE_SIZE * 3
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        c_red = (195, 35, 40)
        c_dark_red = (140, 20, 25)
        c_roof = (55, 55, 60)
        c_white = (245, 245, 245)

        # Structure shadow
        pygame.draw.ellipse(surf, (35, 65, 20, 140), (5, h - 22, w - 10, 18))
        # Barn Base Walls
        pygame.draw.rect(surf, c_red, (12, 45, w - 24, h - 50), border_radius=4)
        for x in range(16, w - 16, 8):
            pygame.draw.line(surf, c_dark_red, (x, 45), (x, h - 6), 2)

        # X-Doors
        door_w, door_h = 46, 46
        bx, by = w // 2 - door_w // 2, h - door_h - 5
        pygame.draw.rect(surf, c_white, (bx, by, door_w, door_h), border_radius=2)
        pygame.draw.rect(surf, c_dark_red, (bx + 2, by + 2, door_w - 4, door_h - 4))
        pygame.draw.line(surf, c_white, (bx + 4, by + 4), (bx + door_w - 5, by + door_h - 5), 3)
        pygame.draw.line(surf, c_white, (bx + door_w - 5, by + 4), (bx + 4, by + door_h - 5), 3)

        # Roof Trims
        roof_pts = [(w // 2, 2), (w // 2 - 36, 12), (w // 2 - 56, 32), (10, 48), (w - 10, 48), (w // 2 + 56, 32), (w // 2 + 36, 12)]
        pygame.draw.polygon(surf, c_roof, roof_pts)
        pygame.draw.polygon(surf, c_white, roof_pts, width=3) 
        return surf

    @staticmethod
    def draw_grain_silo():
        w, h = TILE_SIZE * 2, TILE_SIZE * 3
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        # Drop Shadow
        pygame.draw.ellipse(surf, (35, 65, 20, 130), (4, h - 16, w - 8, 12))
        # Steel Struts
        pygame.draw.rect(surf, (90, 100, 110), (12, h - 45, 6, 40))
        pygame.draw.rect(surf, (90, 100, 110), (w - 18, h - 45, 6, 40))
        # Silo Chamber Cylinder
        pygame.draw.rect(surf, (215, 60, 45), (8, 25, w - 16, h - 65), border_radius=6)
        pygame.draw.rect(surf, (240, 90, 75), (8, 25, (w - 16) // 3, h - 65)) # Highlight strip
        # Hopper Conical Bottom
        pygame.draw.polygon(surf, (150, 35, 25), [(8, h - 40), (w - 8, h - 40), (w // 2, h - 15)])
        # Metallic Roof Cone
        pygame.draw.polygon(surf, (180, 190, 200), [(w // 2, 2), (4, 26), (w - 4, 26)])
        return surf

    @staticmethod
    def draw_cozy_house():
        w, h = TILE_SIZE * 4, TILE_SIZE * 3
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        # Main structure body
        pygame.draw.rect(surf, (230, 215, 190), (20, 40, w - 40, h - 45), border_radius=4)
        # Dark modern shingle roof roofs
        pygame.draw.polygon(surf, (50, 55, 65), [(w // 2, 5), (10, 42), (w - 10, 42)])
        # Window setups
        pygame.draw.rect(surf, (110, 75, 45), (w // 4 - 12, 60, 24, 24), border_radius=2)
        pygame.draw.rect(surf, (135, 210, 240), (w // 4 - 10, 62, 20, 20))
        pygame.draw.rect(surf, (110, 75, 45), (3 * w // 4 - 12, 60, 24, 24), border_radius=2)
        pygame.draw.rect(surf, (135, 210, 240), (3 * w // 4 - 10, 62, 20, 20))
        # Warm central wooden door entryway frame
        pygame.draw.rect(surf, (135, 85, 50), (w // 2 - 15, h - 45, 30, 40), border_radius=2)
        pygame.draw.circle(surface=surf, color=(235, 185, 40), center=(w // 2 + 8, h - 25), radius=2.5) # Golden knob
        return surf

    @staticmethod
    def draw_bush_node(r_max=16, base_color=(45, 105, 35)):
        surf = pygame.Surface((r_max * 2 + 12, r_max * 2 + 12), pygame.SRCALPHA)
        cx, cy = surf.get_width() // 2, surf.get_height() // 2
        pygame.draw.ellipse(surf, (35, 65, 20, 90), (cx - r_max, cy + r_max // 2, r_max * 2, r_max // 2 + 4))
        offsets = [(0,0), (-6, -4), (6, -2), (-4, 6), (5, 5), (0, -8)]
        for ox, oy in offsets:
            r = random.randint(r_max - 4, r_max)
            pygame.draw.circle(surf, base_color, (cx + ox, cy + oy), r)
            pygame.draw.circle(surf, (min(255, base_color[0]+25), min(255, base_color[1]+35), base_color[2]), (cx + ox - 2, cy + oy - 3), int(r * 0.7))
        return surf

    @staticmethod
    def draw_pine_tree():
        w, h = 64, 96
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (35, 65, 20, 110), (w//2 - 16, h - 12, 32, 10))
        # Trunk
        pygame.draw.rect(surf, (75, 50, 35), (w//2 - 5, h - 30, 10, 25))
        # 3 Layers of organic conical pine leaves
        for i in range(3):
            b_y = h - 25 - (i * 20)
            pts = [(w//2, b_y - 30), (10 + (i * 4), b_y), (w - 10 - (i * 4), b_y)]
            pygame.draw.polygon(surf, (32 - (i*4), 78 - (i*8), 28 - (i*3)), pts)
        return surf

# --- Setup Constants ---
SCREEN_WIDTH = 960
SCREEN_HEIGHT = 720
FPS = 60
TILE_SIZE = 48 

# --- Color Palettes ---
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_UI_BAR = (38, 50, 56)
COLOR_ENERGY = (241, 196, 15)  
COLOR_EXP = (46, 204, 113)     

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("AgriQuest - High Fidelity 3.0 Ultimate Farm Engine")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 12, bold=True)
font_large = pygame.font.SysFont("Arial", 15, bold=True)

TEX_GRASS = HighFidelityFarmEngine.create_vibrant_grass(TILE_SIZE)
TEX_WHEAT_FIELD = HighFidelityFarmEngine.create_golden_wheat(TILE_SIZE)
TEX_BARN = HighFidelityFarmEngine.draw_premium_barn()
TEX_SILO = HighFidelityFarmEngine.draw_grain_silo()
TEX_HOUSE = HighFidelityFarmEngine.draw_cozy_house()
TEX_PINE = HighFidelityFarmEngine.draw_pine_tree()

TEX_BUSH_LARGE = HighFidelityFarmEngine.draw_bush_node(18, (35, 88, 28))
TEX_BUSH_SMALL = HighFidelityFarmEngine.draw_bush_node(11, (48, 112, 38))

# =========================================================
# REALTIME PARTICLE ENVIRONMENTAL FX SYSTEM
# =========================================================
class EnvironmentWeatherParticle:
    def __init__(self):
        self.reset()
        self.x = random.randint(0, SCREEN_WIDTH)

    def reset(self):
        self.x = -15
        self.y = random.randint(40, SCREEN_HEIGHT - 80)
        self.speed_x = random.uniform(1.0, 2.4)
        self.speed_y = random.uniform(-0.3, 0.3)
        self.size = random.uniform(3.0, 5.5)
        self.color = random.choice([(145, 215, 90, 150), (240, 200, 60, 130), (100, 180, 60, 140)])
        self.freq = random.uniform(0.02, 0.04)
        self.seed = random.uniform(0, 50)

    def update(self):
        self.x += self.speed_x
        self.y += self.speed_y + math.sin(pygame.time.get_ticks() * self.freq + self.seed) * 0.2
        if self.x > SCREEN_WIDTH or self.y < 40 or self.y > SCREEN_HEIGHT:
            self.reset()

    def draw(self, surface):
        p_surf = pygame.Surface((int(self.size * 2), int(self.size * 2)), pygame.SRCALPHA)
        pygame.draw.ellipse(p_surf, self.color, (0, 0, self.size * 2, self.size))
        surface.blit(p_surf, (int(self.x), int(self.y)))

# =========================================================
# HIGH FIDELITY ANIMALS (100% VISUALLY REDESIGNED PROFILES)
# =========================================================
class HighFidelityAnimal:
    def __init__(self, species, start_x, start_y):
        self.species = species
        self.x = start_x
        self.y = start_y
        self.vx, self.vy = 0, 0
        self.state_timer = random.randint(30, 90)
        self.anim_loop = random.randint(0, 100)
        self.speed = 0.45 if species == "COW" else 0.65
        self.facing_right = random.choice([True, False])

    def update(self):
        self.anim_loop += 1
        self.state_timer -= 1
        
        if self.state_timer <= 0:
            if random.random() < 0.40:
                self.vx, self.vy = 0, 0
                self.state_timer = random.randint(40, 120)
            else:
                angle = random.uniform(0, 2 * math.pi)
                self.vx = math.cos(angle) * self.speed
                self.vy = math.sin(angle) * self.speed
                self.facing_right = self.vx > 0
                self.state_timer = random.randint(60, 180)

        self.x += self.vx
        self.y += self.vy

        # Retain open map edge limits safely
        if self.x < 40: self.x, self.vx = 40, -self.vx; self.facing_right = self.vx > 0
        if self.x > SCREEN_WIDTH - 60: self.x, self.vx = SCREEN_WIDTH - 60, -self.vx; self.facing_right = self.vx > 0
        if self.y < 120: self.y, self.vy = 120, -self.vy
        if self.y > SCREEN_HEIGHT - 60: self.y, self.vy = SCREEN_HEIGHT - 60, -self.vy

    def draw(self, surface):
        cx, cy = int(self.x), int(self.y)
        bob = abs(math.sin(self.anim_loop * 0.14)) * 3.5
        leg_sw = math.sin(self.anim_loop * 0.25) * 4 if (self.vx != 0 or self.vy != 0) else 0

        if self.species == "COW":
            # Vector Shadow
            pygame.draw.ellipse(surface, (30, 60, 15, 110), (cx - 20, cy + 14, 40, 8))
            
            # Leg structures
            pygame.draw.rect(surface, (240, 235, 225), (cx - 14, cy + 6 + int(leg_sw), 5, 10), border_radius=1)
            pygame.draw.rect(surface, (240, 235, 225), (cx - 4, cy + 6 - int(leg_sw), 5, 10), border_radius=1)
            pygame.draw.rect(surface, (240, 235, 225), (cx + 6, cy + 6 + int(leg_sw), 5, 10), border_radius=1)
            pygame.draw.rect(surface, (230, 225, 215), (cx + 12, cy + 6 - int(leg_sw), 5, 10), border_radius=1)
            pygame.draw.rect(surface, (50, 40, 30), (cx - 14, cy + 14 + int(leg_sw), 5, 3)) # Hooves
            pygame.draw.rect(surface, (50, 40, 30), (cx + 12, cy + 14 - int(leg_sw), 5, 3))

            # Rounded organic main chassis torso
            pygame.draw.rect(surface, (245, 240, 235), (cx - 18, cy - 10 - int(bob), 38, 22), border_radius=7)
            # Spot patches overlay setup
            pygame.draw.circle(surface, (70, 45, 30), (cx - 8, cy - int(bob)), 7)
            pygame.draw.circle(surface, (70, 45, 30), (cx + 8, cy + 2 - int(bob)), 8)
            pygame.draw.ellipse(surface, (240, 170, 185), (cx - 2, cy + 8 - int(bob), 10, 6)) # Cute Udder core
            
            # Head structure mechanics
            hx = cx + 14 if self.facing_right else cx - 26
            pygame.draw.rect(surface, (245, 240, 235), (hx, cy - 18 - int(bob), 14, 16), border_radius=4)
            pygame.draw.circle(surface, (40, 40, 40), (hx + 10 if self.facing_right else hx + 4, cy - 12 - int(bob)), 2.5) # Eye
            pygame.draw.rect(surface, (245, 175, 185), (hx + 2 if self.facing_right else hx, cy - 7 - int(bob), 12, 6), border_radius=2) # Snout
        
        elif self.species == "CHICKEN":
            # Vector Shadow
            pygame.draw.ellipse(surface, (30, 60, 15, 110), (cx - 10, cy + 11, 20, 5))
            # Yellow structural support claws
            pygame.draw.line(surface, (245, 180, 20), (cx - 3, cy + 4), (cx - 4, cy + 12), 2)
            pygame.draw.line(surface, (245, 180, 20), (cx + 3, cy + 4), (cx + 4, cy + 12), 2)

            # Smooth layered feather body
            pygame.draw.circle(surface, (235, 235, 235), (cx, cy - int(bob)), 12)
            pygame.draw.ellipse(surface, (215, 95, 25), (cx - 6 if self.facing_right else cx - 2, cy - int(bob), 10, 8)) # Wings winglet
            
            hx = cx + 9 if self.facing_right else cx - 9
            pygame.draw.circle(surface, (245, 245, 245), (hx, cy - 10 - int(bob)), 7)
            pygame.draw.circle(surface, (230, 35, 35), (hx, cy - 17 - int(bob)), 3) # Vibrant Red Comb
            pygame.draw.circle(surface, (20, 20, 20), (hx + 2 if self.facing_right else hx - 2, cy - 11 - int(bob)), 1.5) # Beak eye
            # Beak polygon triangle
            bx_pts = [(hx + 6, cy - 10 - int(bob)), (hx + 11, cy - 8 - int(bob)), (hx + 6, cy - 6 - int(bob))] if self.facing_right else [(hx - 6, cy - 10 - int(bob)), (hx - 11, cy - 8 - int(bob)), (hx - 6, cy - 6 - int(bob))]
            pygame.draw.polygon(surface, (250, 165, 10), bx_pts)

# =========================================================
# FARMER PLAYER COMPONENT (PREMIUM SMOOTH MOVEMENT INTERACTION)
# =========================================================
class RealTimeFarmer:
    def __init__(self, tx, ty):
        self.tx, self.ty = tx, ty
        self.x, self.y = tx * TILE_SIZE, ty * TILE_SIZE
        self.speed = 5.0
        self.anim_tick = 0
        self.is_moving = False
        self.energy = 100.0
        self.exp = 0
        self.level = 1
        self.exp_needed = 100

    def move(self, dx, dy, grid_matrix):
        if self.energy < 5: return 
        nx, ny = self.tx + dx, self.ty + dy
        if 0 <= nx < (SCREEN_WIDTH // TILE_SIZE) and 0 <= ny < (SCREEN_HEIGHT // TILE_SIZE):
            self.tx, self.ty = nx, ny
            self.energy = max(0.0, self.energy - 0.3) 

    def gain_exp(self, amount):
        self.exp += amount
        if self.exp >= self.exp_needed:
            self.exp -= self.exp_needed
            self.level += 1
            self.exp_needed = int(self.exp_needed * 1.30) 

    def update(self):
        target_x, target_y = self.tx * TILE_SIZE, self.ty * TILE_SIZE
        self.is_moving = False
        
        if self.x < target_x: self.x = min(self.x + self.speed, target_x); self.is_moving = True
        elif self.x > target_x: self.x = max(self.x - self.speed, target_x); self.is_moving = True
        if self.y < target_y: self.y = min(self.y + self.speed, target_y); self.is_moving = True
        elif self.y > target_y: self.y = max(self.y - self.speed, target_y); self.is_moving = True
        
        if self.is_moving: self.anim_tick += 1
        else: self.anim_tick = 0
        self.energy = min(100.0, self.energy + 0.05)

    def draw(self, surface):
        cx, cy = int(self.x + TILE_SIZE // 2), int(self.y + TILE_SIZE // 2)
        walk_offset = math.sin(self.anim_tick * 0.35) * 3 if self.is_moving else 0
        leg_swing = math.cos(self.anim_tick * 0.35) * 4.5 if self.is_moving else 0
        arm_swing = math.sin(self.anim_tick * 0.35) * 5.5 if self.is_moving else 0
        
        # Ground Shadow
        pygame.draw.ellipse(surface, (30, 60, 15, 140), (cx - 12, cy + 13, 24, 6))
        # Shoes / Legs
        pygame.draw.rect(surface, (35, 80, 150), (cx - 4, cy + 8 + int(leg_swing), 3, 7), border_radius=1)
        pygame.draw.rect(surface, (35, 80, 150), (cx + 1, cy + 8 - int(leg_swing), 3, 7), border_radius=1)
        pygame.draw.rect(surface, (60, 45, 35), (cx - 5, cy + 14 + int(leg_swing), 4, 3), border_radius=1) 
        pygame.draw.rect(surface, (60, 45, 35), (cx, cy + 14 - int(leg_swing), 4, 3), border_radius=1)  
        
        # Red Arms
        pygame.draw.line(surface, (180, 40, 40), (cx - 5, cy + int(walk_offset)), (cx - 8, cy + 6 + int(walk_offset) + int(arm_swing)), 3)
        pygame.draw.circle(surface, (245, 205, 170), (cx - 8, cy + 6 + int(walk_offset) + int(arm_swing)), 2)
        pygame.draw.line(surface, (180, 40, 40), (cx + 5, cy + int(walk_offset)), (cx + 8, cy + 6 + int(walk_offset) - int(arm_swing)), 3)
        pygame.draw.circle(surface, (245, 205, 170), (cx + 8, cy + 6 + int(walk_offset) - int(arm_swing)), 2)

        # Torso Denim Overalls
        pygame.draw.rect(surface, (40, 100, 180), (cx - 5, cy - 3 + int(walk_offset), 10, 12), border_radius=3)
        pygame.draw.rect(surface, (180, 40, 40), (cx - 5, cy - 5 + int(walk_offset), 10, 3), border_radius=1)
        
        # Head Profile & Straw Hat
        pygame.draw.circle(surface, (245, 205, 170), (cx, cy - 10 + int(walk_offset)), 6)
        pygame.draw.ellipse(surface, (235, 200, 110), (cx - 15, cy - 16 + int(walk_offset), 30, 5))
        pygame.draw.rect(surface, (215, 180, 90), (cx - 6, cy - 22 + int(walk_offset), 12, 7), border_radius=2)

# =========================================================
# ADVANCED WORLD ENVIRONMENT DECOR MAP LAYER
# =========================================================
class UltimateFarmGridMap:
    def __init__(self):
        self.cols = SCREEN_WIDTH // TILE_SIZE
        self.rows = SCREEN_HEIGHT // TILE_SIZE
        self.matrix = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
        self.crop_progress = {}

        # Fields Setup Coordinates
        for r in range(9, 14):
            for c in range(2, 9): 
                self.matrix[r][c] = 2

        # Non-Linear Scattered Flora Bush Assets
        self.organic_flora = [
            (TEX_BUSH_LARGE, 80, 240), (TEX_BUSH_SMALL, 140, 260),
            (TEX_BUSH_LARGE, 480, 190), (TEX_BUSH_SMALL, 540, 210),
            (TEX_BUSH_LARGE, 350, 620), (TEX_BUSH_SMALL, 410, 640),
            (TEX_BUSH_LARGE, 880, 500)
        ]

        # Natural Evergreen Pine Forest Cluster backdrops
        self.forest_pines = [
            (10, 50), (60, 40), (120, 45), (460, 40), (510, 45),
            (740, 50), (800, 40), (860, 42), (910, 55)
        ]

    def draw_pasture_floor(self, surface):
        for r in range(self.rows):
            for c in range(self.cols):
                rect = pygame.Rect(c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                if self.matrix[r][c] == 2: surface.blit(TEX_WHEAT_FIELD, rect)
                else: surface.blit(TEX_GRASS, rect)

        # Draw dirt pathways
        pygame.draw.rect(surface, (190, 160, 120), (0, TILE_SIZE * 5, SCREEN_WIDTH, 40))
        pygame.draw.rect(surface, (195, 165, 125), (TILE_SIZE * 11, TILE_SIZE * 2, 50, SCREEN_HEIGHT))

        # Render active growing grain nodes
        for pos in self.crop_progress:
            c, r = pos
            prog = self.crop_progress[pos]
            px, py = c * TILE_SIZE + TILE_SIZE // 2, r * TILE_SIZE + TILE_SIZE // 2
            if prog < 100:
                pygame.draw.line(surface, (50, 180, 85), (px, py + 10), (px, py - int(prog*0.16)), 3)
            else:
                pygame.draw.line(surface, (245, 195, 30), (px - 4, py + 12), (px - 4, py - 10), 3)
                pygame.draw.line(surface, (245, 195, 30), (px + 4, py + 12), (px + 4, py - 8), 3)
                pygame.draw.circle(surface, (255, 220, 90), (px - 4, py - 12), 4)
                pygame.draw.circle(surface, (255, 220, 90), (px + 4, py - 10), 4)

    def draw_structures_and_flora(self, surface):
        # Background Forest Layer
        for px, py in self.forest_pines:
            surface.blit(TEX_PINE, (px, py))

        # Farm Buildings Setups
        surface.blit(TEX_HOUSE, (TILE_SIZE * 13, TILE_SIZE * 2))
        surface.blit(TEX_BARN, (TILE_SIZE * 2, TILE_SIZE * 2))
        surface.blit(TEX_SILO, (TILE_SIZE * 7, TILE_SIZE * 2)) # Replaces briefcase entirely for trading loops!

        # Scattered Natural Haybales Details
        h_color, h_line = (235, 190, 40), (190, 140, 20)
        bale_positions = [(200, 220), (225, 220), (212, 205), (520, 240), (545, 240)]
        for hx, hy in bale_positions:
            pygame.draw.rect(surface, h_color, (hx, hy, 22, 14), border_radius=2)
            pygame.draw.line(surface, h_line, (hx + 6, hy), (hx + 6, hy + 14), 2)
            pygame.draw.line(surface, h_line, (hx + 14, hy), (hx + 14, hy + 14), 2)

        # Render scattering bushes overlay layer
        for tex, bx, by in self.organic_flora:
            surface.blit(tex, (bx, by))

# =========================================================
# MAIN ENGINE CONSOLE CONTROLLER
# =========================================================
def main():
    grid = UltimateFarmGridMap()
    player = RealTimeFarmer(7, 5)
    inventory = {"Seeds": 5, "Basket": 0, "Barn_Storage": 0, "Coins": 0}

    weather_particles = [EnvironmentWeatherParticle() for _ in range(25)]

    animals = [
        HighFidelityAnimal("COW", 600, 280), HighFidelityAnimal("COW", 760, 500),
        HighFidelityAnimal("CHICKEN", 520, 440), HighFidelityAnimal("CHICKEN", 640, 260),
        HighFidelityAnimal("CHICKEN", 850, 360), HighFidelityAnimal("CHICKEN", 690, 580)
    ]

    tutorial_step = 0
    prompts = [
        "WELCOME! Move down using Arrow Keys into the golden tilled tilled soil blocks.",
        "Excellent! Stand directly over an empty brown field tile and press [P] to plant seeds!",
        "Seeds planted! Stand back and wait a few moments for the grain stalks to mature fully.",
        "Perfect crop growth! Stand on top of your mature golden wheat and press [H] to harvest them!",
        "Wheat collected into active basket! Walk directly to the Red Barn front doors to safely store it.",
        "Stock safely packed inside storage! Step right up onto the Crimson Feed Silo at (7,2) to trade for Gold!",
        "CONGRATULATIONS! You mastered the underlying farming engine loop successfully!"
    ]

    # Premium Radial Ambient Light Mask filter setup
    vignette = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    for r in range(SCREEN_WIDTH // 2, SCREEN_WIDTH, 24):
        alpha = int((r - SCREEN_WIDTH // 2) / (SCREEN_WIDTH // 2) * 60)
        pygame.draw.circle(vignette, (10, 25, 5, min(alpha, 80)), (SCREEN_WIDTH//2, SCREEN_HEIGHT//2), r, 26)

    while True:
        ticker_msg = prompts[tutorial_step]
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:    player.move(-1, 0, grid.matrix)
                elif event.key == pygame.K_RIGHT:  player.move(1, 0, grid.matrix)
                elif event.key == pygame.K_UP:     player.move(0, -1, grid.matrix)
                elif event.key == pygame.K_DOWN:   player.move(0, 1, grid.matrix)

                elif event.key == pygame.K_p:
                    p_pos = (player.tx, player.ty)
                    if grid.matrix[player.ty][player.tx] == 2 and p_pos not in grid.crop_progress:
                        if inventory["Seeds"] > 0 and player.energy >= 10:
                            grid.crop_progress[p_pos] = 0
                            inventory["Seeds"] -= 1
                            player.energy = max(0.0, player.energy - 5.0)
                            player.gain_exp(20)
                            if tutorial_step == 1: tutorial_step = 2

                elif event.key == pygame.K_h:
                    p_pos = (player.tx, player.ty)
                    if p_pos in grid.crop_progress and grid.crop_progress[p_pos] >= 100:
                        if player.energy >= 12:
                            del grid.crop_progress[p_pos]
                            inventory["Basket"] += 1 
                            player.energy = max(0.0, player.energy - 8.0)
                            player.gain_exp(40)
                            if tutorial_step == 3: tutorial_step = 4

        if tutorial_step == 0 and grid.matrix[player.ty][player.tx] == 2:
            tutorial_step = 1

        if tutorial_step == 2:
            all_matured = len(grid.crop_progress) > 0 and all(v >= 100 for v in grid.crop_progress.values())
            if all_matured: tutorial_step = 3

        # Barn door cargo unloading system mechanics
        if 2 <= player.tx <= 4 and 3 <= player.ty <= 5 and inventory["Basket"] > 0:
            inventory["Barn_Storage"] += inventory["Basket"]
            inventory["Basket"] = 0
            player.gain_exp(35)
            if tutorial_step == 4: tutorial_step = 5

        # Premium Grain Silo Interaction (Coordinates x=7, y=2/3)
        if 7 <= player.tx <= 8 and 2 <= player.ty <= 4 and inventory["Barn_Storage"] > 0:
            payout = inventory["Barn_Storage"] * 50
            inventory["Coins"] += payout
            inventory["Barn_Storage"] = 0
            player.gain_exp(75)
            if tutorial_step == 5: tutorial_step = 6

        player.update()
        for p in weather_particles: p.update()
        for animal in animals: animal.update()

        # Dynamic plant node acceleration calculation loop
        grow_speed = 1.7 if tutorial_step == 2 else 0.55
        for pos in grid.crop_progress:
            if grid.crop_progress[pos] < 100:
                grid.crop_progress[pos] = min(100, grid.crop_progress[pos] + grow_speed)

        # Drawing Routine Render Layers
        screen.fill(COLOR_BLACK)
        grid.draw_pasture_floor(screen)
        
        # Waypoint Navigation Highlight Guides
        pulse_alpha = int(110 + math.sin(pygame.time.get_ticks() * 0.009) * 45)
        glow_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        if tutorial_step in [0, 1]:
            glow_surf.fill((241, 196, 15, pulse_alpha // 2))
            screen.blit(glow_surf, (2 * TILE_SIZE, 9 * TILE_SIZE))
        elif tutorial_step == 4:
            big_glow = pygame.Surface((TILE_SIZE * 3, TILE_SIZE), pygame.SRCALPHA)
            big_glow.fill((52, 152, 219, pulse_alpha // 2))
            screen.blit(big_glow, (2 * TILE_SIZE, 4 * TILE_SIZE))
        elif tutorial_step == 5:
            big_glow = pygame.Surface((TILE_SIZE * 2, TILE_SIZE * 2), pygame.SRCALPHA)
            big_glow.fill((46, 204, 113, pulse_alpha // 2))
            screen.blit(big_glow, (7 * TILE_SIZE, 2 * TILE_SIZE))

        # Y-Sorted Entity Depth Processing Matrix
        grid.draw_structures_and_flora(screen)
        for animal in animals: animal.draw(screen)
        player.draw(screen)

        # Environmental FX filters
        for p in weather_particles: p.draw(screen)
        screen.blit(vignette, (0, 0))

        # --- HEADS UP HUD INTERFACE DISPLAY LAYER ---
        pygame.draw.rect(screen, COLOR_UI_BAR, (0, 0, SCREEN_WIDTH, 48))
        
        # Energy status bar
        pygame.draw.rect(screen, COLOR_BLACK, (20, 16, 120, 16), border_radius=3)
        pygame.draw.rect(screen, COLOR_ENERGY, (22, 18, int(player.energy * 1.16), 12), border_radius=1)
        screen.blit(font.render(f"ENERGY: {int(player.energy)}%", True, COLOR_WHITE), (30, 17))

        # Experience advancement bar
        exp_percent = min(1.0, player.exp / max(1, player.exp_needed))
        pygame.draw.rect(screen, COLOR_BLACK, (160, 16, 140, 16), border_radius=3)
        pygame.draw.rect(screen, COLOR_EXP, (162, 18, int(exp_percent * 136), 12), border_radius=1)
        screen.blit(font.render(f"LVL {player.level} ({player.exp}/{player.exp_needed})", True, COLOR_WHITE), (170, 17))

        # Balance trackers
        inv_text = f"Basket: {inventory['Basket']}  |  Silo Stock: {inventory['Barn_Storage']}  |  Wallet: {inventory['Coins']} Gold"
        screen.blit(font_large.render(inv_text, True, (241, 196, 15)), (480, 14))

        # Bottom Command Console Strip
        pygame.draw.rect(screen, COLOR_WHITE, (10, SCREEN_HEIGHT - 45, SCREEN_WIDTH - 20, 35), border_radius=4)
        screen.blit(font.render(f">> DIRECTIVE: {ticker_msg}", True, COLOR_BLACK), (25, SCREEN_HEIGHT - 33))

        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__":
    main()