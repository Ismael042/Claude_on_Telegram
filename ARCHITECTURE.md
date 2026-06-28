# Architecture — Ponte Telegram Claude

## Stack

| Camada | Tecnologia |
|---|---|
| Bot Telegram | `python-telegram-bot` v21 (async) |
| PTY Windows | `pywinpty` v2 |
| Strip ANSI | regex built-in |
| Config | `python-dotenv` |
| Runtime | Python 3.12+ / Windows 11 |

---

## Estrutura de diretórios

```
Ponte Telegram Claude/
  bot.py              ← entry point; handlers Telegram + main loop
  pty_session.py      ← PTY lifecycle; spawn, write_stdin, read_stdout (thread)
  output_buffer.py    ← batching de output (400ms / 30 linhas → flush)
  formatter.py        ← strip ANSI, chunkar em 4096 chars
  config.py           ← carrega .env (TOKEN, ALLOWED_USER_ID, default dir)
  requirements.txt
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
| `PTYSession` | Spawn do processo em PTY, thread de leitura contínua, write ao stdin |
| `OutputBuffer` | Batching com timer (400ms) e limite de linhas (30); thread-safe |
| `formatter` | Strip de códigos ANSI; chunking para limite do Telegram (4000 chars) |
| `bot` | Handlers Telegram, captura do event loop (`post_init`), roteamento I/O |
| `config` | Leitura de variáveis de ambiente via `.env` |

---

## Ambientes e deploy

| Ambiente | Descrição |
|---|---|
| Local (dev) | `python bot.py` direto no terminal |
| Produção | Processo rodando em background no Windows (Task Scheduler ou NSSM) |

Não há staging — é ferramenta pessoal de uso único.

---

## Convenções

- **Auth:** `ALLOWED_USER_ID` no `.env` — qualquer update de outro user_id é ignorado silenciosamente
- **Sessão única:** só um processo PTY ativo por vez; `/stop` antes de iniciar outro
- **Permissões:** padrões `[y/n]`, `Allow this action?` etc. disparam inline keyboard; outros textos são enviados como mensagem simples
- **Commits:** não commitar sem pedido explícito; `.env` e `.claude/` sempre no `.gitignore`
