# program.py
# ----------------------------------------------------------------------------
# Mario & Luigi LIVE — DS-like fan prototype (single file, no assets)
# ----------------------------------------------------------------------------
# This is a purely non-commercial, fan-made prototype for educational purposes.
# It simulates a Nintendo DS–style dual-screen layout using Pygame and provides
# a minimal RPG engine: character creation, world navigation, a turn-based
# battle system, a patch menu, and a "dojo" challenge. Content references
# Nintendo IP, but uses only programmer art and text. No external files.
#
# Controls (Keyboard + Mouse/touch simulation for bottom screen):
#   - Arrow Keys / WASD : Move on overworld
#   - Space / Enter / Z : Confirm / Interact
#   - X / Backspace     : Cancel / Back
#   - ESC               : Pause (open bottom UI)
#   - Mouse Click       : Tap on bottom screen UI
#
# Requirements:
#   pip install pygame
#
# Running:
#   python program.py
#
# Notes:
# - This is a local prototype (no online features). The "Nintendo WFC" menu is
#   a non-functional placeholder.
# - Patches toggle features and are buyable with in-game coins you earn in
#   battles. Only some patches have in-engine effects here (items/classes).
# - The code is kept in one file per your request ("files = off").
# ----------------------------------------------------------------------------

import sys
import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict

try:
    import pygame as pg
except ImportError:
    print("This prototype requires Pygame. Install with: pip install pygame")
    sys.exit(1)

# --------------------------- DS-like screen constants ------------------------

DS_W, DS_H = 256, 192         # Native DS screen size
SCALE      = 3                # 3x scale for modern displays (768x1152 window)
WIN_W      = DS_W * SCALE
WIN_H      = DS_H * 2 * SCALE

FPS        = 60
TILE       = 16               # Tiles are 16x16 in DS pixels (so 16x16 grid on top)

# ------------------------------ Colors --------------------------------------

def C(r,g,b): return pg.Color(r,g,b)
WHITE = C(255,255,255)
BLACK = C(0,0,0)
GRAY  = C(90,90,90)
LG    = C(170,170,170)
DG    = C(40,40,40)
RED   = C(220,60,60)
GREEN = C(70,200,100)
BLUE  = C(70,140,220)
YELL  = C(250,210,80)
ORNG  = C(255,160,64)
PURP  = C(150,90,220)
CYAN  = C(50,220,220)
PINK  = C(250,110,170)
SAND  = C(237, 201, 175)
GRASS = C(90, 170, 90)

# ------------------------------ Data Models ---------------------------------

@dataclass
class Item:
    name: str
    desc: str
    kind: str  # 'heal', 'sp', 'buff', 'special'
    amount: int = 0
    price: int = 0

@dataclass
class Patch:
    name: str
    desc: str
    price: int
    installed: bool = False
    default: bool = False
    grants_item: Optional[str] = None  # make item appear in shops/drops
    unlock_class: Optional[str] = None
    note: str = ""

@dataclass
class Battler:
    name: str
    max_hp: int
    hp: int
    sp: int
    atk: int
    df: int
    spd: int
    species: str = "Human"
    team: str = "player"  # 'player' or 'enemy'
    alive: bool = True
    status: Dict[str, int] = field(default_factory=dict)  # e.g., {'lucky':3, 'poison':2}
    color: pg.Color = WHITE

    def take_damage(self, dmg: int):
        if dmg < 1: dmg = 1
        self.hp -= dmg
        if self.hp <= 0:
            self.hp = 0
            self.alive = False

@dataclass
class PlayerData:
    name: str = "Player"
    species: str = "Human"
    gender: str = "male"
    age: str = "baby"
    guardian: str = "Gold"
    level: int = 1
    exp: int = 0
    coins: int = 0
    inventory: Dict[str, int] = field(default_factory=lambda: {"Mushroom": 1, "Maple Syrup": 1, "Lucky Clover": 1})
    patches: Dict[str, Patch] = field(default_factory=dict)
    dark_mode: bool = False

# ------------------------------ Utility -------------------------------------

def clamp(v, a, b): return max(a, min(b, v))

def wrap_text(text, font, w):
    lines = []
    words = text.split(' ')
    cur = ""
    for w0 in words:
        probe = (cur + " " + w0).strip()
        if font.size(probe)[0] <= w:
            cur = probe
        else:
            if cur:
                lines.append(cur)
            cur = w0
    if cur:
        lines.append(cur)
    return lines

# ------------------------------ Engine --------------------------------------

