from dotenv import load_dotenv
load_dotenv()

import os
import time
import json
from typing import Dict, Any

import requests
from string import Template

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "900"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "450"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))


def load_prompt(prompt_path: str) -> str:
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def _ollama_generate(
    base_url: str,
    model: str,
    prompt: str,
    timeout: int = 120,
) -> str:
    """
    Chama o Ollama local: POST /api/generate
    Retorna o texto final (não-stream).
    """
    url = base_url.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2
        }
    }
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return (data.get("response") or "").strip()


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    """
    Tenta extrair JSON mesmo se o modelo devolver lixo antes/depois.
    Estratégia MVP: pega o primeiro '{' e o último '}'.
    """
    text = text.strip().replace("```json", "").replace("```", "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Não encontrei JSON no retorno do modelo.")
    candidate = text[start:end+1]
    return json.loads(candidate)

def _safe_json_loads(s: str):
    try:
        return json.loads(s)
    except Exception:
        return None

def call_llm_extract_json(prompt_template: str, page_text: str, url: str) -> dict:
    prompt = Template(prompt_template).safe_substitute(texto=page_text, url=url)

    endpoint = f"{OLLAMA_BASE_URL}/api/generate"
    timeout = (10, OLLAMA_TIMEOUT)

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": True,
        "format": "json",
        "options": {
            "temperature": OLLAMA_TEMPERATURE,
            "num_predict": OLLAMA_NUM_PREDICT,
            # stop ajuda MUITO a cortar quando o modelo começa a "explicar"
            "stop": ["\n\n", "```"],
        },
    }

    chunks = []
    last_beat = time.time()
    start = time.time()
    got_any = False

    print("  - IA (Ollama): iniciando geração...")

    with requests.post(endpoint, json=payload, stream=True, timeout=timeout) as r:
        r.raise_for_status()

        for line in r.iter_lines(decode_unicode=True):
            now = time.time()

            # heartbeat a cada 3s, mesmo se ainda não chegou nada
            if now - last_beat >= 3:
                elapsed = int(now - start)
                print(f"  - IA (Ollama): rodando... {elapsed}s | chars_recebidos={sum(len(c) for c in chunks)}")
                last_beat = now

            if not line:
                continue

            obj = _safe_json_loads(line)
            if not obj:
                continue

            if obj.get("response"):
                got_any = True
                chunks.append(obj["response"])

            if obj.get("done") is True:
                break

    raw = "".join(chunks).strip()

    if not got_any:
        # isso indica que o servidor não emitiu nada durante todo o tempo
        return {
            "cargo": None,
            "empresa": None,
            "localidade": None,
            "tipo_trabalho": "desconhecido",
            "senioridade": "desconhecido",
            "requisitos_principais": [],
            "tecnologias": [],
            "salario": None,
            "link_candidatura": None,
            "data_publicacao": None,
            "score_0_100": 0,
            "motivo_curto": "Ollama não retornou chunks (sem streaming).",
            "_raw_llm": raw[:2000],
            "url": url,
        }

    parsed = _safe_json_loads(raw)
    if isinstance(parsed, dict):
        return parsed

    # fallback: extrair json entre { ... }
    s = raw.find("{")
    e = raw.rfind("}")
    if s != -1 and e != -1 and e > s:
        parsed2 = _safe_json_loads(raw[s:e+1])
        if isinstance(parsed2, dict):
            return parsed2

    return {
        "cargo": None,
        "empresa": None,
        "localidade": None,
        "tipo_trabalho": "desconhecido",
        "senioridade": "desconhecido",
        "requisitos_principais": [],
        "tecnologias": [],
        "salario": None,
        "link_candidatura": None,
        "data_publicacao": None,
        "score_0_100": 0,
        "motivo_curto": "LLM retornou texto não-JSON.",
        "_raw_llm": raw[:4000],
        "url": url,
    }


# def call_llm_extract_json(prompt_template: str, page_text: str, url: str) -> dict:
#     """
#     Chama Ollama de forma robusta:
#     - streaming para evitar ReadTimeout de 'silêncio'
#     - limita num_predict
#     - tenta parsear JSON final
#     """
#     # prompt = prompt_template.format(texto=page_text, url=url)
#     prompt = Template(prompt_template).safe_substitute(
#     texto=page_text,
#     url=url
# )

#     payload = {
#         "model": OLLAMA_MODEL,
#         "prompt": prompt,
#         "stream": True,
#         # força o Ollama a tentar entregar JSON "puro" (quando suportado pelo modelo)
#         "format": "json",
#         "options": {
#             "temperature": OLLAMA_TEMPERATURE,
#             "num_predict": OLLAMA_NUM_PREDICT,
#         },
#     }

#     endpoint = f"{OLLAMA_BASE_URL}/api/generate"

#     # connect timeout curto; read timeout longo
#     timeout = (10, OLLAMA_TIMEOUT)

#     chunks = []
#     try:
#         with requests.post(endpoint, json=payload, stream=True, timeout=timeout) as r:
#             r.raise_for_status()
#             for line in r.iter_lines(decode_unicode=True):
#                 if not line:
#                     continue
#                 # cada linha é um JSON com {"response": "...", "done": false/true, ...}
#                 obj = _safe_json_loads(line)
#                 if not obj:
#                     continue
#                 if "response" in obj and obj["response"]:
#                     chunks.append(obj["response"])
#                 if obj.get("done") is True:
#                     break
#     except requests.exceptions.ReadTimeout:
#         raise  # vai aparecer no main.py com o tipo correto
#     except Exception as e:
#         raise RuntimeError(f"Falha ao chamar Ollama em {endpoint}: {e}")

#     raw = "".join(chunks).strip()

#     # tenta parsear o JSON (como dict)
#     parsed = _safe_json_loads(raw)
#     if isinstance(parsed, dict):
#         return parsed

#     # fallback: tenta extrair JSON se veio com lixo
#     # (simples e efetivo pro MVP)
#     start = raw.find("{")
#     end = raw.rfind("}")
#     if start != -1 and end != -1 and end > start:
#         maybe = raw[start : end + 1]
#         parsed2 = _safe_json_loads(maybe)
#         if isinstance(parsed2, dict):
#             return parsed2

#     # se não parseou, devolve algo debugável
#     return {
#         "empresa": "",
#         "titulo_vaga": "",
#         "local": "",
#         "modelo": "",
#         "senioridade": "",
#         "plataforma": "",
#         "url": url,
#         "data_coleta": "",
#         "status": "duvidosa",
#         "observacoes": f"LLM não retornou JSON parseável. Raw (inicio): {raw[:300]}",
#         "_raw_llm": raw[:4000],
#     }


# def _safe_json_loads(s: str):
#     try:
#         return json.loads(s)
#     except Exception:
#         return None
