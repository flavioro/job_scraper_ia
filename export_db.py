import pandas as pd
from db import init_db, connect, fetch_all_jobs

OUT_ALL_CSV = "output/vagas_output_all.csv"
OUT_ALL_XLSX = "output/vagas_output_all.xlsx"

OUT_FILTER_CSV = "output/vagas_output_jr_pleno_ativas.csv"
OUT_FILTER_XLSX = "output/vagas_output_jr_pleno_ativas.xlsx"

def main():
    init_db()
    conn = connect()
    try:
        rows = fetch_all_jobs(conn)
    finally:
        conn.close()

    if not rows:
        print("DB sem registros.")
        return

    df = pd.DataFrame(rows).drop_duplicates(subset=["platform", "job_id"], keep="first")

    # Export ALL
    df.to_csv(OUT_ALL_CSV, index=False, encoding="utf-8-sig")
    df.to_excel(OUT_ALL_XLSX, index=False)

    # Export filtro: ativa + junior/pleno
    df2 = df.copy()
    df2["status"] = df2["status"].fillna("duvidosa").str.lower()
    df2["senioridade"] = df2["senioridade"].fillna("desconhecido").str.lower()

    df2 = df2[(df2["status"] == "ativa") & (df2["senioridade"].isin(["junior", "pleno"]))]

    df2.to_csv(OUT_FILTER_CSV, index=False, encoding="utf-8-sig")
    df2.to_excel(OUT_FILTER_XLSX, index=False)

    print(f"Exportado ALL: {OUT_ALL_CSV} | {OUT_ALL_XLSX} | linhas={len(df)}")
    print(f"Exportado FILTRO: {OUT_FILTER_CSV} | {OUT_FILTER_XLSX} | linhas={len(df2)}")

if __name__ == "__main__":
    main()
