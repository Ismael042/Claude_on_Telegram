# Architecture — Ponte Telegram Claude

## Stack

| Camada | Tecnologia |
|---|---|
| Bot Telegram | `python-telegram-bot` v21 (async) |
| PTY Windows | `pywinpty` v2 |
| Strip ANSI | regex built-in |
| Config | `python-dotenv` |
| System tray | `pystray` + `Pillow` |
| Runtime | Python 3.12+ / Windows 11 |

---

## Estrutura de diretórios

```
Ponte Telegram Claude/
  bot.py              ← entry point; handlers Telegram + main loop
  tray.py             ← system tray; gerencia processo do bot, viewer de logs
  pty_session.py      ← PTY lifecycle; spawn, write_stdin, read_stdout (thread)
  output_buffer.py    ← batching de output (400ms / 30 linhas → flush)
  formatter.py        ← strip ANSI, chunkar em 4096 chars
  config.py           ← carrega .env (TOKEN, ALLOWED_USER_ID, default dir)
  logger.py           ← setup de logging com ícones por nível
  install.ps1         ← registra tray.py no Agendador de Tarefas (logon)
  uninstall.ps1       ← remove do agendador
  requirements.txt
  logs/               ← NÃO commitado; bot.log com rotação a 2 MB
  .env                ← NÃO commitado
  .env.example
  .gitignore
  .claude/            ← NÃO commitado (cofre-path do hook de memória)
```

---

## Fluxo de dados

```
Telegram User
    │  /claude [path] | /stop | /status | texto livre | botão inline
    ▼
bot.py — handlers async (python-telegram-bot)
    │
    ├─ cmd_claude  → instancia PTYSession + OutputBuffer → inicia processo
    ├─ cmd_stop    → força flush do buffer → termina PTYSession
    ├─ handle_message → session.write(texto + \n)
    └─ handle_callback → session.write("y\n" ou "n\n")
    │
    ▼
output_buffer.py — acumula chunks do PTY
    │  flush após 400ms de silêncio OU 30 linhas acumuladas
    ▼
formatter.py — strip_ansi() + chunk_text(max=4000)
    │
    ▼
bot.py — _send_output() → detecta prompt de permissão → envia com ou sem inline keyboard
    │
    ▼
Telegram User (mensagem em monospace)
```

---

## Módulos implementados

| Módulo | Responsabilidade |
|---|---|
| `bot` | Handlers Telegram, captura do event loop (`post_init`), roteamento I/O |
| `tray` | System tray icon (pystray); inicia/para/reinicia `bot.py` como subprocesso; janela de logs tkinter com auto-refresh |
| `PTYSession` | Spawn do processo em PTY, thread de leitura contínua, write ao stdin |
| `OutputBuffer` | Batching com timer (400ms) e limite de linhas (30); thread-safe |
| `formatter` | Strip de códigos ANSI; chunking para limite do Telegram (4000 chars) |
| `logger` | Setup de logging com ícones por nível; saída em stdout (capturada pelo tray em `logs/bot.log`) |
| `config` | Leitura de variáveis de ambiente via `.env` |

---

## Ambientes e deploy

| Ambiente | Descrição |
|---|---|
| Dev | `python bot.py` direto no terminal |
| Produção | `tray.py` via Agendador de Tarefas (`install.ps1`); sobe no logon, reinicia em crash, logs em `logs/bot.log` |

Não há staging — é ferramenta pessoal de uso único.

### Fluxo de produção

```
Windows logon
    │
    ▼
Agendador de Tarefas → pythonw.exe tray.py
    │
    ▼
tray.py (_monitor_loop, 15s delay inicial)
    │  stdout + stderr
    ├─► logs/bot.log  (rotação a 2 MB)
    │
    ▼
python.exe bot.py  [PYTHONUNBUFFERED=1, PYTHONUTF8=1]
    │
    ▼
(comportamento normal — ver fluxo de dados acima)
```

---

## Convenções

- **Auth:** `ALLOWED_USER_ID` no `.env` — qualquer update de outro user_id é ignorado silenciosamente
- **Sessão única:** só um processo PTY ativo por vez; `/stop` antes de iniciar outro
- **Permissões:** padrões `[y/n]`, `Allow this action?` etc. disparam inline keyboard; outros textos são enviados como mensagem simples
- **Commits:** não commitar sem pedido explícito; `.env` e `.claude/` sempre no `.gitignore`
