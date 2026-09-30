import threading
import sqlite3
from datetime import date
from pynput import keyboard
import customtkinter as ctk
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
        self.title("KeyPulse - TypeStats & Keystroke Tracker")
        self.geometry("400x300")
        self.resizable(False, False)
        
        # Setup Database
        self.conn = init_db()
        self.today = str(date.today())
        self.count = self.get_today_count()
        self.lock = threading.Lock() # For thread-safe DB operations

        # UI Elements
        self.title_label = ctk.CTkLabel(self, text="⚡ KeyPulse", font=("Helvetica", 28, "bold"))
        self.title_label.pack(pady=(25, 10))
        
        self.date_label = ctk.CTkLabel(self, text=f"Today: {self.today}", font=("Helvetica", 14))
        self.date_label.pack(pady=0)

        self.count_label = ctk.CTkLabel(self, text=str(self.count), font=("Helvetica", 72, "bold"), text_color="#1f6aa5")
        self.count_label.pack(pady=15)
        
        self.info_label = ctk.CTkLabel(self, text="Keystrokes Today\n(🔒 Privacy mode: No keys recorded)", font=("Helvetica", 12), text_color="gray")
        self.info_label.pack(pady=10)

        # Start Background Listener
        self.listener_thread = threading.Thread(target=self.start_listener, daemon=True)
        self.listener_thread.start()

        # Update UI Loop
        self.update_ui()

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
        # Update DB every 10 strokes to reduce disk I/O operations
        if self.count % 10 == 0:
            self.update_db()

    def start_listener(self):
        # Global listener hooks into OS events
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()

    def update_ui(self):
        # Update the visual label with the new count
        self.count_label.configure(text=str(self.count))
        self.after(200, self.update_ui)  # Refresh UI every 200ms

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = KeyPulseApp()
    
    try:
        app.mainloop()
    finally:
        # Final save to database when the app is closed
        app.update_db()
