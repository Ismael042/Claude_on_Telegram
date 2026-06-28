import logging
import sys

_ICONS = {
    logging.DEBUG:    "🔍",
    logging.INFO:     "📋",
    logging.WARNING:  "⚠️ ",
    logging.ERROR:    "❌",
    logging.CRITICAL: "🔥",
}

# Event-specific loggers — call these directly instead of log.info("...")
def session_start(cwd: str)  -> None: _log.info("🟢 Sessão iniciada em %s", cwd)
def session_stop()           -> None: _log.info("🔴 Sessão encerrada")
def msg_received(user: str)  -> None: _log.info("📨 Mensagem de %s", user)
def msg_sent(chars: int)     -> None: _log.debug("📤 Enviado (%d chars)", chars)
def perm_prompt()            -> None: _log.info("🔐 Prompt de permissão detectado")
def unauthorized(uid: int)   -> None: _log.warning("🚫 Acesso negado — user_id=%d", uid)
def pty_exit()               -> None: _log.info("💀 PTY encerrou")
def pty_start(pid)           -> None: _log.info("🟡 PTY iniciado — PID=%s", pid)
def send_error(err: Exception) -> None: _log.error("📵 Falha ao enviar: %s", err)


class _IconFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        icon = _ICONS.get(record.levelno, "  ")
        record.levelname = f"{icon} {record.levelname:<8}"
        return super().format(record)


def setup(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_IconFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    ))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    # silencia verbosidade do httpx/telegram
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


_log = logging.getLogger("bridge")
