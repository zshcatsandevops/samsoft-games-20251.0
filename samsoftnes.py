import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import sys
import time
import threading
import pickle
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    import winsound
    HAS_SOUND = True
except ImportError:
    HAS_SOUND = False
    def beep(): pass

class NES:
    def __init__(self):
        self.memory = [0] * 0x10000  # 64KB memory
        self.registers = {'A': 0, 'X': 0, 'Y': 0, 'PC': 0x8000, 'S': 0xFD, 'P': 0x34}
        self.ppu_memory = [0] * 0x4000  # 16KB PPU memory
        self.vram = [0] * 0x2000  # Nametable memory
        self.palette = [0] * 0x20  # Palette memory
        self.display = [0] * (256 * 240)  # Flattened 256x240 pixels
        self.keys = [0] * 8  # A, B, Select, Start, Up, Down, Left, Right
        self.keypad_map = {
            'z': 0, 'x': 1, 't': 2, 'y': 3, 'Up': 4, 'Down': 5, 'Left': 6, 'Right': 7
        }
        self.cycles = 0
        self.nmi_pending = False
        self.rom_data = None
        self.prg_rom = []
        self.chr_rom = []
        self.mapper = 0
        self.lock = threading.Lock()

    def load_rom(self, rom_path):
        try:
            with open(rom_path, 'rb') as f:
                header = f.read(16)
                if header[:4] != b'NES\x1A':
                    raise ValueError("Invalid NES ROM header")
                prg_size = header[4] * 0x4000  # 16KB units
                chr_size = header[5] * 0x2000  # 8KB units
                self.mapper = (header[6] >> 4) | (header[7] & 0xF0)
                logging.info(f"Loading ROM: {rom_path}, PRG size: {prg_size}, CHR size: {chr_size}, Mapper: {self.mapper}")
                self.prg_rom = f.read(prg_size)
                self.chr_rom = f.read(chr_size) if chr_size else [0] * 0x2000
                if len(self.prg_rom) != prg_size:
                    raise ValueError(f"ROM PRG data incomplete: expected {prg_size}, got {len(self.prg_rom)}")
                for i in range(len(self.prg_rom)):
                    if self.mapper == 0 and i < 0x4000:
                        self.memory[0x8000 + i] = self.memory[0xC000 + i] = self.prg_rom[i]
                    elif self.mapper == 0 and i < 0x8000:
                        self.memory[0x8000 + i] = self.prg_rom[i]
                for i in range(len(self.chr_rom)):
                    self.ppu_memory[i] = self.chr_rom[i]
            return True
        except Exception as e:
            logging.error(f"ROM load error: {e}")
            return False

    def save_state(self):
        with self.lock:
            return {
                'memory': self.memory[:],
                'registers': self.registers.copy(),
                'ppu_memory': self.ppu_memory[:],
                'vram': self.vram[:],
                'palette': self.palette[:],
                'display': self.display[:],
                'keys': self.keys[:],
                'cycles': self.cycles,
                'nmi_pending': self.nmi_pending
            }

    def load_state(self, state):
        with self.lock:
            self.memory = state['memory'][:]
            self.registers = state['registers'].copy()
            self.ppu_memory = state['ppu_memory'][:]
            self.vram = state['vram'][:]
            self.palette = state['palette'][:]
            self.display = state['display'][:]
            self.keys = state['keys'][:]
            self.cycles = state['cycles']
            self.nmi_pending = state['nmi_pending']

    def render_frame(self):
        with self.lock:
            for y in range(240):
                tile_y = y // 8
                base_idx = y * 256
                for x in range(256):
                    tile_x = x // 8
                    tile_addr = (tile_y * 32 + tile_x) % 0x2000
                    tile_idx = self.vram[tile_addr]
                    tile_offset = tile_idx * 16
                    pattern_slice = self.ppu_memory[tile_offset : tile_offset + 16]
                    pattern = pattern_slice + [0] * (16 - len(pattern_slice))  # Pad to prevent IndexError
                    bit_low = (pattern[y % 8] >> (7 - (x % 8))) & 1
                    bit_high = (pattern[(y % 8) + 8] >> (7 - (x % 8))) & 1
                    pix = (bit_high << 1) | bit_low
                    pal_offset = 0x3F00 + (pix if pix else 0)
                    color = self.ppu_memory[pal_offset & 0x3FFF] & 0x3F if pal_offset < len(self.ppu_memory) else 0
                    self.display[base_idx + x] = color

    def cpu_step(self):
        with self.lock:
            if self.nmi_pending:
                self.nmi_pending = False
                self.push_stack((self.registers['PC'] >> 8) & 0xFF)
                self.push_stack(self.registers['PC'] & 0xFF)
                self.push_stack(self.registers['P'])
                pc_low = self.memory[0xFFFA]
                pc_high = self.memory[0xFFFB]
                self.registers['PC'] = (pc_high << 8) | pc_low
                self.registers['P'] |= 0x04
                return 7
            opcode = self.memory[self.registers['PC']]
            self.registers['PC'] = (self.registers['PC'] + 1) & 0xFFFF
            cycles = 0
            try:
                if opcode == 0xA9:  # LDA Immediate
                    self.registers['A'] = self.memory[self.registers['PC']]
                    self.registers['PC'] = (self.registers['PC'] + 1) & 0xFFFF
                    self.set_flags(self.registers['A'])
                    cycles = 2
                elif opcode == 0xAD:  # LDA Absolute
                    addr = self.memory[self.registers['PC']] | (self.memory[self.registers['PC'] + 1] << 8)
                    self.registers['PC'] = (self.registers['PC'] + 2) & 0xFFFF
                    self.registers['A'] = self.memory[addr & 0xFFFF]
                    self.set_flags(self.registers['A'])
                    cycles = 4
                elif opcode == 0x8D:  # STA Absolute
                    addr = self.memory[self.registers['PC']] | (self.memory[self.registers['PC'] + 1] << 8)
                    self.registers['PC'] = (self.registers['PC'] + 2) & 0xFFFF
                    self.memory[addr & 0xFFFF] = self.registers['A']
                    cycles = 4
                elif opcode == 0x4C:  # JMP Absolute
                    low = self.memory[self.registers['PC']]
                    high = self.memory[self.registers['PC'] + 1]
                    self.registers['PC'] = (high << 8) | low
                    cycles = 3
                else:
                    cycles = 2  # Fallback
            except Exception as e:
                logging.error(f"CPU step error at PC=0x{self.registers['PC']:04X}, opcode=0x{opcode:02X}: {e}")
                cycles = 2
            self.cycles += cycles
            return cycles

    def set_flags(self, value):
        self.registers['P'] = (self.registers['P'] & 0x7D) | (0x80 if value & 0x80 else 0) | (0x02 if value == 0 else 0)

    def push_stack(self, value):
        addr = 0x100 + self.registers['S']
        self.memory[addr] = value
        self.registers['S'] = (self.registers['S'] - 1) & 0xFF

    def pull_stack(self):
        self.registers['S'] = (self.registers['S'] + 1) & 0xFF
        addr = 0x100 + self.registers['S']
        return self.memory[addr]

    def update_timers(self):
        if HAS_SOUND:
            threading.Thread(target=lambda: winsound.Beep(1000, 50), daemon=True).start()
        else:
            beep()

    def set_key(self, key, pressed):
        with self.lock:
            if key in self.keypad_map:
                idx = self.keypad_map[key]
                self.keys[idx] = 1 if pressed else 0
                self.memory[0x4016] = self.keys[0]

