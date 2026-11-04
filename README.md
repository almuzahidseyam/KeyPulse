# KeyPulse

A local Windows keyboard-activity counter. See daily presses, recent presses per minute, a daily goal and a 30-day history. A small optional floating widget and system-tray menu keep the count available without leaving the main window open.

## Run

Requires Windows and Python 3.12+. Use one running instance per Windows user.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python src/keypulse.py
```

Close hides the window to the tray; use **Exit** from the tray to save and stop the keyboard listener. Windows auto-start is opt-in through Settings. The app does not enable it during installation.

## What is recorded

The operating-system keyboard hook receives key events, but the callback ignores key identities. Only daily totals and maximum recent count are written to SQLite. Recent one-second count buckets stay in memory; no typed text, key names, timestamps per key or network uploads are stored. Modifier keys and repeated key-down events count as presses. WPM is only a rough count/5 estimate, not a typing-test result.

Recent KPM uses 60 one-second buckets and therefore has one-second resolution. The speed window resets at a local calendar-date change; daily maximum KPM also starts from that day's saved maximum. Date rollover happens on both key callbacks and UI ticks, so the first key after midnight is not charged to yesterday. Sleep/resume and backward date changes reload the corresponding saved day. A monotonic clock measures recent speed and idle time.

## Data and export

The default database is `%LOCALAPPDATA%/KeyPulse/keypulse.db`. Set `KEYPULSE_DB_PATH` to use another location. Counts flush every five seconds, at date changes, before export and on normal Exit. A crash or forced process termination can lose unsaved counts. If storage fails, the interface reports it; pending counts are retained in memory and Exit waits for a successful save.

The old source-tree sample database is no longer distributed. To keep your own previous history, close KeyPulse, back up your database, and copy it to the new location before launching, or explicitly point `KEYPULSE_DB_PATH` at it. Do not overwrite an existing history file. The existing `daily_stats` schema is supported, including addition of the older missing `max_kpm` column.

CSV export writes `KeyPulse_Export.csv` on the current Windows user's Desktop and replaces an existing export of that name. Back up exports you want to retain.

## Verification

```powershell
python -m unittest discover -s tests -v
.venv/Scripts/python tests/ui_smoke.py
```

Nine counter tests cover midnight before the UI tick, idle rollover, multi-day resume, backward date changes, bounded speed history, peak persistence, concurrent callbacks, additive writes, failed saves and reload. CI runs them on Windows/Linux; the Windows UI check uses synthetic counts with the keyboard hook disabled. Dependency auditing also runs in CI.

[MIT license](LICENSE).
