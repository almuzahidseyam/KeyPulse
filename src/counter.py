"""Daily counts only: never receives or stores a key's identity."""
from collections import deque
from datetime import date
import math
import threading
import time


class DailyCounter:
    def __init__(self, connection, lock=None, day_clock=date.today, clock=time.monotonic):
        self.connection = connection
        self.lock = lock or threading.RLock()
        self.day_clock, self.clock = day_clock, clock
        self.day = str(day_clock())
        self.pending = 0
        self.buckets = deque()
        self.last_press = None
        self.last_clock = None
        self.base, self.maximum = self._load(self.day)

    def _load(self, day):
        row = self.connection.execute('SELECT keystrokes, max_kpm FROM daily_stats WHERE log_date=?', (day,)).fetchone()
        return (row[0] or 0, row[1] or 0) if row else (0, 0)

    def _flush(self):
        # Add only this process's unsaved delta: another instance cannot be
        # overwritten by an absolute count saved from a stale snapshot.
        with self.connection:
            self.connection.execute('''INSERT INTO daily_stats(log_date,keystrokes,max_kpm) VALUES(?,?,?)
                ON CONFLICT(log_date) DO UPDATE SET keystrokes=COALESCE(keystrokes,0)+excluded.keystrokes,
                max_kpm=MAX(COALESCE(max_kpm,0),excluded.max_kpm)''', (self.day,self.pending,self.maximum))
            base, maximum = self._load(self.day)
        self.base, self.maximum, self.pending = base, maximum, 0

    def _advance(self):
        day = str(self.day_clock())
        if day != self.day:
            self._flush()  # If saving fails, preserve the old day's pending data.
            base, maximum = self._load(day)
            self.day, self.base, self.maximum = day, base, maximum
            self.buckets.clear()
            self.last_press = None
        now = self.clock()
        if not math.isfinite(now):
            raise ValueError('Clock must be finite')
        if self.last_clock is not None and now < self.last_clock:
            self.buckets.clear()
            self.last_press = None
        self.last_clock = now
        second = math.floor(now)
        while self.buckets and self.buckets[0][0] <= second-60:
            self.buckets.popleft()
        return now, second

    def press(self):
        with self.lock:
            now, second = self._advance()
            self.pending += 1
            if self.buckets and self.buckets[-1][0] == second:
                self.buckets[-1][1] += 1
            else:
                self.buckets.append([second,1])
            self.last_press = now
            self.maximum = max(self.maximum, sum(bucket[1] for bucket in self.buckets))

    def snapshot(self):
        with self.lock:
            now, _ = self._advance()
            return {'day':self.day, 'count':self.base+self.pending, 'maximum':self.maximum,
                    'kpm':sum(bucket[1] for bucket in self.buckets),
                    'idle':self.last_press is None or now-self.last_press>120}

    def flush(self):
        with self.lock:
            self._advance()
            self._flush()
