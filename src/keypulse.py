import threading
import sqlite3
import time
from datetime import date, timedelta
from pynput import keyboard
import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw
import os

# Database Setup
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
    conn.commit()
    return conn

# Main Application Class
class KeyPulseApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("KeyPulse - Premium Tracker")
        self.geometry("500x550")
        self.resizable(False, False)
        
        # Override close button to minimize to tray
        self.protocol('WM_DELETE_WINDOW', self.hide_window)

        # Setup Database
        self.conn = init_db()
        self.today = str(date.today())
        self.count = self.get_today_count()
        self.lock = threading.Lock()
        
        # Speed Tracking (Keys Per Minute)
        self.keystroke_timestamps = []
        
        # Daily Goal
        self.daily_goal = 5000

        # Build UI
        self.build_ui()

        # Start Background Listener
        self.listener_thread = threading.Thread(target=self.start_listener, daemon=True)
        self.listener_thread.start()

        # Update UI Loop
        self.update_ui()

    def build_ui(self):
        # Title
        self.title_label = ctk.CTkLabel(self, text="⚡ KeyPulse", font=("Helvetica", 28, "bold"))
        self.title_label.pack(pady=(20, 5))
        
        # Big Counter
        self.count_label = ctk.CTkLabel(self, text=str(self.count), font=("Helvetica", 80, "bold"), text_color="#1f6aa5")
        self.count_label.pack(pady=(10, 0))
        
        self.info_label = ctk.CTkLabel(self, text="Keystrokes Today", font=("Helvetica", 14), text_color="gray")
        self.info_label.pack(pady=(0, 15))

        # Progress Bar & Goal
        self.goal_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.goal_frame.pack(fill="x", padx=40, pady=5)
        
        self.goal_label = ctk.CTkLabel(self.goal_frame, text=f"Daily Goal: {self.daily_goal}", font=("Helvetica", 12))
        self.goal_label.pack(anchor="w")
        
        self.progress_bar = ctk.CTkProgressBar(self.goal_frame, height=10)
        self.progress_bar.pack(fill="x", pady=5)
        self.progress_bar.set(min(self.count / self.daily_goal, 1.0))

        # Typing Speed (KPM)
        self.kpm_label = ctk.CTkLabel(self, text="Speed: 0 KPM", font=("Helvetica", 16, "bold"), text_color="#2FA572")
        self.kpm_label.pack(pady=(10, 20))

        # History Graph (7 Days)
        self.graph_title = ctk.CTkLabel(self, text="Last 7 Days Activity", font=("Helvetica", 14, "bold"))
        self.graph_title.pack()
        
        self.canvas = ctk.CTkCanvas(self, width=420, height=120, bg="#2b2b2b", highlightthickness=0)
        self.canvas.pack(pady=5)
        self.draw_graph()

    def get_today_count(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT keystrokes FROM daily_stats WHERE log_date = ?', (self.today,))
        row = cursor.fetchone()
        if row:
            return row[0]
        else:
            cursor.execute('INSERT INTO daily_stats (log_date, keystrokes) VALUES (?, ?)', (self.today, 0))
            self.conn.commit()
            return 0

    def update_db(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('UPDATE daily_stats SET keystrokes = ? WHERE log_date = ?', (self.count, self.today))
            self.conn.commit()

    def on_press(self, key):
        self.count += 1
        self.keystroke_timestamps.append(time.time())
        if self.count % 10 == 0:
            self.update_db()

    def start_listener(self):
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()

    def update_ui(self):
        # Update Count
        self.count_label.configure(text=str(self.count))
        
        # Update Progress
        self.progress_bar.set(min(self.count / self.daily_goal, 1.0))
        
        # Calculate KPM (Keys in last 60 seconds)
        current_time = time.time()
        self.keystroke_timestamps = [t for t in self.keystroke_timestamps if current_time - t <= 60]
        kpm = len(self.keystroke_timestamps)
        self.kpm_label.configure(text=f"Speed: {kpm} KPM")

        self.after(200, self.update_ui)

    def draw_graph(self):
        self.canvas.delete("all")
        cursor = self.conn.cursor()
        
        # Get last 7 days
        days = []
        counts = []
        for i in range(6, -1, -1):
            d = str(date.today() - timedelta(days=i))
            cursor.execute('SELECT keystrokes FROM daily_stats WHERE log_date = ?', (d,))
            row = cursor.fetchone()
            days.append(d[-5:]) # Show only MM-DD
            counts.append(row[0] if row else 0)
            
        max_count = max(counts) if max(counts) > 0 else 1
        canvas_h = 100
        canvas_w = 420
        bar_w = 30
        spacing = (canvas_w - (7 * bar_w)) / 8

        for i in range(7):
            x0 = spacing + i * (bar_w + spacing)
            y0 = canvas_h - (counts[i] / max_count * canvas_h)
            x1 = x0 + bar_w
            y1 = canvas_h
            
            # Draw bar
            color = "#1f6aa5" if i == 6 else "#555555"
            self.canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")
            
            # Draw text
            self.canvas.create_text(x0 + bar_w/2, canvas_h + 10, text=days[i], fill="white", font=("Helvetica", 8))
            if counts[i] > 0:
                self.canvas.create_text(x0 + bar_w/2, y0 - 10, text=str(counts[i]), fill="white", font=("Helvetica", 8))

    # --- System Tray Logic ---
    def create_tray_image(self):
        # Create a simple blue square icon for the tray
        image = Image.new('RGB', (64, 64), color="#1f6aa5")
        draw = ImageDraw.Draw(image)
        draw.rectangle([16, 16, 48, 48], fill="white")
        return image

    def hide_window(self):
        self.withdraw()
        menu = pystray.Menu(
            pystray.MenuItem('Open KeyPulse', self.show_window),
            pystray.MenuItem('Exit', self.quit_window)
        )
        self.icon = pystray.Icon("KeyPulse", self.create_tray_image(), "KeyPulse - Tracking", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def show_window(self, icon, item):
        icon.stop()
        self.after(0, self.deiconify)
        self.draw_graph() # Refresh graph on open

    def quit_window(self, icon, item):
        icon.stop()
        self.update_db()
        os._exit(0)

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = KeyPulseApp()
    try:
        app.mainloop()
    finally:
        app.update_db()
