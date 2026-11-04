from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from counter import DailyCounter


class CounterTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:',check_same_thread=False)
        self.db.execute('CREATE TABLE daily_stats(log_date TEXT PRIMARY KEY,keystrokes INTEGER,max_kpm INTEGER)')
        self.day=date(2026,11,4); self.time=100.0
        self.counter=DailyCounter(self.db,day_clock=lambda:self.day,clock=lambda:self.time)
    def tearDown(self): self.db.close()
    def test_midnight_first_key_before_ui_tick(self):
        self.counter.press(); self.counter.press()
        self.day=date(2026,11,5); self.time+=1
        self.counter.press()
        self.assertEqual(self.counter.snapshot()['count'],1)
        self.assertEqual(self.counter.snapshot()['maximum'],1)
        self.assertEqual(self.db.execute('SELECT keystrokes,max_kpm FROM daily_stats WHERE log_date=?',('2026-11-04',)).fetchone(),(2,2))
    def test_idle_midnight_and_resume_days_later(self):
        self.counter.press(); self.day=date(2026,11,9); self.time+=86400*5
        state=self.counter.snapshot()
        self.assertEqual((state['count'],state['kpm'],state['maximum'],state['idle']),(0,0,0,True))
    def test_existing_day_and_clock_backward(self):
        self.db.execute('INSERT INTO daily_stats VALUES(?,?,?)',('2026-11-03',80,12));self.db.commit()
        self.counter.press();self.day=date(2026,11,3);self.time-=10
        self.counter.press()
        self.assertEqual((self.counter.snapshot()['count'],self.counter.snapshot()['maximum']),(81,12))
        self.counter.flush()
        self.assertEqual(self.db.execute('SELECT SUM(keystrokes) FROM daily_stats').fetchone()[0],82)
    def test_last_minute_is_bounded(self):
        for second in range(100,400):
            self.time=second;self.counter.press()
        self.assertEqual(len(self.counter.buckets),60)
        self.assertEqual(self.counter.snapshot()['kpm'],60)
        self.time=460
        self.assertEqual(self.counter.snapshot()['kpm'],0)
    def test_peak_saved_even_without_ui(self):
        for _ in range(50):self.counter.press()
        self.time+=61;self.counter.flush()
        self.assertEqual(self.db.execute('SELECT keystrokes,max_kpm FROM daily_stats').fetchone(),(50,50))
    def test_threads_do_not_lose_increments(self):
        def work(_):
            for _ in range(200):self.counter.press()
        with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(work,range(8)))
        self.counter.flush()
        self.assertEqual(self.counter.snapshot()['count'],1600)
    def test_two_instances_use_deltas(self):
        other=DailyCounter(self.db,lock=self.counter.lock,day_clock=lambda:self.day,clock=lambda:self.time)
        self.counter.press();other.press();other.press()
        self.counter.flush();other.flush();self.counter.flush()
        self.assertEqual(self.counter.snapshot()['count'],3)
    def test_failed_save_preserves_pending(self):
        self.counter.press()
        self.db.execute("CREATE TRIGGER fail_save BEFORE INSERT ON daily_stats BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.Error):self.counter.flush()
        self.assertEqual(self.counter.pending,1)
        self.db.execute('DROP TRIGGER fail_save');self.counter.flush()
        self.assertEqual(self.counter.snapshot()['count'],1)
    def test_restart_loads_saved_day(self):
        self.counter.press();self.counter.flush()
        reloaded=DailyCounter(self.db,day_clock=lambda:self.day,clock=lambda:self.time)
        self.assertEqual(reloaded.snapshot()['count'],1)


if __name__=='__main__': unittest.main()
