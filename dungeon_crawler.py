# -*- coding: utf-8 -*-
"""
A terminal based ray-casting engine.


IMPORTANT:
Make sure the pygame window is focused for input events to be received.

Depending on your terminal font, Renderer.ascii_map may need to be adjusted.

Values stored in textures should range from 0-9.  Values below 5 are
substractive and above 5 are additive.
"""
import types
import pygame
import curses
import numpy as np

GAME = types.SimpleNamespace(running=True)

KEYS = [False]*324

class Player:
    def __init__(self, x_pos=5., y_pos=5., x_dir=1., y_dir=0.,\
                 x_plane=0., y_plane=1.):
        self.x = x_pos
        self.y = y_pos
        self.x_dir = x_dir
        self.y_dir = y_dir
        self.field_of_view = .3 #Somewhere between 0 and 1 is reasonable
        self.x_plane = self.field_of_view * x_plane 
        self.y_plane = self.field_of_view * y_plane
        self.speed = .03
        self.rotate_speed = .008
        self.left = np.array([[np.cos(-self.rotate_speed),\
                               np.sin(-self.rotate_speed)],\
                              [-np.sin(-self.rotate_speed),\
                                np.cos(-self.rotate_speed)]])
        self.right = np.array([[np.cos(self.rotate_speed),\
                                np.sin(self.rotate_speed)],\
                               [-np.sin(self.rotate_speed),\
                                np.cos(self.rotate_speed)]])

    def turn(self, left=True):
        self.x_dir, self.y_dir = np.array([self.x_dir, self.y_dir]) @\
                                 (self.left if left else self.right)
        self.x_plane, self.y_plane = np.array([self.x_plane, self.y_plane]) @\
                                     (self.left if left else self.right)

    def move(self, forward=1, strafe=False):
        def next_pos(coord, direction):
            return coord + forward * direction * self.speed
        next_x_step = next_pos(self.x, self.y_dir) if strafe else\
                      next_pos(self.x, self.x_dir)
        next_y_step = next_pos(self.y, - self.x_dir) if strafe else\
                      next_pos(self.y, self.y_dir)
        if not GAME.world_map[int(next_x_step)][int(self.y)]:
            self.x = next_x_step
        if not GAME.world_map[int(self.x)][int(next_y_step)]:
            self.y = next_y_step

