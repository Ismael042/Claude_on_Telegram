import re

_ANSI = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text: str) -> str:
    return _ANSI.sub('', text)

def chunk_text(text: str, max_len: int = 4000) -> list[str]:
    chunks = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    return [c for c in chunks if c.strip()]
