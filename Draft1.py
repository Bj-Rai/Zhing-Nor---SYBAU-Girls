import pygame
import sys
import math
import random

# ==========================================
# ADVANCED PRE-CACHED GRAPHICS TEXTURE ENGINE
# ==========================================
class RealisticTextureEngine:
    @staticmethod
    def create_grass_texture(size):
        surf = pygame.Surface((size, size))
        surf.fill((40, 160, 60)) 
        for _ in range(size * size // 12): 
            gx = random.randint(0, size - 1)
            gy = random.randint(0, size - 1)
            g_color = (random.randint(25, 65), random.randint(145, 195), random.randint(35, 85))
            pygame.draw.line(surf, g_color, (gx, gy), (gx + random.randint(-1, 1), gy - random.randint(2, 6)))
        return surf

    @staticmethod
    def create_tilled_soil_texture(size):
        surf = pygame.Surface((size, size))
        surf.fill((100, 70, 45)) 
        for _ in range(size * size // 8):
            gx = random.randint(0, size - 1)
            gy = random.randint(0, size - 1)
            d_color = (random.randint(60, 110), random.randint(45, 80), random.randint(25, 60))
            surf.set_at((gx, gy), d_color)
        for y in range(0, size, 8):
            pygame.draw.line(surf, (70, 50, 35), (0, y), (size, y + 1), 2)
        return surf

    @staticmethod
    def create_barn_wall_texture(size):
        surf = pygame.Surface((size, size))
        surf.fill((150, 20, 25)) 
        for x in range(0, size, 6):
            pygame.draw.line(surf, (95, 10, 12), (x, 0), (x, size), 2)
        for _ in range(20):
            rx = random.randint(0, size - 1)
            ry = random.randint(0, size - 1)
            surf.set_at((rx, ry), (110, 10, 15))
        return surf

    @staticmethod
    def create_roof_texture(size, wall_base):
        surf = wall_base.copy()
        pygame.draw.polygon(surf, (125, 135, 145), [(0, size), (size, 0), (size, size)])
        for step in range(0, size, 6):
            pygame.draw.line(surf, (85, 95, 105), (step, size), (step + 10, 0), 2)
        pygame.draw.line(surf, (210, 215, 220), (0, size), (size, 0), 3) 
        return surf

    @staticmethod
    def create_window_texture(size, wall_base):
        surf = wall_base.copy()
        win_rect = pygame.Rect(8, 6, size - 16, size - 6)
        pygame.draw.rect(surf, (30, 35, 45), win_rect, border_radius=4) 
        pygame.draw.rect(surf, (230, 225, 210), win_rect, 3, border_radius=4) 
        # Fixed lines below:
        pygame.draw.line(surf, (230, 225, 210), (win_rect.centerx, win_rect.top), (win_rect.centerx, win_rect.bottom), 2) 
        pygame.draw.line(surf, (230, 225, 210), (win_rect.left, win_rect.centery), (win_rect.right, win_rect.centery), 2)
        return surf
        pygame.draw.line(surf, (230, 225, 210), win_rect.left, win_rect.centery, win_rect.right, win_rect.centery, 2)
        return surf

    @staticmethod
    def create_door_texture(size, side="left"):
        surf = pygame.Surface((size, size))
        surf.fill((100, 65, 40))
        for px in range(0, size, 6):
            pygame.draw.line(surf, (65, 40, 25), (px, 0), (px, size), 1)
        pygame.draw.rect(surf, (55, 60, 65), (0, 0, size, size), 2)
        if side == "left":
            pygame.draw.line(surf, (125, 85, 55), (0, 0), (size, size), 4)
        else:
            pygame.draw.line(surf, (125, 85, 55), (size, 0), (0, size), 4)
        pygame.draw.rect(surf, (20, 20, 20), (size // 2 - 2, size - 12, 5, 12), border_radius=1)
        return surf

    @staticmethod
    def create_bin_texture(size, grass_base):
        surf = grass_base.copy()
        pygame.draw.rect(surf, (120, 80, 48), (4, 4, size - 8, size - 8), border_radius=3)
        pygame.draw.rect(surf, (70, 45, 25), (4, 4, size - 8, size - 8), 2, border_radius=3)
        pygame.draw.rect(surf, (90, 95, 100), (6, 6, 8, 8))
        pygame.draw.rect(surf, (90, 95, 100), (size - 14, 6, 8, 8))
        pygame.draw.rect(surf, (220, 200, 160), (12, size - 16, 24, 10))
        return surf

# --- Engine Configuration ---
SCREEN_WIDTH = 960
SCREEN_HEIGHT = 720
FPS = 60
TILE_SIZE = 48 

# --- Color Palette ---
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_ENERGY_BAR = (241, 196, 15)  
COLOR_HEALTH_BAR = (231, 76, 60)   
COLOR_INV_DARK = (44, 62, 80)      

# --- Initialize Framework & Load Baked Asset Textures ---
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("AgriQuest Simulator - Error Free Stable Build")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Courier New", 14, bold=True)
font_large = pygame.font.SysFont("Courier New", 18, bold=True)

TEXTURES = RealisticTextureEngine()
TEX_GRASS = TEXTURES.create_grass_texture(TILE_SIZE)
TEX_SOIL = TEXTURES.create_tilled_soil_texture(TILE_SIZE)
TEX_BARN_RED = TEXTURES.create_barn_wall_texture(TILE_SIZE)
TEX_BARN_ROOF = TEXTURES.create_roof_texture(TILE_SIZE, TEX_BARN_RED)
TEX_BARN_WIN = TEXTURES.create_window_texture(TILE_SIZE, TEX_BARN_RED)
TEX_DOOR_L = TEXTURES.create_door_texture(TILE_SIZE, "left")
TEX_DOOR_R = TEXTURES.create_door_texture(TILE_SIZE, "right")
TEX_BIN = TEXTURES.create_bin_texture(TILE_SIZE, TEX_GRASS)

# =========================================================
# SYSTEM AGENT (PLAYER)
# =========================================================
class FarmerPlayer:
    def __init__(self, tile_x, tile_y):
        self.tile_x = tile_x
        self.tile_y = tile_y
        self.x = tile_x * TILE_SIZE
        self.y = tile_y * TILE_SIZE
        self.speed = 4 

        self.max_hp = 100
        self.hp = 100
        self.max_energy = 100
        self.energy = 100

        self.state = "IDLE" 
        self.facing = "DOWN" 
        self.anim_frame = 0
        self.state_timer = 0
        
    def move(self, dx, dy, collision_grid):
        if self.state in ["PLANTING", "HARVESTING", "STORING", "SHIPPING"]:
            return

        target_x = self.tile_x + dx
        target_y = self.tile_y + dy

        if dx > 0: self.facing = "RIGHT"
        elif dx < 0: self.facing = "LEFT"
        elif dy > 0: self.facing = "DOWN"
        elif dy < 0: self.facing = "UP"

        if 0 <= target_x < (SCREEN_WIDTH // TILE_SIZE) and 0 <= target_y < (SCREEN_HEIGHT // TILE_SIZE):
            if collision_grid[target_y][target_x] not in [1, 3, 4, 5, 6, 7, 8]:
                if dx != 0 or dy != 0:
                    self.state = "WALKING"
                    self.tile_x = target_x
                    self.tile_y = target_y
                    self.energy = max(0, self.energy - 0.1)

    def update_physics(self):
        target_pixel_x = self.tile_x * TILE_SIZE
        target_pixel_y = self.tile_y * TILE_SIZE

        if self.x < target_pixel_x: self.x = min(self.x + self.speed, target_pixel_x)
        elif self.x > target_pixel_x: self.x = max(self.x - self.speed, target_pixel_x)

        if self.y < target_pixel_y: self.y = min(self.y + self.speed, target_pixel_y)
        elif self.y > target_pixel_y: self.y = max(self.y - self.speed, target_pixel_y)

        if self.x == target_pixel_x and self.y == target_pixel_y and self.state == "WALKING":
            self.state = "IDLE"

        self.anim_frame += 1
        if self.state_timer > 0:
            self.state_timer -= 1
            if self.state_timer == 0:
                self.state = "IDLE" 

    def start_action(self, action_type, cost=10):
        if self.energy >= cost:
            self.state = action_type
            self.state_timer = 25 
            self.energy -= cost
            return True
        return False

    def draw(self, surface):
        center_x = int(self.x + TILE_SIZE // 2)
        base_y = int(self.y + 2)
        
        bob = 0
        leg_swing = 0
        if self.state == "WALKING":
            bob = abs(math.sin(self.anim_frame * 0.4)) * 5
            leg_swing = math.sin(self.anim_frame * 0.4) * 6
        elif self.state in ["PLANTING", "HARVESTING"]:
            bob = 4 

        # Legs
        leg_y = base_y + 32
        boot_color = (60, 45, 35)
        pants_color = (35, 75, 120)
        
        if self.facing in ["UP", "DOWN", "RIGHT"]:
            pygame.draw.rect(surface, pants_color, (center_x - 6, leg_y - int(bob/2), 4, 9))
            pygame.draw.rect(surface, boot_color, (center_x - 7 + int(leg_swing/2), leg_y + 7 - int(bob/2), 5, 4))
            pygame.draw.rect(surface, pants_color, (center_x + 2, leg_y - int(bob/2), 4, 9))
            pygame.draw.rect(surface, boot_color, (center_x + 1 - int(leg_swing/2), leg_y + 7 - int(bob/2), 5, 4))
        else: 
            pygame.draw.rect(surface, pants_color, (center_x - 4, leg_y - int(bob/2), 8, 9))
            pygame.draw.rect(surface, boot_color, (center_x - 6 + int(leg_swing), leg_y + 7 - int(bob/2), 6, 4))

        # Torso
        body_y = base_y + 16 - int(bob)
        pygame.draw.rect(surface, pants_color, (center_x - 7, body_y, 14, 16), border_radius=2) 
        pygame.draw.rect(surface, (215, 90, 75), (center_x - 6, body_y + 1, 12, 5)) 
        pygame.draw.circle(surface, (240, 195, 15), (center_x - 4, body_y + 6), 1)
        pygame.draw.circle(surface, (240, 195, 15), (center_x + 4, body_y + 6), 1)

        shirt_color = (210, 75, 60)
        skin_color = (253, 235, 208)
        
        if self.state in ["PLANTING", "HARVESTING", "STORING"]: 
            pygame.draw.line(surface, shirt_color, (center_x - 7, body_y + 4), (center_x - 10, body_y + 16), 3)
            pygame.draw.line(surface, skin_color, (center_x - 10, body_y + 16), (center_x - 10, body_y + 19), 2)
        else: 
            pygame.draw.line(surface, shirt_color, (center_x - 8, body_y + 4), (center_x - 11, body_y + 12 + int(leg_swing/2)), 3)
            pygame.draw.line(surface, shirt_color, (center_x + 8, body_y + 4), (center_x + 11, body_y + 12 - int(leg_swing/2)), 3)

        # Living Face Implementation
        head_y = base_y + 8 - int(bob)
        pygame.draw.circle(surface, skin_color, (center_x, head_y + 2), 7) 
        pygame.draw.circle(surface, (80, 50, 30), (center_x, head_y - 2), 7, width=2) 
        
        eye_color = (40, 30, 20)
        if self.facing == "DOWN":
            pygame.draw.circle(surface, COLOR_WHITE, (center_x - 3, head_y + 1), 2)
            pygame.draw.circle(surface, COLOR_WHITE, (center_x + 3, head_y + 1), 2)
            pygame.draw.circle(surface, eye_color, (center_x - 3, head_y + 1), 1)
            pygame.draw.circle(surface, eye_color, (center_x + 3, head_y + 1), 1)
            pygame.draw.line(surface, (230, 100, 90), (center_x - 2, head_y + 5), (center_x + 2, head_y + 5), 1) 
        elif self.facing == "RIGHT":
            pygame.draw.circle(surface, COLOR_WHITE, (center_x + 3, head_y + 1), 2)
            pygame.draw.circle(surface, eye_color, (center_x + 4, head_y + 1), 1)
        elif self.facing == "LEFT":
            pygame.draw.circle(surface, COLOR_WHITE, (center_x - 3, head_y + 1), 2)
            pygame.draw.circle(surface, eye_color, (center_x - 4, head_y + 1), 1)
        elif self.facing == "UP":
            pygame.draw.circle(surface, (80, 50, 30), (center_x, head_y + 2), 6) 

        # Straw Hat
        pygame.draw.ellipse(surface, (235, 195, 120), (center_x - 18, head_y - 4, 36, 9))
        pygame.draw.ellipse(surface, COLOR_BLACK, (center_x - 18, head_y - 4, 36, 9), 1)
        for d in range(1, 3): 
            pygame.draw.ellipse(surface, (195, 155, 85), (center_x - 18 + d*3, head_y - 4 + d, 36 - d*6, 9 - d*2), 1)
        pygame.draw.rect(surface, (205, 165, 95), (center_x - 8, head_y - 11, 16, 8), border_radius=2)
        pygame.draw.rect(surface, COLOR_BLACK, (center_x - 8, head_y - 11, 16, 8), 1)

# =========================================================
# MAP SIMULATION MAP GRID
# =========================================================
class EnvironmentGrid:
    def __init__(self):
        self.cols = SCREEN_WIDTH // TILE_SIZE
        self.rows = SCREEN_HEIGHT // TILE_SIZE
        
        # 0=Grass, 2=Soil, 1=Red Wall, 3=Roof, 4=Window, 5=DoorL, 6=DoorR, 8=Shipping Bin
        self.matrix = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
        self.crop_states = {} 
        self.crop_types = {} 

        # Build Barn Matrix Footprint mapping layout
        for r in range(1, 6):
            for c in range(14, 19):
                if r == 1: self.matrix[r][c] = 3  
                elif r == 2 and c == 16: self.matrix[r][c] = 4  
                elif r in [4, 5] and c == 16: self.matrix[r][c] = 5  
                elif r in [4, 5] and c == 17: self.matrix[r][c] = 6  
                else: self.matrix[r][c] = 1  

        # Place Selling Bin adjacent
        self.matrix[5][13] = 8

        # Fertile Dirt Zones
        for r in range(3, 7):
            for c in range(2, 6): self.matrix[r][c] = 2
            for c in range(8, 12): self.matrix[r][c] = 2

    def draw(self, surface):
        for r in range(self.rows):
            for c in range(self.cols):
                rect = pygame.Rect(c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                tile_type = self.matrix[r][c]
                
                if tile_type == 0: surface.blit(TEX_GRASS, rect)
                elif tile_type == 2: surface.blit(TEX_SOIL, rect)
                elif tile_type == 1: surface.blit(TEX_BARN_RED, rect)
                elif tile_type == 3: surface.blit(TEX_BARN_ROOF, rect)
                elif tile_type == 4: surface.blit(TEX_BARN_WIN, rect)
                elif tile_type == 5: surface.blit(TEX_DOOR_L, rect)
                elif tile_type == 6: surface.blit(TEX_DOOR_R, rect)
                elif tile_type == 8: surface.blit(TEX_BIN, rect)

        # Render Growing Vegetation profiles
        for pos in self.crop_states:
            c, r = pos
            progress = self.crop_states[pos]
            v_type = self.crop_types.get(pos, "Carrots")
            rect = pygame.Rect(c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            cx, cy = rect.centerx, rect.centery
            
            if progress < 45:
                leaf_num = 3 if progress < 20 else 5
                size_scale = int(2 + (progress / 45 * 6))
                for i in range(leaf_num):
                    ang = i * (360 / leaf_num)
                    lx = cx + int(math.cos(math.radians(ang)) * size_scale)
                    ly = cy + int(math.sin(math.radians(ang)) * size_scale)
                    pygame.draw.circle(surface, (46, 204, 113), (lx, ly), int(size_scale * 0.7)) 
                pygame.draw.circle(surface, (39, 174, 96), (cx, cy), int(size_scale * 0.4)) 
            elif progress < 85:
                foliage_radius = int(8 + (progress / 85 * 7))
                for leaf in range(8):
                    ang = leaf * 45 + (progress * 0.5)
                    lx = cx + int(math.cos(math.radians(ang)) * (foliage_radius * 0.5))
                    ly = cy + int(math.sin(math.radians(ang)) * (foliage_radius * 0.5))
                    pygame.draw.circle(surface, (34, 139, 34), (lx, ly), int(foliage_radius * 0.5)) 
                pygame.draw.circle(surface, (40, 180, 99), (cx, cy), int(foliage_radius * 0.6))
            else:
                if v_type == "Carrots":
                    pygame.draw.polygon(surface, (230, 126, 34), [(cx - 8, cy + 2), (cx + 8, cy + 2), (cx, cy + 18)])
                    pygame.draw.polygon(surface, (211, 84, 0), [(cx - 8, cy + 2), (cx, cy + 2), (cx, cy + 18)]) 
                    pygame.draw.line(surface, (245, 176, 116), (cx - 3, cy + 4), (cx - 1, cy + 12), 2)
                    for f in range(4):
                        pygame.draw.line(surface, (39, 174, 96), (cx, cy + 2), (cx - 12 + f * 8, cy - 10), 2)
                        pygame.draw.circle(surface, (46, 204, 113), (cx - 12 + f * 8, cy - 10), 3)
                elif v_type == "Cabbages":
                    cab_rad = 14
                    pygame.draw.circle(surface, (40, 150, 85), (cx, cy), cab_rad) 
                    for w in range(4):
                        ang = w * 90
                        wx = cx + int(math.cos(math.radians(ang)) * 5)
                        wy = cy + int(math.sin(math.radians(ang)) * 5)
                        pygame.draw.circle(surface, (88, 214, 141), (wx, wy), 9, width=2) 
                    pygame.draw.circle(surface, (171, 235, 198), (cx - 3, cy - 3), 6)
                    pygame.draw.circle(surface, COLOR_WHITE, (cx - 4, cy - 4), 2) 

    def tick_growth(self, acceleration_mode=False):
        rate = 1.6 if acceleration_mode else 0.25 
        for pos in self.crop_states:
            if self.crop_states[pos] < 100:
                self.crop_states[pos] = min(100, self.crop_states[pos] + rate)

# =========================================================
# MAIN PIPELINE PIPELINE RUNNER
# =========================================================
def run_game():
    grid = EnvironmentGrid()
    farmer = FarmerPlayer(13, 8) 
    inventory = {"Seeds": 6, "Basket": 0, "Barn_Storage": 0, "Cash": 0}
    
    tutorial_step = 0 
    ui_msg = "TUTORIAL: Walk left to the brown tilled soil plots using Arrow Keys!"

    while True:
        dt = clock.tick(FPS)
        current_pos = (farmer.tile_x, farmer.tile_y)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:   farmer.move(-1, 0, grid.matrix)
                elif event.key == pygame.K_RIGHT: farmer.move(1, 0, grid.matrix)
                elif event.key == pygame.K_UP:    farmer.move(0, -1, grid.matrix)
                elif event.key == pygame.K_DOWN:  farmer.move(0, 1, grid.matrix)

                if tutorial_step == 0 and grid.matrix[farmer.tile_y][farmer.tile_x] == 2:
                    tutorial_step = 1
                    ui_msg = "EXCELLENT! Press [P] to plant a crop seed into the soil."

                if event.key == pygame.K_p:
                    if grid.matrix[farmer.tile_y][farmer.tile_x] == 2 and current_pos not in grid.crop_states:
                        if inventory["Seeds"] > 0:
                            if farmer.start_action("PLANTING", cost=15):
                                grid.crop_states[current_pos] = 0
                                grid.crop_types[current_pos] = "Cabbages" if random.random() > 0.5 else "Carrots"
                                inventory["Seeds"] -= 1
                                if tutorial_step == 1:
                                    tutorial_step = 2
                                    ui_msg = "PLANTED! Watch the biological sprouts grow!"

                elif event.key == pygame.K_h:
                    if current_pos in grid.crop_states and grid.crop_states[current_pos] >= 100:
                        if farmer.start_action("HARVESTING", cost=20):
                            del grid.crop_states[current_pos]
                            if current_pos in grid.crop_types: del grid.crop_types[current_pos]
                            inventory["Basket"] += 1
                            if tutorial_step == 3:
                                tutorial_step = 4
                                ui_msg = "HARVESTED! Walk up to the Red Barn Doors and press [S] to STORE them safely!"

                elif event.key == pygame.K_s:
                    near_barn = False
                    near_bin = False
                    for rx in [-1, 0, 1]:
                        for cy in [-1, 0, 1]:
                            cx = max(0, min(farmer.tile_x + rx, grid.cols - 1))
                            cy_check = max(0, min(farmer.tile_y + cy, grid.rows - 1))
                            if grid.matrix[cy_check][cx] in [1, 3, 4, 5, 6, 7]: near_barn = True
                            if grid.matrix[cy_check][cx] == 8: near_bin = True
                    
                    if near_barn and inventory["Basket"] > 0:
                        if farmer.start_action("STORING", cost=5):
                            inventory["Barn_Storage"] += inventory["Basket"]
                            inventory["Basket"] = 0
                            farmer.energy = min(100, farmer.energy + 20)
                            if tutorial_step == 4:
                                tutorial_step = 5
                                ui_msg = "STORED IN BARN! Step down to the Shipping Bin (left of doors) and press [S] to sell them!"

                    elif near_bin and inventory["Barn_Storage"] > 0:
                        if farmer.start_action("SHIPPING", cost=5):
                            shipped_units = inventory["Barn_Storage"]
                            inventory["Barn_Storage"] = 0
                            inventory["Cash"] += shipped_units * 40
                            if tutorial_step == 5:
                                tutorial_step = 6
                                ui_msg = "SUCCESS! You used the barn storage loop! Sandbox mode fully unlocked!"

        farmer.update_physics()
        grid.tick_growth(acceleration_mode=(tutorial_step == 2))

        if tutorial_step == 2:
            for pos in grid.crop_states:
                if grid.crop_states[pos] >= 100:
                    tutorial_step = 3
                    ui_msg = "FULLY GROWN! Stand over them and press [H] to harvest into your basket!"

        if farmer.state == "IDLE":
            farmer.energy = min(100, farmer.energy + 0.06)

        screen.fill(COLOR_BLACK)
        grid.draw(screen)
        
        # Glow Targets for Tutorial Guidance
        if tutorial_step == 0:
            p_glow = int(110 + math.sin(pygame.time.get_ticks() * 0.008) * 25)
            h_surf = pygame.Surface((TILE_SIZE*4, TILE_SIZE*4))
            h_surf.fill((52, 152, 219)) 
            h_surf.set_alpha(p_glow // 3)
            screen.blit(h_surf, (TILE_SIZE*2, TILE_SIZE*3))
        elif tutorial_step == 4:
            p_glow = int(110 + math.sin(pygame.time.get_ticks() * 0.008) * 25)
            h_surf = pygame.Surface((TILE_SIZE*2, TILE_SIZE*2))
            h_surf.fill((230, 126, 34)) 
            h_surf.set_alpha(p_glow // 3)
            screen.blit(h_surf, (TILE_SIZE*16, TILE_SIZE*4))
        elif tutorial_step == 5:
            p_glow = int(110 + math.sin(pygame.time.get_ticks() * 0.008) * 25)
            h_surf = pygame.Surface((TILE_SIZE, TILE_SIZE))
            h_surf.fill((46, 204, 113)) 
            h_surf.set_alpha(p_glow // 2)
            screen.blit(h_surf, (TILE_SIZE*13, TILE_SIZE*5))

        farmer.draw(screen)

        # UI Header Panel
        pygame.draw.rect(screen, COLOR_INV_DARK, (0, 0, SCREEN_WIDTH, 40))
        screen.blit(font_large.render("OBJECTIVE:", True, COLOR_ENERGY_BAR), (20, 10))
        
        tutorial_prompts = [
            "Use your Keyboard Arrow keys to step left onto the fertile soil plots.",
            "Stand inside the dark brown tilled earth and press [P] to plant vegetable seeds.",
            "Observe the multi-tiered leaf structures scaling up into fully realistic forms.",
            "Walk directly on top of the realistic, mature crops and press [H] to harvest.",
            "Walk over to the Red Barn Doors and press [S] to STORE crops inside!",
            "Walk to the wooden Shipping Bin box and press [S] to ship out your barn stocks!",
            "Sandbox mode active! Control your full-body farmer, manage your storage barn, and expand!"
        ]
        screen.blit(font_large.render(tutorial_prompts[tutorial_step], True, COLOR_WHITE), (120, 10))

        # Vital Bars
        pygame.draw.rect(screen, COLOR_BLACK, (20, 55, 160, 18), border_radius=3)
        pygame.draw.rect(screen, COLOR_HEALTH_BAR, (22, 57, int(farmer.hp * 1.56), 14), border_radius=2)
        screen.blit(font.render(f"HP: {int(farmer.hp)}%", True, COLOR_WHITE), (25, 57))

        pygame.draw.rect(screen, COLOR_BLACK, (20, 77, 160, 18), border_radius=3)
        pygame.draw.rect(screen, COLOR_ENERGY_BAR, (22, 77, int(farmer.energy * 1.56), 14), border_radius=2)
        screen.blit(font.render(f"ENERGY: {int(farmer.energy)}%", True, COLOR_WHITE), (25, 77))

        # Stats Overlay Box
        inv_box = pygame.Rect(700, 50, 250, 100)
        pygame.draw.rect(screen, COLOR_INV_DARK, inv_box, border_radius=5)
        pygame.draw.rect(screen, COLOR_BLACK, inv_box, 2, border_radius=5)
        screen.blit(font.render(f"🎒 FARM MANAGMENT HUD", True, (234, 209, 220)), (710, 56))
        screen.blit(font.render(f"Seed Packets:    {inventory['Seeds']}", True, COLOR_WHITE), (710, 76))
        screen.blit(font.render(f"Hand Basket:     {inventory['Basket']} Crops", True, COLOR_WHITE), (710, 92))
        screen.blit(font.render(f"🌾 BARN STORAGE: {inventory['Barn_Storage']} Crops", True, (241, 196, 15)), (710, 108))
        screen.blit(font.render(f"Total Cash:      Nu.{inventory['Cash']}", True, (46, 204, 113)), (710, 126))

        # Ticker Message bar
        msg_box = pygame.Rect(10, SCREEN_HEIGHT - 45, SCREEN_WIDTH - 20, 35)
        pygame.draw.rect(screen, COLOR_WHITE, msg_box, border_radius=6)
        pygame.draw.rect(screen, COLOR_BLACK, msg_box, 2, border_radius=6)
        screen.blit(font.render(f">> FEEDBACK SYSTEM: {ui_msg}", True, COLOR_BLACK), (20, SCREEN_HEIGHT - 36))

        pygame.display.flip()

if __name__ == "__main__":
    run_game()