class Renderer:
    def __init__(self, screen, player):
        self.screen = screen
        self.height, self.width = screen.getmaxyx()
        self.player = player
        self.buffer = np.full((self.height, self.width), " ", dtype=str)
        self.ascii_map = dict(enumerate(list(" .',:;cxlokXdO0KN")))
        self.shades = len(self.ascii_map)
        self.max_range = 60
        self.wall_scale = 1.5 #Wall Height
        self.wall_y = 1.8 #Wall vertical placement

    def cast_ray(self, column):
        camera = column / self.height - 1.0
        ray_x = self.player.x
        ray_y = self.player.y
        ray_x_dir = self.player.x_dir + self.player.x_plane * camera
        ray_y_dir = self.player.y_dir + self.player.y_plane * camera
        map_x = int(ray_x)
        map_y = int(ray_y)
        
        def delta(ray_dir):
            try:
                return abs(1 / ray_dir)
            except ZeroDivisionError:
                return float("inf")
        
        delta_x = delta(ray_x_dir)
        delta_y = delta(ray_y_dir)
        
        def step_side(ray_dir, ray, map_, delta):
            if ray_dir < 0:
                return -1, (ray - map_) * delta
            else:
                return 1, (map_ + 1 - ray) * delta
            
        step_x, side_x_dis = step_side(ray_x_dir, ray_x, map_x, delta_x)
        step_y, side_y_dis = step_side(ray_y_dir, ray_y, map_y, delta_y)

        #Distance to wall
        for i in range(self.max_range):
            if side_x_dis < side_y_dis:
                side_x_dis += delta_x
                map_x += step_x
                side = True
            else:
                side_y_dis += delta_y
                map_y += step_y
                side = False
            if GAME.world_map[map_x][map_y]:
                break
            if i == self.max_range - 1:
                return
        #Avoiding euclidean distance, to avoid fish-eye effect.
        if side:
            wall_dis = (map_x - ray_x + (1 - step_x) / 2) / ray_x_dir
        else:
            wall_dis = (map_y - ray_y + (1 - step_y) / 2) / ray_y_dir
        
        try:
            line_height = int(self.height / wall_dis)
        except ZeroDivisionError:
            line_height = float("inf")
        
        #Casting is done, drawing starts
        line_start = int((-line_height * self.wall_scale + self.height) /\
                         self.wall_y)
        line_start = np.clip(line_start, 0, None)
        line_end = int((line_height * self.wall_scale + self.height) /\
                       self.wall_y)
        line_end = np.clip(line_end, None, self.height - 1)
        line_height = line_end - line_start
        #Shading
        shade = int(np.clip(wall_dis, 0, 20))
        shade = (20 - shade) // 2 + (6 if side else 4)
        #Write column to a temporary buffer
        shade_buffer = [shade] * line_height

        #============================================================
        #Texturing -- Safe to comment out this block for fps increase
        texture_num = GAME.world_map[map_x][map_y] - 1
        texture_width, texture_height = GAME.textures[texture_num].shape
        if side:
            wall_x = self.player.y + wall_dis * ray_y_dir
        else:
            wall_x = self.player.x + wall_dis * ray_x_dir
        wall_x -= np.floor(wall_x)
        tex_x = int(wall_x * texture_width)
        if (side and ray_x_dir > 0) or (not side and ray_y_dir < 0):
            tex_x = texture_width - tex_x - 1
        #Add or subtract texture values to shade values
        for i, val in enumerate(shade_buffer):
            tex_y = int(i / line_height * texture_height)
            shade_buffer[i] = np.clip(GAME.textures[texture_num][tex_x][tex_y]\
                                      +val - 5, 0, self.shades - 1)
        #===========================================================
        
        #Convert shade values to ascii and write to screen buffer
        column_buffer = [self.ascii_map[val] for val in shade_buffer]
        column_buffer = np.array(column_buffer, dtype=str)
            
        self.buffer[line_start:line_end, column] = column_buffer

    def update(self):
        #Clear buffer
        self.buffer = np.full((self.height, self.width), " ", dtype=str)
        #Draw floor
        self.buffer[self.height // 2 + 1:, :] = self.ascii_map[1]
        #Draw Columns
        for column in range(self.width-1):
            self.cast_ray(column)

    def render(self):
        for row_num, row in enumerate(self.buffer):
            self.screen.addstr(row_num, 0, ''.join(row[:-1]))
        self.screen.refresh()

def load_map(map_name):
    with open(map_name+".txt", 'r') as a_map:
        world_map = [[int(char) for char in row]\
                      for row in a_map.read().splitlines()]

    return np.array(world_map).T

def load_textures(*texture_names):
    textures = []
    for name in texture_names:
        with open(name+".txt", 'r') as texture:
            pre_load = [[int(char) for char in row]\
                        for row in texture.read().splitlines()]
            textures.append(np.array(pre_load).T)
    return textures

def user_input():
    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                GAME.running = False
            KEYS[event.key] = True
        elif event.type == pygame.KEYUP:
            KEYS[event.key] = False

def move(player):
    if KEYS[pygame.K_LEFT] or KEYS[pygame.K_a]:
        player.turn()
    if KEYS[pygame.K_RIGHT] or KEYS[pygame.K_d]:
        player.turn(False)
    if KEYS[pygame.K_UP] or KEYS[pygame.K_w]:
        player.move()
    if KEYS[pygame.K_DOWN] or KEYS[pygame.K_s]:
        player.move(-1)
    if KEYS[pygame.K_q]:
        player.move(strafe=True)
    if KEYS[pygame.K_e]:
        player.move(-1, True)

def main(screen):
    init_curses(screen)
    init_pygame()
    clock = pygame.time.Clock()
    GAME.world_map = load_map("map1")
    GAME.textures = load_textures("texture1",)
    player = Player()
    renderer = Renderer(screen, player)
    while GAME.running:
        renderer.update()
        renderer.render()
        user_input()
        move(player)
    clock.tick(40)
    pygame.display.quit()
    pygame.quit()

def init_pygame():
    pygame.init()
    pygame.display.set_mode((305, 2))
    pygame.display.set_caption('Focus this window to move.')

def init_curses(screen):
    curses.noecho()
    curses.curs_set(0)
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
    screen.attron(curses.color_pair(1))
    screen.clear()

if __name__ == "__main__":
    curses.wrapper(main)
