import pygame
import random

# Initialize pygame
pygame.init()

# Screen setup
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Brain Trek")

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (34, 139, 34)
RED = (200, 0, 0)

# Clock
clock = pygame.time.Clock()
FPS = 60

# Player setup
player_size = 40
player_x = 100
player_y = 100
player_speed = 5

# Game variables
lives = 3
gold = 0
font = pygame.font.SysFont(None, 30)

# Enemy (basic)
enemy_size = 40
enemy_x = random.randint(200, 700)
enemy_y = random.randint(100, 500)
enemy_speed = 2


def draw_player(x, y):
    pygame.draw.rect(screen, GREEN, (x, y, player_size, player_size))


def draw_enemy(x, y):
    pygame.draw.rect(screen, RED, (x, y, enemy_size, enemy_size))


def show_status():
    text = font.render(f"Lives: {lives}   Gold: {gold}", True, BLACK)
    screen.blit(text, (10, 10))


def check_collision(px, py, ex, ey):
    return (
        px < ex + enemy_size and
        px + player_size > ex and
        py < ey + enemy_size and
        py + player_size > ey
    )


# Game loop
running = True
while running:
    screen.fill(WHITE)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Controls
    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]:
        player_x -= player_speed
    if keys[pygame.K_RIGHT]:
        player_x += player_speed
    if keys[pygame.K_UP]:
        player_y -= player_speed
    if keys[pygame.K_DOWN]:
        player_y += player_speed

    # Boundary checking
    if player_x < 0:
        player_x = 0
    elif player_x > WIDTH - player_size:
        player_x = WIDTH - player_size
    if player_y < 0:
        player_y = 0
    elif player_y > HEIGHT - player_size:
        player_y = HEIGHT - player_size

    # Enemy movement (simple chasing)
    if enemy_x < player_x:
        enemy_x += enemy_speed
    if enemy_x > player_x:
        enemy_x -= enemy_speed
    if enemy_y < player_y:
        enemy_y += enemy_speed
    if enemy_y > player_y:
        enemy_y -= enemy_speed

    # Collision detection
    if check_collision(player_x, player_y, enemy_x, enemy_y):
        lives -= 1
        player_x, player_y = 100, 100  # reset position

    # Game over
    if lives <= 0:
        print("Game Over")
        running = False

    # Draw elements
    draw_player(player_x, player_y)
    draw_enemy(enemy_x, enemy_y)
    show_status()

    pygame.display.update()
    clock.tick(FPS)

pygame.quit()
