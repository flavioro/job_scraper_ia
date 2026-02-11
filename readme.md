![Python](https://img.shields.io/badge/python-3.x-blue)
![License](https://img.shields.io/github/license/flavioro/job_scraper_ia)

# Job Scraper IA (Windows + Python + Ollama)

Pipeline local em Python para coletar vagas (URLs diretas), fazer scraping robusto com fallback, extrair campos estruturados com IA local (Ollama), deduplicar e persistir histórico em SQLite, gerando exports CSV/XLSX.

> **Fonte de verdade:** `cache/jobs.db` (SQLite).  
> CSV/XLSX são exports derivados.

---

## ✅ Recursos
- Scraping robusto com:
  - fallback Jina (`r.jina.ai`)
  - fallback HTML (`requests + bs4 + lxml`)
  - retry/backoff exponencial (`tenacity`)
  - rate limit por domínio (jitter)
  - rotação de User-Agent (lista local)
- IA local com **Ollama**
  - streaming + heartbeat
  - retorno em JSON
  - sem quota / sem API paga
- Deduplicação:
  - por `(platform, job_id)` no SQLite
  - por `hash` do texto (mudança real do conteúdo)
- Export:
  - ALL (todas as vagas)
  - filtro JR/PLENO/ATIVAS

---

## Stack
- Python 3.11+ (recomendado via Conda)
- requests
- beautifulsoup4 + lxml
- tenacity
- pandas + openpyxl
- sqlite3 (nativo)
- python-dotenv
- Ollama

---

## Estrutura do Projeto

```
job_scraper_ia/
  main.py
  scraper.py
  processor.py
  utils.py
  text_cleaner.py
  db.py
  export_db.py
  logger.py
  prompts/
    prompt_extracao.txt
  cache/
    jobs.db              # gerado
    processed_urls.json  # gerado (se não ignorar)
  output/
    vagas_output_all.csv
    vagas_output_all.xlsx
    vagas_output_jr_pleno_ativas.csv
    vagas_output_jr_pleno_ativas.xlsx
  logs/
    app.log              # gerado
  .env
  config.json
  requirements.txt
  .gitignore
  README.md
```

---

## Setup (Windows)

### 1) Criar ambiente Conda
```bash
conda create -n vagas_ia python=3.11 -y
conda activate vagas_ia
```

### 2) Instalar dependências
```bash
pip install -r requirements.txt
```

---

## Ollama (IA local)

### 1) Verificar se está rodando
Abra no navegador:
- http://localhost:11434

### 2) Baixar modelo (escolha 1)

Modelo padrão (mais preciso, pode ser mais lento):
```bash
ollama pull qwen2.5:7b
```

Modelo mais rápido para MVP:
```bash
ollama pull qwen2.5:3b
```

### 3) Teste rápido
```bash
ollama run qwen2.5:7b "Responda apenas: ok"
```

---

## Configuração

### `.env` (crie na raiz do projeto)
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b

OLLAMA_TIMEOUT=900
OLLAMA_NUM_PREDICT=250
OLLAMA_TEMPERATURE=0.2
```

### `config.json` (exemplo)
```json
{
  "urls_vagas": [
    "https://fcamara.gupy.io/jobs/10803174",
    "https://boards.greenhouse.io/inter/jobs/4619021005?gh_jid=4619021005"
  ]
}
```

---

## Prompt do LLM

Arquivo: `prompts/prompt_extracao.txt`

**Importante:** usar placeholders do `string.Template`:
- `${url}`
- `${texto}`

---

## Como Rodar

```bash
python main.py
```

Ao final, o script:
- persiste/upserta no SQLite (`cache/jobs.db`)
- exporta:
  - `output/vagas_output_all.csv` e `.xlsx`
  - `output/vagas_output_jr_pleno_ativas.csv` e `.xlsx`
- grava logs em:
  - `logs/app.log`

---

## Arquitetura (alto nível)

1) Lê URLs do `config.json`
2) Normaliza URL (`normalize_url`)
3) Detecta plataforma (`detect_platform`)
4) Extrai `job_id` (`extract_job_id`)
5) Scrape robusto (`scraper.get_page_text`)
   - tenta Jina
   - fallback requests+bs4
   - retry/backoff
   - rate limit por domínio
   - UA rotation
6) Hash do conteúdo (`sha256_text`)
7) Dedupe/skip por `(platform, job_id)` + `hash` no SQLite
8) Detecta status heurístico (ativa/duvidosa/removida)
9) Reduz texto para IA (performance)
10) Chama Ollama com streaming e retorno JSON
11) Normaliza chaves (`normalize_llm_result`)
12) Upsert no SQLite
13) Export CSV/XLSX do SQLite

---

## Outputs

### ALL (todas as vagas)
- `output/vagas_output_all.csv`
- `output/vagas_output_all.xlsx`

### Filtro JR/PLENO/ATIVAS
- `output/vagas_output_jr_pleno_ativas.csv`
- `output/vagas_output_jr_pleno_ativas.xlsx`

---

## Logs

Arquivo:
- `logs/app.log`

O log registra:
- tempos de scrape e IA
- skips por cache/db
- erros com stack trace

---

## Checklist de Saúde (debug rápido)

- Ollama responde: `http://localhost:11434`
- Modelo instalado: `ollama list`
- `.env` presente e correto
- Prompt usa `${texto}` e `${url}`
- Rodar 2x deve pular IA para URLs sem mudança (hash igual)
- Ver logs em `logs/app.log`

---

## Roadmap

- Etapa 15: Testes automatizados (pytest) + fixtures
- Melhorias: extração por plataforma (Gupy/Workday/Greenhouse), parsing sem IA quando possível, reprocessamento seletivo por data.
