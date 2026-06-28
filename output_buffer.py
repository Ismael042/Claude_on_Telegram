import threading


class OutputBuffer:
    def __init__(self, flush_callback, delay: float = 0.4, max_lines: int = 30):
        self._buffer: list[str] = []
        self._lock = threading.Lock()
        self._flush_callback = flush_callback
        self._delay = delay
        self._max_lines = max_lines
        self._timer: threading.Timer | None = None

    def append(self, text: str) -> None:
        with self._lock:
            self._buffer.append(text)
            line_count = ''.join(self._buffer).count('\n')

        if line_count >= self._max_lines:
            self._cancel_timer()
            self._do_flush()
        else:
            self._reset_timer()

    def force_flush(self) -> None:
        self._cancel_timer()
        self._do_flush()

    def _reset_timer(self) -> None:
        self._cancel_timer()
        self._timer = threading.Timer(self._delay, self._do_flush)
        self._timer.daemon = True
        self._timer.start()

    def _cancel_timer(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _do_flush(self) -> None:
        with self._lock:
            if not self._buffer:
                return
            content = ''.join(self._buffer)
            self._buffer.clear()
        self._flush_callback(content)
