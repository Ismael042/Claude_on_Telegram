import os
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext

import pystray
from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).parent
PYTHON = BASE_DIR / ".venv" / "Scripts" / "python.exe"
PYTHON_W = BASE_DIR / ".venv" / "Scripts" / "pythonw.exe"
BOT_SCRIPT = BASE_DIR / "bot.py"
LOG_FILE = BASE_DIR / "logs" / "bot.log"
LOG_MAX_BYTES = 2 * 1024 * 1024   # rotaciona ao chegar em 2 MB
LOG_KEEP_BYTES = 512 * 1024        # mantém os últimos 512 KB

_process: subprocess.Popen | None = None
_paused = False
_icon: pystray.Icon | None = None
_lock = threading.Lock()


# ── ícone ────────────────────────────────────────────────────────────────────

def _make_icon(running: bool) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bg = "#22c55e" if running else "#ef4444"
    d.ellipse([4, 4, 60, 60], fill=bg)
    # letra T
    d.rectangle([20, 18, 44, 24], fill="white")
    d.rectangle([29, 24, 35, 46], fill="white")
    return img


# ── processo ─────────────────────────────────────────────────────────────────

def _is_running() -> bool:
    return _process is not None and _process.poll() is None


def _rotate_log() -> None:
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > LOG_MAX_BYTES:
        data = LOG_FILE.read_bytes()
        LOG_FILE.write_bytes(data[-LOG_KEEP_BYTES:])


def _start_bot() -> None:
    global _process
    with _lock:
        if _is_running():
            return
        LOG_FILE.parent.mkdir(exist_ok=True)
        _rotate_log()
        log_fh = open(LOG_FILE, "ab")
        _process = subprocess.Popen(
            [str(PYTHON), str(BOT_SCRIPT)],
            cwd=str(BASE_DIR),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1"},
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    _update_icon()


def _stop_bot() -> None:
    global _process
    with _lock:
        if _process and _process.poll() is None:
            _process.terminate()
            try:
                _process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _process.kill()
        _process = None
    _update_icon()


def _restart_bot() -> None:
    _stop_bot()
    time.sleep(0.5)
    _start_bot()


def _update_icon() -> None:
    if not _icon:
        return
    running = _is_running()
    _icon.icon = _make_icon(running)
    if _paused:
        status = "Pausado"
    else:
        status = "Rodando" if running else "Parado"
    _icon.title = f"Telegram Bot — {status}"


# ── janela de logs ────────────────────────────────────────────────────────────

def _open_logs() -> None:
    def _build() -> None:
        root = tk.Tk()
        root.title("Telegram Claude Bot — Logs")
        root.geometry("960x560")
        root.configure(bg="#1e1e1e")

        text = scrolledtext.ScrolledText(
            root, bg="#1e1e1e", fg="#d4d4d4",
            font=("Consolas", 10), wrap=tk.WORD, state=tk.DISABLED,
        )
        text.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 0))

        text.tag_configure("green",  foreground="#22c55e")
        text.tag_configure("red",    foreground="#ef4444")
        text.tag_configure("yellow", foreground="#eab308")
        text.tag_configure("blue",   foreground="#60a5fa")
        text.tag_configure("dim",    foreground="#6b7280")

        auto_var = tk.BooleanVar(value=True)

        def _load() -> None:
            text.configure(state=tk.NORMAL)
            text.delete("1.0", tk.END)
            if LOG_FILE.exists():
                content = LOG_FILE.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines(keepends=True)[-600:]
                for line in lines:
                    if any(c in line for c in ("🟢", "✅")):
                        tag = "green"
                    elif any(c in line for c in ("❌", "🔥", "💀", "🔴")):
                        tag = "red"
                    elif any(c in line for c in ("⚠️", "🔐", "🚫")):
                        tag = "yellow"
                    elif any(c in line for c in ("📨", "📤", "🟡")):
                        tag = "blue"
                    elif "httpx" in line or "telegram" in line:
                        tag = "dim"
                    else:
                        tag = ""
                    text.insert(tk.END, line, tag)
                text.see(tk.END)
            else:
                text.insert(tk.END, "(sem logs ainda)")
            text.configure(state=tk.DISABLED)

        def _schedule() -> None:
            if root.winfo_exists() and auto_var.get():
                _load()
                root.after(3000, _schedule)

        # barra inferior
        bar = tk.Frame(root, bg="#2d2d2d", pady=5)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        def _btn(label: str, cmd) -> None:
            tk.Button(bar, text=label, command=cmd, bg="#3c3c3c", fg="#d4d4d4",
                      relief=tk.FLAT, padx=10, pady=3, cursor="hand2"
                      ).pack(side=tk.LEFT, padx=4)

        def _clear_log() -> None:
            LOG_FILE.write_bytes(b"")
            _load()

        _btn("Atualizar", _load)
        _btn("Limpar log", _clear_log)
        tk.Checkbutton(
            bar, text="Auto (3s)", variable=auto_var, bg="#2d2d2d", fg="#d4d4d4",
            selectcolor="#3c3c3c", activebackground="#2d2d2d",
            command=lambda: _schedule() if auto_var.get() else None,
        ).pack(side=tk.LEFT, padx=4)

        status_var = tk.StringVar()

        def _tick_status() -> None:
            s = "Rodando" if _is_running() else "Parado"
            size = f"{LOG_FILE.stat().st_size // 1024} KB" if LOG_FILE.exists() else "—"
            status_var.set(f"Bot: {s}   Log: {size}   {LOG_FILE}")
            if root.winfo_exists():
                root.after(2000, _tick_status)

        tk.Label(bar, textvariable=status_var, bg="#2d2d2d", fg="#6b7280",
                 font=("Consolas", 9)).pack(side=tk.RIGHT, padx=8)

        _load()
        _schedule()
        _tick_status()
        root.mainloop()

    threading.Thread(target=_build, daemon=True).start()


# ── loop de monitoramento ─────────────────────────────────────────────────────

def _monitor_loop() -> None:
    time.sleep(15)  # aguarda rede subir após logon
    while True:
        if not _paused and not _is_running():
            _start_bot()
        _update_icon()
        time.sleep(10)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    global _icon, _paused

    LOG_FILE.parent.mkdir(exist_ok=True)

    def on_toggle_pause(item: pystray.MenuItem) -> None:
        global _paused
        _paused = not _paused
        if _paused:
            _stop_bot()
        else:
            _start_bot()

    menu = pystray.Menu(
        pystray.MenuItem("Ver Logs", lambda: _open_logs(), default=True),
        pystray.MenuItem(
            "Reiniciar",
            lambda: threading.Thread(target=_restart_bot, daemon=True).start(),
        ),
        pystray.MenuItem(
            lambda item: "Pausar bot" if not _paused else "Retomar bot",
            on_toggle_pause,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair", lambda: (_stop_bot(), _icon.stop())),
    )

    _icon = pystray.Icon(
        "telegram-bot", _make_icon(False), "Telegram Bot — Iniciando", menu
    )
    threading.Thread(target=_monitor_loop, daemon=True).start()
    _icon.run()


if __name__ == "__main__":
    main()
