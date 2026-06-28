import os
import re
import subprocess
import threading
import time

import pyte
from winpty import PtyProcess
import logger

COLS = 220
ROWS = 40
FLUSH_DELAY = 0.6
MAX_FLUSH_INTERVAL = 3.0  # force a flush mid-stream so long responses don't silently buffer

_DECORATION = re.compile(r'^[\s─╴╸╌╎┄┅┆┇┈┉┊┋┌┐└┘├┤┬┴┼╭╮╰╯│▀▄█▌▐▗▖▝▘▙▛▜▟·•\-=]+$')


class PTYSession:
    def __init__(self, command: str, cwd: str, on_output):
        self._command = command
        self._cwd = cwd
        self._on_output = on_output
        self._proc: PtyProcess | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._flush_timer: threading.Timer | None = None
        self._screen = pyte.Screen(COLS, ROWS)
        self._stream = pyte.Stream(self._screen)
        self._prev: list[str] = [''] * ROWS
        self._first_flush = True
        self._ready = False
        # Per-turn deduplication: content visible before the user's message or
        # already emitted this turn — never re-emitted regardless of TUI scroll.
        self._turn_baseline: set[str] = set()
        self._turn_emitted: set[str] = set()
        self._last_emit_time: float = 0.0

    def start(self) -> None:
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        self._proc = PtyProcess.spawn(
            self._command, cwd=self._cwd, env=env, dimensions=(ROWS, COLS)
        )
        self._running = True
        logger.pty_start(getattr(self._proc, "pid", "?"))
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        while self._running:
            try:
                data = self._proc.read(4096)
                if data:
                    with self._lock:
                        self._stream.feed(data)
                    self._reset_timer()
            except EOFError:
                self._running = False
                logger.pty_exit()
                break
            except Exception:
                break

    def _reset_timer(self) -> None:
        if self._flush_timer:
            self._flush_timer.cancel()
        # Mid-stream forced flush: if Claude is streaming continuously and we
        # haven't emitted anything in MAX_FLUSH_INTERVAL, flush now so the user
        # sees intermediate output instead of silence for minutes.
        if self._ready and time.time() - self._last_emit_time > MAX_FLUSH_INTERVAL:
            self._flush()
        self._flush_timer = threading.Timer(FLUSH_DELAY, self._flush)
        self._flush_timer.daemon = True
        self._flush_timer.start()

    def _flush(self) -> None:
        with self._lock:
            current = [self._screen.display[i].strip() for i in range(ROWS)]

        if self._first_flush:
            self._first_flush = False
            self._prev = current[:]
            self._turn_baseline.update(r for r in current if r)
            return

        if not self._ready:
            for row in current:
                if row.startswith('❯') or '? for shortcuts' in row:
                    self._ready = True
                    self._prev = current[:]
                    self._turn_baseline.update(r for r in current if r)
                    break
            if not self._ready:
                self._prev = current[:]
                return

        lines = []
        for old, new in zip(self._prev, current):
            if new == old or not new:
                continue
            if _DECORATION.match(new) or new.startswith('❯'):
                continue
            if new in self._turn_baseline or new in self._turn_emitted:
                continue
            lines.append(new)
        self._prev = current[:]
        if lines:
            self._last_emit_time = time.time()
            self._turn_emitted.update(lines)
            self._on_output('\n'.join(lines))

    def write(self, text: str) -> None:
        if self._proc and self._running:
            with self._lock:
                current = [self._screen.display[i].strip() for i in range(ROWS)]
            self._prev = current[:]
            # Merge current screen + previous turn's emitted lines into the new
            # baseline so none of it reappears as "new" in the next response.
            self._turn_baseline = {r for r in current if r} | self._turn_emitted
            self._turn_emitted = set()
            # Force MAX_FLUSH_INTERVAL check on the very first chunk after this
            # write, regardless of when the previous response ended.
            self._last_emit_time = 0.0
            self._proc.write(text)

    def stop(self) -> None:
        self._running = False
        if self._flush_timer:
            self._flush_timer.cancel()
        if self._proc:
            pid = getattr(self._proc, "pid", None)
            try:
                self._proc.write("/exit\r")
            except Exception:
                pass
            time.sleep(0.4)
            try:
                self._proc.terminate()
            except Exception:
                pass
            # Force-kill the entire process tree so orphan node/claude processes don't linger
            if pid:
                try:
                    subprocess.call(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        timeout=3,
                    )
                except Exception:
                    pass

    @property
    def is_alive(self) -> bool:
        return self._running and self._proc is not None and self._proc.isalive()
