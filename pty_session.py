import threading
from winpty import PtyProcess


class PTYSession:
    def __init__(self, command: str, cwd: str, on_output):
        self._command = command
        self._cwd = cwd
        self._on_output = on_output
        self._proc: PtyProcess | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._proc = PtyProcess.spawn(self._command, cwd=self._cwd, dimensions=(40, 200))
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        while self._running:
            try:
                data = self._proc.read(4096)
                if data:
                    self._on_output(data)
            except EOFError:
                self._running = False
                break
            except Exception:
                break

    def write(self, text: str) -> None:
        if self._proc and self._running:
            self._proc.write(text)

    def stop(self) -> None:
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass

    @property
    def is_alive(self) -> bool:
        return self._running and self._proc is not None and self._proc.isalive()
