#!/usr/bin/env python3
"""
Meta-Analysis Statistical Analyzer
메타분석 통계 분석 도구: 이질성 평가, 풀링 추정, 출판 비뚤림, 민감도 분석, Forest/Funnel plot 생성.

Usage:
  python analyzer.py --input data/final_extraction.csv --analysis pooled --output results/
  python analyzer.py --input data/final_extraction.csv --analysis heterogeneity --output results/
  python analyzer.py --input data/final_extraction.csv --analysis publication_bias --output results/
  python analyzer.py --input data/final_extraction.csv --analysis subgroup --subgroup Country --output results/
  python analyzer.py --input data/final_extraction.csv --analysis leave_one_out --output results/
  python analyzer.py --input data/final_extraction.csv --analysis all --output results/
"""

import argparse
import os
import sys
import warnings
warnings.filterwarnings("ignore")

try:
    import numpy as np
    import pandas as pd
    from scipy import stats
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
except ImportError as e:
    print(f"Error: 필수 라이브러리 없음 ({e}). 설치: pip install numpy pandas scipy matplotlib", file=sys.stderr)
    sys.exit(1)


# ──────────────────────────────────────────────
# 핵심 메타분석 함수
# ──────────────────────────────────────────────

def compute_log_effect(df: pd.DataFrame) -> pd.DataFrame:
    """발생률을 로그 변환하고 표준오차를 계산한다."""
    df = df.copy()
    df["logIR"] = np.log(df["Incidence_Rate"].astype(float))
    ci_lower = df["CI_Lower"].astype(float)
    ci_upper = df["CI_Upper"].astype(float)
    # SE = (log(upper) - log(lower)) / (2 * 1.96)
    df["logSE"] = (np.log(ci_upper) - np.log(ci_lower)) / (2 * 1.96)
    df["weight_FE"] = 1.0 / df["logSE"] ** 2
    return df


def fixed_effects(logIR: np.ndarray, logSE: np.ndarray) -> dict:
    """역분산 고정효과 모형."""
    w = 1.0 / logSE ** 2
    pooled_log = np.sum(w * logIR) / np.sum(w)
    se_pooled = np.sqrt(1.0 / np.sum(w))
    ci_lower = np.exp(pooled_log - 1.96 * se_pooled)
    ci_upper = np.exp(pooled_log + 1.96 * se_pooled)
    return {
        "model": "Fixed Effects (Inverse Variance)",
        "pooled": np.exp(pooled_log),
        "pooled_log": pooled_log,
        "se": se_pooled,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
    }


def heterogeneity_stats(logIR: np.ndarray, logSE: np.ndarray) -> dict:
    """Cochran's Q, I², τ² (DerSimonian-Laird) 계산."""
    k = len(logIR)
    w = 1.0 / logSE ** 2
    pooled_log_fe = np.sum(w * logIR) / np.sum(w)

    Q = np.sum(w * (logIR - pooled_log_fe) ** 2)
    df_Q = k - 1
    p_Q = 1 - stats.chi2.cdf(Q, df_Q)

    # I²
    I2 = max(0.0, (Q - df_Q) / Q * 100) if Q > 0 else 0.0

    # τ² (DerSimonian-Laird)
    c = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    tau2 = max(0.0, (Q - df_Q) / c)
    tau = np.sqrt(tau2)

    return {
        "k": k,
        "Q": Q,
        "df_Q": df_Q,
        "p_Q": p_Q,
        "I2": I2,
        "tau2": tau2,
        "tau": tau,
    }


def random_effects(logIR: np.ndarray, logSE: np.ndarray, tau2: float) -> dict:
    """DerSimonian-Laird 무작위효과 모형."""
    w_re = 1.0 / (logSE ** 2 + tau2)
    pooled_log = np.sum(w_re * logIR) / np.sum(w_re)
    se_pooled = np.sqrt(1.0 / np.sum(w_re))
    ci_lower = np.exp(pooled_log - 1.96 * se_pooled)
    ci_upper = np.exp(pooled_log + 1.96 * se_pooled)
    return {
        "model": "Random Effects (DerSimonian-Laird)",
        "pooled": np.exp(pooled_log),
        "pooled_log": pooled_log,
        "se": se_pooled,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "weights": w_re,
    }


def egger_test(logIR: np.ndarray, logSE: np.ndarray) -> dict:
    """Egger's test for publication bias (선형 회귀 기반)."""
    precision = 1.0 / logSE
    standard_normal = logIR / logSE
    slope, intercept, r, p_value, _ = stats.linregress(precision, standard_normal)
    return {
        "intercept": intercept,
        "slope": slope,
        "r": r,
        "p_value": p_value,
        "significant": p_value < 0.05,
    }


# ──────────────────────────────────────────────
# 시각화 함수
# ──────────────────────────────────────────────

