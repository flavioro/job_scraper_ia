import os
import json
from typing import Dict, Any

from dotenv import load_dotenv
from google import genai

import time
from google.api_core import exceptions

def call_gemini_extract_json(
    client: genai.Client,
    model: str,
    prompt_template: str,
    page_text: str,
    url: str,
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Envia texto para Gemini com tratamento de erro 429 e modo JSON nativo.
    """
    final_prompt = prompt_template.replace("{{TEXTO_DA_VAGA}}", page_text[:1500])
    
    for attempt in range(max_retries):
        try:
            # Usando o modo de resposta JSON nativo do Gemini
            resp = client.models.generate_content(
                model=model,
                contents=final_prompt,
                config={
                    'response_mime_type': 'application/json',
                }
            )
            
            # Com response_mime_type, o resp.text já deve vir como JSON puro
            data = json.loads(resp.text)
            
            if isinstance(data, dict):
                data["url_origem"] = url
            return data

        except exceptions.ResourceExhausted as e:
            # Erro 429: Limite atingido
            wait_time = (attempt + 1) * 10  # 10s, 20s, 30s...
            print(f"Limite atingido. Tentativa {attempt+1}/{max_retries}. Aguardando {wait_time}s...")
            time.sleep(wait_time)
            
        except Exception as e:
            print(f"Erro inesperado: {e}")
            break
            
    return {"error": "Não foi possível processar após várias tentativas", "url_origem": url}

def load_prompt(prompt_path: str) -> str:
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def init_gemini_client() -> genai.Client:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não encontrado no .env")

    return genai.Client(api_key=api_key)


# def call_gemini_extract_json(
#     client: genai.Client,
#     model: str,
#     prompt_template: str,
#     page_text: str,
#     url: str
# ) -> Dict[str, Any]:
#     """
#     Envia texto para Gemini e espera um JSON puro.
#     """
#     final_prompt = prompt_template.replace("{{TEXTO_DA_VAGA}}", page_text[:5000])

#     resp = client.models.generate_content(
#         model=model,
#         contents=final_prompt,
#     )

#     raw = (resp.text or "").strip()

#     # Alguns modelos podem devolver ```json ... ```
#     raw = raw.replace("```json", "").replace("```", "").strip()

#     try:
#         data = json.loads(raw)
#     except Exception:
#         # Retry 1 vez pedindo correção
#         fix_prompt = (
#             "O texto abaixo deveria ser um JSON válido, mas está inválido.\n"
#             "Corrija e devolva APENAS um JSON válido.\n\n"
#             f"TEXTO:\n{raw}"
#         )
#         resp2 = client.models.generate_content(
#             model=model,
#             contents=fix_prompt,
#         )
#         raw2 = (resp2.text or "").strip()
#         raw2 = raw2.replace("```json", "").replace("```", "").strip()
#         data = json.loads(raw2)

#     # Adiciona URL de origem
#     if isinstance(data, dict):
#         data["url_origem"] = url

#     return data
