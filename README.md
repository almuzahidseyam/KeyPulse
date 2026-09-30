# âš¡ KeyPulse

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-brightgreen.svg)
![Open Source](https://img.shields.io/badge/Open%20Source-%E2%9D%A4-red.svg)

**KeyPulse** is a premium, privacy-focused desktop application that tracks your daily keyboard usage in real-time. It counts the number of keystrokes you make every day and visualizes your typing activity through a modern, sleek interface.

## âœ¨ Features

- **Real-Time Tracking:** Watch your keystroke count go up in real-time as you type anywhere on your PC.
- **Daily History:** Automatically saves your daily progress using a lightweight `SQLite` database.
- **Privacy First (ðŸ”’):** KeyPulse only counts *how many* keys are pressed. It **never** records *which* keys are pressed. There is absolutely no keylogging functionality.
- **Modern UI:** Built with `CustomTkinter` for a beautiful, dark-mode first desktop experience.

## ðŸš€ Installation & Usage

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

## ðŸ› ï¸ Built With
- [Python 3](https://www.python.org/)
- [pynput](https://pynput.readthedocs.io/en/latest/) - For global OS keyboard hooks.
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - For the modern UI design.
- [SQLite3](https://docs.python.org/3/library/sqlite3.html) - For local history storage.

## ðŸ¤ Contributing

Contributions, issues, and feature requests are highly welcome! We want this to be an open-source tool built by the community. Feel free to check the [issues page](https://github.com/almuzahidseyam/KeyPulse/issues). Please read `CONTRIBUTING.md` for details.

## ðŸ“ License

This project is [MIT](LICENSE) licensed. Copyright Â© 2026 Muhammad Al-Muzahid.

