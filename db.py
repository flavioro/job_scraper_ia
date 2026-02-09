import sqlite3
from typing import Optional, Dict, Any, List

DB_PATH = "cache/jobs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    platform TEXT,
    job_id TEXT,
    url TEXT,
    url_norm TEXT,

    content_hash TEXT,
    last_seen TEXT,
    created_at TEXT,

    status TEXT,
    empresa TEXT,
    cargo TEXT,
    localidade TEXT,
    tipo_trabalho TEXT,
    senioridade TEXT,
    salario TEXT,
    link_candidatura TEXT,
    data_publicacao TEXT,
    score_0_100 INTEGER,
    motivo_curto TEXT,

    requisitos_json TEXT,
    tecnologias_json TEXT,

    raw_json TEXT,

    UNIQUE(platform, job_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_url_norm ON jobs(url_norm);
CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen);
"""

def connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db(db_path: str = DB_PATH) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

def get_job_by_key(conn: sqlite3.Connection, platform: str, job_id: str) -> Optional[Dict[str, Any]]:
    cur = conn.execute(
        "SELECT platform, job_id, content_hash, last_seen, url_norm FROM jobs WHERE platform=? AND job_id=?",
        (platform, job_id),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "platform": row[0],
        "job_id": row[1],
        "content_hash": row[2],
        "last_seen": row[3],
        "url_norm": row[4],
    }

def upsert_job(conn: sqlite3.Connection, rec: Dict[str, Any]) -> None:
    """
    Upsert por (platform, job_id). Mantém histórico via raw_json/last_seen.
    """
    conn.execute(
        """
        INSERT INTO jobs (
            platform, job_id, url, url_norm,
            content_hash, last_seen, created_at,
            status, empresa, cargo, localidade, tipo_trabalho, senioridade,
            salario, link_candidatura, data_publicacao,
            score_0_100, motivo_curto,
            requisitos_json, tecnologias_json,
            raw_json
        ) VALUES (
            :platform, :job_id, :url, :url_norm,
            :content_hash, :last_seen, :created_at,
            :status, :empresa, :cargo, :localidade, :tipo_trabalho, :senioridade,
            :salario, :link_candidatura, :data_publicacao,
            :score_0_100, :motivo_curto,
            :requisitos_json, :tecnologias_json,
            :raw_json
        )
        ON CONFLICT(platform, job_id) DO UPDATE SET
            url=excluded.url,
            url_norm=excluded.url_norm,
            content_hash=excluded.content_hash,
            last_seen=excluded.last_seen,
            status=excluded.status,
            empresa=excluded.empresa,
            cargo=excluded.cargo,
            localidade=excluded.localidade,
            tipo_trabalho=excluded.tipo_trabalho,
            senioridade=excluded.senioridade,
            salario=excluded.salario,
            link_candidatura=excluded.link_candidatura,
            data_publicacao=excluded.data_publicacao,
            score_0_100=excluded.score_0_100,
            motivo_curto=excluded.motivo_curto,
            requisitos_json=excluded.requisitos_json,
            tecnologias_json=excluded.tecnologias_json,
            raw_json=excluded.raw_json
        """,
        rec,
    )
    conn.commit()

def fetch_all_jobs(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT
          platform, job_id, url, url_norm,
          last_seen, status, empresa, cargo, localidade, tipo_trabalho, senioridade,
          salario, link_candidatura, data_publicacao,
          score_0_100, motivo_curto
        FROM jobs
        ORDER BY last_seen DESC
        """
    )
    rows = cur.fetchall()
    out = []
    for r in rows:
        out.append({
            "platform": r[0], "job_id": r[1], "url": r[2], "url_norm": r[3],
            "last_seen": r[4], "status": r[5], "empresa": r[6], "cargo": r[7],
            "localidade": r[8], "tipo_trabalho": r[9], "senioridade": r[10],
            "salario": r[11], "link_candidatura": r[12], "data_publicacao": r[13],
            "score_0_100": r[14], "motivo_curto": r[15],
        })
    return out
