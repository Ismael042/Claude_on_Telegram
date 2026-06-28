# Ponte Telegram ↔ Claude Code

Bot do Telegram que conecta ao [Claude Code CLI](https://claude.ai/code) via pseudo-terminal (PTY), permitindo controlar sessões do Claude remotamente pelo celular.

## Como funciona

```
Telegram ──► bot.py ──► PTYSession (winpty) ──► claude CLI
                ▲                                      │
                └──── OutputBuffer ◄── formatter ◄────┘
```

- Abre uma sessão PTY com o `claude` no diretório configurado
- Captura o output em tempo real, remove códigos ANSI e envia ao Telegram em blocos
- Repassa suas mensagens do Telegram diretamente para o processo do Claude
- Detecta prompts de permissão (`[y/n]`, `Allow this action?`) e exibe botões inline no chat

## Requisitos

- Windows (usa `pywinpty`)
- Python 3.11+
- Claude Code CLI instalado e autenticado (`claude` no PATH)
- Bot do Telegram criado via [@BotFather](https://t.me/BotFather)

## Instalação

```bash
git clone https://github.com/seu-usuario/ponte-telegram-claude
cd ponte-telegram-claude

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt

copy .env.example .env
# edite o .env com suas credenciais
```

## Configuração (`.env`)

| Variável | Descrição |
|---|---|
| `TELEGRAM_TOKEN` | Token do bot obtido no BotFather |
| `ALLOWED_USER_ID` | Seu ID numérico do Telegram (use [@userinfobot](https://t.me/userinfobot)) |
| `CLAUDE_DEFAULT_DIR` | Diretório padrão onde o Claude será iniciado |

## Uso

```bash
python bot.py
```

| Comando | Descrição |
|---|---|
| `/claude` | Inicia uma sessão do Claude no diretório padrão |
| `/claude C:\meu\projeto` | Inicia em um diretório específico |
| `/stop` | Encerra a sessão ativa |
| `/status` | Verifica se há sessão ativa |
| Qualquer texto | Enviado diretamente ao Claude |

Quando o Claude pedir confirmação, botões **Sim (y)** e **Não (n)** aparecem automaticamente no chat.

## Segurança

O bot só responde ao `ALLOWED_USER_ID` configurado no `.env`. Qualquer outra conta é silenciosamente ignorada.
