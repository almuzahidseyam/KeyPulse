"""Windows UI check with synthetic counts and no keyboard hook or startup changes."""
import os
from pathlib import Path
import sys
import tempfile

with tempfile.TemporaryDirectory() as folder:
    os.environ['KEYPULSE_DB_PATH']=str(Path(folder)/'test.db')
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
    from keypulse import KeyPulseApp
    app=KeyPulseApp(enable_listener=False)
    try:
        for _ in range(12): app.on_press(None)
        app.update_ui(); app.update()
        assert app.count_label.cget('text')=='12'
        assert app.max_kpm_label.cget('text')=='Max KPM: 12'
        assert app.listener is None
        app.update_db()
        assert app.conn.execute('SELECT keystrokes FROM daily_stats').fetchone()[0]==12
    finally:
        app.shutdown()
print('Windows UI and saved synthetic counts passed; no real keys captured.')