def forest_plot(df: pd.DataFrame, pooled: dict, het: dict, output_path: str,
                title: str = "Forest Plot") -> None:
    """Forest plot 생성."""
    df = df.copy().reset_index(drop=True)
    n = len(df)

    fig, ax = plt.subplots(figsize=(12, max(6, n * 0.5 + 3)))

    # 개별 연구 포인트 및 CI
    y_positions = list(range(n, 0, -1))
    for i, (_, row) in enumerate(df.iterrows()):
        y = y_positions[i]
        ir = row["Incidence_Rate"]
        lo = row["CI_Lower"]
        hi = row["CI_Upper"]
        label = f"{row.get('First_Author', row.get('PMID', ''))} {row.get('Year', '')}"
        ax.plot([lo, hi], [y, y], "b-", linewidth=1.2)
        ax.plot(ir, y, "bs", markersize=6)
        ax.text(-0.02, y, label, ha="right", va="center", fontsize=8, transform=ax.get_yaxis_transform())
        ax.text(1.02, y, f"{ir:.1f} [{lo:.1f}, {hi:.1f}]",
                ha="left", va="center", fontsize=8, transform=ax.get_yaxis_transform())

    # 풀링된 효과 (다이아몬드)
    y_diamond = 0
    p = pooled["pooled"]
    lo_p, hi_p = pooled["ci_lower"], pooled["ci_upper"]
    diamond = plt.Polygon(
        [[lo_p, y_diamond], [p, y_diamond + 0.4], [hi_p, y_diamond], [p, y_diamond - 0.4]],
        closed=True, color="red", zorder=5,
    )
    ax.add_patch(diamond)

    # 세로 기준선
    ax.axvline(x=pooled["pooled"], color="red", linestyle="--", alpha=0.4)

    # 레이블 및 제목
    ax.set_xlabel("Incidence Rate (per 100,000)", fontsize=11)
    ax.set_title(
        f"{title}\n"
        f"Pooled = {p:.1f} [{lo_p:.1f}, {hi_p:.1f}]  |  "
        f"I² = {het['I2']:.1f}%  |  τ² = {het['tau2']:.4f}",
        fontsize=11,
    )
    ax.set_yticks([])
    ax.margins(y=0.05)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Forest plot 저장: {output_path}")


