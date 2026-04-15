#!/usr/bin/env python3
"""
PubMed Search Tool for Meta-Analysis
Biopython (Entrez) 기반 PubMed 검색 및 CSV 저장 스크립트.

Usage:
  python pubmed_tool.py --query "breast cancer AND ethnicity" --max 200 --output data/search_results.csv
"""

import argparse
import csv
import os
import time
import sys
from datetime import date

try:
    from Bio import Entrez
except ImportError:
    print("Error: Biopython not installed. Run: pip install biopython", file=sys.stderr)
    sys.exit(1)


def search_pubmed(query: str, max_results: int = 200, email: str = "researcher@example.com") -> list[dict]:
    """PubMed 검색 후 결과 딕셔너리 목록 반환."""
    Entrez.email = email

    print(f"[1/3] PubMed 검색 중: {query[:80]}...")
    handle = Entrez.esearch(db="pubmed", term=query, retmax=max_results, sort="relevance")
    record = Entrez.read(handle)
    handle.close()

    ids = record["IdList"]
    total_found = int(record["Count"])
    print(f"      총 {total_found}건 발견, {len(ids)}건 다운로드 예정")

    if not ids:
        return []

    print(f"[2/3] 상세 정보 가져오는 중 ({len(ids)}편)...")
    results = []
    batch_size = 100

    for start in range(0, len(ids), batch_size):
        batch = ids[start:start + batch_size]
        handle = Entrez.efetch(db="pubmed", id=batch, rettype="xml", retmode="xml")
        records = Entrez.read(handle)
        handle.close()

        for article in records["PubmedArticle"]:
            try:
                medline = article["MedlineCitation"]
                pmid = str(medline["PMID"])
                art = medline["Article"]

                # 제목
                title = str(art.get("ArticleTitle", "N/A"))

                # 저자
                authors = []
                if "AuthorList" in art:
                    for author in art["AuthorList"]:
                        last = author.get("LastName", "")
                        initials = author.get("Initials", "")
                        if last:
                            authors.append(f"{last} {initials}".strip())
                author_str = "; ".join(authors[:6])
                if len(authors) > 6:
                    author_str += " et al."

                # 저널 및 연도
                journal_info = art.get("Journal", {})
                journal = str(journal_info.get("Title", "N/A"))
                issue_info = journal_info.get("JournalIssue", {})
                pub_date = issue_info.get("PubDate", {})
                year = str(pub_date.get("Year", pub_date.get("MedlineDate", "N/A"))).split()[0]

                # 초록
                abstract = ""
                if "Abstract" in art:
                    texts = art["Abstract"]["AbstractText"]
                    if isinstance(texts, list):
                        abstract = " ".join(
                            f"{t.attributes.get('Label', '')}: {str(t)}"
                            if hasattr(t, 'attributes') else str(t)
                            for t in texts
                        )
                    else:
                        abstract = str(texts)

                # MeSH 용어
                mesh_terms = []
                if "MeshHeadingList" in medline:
                    for mesh in medline["MeshHeadingList"]:
                        mesh_terms.append(str(mesh["DescriptorName"]))

                results.append({
                    "PMID": pmid,
                    "Title": title,
                    "Authors": author_str,
                    "Journal": journal,
                    "Year": year,
                    "Abstract": abstract[:1000] + ("..." if len(abstract) > 1000 else ""),
                    "MeSH_Terms": "; ".join(mesh_terms[:10]),
                })

            except Exception as e:
                print(f"      경고: PMID 파싱 오류 ({e}), 건너뜀", file=sys.stderr)

        time.sleep(0.4)  # NCBI rate limit: max 3 requests/sec

    print(f"      {len(results)}편 처리 완료")
    return results


def save_to_csv(results: list[dict], output_path: str) -> None:
    """결과를 CSV 파일로 저장."""
    if not results:
        print("저장할 결과 없음.")
        return

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"[3/3] {len(results)}편 저장 완료: {output_path}")


def save_search_log(query: str, total_results: int, saved_results: int, output_path: str, log_path: str) -> None:
    """검색 로그를 텍스트 파일로 저장."""
    os.makedirs(os.path.dirname(log_path) if os.path.dirname(log_path) else ".", exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write(f"검색 일자: {date.today()}\n")
        f.write(f"데이터베이스: PubMed\n")
        f.write(f"검색 쿼리:\n{query}\n\n")
        f.write(f"총 검색 결과: {total_results}편\n")
        f.write(f"저장된 결과: {saved_results}편\n")
        f.write(f"출력 파일: {output_path}\n")
        f.write("=" * 60 + "\n\n")
    print(f"      검색 로그 저장: {log_path}")


def deduplicate(input_path: str, output_path: str) -> None:
    """PMID 기준 중복 제거."""
    import pandas as pd
    df = pd.read_csv(input_path)
    original = len(df)
    df_dedup = df.drop_duplicates(subset="PMID")
    df_dedup.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"중복 제거: {original}편 → {len(df_dedup)}편 ({original - len(df_dedup)}편 제거)")


def main():
    parser = argparse.ArgumentParser(
        description="PubMed 검색 후 결과를 CSV로 저장하는 메타분석 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python pubmed_tool.py \\
    --query '("Breast Neoplasms"[MeSH] OR "breast cancer"[tiab]) AND ("Racial Groups"[MeSH])' \\
    --max 200 \\
    --output data/search_results.csv \\
    --email your@email.com
        """
    )
    parser.add_argument("--query", required=True, help="PubMed 검색 쿼리")
    parser.add_argument("--max", type=int, default=200, dest="max_results", help="최대 검색 결과 수 (기본값: 200)")
    parser.add_argument("--output", default="data/search_results.csv", help="출력 CSV 파일 경로")
    parser.add_argument("--email", default="researcher@example.com", help="NCBI Entrez용 이메일")
    parser.add_argument("--dedup", action="store_true", help="중복 제거 후 별도 파일 저장")
    parser.add_argument("--log", default="data/search_log.txt", help="검색 로그 파일 경로")

    args = parser.parse_args()

    results = search_pubmed(args.query, args.max_results, args.email)
    save_to_csv(results, args.output)

    total_str = "N/A"
    Entrez.email = args.email
    try:
        handle = Entrez.esearch(db="pubmed", term=args.query, retmax=0)
        rec = Entrez.read(handle)
        handle.close()
        total_str = rec["Count"]
    except Exception:
        pass

    save_search_log(args.query, total_str, len(results), args.output, args.log)

    if args.dedup:
        dedup_path = args.output.replace(".csv", "_dedup.csv")
        deduplicate(args.output, dedup_path)

    print("\n완료!")


if __name__ == "__main__":
    main()
