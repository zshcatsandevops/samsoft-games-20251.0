# mario_luigi_live_bros.py
# ============================================================================
# MARIO AND LUIGI + LIVE BROS.
# Offline Campaign Edition
# ============================================================================
# A complete single-player Mario & Luigi RPG experience
# Features authentic timing-based combat and Bros. Attacks
# ============================================================================

import pygame as pg
import math
import random
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum

pg.init()
pg.mixer.init()

# ======================== DISPLAY SETTINGS ==================================

DS_W, DS_H = 256, 192
SCALE = 3
WIN_W, WIN_H = DS_W * SCALE, DS_H * 2 * SCALE
FPS = 60
TILE_SIZE = 16

# ======================== COLORS ============================================

ML_RED = pg.Color(228, 59, 68)
ML_GREEN = pg.Color(67, 176, 71)
ML_YELLOW = pg.Color(251, 208, 72)
ML_BLUE = pg.Color(66, 165, 245)
ML_PURPLE = pg.Color(142, 76, 200)
BLACK = pg.Color(0, 0, 0)
WHITE = pg.Color(255, 255, 255)
GRAY = pg.Color(128, 128, 128)

# ======================== GAME DATA =========================================

@dataclass
class Character:
    name: str
    hp: int
    max_hp: int
    bp: int
    max_bp: int
    pow: int
    defense: int
    speed: int
    stache: int
    level: int = 1
    exp: int = 0
    exp_next: int = 10

@dataclass
class Enemy:
    name: str
    hp: int
    max_hp: int
    pow: int
    defense: int
    speed: int
    exp_reward: int
    coin_reward: int
    sprite_color: Optional[pg.Color] = None
    
    def __post_init__(self):
        if self.sprite_color is None:
            self.sprite_color = GRAY

@dataclass
class BrosAttack:
    name: str
    bp_cost: int
    damage: int
    description: str
    button_sequence: List[str]
    timing_windows: List[float]

# Bros. Attacks
BROS_ATTACKS = {
    'bounce_bros': BrosAttack(
        "Bounce Bros", 3, 25,
        "Jump on enemies together!",
        ['A', 'B', 'A', 'B'],
        [0.5, 0.4, 0.3, 0.25]
    ),
    'green_shell': BrosAttack(
        "Green Shell", 4, 30,
        "Kick a shell between bros!",
        ['A', 'A', 'B', 'B', 'A'],
        [0.4, 0.35, 0.3, 0.25, 0.2]
    ),
    'fire_flower': BrosAttack(
        "Fire Flower", 5, 35,
        "Alternate fireballs!",
        ['A', 'B'] * 5,
        [0.3] * 10
    ),
    'copy_flower': BrosAttack(
        "Copy Flower", 8, 50,
        "Multiply and attack!",
        ['A', 'A', 'B', 'B'] * 3,
        [0.25] * 12
    )
}

# ======================== CAMPAIGN CHAPTERS =================================

