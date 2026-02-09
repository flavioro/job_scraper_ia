import os
import pandas as pd

from utils import (
    ensure_dirs,
    load_json,
    append_jsonl,
    load_cache,
    save_cache,
    sha256_text,
    basic_validate_result,
    to_csv_rows,
    now_iso,
)

from scraper import get_page_text
from processor import load_prompt, call_llm_extract_json
from text_cleaner import extract_relevant_sections, detect_status_from_text
from utils import normalize_url

def main():
    ensure_dirs()

    # 1) carregar config
    config = load_json("config.json")
    urls = config.get("urls_vagas", [])

    if not urls:
        print("Nenhuma URL encontrada em config.json -> urls_vagas")
        return

    # 2) saída
    out_jsonl = config["saida"]["jsonl"]
    out_csv = config["saida"]["csv"]

    # limpa output antigo (MVP)
    # if os.path.exists(out_jsonl):
    #     os.remove(out_jsonl)
    # if os.path.exists(out_csv):
    #     os.remove(out_csv)

    # 3) cache
    cache_path = "cache/processed_urls.json"
    cache = load_cache(cache_path)

    # 4) prompt
    prompt_path = "prompts/prompt_extracao.txt"
    if not os.path.exists(prompt_path):
        raise RuntimeError(f"Prompt não encontrado: {prompt_path}")
    prompt_template = load_prompt(prompt_path)

    # 5) info do LLM (Ollama)
    provider = os.getenv("LLM_PROVIDER", "ollama")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    total = len(urls)
    all_results = []

    print("=" * 70)
    print(f"[{now_iso()}] Iniciando pipeline com {total} URLs")
    print(f"LLM_PROVIDER: {provider}")
    print(f"OLLAMA_MODEL: {model}")
    print(f"OLLAMA_BASE_URL: {base_url}")
    print("=" * 70)

    for i, url in enumerate(urls, start=1):
        print(f"\n[{i}/{total}] URL: {url}")

        try:
            page_text = get_page_text(url)
            
            url_norm = normalize_url(url)

            # status prévio baseado no texto bruto
            status_pre = detect_status_from_text(page_text)
            
            # corta/limpa texto para acelerar MUITO a IA
            page_text_reduced = extract_relevant_sections(page_text, max_chars=9000)
            
            print(f"  - Texto reduzido p/ IA: {len(page_text_reduced)} chars | status_pre={status_pre}")

            
            text_hash = sha256_text(page_text)

            # cache: se URL já foi processada com mesmo hash, pula
            # if url in cache and cache[url].get("hash") == text_hash:
            #     print("  - Já processada (cache por hash). Pulando.")
            #     continue
            cache_key = url_norm
            if cache_key in cache and cache[cache_key].get("hash") == text_hash:
                print("  - Já processada (cache por hash). Pulando.")
                continue
            
            cache[cache_key] = {"hash": text_hash, "last_run": now_iso(), "url_original": url}        

            print(f"  - Texto coletado: {len(page_text)} chars")

            # result = call_llm_extract_json(
            #     prompt_template=prompt_template,
            #     page_text=page_text,
            #     url=url,
            # )
            
            result = call_llm_extract_json(
                prompt_template=prompt_template,
                page_text=page_text_reduced,
                url=url_norm,
            )

            # se o LLM não definiu status, usamos o pré
            if isinstance(result, dict):
                result.setdefault("status", status_pre)
                result["url"] = url_norm
                result.setdefault("data_coleta", now_iso())

            if not basic_validate_result(result):
                print("  - AVISO: JSON retornado sem todas as chaves mínimas.")
                print("  - Salvando no JSONL mesmo assim (debug).")
            else:
                print("  - OK: JSON validado (chaves mínimas presentes).")

            # salva no jsonl
            append_jsonl(out_jsonl, result)

            # atualiza cache
            cache[url] = {"hash": text_hash, "last_run": now_iso()}
            save_cache(cache_path, cache)

            all_results.append(result)

        except Exception as e:
            print(f"  - ERRO ao processar URL: {type(e).__name__}: {e}")

    # 6) gerar CSV
    if all_results:
        rows = to_csv_rows(all_results)
        df = pd.DataFrame(rows)
        df.to_csv(out_csv, index=False, encoding="utf-8-sig")

        print("\n" + "=" * 70)
        print("Finalizado. Resultados:")
        print(f"- JSONL: {out_jsonl}")
        print(f"- CSV:   {out_csv}")
        print("=" * 70)
    else:
        print("\nNenhum resultado gerado (verifique URLs, bloqueios e o cache).")


if __name__ == "__main__":
    main()
