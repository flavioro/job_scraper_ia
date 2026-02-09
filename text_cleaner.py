import re

SECTION_HINTS = [
    "responsabilidades", "atribuições", "atividades",
    "requisitos", "qualificações", "desejável", "diferenciais",
    "benefícios", "beneficios",
    "descrição", "descricao", "sobre a vaga", "sobre nós", "sobre a empresa",
    "local", "localidade", "modelo", "remoto", "híbrido", "presencial", "hibrido",
    "salário", "salario",
]

REMOVAL_HINTS = [
    "vaga encerrada", "oportunidade encerrada", "inscrições encerradas",
    "não está mais disponível", "nao esta mais disponivel",
    "job is no longer available", "position is no longer available",
    "404", "página não encontrada", "pagina nao encontrada",
]

def detect_status_from_text(text: str) -> str:
    t = (text or "").lower()
    for h in REMOVAL_HINTS:
        if h in t:
            return "removida"
    if len(t.strip()) < 400:
        return "duvidosa"
    return "ativa"

def clean_text(text: str) -> str:
    """Limpeza leve (sem destruir conteúdo útil)."""
    if not text:
        return ""
    t = text

    # Normaliza espaços
    t = t.replace("\r\n", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)

    # Remove linhas muito repetitivas (heurística simples)
    lines = [ln.strip() for ln in t.split("\n")]
    filtered = []
    for ln in lines:
        if not ln:
            continue
        if len(ln) <= 2:
            continue
        filtered.append(ln)
    return "\n".join(filtered)

def extract_relevant_sections(text: str, max_chars: int = 9000) -> str:
    """
    Reduz texto mantendo partes relevantes, evitando duplicar trechos.
    """
    t = clean_text(text)
    if not t:
        return ""

    lines = t.split("\n")

    head_lines = lines[:40]
    mid_lines = lines[40:220]

    chosen_lines = []
    for ln in lines:
        low = ln.lower()
        if any(h in low for h in SECTION_HINTS):
            chosen_lines.append(ln)

    # monta e deduplica mantendo ordem
    combined = head_lines + [""] + mid_lines + [""] + chosen_lines[:200]

    seen = set()
    out_lines = []
    for ln in combined:
        key = ln.strip().lower()
        if not key:
            # mantém separadores de bloco (vazios) com parcimônia
            if out_lines and out_lines[-1] != "":
                out_lines.append("")
            continue
        if key in seen:
            continue
        seen.add(key)
        out_lines.append(ln)

    out = "\n".join(out_lines).strip()

    if len(out) > max_chars:
        out = out[:max_chars] + "\n\n[TRUNCADO]"

    return out