CAMPAIGN_CHAPTERS = [
    {
        'id': 1,
        'name': "Mushroom Kingdom",
        'description': "The adventure begins!",
        'battles': [
            {'enemies': [Enemy(name="Goomba", hp=20, max_hp=20, pow=5, defense=2, speed=3, exp_reward=5, coin_reward=3, sprite_color=ML_YELLOW)]},
            {'enemies': [Enemy(name="Goomba", hp=20, max_hp=20, pow=5, defense=2, speed=3, exp_reward=5, coin_reward=3, sprite_color=ML_YELLOW),
                        Enemy(name="Goomba", hp=20, max_hp=20, pow=5, defense=2, speed=3, exp_reward=5, coin_reward=3, sprite_color=ML_YELLOW)]},
            {'enemies': [Enemy(name="Koopa", hp=30, max_hp=30, pow=7, defense=4, speed=4, exp_reward=8, coin_reward=5, sprite_color=ML_GREEN)]},
        ],
        'boss': Enemy(name="Bowser Jr.", hp=100, max_hp=100, pow=12, defense=5, speed=5, exp_reward=50, coin_reward=30, sprite_color=ML_RED)
    },
    {
        'id': 2,
        'name': "Beanbean Kingdom",
        'description': "Journey to a new land!",
        'battles': [
            {'enemies': [Enemy(name="Fighter Fly", hp=25, max_hp=25, pow=8, defense=3, speed=6, exp_reward=7, coin_reward=4, sprite_color=ML_BLUE)]},
            {'enemies': [Enemy(name="Beanie", hp=35, max_hp=35, pow=9, defense=4, speed=5, exp_reward=10, coin_reward=6, sprite_color=ML_GREEN),
                        Enemy(name="Beanie", hp=35, max_hp=35, pow=9, defense=4, speed=5, exp_reward=10, coin_reward=6, sprite_color=ML_GREEN)]},
        ],
        'boss': Enemy(name="Cackletta", hp=150, max_hp=150, pow=15, defense=6, speed=6, exp_reward=80, coin_reward=50, sprite_color=ML_PURPLE)
    },
    {
        'id': 3,
        'name': "Pi'illo Island",
        'description': "Enter the dream world!",
        'battles': [
            {'enemies': [Enemy(name="Nightmare", hp=40, max_hp=40, pow=12, defense=5, speed=7, exp_reward=12, coin_reward=8, sprite_color=ML_PURPLE)]},
            {'enemies': [Enemy(name="Dream Enemy", hp=45, max_hp=45, pow=14, defense=6, speed=8, exp_reward=15, coin_reward=10, sprite_color=ML_BLUE)]},
        ],
        'boss': Enemy(name="Antasma", hp=200, max_hp=200, pow=18, defense=7, speed=7, exp_reward=120, coin_reward=80, sprite_color=BLACK)
    },
    {
        'id': 4,
        'name': "Dark Bowser Castle",
        'description': "The final battle!",
        'battles': [
            {'enemies': [Enemy(name="Dark Minion", hp=50, max_hp=50, pow=15, defense=7, speed=8, exp_reward=18, coin_reward=12, sprite_color=BLACK)]},
            {'enemies': [Enemy(name="Fawful", hp=80, max_hp=80, pow=20, defense=8, speed=9, exp_reward=25, coin_reward=20, sprite_color=ML_RED)]},
        ],
        'boss': Enemy(name="Dark Star", hp=300, max_hp=300, pow=25, defense=10, speed=8, exp_reward=200, coin_reward=150, sprite_color=ML_PURPLE)
    }
]

# ======================== GAME ENGINE =======================================

