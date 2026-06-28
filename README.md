# Ponte Telegram ↔ Claude Code

Bot do Telegram que conecta ao [Claude Code CLI](https://claude.ai/code) via pseudo-terminal (PTY), permitindo controlar sessões do Claude remotamente pelo celular.

```
Telegram ──► bot.py ──► PTYSession (winpty) ──► claude CLI
                ▲                                      │
                └──────────── formatter ◄──────────────┘
```

## Funcionalidades

- Abre uma sessão PTY com o `claude` no diretório escolhido
- Captura o output em tempo real, remove ANSI e envia ao Telegram em blocos de código
- Repassa suas mensagens diretamente ao processo do Claude
- Detecta prompts de permissão e exibe botões inline (opções numeradas + "✏️ Digitar...")
- Sugestão de diretórios recentes ao iniciar ou continuar sessão
- Flush periódico durante streaming longo (respostas não ficam em silêncio por minutos)

## Requisitos

- **Windows** (usa `pywinpty`)
- Python 3.11+
- [Claude Code CLI](https://claude.ai/code) instalado e autenticado (`claude` disponível no PATH)
- Bot do Telegram criado via [@BotFather](https://t.me/BotFather)

## Instalação

```bash
git clone https://github.com/Ismael042/Claude_on_Telegram.git
cd Claude_on_Telegram

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt

copy .env.example .env
```

Edite o `.env` com suas credenciais (veja seção abaixo) e execute:

```bash
python bot.py
```

## Configuração (`.env`)

| Variável | Descrição |
|---|---|
| `TELEGRAM_TOKEN` | Token do bot obtido no [@BotFather](https://t.me/BotFather) |
| `ALLOWED_USER_ID` | Seu ID numérico do Telegram — obtenha com [@userinfobot](https://t.me/userinfobot) |
| `CLAUDE_DEFAULT_DIR` | Diretório padrão onde o Claude será iniciado |

**Exemplo:**
```env
TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
ALLOWED_USER_ID=987654321
CLAUDE_DEFAULT_DIR=C:\Users\voce\projetos
```

## Comandos disponíveis

| Comando | Descrição |
|---|---|
| `/start` | Inicia novo agente ou continua sessão anterior (com seleção de diretório) |
| `/stop` | Encerra a sessão ativa |
| `/status` | Verifica se há sessão ativa |
| `/clear` | Apaga as mensagens do bot no chat do Telegram |
| `/reset` | Limpa o histórico da conversa no Claude (`/clear` interno) |
| `/compact` | Comprime o contexto da sessão (`/compact` interno) |
| `/esc` | Envia tecla Escape ao Claude |
| `/interrupt` | Envia Ctrl+C (interrompe execução em andamento) |
| Qualquer texto | Enviado diretamente ao Claude |

Quando o Claude solicitar permissão, botões inline aparecem automaticamente com as opções disponíveis (ex: "1. Sim", "2. Sim, não pedir de novo", "3. Não") e um botão "✏️ Digitar..." para entrada livre.

## Segurança

O bot só responde ao `ALLOWED_USER_ID` configurado no `.env`. Qualquer outra conta é silenciosamente ignorada. **Nunca compartilhe seu `.env`.**