class SamsoftEmuNES:
    def __init__(self, root):
        self.root = root
        self.root.title("Samsoft NES Emulator")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        self.root.configure(bg="#2C2F33")
        self.nes = NES()
        self.scale = 2
        self.running = False
        self.cycles_per_frame = 29780  # NTSC CPU cycles (~60 FPS)
        self.fps = 60
        self.frame_time = 1000 // self.fps
        self.speed = 1.0
        self.emulation_thread = None
        self.running_lock = threading.Lock()
        self.rom_loaded = False
        self.setup_ui()
        self.load_config()
        self.load_rom()
        self.root.after(self.frame_time, self.update_display)  # Start display updates
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        self.main_frame = tk.Frame(self.root, bg="#2C2F33")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)
        file_menu = tk.Menu(self.menu_bar, tearoff=0, bg="#2C2F33", fg="white")
        self.menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Load ROM", command=self.load_rom)
        file_menu.add_command(label="Reset", command=self.reset)
        file_menu.add_command(label="Save State", command=self.save_state)
        file_menu.add_command(label="Load State", command=self.load_state)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        settings_menu = tk.Menu(self.menu_bar, tearoff=0, bg="#2C2F33", fg="white")
        self.menu_bar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Configure Keys", command=self.configure_keys)
        settings_menu.add_command(label="Set Speed", command=self.set_speed)
        self.display_frame = tk.Frame(self.main_frame, bg="black", bd=2, relief=tk.SUNKEN)
        self.display_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(self.display_frame, width=256 * self.scale, height=240 * self.scale, bg="black", highlightthickness=0)
        self.canvas.pack(pady=5, padx=5)
        self.status_bar = ttk.Label(self.main_frame, text="No ROM loaded", background="#2C2F33", foreground="white")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=5)  # Fixed: side=tk.BOTTOM
        self.canvas.bind("<KeyPress>", self.on_key_press)
        self.canvas.bind("<KeyRelease>", self.on_key_release)
        self.canvas.focus_set()
        self.image = tk.PhotoImage(width=256 * self.scale, height=240 * self.scale)
        self.canvas.create_image(0, 0, image=self.image, anchor="nw")

    def load_config(self):
        try:
            with open("samsoft_nes_config.pkl", "rb") as f:
                config = pickle.load(f)
                self.keypad_map = config.get("keypad_map", self.nes.keypad_map)
                self.nes.keypad_map = self.keypad_map
                self.speed = config.get("speed", 1.0)
            logging.info("Configuration loaded successfully")
        except FileNotFoundError:
            self.keypad_map = self.nes.keypad_map
            logging.info("No config file found, using default keypad map")

    def save_config(self):
        config = {
            "keypad_map": self.keypad_map,
            "speed": self.speed
        }
        try:
            with open("samsoft_nes_config.pkl", "wb") as f:
                pickle.dump(config, f)
            logging.info("Configuration saved")
        except Exception as e:
            logging.error(f"Error saving config: {e}")

    def load_rom(self):
        rom_path = sys.argv[1] if len(sys.argv) > 1 else None
        if not rom_path or not os.path.exists(rom_path):
            rom_path = filedialog.askopenfilename(
                title="Select NES ROM",
                filetypes=[("NES files", "*.nes"), ("All files", "*.*")]
            )
        if rom_path:
            self.stop_emulation()
            if self.nes.load_rom(rom_path):
                self.rom_loaded = True
                self.running = True
                self.status_bar.config(text=f"ROM: {os.path.basename(rom_path)}")
                self.canvas.focus_set()
                logging.info(f"ROM loaded: {rom_path}")
                self.start_emulation()
            else:
                messagebox.showerror("Error", "Failed to load ROM!")
                self.status_bar.config(text="No ROM loaded")
                self.rom_loaded = False
                self.running = False
        else:
            messagebox.showwarning("Warning", "No ROM selected!")
            self.status_bar.config(text="No ROM loaded")
            self.rom_loaded = False
            self.running = False

    def reset(self):
        if not self.rom_loaded:
            messagebox.showwarning("Warning", "No ROM loaded!")
            return
        self.stop_emulation()
        self.nes = NES()
        self.nes.keypad_map = self.keypad_map
        self.nes.load_rom(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else None)  # Reload original ROM if provided
        self.rom_loaded = True
        self.start_emulation()

    def save_state(self):
        if not self.rom_loaded:
            messagebox.showwarning("Warning", "No ROM loaded!")
            return
        state_path = filedialog.asksaveasfilename(title="Save State", filetypes=[("State files", "*.state")])
        if state_path:
            try:
                state = self.nes.save_state()
                with open(state_path, "wb") as f:
                    pickle.dump(state, f)
                messagebox.showinfo("Success", "State saved successfully!")
                logging.info(f"State saved to {state_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save state: {e}")
                logging.error(f"State save error: {e}")

    def load_state(self):
        if not self.rom_loaded:
            messagebox.showwarning("Warning", "No ROM loaded!")
            return
        state_path = filedialog.askopenfilename(title="Load State", filetypes=[("State files", "*.state")])
        if state_path:
            try:
                with open(state_path, "rb") as f:
                    state = pickle.load(f)
                self.nes.load_state(state)
                self.running = True
                messagebox.showinfo("Success", "State loaded successfully!")
                logging.info(f"State loaded from {state_path}")
                self.canvas.focus_set()
                self.start_emulation()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load state: {e}")
                logging.error(f"State load error: {e}")

    def configure_keys(self):
        key_window = tk.Toplevel(self.root)
        key_window.title("Configure Keys")
        key_window.geometry("300x400")
        key_window.configure(bg="#2C2F33")
        tk.Label(key_window, text="Configure Key Bindings", bg="#2C2F33", fg="white", font=("Arial", 12)).pack(pady=10)
        self.temp_keymap = self.keypad_map.copy()
        button_names = ['A', 'B', 'Select', 'Start', 'Up', 'Down', 'Left', 'Right']
        for key_name, value in list(self.temp_keymap.items()):
            frame = tk.Frame(key_window, bg="#2C2F33")
            frame.pack(fill=tk.X, padx=5, pady=2)
            tk.Label(frame, text=f"{button_names[value]}:", bg="#2C2F33", fg="white").pack(side=tk.LEFT)
            entry = tk.Entry(frame, width=10)
            entry.insert(0, key_name)
            entry.bind("<KeyPress>", lambda e, k=key_name, ent=entry: self.update_keymap(e, k, ent))
            entry.pack(side=tk.LEFT, padx=5)
        def save_keymap():
            self.keypad_map = self.temp_keymap.copy()
            self.nes.keypad_map = self.keypad_map
            self.save_config()
            messagebox.showinfo("Success", "Key bindings saved!")
            key_window.destroy()
            self.root.focus_set()
        tk.Button(key_window, text="Save", command=save_keymap, bg="#7289DA", fg="white").pack(pady=10)
        tk.Button(key_window, text="Cancel", command=key_window.destroy, bg="#7289DA", fg="white").pack(pady=5)

    def update_keymap(self, event, old_key, entry):
        new_key = event.keysym
        if new_key.isprintable() or new_key in ['Up', 'Down', 'Left', 'Right']:
            if new_key in self.temp_keymap and self.temp_keymap[new_key] != self.temp_keymap[old_key]:
                messagebox.showwarning("Warning", f"Key {new_key} already mapped!")
                return
            old_value = self.temp_keymap[old_key]
            del self.temp_keymap[old_key]
            self.temp_keymap[new_key] = old_value
            entry.delete(0, tk.END)
            entry.insert(0, new_key)

    def set_speed(self):
        speed_window = tk.Toplevel(self.root)
        speed_window.title("Set Emulator Speed")
        speed_window.geometry("200x150")
        speed_window.configure(bg="#2C2F33")
        tk.Label(speed_window, text="Speed (x):", bg="#2C2F33", fg="white").pack(pady=5)
        speed_var = tk.StringVar(value=str(self.speed))
        tk.Entry(speed_window, textvariable=speed_var).pack(pady=5)
        def save_speed():
            try:
                new_speed = float(speed_var.get())
                if new_speed > 0:
                    self.speed = new_speed
                    self.save_config()
                    messagebox.showinfo("Success", "Speed updated!")
                else:
                    raise ValueError("Speed must be positive")
            except ValueError:
                messagebox.showerror("Error", "Invalid speed value!")
            finally:
                speed_window.destroy()  # Always close window
        tk.Button(speed_window, text="Save", command=save_speed, bg="#7289DA", fg="white").pack(pady=10)

    def on_key_press(self, event):
        self.nes.set_key(event.keysym, True)

    def on_key_release(self, event):
        self.nes.set_key(event.keysym, False)

    def start_emulation(self):
        with self.running_lock:
            if self.rom_loaded and (self.emulation_thread is None or not self.emulation_thread.is_alive()):
                self.running = True
                self.emulation_thread = threading.Thread(target=self.emulate_loop, daemon=True)
                self.emulation_thread.start()
                logging.info("Emulation thread started")

    def stop_emulation(self):
        with self.running_lock:
            self.running = False
            if self.emulation_thread and self.emulation_thread.is_alive():
                self.emulation_thread.join(timeout=1.0)
                self.emulation_thread = None
                logging.info("Emulation thread stopped")

    def emulate_loop(self):
        while True:
            with self.running_lock:
                if not self.running:
                    break
            try:
                start_time = time.time()
                cycles = 0
                target_cycles = int(self.cycles_per_frame * self.speed)
                while cycles < target_cycles:
                    cycles += self.nes.cpu_step()
                self.nes.render_frame()
                with self.nes.lock:
                    self.nes.nmi_pending = True
                self.nes.update_timers()
                elapsed = (time.time() - start_time) * 1000
                sleep_ms = max(0, self.frame_time - elapsed)
                time.sleep(sleep_ms / 1000.0)
            except Exception as e:
                logging.error(f"Emulation loop error: {e}")
                self.stop_emulation()
                # Note: messagebox in thread may cause issues; log instead
                break

    def update_display(self):
        palette = [
            "#000000", "#7C7C7C", "#0000FC", "#0000BC", "#4428BC", "#940084", "#A80020", "#A81000",
            "#881400", "#503000", "#007800", "#006800", "#005800", "#004058", "#000000", "#000000",
            "#BCBCBC", "#0078F8", "#0058F8", "#6844FC", "#D800CC", "#E40058", "#F83800", "#E45C10",
            "#AC7C00", "#00B800", "#00A800", "#00A844", "#008888", "#000000", "#000000", "#000000",
            "#F8F8F8", "#3CBCFC", "#6888FC", "#9878F8", "#F878F8", "#F85898", "#F87858", "#FCA044",
            "#F8B800", "#B8F818", "#58D854", "#58F898", "#00E8D8", "#787878", "#000000", "#000000"
        ]
        data = []
        width = 256 * self.scale
        height = 240 * self.scale
        black_row = ["#000000"] * width
        if not self.rom_loaded:
            # Full black screen data to match image size
            for _ in range(height):
                data.append("{" + " ".join(black_row) + "}")
        else:
            try:
                with self.nes.lock:
                    for y in range(240):
                        row_idx = y * 256
                        row = [palette[self.nes.display[row_idx + x] % 64] for x in range(256)]
                        scaled_row = [col for col in row for _ in range(self.scale)]
                        for _ in range(self.scale):
                            data.append("{" + " ".join(scaled_row) + "}")
            except Exception as e:
                logging.error(f"Display update error: {e}")
                # Fallback to black
                for _ in range(height):
                    data.append("{" + " ".join(black_row) + "}")
        data_str = " ".join(data)
        self.image.put(data_str, to=(0, 0))  # Full image; data matches size
        self.root.after(self.frame_time, self.update_display)

    def on_closing(self):
        self.stop_emulation()
        self.save_config()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    emu = SamsoftEmuNES(root)
    root.mainloop()