class DSApp:
    def __init__(self):
        pg.init()
        self.screen = pg.display.set_mode((WIN_W, WIN_H))
        pg.display.set_caption("Mario & Luigi LIVE (fan prototype) — DS-like Engine")
        self.clock = pg.time.Clock()

        # Two DS-sized layers
        self.top = pg.Surface((DS_W, DS_H)).convert()
        self.bot = pg.Surface((DS_W, DS_H)).convert()

        # Fonts
        self.font  = pg.font.SysFont("Verdana", 12)
        self.font2 = pg.font.SysFont("Verdana", 10)
        self.big   = pg.font.SysFont("Verdana", 18, bold=True)

        # Game state
        self.running = True
        self.scene: Scene = BootScene(self)
        self.player = PlayerData()
        self.register_default_patches()

        # Simple audio placeholders (muted — no assets). Kept to show extensibility.
        pg.mixer.set_num_channels(8)

    # --------------------------- Patches -------------------------------------

    def register_default_patches(self):
        patches = [
            Patch("MLSS Patch", "Adds Superstar Saga areas. (stub in this build)", 0, installed=True, default=True),
            Patch("MLPiT Patch", "Adds Partners in Time areas. (stub)", 0, installed=True, default=True),
            Patch("Beanish Patch", "Unlocks Beanish class at creation.", 0, installed=True, default=True, unlock_class="Beanish"),
            Patch("Ukiki Patch", "Unlocks Ukiki class at creation.", 0, installed=True, default=True, unlock_class="Ukiki"),
            Patch("Poison Mushroom Patch", "Adds Poison Mushroom item. Shrinks/weakens foes.", 0, installed=True, default=True, grants_item="Poison Mushroom"),
        ]
        purch = [
            Patch("MLBiS Patch", "Adds Bowser's Inside Story areas. (stub)", 750),
            Patch("'Shroomy Helpers Patch", "Recruit Toad/Blue/Yellow Toad (replace party).", 1000),
            Patch("Golden Mushroom Patch", "Adds Golden Mushroom item: Speed to max for battle.", 500, grants_item="Golden Mushroom"),
            Patch("Apprentice Patch", "Become apprentice of Mario/Luigi/Wario/Bowser/Fawful.", 1_000_000),
            Patch("Stuffwell Patch", "Get Stuffwell (customizable) + suitcase menu.", 1000),
            Patch("Star Guardians Patch", "Recruit Geno and Mallow (replace 2 slots).", 1000),
            Patch("SMRPG Patch", "Adds SMRPG areas. (stub)", 0),
            Patch("Smithy Gang Patch", "Adds optional Smithy Gang bosses (needs SMRPG).", 1000, note="Requires SMRPG Patch"),
            Patch("Paper Partners Patch", "Recruit 3 partners from Paper Mario 64.", 2000),
            Patch("Cooligan Patch", "Unlocks Cooligan class at creation.", 750, unlock_class="Cooligan"),
            Patch("Dark Patch", "Infuse Dark Star power: dark versions of party!", 2_000_000),
            Patch("Fountain of Youth Patch", "Stay baby class forever.", 1_000_000),
            Patch("Toady Patch", "Unlocks Toady class at creation.", 0, unlock_class="Toady"),
            Patch("Rookie Patch", "Thief training under Popple.", 0),
        ]
        for p in patches + purch:
            self.player.patches[p.name] = p

    # --------------------------- Main Loop -----------------------------------

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for e in pg.event.get():
                if e.type == pg.QUIT:
                    self.running = False
                else:
                    self.scene.handle_event(e)

            self.scene.update(dt)
            self.scene.draw(self.top, self.bot)

            # Compose to window
            top_scaled = pg.transform.scale(self.top, (DS_W*SCALE, DS_H*SCALE))
            bot_scaled = pg.transform.scale(self.bot, (DS_W*SCALE, DS_H*SCALE))
            self.screen.fill(BLACK)
            self.screen.blit(top_scaled, (0, 0))
            self.screen.blit(bot_scaled, (0, DS_H*SCALE))

            # Border lines between screens
            pg.draw.rect(self.screen, LG, pg.Rect(0, DS_H*SCALE-2, WIN_W, 4))
            pg.display.flip()

    # --------------------------- Helpers -------------------------------------

    def ds_mouse_pos(self) -> Tuple[int,int, str]:
        """Returns DS-coordinates and which screen: 'top' or 'bottom' or '' if outside."""
        mx, my = pg.mouse.get_pos()
        # top
        if 0 <= mx < DS_W*SCALE and 0 <= my < DS_H*SCALE:
            return (mx//SCALE, my//SCALE, 'top')
        # bottom
        if 0 <= mx < DS_W*SCALE and DS_H*SCALE <= my < DS_H*2*SCALE:
            return (mx//SCALE, (my-DS_H*SCALE)//SCALE, 'bottom')
        return (-1,-1,'')

# ------------------------------ UI Widgets ----------------------------------

class UIButton:
    def __init__(self, rect: pg.Rect, text: str, cb=None, small=False):
        self.rect = rect
        self.text = text
        self.cb = cb
        self.small = small
        self.enabled = True

    def draw(self, surf: pg.Surface, font: pg.font.Font):
        col = DG if not self.enabled else (BLUE if self.hovered(surf) else LG)
        pg.draw.rect(surf, col, self.rect, border_radius=4)
        pg.draw.rect(surf, BLACK, self.rect, 2, border_radius=4)
        tx = font.render(self.text, True, BLACK if self.enabled else GRAY)
        surf.blit(tx, tx.get_rect(center=self.rect.center))

    def hovered(self, surf: pg.Surface) -> bool:
        # We only use bottom screen clicks; caller ensures mapping.
        mx, my = pg.mouse.get_pos()
        # Convert global to surf-relative; assume surf scaled placement handled by caller.
        # Here we only use hover visuals on bottom (callers prefer correct overlay).
        return False

    def hit(self, pos: Tuple[int,int]):
        return self.rect.collidepoint(pos)

# ------------------------------ Scenes --------------------------------------

class Scene:
    def __init__(self, app: DSApp):
        self.app = app

    def handle_event(self, e: pg.event.Event): pass
    def update(self, dt: float): pass
    def draw(self, top: pg.Surface, bot: pg.Surface): pass

# -------------------------------- Boot --------------------------------------

class BootScene(Scene):
    def __init__(self, app: DSApp):
        super().__init__(app)
        self.t = 0.0
        self.phase = 0
        self.msgs = [
            "Starlow: Welcome to the Mushroom World!",
            "We'll forge your Star Energy into a new being...",
            "First, tell me about yourself!",
        ]

    def handle_event(self, e):
        if e.type == pg.KEYDOWN and e.key in (pg.K_RETURN, pg.K_SPACE, pg.K_z):
            self.phase += 1
            if self.phase >= len(self.msgs):
                self.app.scene = CharCreateScene(self.app)
        if e.type == pg.MOUSEBUTTONDOWN:
            # Treat any bottom tap as advance for simplicity
            _,_,which = self.app.ds_mouse_pos()
            if which in ('top','bottom'):
                self.phase += 1
                if self.phase >= len(self.msgs):
                    self.app.scene = CharCreateScene(self.app)

    def update(self, dt): self.t += dt

    def draw(self, top, bot):
        top.fill(pg.Color(5, 10, 25))
        bot.fill(pg.Color(12, 20, 40))

        # Starfield
        random.seed(1)
        for _ in range(120):
            x = random.randint(0, DS_W-1)
            y = random.randint(0, DS_H-1)
            top.set_at((x,y), YELL if (x+y)%9==0 else WHITE)

        title = self.app.big.render("Mario & Luigi LIVE (fan prototype)", True, YELL)
        top.blit(title, title.get_rect(center=(DS_W//2, 28)))
        sub = self.app.font.render("Press [Enter]/[Space] or Tap to continue", True, WHITE)
        top.blit(sub, sub.get_rect(center=(DS_W//2, 58)))

        # Dialog on bottom
        pg.draw.rect(bot, DG, pg.Rect(6, 6, DS_W-12, DS_H-12), border_radius=10)
        pg.draw.rect(bot, WHITE, pg.Rect(6, 6, DS_W-12, DS_H-12), 2, border_radius=10)
        if 0 <= self.phase < len(self.msgs):
            lines = wrap_text(self.msgs[self.phase], self.app.big, DS_W-24)
            y = 26
            for ln in lines:
                tx = self.app.big.render(ln, True, WHITE)
                bot.blit(tx, (18, y)); y += tx.get_height()+6

# ------------------------ Character Creation --------------------------------

SPECIES_ALL = [
    "Human","Koopa","Goomba","Pianta","Noki","Toad","Yoshi","Hammer Bro.","Luma",
    "Boo","Bob-Omb","Shy Guy","Piranha Plant","Tanooki","Buzzy Beetle","Lakitu",
    "Wiggler","Shroob","Monty Mole","Birdo","Cloud Creature","Magikoopa","Blooper",
    "Bumpty","Thwomp","Cataquack","Chain-Chomp","Crazee Dayzee","Kong","Cheep Cheep",
    "Fang","Bandinero","Spike","Spiny","Pokey","Beanish","Ukiki","Cooligan","Toady"
]

GENDERS = ["male", "female"]
AGES = ["baby", "adult"]

GUARDIANS = ["Gold","Silver","Purple","Blue","Dark Red","Orange","Green"]

class CharCreateScene(Scene):
    def __init__(self, app: DSApp):
        super().__init__(app)
        # Filter species by installed patches
        enabled = set()
        for p in app.player.patches.values():
            if p.installed and p.unlock_class:
                enabled.add(p.unlock_class)
        self.species_list = [s for s in SPECIES_ALL if (s in ("Beanish","Ukiki","Cooligan","Toady") and s in enabled) or (s not in ("Beanish","Ukiki","Cooligan","Toady"))]
        self.idx = 0
        self.gi = 0
        self.ai = 0
        self.name = "Starling"
        self.step = 0    # 0=species, 1=gender, 2=age, 3=confirm
        self.buttons = self.build_buttons()

    def build_buttons(self):
        b = []
        # Bottom bar: Prev, Next, Confirm
        b.append(UIButton(pg.Rect(12, DS_H-34, 70, 24), "Prev", cb=lambda:self.prev()))
        b.append(UIButton(pg.Rect(DS_W-82, DS_H-34, 70, 24), "Next", cb=lambda:self.next()))
        b.append(UIButton(pg.Rect(DS_W//2-38, DS_H-34, 76, 24), "Confirm", cb=lambda:self.confirm()))
        return b

    def prev(self):
        if self.step == 0:
            self.idx = (self.idx - 1) % len(self.species_list)
        elif self.step == 1:
            self.gi = (self.gi - 1) % len(GENDERS)
        elif self.step == 2:
            self.ai = (self.ai - 1) % len(AGES)

    def next(self):
        if self.step == 0:
            self.idx = (self.idx + 1) % len(self.species_list)
        elif self.step == 1:
            self.gi = (self.gi + 1) % len(GENDERS)
        elif self.step == 2:
            self.ai = (self.ai + 1) % len(AGES)

    def confirm(self):
        self.step += 1
        if self.step >= 3:
            # Save into player
            self.app.player.species = self.species_list[self.idx]
            self.app.player.gender  = GENDERS[self.gi]
            self.app.player.age     = AGES[self.ai]
            self.app.scene = GuardianSelectScene(self.app)

    def handle_event(self, e):
        if e.type == pg.KEYDOWN:
            if e.key in (pg.K_LEFT, pg.K_a): self.prev()
            if e.key in (pg.K_RIGHT, pg.K_d): self.next()
            if e.key in (pg.K_RETURN, pg.K_SPACE, pg.K_z): self.confirm()
            if e.key in (pg.K_BACKSPACE, pg.K_x):
                self.step = max(0, self.step-1)
        if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            x,y,which = self.app.ds_mouse_pos()
            if which == 'bottom':
                for btn in self.buttons:
                    if btn.hit((x,y)) and btn.enabled and btn.cb:
                        btn.cb()

    def update(self, dt): pass

    def draw(self, top, bot):
        top.fill(pg.Color(10,30,10))
        bot.fill(pg.Color(18,18,18))

        title = self.app.big.render("Character Creation", True, WHITE)
        top.blit(title, (8,8))

        # Display current selection on top
        if self.step == 0:
            label = "Species"
            val = self.species_list[self.idx]
        elif self.step == 1:
            label = "Gender"
            val = GENDERS[self.gi]
        else:
            label = "Age"
            val = AGES[self.ai]
        tx = self.app.big.render(f"{label}: {val}", True, YELL)
        top.blit(tx, (8, 40))

        # Simple figure preview
        pg.draw.rect(top, BLUE if self.app.player.gender=="male" else PINK, pg.Rect(128-10, 96-20, 20, 30))
        pg.draw.circle(top, YELL, (128, 96-20), 10)
        sp = self.species_list[self.idx]
        sp_tx = self.app.font.render(f"{sp}", True, WHITE)
        top.blit(sp_tx, sp_tx.get_rect(center=(128, 140)))

        # Bottom instructions + buttons
        pg.draw.rect(bot, DG, pg.Rect(8, 8, DS_W-16, DS_H-56), border_radius=8)
        pg.draw.rect(bot, WHITE, pg.Rect(8, 8, DS_W-16, DS_H-56), 2, border_radius=8)
        msg = ["Choose your Species, Gender, and Age.",
               "Use Left/Right or tap Prev/Next.",
               "Confirm to continue."]
        y = 16
        for m in msg:
            t0 = self.app.font.render(m, True, WHITE)
            bot.blit(t0, (16,y)); y += t0.get_height()+4

        for btn in self.buttons: btn.draw(bot, self.app.font)

# ------------------------ Guardian Selection --------------------------------

class GuardianSelectScene(Scene):
    def __init__(self, app: DSApp):
        super().__init__(app)
        self.idx = 0
        self.buttons = [
            UIButton(pg.Rect(12, DS_H-34, 70, 24), "Prev", cb=lambda:self.prev() ),
            UIButton(pg.Rect(DS_W-82, DS_H-34, 70, 24), "Next", cb=lambda:self.next() ),
            UIButton(pg.Rect(DS_W//2-38, DS_H-34, 76, 24), "Pick", cb=lambda:self.pick() ),
        ]

    def prev(self): self.idx = (self.idx-1) % len(GUARDIANS)
    def next(self): self.idx = (self.idx+1) % len(GUARDIANS)
    def pick(self):
        self.app.player.guardian = GUARDIANS[self.idx]
        self.app.scene = BabyRoomScene(self.app)

    def handle_event(self, e):
        if e.type == pg.KEYDOWN:
            if e.key in (pg.K_LEFT, pg.K_a): self.prev()
            if e.key in (pg.K_RIGHT, pg.K_d): self.next()
            if e.key in (pg.K_RETURN, pg.K_SPACE, pg.K_z): self.pick()
        if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            x,y,which = self.app.ds_mouse_pos()
            if which == 'bottom':
                for btn in self.buttons:
                    if btn.hit((x,y)) and btn.cb: btn.cb()

    def draw(self, top, bot):
        top.fill(pg.Color(5, 15, 30))
        bot.fill(pg.Color(16, 18, 26))

        title = self.app.big.render("Choose a Guardian Sprite", True, WHITE)
        top.blit(title, (8,8))
        name = GUARDIANS[self.idx]
        col = {
            "Gold": YELL, "Silver": LG, "Purple": PURP, "Blue": BLUE,
            "Dark Red": RED, "Orange": ORNG, "Green": GREEN
        }.get(name, WHITE)

        # Draw guardian star
        pg.draw.circle(top, col, (DS_W//2, DS_H//2), 30)
        for i in range(8):
            a = math.tau * i / 8.0
            pg.draw.line(top, col, (DS_W//2, DS_H//2), (DS_W//2+int(40*math.cos(a)), DS_H//2+int(40*math.sin(a))), 2)

        lbl = self.app.big.render(name, True, col)
        top.blit(lbl, lbl.get_rect(center=(DS_W//2, 24)))

        pg.draw.rect(bot, DG, pg.Rect(8, 8, DS_W-16, DS_H-56), border_radius=8)
        pg.draw.rect(bot, WHITE, pg.Rect(8, 8, DS_W-16, DS_H-56), 2, border_radius=8)
        t = "Pick the star sprite that best matches your vibe."
        y = 16
        for ln in wrap_text(t, self.app.font, DS_W-28):
            txt = self.app.font.render(ln, True, WHITE)
            bot.blit(txt, (16, y)); y += 16

        for btn in self.buttons: btn.draw(bot, self.app.font)

# ----------------------------- Overworld Maps --------------------------------

# Legend:
#   W=Wall, G=Grass, P=Path, H=Star Hut, C=Shop, T=Dojo, D=Exit to Desert, .=empty
TOAD_TOWN = [
"WWWWWWWWWWWWWWWW",
"WGGGGGGGGGGGGGGW",
"WGHHGGGGGGGCCGGW",
"WGGGGGGGGGGGGGGW",
"WGGGGTTGGGGGGGGW",
"WGGGGGGGGGGGDGGW",
"WGGGGGGGGGGGGGGW",
"WGGGGGGGGGGGGGGW",
"WGGGGGGGGGGGGGGW",
"WGGGGGGGGGGGGGGW",
"WGGGGGGGGGGGGGGW",
"WWWWWWWWWWWWWWWW",
]

# Desert: S=Sand, R=Ruins, B=Boss gate
DESERT = [
"WWWWWWWWWWWWWWWW",
"WSSSSSSSSSSSSSSW",
"WSSSSSSSSSSSSSSW",
"WSSSSSSSSSSSSSSW",
"WSSSSSSSSSSSSSSW",
"WSSSSSRSSSSSSSSW",
"WSSSSSSSSSSSSSSW",
"WSSSSSSSSSSSSSSW",
"WSSSSSSSSSSSSSSW",
"WSSSSSSSSSSSSSSW",
"WSSSSSSSSSSSSSSW",
"WWWWWWWWWWWWWWWW",
]

class Overworld:
    def __init__(self, grid: List[str]):
        self.grid = grid
        self.w = len(grid[0]); self.h = len(grid)
        self.spawn = (2,2)

    def solid(self, gx, gy) -> bool:
        if gx<0 or gy<0 or gx>=self.w or gy>=self.h: return True
        ch = self.grid[gy][gx]
        return ch == 'W'

    def tile(self, gx, gy) -> str:
        if gx<0 or gy<0 or gx>=self.w or gy>=self.h: return 'W'
        return self.grid[gy][gx]

    def draw(self, surf: pg.Surface):
        for y,row in enumerate(self.grid):
            for x,ch in enumerate(row):
                r = pg.Rect(x*TILE, y*TILE, TILE, TILE)
                if ch == 'W':
                    pg.draw.rect(surf, DG, r)
                elif ch in ('G','P','T','H','C','D'):
                    pg.draw.rect(surf, GRASS if ch!='P' else LG, r)
                elif ch in ('S','R','B'):
                    pg.draw.rect(surf, SAND, r)
                else:
                    pg.draw.rect(surf, BLACK, r)

                # Landmarks
                if ch == 'H': txt="STAR HUT"
                elif ch == 'C': txt="SHOP"
                elif ch == 'T': txt="DOJO"
                elif ch == 'D': txt="DESERT"
                elif ch == 'R': txt="RUINS"
                else: txt=None
                if txt:
                    t0 = pg.font.SysFont("Verdana", 8).render(txt, True, BLACK)
                    surf.blit(t0, (r.x+1, r.y+1))

# ----------------------------- World Scene ----------------------------------

class WorldScene(Scene):
    def __init__(self, app: DSApp, world: Overworld, area_name: str):
        super().__init__(app)
        self.world = world
        self.area_name = area_name
        self.px, self.py = world.spawn
        self.move_delay = 0.0
        self.msg = ""
        self.bottom_mode = "hud"  # 'hud','bag','patch','help','map'
        self.buttons = self.build_buttons()
        self.desert_intro_pending = (area_name == "Dry Dry Desert")
        self.show_tip = True
        self.cutscene_timer = 0.0

    def build_buttons(self):
        bx = 12; by = DS_H-34; bw=70; bh=24; gap=6
        return [
            UIButton(pg.Rect(bx + (bw+gap)*0, by, bw, bh), "Party", cb=lambda:self.set_bottom("hud")),
            UIButton(pg.Rect(bx + (bw+gap)*1, by, bw, bh), "Bag",   cb=lambda:self.set_bottom("bag")),
            UIButton(pg.Rect(bx + (bw+gap)*2, by, bw, bh), "Patches", cb=lambda:self.set_bottom("patch")),
            UIButton(pg.Rect(bx + (bw+gap)*3, by, bw, bh), "Map", cb=lambda:self.set_bottom("map")),
            UIButton(pg.Rect(bx + (bw+gap)*4, by, bw, bh), "Help", cb=lambda:self.set_bottom("help")),
        ]

    def set_bottom(self, m): self.bottom_mode = m

    def handle_event(self, e):
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_ESCAPE: self.bottom_mode = "hud" if self.bottom_mode!="hud" else "help"
            if e.key in (pg.K_UP, pg.K_w): self.try_move(0,-1)
            if e.key in (pg.K_DOWN, pg.K_s): self.try_move(0,1)
            if e.key in (pg.K_LEFT, pg.K_a): self.try_move(-1,0)
            if e.key in (pg.K_RIGHT, pg.K_d): self.try_move(1,0)
            if e.key in (pg.K_SPACE, pg.K_RETURN, pg.K_z):
                self.interact()
        if e.type == pg.MOUSEBUTTONDOWN and e.button==1:
            x,y,which = self.app.ds_mouse_pos()
            if which == 'bottom':
                for btn in self.buttons:
                    if btn.hit((x,y)) and btn.cb: btn.cb()

    def try_move(self, dx, dy):
        nx, ny = self.px+dx, self.py+dy
        if not self.world.solid(nx, ny):
            self.px, self.py = nx, ny
            self.on_enter_tile(nx, ny)

    def interact(self):
        ch = self.world.tile(self.px, self.py)
        if self.area_name == "Toad Town":
            if ch == 'D':
                # Go to desert
                self.app.scene = WorldScene(self.app, Overworld(DESERT), "Dry Dry Desert")
            elif ch == 'H':
                self.app.scene = GuardianHutScene(self.app, self, "Star Hut")
            elif ch == 'T':
                self.app.scene = DojoScene(self.app, self)
            elif ch == 'C':
                self.msg = "Shop: No items for sale yet."
        elif self.area_name == "Dry Dry Desert":
            if ch == 'R':
                # Guardian may block until level or random choice
                allow = random.random() < 0.5 or self.app.player.level >= 3
                if allow:
                    # Boss battle: Tutankoopa
                    enemies = [
                        Battler("Tutankoopa", 55, 55, 10, 7, 2, 6, species="Koopa", team="enemy", color=YELL),
                        Battler("Chompy", 35, 35, 5, 6, 3, 4, species="Chain-Chomp", team="enemy", color=DG),
                    ]
                    self.start_battle(enemies, reward=(200, 30))
                else:
                    self.msg = "Your Guardian advises waiting until you're stronger (Lv 3)."

    def on_enter_tile(self, x, y):
        if self.area_name == "Dry Dry Desert" and self.desert_intro_pending:
            self.desert_intro_pending = False
            enemies = [
                Battler("Pokey A", 18, 18, 5, 5, 1, 4, species="Pokey", team="enemy", color=YELL),
                Battler("Pokey B", 18, 18, 5, 5, 1, 3, species="Pokey", team="enemy", color=YELL),
                Battler("Pokey C", 18, 18, 5, 5, 1, 2, species="Pokey", team="enemy", color=YELL),
            ]
            self.start_battle(enemies, reward=(90,12))

    def start_battle(self, enemies: List[Battler], reward=(50,10)):
        player_char = self.make_player_battler()
        self.app.scene = BattleScene(self.app, [player_char], enemies, origin=self, reward=reward)

    def make_player_battler(self) -> Battler:
        base_hp = 28 if self.app.player.age=="baby" else 36
        if self.app.player.species == "Koopa": species_atk = 6; species_df = 3
        elif self.app.player.species == "Yoshi": species_atk = 6; species_df = 2
        elif self.app.player.species == "Beanish": species_atk = 5; species_df = 2
        else: species_atk = 5; species_df = 2
        if self.app.player.dark_mode:
            species_atk += 2
        return Battler(
            name=self.app.player.name,
            max_hp=base_hp, hp=base_hp, sp=10,
            atk=species_atk, df=species_df, spd=5,
            species=self.app.player.species, team="player", color=BLUE
        )

    def update(self, dt):
        if self.show_tip:
            self.cutscene_timer += dt
            if self.cutscene_timer > 3.0:
                self.show_tip = False

    def draw(self, top, bot):
        top.fill(BLACK)
        self.world.draw(top)

        # Player
        r = pg.Rect(self.px*TILE+3, self.py*TILE+1, TILE-6, TILE-2)
        pg.draw.rect(top, BLUE if self.app.player.gender=="male" else PINK, r)
        pg.draw.rect(top, WHITE, r, 1)

        # HUD (top)
        tx = self.app.font.render(f"{self.area_name}  |  Lv {self.app.player.level}  Coins: {self.app.player.coins}", True, WHITE)
        top.blit(tx, (4, 2))

        # Bottom UI
        bot.fill(pg.Color(25,25,25))
        pg.draw.rect(bot, DG, pg.Rect(8, 8, DS_W-16, DS_H-56), border_radius=8)
        pg.draw.rect(bot, WHITE, pg.Rect(8, 8, DS_W-16, DS_H-56), 2, border_radius=8)

        if self.bottom_mode == "hud":
            lines = [
                f"Name: {self.app.player.name}  Species: {self.app.player.species}  Age: {self.app.player.age}",
                f"Guardian: {self.app.player.guardian}  Dark Mode: {'ON' if self.app.player.dark_mode else 'OFF'}",
                "Tip: Press Space near landmarks (STAR HUT, DOJO, DESERT).",
            ]
            y = 16
            for ln in lines:
                t0 = self.app.font.render(ln, True, WHITE); bot.blit(t0, (16,y)); y+=16
            if self.msg:
                for ln in wrap_text(self.msg, self.app.font, DS_W-32):
                    t0 = self.app.font.render(ln, True, YELL); bot.blit(t0, (16,y)); y+=16
        elif self.bottom_mode == "bag":
            y = 16
            bot.blit(self.app.font.render("Bag (click item to use if applicable)", True, WHITE),(16,y)); y+=18
            mx,my,which = self.app.ds_mouse_pos()
            for name, qty in list(self.app.player.inventory.items()):
                if qty<=0: continue
                rect = pg.Rect(16, y, DS_W-48, 18)
                pg.draw.rect(bot, LG, rect, border_radius=4)
                label = f"{name} x{qty}"
                bot.blit(self.app.font.render(label, True, BLACK), (rect.x+6, rect.y+2))
                if pg.mouse.get_pressed()[0] and which=='bottom' and rect.collidepoint((mx,my)):
                    # Try to use in overworld (non-battle) if meaningful
                    if name == "Mushroom":
                        self.msg = "You feel healthy! (Nothing to heal out of battle.)"
                    elif name == "Maple Syrup":
                        self.msg = "You feel energized! (SP is restored in battle.)"
                    elif name == "Lucky Clover":
                        self.msg = "Saved for battle — boosts your luck."
                    elif name == "Golden Mushroom":
                        self.msg = "Saved for battle — maxes your speed."
                    elif name == "Poison Mushroom":
                        self.msg = "Saved for battle — weakens enemies."
                y += 22
        elif self.bottom_mode == "patch":
            y = 14
            bot.blit(self.app.font.render("Patches (tap to buy/enable/disable)", True, WHITE),(16,y)); y+=16
            mx,my,which = self.app.ds_mouse_pos()
            for nm in sorted(self.app.player.patches.keys()):
                p = self.app.player.patches[nm]
                status = "ON" if p.installed else (p.price and f"{p.price} coins" or "OFF")
                color = GREEN if p.installed else (YELL if p.price else LG)
                line = f"{p.name} — {status}"
                rect = pg.Rect(16, y, DS_W-32, 18)
                pg.draw.rect(bot, color, rect, border_radius=2)
                bot.blit(self.app.font2.render(line, True, BLACK),(rect.x+4, rect.y+2))
                if which=='bottom' and pg.mouse.get_pressed()[0] and rect.collidepoint((mx,my)):
                    if p.default:
                        # Toggle default patch on/off if price==0?
                        p.installed = not p.installed
                    elif not p.installed and p.price and self.app.player.coins >= p.price:
                        self.app.player.coins -= p.price
                        p.installed = True
                        # Golden Mushroom: add to inventory
                        if p.grants_item:
                            self.app.player.inventory.setdefault(p.grants_item, 0)
                            self.app.player.inventory[p.grants_item] += 1
                        if p.name == "Dark Patch":
                            self.app.player.dark_mode = True
                        if p.name == "Fountain of Youth Patch":
                            self.app.player.age = "baby"
                y += 20
        elif self.bottom_mode == "map":
            y = 16
            lines = ["World Map (stub):",
                     "Toad Town — current hub",
                     "Dry Dry Desert — east exit",
                     "Dry Dry Ruins — inside desert (R tile)"]
            for ln in lines:
                bot.blit(self.app.font.render(ln, True, WHITE), (16,y)); y+=16
        else: # help
            y = 16
            for ln in [
                "Help:",
                "Move: Arrow/WASD | Interact: Space/Enter/Z | Back: X",
                "ESC to toggle bottom panels. Click/tap buttons/items.",
                "Beat enemies to earn coins and buy patches!",
            ]:
                bot.blit(self.app.font.render(ln, True, WHITE), (16,y)); y+=16

        for btn in self.buttons: btn.draw(bot, self.app.font)

# ------------------------------ Baby Room Intro ------------------------------

class BabyRoomScene(Scene):
    def __init__(self, app: DSApp):
        super().__init__(app)
        self.stage = 0
        self.t = 0.0
        self.msg = "Toadsworth: Another baby? Let's keep you safe here for now."
        self.ready_for_battle = False

    def handle_event(self, e):
        if e.type == pg.KEYDOWN and e.key in (pg.K_RETURN, pg.K_SPACE, pg.K_z):
            self.stage += 1
            if self.stage == 1:
                self.msg = "Bowser: Meanie!? You'll regret that!"
                self.ready_for_battle = True
            elif self.stage >= 2 and self.ready_for_battle:
                self.start_battle()
        if e.type == pg.MOUSEBUTTONDOWN:
            _,_,which = self.app.ds_mouse_pos()
            if which in ('top','bottom'):
                self.stage += 1
                if self.stage == 1:
                    self.msg = "Bowser: Meanie!? You'll regret that!"
                    self.ready_for_battle = True
                elif self.stage >= 2 and self.ready_for_battle:
                    self.start_battle()

    def start_battle(self):
        enemies = [
            Battler("Goomba", 14, 14, 0, 4, 1, 4, species="Goomba", team="enemy", color=ORNG),
            Battler("Goomba", 14, 14, 0, 4, 1, 3, species="Goomba", team="enemy", color=ORNG),
            Battler("Bowser", 40, 40, 10, 7, 3, 4, species="Koopa", team="enemy", color=RED),
        ]
        origin = WorldScene(self.app, Overworld(TOAD_TOWN), "Toad Town")
        reward = (120, 20)
        self.app.scene = BattleScene(self.app, [origin.make_player_battler()], enemies, origin=origin, reward=reward, tutorial=True)

    def update(self, dt): self.t += dt

    def draw(self, top, bot):
        top.fill(pg.Color(50,40,40))
        # Simple nursery
        for y in range(0, DS_H, TILE):
            for x in range(0, DS_W, TILE):
                pg.draw.rect(top, pg.Color(60,50,50), pg.Rect(x,y,TILE,TILE), 1)
        pg.draw.rect(top, PINK, pg.Rect(16, 64, 40, 24))  # toys
        pg.draw.rect(top, BLUE, pg.Rect(64, 70, 24, 18))
        pg.draw.rect(top, YELL, pg.Rect(200, 70, 24, 18))

        # Bottom dialog
        bot.fill(pg.Color(24,24,24))
        pg.draw.rect(bot, DG, pg.Rect(8, 8, DS_W-16, DS_H-16), border_radius=10)
        pg.draw.rect(bot, WHITE, pg.Rect(8, 8, DS_W-16, DS_H-16), 2, border_radius=10)
        y = 18
        for ln in wrap_text(self.msg, self.app.big, DS_W-26):
            bot.blit(self.app.big.render(ln, True, WHITE),(16,y)); y+=22
        tip = "(Press to continue)"
        bot.blit(self.app.font.render(tip, True, LG), (16, DS_H-26))

# ------------------------------ Guardian Hut ---------------------------------

class GuardianHutScene(Scene):
    def __init__(self, app: DSApp, return_to: WorldScene, name="Star Hut"):
        super().__init__(app)
        self.return_to = return_to
        self.name = name
        self.msg = "Pick a Guardian personality and name it (name entry stub)."
        self.idx = GUARDIANS.index(self.app.player.guardian) if self.app.player.guardian in GUARDIANS else 0
        self.buttons = [
            UIButton(pg.Rect(12, DS_H-34, 70, 24), "Prev", cb=lambda:self.prev() ),
            UIButton(pg.Rect(DS_W-82, DS_H-34, 70, 24), "Next", cb=lambda:self.next() ),
            UIButton(pg.Rect(DS_W//2-38, DS_H-34, 76, 24), "Done", cb=lambda:self.done() ),
        ]

    def prev(self): self.idx = (self.idx - 1) % len(GUARDIANS)
    def next(self): self.idx = (self.idx + 1) % len(GUARDIANS)
    def done(self): self.app.player.guardian = GUARDIANS[self.idx]; self.app.scene = self.return_to

    def handle_event(self, e):
        if e.type == pg.KEYDOWN:
            if e.key in (pg.K_LEFT, pg.K_a): self.prev()
            if e.key in (pg.K_RIGHT, pg.K_d): self.next()
            if e.key in (pg.K_RETURN, pg.K_SPACE, pg.K_z): self.done()
            if e.key in (pg.K_ESCAPE, pg.K_x): self.app.scene = self.return_to
        if e.type == pg.MOUSEBUTTONDOWN and e.button==1:
            x,y,which = self.app.ds_mouse_pos()
            if which=='bottom':
                for btn in self.buttons:
                    if btn.hit((x,y)) and btn.cb: btn.cb()

    def draw(self, top, bot):
        top.fill(pg.Color(10,10,30))
        pg.draw.rect(top, YELL, pg.Rect(12,12, DS_W-24, DS_H-24), 2, border_radius=12)
        name = GUARDIANS[self.idx]
        col = {"Gold":YELL,"Silver":LG,"Purple":PURP,"Blue":BLUE,"Dark Red":RED,"Orange":ORNG,"Green":GREEN}.get(name, WHITE)
        pg.draw.circle(top, col, (DS_W//2, DS_H//2), 28)
        lab = self.app.big.render(f"{self.name}", True, WHITE)
        top.blit(lab, (16, 12))
        nm = self.app.big.render(name, True, col)
        top.blit(nm, nm.get_rect(center=(DS_W//2, DS_H//2+40)))

        bot.fill(pg.Color(25,25,25))
        pg.draw.rect(bot, DG, pg.Rect(8,8, DS_W-16, DS_H-56), border_radius=8)
        pg.draw.rect(bot, WHITE, pg.Rect(8,8, DS_W-16, DS_H-56), 2, border_radius=8)
        y=16
        for ln in wrap_text(self.msg, self.app.font, DS_W-28):
            bot.blit(self.app.font.render(ln, True, WHITE), (16,y)); y+=16
        for btn in self.buttons: btn.draw(bot, self.app.font)

# ------------------------------ Dojo Scene ----------------------------------

class DojoScene(Scene):
    def __init__(self, app: DSApp, return_to: WorldScene):
        super().__init__(app)
        self.return_to = return_to
        self.fights = [
            ("YoshiEgg Nook", [Battler("YoshiEgg Nook", 45,45,10,7,3,6, species="Tanooki", team="enemy", color=GREEN)], (150,20)),
            ("SpriteDev Blue", [Battler("SpriteDev Blue", 55,55,12,8,3,7, species="Luma", team="enemy", color=BLUE)], (180, 24)),
            ("TanookiCoder Red", [Battler("TanookiCoder Red", 65,65,12,9,4,7, species="Tanooki", team="enemy", color=RED)], (220, 30)),
            ("BombSpark", [Battler("BombSpark", 80,80,15,10,5,8, species="Bob-Omb", team="enemy", color=ORNG)], (300, 40)),
        ]
        self.buttons = []
        y = 16
        for i,(name, enemies, rew) in enumerate(self.fights):
            self.buttons.append(UIButton(pg.Rect(16, y, DS_W-32, 20), f"Fight {name}", cb=lambda i=i:self.start(i)))
            y += 24
        self.buttons.append(UIButton(pg.Rect(DS_W//2-40, DS_H-34, 80, 24), "Back", cb=lambda:self.go_back()))

    def go_back(self): self.app.scene = self.return_to

    def start(self, idx):
        origin = self.return_to
        player_char = origin.make_player_battler()
        name, enemies, rew = self.fights[idx]
        self.app.scene = BattleScene(self.app, [player_char], enemies, origin=origin, reward=rew)

    def handle_event(self, e):
        if e.type == pg.KEYDOWN and e.key in (pg.K_ESCAPE, pg.K_x): self.go_back()
        if e.type == pg.MOUSEBUTTONDOWN and e.button==1:
            x,y,which = self.app.ds_mouse_pos()
            if which=='bottom':
                for btn in self.buttons:
                    if btn.hit((x,y)) and btn.cb: btn.cb()

    def draw(self, top, bot):
        top.fill(pg.Color(35,20,20))
        t = self.app.big.render("Mushroom Kingdom Dojo", True, WHITE)
        top.blit(t,(8,8))
        bot.fill(pg.Color(25,25,25))
        pg.draw.rect(bot, DG, pg.Rect(8,8, DS_W-16, DS_H-56), border_radius=8)
        pg.draw.rect(bot, WHITE, pg.Rect(8,8, DS_W-16, DS_H-56), 2, border_radius=8)
        for btn in self.buttons: btn.draw(bot, self.app.font)

# ------------------------------ Battle Scene ---------------------------------

class BattleScene(Scene):
    def __init__(self, app: DSApp, heroes: List[Battler], foes: List[Battler], origin: WorldScene, reward=(50,10), tutorial=False):
        super().__init__(app)
        self.heroes = heroes
        self.foes   = foes
        self.turn_order: List[Battler] = []
        self.origin = origin
        self.reward_coins, self.reward_exp = reward
        self.tutorial = tutorial

        self.bottom_mode = "menu"  # 'menu','items','log'
        self.log: List[str] = []
        self.sel_action = None  # 'Attack','Special','Item','Run'
        self.selected_enemy = 0

        self.compute_turn_order()
        self.log_msg("A battle starts!")

    def compute_turn_order(self):
        party = [b for b in self.heroes if b.alive] + [b for b in self.foes if b.alive]
        # Simple speed order each round
        self.turn_order = sorted(party, key=lambda b: (-b.spd, b.team))

    def log_msg(self, msg: str):
        self.log.append(msg)
        self.log = self.log[-6:]

    def handle_event(self, e):
        if e.type == pg.KEYDOWN:
            if e.key in (pg.K_ESCAPE, pg.K_x):
                self.bottom_mode = "menu"
        if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            x,y,which = self.app.ds_mouse_pos()
            if which=='bottom':
                self.handle_bottom_click((x,y))
            elif which=='top' and self.bottom_mode=="target":
                self.confirm_target_click((x,y))

    def handle_bottom_click(self, pos):
        # Action buttons
        btns = [
            (pg.Rect(16, 16, 100, 22), "Attack"),
            (pg.Rect(16, 44, 100, 22), "Special"),
            (pg.Rect(16, 72, 100, 22), "Item"),
            (pg.Rect(16, 100, 100, 22), "Run"),
        ]
        if self.bottom_mode == "menu":
            for r,name in btns:
                if r.collidepoint(pos):
                    self.sel_action = name
                    if name == "Item":
                        self.bottom_mode = "items"
                    elif name in ("Attack","Special"):
                        self.bottom_mode = "target"
                    elif name == "Run":
                        self.try_run()
        elif self.bottom_mode == "items":
            # list inventory
            y = 16
            entries = []
            for nm, qty in list(self.app.player.inventory.items()):
                if qty > 0:
                    r = pg.Rect(16, y, DS_W-32, 18); entries.append((r, nm)); y+=22
            for r, nm in entries:
                if r.collidepoint(pos):
                    self.use_item_in_battle(nm)
                    self.bottom_mode = "menu"
                    break

    def try_run(self):
        # Simple 50% to run
        if random.random() < 0.5:
            self.log_msg("You fled successfully!")
            self.end_battle(won=False, fled=True)
        else:
            self.log_msg("Couldn't run!")

    def use_item_in_battle(self, name: str):
        inv = self.app.player.inventory
        if inv.get(name,0) <= 0:
            self.log_msg("No item left.")
            return
        inv[name] -= 1
        if name == "Mushroom":
            b = self.heroes[0]
            heal = 18
            b.hp = clamp(b.hp+heal, 1, b.max_hp)
            self.log_msg(f"Used Mushroom! Healed {heal} HP.")
        elif name == "Maple Syrup":
            self.heroes[0].sp += 6
            self.log_msg("Used Maple Syrup! Restored 6 SP.")
        elif name == "Lucky Clover":
            self.heroes[0].status['lucky'] = 3
            self.log_msg("Lucky Clover! Critical chance up for 3 turns.")
        elif name == "Golden Mushroom":
            self.heroes[0].spd = 99
            self.log_msg("Golden Mushroom! Speed maxed for this battle.")
        elif name == "Poison Mushroom":
            # Apply to random enemy
            foes_alive = [f for f in self.foes if f.alive]
            if foes_alive:
                t = random.choice(foes_alive)
                t.status['weaken'] = 3
                self.log_msg(f"Poison Mushroom! {t.name} is weakened.")

    def confirm_target_click(self, pos):
        # Map enemy hitboxes on top screen (roughly fixed spots)
        slots = self.enemy_slots()
        for i, (rect, foe) in enumerate(slots):
            if rect.collidepoint(pos) and foe.alive:
                self.selected_enemy = i
                self.execute_action(foe)

    def enemy_slots(self):
        # Return list of (Rect, Battler) in DS coords for targeting
        slots = []
        alive = [f for f in self.foes if f.alive]
        n = len(alive)
        xs = [180, 200, 220][:n]
        ys = [70, 110, 90][:n]
        for i, foe in enumerate(alive):
            r = pg.Rect(xs[i]-12, ys[i]-12, 24, 24)
            slots.append((r, foe))
        return slots

    def execute_action(self, target: Battler):
        actor = self.heroes[0]
        if self.sel_action == "Attack":
            crit = 1.5 if random.random() < (0.1 + (0.4 if actor.status.get('lucky',0)>0 else 0.0)) else 1.0
            base = max(1, actor.atk - target.df + random.randint(0,2))
            if target.status.get('weaken',0)>0: base += 1
            dmg = int(base * crit)
            target.take_damage(dmg)
            self.log_msg(f"You attack {target.name} for {dmg} damage{' (CRIT!)' if crit>1 else ''}.")
            if not target.alive:
                self.log_msg(f"{target.name} defeated!")
            self.after_player_action()
        elif self.sel_action == "Special":
            # Species-based demo: Koopa Shell Toss / Star Spark otherwise (cost 3 SP)
            if actor.sp >= 3:
                actor.sp -= 3
                if self.app.player.species == "Koopa":
                    dmg = max(1, actor.atk + 2 - target.df) + random.randint(1,3)
                    self.log_msg("Shell Toss!")
                else:
                    dmg = max(1, actor.atk + 1 - target.df) + random.randint(0,2)
                    self.log_msg("Star Spark!")
                target.take_damage(dmg)
                self.log_msg(f"It hits {target.name} for {dmg} damage.")
                if not target.alive:
                    self.log_msg(f"{target.name} defeated!")
                self.after_player_action()
            else:
                self.log_msg("Not enough SP!")
        self.bottom_mode = "menu"

    def after_player_action(self):
        # Enemies take their turns (simple AI)
        for foe in [f for f in self.foes if f.alive]:
            if not self.heroes[0].alive: break
            base = max(1, foe.atk - self.heroes[0].df + random.randint(0,2))
            if self.heroes[0].status.get('lucky',0)>0 and random.random()<0.3:
                self.log_msg(f"{foe.name} missed (Lucky)!")
                continue
            dmg = base
            self.heroes[0].take_damage(dmg)
            self.log_msg(f"{foe.name} hits you for {dmg}.")
        # Tick statuses (simple)
        for b in self.heroes + self.foes:
            for k in list(b.status.keys()):
                b.status[k] -= 1
                if b.status[k] <= 0: del b.status[k]

        if all(not f.alive for f in self.foes):
            self.log_msg("You win!")
            self.end_battle(won=True)
        elif not any(h.alive for h in self.heroes):
            self.log_msg("You fainted...")
            self.end_battle(won=False)

    def end_battle(self, won: bool, fled: bool=False):
        if won:
            self.app.player.coins += self.reward_coins
            self.app.player.exp += self.reward_exp
            # Simple level up rule
            while self.app.player.exp >= self.app.player.level*25:
                self.app.player.exp -= self.app.player.level*25
                self.app.player.level += 1
        # Return to origin world
        self.app.scene = self.origin

    def draw(self, top, bot):
        # Top: battlefield
        top.fill(pg.Color(25,35,50))
        # Player slot
        pg.draw.rect(top, self.heroes[0].color, pg.Rect(30, 120, 24, 24))
        top.blit(self.app.font.render(f"{self.heroes[0].name}", True, WHITE),(16, 146))
        # Enemies
        for rect, foe in self.enemy_slots():
            pg.draw.rect(top, foe.color, rect)
            top.blit(self.app.font.render(foe.name, True, WHITE),(rect.x-8, rect.y-18))
        # HUD stats
        h = self.heroes[0]
        hud = f"HP {h.hp}/{h.max_hp}  SP {h.sp}  Lv {self.app.player.level}  Coins {self.app.player.coins}"
        top.blit(self.app.font.render(hud, True, WHITE), (8, 2))

        # Bottom: command panel
        bot.fill(pg.Color(20,20,20))
        pg.draw.rect(bot, DG, pg.Rect(8, 8, DS_W-16, DS_H-16), border_radius=10)
        pg.draw.rect(bot, WHITE, pg.Rect(8, 8, DS_W-16, DS_H-16), 2, border_radius=10)

        if self.bottom_mode in ("menu","target"):
            labels = ["Attack","Special","Item","Run"]
            for i, name in enumerate(labels):
                r = pg.Rect(16, 16+i*28, 100, 22)
                pg.draw.rect(bot, LG, r, border_radius=6)
                bot.blit(self.app.font.render(name, True, BLACK),(r.x+6, r.y+3))
            if self.bottom_mode == "target":
                tip = "Tap an enemy on the top screen to target."
                bot.blit(self.app.font.render(tip, True, WHITE), (16, 140))
        elif self.bottom_mode == "items":
            y = 16
            for name, qty in list(self.app.player.inventory.items()):
                if qty <= 0: continue
                r = pg.Rect(16, y, DS_W-32, 18)
                pg.draw.rect(bot, LG, r, border_radius=4)
                bot.blit(self.app.font.render(f"{name} x{qty}", True, BLACK),(r.x+6, r.y+2))
                y += 22

        # Log
        y = 16
        for ln in self.log[-6:]:
            tx = self.app.font.render(ln, True, WHITE)
            bot.blit(tx, (140, y)); y += 16

# ------------------------------ Entry Point ----------------------------------

def main():
    app = DSApp()
    # Begin at boot; after battles, over to To a d Town / Desert etc.
    app.run()
    pg.quit()

if __name__ == "__main__":
    main()
