import time
from logger import setup_logger
import os
import json
# import pandas as pd

from utils import (
    ensure_dirs, load_json, load_cache, save_cache,
    sha256_text, basic_validate_result, now_iso,
    normalize_url, detect_platform, extract_job_id
)
from scraper import get_page_text
from processor import load_prompt, call_llm_extract_json
from text_cleaner import extract_relevant_sections, detect_status_from_text

from utils import normalize_llm_result, extract_company_slug


from db import init_db, connect, get_job_by_key, upsert_job


def _json_dump(x) -> str:
    return json.dumps(x, ensure_ascii=False)

def main():
    logger = setup_logger()
    run_start = time.time()

    ensure_dirs()
    init_db()

    config = load_json("config.json")
    urls = config.get("urls_vagas", [])
    if not urls:
        print("Nenhuma URL encontrada em config.json -> urls_vagas")
        return

    # Cache antigo ainda útil (para pular rápido sem bater DB/IA em alguns casos)
    cache_path = "cache/processed_urls.json"
    cache = load_cache(cache_path)

    prompt_path = "prompts/prompt_extracao.txt"
    if not os.path.exists(prompt_path):
        raise RuntimeError(f"Prompt não encontrado: {prompt_path}")
    prompt_template = load_prompt(prompt_path)

    provider = os.getenv("LLM_PROVIDER", "ollama")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    logger.info("=" * 70)
    logger.info(f"[{now_iso()}] Iniciando pipeline com {len(urls)} URLs")
    logger.info(f"LLM_PROVIDER: {provider}")
    logger.info(f"OLLAMA_MODEL: {model}")
    logger.info(f"OLLAMA_BASE_URL: {base_url}")
    logger.info("=" * 70)

    conn = connect()
    try:
        for i, url in enumerate(urls, start=1):
            logger.info(f"\n[{i}/{len(urls)}] URL: {url}")

            try:
                url_norm = normalize_url(url)
                platform = detect_platform(url_norm)
                job_id = extract_job_id(url_norm)

                # Scrape
                t0 = time.time()
                page_text = get_page_text(url_norm)
                scrape_ms = int((time.time() - t0) * 1000)
                logger.info(f"Scrape OK | chars={len(page_text)} | scrape_ms={scrape_ms}")
                # print(f"  - Texto coletado: {len(page_text)} chars")

                status_pre = detect_status_from_text(page_text)
                page_text_reduced = extract_relevant_sections(page_text, max_chars=9000)
                # print(f"  - Texto reduzido p/ IA: {len(page_text_reduced)} chars | status_pre={status_pre}")
                # print(
                #     f"  - Texto: bruto={len(page_text)} | reduzido={len(page_text_reduced)} | "
                #     f"delta={len(page_text_reduced)-len(page_text)} | status_pre={status_pre}"
                # )
                logger.info(
                    f"Text reduce | bruto={len(page_text)} | reduzido={len(page_text_reduced)} | "
                    f"delta={len(page_text_reduced)-len(page_text)} | status_pre={status_pre}"
                )



                text_hash = sha256_text(page_text)

                # 1) dedupe/skip via DB (principal)
                existing = None
                if platform != "unknown" and job_id:
                    existing = get_job_by_key(conn, platform, job_id)

                if existing and existing.get("content_hash") == text_hash:
                    logger.info("  - Já existe no DB com mesmo hash. Pulando IA.")
                    # ainda atualiza "last_seen" via upsert mínimo
                    rec = {
                        "platform": platform,
                        "job_id": job_id,
                        "url": url,
                        "url_norm": url_norm,
                        "content_hash": text_hash,
                        "last_seen": now_iso(),
                        "created_at": now_iso(),  # ignorado no update
                        "status": status_pre,
                        "empresa": None, "cargo": None, "localidade": None,
                        "tipo_trabalho": "desconhecido", "senioridade": "desconhecido",
                        "salario": None, "link_candidatura": None, "data_publicacao": None,
                        "score_0_100": 0, "motivo_curto": "Sem mudanças (hash igual).",
                        "requisitos_json": _json_dump([]),
                        "tecnologias_json": _json_dump([]),
                        "raw_json": _json_dump({}),
                    }
                    upsert_job(conn, rec)
                    continue

                # 2) cache auxiliar (URL norm + hash)
                cache_key = url_norm
                if cache_key in cache and cache[cache_key].get("hash") == text_hash:
                    logger.info("  - Cache local por hash igual. Pulando IA.")
                    continue

                # IA
                t1 = time.time()
                result = call_llm_extract_json(
                    prompt_template=prompt_template,
                    page_text=page_text_reduced,
                    url=url_norm,
                )
                llm_ms = int((time.time() - t1) * 1000)
                logger.info(f"LLM OK | llm_ms={llm_ms}")

                if not isinstance(result, dict):
                    result = {}

                # Normalização do resultado
                result = normalize_llm_result(result)
                result.setdefault("status", status_pre)
                result["url"] = url_norm
                result.setdefault("data_coleta", now_iso())
                
                result["_company_slug"] = extract_company_slug(url_norm)

                # Validação mínima
                if not basic_validate_result(result):
                    logger.warning("  - AVISO: retornado sem todas as chaves mínimas (salvando mesmo assim).")
                else:
                    logger.info("  - OK: validado (chaves mínimas presentes).")

                # Persistir no DB (upsert)
                rec = {
                    "platform": platform,
                    "job_id": job_id,
                    "url": url,
                    "url_norm": url_norm,
                    "content_hash": text_hash,
                    "last_seen": now_iso(),
                    "created_at": now_iso(),

                    "status": result.get("status"),
                    "empresa": result.get("empresa"),

                    "cargo": result.get("cargo"),
                    "localidade": result.get("localidade"),
                    "tipo_trabalho": result.get("tipo_trabalho") or "desconhecido",

                    "senioridade": result.get("senioridade") or "desconhecido",
                    "salario": result.get("salario"),
                    "link_candidatura": result.get("link_candidatura"),
                    "data_publicacao": result.get("data_publicacao"),
                    "score_0_100": int(result.get("score_0_100") or 0),
                    "motivo_curto": result.get("motivo_curto"),

                    "requisitos_json": _json_dump(result.get("requisitos_principais") or []),
                    "tecnologias_json": _json_dump(result.get("tecnologias") or []),
                    "raw_json": _json_dump(result),
                }
                # Se plataforma desconhecida, ainda assim gravamos (usa UNIQUE(platform,job_id); job_id fallback)
                if not rec["job_id"]:
                    rec["job_id"] = url_norm

                upsert_job(conn, rec)

                # Atualiza cache auxiliar
                cache[cache_key] = {"hash": text_hash, "last_run": now_iso(), "url_original": url}
                save_cache(cache_path, cache)
                
                total_ms = int((time.time() - run_start) * 1000)
                logger.info(f"Run finalizado | total_ms={total_ms}")

            except Exception as e:
                logger.exception(f"  - ERRO ao processar URL: {type(e).__name__}: {e}")

    finally:
        conn.close()

    # Export (CSV + XLSX) direto do DB
    import export_db
    export_db.main()


if __name__ == "__main__":
    main()