def funnel_plot(logIR: np.ndarray, logSE: np.ndarray, pooled_log: float,
                output_path: str) -> None:
    """Funnel plot 생성."""
    fig, ax = plt.subplots(figsize=(7, 6))

    ax.scatter(np.exp(logIR), logSE, color="steelblue", s=50, alpha=0.8, zorder=3)

    # 깔때기 경계
    se_range = np.linspace(0, max(logSE) * 1.1, 200)
    ax.plot(np.exp(pooled_log + 1.96 * se_range), se_range, "r--", alpha=0.6, label="95% Pseudo-CI")
    ax.plot(np.exp(pooled_log - 1.96 * se_range), se_range, "r--", alpha=0.6)
    ax.axvline(x=np.exp(pooled_log), color="gray", linestyle=":", alpha=0.8)

    ax.set_xlabel("Incidence Rate (per 100,000)", fontsize=11)
    ax.set_ylabel("Standard Error (SE of log IR)", fontsize=11)
    ax.set_title("Funnel Plot (Publication Bias Assessment)", fontsize=12)
    ax.invert_yaxis()
    ax.legend(fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Funnel plot 저장: {output_path}")


# ──────────────────────────────────────────────
# 분석 메인 함수
# ──────────────────────────────────────────────

def load_data(input_path: str) -> pd.DataFrame:
    df = pd.read_csv(input_path)
    required = ["Incidence_Rate", "CI_Lower", "CI_Upper"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"Error: 필수 컬럼 없음: {missing}", file=sys.stderr)
        print(f"  사용 가능한 컬럼: {list(df.columns)}", file=sys.stderr)
        sys.exit(1)
    df = df.dropna(subset=required)
    df["Incidence_Rate"] = pd.to_numeric(df["Incidence_Rate"], errors="coerce")
    df["CI_Lower"] = pd.to_numeric(df["CI_Lower"], errors="coerce")
    df["CI_Upper"] = pd.to_numeric(df["CI_Upper"], errors="coerce")
    df = df.dropna(subset=required)
    df = df[df["Incidence_Rate"] > 0]
    return df


def run_pooled(df: pd.DataFrame, output_dir: str, label: str = "Overall") -> dict:
    df = compute_log_effect(df)
    df = df.dropna(subset=["logIR", "logSE"])
    df = df[df["logSE"] > 0]

    logIR = df["logIR"].values
    logSE = df["logSE"].values

    het = heterogeneity_stats(logIR, logSE)
    fe = fixed_effects(logIR, logSE)
    re = random_effects(logIR, logSE, het["tau2"])

    model = re if het["I2"] >= 25 or het["p_Q"] <= 0.1 else fe
    model["selected"] = True

    # 보고
    print(f"\n{'='*55}")
    print(f"  분석: {label}  (n={het['k']}편)")
    print(f"{'='*55}")
    print(f"  이질성: Q={het['Q']:.2f} (df={het['df_Q']}, p={het['p_Q']:.4f})")
    print(f"          I²={het['I2']:.1f}%  τ²={het['tau2']:.4f}  τ={het['tau']:.4f}")
    print(f"  선택 모형: {model['model']}")
    print(f"  풀링 추정치: {model['pooled']:.2f} [95%CI: {model['ci_lower']:.2f}~{model['ci_upper']:.2f}]")
    print(f"{'='*55}")

    # Forest plot
    os.makedirs(output_dir, exist_ok=True)
    forest_path = os.path.join(output_dir, f"forest_plot_{label.replace(' ', '_')}.png")
    forest_plot(df, model, het, forest_path, title=f"Forest Plot — {label}")

    # 결과 저장
    result_rows = []
    for _, row in df.iterrows():
        result_rows.append({
            "Label": label,
            "Study": f"{row.get('First_Author', row.get('PMID', ''))} {row.get('Year', '')}".strip(),
            "PMID": row.get("PMID", ""),
            "Racial_Group": row.get("Racial_Group", ""),
            "N": row.get("N", ""),
            "Incidence_Rate": row["Incidence_Rate"],
            "CI_Lower": row["CI_Lower"],
            "CI_Upper": row["CI_Upper"],
        })
    result_rows.append({
        "Label": f"[POOLED] {label}",
        "Study": model["model"],
        "PMID": "",
        "Racial_Group": "All",
        "N": "",
        "Incidence_Rate": round(model["pooled"], 3),
        "CI_Lower": round(model["ci_lower"], 3),
        "CI_Upper": round(model["ci_upper"], 3),
    })

    return {"fe": fe, "re": re, "het": het, "selected": model, "rows": result_rows, "df": df}


def run_subgroup(df: pd.DataFrame, subgroup_col: str, output_dir: str) -> None:
    if subgroup_col not in df.columns:
        print(f"Error: 컬럼 '{subgroup_col}' 없음. 사용 가능: {list(df.columns)}", file=sys.stderr)
        return

    subdir = os.path.join(output_dir, f"subgroup_{subgroup_col}")
    os.makedirs(subdir, exist_ok=True)
    all_rows = []

    for group, gdf in df.groupby(subgroup_col):
        if len(gdf) < 2:
            print(f"  건너뜀 '{group}': 2편 미만")
            continue
        res = run_pooled(gdf, subdir, label=str(group))
        all_rows.extend(res["rows"])

    if all_rows:
        out_csv = os.path.join(subdir, "subgroup_results.csv")
        pd.DataFrame(all_rows).to_csv(out_csv, index=False, encoding="utf-8-sig")
        print(f"\n  하위집단 결과 저장: {out_csv}")


def run_publication_bias(df: pd.DataFrame, output_dir: str) -> None:
    df = compute_log_effect(df).dropna(subset=["logIR", "logSE"])
    df = df[df["logSE"] > 0]
    logIR = df["logIR"].values
    logSE = df["logSE"].values

    fe = fixed_effects(logIR, logSE)
    egger = egger_test(logIR, logSE)

    os.makedirs(output_dir, exist_ok=True)
    funnel_path = os.path.join(output_dir, "funnel_plot.png")
    funnel_plot(logIR, logSE, fe["pooled_log"], funnel_path)

    print(f"\n출판 비뚤림 검정 (Egger's Test):")
    print(f"  절편 = {egger['intercept']:.4f}")
    print(f"  p-값 = {egger['p_value']:.4f} {'← 유의한 비뚤림 의심' if egger['significant'] else '(비뚤림 없음)'}")

    report_path = os.path.join(output_dir, "publication_bias.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("출판 비뚤림 검정 결과\n")
        f.write("=" * 40 + "\n")
        f.write(f"Egger's Test:\n")
        f.write(f"  절편 (intercept): {egger['intercept']:.4f}\n")
        f.write(f"  기울기 (slope):   {egger['slope']:.4f}\n")
        f.write(f"  p-값:             {egger['p_value']:.4f}\n")
        f.write(f"  해석: {'출판 비뚤림 존재 의심 (p<0.05)' if egger['significant'] else '유의한 출판 비뚤림 없음'}\n")
    print(f"  보고서 저장: {report_path}")


def run_leave_one_out(df: pd.DataFrame, output_dir: str) -> None:
    """Leave-one-out 민감도 분석."""
    df = compute_log_effect(df).dropna(subset=["logIR", "logSE"])
    df = df[df["logSE"] > 0].reset_index(drop=True)

    loo_results = []
    for i, row in df.iterrows():
        df_loo = df.drop(index=i)
        if len(df_loo) < 2:
            continue
        het = heterogeneity_stats(df_loo["logIR"].values, df_loo["logSE"].values)
        re = random_effects(df_loo["logIR"].values, df_loo["logSE"].values, het["tau2"])
        study_id = f"{row.get('First_Author', row.get('PMID', ''))} {row.get('Year', '')}".strip()
        loo_results.append({
            "Excluded_Study": study_id,
            "Pooled_IR": round(re["pooled"], 3),
            "CI_Lower": round(re["ci_lower"], 3),
            "CI_Upper": round(re["ci_upper"], 3),
            "I2": round(het["I2"], 1),
        })

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "leave_one_out.csv")
    pd.DataFrame(loo_results).to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n  Leave-one-out 결과 저장: {out_path}")
    print(f"  풀링 범위: {min(r['Pooled_IR'] for r in loo_results):.2f} ~ {max(r['Pooled_IR'] for r in loo_results):.2f}")


def run_all(df: pd.DataFrame, output_dir: str, subgroup_col: str | None = None) -> None:
    os.makedirs(output_dir, exist_ok=True)
    run_pooled(df, output_dir, "Overall")
    run_publication_bias(df, output_dir)
    run_leave_one_out(df, os.path.join(output_dir, "sensitivity"))
    if subgroup_col:
        run_subgroup(df, subgroup_col, output_dir)


# ──────────────────────────────────────────────
# CLI 진입점
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="메타분석 통계 분석 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="입력 CSV 파일 (final_extraction.csv)")
    parser.add_argument(
        "--analysis",
        choices=["pooled", "heterogeneity", "subgroup", "publication_bias", "leave_one_out", "all"],
        default="all",
        help="수행할 분석 유형",
    )
    parser.add_argument("--output", default="results/", help="출력 디렉토리")
    parser.add_argument("--subgroup", default=None, help="하위집단 분석 기준 컬럼명 (예: Country)")
    parser.add_argument("--group", default=None, help="인종 집단별 분석 기준 컬럼명 (예: Racial_Group_Std)")
    parser.add_argument("--quality_file", default=None, help="품질 평가 CSV (민감도 분석 시 사용)")
    parser.add_argument("--exclude_high_rob", action="store_true", help="비뚤림 위험 높은 연구 제외")

    args = parser.parse_args()

    print(f"\n메타분석 통계 분석 시작")
    print(f"  입력: {args.input}")
    print(f"  분석: {args.analysis}")
    print(f"  출력: {args.output}\n")

    df = load_data(args.input)
    print(f"데이터 로드: {len(df)}개 데이터포인트, {df['PMID'].nunique() if 'PMID' in df.columns else '?'}편 논문")

    # 비뚤림 높은 연구 제외
    if args.exclude_high_rob and args.quality_file:
        qdf = pd.read_csv(args.quality_file)
        high_rob = qdf[qdf["RoB"] == "High"]["PMID"].tolist()
        before = len(df)
        df = df[~df["PMID"].isin(high_rob)]
        print(f"  고비뚤림 연구 제외: {before}→{len(df)}개")

    if args.analysis == "pooled":
        if args.group and args.group in df.columns:
            os.makedirs(args.output, exist_ok=True)
            all_rows = []
            for group, gdf in df.groupby(args.group):
                if len(gdf) < 2:
                    continue
                res = run_pooled(gdf, args.output, label=str(group))
                all_rows.extend(res["rows"])
            pd.DataFrame(all_rows).to_csv(
                os.path.join(args.output, "pooled_by_group.csv"), index=False, encoding="utf-8-sig"
            )
        else:
            run_pooled(df, args.output)

    elif args.analysis == "heterogeneity":
        df2 = compute_log_effect(df).dropna(subset=["logIR", "logSE"])
        df2 = df2[df2["logSE"] > 0]
        het = heterogeneity_stats(df2["logIR"].values, df2["logSE"].values)
        print(f"\n이질성 검정 결과:")
        for k, v in het.items():
            print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    elif args.analysis == "subgroup":
        col = args.subgroup or args.group
        if not col:
            print("Error: --subgroup 또는 --group 컬럼명을 지정하세요.", file=sys.stderr)
            sys.exit(1)
        run_subgroup(df, col, args.output)

    elif args.analysis == "publication_bias":
        run_publication_bias(df, args.output)

    elif args.analysis == "leave_one_out":
        run_leave_one_out(df, args.output)

    elif args.analysis == "all":
        run_all(df, args.output, subgroup_col=args.subgroup or args.group)

    print("\n분석 완료!")


if __name__ == "__main__":
    main()
