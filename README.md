# ⚡ KeyPulse

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-brightgreen.svg)
![Open Source](https://img.shields.io/badge/Open%20Source-%E2%9D%A4-red.svg)

**KeyPulse** is a premium, privacy-focused desktop application that tracks your daily keyboard usage in real-time. It counts the number of keystrokes you make every day and visualizes your typing activity through a modern, sleek interface.

## 🌟 Ultra-Premium Features
- **Floating Mini-Widget:** A semi-transparent, draggable floating widget stays always-on-top so you can see your live typing speed and daily count while working in other apps.
- **Customizable Daily Goal:** Change your daily keystroke target directly from the Settings tab.
- **WPM Calculator:** See your approximate Words Per Minute (WPM) in real-time alongside your KPM.
- **Gamification & Badges:** Unlock achievements like "Speed Demon" and "Goal Crusher" based on your performance.

## 🚀 Advanced Premium Features
- **Auto-Start with Windows:** Can automatically start silently in the background when Windows boots up.
- **GitHub-Style Heatmap:** Visualize your last 30 days of typing activity in a beautiful color-coded grid.
- **Idle Detection:** Automatically detects if you're AFK for more than 2 minutes and updates your status.
- **Advanced Analytics:** View your *Lifetime Total Keystrokes*, *Best Day*, and *Maximum KPM*.
- **Data Export:** Export your typing history directly to your Desktop as a CSV file with a single click.

## ✨ Features
- **Real-Time Tracking:** Watch your keystroke count go up in real-time as you type anywhere on your PC.
- **Daily History:** Automatically saves your daily progress using a lightweight `SQLite` database.
- **Privacy First (🔒):** KeyPulse only counts *how many* keys are pressed. It **never** records *which* keys are pressed. There is absolutely no keylogging functionality.
- **Modern UI:** Built with `CustomTkinter` for a beautiful, dark-mode first desktop experience.

## 🚀 Installation & Usage

1. **Clone the repository:**
   ```bash
   git clone https://github.com/almuzahidseyam/KeyPulse.git
   cd KeyPulse
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python src/keypulse.py
   ```

## 🛠️ Built With
- [Python 3](https://www.python.org/)
- [pynput](https://pynput.readthedocs.io/en/latest/) - For global OS keyboard hooks.
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - For the modern UI design.
- [SQLite3](https://docs.python.org/3/library/sqlite3.html) - For local history storage.

## 🤝 Contributing

Contributions, issues, and feature requests are highly welcome! We want this to be an open-source tool built by the community. Feel free to check the [issues page](https://github.com/almuzahidseyam/KeyPulse/issues). Please read `CONTRIBUTING.md` for details.

## 📝 License

This project is [MIT](LICENSE) licensed. Copyright © 2026 Muhammad Al-Muzahid.
