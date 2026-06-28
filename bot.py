import asyncio
import json
import re
from pathlib import Path

from telegram import BotCommand, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import TELEGRAM_TOKEN, ALLOWED_USER_ID, CLAUDE_DEFAULT_DIR
from pty_session import PTYSession
from formatter import strip_ansi, chunk_text
import logger

logger.setup()

_PERM_PATTERN = re.compile(
    r'\[y/n\]|\(y/N\)|\[Y/n\]|\[y/N\]|Allow this action\?|Do you want to',
    re.IGNORECASE,
)
_OPTION_RE = re.compile(r'^(\d+)\.\s+(.+)$')

_RECENT_FILE = Path(__file__).parent / "recent_dirs.json"

_session: PTYSession | None = None
_loop: asyncio.AbstractEventLoop | None = None
_chat_id: int | None = None
_app: Application | None = None
_waiting_for_dir: bool = False
_waiting_for_perm_input: bool = False
_continue_mode: bool = False
_pending_dirs: list[str] = []
_bot_message_ids: list[int] = []


# ── recent dirs ──────────────────────────────────────────────────────────────

def _load_recent() -> list[str]:
    try:
        return json.loads(_RECENT_FILE.read_text()).get("dirs", [])
    except Exception:
        return []


def _save_recent(cwd: str) -> None:
    dirs = _load_recent()
    if cwd in dirs:
        dirs.remove(cwd)
    dirs.insert(0, cwd)
    _RECENT_FILE.write_text(json.dumps({"dirs": dirs[:8]}))


# ── helpers ───────────────────────────────────────────────────────────────────

