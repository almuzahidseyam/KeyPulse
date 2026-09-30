import threading
import sqlite3
import time
from datetime import date, timedelta
from pynput import keyboard
import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw
import os
import sys
import csv
import winreg

# --- Database Setup ---
DB_PATH = os.path.join(os.path.dirname(__file__), 'keypulse.db')

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_stats (
            log_date TEXT PRIMARY KEY,
            keystrokes INTEGER,
            max_kpm INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("daily_goal", "5000")')
    cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("show_widget", "0")')
    
    # Safe Schema Migration
    cursor.execute("PRAGMA table_info(daily_stats)")
    columns = [col[1] for col in cursor.fetchall()]
    if "max_kpm" not in columns:
        cursor.execute('ALTER TABLE daily_stats ADD COLUMN max_kpm INTEGER DEFAULT 0')
        
    conn.commit()
    return conn

# --- Floating Widget Class ---
class FloatingWidget(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.geometry("180x60+20+20")
        self.overrideredirect(True) 
        self.attributes("-topmost", True) 
        self.attributes("-alpha", 0.85) 
        
        self.parent = parent
        
        self.label = ctk.CTkLabel(self, text="0 KPM\n0 Today", font=("Helvetica", 14, "bold"), text_color="#2FA572")
        self.label.pack(expand=True)
        
        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")
        
    def update_text(self, kpm, count):
        self.label.configure(text=f"⚡ {kpm} KPM\n🎯 {count} Today")


# --- Main Application Class ---
class KeyPulseApp(ctk.CTk):
    def __init__(self, start_minimized=False):
        super().__init__()
        self.title("KeyPulse - Ultra Premium")
        self.geometry("550x700")
        self.resizable(False, False)
        
        self.protocol('WM_DELETE_WINDOW', self.hide_window)

        # State Variables
        self.conn = init_db()
        self.today = str(date.today())
        self.count, self.max_kpm_today = self.get_today_stats()
        self.last_saved_count = self.count # For efficient DB writes
        self.save_ticker = 0
        
        self.daily_goal = self.get_setting("daily_goal", int, 5000)
        self.show_widget_flag = self.get_setting("show_widget", int, 0)
        self.lifetime_total = 0
        
        self.lock = threading.Lock()
        self.keystroke_timestamps = []
        self.last_press_time = time.time()
        self.is_idle = False
        self.floating_widget = None
        self.tray_icon = None

        # Build UI
        self.build_ui()
        
        if self.show_widget_flag:
            self.toggle_widget()

        # Start Listener safely
        self.listener_thread = threading.Thread(target=self.start_listener, daemon=True)
        self.listener_thread.start()

        self.check_autostart()

        # Background Loop
        self.update_ui()
        
        if start_minimized:
            self.after(100, self.hide_window) # Delay slightly to ensure UI is drawn before hiding

    def get_setting(self, key, cast_type, default):
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        return cast_type(row[0]) if row else default

    def set_setting(self, key, value):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('UPDATE settings SET value = ? WHERE key = ?', (str(value), key))
            self.conn.commit()

    def build_ui(self):
        self.tabview = ctk.CTkTabview(self, width=500, height=650)
        self.tabview.pack(padx=20, pady=10)
        
        self.tab_dash = self.tabview.add("Dashboard")
        self.tab_stats = self.tabview.add("Insights & Badges")
        self.tab_settings = self.tabview.add("Settings")

        # --- TAB 1: DASHBOARD ---
        self.title_label = ctk.CTkLabel(self.tab_dash, text="⚡ KeyPulse", font=("Helvetica", 28, "bold"))
        self.title_label.pack(pady=(15, 5))
        
        self.status_label = ctk.CTkLabel(self.tab_dash, text="Status: Active 🟢", font=("Helvetica", 12), text_color="#2FA572")
        self.status_label.pack()

        self.count_label = ctk.CTkLabel(self.tab_dash, text=str(self.count), font=("Helvetica", 90, "bold"), text_color="#1f6aa5")
        self.count_label.pack(pady=(10, 0))
        
        self.info_label = ctk.CTkLabel(self.tab_dash, text="Keystrokes Today\n(🔒 Privacy mode: No keys recorded)", font=("Helvetica", 12), text_color="gray")
        self.info_label.pack(pady=(0, 15))

        self.goal_frame = ctk.CTkFrame(self.tab_dash, fg_color="transparent")
        self.goal_frame.pack(fill="x", padx=40, pady=5)
        
        self.goal_label = ctk.CTkLabel(self.goal_frame, text=f"Daily Goal: {self.daily_goal}", font=("Helvetica", 12))
        self.goal_label.pack(anchor="w")
        
        self.progress_bar = ctk.CTkProgressBar(self.goal_frame, height=12)
        self.progress_bar.pack(fill="x", pady=5)
        self.progress_bar.set(min(self.count / self.daily_goal, 1.0) if self.daily_goal > 0 else 1.0)

        self.kpm_frame = ctk.CTkFrame(self.tab_dash)
        self.kpm_frame.pack(fill="x", padx=40, pady=15)
        
        self.kpm_label = ctk.CTkLabel(self.kpm_frame, text="Speed: 0 KPM\n(~0 WPM)", font=("Helvetica", 16, "bold"), text_color="#2FA572")
        self.kpm_label.pack(side="left", padx=20, pady=10)
        
        self.max_kpm_label = ctk.CTkLabel(self.kpm_frame, text=f"Max KPM: {self.max_kpm_today}", font=("Helvetica", 14), text_color="gray")
        self.max_kpm_label.pack(side="right", padx=20, pady=10)

        # --- TAB 2: INSIGHTS & BADGES ---
        self.lifetime_frame = ctk.CTkFrame(self.tab_stats)
        self.lifetime_frame.pack(fill="x", padx=20, pady=10)
        
        self.stat_total = ctk.CTkLabel(self.lifetime_frame, text="Lifetime Keystrokes: Loading...", font=("Helvetica", 14))
        self.stat_total.pack(anchor="w", padx=15, pady=5)
        
        self.stat_best = ctk.CTkLabel(self.lifetime_frame, text="Best Day: Loading...", font=("Helvetica", 14))
        self.stat_best.pack(anchor="w", padx=15, pady=5)

        self.heat_label = ctk.CTkLabel(self.tab_stats, text="30-Day Activity Heatmap", font=("Helvetica", 14, "bold"))
        self.heat_label.pack(pady=(15, 5))
        
        self.heat_canvas = ctk.CTkCanvas(self.tab_stats, width=420, height=120, bg="#2b2b2b", highlightthickness=0)
        self.heat_canvas.pack(pady=5)
        
        self.badge_label = ctk.CTkLabel(self.tab_stats, text="🏆 Achievements", font=("Helvetica", 14, "bold"))
        self.badge_label.pack(pady=(15, 5))
        
        self.badges_display = ctk.CTkLabel(self.tab_stats, text="Loading...", font=("Helvetica", 13), text_color="#ffcc00")
        self.badges_display.pack()

        # --- TAB 3: SETTINGS ---
        self.set_goal_label = ctk.CTkLabel(self.tab_settings, text="Set Daily Goal:", font=("Helvetica", 14))
        self.set_goal_label.pack(pady=(15, 5))
        
        self.goal_entry = ctk.CTkEntry(self.tab_settings, placeholder_text="e.g. 5000")
        self.goal_entry.pack(pady=5)
        self.goal_entry.insert(0, str(self.daily_goal))
        
        self.save_goal_btn = ctk.CTkButton(self.tab_settings, text="Save Goal", command=self.save_goal)
        self.save_goal_btn.pack(pady=5)
        
        self.settings_msg = ctk.CTkLabel(self.tab_settings, text="", font=("Helvetica", 12), text_color="#2FA572")
        self.settings_msg.pack(pady=5)

        self.widget_var = ctk.BooleanVar(value=bool(self.show_widget_flag))
        self.widget_switch = ctk.CTkSwitch(self.tab_settings, text="Enable Floating Mini-Widget", variable=self.widget_var, command=self.toggle_widget)
        self.widget_switch.pack(pady=10, anchor="w", padx=40)

        self.autostart_var = ctk.BooleanVar()
        self.autostart_switch = ctk.CTkSwitch(self.tab_settings, text="Auto-Start with Windows", variable=self.autostart_var, command=self.toggle_autostart)
        self.autostart_switch.pack(pady=10, anchor="w", padx=40)

        self.export_btn = ctk.CTkButton(self.tab_settings, text="Export Data to CSV", command=self.export_csv)
        self.export_btn.pack(pady=20)

        self.refresh_stats()

    def get_today_stats(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT keystrokes, max_kpm FROM daily_stats WHERE log_date = ?', (self.today,))
        row = cursor.fetchone()
        if row:
            return row[0], row[1]
        else:
            cursor.execute('INSERT INTO daily_stats (log_date, keystrokes, max_kpm) VALUES (?, ?, ?)', (self.today, 0, 0))
            self.conn.commit()
            return 0, 0

    def update_db(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute('UPDATE daily_stats SET keystrokes = ?, max_kpm = ? WHERE log_date = ?', 
                               (self.count, self.max_kpm_today, self.today))
                self.conn.commit()
            except sqlite3.Error as e:
                print(f"Database error: {e}")

    def on_press(self, key):
        try:
            self.count += 1
            t = time.time()
            self.keystroke_timestamps.append(t)
            self.last_press_time = t
            # Removed DB sync from here to prevent threading blockages. Moved to update_ui loop.
        except Exception:
            pass # Keep listener alive no matter what

    def start_listener(self):
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()

    def update_ui(self):
        try:
            # Sync DB occasionally (approx every 5 seconds)
            self.save_ticker += 1
            if self.save_ticker >= 25:
                self.save_ticker = 0
                if self.count != self.last_saved_count:
                    self.update_db()
                    self.last_saved_count = self.count

            # Update Main Counter
            self.count_label.configure(text=str(self.count))
            self.progress_bar.set(min(self.count / self.daily_goal, 1.0) if self.daily_goal > 0 else 1.0)
            
            # Idle Detection
            current_time = time.time()
            self.is_idle = (current_time - self.last_press_time) > 120
            
            if self.is_idle:
                self.status_label.configure(text="Status: Idle 🟠", text_color="orange")
            else:
                self.status_label.configure(text="Status: Active 🟢", text_color="#2FA572")
                
            # KPM Calculation
            self.keystroke_timestamps = [t for t in self.keystroke_timestamps if current_time - t <= 60]
            kpm = len(self.keystroke_timestamps)
            wpm = kpm // 5 
            
            if kpm > self.max_kpm_today:
                self.max_kpm_today = kpm
                self.max_kpm_label.configure(text=f"Max KPM: {self.max_kpm_today}")
                
            self.kpm_label.configure(text=f"Speed: {kpm} KPM\n(~{wpm} WPM)")
            
            # Update Floating Widget
            if self.floating_widget and self.floating_widget.winfo_exists():
                self.floating_widget.update_text(kpm, self.count)
        
        except Exception as e:
            print(f"UI Update error: {e}")
            
        finally:
            self.after(200, self.update_ui)

    def refresh_stats(self):
        cursor = self.conn.cursor()
        
        cursor.execute('SELECT SUM(keystrokes), MAX(keystrokes) FROM daily_stats')
        res = cursor.fetchone()
        self.lifetime_total = res[0] if res[0] else 0
        best_day_count = res[1] if res[1] else 0
        
        self.stat_total.configure(text=f"Lifetime Keystrokes: {self.lifetime_total:,}")
        
        cursor.execute('SELECT log_date FROM daily_stats WHERE keystrokes = ?', (best_day_count,))
        best_day_row = cursor.fetchone()
        best_day_date = best_day_row[0] if best_day_row else "N/A"
        self.stat_best.configure(text=f"Best Day: {best_day_date} ({best_day_count:,} keys)")

        # Badges Logic
        badges = []
        if self.lifetime_total >= 1000: badges.append("🥉 1k Typer")
        if self.lifetime_total >= 10000: badges.append("🥈 10k Pro")
        if self.max_kpm_today >= 200: badges.append("🔥 Speed Demon")
        if self.max_kpm_today >= 400: badges.append("🚀 Flash")
        if self.count >= self.daily_goal: badges.append("⭐ Goal Crusher")
        
        if not badges:
            badges.append("Keep typing to unlock badges!")
            
        self.badges_display.configure(text=" | ".join(badges))

        # 30-Day Heatmap
        self.heat_canvas.delete("all")
        day_counts = {}
        for i in range(29, -1, -1):
            d = str(date.today() - timedelta(days=i))
            cursor.execute('SELECT keystrokes FROM daily_stats WHERE log_date = ?', (d,))
            r = cursor.fetchone()
            day_counts[d] = r[0] if r else 0

        box_size = 20
        padding = 5
        start_x = (420 - (6 * (box_size + padding))) / 2
        start_y = 10
        
        dates = list(day_counts.keys())
        for i, d in enumerate(dates):
            col = i // 5
            row = i % 5
            count = day_counts[d]
            
            if count == 0: color = "#3a3a3a"
            elif count < 1000: color = "#1f6aa5"
            elif count < 3000: color = "#2FA572"
            elif count < 6000: color = "#28cc83"
            else: color = "#26ff9e"
            
            x0 = start_x + col * (box_size + padding)
            y0 = start_y + row * (box_size + padding)
            self.heat_canvas.create_rectangle(x0, y0, x0+box_size, y0+box_size, fill=color, outline="")

    # --- Actions & Settings ---
    def save_goal(self):
        try:
            val = int(self.goal_entry.get())
            if val <= 0: raise ValueError
            self.daily_goal = val
            self.set_setting("daily_goal", val)
            self.goal_label.configure(text=f"Daily Goal: {self.daily_goal}")
            self.settings_msg.configure(text="Goal saved successfully!", text_color="#2FA572")
            self.refresh_stats()
        except ValueError:
            self.settings_msg.configure(text="Please enter a valid positive number.", text_color="red")
        self.after(3000, lambda: self.settings_msg.configure(text=""))

    def toggle_widget(self):
        state = self.widget_var.get()
        self.set_setting("show_widget", int(state))
        
        if state:
            if self.floating_widget is None or not self.floating_widget.winfo_exists():
                self.floating_widget = FloatingWidget(self)
        else:
            if self.floating_widget and self.floating_widget.winfo_exists():
                self.floating_widget.destroy()
                self.floating_widget = None

    def export_csv(self):
        desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
        path = os.path.join(desktop, 'KeyPulse_Export.csv')
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM daily_stats ORDER BY log_date DESC')
        rows = cursor.fetchall()
        try:
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Date', 'Keystrokes', 'Max KPM'])
                writer.writerows(rows)
            self.settings_msg.configure(text="Exported to Desktop!", text_color="#2FA572")
        except Exception as e:
            self.settings_msg.configure(text=f"Export failed: {e}", text_color="red")
        self.after(3000, lambda: self.settings_msg.configure(text=""))

    def check_autostart(self):
        key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ) as k:
                winreg.QueryValueEx(k, "KeyPulse")
                self.autostart_var.set(True)
        except FileNotFoundError:
            self.autostart_var.set(False)

    def toggle_autostart(self):
        key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_path = os.path.abspath(sys.argv[0])
        command = f'"{sys.executable}" "{app_path}" --minimized'
        
        if self.autostart_var.get():
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, "KeyPulse", 0, winreg.REG_SZ, command)
        else:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
                try:
                    winreg.DeleteValue(k, "KeyPulse")
                except FileNotFoundError:
                    pass

    # --- System Tray Logic ---
    def create_tray_image(self):
        image = Image.new('RGB', (64, 64), color="#1f6aa5")
        draw = ImageDraw.Draw(image)
        draw.polygon([(32, 10), (15, 35), (30, 35), (25, 54), (49, 29), (32, 29)], fill="white")
        return image

    def hide_window(self):
        self.withdraw()
        # Create tray icon only if it doesn't exist
        if self.tray_icon is None:
            menu = pystray.Menu(
                pystray.MenuItem('Open KeyPulse', self.show_window),
                pystray.MenuItem('Exit', self.quit_window)
            )
            self.tray_icon = pystray.Icon("KeyPulse", self.create_tray_image(), "KeyPulse Tracker", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self, icon, item):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.after(0, self.deiconify)
        self.refresh_stats()

    def quit_window(self, icon, item):
        if self.tray_icon:
            self.tray_icon.stop()
        self.update_db()
        os._exit(0)

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    start_minimized = "--minimized" in sys.argv
    app = KeyPulseApp(start_minimized=start_minimized)
    
    try:
        app.mainloop()
    finally:
        app.update_db()
