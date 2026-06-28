import asyncio
import re
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

_session: PTYSession | None = None
_loop: asyncio.AbstractEventLoop | None = None
_chat_id: int | None = None
_app: Application | None = None
_waiting_for_dir: bool = False


def _is_authorized(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID


def _schedule(coro) -> None:
    if _loop:
        asyncio.run_coroutine_threadsafe(coro, _loop)


async def _send_output(text: str) -> None:
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
                keyboard = [[
                    InlineKeyboardButton("✅ Sim (y)", callback_data="y"),
                    InlineKeyboardButton("❌ Não (n)", callback_data="n"),
                ]]
                await _app.bot.send_message(
                    _chat_id,
                    f"```\n{chunk}\n```",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            else:
                await _app.bot.send_message(
                    _chat_id,
                    f"```\n{chunk}\n```",
                    parse_mode="Markdown",
                )
        except Exception as e:
            logger.send_error(e)


async def _start_claude(update: Update, cwd: str) -> None:
    global _session, _buffer, _chat_id

    _chat_id = update.effective_chat.id
    _session = PTYSession(command="claude", cwd=cwd, on_output=lambda t: _schedule(_send_output(t)))
    _session.start()
    logger.session_start(cwd)
    await update.message.reply_text(f"Claude iniciado em `{cwd}`", parse_mode="Markdown")


async def cmd_claude(update: Update, context) -> None:
    global _waiting_for_dir, _chat_id

    if not _is_authorized(update):
        return

    if _session and _session.is_alive:
        await update.message.reply_text("Sessão ativa. Use /stop primeiro.")
        return

    if context.args:
        await _start_claude(update, " ".join(context.args))
    else:
        _waiting_for_dir = True
        _chat_id = update.effective_chat.id
        await update.message.reply_text("Em qual diretório deseja iniciar o Claude?")


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


async def handle_message(update: Update, context) -> None:
    global _waiting_for_dir

    if not _is_authorized(update):
        logger.unauthorized(update.effective_user.id)
        return

    if _waiting_for_dir:
        _waiting_for_dir = False
        await _start_claude(update, update.message.text.strip())
        return

    if not _session or not _session.is_alive:
        await update.message.reply_text("Sem sessão ativa. Use /claude para iniciar.")
        return

    _session.write(update.message.text + "\r")


async def handle_callback(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()

    if not _is_authorized(update):
        return

    if not _session or not _session.is_alive:
        await query.edit_message_text("Sessão não está mais ativa.")
        return

    _session.write(query.data + "\r")


async def post_init(application: Application) -> None:
    global _loop, _app
    _loop = asyncio.get_running_loop()
    _app = application
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