def _is_authorized(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID


def _parse_menu_options(text: str) -> list[tuple[str, str]]:
    """Parse numbered options from Claude Code menus, returns [(button_label, value)]."""
    opts = []
    for line in text.split('\n'):
        m = _OPTION_RE.match(line.strip())
        if m:
            num, label = m.group(1), m.group(2)
            short = label[:28] + '…' if len(label) > 28 else label
            opts.append((f"{num}. {short}", num))
    return opts


def _schedule(coro) -> None:
    if _loop:
        asyncio.run_coroutine_threadsafe(coro, _loop)


async def _send_output(text: str) -> None:
    global _bot_message_ids
    if not _chat_id or not _app:
        return

    text = strip_ansi(text)
    if not text.strip():
        return

    has_perm = _PERM_PATTERN.search(text)
    if has_perm:
        logger.perm_prompt()

    for chunk in chunk_text(text):
        try:
            if has_perm:
                opts = _parse_menu_options(chunk)
                if opts:
                    rows = [[InlineKeyboardButton(lbl, callback_data=f"perm:{val}") for lbl, val in opts[i:i+2]]
                            for i in range(0, min(len(opts), 6), 2)]
                else:
                    rows = [[
                        InlineKeyboardButton("✅ Sim (y)", callback_data="perm:y"),
                        InlineKeyboardButton("❌ Não (n)", callback_data="perm:n"),
                    ]]
                rows.append([InlineKeyboardButton("✏️ Digitar...", callback_data="perm:custom")])
                msg = await _app.bot.send_message(
                    _chat_id,
                    f"```\n{chunk}\n```",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(rows),
                )
            else:
                msg = await _app.bot.send_message(
                    _chat_id,
                    f"```\n{chunk}\n```",
                    parse_mode="Markdown",
                )
            _bot_message_ids.append(msg.message_id)
        except Exception as e:
            logger.send_error(e)


def _launch(cwd: str, chat_id: int) -> None:
    global _session, _chat_id, _bot_message_ids
    command = "claude --continue" if _continue_mode else "claude"
    _chat_id = chat_id
    _bot_message_ids = []
    _session = PTYSession(command=command, cwd=cwd, on_output=lambda t: _schedule(_send_output(t)))
    _session.start()
    _save_recent(cwd)
    logger.session_start(cwd)


# ── handlers ──────────────────────────────────────────────────────────────────

async def _start_claude(update: Update, cwd: str) -> None:
    _launch(cwd, update.effective_chat.id)
    label = "continuado em" if _continue_mode else "iniciado em"
    await update.message.reply_text(f"Claude {label} `{cwd}`", parse_mode="Markdown")


async def cmd_claude(update: Update, context) -> None:
    global _waiting_for_dir, _continue_mode, _chat_id

    if not _is_authorized(update):
        return

    if _session and _session.is_alive:
        await update.message.reply_text("Sessão ativa. Use /stop primeiro.")
        return

    if context.args:
        _continue_mode = False
        await _start_claude(update, " ".join(context.args))
    else:
        _chat_id = update.effective_chat.id
        keyboard = [[
            InlineKeyboardButton("🆕 Novo agente", callback_data="agent:new"),
            InlineKeyboardButton("🔄 Continuar anterior", callback_data="agent:continue"),
        ]]
        await update.message.reply_text(
            "Iniciar novo agente ou continuar sessão anterior?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def cmd_stop(update: Update, context) -> None:
    global _session

    if not _is_authorized(update):
        return

    if _session:
        _session.stop()
        _session = None
        logger.session_stop()
        await update.message.reply_text("Sessão encerrada.")
    else:
        await update.message.reply_text("Nenhuma sessão ativa.")


async def cmd_status(update: Update, context) -> None:
    if not _is_authorized(update):
        return

    if _session and _session.is_alive:
        await update.message.reply_text("Status: sessão ativa.")
    else:
        await update.message.reply_text("Status: sem sessão ativa.")


async def cmd_clear(update: Update, context) -> None:
    global _bot_message_ids
    if not _is_authorized(update):
        return
    chat_id = update.effective_chat.id
    ids = _bot_message_ids[:]
    _bot_message_ids.clear()
    for msg_id in ids:
        try:
            await _app.bot.delete_message(chat_id, msg_id)
        except Exception:
            pass
    try:
        await update.message.delete()
    except Exception:
        pass


async def cmd_esc(update: Update, context) -> None:
    if not _is_authorized(update):
        return
    if not _session or not _session.is_alive:
        await update.message.reply_text("Sem sessão ativa.")
        return
    _session.write("\x1b")
    try:
        await update.message.delete()
    except Exception:
        pass


async def cmd_interrupt(update: Update, context) -> None:
    if not _is_authorized(update):
        return
    if not _session or not _session.is_alive:
        await update.message.reply_text("Sem sessão ativa.")
        return
    _session.write("\x03")
    await update.message.reply_text("⛔ Interrompido (Ctrl+C)")


async def cmd_compact(update: Update, context) -> None:
    if not _is_authorized(update):
        return
    if not _session or not _session.is_alive:
        await update.message.reply_text("Sem sessão ativa.")
        return
    _session.write("/compact\r")
    await update.message.reply_text("📦 /compact enviado")


async def handle_message(update: Update, context) -> None:
    global _waiting_for_dir, _waiting_for_perm_input

    if not _is_authorized(update):
        logger.unauthorized(update.effective_user.id)
        return

    if _waiting_for_dir:
        _waiting_for_dir = False
        await _start_claude(update, update.message.text.strip())
        return

    if not _session or not _session.is_alive:
        await update.message.reply_text("Sem sessão ativa. Use /start para iniciar.")
        return

    if _waiting_for_perm_input:
        _waiting_for_perm_input = False
        text = update.message.text.strip()
        _session.write(text + "\r")
        await update.message.reply_text(f"✏️ Enviado: `{text}`", parse_mode="Markdown")
        return

    await update.message.reply_text("⏳ Raciocinando...")
    _session.write(update.message.text + "\r")


async def handle_callback(update: Update, context) -> None:
    global _waiting_for_dir, _waiting_for_perm_input, _continue_mode, _pending_dirs

    query = update.callback_query
    await query.answer()

    if not _is_authorized(update):
        return

    data = query.data

    # ── agent selection ───────────────────────────────────────────────────────
    if data == "agent:new":
        _continue_mode = False
        _waiting_for_dir = True
        await query.edit_message_text("Em qual diretório deseja iniciar o Claude?")
        return

    if data == "agent:continue":
        _continue_mode = True
        _pending_dirs = _load_recent()
        if not _pending_dirs:
            _waiting_for_dir = True
            await query.edit_message_text("Nenhum diretório recente. Em qual deseja continuar?")
            return
        keyboard = [
            [InlineKeyboardButton(d, callback_data=f"dir:{i}")]
            for i, d in enumerate(_pending_dirs)
        ]
        keyboard.append([InlineKeyboardButton("📁 Outro diretório...", callback_data="dir:other")])
        await query.edit_message_text(
            "Selecione o projeto para continuar:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # ── directory selection ───────────────────────────────────────────────────
    if data.startswith("dir:"):
        suffix = data[4:]
        if suffix == "other":
            _waiting_for_dir = True
            await query.edit_message_text("Em qual diretório deseja continuar?")
        else:
            cwd = _pending_dirs[int(suffix)]
            label = "continuado em" if _continue_mode else "iniciado em"
            await query.edit_message_text(f"Claude {label} `{cwd}`", parse_mode="Markdown")
            _launch(cwd, query.message.chat.id)
        return

    # ── permission prompt ─────────────────────────────────────────────────────
    if not _session or not _session.is_alive:
        await query.edit_message_text("Sessão não está mais ativa.")
        return

    val = data[5:] if data.startswith("perm:") else data  # handle legacy y/n callbacks

    if val == "custom":
        _waiting_for_perm_input = True
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await query.message.reply_text("✏️ Digite sua resposta:")
        return

    _session.write(val + "\r")
    if val == "y":
        label = "✅ Sim (y)"
    elif val == "n":
        label = "❌ Não (n)"
    else:
        label = f"#{val}"
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await query.message.reply_text(f"→ Enviado: {label}")


async def post_init(application: Application) -> None:
    global _loop, _app
    _loop = asyncio.get_running_loop()
    _app = application

    await application.bot.set_my_commands([
        BotCommand("start", "Iniciar ou continuar sessão do Claude"),
        BotCommand("stop", "Encerrar sessão ativa"),
        BotCommand("status", "Ver status da sessão"),
        BotCommand("clear", "Apagar mensagens do bot no chat"),
        BotCommand("esc", "Enviar tecla Escape"),
        BotCommand("interrupt", "Interromper execução (Ctrl+C)"),
        BotCommand("compact", "Comprimir contexto (/compact)"),
    ])

    me = await application.bot.get_me()
    print(f"✅ Bot @{me.username} online — aguardando mensagens...")


def main() -> None:
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_claude))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("esc", cmd_esc))
    app.add_handler(CommandHandler("interrupt", cmd_interrupt))
    app.add_handler(CommandHandler("compact", cmd_compact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
