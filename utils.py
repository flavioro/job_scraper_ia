import os
import json
import hashlib
from datetime import datetime
from typing import Any, Dict, List
import time
import random
from urllib.parse import urlparse, urlunparse
import re

DEFAULT_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/121.0.0.0 Safari/537.36",
]

def detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "gupy.io" in host:
        return "gupy"
    if "linkedin.com" in host:
        return "linkedin"
    if "indeed." in host:
        return "indeed"
    return "unknown"

def extract_job_id(url: str) -> str:
    """
    Extrai identificador estável.
    Para Gupy:
      https://empresa.gupy.io/jobs/10803174 -> 10803174
    Fallback: último segmento do path.
    """
    parsed = urlparse(url)
    path = parsed.path.lower()

    # Gupy padrão
    m = re.search(r"/jobs/(\d+)", path)
    if m:
        return m.group(1)

    # fallback: procura um número "grande" em qualquer lugar do path
    m2 = re.search(r"(\d{6,})", path)
    if m2:
        return m2.group(1)

    parts = [p for p in path.split("/") if p]
    if parts:
        return parts[-1]

    return parsed.netloc.lower()

def pick_user_agent() -> str:
    return random.choice(DEFAULT_UAS)

def normalize_url(url: str) -> str:
    """
    Normaliza URL para dedupe:
    - remove fragment
    - remove trailing slash (exceto raiz)
    """
    p = urlparse(url.strip())
    p = p._replace(fragment="")
    norm = urlunparse(p)
    if norm.endswith("/") and len(norm) > len(p.scheme) + 3:
        norm = norm[:-1]
    return norm

class DomainRateLimiter:
    """
    Rate limit por domínio com jitter.
    Ex.: min_interval=1.2 => no máximo ~0.8 req/s por domínio.
    """
    def __init__(self, min_interval: float = 1.2, jitter: float = 0.25):
        self.min_interval = float(min_interval)
        self.jitter = float(jitter)
        self._last = {}  # domain -> time

    def wait(self, url: str):
        domain = urlparse(url).netloc.lower()
        now = time.time()
        last = self._last.get(domain, 0.0)
        elapsed = now - last
        target = self.min_interval + random.uniform(0, self.jitter)
        if elapsed < target:
            time.sleep(target - elapsed)
        self._last[domain] = time.time()

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_dirs():
    os.makedirs("output", exist_ok=True)
    os.makedirs("cache", exist_ok=True)
    os.makedirs("prompts", exist_ok=True)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def append_jsonl(path: str, obj: Dict[str, Any]):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def load_cache(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        return load_json(path)
    except Exception:
        return {}


def save_cache(path: str, cache: Dict[str, Any]):
    save_json(path, cache)


def basic_validate_result(result: Dict[str, Any]) -> bool:
    """
    Validação MVP: garante que é um dict e tem chaves mínimas.
    """
    required_keys = [
        "cargo",
        "empresa",
        "localidade",
        "tipo_trabalho",
        "senioridade",
        "requisitos_principais",
        "tecnologias",
        "salario",
        "link_candidatura",
        "data_publicacao",
        "score_0_100",
        "motivo_curto",
    ]
    if not isinstance(result, dict):
        return False
    for k in required_keys:
        if k not in result:
            return False
    return True


def to_csv_rows(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Converte para linhas simples, amigáveis pro Excel.
    """
    rows = []
    for r in results:
        rows.append({
            "cargo": r.get("cargo"),
            "empresa": r.get("empresa"),
            "localidade": r.get("localidade"),
            "tipo_trabalho": r.get("tipo_trabalho"),
            "senioridade": r.get("senioridade"),
            "salario": r.get("salario"),
            "link_candidatura": r.get("link_candidatura"),
            "score_0_100": r.get("score_0_100"),
            "motivo_curto": r.get("motivo_curto"),
            "tecnologias": ", ".join(r.get("tecnologias") or []),
            "requisitos_principais": " | ".join(r.get("requisitos_principais") or []),
            "data_publicacao": r.get("data_publicacao"),
            "url": r.get("url") or r.get("url_origem"),
        })
    return rows

def normalize_llm_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normaliza chaves para o schema padrão do projeto (cargo/localidade/tipo_trabalho...).
    Mantém compatibilidade com respostas que venham como titulo_vaga/local/modelo etc.
    """
    if not isinstance(result, dict):
        return {}

    # aliases comuns
    if "cargo" not in result and "titulo_vaga" in result:
        result["cargo"] = result.get("titulo_vaga")

    if "localidade" not in result and "local" in result:
        result["localidade"] = result.get("local")

    if "tipo_trabalho" not in result:
        # alguns modelos retornam "modelo"
        if "modelo" in result:
            result["tipo_trabalho"] = result.get("modelo")
        else:
            result["tipo_trabalho"] = "desconhecido"

    if "senioridade" not in result:
        result["senioridade"] = "desconhecido"

    if "requisitos_principais" not in result or result.get("requisitos_principais") is None:
        result["requisitos_principais"] = []

    if "tecnologias" not in result or result.get("tecnologias") is None:
        result["tecnologias"] = []

    # campos opcionais padrão
    result.setdefault("empresa", None)
    result.setdefault("salario", None)
    result.setdefault("link_candidatura", None)
    result.setdefault("data_publicacao", None)
    result.setdefault("score_0_100", 0)
    result.setdefault("motivo_curto", "")

    return result

def extract_company_slug(url: str) -> str:
    """
    Para Gupy: empresa.gupy.io -> empresa
    """
    host = urlparse(url).netloc.lower()
    if host.endswith(".gupy.io"):
        return host.split(".gupy.io")[0]
    return host