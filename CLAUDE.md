# Meta-Analysis Project: Breast Cancer & Race

의학 분야 메타분석의 전 과정(문헌 검색 → 선별 → 추출 → 질 평가 → 통계 분석 → 논문 작성)을
자동화하는 전문 서브에이전트 시스템.

---

## 서브에이전트 목록 (6개)

| 에이전트 | 파일 | 담당 역할 |
|---------|------|----------|
| **Searcher** | `agents/searcher.md` | 체계적 문헌 검색 (PubMed MeSH 전략, PRISMA 추적) |
| **Screener** | `agents/screener.md` | 2단계 논문 선별 (제목/초록 → 원문, 포함/제외 판정) |
| **Extractor** | `agents/extractor.md` | 표준화 데이터 추출 (인종별 발생률, CI, 연구 특성) |
| **Quality Assessor** | `agents/quality_assessor.md` | 비뚤림 위험 평가 (NOS, ROBINS-I) + GRADE 등급 |
| **Analyzer** | `agents/analyzer.md` | 메타분석 통계 (이질성, 풀링 추정, 출판 비뚤림, Forest/Funnel plot) |
| **Writer** | `agents/writer.md` | PRISMA 2020 준수 학술 논문 전체 작성 |

---

## 전체 워크플로우

```
[1] Searcher
    └─ pubmed_tool.py 실행
    └─ data/search_results.csv 생성
    └─ data/search_log.txt 기록

[2] Screener
    ├─ 1단계: 제목/초록 스크리닝 → data/screening_t1.csv
    └─ 2단계: 원문 스크리닝 → data/screening_results.csv
              data/prisma_numbers.txt 집계

[3] Extractor
    └─ data/final_extraction.csv (인종별 발생률, N, CI, 연구 특성)

[4] Quality Assessor
    ├─ data/quality_assessment.csv (NOS 점수, 비뚤림 위험 등급)
    └─ data/grade_assessment.csv (GRADE 근거 확실성)

[5] Analyzer
    ├─ analyzer.py 실행
    ├─ results/forest_plot_Overall.png
    ├─ results/funnel_plot.png
    ├─ results/subgroup_*/
    ├─ results/sensitivity/leave_one_out.csv
    └─ results/statistics_summary.csv

[6] Writer
    ├─ manuscript/title_abstract.md
    ├─ manuscript/introduction.md
    ├─ manuscript/methods.md
    ├─ manuscript/results.md
    ├─ manuscript/discussion.md
    ├─ manuscript/references.md
    ├─ manuscript/supplementary.md
    └─ manuscript/full_manuscript.md
```

---

## 주요 도구

| 스크립트 | 설명 | 사용법 |
|---------|------|--------|
| `pubmed_tool.py` | PubMed 검색 및 CSV 저장 (Biopython) | `python pubmed_tool.py --query "..." --max 200 --output data/search_results.csv` |
| `analyzer.py` | 메타분석 통계 분석 (이질성, 풀링, 출판 비뚤림) | `python analyzer.py --input data/final_extraction.csv --analysis all --output results/` |

### analyzer.py 주요 옵션
```bash
# 전체 분석 (풀링 + 출판 비뚤림 + Leave-one-out)
python analyzer.py --input data/final_extraction.csv --analysis all --output results/

# 인종 집단별 분석
python analyzer.py --input data/final_extraction.csv --analysis pooled --group Racial_Group_Std --output results/

# 하위집단 분석 (국가별)
python analyzer.py --input data/final_extraction.csv --analysis subgroup --subgroup Country --output results/

# 출판 비뚤림만
python analyzer.py --input data/final_extraction.csv --analysis publication_bias --output results/
```

---

## 디렉토리 구조

```
meta_analysis/
├── CLAUDE.md                    # 이 파일
├── pubmed_tool.py               # PubMed 검색 도구
├── analyzer.py                  # 통계 분석 도구
├── agents/
│   ├── searcher.md              # 에이전트 1: 문헌 검색
│   ├── screener.md              # 에이전트 2: 논문 선별
│   ├── extractor.md             # 에이전트 3: 데이터 추출
│   ├── quality_assessor.md      # 에이전트 4: 질 평가
│   ├── analyzer.md              # 에이전트 5: 통계 분석
│   └── writer.md                # 에이전트 6: 논문 작성
├── data/
│   ├── search_results.csv       # [1] 검색 결과
│   ├── search_results_dedup.csv # [1] 중복 제거 결과
│   ├── search_log.txt           # [1] 검색 로그
│   ├── screening_t1.csv         # [2] 1단계 스크리닝
│   ├── screening_results.csv    # [2] 최종 스크리닝
│   ├── prisma_numbers.txt       # [2] PRISMA 흐름도 수치
│   ├── final_extraction.csv     # [3] 추출 데이터
│   ├── quality_assessment.csv   # [4] NOS 점수
│   └── grade_assessment.csv     # [4] GRADE 등급
├── results/
│   ├── forest_plot_Overall.png  # [5] Forest plot
│   ├── funnel_plot.png          # [5] Funnel plot
│   ├── subgroup_*/              # [5] 하위집단 분석
│   ├── sensitivity/             # [5] 민감도 분석
│   └── statistics_summary.csv  # [5] 통계 요약
└── manuscript/
    ├── title_abstract.md        # [6] 제목 및 초록
    ├── introduction.md          # [6] 서론
    ├── methods.md               # [6] 방법론
    ├── results.md               # [6] 결과
    ├── discussion.md            # [6] 고찰
    ├── references.md            # [6] 참고문헌
    ├── supplementary.md         # [6] 보충 자료
    └── full_manuscript.md       # [6] 완성 원고
```

---

## 설치 요구사항

```bash
pip install biopython pandas numpy scipy matplotlib
```

---

## 사용 예시 (Claude Code에서 에이전트 호출)

```
# 에이전트 1: 문헌 검색 시작
agents/searcher.md 를 읽고 검색 전략을 수립한 후 pubmed_tool.py를 실행해줘.

# 에이전트 2: 검색 결과 선별
agents/screener.md 지침에 따라 data/search_results_dedup.csv 를 스크리닝해줘.

# 에이전트 3: 데이터 추출
agents/extractor.md 기준으로 선별된 논문들의 데이터를 추출해줘.

# 에이전트 4: 질 평가
agents/quality_assessor.md 를 참고해서 포함 논문들의 NOS 평가를 수행해줘.

# 에이전트 5: 통계 분석
agents/analyzer.md 지침대로 analyzer.py를 실행해서 메타분석을 수행해줘.

# 에이전트 6: 논문 작성
agents/writer.md 를 참고해서 메타분석 논문 전체를 manuscript/ 폴더에 작성해줘.
```
