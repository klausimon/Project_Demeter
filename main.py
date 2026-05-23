import cv2
import numpy as np
import mss
import pyautogui as pag
import time
import threading
import tkinter as tk
import os
import pygetwindow as gw

# Optional: Prevents the bot from crashing if a sweep hits the edge of your monitor
pag.FAILSAFE = False


class HayDayBot:
    def __init__(self, ui_label):
        self.running = False
        self.ui_label = ui_label
        self.screen_capture = mss.MSS()
        self.template_dir = os.path.join(os.path.dirname(__file__), 'templates')

        self.cached_coords = {}
        self.cached_scales = {}  # Remembers the successful scale for each template
        self.templates = {}  # Pre-loaded images in memory
        self.last_newspaper_time = 0

        self._preload_templates()

    def _preload_templates(self):
        """Loads all templates into memory once as grayscale images for 3x faster matching."""
        if not os.path.exists(self.template_dir):
            self.update_status(f"Error: Template folder '{self.template_dir}' not found.")
            return

        for filename in os.listdir(self.template_dir):
            if filename.endswith(('.jpg', '.png')):
                path = os.path.join(self.template_dir, filename)
                # Load in grayscale
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    self.templates[filename] = img
                else:
                    print(f"Failed to load: {filename}")

    def update_status(self, text):
        """Updates the GUI label with the current action."""
        self.ui_label.config(text=f"Status: {text}")
        print(text)

    def get_emulator_window(self):
        """Returns the bounding box of the MEmu window to restrict screen capture area."""
        try:
            windows = gw.getWindowsWithTitle('MEmu')
            if windows:
                win = windows[0]
                return win
        except Exception:
            pass
        return None

    def focus_emulator(self):
        """Finds the MEmu window and forces it to the absolute front of the OS."""
        self.update_status("Locating MEmu window...")
        win = self.get_emulator_window()
        if win:
            if win.isMinimized:
                win.restore()
            try:
                win.activate()
            except Exception:
                pass  # Windows sometimes blocks programmatic activation
            time.sleep(0.5)
        else:
            self.update_status("WARNING: MEmu window not found. Please keep it visible.")

    def find_template(self, image_name, threshold=0.8, use_cache=False, scales=None, sort_by=None):
        """
        Takes a screenshot of just the emulator and finds the center coordinates.
        Utilizes grayscale matching and scale caching for massive speed improvements.
        """
        if scales is None:
            scales = [0.8, 0.9, 1.0, 1.1, 1.2]

        if use_cache and image_name in self.cached_coords:
            return self.cached_coords[image_name]

        if image_name not in self.templates:
            self.update_status(f"Missing template: {image_name}")
            return None

        template = self.templates[image_name]

        # Optimize Capture Area: Only grab the emulator window
        win = self.get_emulator_window()
        if win:
            # Ensure boundaries are within monitor bounds
            monitor = {'left': max(0, win.left), 'top': max(0, win.top),
                       'width': win.width, 'height': win.height}
            offset_x, offset_y = monitor['left'], monitor['top']
        else:
            monitor = {'left': 0, 'top': 0, 'width': 1920, 'height': 1080}
            offset_x, offset_y = 0, 0

        screen_data = self.screen_capture.grab(monitor)
        screen = np.array(screen_data)
        # Convert screen to grayscale for faster processing
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGRA2GRAY)

        # Smart Scaling: Try the last successful scale first
        if image_name in self.cached_scales:
            best_past_scale = self.cached_scales[image_name]
            if best_past_scale in scales:
                scales.remove(best_past_scale)
                scales.insert(0, best_past_scale)

        best_match_coords = None
        best_match_val = -1
        best_points = []
        best_w, best_h = 0, 0
        successful_scale = None

        for scale in scales:
            # Resize template (much smaller than resizing the whole screen)
            resized_template = cv2.resize(template, (0, 0), fx=scale, fy=scale)
            h, w = resized_template.shape

            if h > screen_gray.shape[0] or w > screen_gray.shape[1]:
                continue

            res = cv2.matchTemplate(screen_gray, resized_template, cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= threshold)

            if len(loc[0]) > 0:
                _, max_val, _, _ = cv2.minMaxLoc(res)
                if max_val > best_match_val:
                    best_match_val = max_val
                    best_points = list(zip(loc[1], loc[0]))
                    best_w, best_h = w, h
                    successful_scale = scale

                # If we find a very strong match, break early to save CPU
                if max_val > 0.95:
                    break

        if best_match_val >= threshold and best_points:
            screen_height, screen_width = screen_gray.shape

            # GLOBAL TASKBAR DEADZONE
            best_points = [p for p in best_points if p[1] < (screen_height - 60)]

            if not best_points:
                return None

            if image_name == 'plus_button.jpg':
                unique_buttons = []
                for p in best_points:
                    if not any(abs(p[0] - ub[0]) < 30 and abs(p[1] - ub[1]) < 30 for ub in unique_buttons):
                        unique_buttons.append(p)

                if len(unique_buttons) >= 2:
                    unique_buttons.sort(key=lambda p: p[1])
                    pt = unique_buttons[0]
                else:
                    return None

            # SPECIAL SORTING & DEADZONE LOGIC FOR TILES
            elif image_name in ['soil.jpg', 'ready_wheat.jpg']:
                # UI DEADZONE: Ignore the Friends button in the bottom-right corner
                best_points = [p for p in best_points if
                               not (p[0] > screen_width * 0.85 and p[1] > screen_height * 0.75)]

                if not best_points:
                    return None

                if sort_by == 'right':
                    best_points.sort(key=lambda p: p[0], reverse=True)
                else:
                    best_points.sort(key=lambda p: p[1], reverse=True)

                pt = best_points[0]
            else:
                pt = best_points[0]

            # Adjust coordinates back to absolute screen space
            center_x = pt[0] + (best_w // 2) + offset_x
            center_y = pt[1] + (best_h // 2) + offset_y

            # Cache the successful values
            self.cached_scales[image_name] = successful_scale
            if use_cache:
                self.cached_coords[image_name] = (center_x, center_y)

            return center_x, center_y

        return None

    def close_stray_menus(self):
        """Actively hunts for an X button to clear the screen before major actions."""
        self.update_status("Checking for stray menus...")
        close_btn = self.find_template('close_x.jpg', threshold=0.8, use_cache=False)
        if close_btn:
            self.update_status("Stray menu found. Closing...")
            pag.click(close_btn[0], close_btn[1])
            time.sleep(1)

    def sweep_field(self, start_x, start_y):
        self.update_status("Sweeping field (15 tighter passes)...")

        current_x, current_y = start_x, start_y
        sweep_dx, sweep_dy = 500, -250
        shift_dx, shift_dy = -40, -20

        for i in range(15):
            if not self.running: break

            if i % 2 == 0:
                current_x += sweep_dx
                current_y += sweep_dy
            else:
                current_x -= sweep_dx
                current_y -= sweep_dy

            # Restrict bounds to typical 1080p to avoid PyAutoGUI crashes
            safe_x = max(10, min(1910, current_x))
            safe_y = max(10, min(1020, current_y))
            pag.moveTo(safe_x, safe_y, duration=0.8)

            if i < 14:
                current_x += shift_dx
                current_y += shift_dy
                safe_x = max(10, min(1910, current_x))
                safe_y = max(10, min(1020, current_y))
                pag.moveTo(safe_x, safe_y, duration=0.2)

    def handle_failsafe(self):
        self.update_status("Checking for 'Try Again' connection error...")
        try_again_btn = self.find_template('try_again_btn.jpg', threshold=0.7, use_cache=False)

        if try_again_btn:
            pag.click(try_again_btn[0], try_again_btn[1])
            self.update_status("Clicked 'Try Again'. Waiting 2 minutes to reconnect...")
            self._interruptible_sleep(120)
            return

        self.update_status("CRITICAL FAILSAFE: Pressing F8...")
        pag.press('f8')
        time.sleep(2)

        self.update_status("Looking for restart button...")
        restart_btn = self.find_template('restart_btn.jpg', threshold=0.7, use_cache=False)

        if restart_btn:
            pag.click(restart_btn[0], restart_btn[1])
            self.update_status("Game restarting. Waiting 2 minutes to load...")
            self._interruptible_sleep(120)
        else:
            self.update_status("Could not find any recovery buttons! Waiting 5s...")
            self._interruptible_sleep(5)

    def _interruptible_sleep(self, seconds):
        """Allows long waits to be interrupted immediately if stop is pressed."""
        for _ in range(seconds * 10):
            if not self.running: break
            time.sleep(0.1)

    def reset_camera(self):
        self.update_status("Resetting camera: Step 1 (Finding Right-Most Tile)...")

        target_coords = self.find_template('ready_wheat.jpg', threshold=0.65, sort_by='right')
        if not target_coords:
            target_coords = self.find_template('soil.jpg', threshold=0.7, sort_by='right')

        if target_coords:
            pag.click(target_coords[0], target_coords[1])
            time.sleep(1.5)
            pag.click(100, 100)
            time.sleep(0.5)
        else:
            self.update_status("WARNING: Initial right-most anchor not found.")

        self.update_status("Resetting camera: Step 2 (Finding Bottom-Most Tile)...")
        target_coords = self.find_template('ready_wheat.jpg', threshold=0.65, sort_by='bottom')
        if not target_coords:
            target_coords = self.find_template('soil.jpg', threshold=0.7, sort_by='bottom')

        if target_coords:
            pag.click(target_coords[0], target_coords[1])
            time.sleep(1.5)
            pag.click(100, 100)
            time.sleep(0.5)
        else:
            self.update_status("Camera reset failed. Game might be stuck.")
            self.handle_failsafe()
            return False

        self.update_status("Zooming out...")
        # Get center of emulator rather than hardcoded 960x540
        win = self.get_emulator_window()
        if win:
            cx, cy = win.left + win.width // 2, win.top + win.height // 2
        else:
            cx, cy = 960, 540

        pag.moveTo(cx, cy)
        time.sleep(0.2)

        pag.keyDown('ctrl')
        for _ in range(5):
            pag.scroll(-200)
            time.sleep(0.1)
        pag.keyUp('ctrl')
        time.sleep(1)

        return True

    def harvest_wheat(self):
        self.update_status("Finding bottom-most ready wheat...")
        wheat_coords = self.find_template('ready_wheat.jpg', threshold=0.65, sort_by='bottom')
        if not wheat_coords:
            self.update_status("No ready wheat found.")
            return

        cx, cy = wheat_coords

        self.update_status("Opening harvest menu...")
        pag.click(cx, cy)
        time.sleep(1.5)

        self.update_status("Finding sickle...")
        sickle_coords = self.find_template('sickle.jpg', threshold=0.75)
        if not sickle_coords:
            self.update_status("WARNING: Sickle not found!")
            pag.click(100, 100)
            return

        pag.moveTo(sickle_coords[0], sickle_coords[1])
        time.sleep(0.2)
        pag.mouseDown()
        time.sleep(0.2)

        pag.moveTo(cx, cy, duration=0.5)
        self.sweep_field(cx, cy)
        pag.mouseUp()
        time.sleep(2)

    def plant_wheat(self):
        self.update_status("Finding bottom-most soil...")
        soil_coords = self.find_template('soil.jpg', threshold=0.7, sort_by='bottom')
        if not soil_coords:
            self.update_status("No soil found to plant.")
            return

        cx, cy = soil_coords

        self.update_status("Opening plant menu...")
        pag.click(cx, cy)
        time.sleep(1.5)

        self.update_status("Finding wheat seed...")
        seed_coords = self.find_template('wheat_seed_icon.jpg', threshold=0.65)
        if not seed_coords:
            self.update_status("WARNING: Wheat seed not found!")
            pag.click(100, 100)
            return

        pag.moveTo(seed_coords[0], seed_coords[1])
        time.sleep(0.2)
        pag.mouseDown()
        time.sleep(0.2)

        pag.moveTo(cx, cy, duration=0.5)
        self.sweep_field(cx, cy)
        pag.mouseUp()
        time.sleep(1)

    def find_and_open_shop(self):
        if not self.running: return False

        self.update_status("Looking for shop without moving...")
        shop_coords = self.find_template('shop_building.jpg', threshold=0.7, use_cache=False)
        if not shop_coords:
            shop_coords = self.find_template('shop_building_sold.jpg', threshold=0.7, use_cache=False)

        if shop_coords:
            self.update_status("Shop found! Opening...")
            pag.click(shop_coords[0], shop_coords[1])
            time.sleep(2)
            return True

        self.update_status("Shop not immediately visible. Zooming out...")
        win = self.get_emulator_window()
        cx = win.left + win.width // 2 if win else 960
        cy = win.top + win.height // 2 if win else 540

        pag.moveTo(cx, cy)
        time.sleep(0.2)
        pag.keyDown('ctrl')
        for _ in range(5):
            pag.scroll(-200)
            time.sleep(0.1)
        pag.keyUp('ctrl')
        time.sleep(1)

        self.update_status("Sliding camera slightly UP...")
        pag.moveTo(cx, cy - 140)
        pag.mouseDown()
        pag.moveTo(cx, cy + 160, duration=0.5)
        pag.mouseUp()
        time.sleep(2)

        for _ in range(4):
            if not self.running: return False

            self.update_status("Looking for shop...")
            shop_coords = self.find_template('shop_building.jpg', threshold=0.7, use_cache=False)
            if not shop_coords:
                shop_coords = self.find_template('shop_building_sold.jpg', threshold=0.7, use_cache=False)

            if shop_coords:
                self.update_status("Shop found! Opening...")
                pag.click(shop_coords[0], shop_coords[1])
                time.sleep(2)
                return True

            self.update_status("Shop not visible yet. Swiping camera DOWN...")
            pag.moveTo(cx, cy + 260)
            pag.mouseDown()
            pag.moveTo(cx, cy - 340, duration=0.8)
            pag.mouseUp()
            time.sleep(1.5)

        self.update_status("Failed to find shop. Triggering failsafe...")
        self.reset_camera()
        return False

    def sell_in_shop(self):
        if not self.find_and_open_shop():
            return

        for _ in range(5):
            if not self.running: break

            self.update_status("Checking for sold boxes...")
            sold_box = self.find_template('sold_box.jpg', threshold=0.8)
            if sold_box:
                pag.click(sold_box[0], sold_box[1])
                time.sleep(1)

            self.update_status("Looking for empty box...")
            box_coords = self.find_template('empty_box.jpg', threshold=0.8)
            if not box_coords:
                self.update_status("No empty boxes visible.")
                break

            pag.click(box_coords[0], box_coords[1])
            time.sleep(1)

            self.update_status("Finding wheat in inventory...")
            wheat_inv_coords = self.find_template('wheat_inventory.jpg', threshold=0.80)

            if not wheat_inv_coords:
                self.update_status("No wheat found to sell! Closing menu.")
                self.close_stray_menus()
                break

            pag.click(wheat_inv_coords[0], wheat_inv_coords[1])
            time.sleep(0.5)

            self.update_status("Setting quantity to 10...")
            plus_btn = self.find_template('plus_button.jpg', threshold=0.90, use_cache=False)
            if plus_btn:
                for _ in range(9):
                    pag.click(plus_btn[0], plus_btn[1])
                    time.sleep(0.05)
            else:
                self.update_status("Quantity is maxed (Plus button greyed out).")

            current_time = time.time()
            if current_time - self.last_newspaper_time >= 300:
                self.update_status("Toggling newspaper ad...")
                news_btn = self.find_template('newspaper_toggle.jpg', use_cache=True)
                if news_btn:
                    pag.click(news_btn[0], news_btn[1])
                    self.last_newspaper_time = current_time
            else:
                rem = int(300 - (current_time - self.last_newspaper_time))
                self.update_status(f"Ad on cooldown ({rem}s). Skipping.")
            time.sleep(0.5)

            sell_btn = self.find_template('put_on_sale_btn.jpg', use_cache=True)
            if sell_btn: pag.click(sell_btn[0], sell_btn[1])
            time.sleep(1)

        self.close_stray_menus()
        self.update_status("Shop closed.")
        time.sleep(1)

    def run_bot(self):
        self.running = True

        while self.running:
            self.focus_emulator()
            self.close_stray_menus()

            if not self.reset_camera():
                continue

            self.close_stray_menus()
            self.plant_wheat()

            plant_time = time.time()

            self.close_stray_menus()
            self.sell_in_shop()

            elapsed_time = time.time() - plant_time
            remaining_wait = 120 - elapsed_time

            if remaining_wait > 0:
                self.update_status(f"Waiting {int(remaining_wait)}s for wheat to finish growing...")
                self._interruptible_sleep(int(remaining_wait))

            if not self.running: break

            self.close_stray_menus()
            self.harvest_wheat()

        self.update_status("Bot Stopped.")


# --- Thread Management ---
bot_thread = None


def start_bot_thread():
    global bot_thread
    if bot_thread is None or not bot_thread.is_alive():
        bot.running = True
        bot_thread = threading.Thread(target=bot.run_bot, daemon=True)
        bot_thread.start()


def stop_bot_thread():
    """Signals the thread to stop gracefully via the running flag."""
    bot.running = False
    bot.update_status("Stopping bot... (Will finish current action)")


# --- GUI Setup ---
root = tk.Tk()
root.title("Hay Day Wheat Bot")
root.geometry("300x150")
root.attributes("-topmost", True)

status_label = tk.Label(root, text="Status: Idle", wraplength=280)
status_label.pack(pady=20)

bot = HayDayBot(status_label)

start_btn = tk.Button(root, text="Start Bot", command=start_bot_thread, bg="green", fg="white", width=15)
start_btn.pack(pady=5)

stop_btn = tk.Button(root, text="Stop Bot", command=stop_bot_thread, bg="red", fg="white", width=15)
stop_btn.pack(pady=5)

root.mainloop()