class MarioLuigiGame:
    def __init__(self):
        self.screen = pg.display.set_mode((WIN_W, WIN_H))
        pg.display.set_caption("MARIO AND LUIGI + LIVE BROS.")
        
        self.clock = pg.time.Clock()
        self.top_screen = pg.Surface((DS_W, DS_H))
        self.bottom_screen = pg.Surface((DS_W, DS_H))
        
        # Fonts
        self.font_small = pg.font.Font(None, 14)
        self.font_normal = pg.font.Font(None, 18)
        self.font_large = pg.font.Font(None, 24)
        
        # Game state
        self.running = True
        self.scene = 'title'
        self.chapter = 0
        self.battle_index = 0
        
        # Characters
        self.mario = Character("Mario", 100, 100, 20, 20, 25, 20, 25, 30)
        self.luigi = Character("Luigi", 90, 90, 25, 25, 20, 18, 30, 25)
        self.coins = 0
        
        # Battle state
        self.in_battle = False
        self.current_enemies = []
        self.turn = 'player'
        self.selected_action = None
        self.selected_target = 0
        self.action_timer = 0
        self.action_window = 0
        self.last_timing = None
        self.combo_count = 0
        
        # Bros. Attack state
        self.current_bros_attack = None
        self.bros_input_index = 0
        self.bros_inputs = []
        
        # Unlocked Bros. Attacks
        self.unlocked_attacks = ['bounce_bros']
        
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    self.running = False
                else:
                    self.handle_event(event)
                    
            self.update(dt)
            self.draw()
            pg.display.flip()
            
    def handle_event(self, event):
        if event.type == pg.KEYDOWN:
            if self.scene == 'title':
                if event.key == pg.K_RETURN:
                    self.scene = 'chapter_select'
                    
            elif self.scene == 'chapter_select':
                if event.key == pg.K_UP:
                    self.chapter = max(0, self.chapter - 1)
                elif event.key == pg.K_DOWN:
                    self.chapter = min(len(CAMPAIGN_CHAPTERS) - 1, self.chapter + 1)
                elif event.key == pg.K_RETURN:
                    self.start_chapter(self.chapter)
                elif event.key == pg.K_ESCAPE:
                    self.scene = 'title'
                    
            elif self.scene == 'battle':
                self.handle_battle_input(event)
                
            elif self.scene == 'victory':
                if event.key == pg.K_RETURN:
                    self.next_battle()
                    
            elif self.scene == 'game_over':
                if event.key == pg.K_RETURN:
                    self.__init__()  # Reset game
                    
    def handle_battle_input(self, event):
        if self.turn != 'player':
            return
            
        if self.current_bros_attack:
            # Handle Bros. Attack input
            if event.key == pg.K_a:
                self.check_bros_input('A')
            elif event.key == pg.K_b:
                self.check_bros_input('B')
                
        elif self.action_window > 0:
            # Handle action command timing
            if event.key == pg.K_a:
                self.check_action_timing()
                
        elif not self.selected_action:
            # Select action
            if event.key == pg.K_1:
                self.selected_action = 'jump'
                self.action_window = 0.5
                self.action_timer = 0
            elif event.key == pg.K_2:
                self.selected_action = 'hammer'
                self.action_window = 0.4
                self.action_timer = 0
            elif event.key == pg.K_3 and len(self.unlocked_attacks) > 0:
                self.show_bros_menu()
            elif event.key == pg.K_LEFT:
                self.selected_target = max(0, self.selected_target - 1)
            elif event.key == pg.K_RIGHT:
                alive_enemies = [e for e in self.current_enemies if e.hp > 0]
                self.selected_target = min(len(alive_enemies) - 1, self.selected_target + 1)
                
    def check_action_timing(self):
        accuracy = 1.0 - abs(self.action_timer - self.action_window/2) / (self.action_window/2)
        
        if accuracy > 0.9:
            self.last_timing = 'EXCELLENT'
            damage_mult = 2.0
        elif accuracy > 0.7:
            self.last_timing = 'GREAT'
            damage_mult = 1.5
        elif accuracy > 0.5:
            self.last_timing = 'GOOD'
            damage_mult = 1.2
        elif accuracy > 0.3:
            self.last_timing = 'OK'
            damage_mult = 1.0
        else:
            self.last_timing = 'MISS'
            damage_mult = 0.5
            
        # Deal damage
        base_damage = self.mario.pow if self.selected_action == 'jump' else self.mario.pow * 1.2
        damage = int(base_damage * damage_mult)
        
        alive_enemies = [e for e in self.current_enemies if e.hp > 0]
        if self.selected_target < len(alive_enemies):
            target = alive_enemies[self.selected_target]
            target.hp = max(0, target.hp - damage)
            
        self.action_window = 0
        self.selected_action = None
        self.end_player_turn()
        
    def check_bros_input(self, button):
        attack = BROS_ATTACKS[self.current_bros_attack]
        
        if self.bros_input_index < len(attack.button_sequence):
            expected = attack.button_sequence[self.bros_input_index]
            
            if button == expected:
                self.bros_inputs.append('HIT')
                self.combo_count += 1
            else:
                self.bros_inputs.append('MISS')
                self.combo_count = 0
                
            self.bros_input_index += 1
            
            if self.bros_input_index >= len(attack.button_sequence):
                # Calculate damage
                hits = self.bros_inputs.count('HIT')
                accuracy = hits / len(attack.button_sequence)
                damage = int(attack.damage * accuracy * (1 + self.combo_count * 0.1))
                
                # Apply to all enemies
                for enemy in self.current_enemies:
                    if enemy.hp > 0:
                        enemy.hp = max(0, enemy.hp - damage)
                        
                # Use BP
                self.mario.bp = max(0, self.mario.bp - attack.bp_cost)
                
                # Reset
                self.current_bros_attack = None
                self.bros_input_index = 0
                self.bros_inputs = []
                self.end_player_turn()
                
    def show_bros_menu(self):
        # For simplicity, auto-select first available attack
        if len(self.unlocked_attacks) > 0 and self.mario.bp >= 3:
            self.current_bros_attack = self.unlocked_attacks[0]
            self.bros_input_index = 0
            self.bros_inputs = []
            
    def end_player_turn(self):
        # Check victory
        if all(e.hp <= 0 for e in self.current_enemies):
            self.victory()
            return
            
        # Enemy turn
        self.turn = 'enemy'
        self.enemy_attack()
        
    def enemy_attack(self):
        for enemy in self.current_enemies:
            if enemy.hp > 0:
                # Simple AI - attack Mario or Luigi
                target = self.mario if random.random() < 0.6 else self.luigi
                damage = max(1, enemy.pow - target.defense)
                target.hp = max(0, target.hp - damage)
                
        # Check game over
        if self.mario.hp <= 0 and self.luigi.hp <= 0:
            self.scene = 'game_over'
        else:
            self.turn = 'player'
            
    def victory(self):
        self.scene = 'victory'
        
        # Calculate rewards
        total_exp = sum(e.exp_reward for e in self.current_enemies)
        total_coins = sum(e.coin_reward for e in self.current_enemies)
        
        self.mario.exp += total_exp
        self.luigi.exp += total_exp // 2
        self.coins += total_coins
        
        # Level up check
        while self.mario.exp >= self.mario.exp_next:
            self.mario.exp -= self.mario.exp_next
            self.mario.level += 1
            self.mario.exp_next = self.mario.level * 15
            self.mario.max_hp += 10
            self.mario.max_bp += 2
            self.mario.pow += 2
            self.mario.defense += 1
            
            # Unlock new Bros. Attack
            if self.mario.level == 3:
                self.unlocked_attacks.append('green_shell')
            elif self.mario.level == 5:
                self.unlocked_attacks.append('fire_flower')
            elif self.mario.level == 8:
                self.unlocked_attacks.append('copy_flower')
                
    def next_battle(self):
        chapter = CAMPAIGN_CHAPTERS[self.chapter]
        self.battle_index += 1
        
        if self.battle_index < len(chapter['battles']):
            # Next regular battle
            battle_data = chapter['battles'][self.battle_index]
            self.start_battle(battle_data['enemies'])
        elif self.battle_index == len(chapter['battles']):
            # Boss battle
            self.start_battle([chapter['boss']])
        else:
            # Chapter complete
            self.scene = 'chapter_complete'
            
    def start_chapter(self, chapter_index):
        self.chapter = chapter_index
        self.battle_index = 0
        chapter = CAMPAIGN_CHAPTERS[self.chapter]
        
        # Heal characters
        self.mario.hp = self.mario.max_hp
        self.mario.bp = self.mario.max_bp
        self.luigi.hp = self.luigi.max_hp
        self.luigi.bp = self.luigi.max_bp
        
        # Start first battle
        battle_data = chapter['battles'][0]
        self.start_battle(battle_data['enemies'])
        
    def start_battle(self, enemies):
        self.scene = 'battle'
        self.current_enemies = [Enemy(**e.__dict__) for e in enemies]  # Copy enemies
        self.turn = 'player'
        self.selected_action = None
        self.selected_target = 0
        self.last_timing = None
        self.combo_count = 0
        
    def update(self, dt):
        if self.scene == 'battle':
            # Update action timer
            if self.action_window > 0:
                self.action_timer += dt
                if self.action_timer > self.action_window:
                    # Missed timing
                    self.last_timing = 'MISS'
                    self.check_action_timing()
                    
    def draw(self):
        self.top_screen.fill(BLACK)
        self.bottom_screen.fill(BLACK)
        
        if self.scene == 'title':
            self.draw_title()
        elif self.scene == 'chapter_select':
            self.draw_chapter_select()
        elif self.scene == 'battle':
            self.draw_battle()
        elif self.scene == 'victory':
            self.draw_victory()
        elif self.scene == 'chapter_complete':
            self.draw_chapter_complete()
        elif self.scene == 'game_over':
            self.draw_game_over()
            
        # Scale and draw to main screen
        top_scaled = pg.transform.scale(self.top_screen, (WIN_W, WIN_H//2))
        bottom_scaled = pg.transform.scale(self.bottom_screen, (WIN_W, WIN_H//2))
        
        self.screen.blit(top_scaled, (0, 0))
        self.screen.blit(bottom_scaled, (0, WIN_H//2))
        
        # DS border
        pg.draw.rect(self.screen, GRAY, (0, WIN_H//2-2, WIN_W, 4))
        
    def draw_title(self):
        # Top screen
        title = self.font_large.render("MARIO AND LUIGI", True, ML_RED)
        self.top_screen.blit(title, (DS_W//2 - title.get_width()//2, 40))
        
        subtitle = self.font_large.render("+ LIVE BROS.", True, ML_GREEN)
        self.top_screen.blit(subtitle, (DS_W//2 - subtitle.get_width()//2, 70))
        
        # Bottom screen
        start = self.font_normal.render("Press ENTER to Start", True, WHITE)
        self.bottom_screen.blit(start, (DS_W//2 - start.get_width()//2, DS_H//2))
        
    def draw_chapter_select(self):
        # Top screen - chapter info
        chapter = CAMPAIGN_CHAPTERS[self.chapter]
        name = self.font_large.render(f"Chapter {chapter['id']}", True, ML_YELLOW)
        self.top_screen.blit(name, (DS_W//2 - name.get_width()//2, 30))
        
        title = self.font_normal.render(chapter['name'], True, WHITE)
        self.top_screen.blit(title, (DS_W//2 - title.get_width()//2, 60))
        
        desc = self.font_small.render(chapter['description'], True, GRAY)
        self.top_screen.blit(desc, (DS_W//2 - desc.get_width()//2, 90))
        
        # Bottom screen - chapter list
        y = 20
        for i, ch in enumerate(CAMPAIGN_CHAPTERS):
            color = ML_YELLOW if i == self.chapter else WHITE
            text = self.font_normal.render(f"{ch['id']}. {ch['name']}", True, color)
            self.bottom_screen.blit(text, (20, y))
            y += 30
            
    def draw_battle(self):
        # Top screen - battlefield
        
        # Draw enemies
        x_spacing = DS_W // (len(self.current_enemies) + 1)
        for i, enemy in enumerate(self.current_enemies):
            if enemy.hp > 0:
                x = x_spacing * (i + 1)
                y = DS_H // 2
                
                # Enemy sprite
                pg.draw.circle(self.top_screen, enemy.sprite_color, (x, y), 20)
                
                # Selection indicator
                if self.selected_target == i and self.turn == 'player':
                    pg.draw.circle(self.top_screen, ML_YELLOW, (x, y), 25, 2)
                
                # HP bar
                bar_width = 40
                bar_x = x - bar_width // 2
                bar_y = y - 35
                hp_ratio = enemy.hp / enemy.max_hp
                
                pg.draw.rect(self.top_screen, BLACK, (bar_x, bar_y, bar_width, 4))
                pg.draw.rect(self.top_screen, ML_RED, (bar_x, bar_y, int(bar_width * hp_ratio), 4))
                
                # Name
                name = self.font_small.render(enemy.name, True, WHITE)
                self.top_screen.blit(name, (x - name.get_width()//2, y + 25))
                
        # Bottom screen - battle menu
        
        # Character stats
        y = 10
        for char in [self.mario, self.luigi]:
            color = ML_RED if char == self.mario else ML_GREEN
            name = self.font_normal.render(char.name, True, color)
            self.bottom_screen.blit(name, (10, y))
            
            hp = self.font_small.render(f"HP: {char.hp}/{char.max_hp}", True, WHITE)
            self.bottom_screen.blit(hp, (70, y))
            
            bp = self.font_small.render(f"BP: {char.bp}/{char.max_bp}", True, WHITE)
            self.bottom_screen.blit(bp, (140, y))
            
            y += 30
            
        # Action prompt or timing window
        if self.current_bros_attack:
            attack = BROS_ATTACKS[self.current_bros_attack]
            prompt = self.font_normal.render(attack.name, True, ML_YELLOW)
            self.bottom_screen.blit(prompt, (DS_W//2 - prompt.get_width()//2, 80))
            
            # Button sequence
            seq_text = ' '.join(attack.button_sequence[self.bros_input_index:self.bros_input_index+4])
            seq = self.font_small.render(seq_text, True, WHITE)
            self.bottom_screen.blit(seq, (DS_W//2 - seq.get_width()//2, 110))
            
        elif self.action_window > 0:
            # Timing bar
            bar_width = 150
            bar_x = DS_W//2 - bar_width//2
            bar_y = 100
            
            pg.draw.rect(self.bottom_screen, GRAY, (bar_x, bar_y, bar_width, 20))
            
            # Perfect zone
            perfect_x = bar_x + bar_width//2 - 10
            pg.draw.rect(self.bottom_screen, ML_YELLOW, (perfect_x, bar_y, 20, 20))
            
            # Timer position
            timer_x = bar_x + int((self.action_timer / self.action_window) * bar_width)
            pg.draw.rect(self.bottom_screen, WHITE, (timer_x - 2, bar_y, 4, 20))
            
            prompt = self.font_normal.render("Press A!", True, ML_BLUE)
            self.bottom_screen.blit(prompt, (DS_W//2 - prompt.get_width()//2, 130))
            
        elif self.turn == 'player':
            # Action menu
            menu = [
                "1. Jump",
                "2. Hammer",
                "3. Bros. Attack" if len(self.unlocked_attacks) > 0 else "3. ---"
            ]
            
            y = 90
            for option in menu:
                color = WHITE if '---' not in option else GRAY
                text = self.font_normal.render(option, True, color)
                self.bottom_screen.blit(text, (20, y))
                y += 25
                
        # Last timing result
        if self.last_timing:
            color = {
                'EXCELLENT': ML_YELLOW,
                'GREAT': ML_GREEN,
                'GOOD': ML_BLUE,
                'OK': WHITE,
                'MISS': GRAY
            }.get(self.last_timing, WHITE)
            
            result = self.font_large.render(self.last_timing, True, color)
            self.top_screen.blit(result, (DS_W//2 - result.get_width()//2, 20))
            
    def draw_victory(self):
        # Top screen
        victory = self.font_large.render("VICTORY!", True, ML_YELLOW)
        self.top_screen.blit(victory, (DS_W//2 - victory.get_width()//2, 40))
        
        # Bottom screen - rewards
        rewards = [
            f"EXP: +{sum(e.exp_reward for e in self.current_enemies)}",
            f"Coins: +{sum(e.coin_reward for e in self.current_enemies)}",
            "",
            "Press ENTER to continue"
        ]
        
        y = 40
        for text in rewards:
            color = ML_GREEN if 'Press' not in text else WHITE
            txt = self.font_normal.render(text, True, color)
            self.bottom_screen.blit(txt, (DS_W//2 - txt.get_width()//2, y))
            y += 25
            
    def draw_chapter_complete(self):
        # Top screen
        complete = self.font_large.render("CHAPTER COMPLETE!", True, ML_YELLOW)
        self.top_screen.blit(complete, (DS_W//2 - complete.get_width()//2, 40))
        
        chapter = CAMPAIGN_CHAPTERS[self.chapter]
        name = self.font_normal.render(chapter['name'], True, WHITE)
        self.top_screen.blit(name, (DS_W//2 - name.get_width()//2, 80))
        
        # Bottom screen
        stats = [
            f"Mario Level: {self.mario.level}",
            f"Luigi Level: {self.luigi.level}",
            f"Total Coins: {self.coins}",
            "",
            "Press ENTER to continue"
        ]
        
        y = 30
        for text in stats:
            txt = self.font_normal.render(text, True, WHITE)
            self.bottom_screen.blit(txt, (DS_W//2 - txt.get_width()//2, y))
            y += 25
            
    def draw_game_over(self):
        # Top screen
        game_over = self.font_large.render("GAME OVER", True, ML_RED)
        self.top_screen.blit(game_over, (DS_W//2 - game_over.get_width()//2, DS_H//2 - 20))
        
        # Bottom screen
        restart = self.font_normal.render("Press ENTER to restart", True, WHITE)
        self.bottom_screen.blit(restart, (DS_W//2 - restart.get_width()//2, DS_H//2))

# ======================== MAIN ==============================================

def main():
    game = MarioLuigiGame()
    game.run()
    pg.quit()

if __name__ == "__main__":
    main()
