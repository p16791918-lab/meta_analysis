# Meta-Analysis Agent System
> 의학 메타분석 논문을 자동으로 작성하는 Claude Code 서브에이전트 시스템

## 파일 구조

```
meta_agents/
├── orchestrator.py          ← 진입점 (여기서 실행)
├── agent_1_search.py        ← 문헌 검색 에이전트
├── agent_2_screening.py     ← PRISMA 선별 에이전트
├── agent_3_extraction.py    ← 데이터 추출 에이전트
├── agent_4_analysis.py      ← 통계 분석 에이전트 (R 코드 생성)
├── agent_5_writer.py        ← 논문 작성 에이전트 (IMRAD)
└── shared/
    ├── prompts.py           ← 각 에이전트 시스템 프롬프트
    └── models.py            ← 데이터 모델 (Pydantic)
```

## 설치

```bash
pip install anthropic biopython
export ANTHROPIC_API_KEY="sk-ant-..."
export NCBI_EMAIL="your@email.com"   # PubMed 실제 검색 시
```

## 사용법

### 1. 빠른 시작 (데모 모드)
```bash
cd meta_agents
python orchestrator.py
```

### 2. 본인 PICO로 실행
`orchestrator.py` 하단의 `MY_PICO` 섹션을 수정:

```python
MY_PICO = PICO(
    population="연구 대상 환자군",
    intervention="중재 (약물/시술)",
    comparison="대조군",
    outcome="주요 결과변수",
    study_design="Randomized controlled trial"
)
```

### 3. 실제 PubMed 검색
```python
run_meta_analysis(
    ...
    demo_mode=False    # True → False 변경
)
```

## 산출물 (output_YYYYMMDD_HHMMSS/)

| 파일 | 내용 |
|------|------|
| `search_queries.json` | PubMed/Cochrane/Embase 검색식 |
| `prisma_flow.txt` | PRISMA 2020 흐름도 숫자 |
| `data.R` | 추출된 데이터 (R data.frame) |
| `meta_analysis.R` | 완성된 메타분석 R 스크립트 |
| `manuscript.md` | 초안 논문 (Abstract~Conclusion) |

## 각 에이전트 역할

### Agent 1: Search
- PICO → MeSH term 생성
- Boolean operator 검색식 자동 작성
- PubMed Entrez API 호출

### Agent 2: Screening
- 포함/배제 기준 적용
- Title/Abstract → Full-text 2단계 선별
- RoB 2 / NOS 비뚤림 위험 평가

### Agent 3: Extraction
- 연속형 (mean ± SD) / 이진형 (events/total) 데이터 추출
- R data.frame 코드 자동 생성

### Agent 4: Analysis
- I² 기반 모델 선택 (fixed/random-effects)
- metafor::rma() 완성 코드 생성
- Forest plot, Funnel plot, Egger's test
- GRADE 근거 수준 평가

### Agent 5: Writer
- IMRAD 전 섹션 작성
- PRISMA 2020 체크리스트 준수
- 목표 저널 스타일 적용

## Claude Code에서 실행하는 법

```bash
# Claude Code 터미널에서
cd meta_agents
python orchestrator.py

# 또는 각 에이전트 개별 테스트
python agent_1_search.py
```

## 참고

- PRISMA 2020: http://www.prisma-statement.org/
- GRADE: https://www.gradeworkinggroup.org/
- PROSPERO 등록: https://www.crd.york.ac.uk/prospero/
- metafor R package: https://www.metafor-project.org/
