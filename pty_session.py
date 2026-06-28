import os
import re
import threading

import pyte
from winpty import PtyProcess
import logger

COLS = 220
ROWS = 40
FLUSH_DELAY = 0.6

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

    def start(self) -> None:
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        self._proc = PtyProcess.spawn(
            self._command, cwd=self._cwd, env=env, dimensions=(ROWS, COLS)
        )
        self._running = True
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
        self._flush_timer = threading.Timer(FLUSH_DELAY, self._flush)
        self._flush_timer.daemon = True
        self._flush_timer.start()

    def _flush(self) -> None:
        with self._lock:
            current = [self._screen.display[i].strip() for i in range(ROWS)]
        if self._first_flush:
            self._first_flush = False
            self._prev = current[:]
            return
        lines = []
        for old, new in zip(self._prev, current):
            if new == old or not new:
                continue
            if _DECORATION.match(new) or new.startswith('❯'):
                continue
            lines.append(new)
        self._prev = current[:]
        if lines:
            self._on_output('\n'.join(lines))

    def write(self, text: str) -> None:
        if self._proc and self._running:
            self._proc.write(text)

    def stop(self) -> None:
        self._running = False
        if self._flush_timer:
            self._flush_timer.cancel()
        if self._proc:
            try:
                self._proc.write("/exit\r")
            except Exception:
                pass
            try:
                self._proc.terminate()
            except Exception:
                pass

    @property
    def is_alive(self) -> bool:
        return self._running and self._proc is not None and self._proc.isalive()
