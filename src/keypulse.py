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
            keystrokes INTEGER
        )
    ''')
    # Safe Schema Migration for advanced stats
    try:
        cursor.execute('ALTER TABLE daily_stats ADD COLUMN max_kpm INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    conn.commit()
    return conn


# --- Main Application Class ---
class KeyPulseApp(ctk.CTk):
    def __init__(self, start_minimized=False):
        super().__init__()
        self.title("KeyPulse - Premium")
        self.geometry("550x650")
        self.resizable(False, False)
        
        self.protocol('WM_DELETE_WINDOW', self.hide_window)

        # State Variables
        self.conn = init_db()
        self.today = str(date.today())
        self.count, self.max_kpm_today = self.get_today_stats()
        self.lock = threading.Lock()
        
        self.keystroke_timestamps = []
        self.daily_goal = 5000
        self.last_press_time = time.time()
        self.is_idle = False

        # Build UI
        self.build_ui()

        # Start Listener
        self.listener_thread = threading.Thread(target=self.start_listener, daemon=True)
        self.listener_thread.start()

        # Check autostart status
        self.check_autostart()

        # Background Loops
        self.update_ui()
        
        if start_minimized:
            self.hide_window()

    def build_ui(self):
        # Tabs for Dashboard and Insights
        self.tabview = ctk.CTkTabview(self, width=500, height=600)
        self.tabview.pack(padx=20, pady=10)
        
        self.tab_dash = self.tabview.add("Dashboard")
        self.tab_stats = self.tabview.add("Insights & Settings")

        # --- TAB 1: DASHBOARD ---
        self.title_label = ctk.CTkLabel(self.tab_dash, text="⚡ KeyPulse", font=("Helvetica", 28, "bold"))
        self.title_label.pack(pady=(15, 5))
        
        self.status_label = ctk.CTkLabel(self.tab_dash, text="Status: Active 🟢", font=("Helvetica", 12), text_color="#2FA572")
        self.status_label.pack()

        self.count_label = ctk.CTkLabel(self.tab_dash, text=str(self.count), font=("Helvetica", 90, "bold"), text_color="#1f6aa5")
        self.count_label.pack(pady=(10, 0))
        
        self.info_label = ctk.CTkLabel(self.tab_dash, text="Keystrokes Today\n(🔒 Privacy mode: No keys recorded)", font=("Helvetica", 12), text_color="gray")
        self.info_label.pack(pady=(0, 20))

        # Goal Progress
        self.goal_frame = ctk.CTkFrame(self.tab_dash, fg_color="transparent")
        self.goal_frame.pack(fill="x", padx=40, pady=5)
        
        self.goal_label = ctk.CTkLabel(self.goal_frame, text=f"Daily Goal: {self.daily_goal}", font=("Helvetica", 12))
        self.goal_label.pack(anchor="w")
        
        self.progress_bar = ctk.CTkProgressBar(self.goal_frame, height=12)
        self.progress_bar.pack(fill="x", pady=5)
        self.progress_bar.set(min(self.count / self.daily_goal, 1.0))

        # KPM Stats
        self.kpm_frame = ctk.CTkFrame(self.tab_dash)
        self.kpm_frame.pack(fill="x", padx=40, pady=20)
        
        self.kpm_label = ctk.CTkLabel(self.kpm_frame, text="Speed: 0 KPM", font=("Helvetica", 16, "bold"), text_color="#2FA572")
        self.kpm_label.pack(side="left", padx=20, pady=10)
        
        self.max_kpm_label = ctk.CTkLabel(self.kpm_frame, text=f"Max KPM: {self.max_kpm_today}", font=("Helvetica", 14), text_color="gray")
        self.max_kpm_label.pack(side="right", padx=20, pady=10)


        # --- TAB 2: INSIGHTS & SETTINGS ---
        # Lifetime Stats
        self.lifetime_frame = ctk.CTkFrame(self.tab_stats)
        self.lifetime_frame.pack(fill="x", padx=20, pady=10)
        
        self.stat_total = ctk.CTkLabel(self.lifetime_frame, text="Lifetime Keystrokes: Loading...", font=("Helvetica", 14))
        self.stat_total.pack(anchor="w", padx=15, pady=5)
        
        self.stat_best = ctk.CTkLabel(self.lifetime_frame, text="Best Day: Loading...", font=("Helvetica", 14))
        self.stat_best.pack(anchor="w", padx=15, pady=5)

        # 30-Day Heatmap
        self.heat_label = ctk.CTkLabel(self.tab_stats, text="30-Day Activity Heatmap", font=("Helvetica", 14, "bold"))
        self.heat_label.pack(pady=(15, 5))
        
        self.heat_canvas = ctk.CTkCanvas(self.tab_stats, width=420, height=120, bg="#2b2b2b", highlightthickness=0)
        self.heat_canvas.pack(pady=5)
        
        # Action Buttons
        self.btn_frame = ctk.CTkFrame(self.tab_stats, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=20, pady=20)

        self.export_btn = ctk.CTkButton(self.btn_frame, text="Export CSV", command=self.export_csv)
        self.export_btn.pack(side="left", padx=10)
        
        self.autostart_var = ctk.BooleanVar()
        self.autostart_switch = ctk.CTkSwitch(self.btn_frame, text="Auto-Start with Windows", variable=self.autostart_var, command=self.toggle_autostart)
        self.autostart_switch.pack(side="right", padx=10)

        self.export_status = ctk.CTkLabel(self.tab_stats, text="", font=("Helvetica", 12), text_color="#2FA572")
        self.export_status.pack()

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
            cursor = self.conn.cursor()
            cursor.execute('UPDATE daily_stats SET keystrokes = ?, max_kpm = ? WHERE log_date = ?', 
                           (self.count, self.max_kpm_today, self.today))
            self.conn.commit()

    def on_press(self, key):
        self.count += 1
        t = time.time()
        self.keystroke_timestamps.append(t)
        self.last_press_time = t
        
        if self.count % 10 == 0:
            self.update_db()

    def start_listener(self):
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()

    def update_ui(self):
        # Update Main Counter
        self.count_label.configure(text=str(self.count))
        self.progress_bar.set(min(self.count / self.daily_goal, 1.0))
        
        # Idle Detection & KPM
        current_time = time.time()
        self.is_idle = (current_time - self.last_press_time) > 120 # 2 minutes idle
        
        if self.is_idle:
            self.status_label.configure(text="Status: Idle 🟠", text_color="orange")
        else:
            self.status_label.configure(text="Status: Active 🟢", text_color="#2FA572")
            
        self.keystroke_timestamps = [t for t in self.keystroke_timestamps if current_time - t <= 60]
        kpm = len(self.keystroke_timestamps)
        
        if kpm > self.max_kpm_today:
            self.max_kpm_today = kpm
            self.max_kpm_label.configure(text=f"Max KPM: {self.max_kpm_today}")
            
        self.kpm_label.configure(text=f"Speed: {kpm} KPM")
        self.after(200, self.update_ui)

    def refresh_stats(self):
        cursor = self.conn.cursor()
        
        # Lifetime Stats
        cursor.execute('SELECT SUM(keystrokes), MAX(keystrokes) FROM daily_stats')
        res = cursor.fetchone()
        lifetime_total = res[0] if res[0] else 0
        best_day_count = res[1] if res[1] else 0
        
        self.stat_total.configure(text=f"Lifetime Keystrokes: {lifetime_total:,}")
        
        cursor.execute('SELECT log_date FROM daily_stats WHERE keystrokes = ?', (best_day_count,))
        best_day_row = cursor.fetchone()
        best_day_date = best_day_row[0] if best_day_row else "N/A"
        self.stat_best.configure(text=f"Best Day: {best_day_date} ({best_day_count:,} keys)")

        # 30-Day Heatmap (GitHub Style)
        self.heat_canvas.delete("all")
        
        # Fetch last 30 days
        day_counts = {}
        for i in range(29, -1, -1):
            d = str(date.today() - timedelta(days=i))
            cursor.execute('SELECT keystrokes FROM daily_stats WHERE log_date = ?', (d,))
            r = cursor.fetchone()
            day_counts[d] = r[0] if r else 0

        # Draw grid (6 cols x 5 rows = 30 days)
        box_size = 20
        padding = 5
        start_x = (420 - (6 * (box_size + padding))) / 2
        start_y = 10
        
        dates = list(day_counts.keys())
        for i, d in enumerate(dates):
            col = i // 5
            row = i % 5
            count = day_counts[d]
            
            # Determine color intensity
            if count == 0: color = "#3a3a3a"
            elif count < 1000: color = "#1f6aa5"
            elif count < 3000: color = "#2FA572"
            elif count < 6000: color = "#28cc83"
            else: color = "#26ff9e"
            
            x0 = start_x + col * (box_size + padding)
            y0 = start_y + row * (box_size + padding)
            x1 = x0 + box_size
            y1 = y0 + box_size
            
            self.heat_canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

    # --- Premium Features ---
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
            self.export_status.configure(text=f"Exported to Desktop!", text_color="#2FA572")
        except Exception as e:
            self.export_status.configure(text=f"Export failed: {e}", text_color="red")
            
        self.after(3000, lambda: self.export_status.configure(text=""))

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
        draw.polygon([(32, 10), (15, 35), (30, 35), (25, 54), (49, 29), (32, 29)], fill="white") # Lightning bolt
        return image

    def hide_window(self):
        self.withdraw()
        menu = pystray.Menu(
            pystray.MenuItem('Open KeyPulse', self.show_window),
            pystray.MenuItem('Exit', self.quit_window)
        )
        self.icon = pystray.Icon("KeyPulse", self.create_tray_image(), "KeyPulse", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def show_window(self, icon, item):
        icon.stop()
        self.after(0, self.deiconify)
        self.refresh_stats()

    def quit_window(self, icon, item):
        icon.stop()
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
