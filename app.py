from __future__ import annotations

import html
import io
import hashlib
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st


st.set_page_config(
    page_title="SELL-IN 분석 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------
# 라이트 모드 · 차트 접근성
# ---------------------------------------------------------------------
LIGHT_CHART_COLORS = [
    "#2563EB", "#059669", "#D97706", "#DC2626", "#7C3AED",
    "#0891B2", "#65A30D", "#DB2777", "#4F46E5", "#0F766E",
]

PRODUCT_GROUP_COLORS = [
    "#93C5FD", "#A7F3D0", "#FDE68A", "#FDBA74", "#C4B5FD",
    "#F9A8D4", "#67E8F9", "#BEF264", "#FCA5A5", "#D8B4FE",
    "#86EFAC", "#FCD34D", "#7DD3FC", "#F0ABFC", "#A5B4FC",
    "#6EE7B7", "#FED7AA", "#FDA4AF", "#BAE6FD", "#D9F99D",
    "#CBD5E1",
]

pio.templates["sellin_light"] = go.layout.Template(
    layout=dict(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        colorway=LIGHT_CHART_COLORS,
        font=dict(
            family="Arial, 'Noto Sans KR', sans-serif",
            color="#172033",
            size=13,
        ),
        title=dict(font=dict(color="#0F172A", size=17)),
        legend=dict(
            font=dict(color="#1F2937", size=12),
            title=dict(font=dict(color="#111827", size=12)),
        ),
        xaxis=dict(
            gridcolor="#E5E7EB",
            linecolor="#CBD5E1",
            zerolinecolor="#94A3B8",
            tickfont=dict(color="#334155"),
            title=dict(font=dict(color="#334155")),
        ),
        yaxis=dict(
            gridcolor="#E5E7EB",
            linecolor="#CBD5E1",
            zerolinecolor="#94A3B8",
            tickfont=dict(color="#334155"),
            title=dict(font=dict(color="#334155")),
        ),
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            bordercolor="#94A3B8",
            font=dict(color="#111827", size=13),
        ),
    )
)
pio.templates.default = "sellin_light"
px.defaults.template = "sellin_light"
px.defaults.color_discrete_sequence = LIGHT_CHART_COLORS

st.markdown(
    """
    <style>
    :root { color-scheme: light; }
    [data-testid="stAppViewContainer"] {
        background: #FFFFFF;
        color: #111827;
    }
    [data-testid="stHeader"] { background: rgba(255, 255, 255, 0.96); }
    [data-testid="stSidebar"] {
        background: #F4F7FB;
        border-right: 1px solid #DCE3EC;
    }
    h1, h2, h3, h4, h5, h6 { color: #0F172A !important; }
    [data-testid="stCaptionContainer"], .stCaption { color: #475569 !important; }
    [data-testid="stMetric"] {
        background: #F8FAFC;
        border: 1px solid #DCE3EC;
        border-radius: 12px;
        padding: 14px 16px;
    }
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {
        color: #111827;
    }
    [data-testid="stExpander"] {
        background: #FFFFFF;
        border-color: #D6DEE8;
        border-radius: 10px;
    }
    [data-testid="stFileUploaderDropzone"] {
        background: #F8FAFC;
        border-color: #B8C4D3;
    }
    [data-baseweb="tab-list"] { border-bottom: 1px solid #D7DEE8; }
    [data-baseweb="tab"] { color: #334155; }
    [aria-selected="true"][data-baseweb="tab"] {
        color: #1D4ED8;
        font-weight: 700;
    }
    .product-group-list {
        background: #F8FAFC;
        border: 1px solid #D7DEE8;
        border-radius: 12px;
        padding: 12px 14px;
    }
    .product-group-list-title {
        color: #0F172A;
        font-size: 0.92rem;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .product-group-row {
        display: grid;
        grid-template-columns: 14px minmax(0, 1fr) auto;
        align-items: center;
        column-gap: 10px;
        min-height: 42px;
        border-top: 1px solid #E2E8F0;
    }
    .product-group-row:first-of-type { border-top: 0; }
    .product-group-swatch {
        width: 12px;
        height: 12px;
        border-radius: 3px;
        border: 1px solid rgba(15, 23, 42, 0.16);
    }
    .product-group-name {
        color: #1E293B;
        font-size: 0.92rem;
        font-weight: 600;
        line-height: 1.25;
        overflow-wrap: anywhere;
    }
    .product-group-value {
        color: #0F172A;
        font-size: 0.91rem;
        font-weight: 700;
        text-align: right;
        white-space: nowrap;
    }
    .product-group-share {
        color: #64748B;
        font-size: 0.78rem;
        font-weight: 600;
        margin-left: 7px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------------------
REQUIRED_COLUMNS = ["출고일", "출고수량", "품목", "품목명"]
NUMERIC_COLUMNS = [
    "출고수량",
    "기본출고수량",
    "판매단가",
    "출고금액",
    "조정출고금액",
]
DATE_COLUMNS = [
    "출고일",
    "납품지시일",
    "납품요청일",
    "수주일",
    "입력시간",
]

LABEL_MAP = {
    "분석수량": "출고수량 (개)",
    "분석금액": "출고금액 (천원)",
}

PRODUCT_MAPPING_COLUMNS = [
    "품목코드",
    "품목명",
    "대분류",
    "제품군",
    "판매형태",
    "에디션",
    "시장사양",
    "기본분석포함",
    "검토상태",
    "검토사유",
]

AMOUNT_POLICY_ADJUSTED = "조정출고금액 우선 (공란만 출고금액 대체)"
AMOUNT_POLICY_ZERO_AS_BLANK = "조정출고금액 0도 미입력으로 간주"
AMOUNT_POLICY_ORIGINAL = "출고금액만 사용"


# ---------------------------------------------------------------------
# 공통 함수
# ---------------------------------------------------------------------
def clean_column_name(value: object) -> str:
    """공백/줄바꿈을 정리한 컬럼명 반환."""
    return re.sub(r"\s+", " ", str(value)).strip()


def safe_numeric(series: pd.Series) -> pd.Series:
    """쉼표, 통화기호, 괄호 음수, '원/개'가 포함된 값을 숫자로 변환."""
    cleaned = (
        series.astype("string")
        .str.replace(",", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace("₩", "", regex=False)
        .str.replace(r"^(\(.+\))$", r"-\1", regex=True)
        .str.replace("(", "", regex=False)
        .str.replace(")", "", regex=False)
        .str.replace(r"(원|개)$", "", regex=True)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def safe_datetime(series: pd.Series) -> pd.Series:
    """일반 날짜, YYYYMMDD 숫자, Excel 일련번호를 함께 안전하게 변환."""
    parsed = pd.to_datetime(series, errors="coerce", format="mixed")
    numeric = pd.to_numeric(series, errors="coerce")

    excel_serial = numeric.between(20_000, 80_000, inclusive="both")
    if excel_serial.any():
        parsed.loc[excel_serial] = pd.Timestamp("1899-12-30") + pd.to_timedelta(
            numeric.loc[excel_serial],
            unit="D",
        )

    compact_date = numeric.between(19_000_101, 21_001_231, inclusive="both")
    if compact_date.any():
        compact_text = numeric.loc[compact_date].round().astype("Int64").astype("string")
        parsed.loc[compact_date] = pd.to_datetime(
            compact_text,
            format="%Y%m%d",
            errors="coerce",
        )
    return parsed


def nonblank_mask(series: pd.Series) -> pd.Series:
    """원본 셀에 실제 값이 입력되어 있는 행을 판정."""
    text = series.astype("string").fillna("").str.strip()
    return text.ne("") & ~text.str.lower().isin({"nan", "none", "<na>"})


def representative_text(series: pd.Series, default: str = "미기재") -> str:
    """가장 자주 등장한 값을 대표값으로 선택하고 동률이면 최근 값을 사용."""
    values = series.astype("string").fillna("").str.strip()
    values = values[~values.isin({"", "nan", "None", "<NA>"})]
    if values.empty:
        return default
    counts = values.value_counts()
    candidates = set(counts[counts.eq(counts.max())].index.tolist())
    return next(value for value in reversed(values.tolist()) if value in candidates)


def first_existing_value(
    df: pd.DataFrame,
    preferred: str,
    fallback: str,
    default: str = "",
) -> pd.Series:
    """우선 컬럼이 비어 있으면 대체 컬럼을 사용하는 Series 생성."""
    if preferred in df.columns and fallback in df.columns:
        preferred_value = df[preferred].astype("string").fillna("").str.strip()
        fallback_value = df[fallback].astype("string").fillna("").str.strip()
        return preferred_value.mask(preferred_value.eq(""), fallback_value)
    if preferred in df.columns:
        return df[preferred].astype("string").fillna("").str.strip()
    if fallback in df.columns:
        return df[fallback].astype("string").fillna("").str.strip()
    return pd.Series(default, index=df.index, dtype="string")


def simplify_warehouse(value: object) -> str:
    text = str(value).strip()
    upper = text.upper()
    for code in ("DU", "GD", "GL"):
        if re.search(rf"(?<![A-Z]){code}(?![A-Z])", upper):
            return code
    if text in {"", "nan", "None", "<NA>"}:
        return "미기재"
    return text


def product_version(product_name: object) -> str:
    """제품명 끝의 [23], [24], [25] 등을 버전으로 추출."""
    match = re.search(r"\[(\d{2,4})\]\s*$", str(product_name))
    return match.group(1) if match else "미기재"


def strip_product_version(product_name: object) -> str:
    return re.sub(r"\s*\[\d{2,4}\]\s*$", "", str(product_name)).strip()


def combine_display_key(name: pd.Series, code: pd.Series) -> pd.Series:
    name_value = name.astype("string").fillna("").str.strip()
    code_value = code.astype("string").fillna("").str.strip()

    result = np.where(
        name_value.ne("") & code_value.ne(""),
        name_value + " | " + code_value,
        np.where(name_value.ne(""), name_value, code_value),
    )
    result = pd.Series(result, index=name.index, dtype="string")
    return result.mask(result.eq(""), "미기재")


def format_number(value: float | int | np.number | None, decimals: int = 0) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.{decimals}f}"


def format_pct(value: float | int | np.number | None, decimals: int = 1) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) * 100:.{decimals}f}%"


def sort_unique(values: Iterable[object]) -> list[str]:
    cleaned = {
        str(value).strip()
        for value in values
        if pd.notna(value) and str(value).strip() not in {"", "nan", "None", "<NA>"}
    }
    return sorted(cleaned)


def normalize_continent(value: object) -> str:
    """매핑 파일에 입력된 대륙명을 하드코딩 없이 그대로 사용합니다."""
    text = str(value).strip()
    if text in {"", "nan", "None", "<NA>"}:
        return "미지정"
    return text


def get_sheet_names(file_bytes: bytes) -> list[str]:
    """업로드된 파일의 시트명을 세션 실행 중 직접 읽습니다."""
    return pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl").sheet_names


def load_excel(file_bytes: bytes, sheet_name: str) -> pd.DataFrame:
    """업로드된 SELL-IN 데이터를 서버 공용 캐시에 저장하지 않고 읽습니다."""
    return pd.read_excel(
        io.BytesIO(file_bytes),
        sheet_name=sheet_name,
        engine="openpyxl",
    )


def load_region_mapping(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    """CSV/XLSX 형식의 거래처-국가-대륙 매핑 파일을 검증해 불러옵니다."""
    suffix = Path(file_name).suffix.lower()
    buffer = io.BytesIO(file_bytes)

    if suffix == ".csv":
        try:
            mapping = pd.read_csv(buffer, encoding="utf-8-sig")
        except UnicodeDecodeError:
            buffer.seek(0)
            mapping = pd.read_csv(buffer, encoding="cp949")
    elif suffix in {".xlsx", ".xlsm"}:
        workbook = pd.ExcelFile(buffer, engine="openpyxl")
        target_sheet = (
            "국가 대륙 매핑"
            if "국가 대륙 매핑" in workbook.sheet_names
            else workbook.sheet_names[0]
        )
        mapping = pd.read_excel(workbook, sheet_name=target_sheet)
    else:
        raise ValueError("국가·대륙 매핑 파일은 CSV 또는 XLSX 형식만 지원합니다.")

    mapping.columns = [clean_column_name(col) for col in mapping.columns]
    missing = [col for col in ["국가", "대륙"] if col not in mapping.columns]
    if missing:
        raise ValueError(
            "매핑 파일에 다음 컬럼이 필요합니다: " + ", ".join(missing)
        )

    mapping_key_columns = ["거래처", "거래처코드", "거래처명"]
    for col in [*mapping_key_columns, "국가", "대륙"]:
        if col not in mapping.columns:
            mapping[col] = ""
        mapping[col] = mapping[col].astype("string").fillna("").str.strip()

    mapping["대륙"] = mapping["대륙"].map(normalize_continent)

    mapping["국가"] = mapping["국가"].replace("", "미지정")
    mapping["대륙"] = mapping["대륙"].replace("", "미지정")

    if not mapping[mapping_key_columns].ne("").any(axis=1).all():
        bad_rows = mapping.index[~mapping[mapping_key_columns].ne("").any(axis=1)] + 2
        raise ValueError(
            "거래처·거래처코드·거래처명이 모두 비어 있는 행이 있습니다: "
            + ", ".join(map(str, bad_rows[:10]))
        )

    for key in mapping_key_columns:
        keyed = mapping[mapping[key].ne("")].copy()
        if keyed.empty:
            continue
        conflicts = (
            keyed.groupby(key)[["국가", "대륙"]]
            .apply(lambda group: len(group.drop_duplicates()))
        )
        conflict_keys = conflicts[conflicts.gt(1)].index.tolist()
        if conflict_keys:
            raise ValueError(
                f"동일 {key}에 서로 다른 국가·대륙이 입력되어 있습니다: "
                + ", ".join(map(str, conflict_keys[:10]))
            )

    country_continent_conflicts = (
        mapping[
            mapping["국가"].ne("미지정") & mapping["대륙"].ne("미지정")
        ]
        .groupby("국가")["대륙"]
        .nunique()
    )
    conflict_countries = country_continent_conflicts[
        country_continent_conflicts.gt(1)
    ].index.tolist()
    if conflict_countries:
        raise ValueError(
            "동일 국가에 서로 다른 대륙이 입력되어 있습니다: "
            + ", ".join(map(str, conflict_countries[:10]))
        )

    return mapping[
        ["거래처", "거래처코드", "거래처명", "국가", "대륙"]
    ].copy()


def apply_region_mapping(
    sellin_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    """거래처 → 거래처코드 → 거래처명 순으로 국가·대륙을 함께 연결합니다."""
    result = sellin_df.copy()
    result["국가"] = "미지정"
    result["대륙"] = "미지정"

    mapping = mapping_df.copy()
    for col in ["거래처", "거래처코드", "거래처명", "국가", "대륙"]:
        if col not in mapping.columns:
            mapping[col] = ""
        mapping[col] = mapping[col].astype("string").fillna("").str.strip()
    mapping["국가"] = mapping["국가"].replace("", "미지정")
    mapping["대륙"] = mapping["대륙"].replace("", "미지정")

    matched = pd.Series(False, index=result.index)
    for key in ["거래처", "거래처코드", "거래처명"]:
        keyed = (
            mapping[mapping[key].ne("")]
            .drop_duplicates(key, keep="last")
            .set_index(key)[["국가", "대륙"]]
        )
        if keyed.empty:
            continue
        country_match = result[key].map(keyed["국가"])
        continent_match = result[key].map(keyed["대륙"])
        hit = ~matched & (country_match.notna() | continent_match.notna())
        result.loc[hit, "국가"] = country_match.loc[hit].fillna("미지정")
        result.loc[hit, "대륙"] = continent_match.loc[hit].fillna("미지정")
        matched = matched | hit

    result["국가"] = result["국가"].fillna("미지정").replace("", "미지정")
    result["대륙"] = result["대륙"].fillna("미지정").replace("", "미지정")

    return result


def load_product_mapping(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    """CSV/XLSX 형식의 SKU-제품군 매핑 파일을 검증해 불러옵니다."""
    suffix = Path(file_name).suffix.lower()
    buffer = io.BytesIO(file_bytes)

    if suffix == ".csv":
        try:
            mapping = pd.read_csv(buffer, encoding="utf-8-sig")
        except UnicodeDecodeError:
            buffer.seek(0)
            mapping = pd.read_csv(buffer, encoding="cp949")
    elif suffix in {".xlsx", ".xlsm"}:
        workbook = pd.ExcelFile(buffer, engine="openpyxl")
        target_sheet = (
            "제품군 매핑"
            if "제품군 매핑" in workbook.sheet_names
            else workbook.sheet_names[0]
        )
        mapping = pd.read_excel(workbook, sheet_name=target_sheet)
    else:
        raise ValueError("제품군 매핑 파일은 CSV 또는 XLSX 형식만 지원합니다.")

    mapping.columns = [clean_column_name(col) for col in mapping.columns]
    required = ["품목코드", "대분류", "제품군"]
    missing = [col for col in required if col not in mapping.columns]
    if missing:
        raise ValueError("필수 컬럼이 없습니다: " + ", ".join(missing))

    for col in PRODUCT_MAPPING_COLUMNS:
        if col not in mapping.columns:
            mapping[col] = ""
        mapping[col] = mapping[col].astype("string").fillna("").str.strip()

    mapping = mapping[mapping["품목코드"].ne("")].copy()
    if mapping.empty:
        raise ValueError("품목코드가 입력된 매핑 행이 없습니다.")

    duplicate_codes = sort_unique(
        mapping.loc[
            mapping.duplicated("품목코드", keep=False),
            "품목코드",
        ]
    )
    if duplicate_codes:
        preview = ", ".join(duplicate_codes[:5])
        suffix_text = " 외" if len(duplicate_codes) > 5 else ""
        raise ValueError(
            f"중복 품목코드가 {len(duplicate_codes):,}개 있습니다: "
            f"{preview}{suffix_text}"
        )

    for col in ["대분류", "제품군", "판매형태", "에디션", "시장사양"]:
        mapping[col] = mapping[col].mask(mapping[col].eq(""), "미분류")
    mapping["기본분석포함"] = mapping["기본분석포함"].where(
        mapping["기본분석포함"].isin(["포함", "제외"]),
        "포함",
    )
    mapping["검토상태"] = mapping["검토상태"].mask(
        mapping["검토상태"].eq(""),
        "미확인",
    )
    return mapping[PRODUCT_MAPPING_COLUMNS].copy()


def apply_product_mapping(
    sellin_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """품목코드(SKU) 기준으로 제품 분류를 m:1 연결합니다."""
    result = sellin_df.copy()
    mapping = mapping_df.copy()

    # 재적용 시 기존 매핑 컬럼이 남아 접미사가 붙지 않도록 제거합니다.
    mapped_columns = [
        "품목코드",
        "매핑품목명",
        "대분류",
        "제품군",
        "판매형태",
        "에디션",
        "시장사양",
        "기본분석포함",
        "검토상태",
        "검토사유",
        "제품군매핑상태",
        "대분류_분석",
    ]
    result = result.drop(
        columns=[col for col in mapped_columns if col in result.columns],
        errors="ignore",
    )

    mapping = mapping.rename(columns={"품목명": "매핑품목명"})
    result = result.merge(
        mapping,
        left_on="SKU",
        right_on="품목코드",
        how="left",
        validate="m:1",
    )

    matched = result["품목코드"].notna()
    result["제품군매핑상태"] = np.where(matched, "매핑완료", "미분류")
    for col in ["대분류", "제품군", "판매형태", "에디션", "시장사양"]:
        result[col] = (
            result[col].astype("string").fillna("").str.strip().replace("", "미분류")
        )
    result["기본분석포함"] = (
        result["기본분석포함"]
        .astype("string")
        .fillna("포함")
        .where(lambda values: values.isin(["포함", "제외"]), "포함")
    )
    result["검토상태"] = (
        result["검토상태"].astype("string").fillna("미확인").replace("", "미확인")
    )
    result["검토사유"] = result["검토사유"].astype("string").fillna("")
    result["제품군_분석"] = result["제품군"]
    result["대분류_분석"] = result["대분류"]

    sku_master = result[result["SKU"].ne("")][
        ["SKU", "제품명_정리", "제품군매핑상태"]
    ].drop_duplicates("SKU")
    unmatched_skus = (
        sku_master[sku_master["제품군매핑상태"].eq("미분류")]
        .rename(columns={"SKU": "품목코드", "제품명_정리": "품목명"})
        [["품목코드", "품목명"]]
        .sort_values("품목코드")
        .reset_index(drop=True)
    )
    total_skus = int(sku_master["SKU"].nunique())
    matched_skus = total_skus - len(unmatched_skus)
    quality = {
        "total_skus": total_skus,
        "matched_skus": matched_skus,
        "unmatched_sku_count": len(unmatched_skus),
        "unmatched_skus": unmatched_skus,
        "matched_row_count": int(matched.sum()),
        "unmatched_row_count": int((~matched).sum()),
        "review_sku_count": int(
            result.loc[result["검토상태"].eq("검토필요"), "SKU"].nunique()
        ),
    }
    return result, quality


def make_product_group_summary(
    df: pd.DataFrame,
    dimension: str = "제품군",
) -> pd.DataFrame:
    """대분류 또는 제품군 단위의 수량·금액·구성비 요약을 생성합니다."""
    result = (
        df.groupby(dimension, as_index=False, dropna=False)
        .agg(
            출고수량=("분석수량", "sum"),
            출고금액=("분석금액", "sum"),
            SKU수=("SKU", "nunique"),
            거래처수=("거래처", "nunique"),
            국가수=("국가", "nunique"),
            대륙수=("대륙", "nunique"),
        )
        .sort_values(["출고수량", "출고금액"], ascending=False)
        .reset_index(drop=True)
    )
    total_qty = result["출고수량"].sum()
    total_amount = result["출고금액"].sum()
    result["수량비중"] = np.where(total_qty != 0, result["출고수량"] / total_qty, 0)
    result["금액비중"] = np.where(
        total_amount != 0,
        result["출고금액"] / total_amount,
        0,
    )
    return result


def prepare_data(
    raw_df: pd.DataFrame,
    amount_policy: str = AMOUNT_POLICY_ADJUSTED,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """ERP SELL-IN 원본을 분석용 형태로 정리."""
    df = raw_df.copy()
    df.columns = [clean_column_name(col) for col in df.columns]

    # 완전히 비어 있는 행과 자동 생성된 Unnamed 컬럼 제거
    df = df.dropna(how="all").copy()
    unnamed = [col for col in df.columns if col.lower().startswith("unnamed")]
    if unnamed:
        df = df.drop(columns=unnamed)

    missing_required = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_required:
        return df, {
            "missing_required": missing_required,
            "raw_rows": len(raw_df),
            "prepared_rows": 0,
        }

    # 날짜 변환
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = safe_datetime(df[col])

    # 숫자 변환: 변환 실패를 조용히 0으로 처리하지 않고 별도 보고합니다.
    numeric_issue_frames: list[pd.DataFrame] = []
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            original = df[col].copy()
            converted = safe_numeric(original)
            failed = nonblank_mask(original) & converted.isna()
            if failed.any():
                issue = pd.DataFrame(
                    {
                        "원본행": df.index[failed] + 2,
                        "컬럼": col,
                        "원본값": original.loc[failed].astype("string"),
                    }
                )
                numeric_issue_frames.append(issue)
            df[col] = converted

    numeric_issues = (
        pd.concat(numeric_issue_frames, ignore_index=True)
        if numeric_issue_frames
        else pd.DataFrame(columns=["원본행", "컬럼", "원본값"])
    )

    # 분석 기준 컬럼 생성
    df["분석수량"] = df["출고수량"].fillna(0)

    has_adjusted_amount = "조정출고금액" in df.columns
    has_original_amount = "출고금액" in df.columns
    amount_source_error = ""

    if amount_policy == AMOUNT_POLICY_ORIGINAL:
        if has_original_amount:
            df["분석금액"] = df["출고금액"]
        else:
            df["분석금액"] = np.nan
            amount_source_error = "선택한 금액 기준에 필요한 '출고금액' 컬럼이 없습니다."
    elif has_adjusted_amount and has_original_amount:
        adjusted = df["조정출고금액"]
        if amount_policy == AMOUNT_POLICY_ZERO_AS_BLANK:
            adjusted = adjusted.mask(adjusted.eq(0))
        df["분석금액"] = adjusted.where(adjusted.notna(), df["출고금액"])
    elif has_adjusted_amount:
        df["분석금액"] = df["조정출고금액"]
    elif has_original_amount:
        df["분석금액"] = df["출고금액"]
    else:
        df["분석금액"] = np.nan
        amount_source_error = "'출고금액'과 '조정출고금액' 컬럼이 모두 없습니다."

    if not amount_source_error and not df["분석금액"].notna().any():
        amount_source_error = "금액 컬럼은 있지만 집계 가능한 금액 값이 없습니다."
    df["분석금액"] = df["분석금액"].fillna(0)

    # 판매처 코드/명이 모두 있으면 판매처 쌍을 사용하고,
    # 한쪽이라도 없으면 납품처 코드/명 쌍으로 보완합니다.
    sales_code = first_existing_value(df, "판매처", "__없는컬럼__")
    sales_name = first_existing_value(df, "판매처명", "__없는컬럼__")
    delivery_code = first_existing_value(df, "납품처", "__없는컬럼__")
    delivery_name = first_existing_value(df, "납품처명", "__없는컬럼__")

    use_sales_pair = sales_code.ne("") & sales_name.ne("")
    df["거래처코드"] = sales_code.where(use_sales_pair, delivery_code)
    df["거래처명"] = sales_name.where(use_sales_pair, delivery_name)

    df["거래처코드"] = df["거래처코드"].mask(
        df["거래처코드"].eq(""),
        sales_code.mask(sales_code.eq(""), delivery_code),
    )
    df["거래처명"] = df["거래처명"].mask(
        df["거래처명"].eq(""),
        sales_name.mask(sales_name.eq(""), delivery_name),
    )
    df["거래처"] = combine_display_key(df["거래처명"], df["거래처코드"])

    df["SKU"] = df["품목"].astype("string").fillna("").str.strip()
    df["제품명"] = df["품목명"].astype("string").fillna("").str.strip()
    df["제품명_정리"] = df["제품명"].map(strip_product_version)
    df["제품버전"] = df["제품명"].map(product_version)

    if "저장위치" in df.columns:
        df["창고"] = df["저장위치"].map(simplify_warehouse)
    else:
        df["창고"] = "미기재"

    # 제품군은 실제 파일에서 값이 가장 잘 채워진 컬럼을 우선 사용
    product_group_candidates = ["제품군", "대분류", "중분류", "품목그룹명", "품목제품군"]
    existing_candidates = [col for col in product_group_candidates if col in df.columns]
    if existing_candidates:
        df["제품군_분석"] = "미기재"
        for col in existing_candidates:
            values = df[col].astype("string").fillna("").str.strip()
            current = df["제품군_분석"].astype("string")
            df["제품군_분석"] = current.mask(
                current.eq("미기재") & values.ne(""),
                values,
            )
    else:
        df["제품군_분석"] = "미기재"

    shipment_number_present = (
        "출고번호" in df.columns and nonblank_mask(df["출고번호"]).any()
    )

    # 조직/지역 컬럼이 없더라도 화면이 중단되지 않도록 보완
    for col in ["판매지역", "영업그룹", "영업담당자명", "수불유형", "출고번호"]:
        if col not in df.columns:
            df[col] = "미기재"
        else:
            df[col] = df[col].astype("string").fillna("미기재").str.strip()
            df[col] = df[col].mask(df[col].eq(""), "미기재")

    df["연월"] = df["출고일"].dt.to_period("M").astype("string")
    df["연도"] = df["출고일"].dt.year.astype("Int64")
    df["월"] = df["출고일"].dt.month.astype("Int64")
    df["단가_계산"] = np.where(
        df["분석수량"].ne(0),
        df["분석금액"] / df["분석수량"],
        np.nan,
    )

    invalid_date_count = int(df["출고일"].isna().sum())
    invalid_sku_count = int(df["SKU"].eq("").sum())
    invalid_customer_count = int(df["거래처"].eq("미기재").sum())

    quality = {
        "missing_required": [],
        "raw_rows": len(raw_df),
        "prepared_rows": len(df),
        "invalid_date_count": invalid_date_count,
        "invalid_sku_count": invalid_sku_count,
        "invalid_customer_count": invalid_customer_count,
        "numeric_issues": numeric_issues,
        "numeric_failure_count": len(numeric_issues),
        "numeric_failure_counts": (
            numeric_issues.groupby("컬럼").size().to_dict()
            if not numeric_issues.empty
            else {}
        ),
        "amount_policy": amount_policy,
        "amount_source_error": amount_source_error,
        "shipment_number_present": shipment_number_present,
    }
    return df, quality


def apply_multiselect_filter(
    df: pd.DataFrame,
    column: str,
    selected: list[str],
) -> pd.DataFrame:
    if selected:
        return df[df[column].isin(selected)].copy()
    return df


def make_customer_summary(df: pd.DataFrame) -> pd.DataFrame:
    source = df.copy()
    if "국가" not in source.columns:
        source["국가"] = "미지정"
    if "대륙" not in source.columns:
        source["대륙"] = "미지정"
    result = (
        source.groupby(["거래처", "거래처명", "거래처코드"], dropna=False)
        .agg(
            국가=("국가", representative_text),
            대륙=("대륙", representative_text),
            출고수량=("분석수량", "sum"),
            출고금액=("분석금액", "sum"),
            SKU수=("SKU", "nunique"),
            출고건수=("출고번호", "nunique"),
            최근출고일=("출고일", "max"),
        )
        .reset_index()
    )
    result["거래처표시"] = (
        result["국가"].astype("string").fillna("미지정")
        + " | "
        + result["거래처명"].astype("string").fillna("미기재")
    )
    total_amount = result["출고금액"].sum()
    total_qty = result["출고수량"].sum()
    result["금액비중"] = np.where(total_amount != 0, result["출고금액"] / total_amount, 0)
    result["수량비중"] = np.where(total_qty != 0, result["출고수량"] / total_qty, 0)
    result["건당평균금액"] = np.where(
        result["출고건수"].ne(0),
        result["출고금액"] / result["출고건수"],
        np.nan,
    )
    return result.sort_values(["출고수량", "거래처"], ascending=[False, True])


def group_other_continent_customers_for_chart(
    customer_summary: pd.DataFrame,
) -> pd.DataFrame:
    """대륙이 '기타'인 거래처를 차트에서 하나의 '기타' 막대로 합칩니다."""
    chart_summary = customer_summary.copy()
    if "대륙" not in chart_summary.columns:
        return chart_summary

    continent = (
        chart_summary["대륙"]
        .astype("string")
        .fillna("")
        .str.strip()
    )
    other_mask = continent.eq("기타")
    if not other_mask.any():
        return chart_summary

    other_quantity = chart_summary.loc[other_mask, "출고수량"].sum()
    chart_summary = chart_summary.loc[~other_mask].copy()
    other_row = pd.DataFrame(
        [{
            "거래처표시": "기타",
            "출고수량": other_quantity,
            "대륙": "기타",
        }]
    )
    return pd.concat([chart_summary, other_row], ignore_index=True, sort=False)


def make_sku_summary(df: pd.DataFrame) -> pd.DataFrame:
    # 순위는 SKU만을 고유 키로 집계합니다. 제품명 변경 이력은 품질 탭에서 별도 확인합니다.
    result = (
        df.groupby("SKU", dropna=False)
        .agg(
            출고수량=("분석수량", "sum"),
            출고금액=("분석금액", "sum"),
            거래처수=("거래처", "nunique"),
            출고건수=("출고번호", "nunique"),
            최근출고일=("출고일", "max"),
            제품명_원본=("제품명", representative_text),
            제품명_정리=("제품명_정리", representative_text),
            제품버전=("제품버전", representative_text),
            제품군_분석=("제품군_분석", representative_text),
            대분류=("대분류", representative_text),
            제품군=("제품군", representative_text),
            판매형태=("판매형태", representative_text),
            에디션=("에디션", representative_text),
            검토상태=("검토상태", representative_text),
        )
        .reset_index()
    )
    total_amount = result["출고금액"].sum()
    total_qty = result["출고수량"].sum()
    result["금액비중"] = np.where(total_amount != 0, result["출고금액"] / total_amount, 0)
    result["수량비중"] = np.where(total_qty != 0, result["출고수량"] / total_qty, 0)
    result["평균출고단가"] = np.where(
        result["출고수량"].ne(0),
        result["출고금액"] / result["출고수량"],
        np.nan,
    )
    return result.sort_values(["출고수량", "출고금액"], ascending=False)


def safe_download_filename_part(value: object) -> str:
    """거래처명을 운영체제와 관계없이 안전한 다운로드 파일명으로 바꿉니다."""
    text = re.sub(r'[\\/:*?"<>|]+', "_", str(value)).strip(" ._")
    return text[:60] or "거래처"


@st.cache_data(show_spinner=False)
def build_customer_sku_excel(
    customer_sku_summary: pd.DataFrame,
    customer_label: str,
    start_date_text: str,
    end_date_text: str,
) -> bytes:
    """현재 필터 기준의 선택 거래처 SKU 분석표를 서식 있는 XLSX로 만듭니다."""
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    export = customer_sku_summary.sort_values(
        ["출고수량", "SKU"],
        ascending=[False, True],
        kind="stable",
    ).reset_index(drop=True)
    export.insert(0, "순위", range(1, len(export) + 1))
    export = export.rename(
        columns={
            "SKU": "SKU 코드",
            "제품명_원본": "제품명",
            "출고수량": "출고수량 (개)",
            "수량비중": "수량 비중",
        }
    )[
        [
            "순위",
            "SKU 코드",
            "제품명",
            "대분류",
            "제품군",
            "판매형태",
            "출고수량 (개)",
            "수량 비중",
        ]
    ]

    total_quantity = float(export["출고수량 (개)"].sum())
    workbook_buffer = io.BytesIO()
    with pd.ExcelWriter(workbook_buffer, engine="openpyxl") as writer:
        export.to_excel(
            writer,
            sheet_name="SKU 분석",
            index=False,
            startrow=5,
        )
        worksheet = writer.sheets["SKU 분석"]
        worksheet.sheet_view.showGridLines = False
        worksheet.freeze_panes = "A7"

        worksheet.merge_cells("A1:H1")
        worksheet["A1"] = "SELL-IN 거래처 SKU 분석"
        worksheet["A1"].font = Font(bold=True, color="FFFFFF", size=16)
        worksheet["A1"].fill = PatternFill("solid", fgColor="1D4ED8")
        worksheet["A1"].alignment = Alignment(horizontal="left", vertical="center")
        worksheet.row_dimensions[1].height = 30

        worksheet["A2"] = "거래처"
        worksheet.merge_cells("B2:H2")
        worksheet["B2"] = customer_label
        worksheet["A3"] = "분석 기간"
        worksheet.merge_cells("B3:C3")
        worksheet["B3"] = f"{start_date_text} ~ {end_date_text}"
        worksheet["D3"] = "총 출고수량 (개)"
        worksheet["E3"] = total_quantity
        worksheet["F3"] = "거래 SKU"
        worksheet["G3"] = len(export)
        worksheet["A4"] = "다운로드 기준"
        worksheet.merge_cells("B4:H4")
        worksheet["B4"] = "화면에 적용된 기간·대륙·국가·제품·조직·검색 필터 기준"

        label_fill = PatternFill("solid", fgColor="E2E8F0")
        value_fill = PatternFill("solid", fgColor="F8FAFC")
        for coordinate in ["A2", "B2", "A3", "B3", "D3", "E3", "F3", "G3", "A4", "B4"]:
            worksheet[coordinate].alignment = Alignment(vertical="center")
            worksheet[coordinate].fill = value_fill
        for coordinate in ["A2", "A3", "D3", "F3", "A4"]:
            worksheet[coordinate].font = Font(bold=True, color="0F172A")
            worksheet[coordinate].fill = label_fill
        worksheet["E3"].number_format = "#,##0"
        worksheet["G3"].number_format = "#,##0"

        header_fill = PatternFill("solid", fgColor="DBEAFE")
        thin_gray = Side(style="thin", color="CBD5E1")
        for cell in worksheet[6]:
            cell.font = Font(bold=True, color="0F172A")
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = Border(bottom=thin_gray)
        worksheet.row_dimensions[6].height = 24

        band_fill = PatternFill("solid", fgColor="EFF6FF")
        for row in range(7, 7 + len(export)):
            worksheet.cell(row=row, column=1).alignment = Alignment(horizontal="center")
            worksheet.cell(row=row, column=7).number_format = "#,##0"
            worksheet.cell(row=row, column=8).number_format = "0.0%"
            for column in range(1, 9):
                cell = worksheet.cell(row=row, column=column)
                cell.border = Border(bottom=thin_gray)
                cell.alignment = Alignment(
                    vertical="center",
                    horizontal=("right" if column in {7, 8} else None),
                )
                if (row - 7) % 2 == 0:
                    cell.fill = band_fill

        last_row = 6 + len(export)
        worksheet.auto_filter.ref = f"A6:H{last_row}"

        column_widths = {
            "A": 8,
            "B": 18,
            "C": 42,
            "D": 16,
            "E": 24,
            "F": 14,
            "G": 18,
            "H": 14,
        }
        for column, width in column_widths.items():
            worksheet.column_dimensions[column].width = width
        worksheet.print_title_rows = "1:6"
        worksheet.sheet_properties.pageSetUpPr.fitToPage = True
        worksheet.page_setup.fitToWidth = 1
        worksheet.page_setup.fitToHeight = 0
        worksheet.sheet_properties.outlinePr.summaryBelow = True

    return workbook_buffer.getvalue()


def make_customer_sku_rank(df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """거래처별 출고수량 상위 SKU를 동률과 관계없이 정확히 N개까지 반환."""
    source = df.copy()
    if "국가" not in source.columns:
        source["국가"] = "미지정"
    if "대륙" not in source.columns:
        source["대륙"] = "미지정"
    result = (
        source.groupby(
            ["거래처", "거래처명", "거래처코드", "국가", "대륙", "SKU"],
            as_index=False,
        )
        .agg(
            출고수량=("분석수량", "sum"),
            출고금액=("분석금액", "sum"),
            제품명_정리=("제품명_정리", representative_text),
        )
        .sort_values(
            ["거래처", "출고수량", "SKU"],
            ascending=[True, False, True],
            kind="stable",
        )
    )
    result["거래처내순위"] = result.groupby("거래처").cumcount() + 1
    result["거래처표시"] = (
        result["국가"].astype("string").fillna("미지정")
        + " | "
        + result["거래처명"].astype("string").fillna("미기재")
    )
    return result[result["거래처내순위"] <= top_n].sort_values(
        ["거래처표시", "거래처내순위", "출고수량", "SKU"],
        ascending=[True, True, False, True],
    )


def make_monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    monthly = (
        df.dropna(subset=["출고일"])
        .groupby("연월", as_index=False)
        .agg(
            출고수량=("분석수량", "sum"),
            출고금액=("분석금액", "sum"),
        )
        .sort_values("연월")
    )
    return monthly


def make_quantity_trend(df: pd.DataFrame, granularity: str) -> pd.DataFrame:
    """월/주/일 단위 출고수량 추이 데이터 생성."""
    dated = df.dropna(subset=["출고일"]).copy()
    if granularity == "월별":
        dated["기간"] = dated["출고일"].dt.to_period("M").astype("string")
    elif granularity == "주별":
        dated["기간"] = (
            dated["출고일"]
            .dt.to_period("W-SUN")
            .apply(lambda period: period.start_time.date())
        )
    else:
        dated["기간"] = dated["출고일"].dt.date

    return (
        dated.groupby("기간", as_index=False)
        .agg(출고수량=("분석수량", "sum"))
        .sort_values("기간")
    )


def top_n_chart(
    summary: pd.DataFrame,
    category: str,
    value: str,
    title: str,
    top_n: int = 10,
    show_share: bool = True,
):
    # 집계 후 남아 있는 기존 인덱스나 Plotly의 범주 정렬에 순위가 좌우되지 않도록
    # 표시 기준으로 명시 정렬한 뒤 인덱스를 새로 부여합니다.
    tie_breakers = [
        col for col in ["SKU", category] if col in summary.columns and col != value
    ]
    chart_df = (
        summary.sort_values(
            [value, *tie_breakers],
            ascending=[False, *([True] * len(tie_breakers))],
            kind="stable",
        )
        .head(top_n)
        .reset_index(drop=True)
        .copy()
    )
    chart_df["_순위"] = range(1, len(chart_df) + 1)
    chart_df["_표시명"] = (
        chart_df["_순위"].astype(str)
        + ". "
        + chart_df[category].astype("string").fillna("미기재")
    )
    total_value = summary[value].sum()
    chart_df["_비중"] = np.where(
        total_value != 0,
        chart_df[value] / total_value,
        0,
    )
    if value == "출고금액":
        chart_df["_차트값"] = chart_df[value] / 1_000
        xaxis_title = "출고금액 (천원)"
        hovertemplate = (
            "%{y}<br>출고금액: %{customdata[0]:,.0f}원"
            "<br>비중: %{customdata[1]:.1%}<extra></extra>"
        )
    else:
        chart_df["_차트값"] = chart_df[value]
        xaxis_title = "출고수량 (개)"
        hovertemplate = "%{y}<br>출고수량: %{customdata[0]:,.0f}개"
        if show_share:
            hovertemplate += "<br>비중: %{customdata[1]:.1%}"
        hovertemplate += "<extra></extra>"
    chart_df["_내부텍스트"] = chart_df["_차트값"].map(lambda x: f"{x:,.0f}")
    chart_df["_외부텍스트"] = (
        chart_df["_비중"].map(lambda x: f"{x:.1%}") if show_share else ""
    )
    max_value = chart_df["_차트값"].max() if not chart_df.empty else 0
    min_value = chart_df["_차트값"].min() if not chart_df.empty else 0
    # 비중 라벨을 막대 끝에서 일정 거리만큼 띄웁니다. 각 막대값의 비율을
    # 곱하는 대신 전체 최댓값 기준의 고정 간격을 사용해야 짧은 막대에서도
    # 동일한 픽셀 간격처럼 보입니다.
    label_gap = max_value * 0.012 if max_value > 0 else 0
    chart_df["_비중위치"] = chart_df["_차트값"] + label_gap
    fig = px.bar(
        chart_df,
        x="_차트값",
        y="_표시명",
        orientation="h",
        text="_내부텍스트",
        title=title,
        custom_data=[value, "_비중"],
        # 순위 배열은 1위부터 유지하고, 아래에서 y축 자체를 반전해
        # Plotly 버전에 관계없이 첫 번째 범주(1위)가 맨 위에 오게 합니다.
        category_orders={"_표시명": chart_df["_표시명"].tolist()},
        color_discrete_sequence=["#2563EB"],
    )
    fig.update_traces(
        texttemplate="%{text}",
        textposition="inside",
        insidetextanchor="middle",
        textangle=0,
        constraintext="inside",
        textfont_color="white",
        cliponaxis=False,
        hovertemplate=hovertemplate,
        selector=dict(type="bar"),
    )
    if show_share:
        fig.add_trace(
            go.Scatter(
                x=chart_df["_비중위치"],
                y=chart_df["_표시명"],
                text=chart_df["_외부텍스트"],
                mode="text",
                textposition="middle right",
                cliponaxis=False,
                hoverinfo="skip",
                showlegend=False,
            )
        )
    fig.update_layout(
        height=max(500, len(chart_df) * 34 + 120),
        margin=dict(l=20, r=80 if show_share else 25, t=55, b=20),
        yaxis_title="",
        xaxis_title=xaxis_title,
        xaxis_tickformat=",.0f",
        showlegend=False,
        uniformtext_minsize=10,
        # 막대 폭이 숫자를 담기에 부족하면 억지로 회전·축소하지 않고 숨깁니다.
        uniformtext_mode="hide",
    )
    if min_value < 0:
        positive_limit = max_value * (1.20 if show_share else 1.05)
        fig.update_xaxes(range=[min_value * 1.10, max(0, positive_limit)])
    elif max_value > 0:
        fig.update_xaxes(range=[0, max_value * (1.20 if show_share else 1.05)])
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=chart_df["_표시명"].tolist(),
        autorange="reversed",
    )
    return fig


def find_potential_duplicates(
    df: pd.DataFrame,
    shipment_number_present: bool,
) -> tuple[pd.Series, list[str]]:
    """출고번호 유무에 따라 중복 후보 기준을 분리해 오탐을 줄입니다."""
    mask = pd.Series(False, index=df.index)
    if shipment_number_present and "출고번호" in df.columns:
        shipment_key_cols = [
            col
            for col in ["출고번호", "출고순번", "수불번호", "수불순번", "품목"]
            if col in df.columns
        ]
        valid = df["출고번호"].astype("string").fillna("").str.strip()
        valid = valid.ne("") & valid.ne("미기재")
        if shipment_key_cols:
            mask.loc[valid] = df.loc[valid].duplicated(
                subset=shipment_key_cols,
                keep=False,
            )

        # 파일 전체에 출고번호가 존재하더라도 일부 행만 공란일 수 있습니다.
        # 그 행은 날짜·거래처·SKU·수량·금액·창고 조합으로 별도 점검합니다.
        fallback_key_cols = [
            col
            for col in [
                "출고일",
                "거래처코드",
                "SKU",
                "분석수량",
                "분석금액",
                "창고",
            ]
            if col in df.columns
        ]
        if fallback_key_cols:
            missing_shipment = ~valid
            mask.loc[missing_shipment] = df.loc[missing_shipment].duplicated(
                subset=fallback_key_cols,
                keep=False,
            )
        return mask, shipment_key_cols + fallback_key_cols

    key_cols = [
        col
        for col in [
            "출고일",
            "거래처코드",
            "SKU",
            "분석수량",
            "분석금액",
            "창고",
        ]
        if col in df.columns
    ]
    if key_cols:
        mask = df.duplicated(subset=key_cols, keep=False)
    return mask, key_cols


def style_table(df: pd.DataFrame, percent_cols: list[str] | None = None):
    percent_cols = percent_cols or []
    formats = {
        col: "{:,.0f}"
        for col in df.columns
        if col in {
            "출고수량",
            "출고수량 (개)",
            "출고금액",
            "출고금액(원)",
            "출고금액 (천원)",
            "건당평균금액",
            "건당평균금액 (천원)",
            "평균출고단가",
            "누적출고금액",
            "누적출고수량",
        }
    }
    formats.update({col: "{:.1%}" for col in percent_cols if col in df.columns})
    return df.style.format(formats, na_rep="-")


# ---------------------------------------------------------------------
# 화면 시작
# ---------------------------------------------------------------------
st.title("SELL-IN 분석 대시보드")
st.caption(
    "ERP 출고 데이터를 기준으로 전체 실적, 대륙·국가·제품군, 거래처, SKU, 월별 추이 및 데이터 품질을 분석합니다."
)

uploaded_file = st.sidebar.file_uploader(
    "SELL-IN 엑셀 업로드",
    type=["xlsx", "xlsm"],
    help=(
        "업로드한 파일은 GitHub 저장소에 저장되지 않으며, "
        "서버 공용 데이터 캐시를 사용하지 않고 현재 실행에서만 처리합니다."
    ),
)

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    source_file_name = uploaded_file.name
    st.sidebar.success(f"업로드 데이터 사용 중: {source_file_name}")
else:
    st.info(
        "왼쪽 사이드바에서 SELL-IN 엑셀 파일을 업로드하면 대시보드가 시작됩니다."
    )
    st.markdown(
        """
        **주요 제공 화면**
        - 전체 SELL-IN 핵심 KPI와 월별 추이
        - 분석에 포함하거나 제외할 거래처 직접 선택
        - 전체 Top SKU / Top 거래처
        - 거래처별 Top SKU
        - 거래처·월별 출고수량 히트맵 및 실적 집중도
        - 거래처별 국가·대륙 매핑 및 지역별 SELL-IN 분석
        - SKU 제품군 매핑 및 대륙 → 국가 → 대분류 → 제품군 → SKU/홋수 분석
        - 본품·미니·세트·리필 및 에디션 필터
        - 판매지역·영업그룹·담당자·창고 분석
        - 누락값·음수 출고·잠재 중복 등 데이터 품질 점검
        """
    )
    st.stop()

try:
    sheet_names = get_sheet_names(file_bytes)
except Exception as exc:
    st.error(f"엑셀 파일을 열 수 없습니다: {exc}")
    st.stop()

sheet_name = st.sidebar.selectbox("분석 시트", sheet_names)

try:
    raw_df = load_excel(file_bytes, sheet_name)
except Exception as exc:
    st.error(f"데이터를 읽는 중 오류가 발생했습니다: {exc}")
    st.stop()

raw_columns = {clean_column_name(col) for col in raw_df.columns}
has_adjusted_amount = "조정출고금액" in raw_columns
has_original_amount = "출고금액" in raw_columns

if not has_adjusted_amount and not has_original_amount:
    st.error("금액 분석에 필요한 '출고금액' 또는 '조정출고금액' 컬럼이 없습니다.")
    st.stop()

amount_policy_options: list[str] = []
if has_adjusted_amount and has_original_amount:
    amount_policy_options = [
        AMOUNT_POLICY_ADJUSTED,
        AMOUNT_POLICY_ZERO_AS_BLANK,
        AMOUNT_POLICY_ORIGINAL,
    ]
elif has_adjusted_amount:
    amount_policy_options = [AMOUNT_POLICY_ADJUSTED]
else:
    amount_policy_options = [AMOUNT_POLICY_ORIGINAL]

with st.sidebar.expander("금액 집계 기준", expanded=False):
    amount_policy = st.radio(
        "적용 방식",
        amount_policy_options,
        help=(
            "기본값은 기존과 동일하게 조정출고금액이 입력된 행만 우선합니다. "
            "ERP가 미입력 조정금액을 0으로 채우는 경우에는 두 번째 방식을 선택하세요."
        ),
    )

try:
    df, quality = prepare_data(raw_df, amount_policy)
except Exception as exc:
    st.error(f"데이터를 정리하는 중 오류가 발생했습니다: {exc}")
    st.stop()

if quality.get("missing_required"):
    st.error(
        "필수 컬럼이 없습니다: "
        + ", ".join(quality["missing_required"])
        + "\n\n필요한 최소 컬럼: 출고일, 출고수량, 품목, 품목명"
    )
    st.stop()

if quality.get("amount_source_error"):
    st.error(str(quality["amount_source_error"]))
    st.stop()

if quality.get("numeric_failure_count", 0):
    st.warning(
        f"숫자로 변환되지 않은 값이 {quality['numeric_failure_count']:,}개 있습니다. "
        "해당 값은 0 또는 대체값으로 처리될 수 있으므로 "
        "'데이터 품질' 탭에서 반드시 확인하세요."
    )

# ---------------------------------------------------------------------
# 1. SKU별 제품군 매핑
# ---------------------------------------------------------------------
st.sidebar.divider()
st.sidebar.subheader("제품군 매핑")
product_mapping_file = st.sidebar.file_uploader(
    "제품군 매핑표 업로드",
    type=["csv", "xlsx", "xlsm"],
    key="product_mapping_upload",
    help=(
        "품목코드 기준으로 대분류·제품군·판매형태·에디션을 연결합니다. "
        "공개 저장소에는 매핑표를 포함하지 않으므로 분석할 때 직접 업로드해야 합니다."
    ),
)

if product_mapping_file is None:
    st.info(
        "왼쪽 사이드바에서 제품군 매핑표를 업로드하면 제품군 분석을 시작합니다."
    )
    st.stop()

try:
    product_mapping_bytes = product_mapping_file.getvalue()
    product_mapping_name = product_mapping_file.name
    st.sidebar.success(f"업로드 매핑 사용 중: {product_mapping_name}")
    product_mapping = load_product_mapping(
        product_mapping_bytes,
        product_mapping_name,
    )
    df, product_mapping_quality = apply_product_mapping(df, product_mapping)
except Exception as exc:
    st.error(f"제품군 매핑을 적용할 수 없습니다: {exc}")
    st.stop()

st.sidebar.caption(
    f"SKU 매핑 {product_mapping_quality['matched_skus']:,}/"
    f"{product_mapping_quality['total_skus']:,}개 · "
    f"검토 필요 {product_mapping_quality['review_sku_count']:,}개"
)

apply_default_product_scope = st.sidebar.checkbox(
    "기본 분석 포함 SKU만 사용",
    value=True,
    help=(
        "매핑표의 '기본분석포함'이 '제외'인 샘플·증정품을 전체 KPI와 "
        "차트에서 제외합니다. 미분류 신규 SKU는 누락 방지를 위해 포함됩니다."
    ),
)

excluded_product_sku_count = int(
    df.loc[df["기본분석포함"].eq("제외"), "SKU"].nunique()
)
excluded_product_row_count = int(df["기본분석포함"].eq("제외").sum())
if apply_default_product_scope:
    df = df[df["기본분석포함"].eq("포함")].copy()
    st.sidebar.caption(
        f"샘플·증정품 등 {excluded_product_sku_count:,}개 SKU · "
        f"{excluded_product_row_count:,}행 제외"
    )

if product_mapping_quality["unmatched_sku_count"]:
    st.warning(
        f"제품군이 미분류된 신규 SKU가 "
        f"{product_mapping_quality['unmatched_sku_count']:,}개 있습니다. "
        "분석에서는 제외하지 않고 '미분류' 제품군으로 포함했습니다. "
        "데이터 품질 탭에서 목록을 내려받아 매핑표에 추가하세요."
    )

# ---------------------------------------------------------------------
# 2. 거래처별 국가·대륙 매핑
# ---------------------------------------------------------------------
customer_master = (
    df[["거래처", "거래처코드", "거래처명"]]
    .drop_duplicates("거래처")
    .sort_values(["거래처명", "거래처코드"])
    .reset_index(drop=True)
)
customer_master["대륙"] = "미지정"
customer_master["국가"] = "미지정"

st.sidebar.divider()
st.sidebar.subheader("거래처 국가·대륙 매핑")
region_mapping_file = st.sidebar.file_uploader(
    "국가·대륙 매핑표 업로드",
    type=["csv", "xlsx", "xlsm"],
    key="region_mapping_upload",
    help="거래처, 거래처코드, 거래처명, 국가, 대륙 열이 있는 매핑표를 업로드합니다.",
)

mapping_message = ""
mapping_file_hash = "no_mapping"
if region_mapping_file is not None:
    try:
        mapping_file_bytes = region_mapping_file.getvalue()
        mapping_file_hash = hashlib.sha256(mapping_file_bytes).hexdigest()[:12]
        uploaded_mapping = load_region_mapping(
            mapping_file_bytes,
            region_mapping_file.name,
        )
        customer_master = apply_region_mapping(
            customer_master,
            uploaded_mapping,
        )
        mapping_message = f"{region_mapping_file.name} 매핑을 불러왔습니다."
    except Exception as exc:
        st.sidebar.error(f"국가·대륙 매핑 파일 오류: {exc}")

with st.expander(
    "거래처별 국가·대륙 입력·수정",
    expanded=bool(
        customer_master["국가"].eq("미지정").any()
        or customer_master["대륙"].eq("미지정").any()
    ),
):
    st.caption(
        "업로드한 값이 표시됩니다. 필요한 경우 국가와 대륙을 직접 수정한 뒤 "
        "'국가·대륙 매핑 적용'을 누르세요. "
        "여러 행을 수정해도 적용 버튼을 누를 때 한 번만 다시 계산됩니다."
    )
    if mapping_message:
        st.success(mapping_message)

    source_file_hash = hashlib.sha256(file_bytes).hexdigest()[:12]
    customer_identity_hash = hashlib.sha256(
        customer_master[["거래처", "거래처코드", "거래처명"]]
        .to_csv(index=False)
        .encode("utf-8")
    ).hexdigest()[:12]
    editor_key = (
        f"region_editor_{source_file_hash}_{sheet_name}_"
        f"{mapping_file_hash}_{customer_identity_hash}"
    )
    with st.form(key=f"region_form_{editor_key}", clear_on_submit=False):
        edited_region_mapping = st.data_editor(
            customer_master[
                ["거래처", "거래처코드", "거래처명", "국가", "대륙"]
            ],
            column_config={
                "거래처": st.column_config.TextColumn("거래처", disabled=True),
                "거래처코드": st.column_config.TextColumn("거래처코드", disabled=True),
                "거래처명": st.column_config.TextColumn("거래처명", disabled=True),
                "국가": st.column_config.TextColumn(
                    "국가",
                    help="예: 싱가포르, 말레이시아, 호주",
                ),
                "대륙": st.column_config.TextColumn(
                    "대륙",
                    help="매핑 파일에 사용하는 대륙명을 직접 입력하세요.",
                ),
            },
            disabled=["거래처", "거래처코드", "거래처명"],
            hide_index=True,
            width="stretch",
            key=editor_key,
        )
        st.form_submit_button("국가·대륙 매핑 적용", type="primary")

    mapping_csv = edited_region_mapping[
        ["거래처", "거래처코드", "거래처명", "국가", "대륙"]
    ].to_csv(
        index=False,
        encoding="utf-8-sig",
    )
    st.download_button(
        "거래처 국가·대륙 매핑 CSV 저장",
        data=mapping_csv,
        file_name="SELLIN_거래처_국가_대륙_매핑.csv",
        mime="text/csv",
    )

country_continent_conflicts = (
    edited_region_mapping[
        edited_region_mapping["국가"].ne("미지정")
        & edited_region_mapping["국가"].ne("")
        & edited_region_mapping["대륙"].ne("미지정")
    ]
    .groupby("국가")["대륙"]
    .nunique()
)
conflict_countries = country_continent_conflicts[
    country_continent_conflicts.gt(1)
].index.tolist()
if conflict_countries:
    st.error(
        "동일 국가에 서로 다른 대륙이 지정되어 있습니다: "
        + ", ".join(map(str, conflict_countries))
    )
    st.stop()

df = apply_region_mapping(df, edited_region_mapping)

unassigned_country_count = int(
    df.loc[df["국가"].eq("미지정"), "거래처"].nunique()
)
unassigned_customer_count = int(
    df.loc[df["대륙"].eq("미지정"), "거래처"].nunique()
)
if unassigned_country_count or unassigned_customer_count:
    unassigned_row_share = (
        df["국가"].eq("미지정") | df["대륙"].eq("미지정")
    ).mean()
    st.warning(
        f"국가 미지정 {unassigned_country_count:,}개 · "
        f"대륙 미지정 {unassigned_customer_count:,}개 거래처가 있습니다. "
        f"전체 행의 {unassigned_row_share:.1%}가 미지정이므로, 발표 전 "
        "'거래처별 국가·대륙 입력·수정'에서 매핑을 완료하세요."
    )

# ---------------------------------------------------------------------
# 3. 전체 분석 기준: 거래처 포함/제외
# ---------------------------------------------------------------------
st.sidebar.divider()
st.sidebar.subheader("전체 분석 거래처 기준")

all_customers = sort_unique(df["거래처"])
sidebar_customer_labels = (
    df[["거래처", "대륙", "국가", "거래처명"]]
    .drop_duplicates("거래처")
    .assign(
        거래처표시=lambda data: (
            data["국가"].astype("string").fillna("미지정")
            + " | "
            + data["거래처명"].astype("string").fillna("미기재")
        )
    )
    .set_index("거래처")["거래처표시"]
    .to_dict()
)
customer_mode = st.sidebar.radio(
    "거래처 적용 방식",
    ["제외할 거래처 선택", "포함할 거래처 선택"],
    horizontal=False,
    help="여기서 정한 거래처 기준은 모든 KPI와 차트에 공통 적용됩니다.",
)

if customer_mode == "제외할 거래처 선택":
    selected_customers = st.sidebar.multiselect(
        "전체 SELL-IN에서 제외",
        options=all_customers,
        default=[],
        format_func=lambda key: sidebar_customer_labels.get(key, key),
        placeholder="제외할 거래처 검색",
    )
    global_df = df[~df["거래처"].isin(selected_customers)].copy()
    customer_filter_message = (
        f"전체 {len(all_customers):,}개 거래처 중 "
        f"{len(selected_customers):,}개 제외"
    )
else:
    selected_customers = st.sidebar.multiselect(
        "전체 SELL-IN에 포함",
        options=all_customers,
        default=[],
        format_func=lambda key: sidebar_customer_labels.get(key, key),
        placeholder="포함할 거래처 검색",
        help="아무 거래처도 선택하지 않으면 전체 거래처가 포함됩니다.",
    )
    global_df = (
        df[df["거래처"].isin(selected_customers)].copy()
        if selected_customers
        else df.copy()
    )
    customer_filter_message = (
        f"전체 {len(all_customers):,}개 거래처 중 "
        f"{global_df['거래처'].nunique():,}개 포함"
    )

st.sidebar.caption(customer_filter_message)

if global_df.empty:
    st.warning("선택한 거래처 기준에 해당하는 데이터가 없습니다.")
    st.stop()

# ---------------------------------------------------------------------
# 4. 공통 상세 필터
# ---------------------------------------------------------------------
st.sidebar.divider()
st.sidebar.subheader("상세 필터")

valid_dates = global_df["출고일"].dropna()
if valid_dates.empty:
    st.error("유효한 출고일 데이터가 없습니다.")
    st.stop()

min_date = valid_dates.min().date()
max_date = valid_dates.max().date()

selected_dates = st.sidebar.date_input(
    "출고일 기간",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

if not isinstance(selected_dates, (tuple, list)):
    start_date = end_date = selected_dates
elif len(selected_dates) == 2:
    start_date, end_date = selected_dates
elif len(selected_dates) == 1:
    st.info("출고일 기간의 종료일도 선택해 주세요.")
    st.stop()
else:
    st.info("분석할 출고일 기간을 선택해 주세요.")
    st.stop()

filtered = global_df[
    global_df["출고일"].dt.date.between(start_date, end_date)
].copy()

include_negative = st.sidebar.checkbox(
    "반품/음수 출고 포함",
    value=True,
    help="체크 해제 시 출고수량이 0 이하인 행은 분석에서 제외됩니다.",
)
if not include_negative:
    filtered = filtered[filtered["분석수량"] > 0].copy()

continent_selected = st.sidebar.multiselect(
    "대륙",
    sort_unique(filtered["대륙"]),
    placeholder="미선택 시 전체",
)
filtered = apply_multiselect_filter(filtered, "대륙", continent_selected)

country_selected = st.sidebar.multiselect(
    "국가",
    sort_unique(filtered["국가"]),
    placeholder="미선택 시 전체",
)
filtered = apply_multiselect_filter(filtered, "국가", country_selected)

category_selected = st.sidebar.multiselect(
    "대분류",
    sort_unique(filtered["대분류"]),
    placeholder="예: 립, 베이스",
)
filtered = apply_multiselect_filter(filtered, "대분류", category_selected)

product_group_selected = st.sidebar.multiselect(
    "제품군",
    sort_unique(filtered["제품군"]),
    placeholder="예: 듀 틴트, 젤핏 틴트",
)
filtered = apply_multiselect_filter(filtered, "제품군", product_group_selected)

with st.sidebar.expander("판매형태·에디션 필터", expanded=False):
    sales_type_selected = st.multiselect(
        "판매형태",
        sort_unique(filtered["판매형태"]),
        placeholder="본품·미니·세트·리필",
        key="sidebar_sales_type_filter",
    )
    filtered = apply_multiselect_filter(filtered, "판매형태", sales_type_selected)

    edition_selected = st.multiselect(
        "에디션",
        sort_unique(filtered["에디션"]),
        placeholder="예: 일반, 몬치치",
        key="sidebar_edition_filter",
    )
    filtered = apply_multiselect_filter(filtered, "에디션", edition_selected)

    market_selected = st.multiselect(
        "시장사양",
        sort_unique(filtered["시장사양"]),
        placeholder="예: 미국 수출",
        key="sidebar_market_filter",
    )
    filtered = apply_multiselect_filter(filtered, "시장사양", market_selected)

region_selected = st.sidebar.multiselect(
    "판매지역",
    sort_unique(filtered["판매지역"]),
    placeholder="미선택 시 전체",
)
filtered = apply_multiselect_filter(filtered, "판매지역", region_selected)

group_selected = st.sidebar.multiselect(
    "영업그룹",
    sort_unique(filtered["영업그룹"]),
    placeholder="미선택 시 전체",
)
filtered = apply_multiselect_filter(filtered, "영업그룹", group_selected)

owner_selected = st.sidebar.multiselect(
    "영업담당자",
    sort_unique(filtered["영업담당자명"]),
    placeholder="미선택 시 전체",
)
filtered = apply_multiselect_filter(filtered, "영업담당자명", owner_selected)

warehouse_selected = st.sidebar.multiselect(
    "창고",
    sort_unique(filtered["창고"]),
    placeholder="미선택 시 전체",
)
filtered = apply_multiselect_filter(filtered, "창고", warehouse_selected)

sku_search = st.sidebar.text_input(
    "SKU / 제품명 / 제품군 검색",
    placeholder="예: 젤핏 틴트 또는 1AMU",
).strip()
if sku_search:
    search_mask = (
        filtered["SKU"].str.contains(
            sku_search, case=False, na=False, regex=False
        )
        | filtered["제품명"].str.contains(
            sku_search, case=False, na=False, regex=False
        )
        | filtered["제품명_정리"].str.contains(
            sku_search, case=False, na=False, regex=False
        )
        | filtered["제품군"].str.contains(
            sku_search, case=False, na=False, regex=False
        )
        | filtered["대분류"].str.contains(
            sku_search, case=False, na=False, regex=False
        )
    )
    filtered = filtered[search_mask].copy()

if filtered.empty:
    st.warning("현재 필터 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# ---------------------------------------------------------------------
# 상단 기준 안내
# ---------------------------------------------------------------------
filtered_qty = filtered["분석수량"].sum()
base_qty = global_df["분석수량"].sum()
qty_filter_share = filtered_qty / base_qty if base_qty != 0 else np.nan

st.caption(
    f"분석 기간 {start_date} ~ {end_date} · 거래처 기준 데이터 대비 "
    f"출고수량 {format_pct(qty_filter_share)}"
)

customer_summary = make_customer_summary(filtered)
sku_summary = make_sku_summary(filtered)
monthly_summary = make_monthly_summary(filtered)
category_summary = make_product_group_summary(filtered, "대분류")
product_group_summary = make_product_group_summary(filtered, "제품군")
customer_label_map = customer_summary.set_index("거래처")["거래처표시"].to_dict()

# ---------------------------------------------------------------------
# 탭
# ---------------------------------------------------------------------
tab_summary, tab_continent, tab_customer, tab_sku, tab_org, tab_quality = st.tabs(
    [
        "1. 전체 요약",
        "2. 대륙·국가 분석",
        "3. 거래처 분석",
        "4. 제품군·SKU 분석",
        "5. 조직·지역·창고",
        "6. 데이터 품질",
    ]
)

# ---------------------------------------------------------------------
# 전체 요약
# ---------------------------------------------------------------------
with tab_summary:
    total_qty = filtered["분석수량"].sum()
    total_amount = filtered["분석금액"].sum()

    k1, k2 = st.columns(2)
    k1.metric(
        "순출고수량 (개)",
        format_number(total_qty),
        help="정상 출고와 반품(음수 출고)을 합산한 수량입니다.",
    )
    k2.metric("출고금액 (천원)", format_number(total_amount / 1_000))

    st.subheader("전체 Top 20 SKU · 출고수량 기준")
    summary_sku_display = sku_summary.head(20).copy()
    summary_sku_display.insert(0, "순위", range(1, len(summary_sku_display) + 1))
    summary_sku_display = summary_sku_display.rename(
        columns={
            "제품명_정리": "제품명",
            "출고수량": "출고수량 (개)",
        }
    )
    st.plotly_chart(
        top_n_chart(
            sku_summary,
            "제품명_정리",
            "출고수량",
            "전체 Top 20 SKU · 출고수량 (개)",
            top_n=min(20, max(1, len(sku_summary))),
            show_share=False,
        ),
        width="stretch",
        key="summary_top20_sku_chart",
    )
    with st.expander("Top 20 SKU 상세 표", expanded=False):
        st.dataframe(
            style_table(
                summary_sku_display[
                    [
                        "순위",
                        "SKU",
                        "제품명",
                        "출고수량 (개)",
                    ]
                ]
            ),
            width="stretch",
            hide_index=True,
            height=735,
        )

    trend_granularity = st.radio(
        "출고수량 추이 단위",
        ["월별", "주별", "일별"],
        horizontal=True,
        key="summary_quantity_granularity",
    )
    quantity_trend = make_quantity_trend(filtered, trend_granularity)
    trend_fig = px.bar(
        quantity_trend,
        x="기간",
        y="출고수량",
        text="출고수량",
        title=f"{trend_granularity} SELL-IN 출고수량 추이 (개)",
        color_discrete_sequence=["#2563EB"],
    )
    trend_fig.update_traces(
        texttemplate="%{text:,.0f}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate="기간: %{x}<br>출고수량: %{y:,.0f}<extra></extra>",
    )
    trend_fig.update_layout(
        height=430,
        xaxis_title="",
        yaxis_title="출고수량 (개)",
        yaxis_tickformat=",.0f",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    st.plotly_chart(
        trend_fig,
        width="stretch",
        key="summary_quantity_trend_chart",
    )

    st.plotly_chart(
        top_n_chart(
            customer_summary,
            "거래처표시",
            "출고수량",
            "Top 거래처 · 출고수량 (개)",
            top_n=10,
        ),
        width="stretch",
        key="summary_top_customer_quantity_chart",
    )

    st.subheader("월별 요약")
    monthly_display = monthly_summary.copy()
    monthly_display = monthly_display.rename(
        columns={
            "출고수량": "출고수량 (개)",
        }
    )
    st.dataframe(
        style_table(
            monthly_display[["연월", "출고수량 (개)"]]
        ),
        width="stretch",
        hide_index=True,
    )

# ---------------------------------------------------------------------
# 대륙·국가 분석
# ---------------------------------------------------------------------
with tab_continent:

    assigned_rows = filtered[
        ~filtered["대륙"].eq("미지정") & ~filtered["국가"].eq("미지정")
    ]
    assigned_customer_count = assigned_rows["거래처"].nunique()
    total_customer_count = filtered["거래처"].nunique()
    assigned_row_share = len(assigned_rows) / len(filtered) if len(filtered) else 0
    st.caption(
        f"국가·대륙 지정 거래처 {assigned_customer_count:,}/{total_customer_count:,}개 · "
        f"분석 행 커버리지 {assigned_row_share:.1%}"
    )
    include_unassigned_region = st.checkbox(
        "대륙·국가 분석에 '미지정' 포함",
        value=False,
        help="체크하지 않으면 국가와 대륙이 모두 확인된 거래처만 포함됩니다.",
        key="include_unassigned_region_v10",
    )
    region_source = (
        filtered.copy() if include_unassigned_region else assigned_rows.copy()
    )
    if region_source.empty:
        st.warning(
            "국가·대륙이 지정된 거래처가 없어 '미지정' 데이터를 표시합니다. "
            "상단의 거래처별 국가·대륙 입력·수정에서 매핑을 완료하세요."
        )
        region_source = filtered.copy()

    continent_summary = (
        region_source.groupby("대륙", as_index=False)
        .agg(출고수량=("분석수량", "sum"))
        .sort_values(["출고수량", "대륙"], ascending=[False, True])
    )
    country_summary = (
        region_source.groupby(["대륙", "국가"], as_index=False)
        .agg(출고수량=("분석수량", "sum"))
        .sort_values(["출고수량", "국가"], ascending=[False, True])
    )
    country_summary["국가표시"] = country_summary["국가"]

    overview_left, overview_right = st.columns(2)
    with overview_left:
        st.plotly_chart(
            top_n_chart(
                continent_summary,
                "대륙",
                "출고수량",
                "대륙별 출고수량 (개)",
                top_n=max(1, len(continent_summary)),
            ),
            width="stretch",
            key="region_continent_quantity_chart_v10",
        )
    with overview_right:
        st.plotly_chart(
            top_n_chart(
                country_summary,
                "국가표시",
                "출고수량",
                "국가별 출고수량 (개)",
                top_n=min(30, max(1, len(country_summary))),
            ),
            width="stretch",
            key="region_country_quantity_chart_v10",
        )

    st.divider()
    selected_continent = st.selectbox(
        "상세 분석 대륙",
        options=continent_summary["대륙"].tolist(),
        key="region_continent_detail_select_v10",
    )
    continent_detail = region_source[
        region_source["대륙"].eq(selected_continent)
    ].copy()
    detail_customer = make_customer_summary(continent_detail)
    detail_sku = make_sku_summary(continent_detail)
    detail_group = make_product_group_summary(continent_detail, "제품군")

    chart_customer, chart_sku = st.columns(2)
    with chart_customer:
        st.plotly_chart(
            top_n_chart(
                detail_customer,
                "거래처표시",
                "출고수량",
                f"{selected_continent} · Top 거래처 출고수량 (개)",
                top_n=min(20, max(1, len(detail_customer))),
            ),
            width="stretch",
            key="region_continent_top_customer_chart_v10",
        )
    with chart_sku:
        st.plotly_chart(
            top_n_chart(
                detail_sku,
                "제품명_정리",
                "출고수량",
                f"{selected_continent} · Top 20 SKU 출고수량 (개)",
                top_n=min(20, max(1, len(detail_sku))),
                show_share=False,
            ),
            width="stretch",
            key="region_continent_top_sku_chart_v10",
        )

    pie_source = detail_group.loc[
        detail_group["출고수량"] > 0,
        ["제품군", "출고수량"],
    ].copy()
    product_group_count = len(pie_source)
    st.markdown(f"#### {selected_continent} · 제품군별 출고수량 구성")
    st.caption(
        f"양수 출고 제품군 {product_group_count:,}개 · "
        "도넛은 상위 8개와 9위 이하 기타로 단순화하고, "
        "전체 Top 20은 아래 표에서 확인할 수 있습니다."
    )
    if pie_source.empty:
        st.info("선택한 조건에는 원형 그래프로 표시할 양수 출고 제품군이 없습니다.")
    else:
        total_group_qty = pie_source["출고수량"].sum()
        top20_source = pie_source.head(20).copy()
        top20_source.insert(0, "순위", range(1, len(top20_source) + 1))
        top20_source["비중"] = top20_source["출고수량"] / total_group_qty

        donut_source = pie_source.head(8).copy()
        donut_source["포함제품군수"] = 1
        donut_source["색상"] = PRODUCT_GROUP_COLORS[: len(donut_source)]
        if len(pie_source) > 8:
            other_qty = pie_source.iloc[8:]["출고수량"].sum()
            donut_source = pd.concat(
                [
                    donut_source,
                    pd.DataFrame(
                        {
                            "제품군": ["기타 제품군"],
                            "출고수량": [other_qty],
                            "포함제품군수": [len(pie_source) - 8],
                            "색상": ["#CBD5E1"],
                        }
                    ),
                ],
                ignore_index=True,
            )
        donut_source["비중"] = donut_source["출고수량"] / total_group_qty
        donut_source["표시제품군"] = donut_source["제품군"]
        other_mask = donut_source["제품군"].eq("기타 제품군")
        donut_source.loc[other_mask, "표시제품군"] = donut_source.loc[
            other_mask, "포함제품군수"
        ].map(lambda count: f"기타 제품군 (9위 이하 {int(count)}개)")

        legend_rows = []
        for rank, row in donut_source.reset_index(drop=True).iterrows():
            legend_rows.append(
                '<div class="product-group-row">'
                f'<span class="product-group-swatch" '
                f'style="background:{row["색상"]}"></span>'
                f'<span class="product-group-name">{rank + 1}. '
                f'{html.escape(str(row["표시제품군"]))}</span>'
                f'<span class="product-group-value">{row["출고수량"]:,.0f}개'
                f'<span class="product-group-share">{row["비중"]:.1%}</span></span>'
                "</div>"
            )
        legend_html = (
            '<div class="product-group-list">'
            '<div class="product-group-list-title">제품군 · 출고수량 · 비중</div>'
            + "".join(legend_rows)
            + "</div>"
        )

        legend_col, donut_col = st.columns(
            [0.94, 1.06],
            gap="small",
            vertical_alignment="center",
        )
        with legend_col:
            st.markdown(legend_html, unsafe_allow_html=True)
        with donut_col:
            group_pie = px.pie(
                donut_source,
                names="표시제품군",
                values="출고수량",
                custom_data=["제품군", "포함제품군수"],
                hole=0.56,
            )
            group_pie.update_traces(
                textposition="inside",
                textinfo="percent",
                textfont=dict(color="#0F172A", size=13),
                insidetextorientation="horizontal",
                sort=False,
                direction="clockwise",
                domain=dict(x=[0.0, 1.0], y=[0.0, 1.0]),
                marker=dict(
                    colors=donut_source["색상"].tolist(),
                    line=dict(color="#FFFFFF", width=3),
                ),
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "출고수량: %{value:,.0f}개<br>비중: %{percent}<extra></extra>"
                ),
            )
            group_pie.update_layout(
                height=500,
                margin=dict(l=6, r=6, t=18, b=18),
                showlegend=False,
                uniformtext_minsize=11,
                uniformtext_mode="hide",
                annotations=[
                    dict(
                        text=(
                            "총 출고수량<br>"
                            f"<b>{total_group_qty:,.0f}개</b>"
                        ),
                        x=0.5,
                        y=0.5,
                        xref="paper",
                        yref="paper",
                        xanchor="center",
                        yanchor="middle",
                        showarrow=False,
                        align="center",
                        font=dict(color="#0F172A", size=16),
                    )
                ],
            )
            st.plotly_chart(
                group_pie,
                width="stretch",
                key="region_continent_product_group_pie_v13",
            )

        with st.expander("전체 제품군 Top 20 보기", expanded=False):
            st.dataframe(
                top20_source.style.format(
                    {
                        "출고수량": "{:,.0f}",
                        "비중": "{:.1%}",
                    }
                ),
                hide_index=True,
                width="stretch",
                height=min(738, 38 + len(top20_source) * 35),
                column_config={
                    "순위": st.column_config.NumberColumn("순위", width="small"),
                    "제품군": st.column_config.TextColumn("제품군", width="large"),
                    "출고수량": st.column_config.NumberColumn(
                        "출고수량 (개)",
                        width="medium",
                    ),
                    "비중": st.column_config.NumberColumn("비중", width="small"),
                },
            )

    region_download = (
        country_summary[["대륙", "국가", "출고수량"]]
        .rename(columns={"출고수량": "출고수량 (개)"})
        .to_csv(index=False, encoding="utf-8-sig")
    )
    st.download_button(
        "대륙·국가 수량 요약 CSV 다운로드",
        data=region_download,
        file_name="SELLIN_대륙_국가_수량_요약.csv",
        mime="text/csv",
    )

# ---------------------------------------------------------------------
# 거래처 분석
# ---------------------------------------------------------------------
with tab_customer:
    st.subheader("거래처 실적 순위")

    top_customer_count = st.slider(
        "표시할 거래처 수",
        min_value=5,
        max_value=max(6, min(50, max(5, len(customer_summary)))),
        value=min(20, max(5, len(customer_summary))),
        key="top_customer_count",
    )

    customer_display = customer_summary.head(top_customer_count).copy()
    customer_display.insert(0, "순위", range(1, len(customer_display) + 1))
    customer_main_display = customer_display.copy()
    customer_main_display = customer_main_display.rename(
        columns={
            "거래처표시": "국가 | 거래처명",
            "출고수량": "출고수량 (개)",
        }
    )
    st.dataframe(
        style_table(
            customer_main_display[
                [
                    "순위",
                    "국가 | 거래처명",
                    "출고수량 (개)",
                    "수량비중",
                ]
            ],
            percent_cols=["수량비중"],
        ),
        width="stretch",
        hide_index=True,
        height=min(735, 45 + top_customer_count * 32),
    )

    customer_chart_summary = group_other_continent_customers_for_chart(
        customer_summary
    )
    st.caption(
        "대륙이 '기타'인 거래처는 개별 거래처명을 표시하지 않고 "
        "출고수량을 합산한 하나의 '기타' 막대로 표시합니다."
    )
    st.plotly_chart(
        top_n_chart(
            customer_chart_summary,
            "거래처표시",
            "출고수량",
            f"Top {top_customer_count} 거래처 · 출고수량 (개)",
            top_n=top_customer_count,
        ),
        width="stretch",
        key="customer_ranking_quantity_chart",
    )

    with st.expander("거래처 순위 상세 지표", expanded=False):
        customer_detail_display = customer_display.copy()
        customer_detail_display = customer_detail_display.rename(
            columns={
                "거래처표시": "국가 | 거래처명",
                "출고수량": "출고수량 (개)",
            }
        )
        st.dataframe(
            style_table(
                customer_detail_display[
                    [
                        "순위",
                        "국가 | 거래처명",
                        "거래처코드",
                        "출고수량 (개)",
                        "수량비중",
                        "SKU수",
                        "출고건수",
                        "최근출고일",
                    ]
                ],
                percent_cols=["수량비중"],
            ),
            width="stretch",
            hide_index=True,
            height=560,
        )

    st.subheader("거래처 상세")
    selected_customer = st.selectbox(
        "상세 분석 거래처",
        options=customer_summary["거래처"].tolist(),
        format_func=lambda key: customer_label_map.get(key, key),
    )
    selected_customer_label = customer_label_map.get(selected_customer, selected_customer)
    customer_df = filtered[filtered["거래처"].eq(selected_customer)].copy()

    selected_customer_summary = customer_summary[
        customer_summary["거래처"].eq(selected_customer)
    ].iloc[0]

    a, b, c, d = st.columns(4)
    a.metric("출고수량 (개)", format_number(selected_customer_summary["출고수량"]))
    b.metric("거래 SKU", format_number(selected_customer_summary["SKU수"]))
    c.metric("전체 수량 비중", format_pct(selected_customer_summary["수량비중"]))
    d.metric("최근 출고일", str(selected_customer_summary["최근출고일"].date()))

    customer_monthly = make_monthly_summary(customer_df)
    customer_sku = make_sku_summary(customer_df)

    left, right = st.columns(2)
    with left:
        fig = px.bar(
            customer_monthly,
            x="연월",
            y="출고수량",
            title=f"{selected_customer_label} · 월별 출고수량 (개)",
            text="출고수량",
        )
        fig.update_traces(
            texttemplate="%{text:,.0f}",
            textposition="outside",
            cliponaxis=False,
        )
        fig.update_layout(
            height=420,
            xaxis_title="",
            yaxis_title="출고수량 (개)",
            margin=dict(l=20, r=20, t=55, b=20),
        )
        st.plotly_chart(
            fig,
            width="stretch",
            key="customer_detail_monthly_chart",
        )

    with right:
        st.plotly_chart(
            top_n_chart(
                customer_sku,
                "제품명_정리",
                "출고수량",
                f"{selected_customer_label} · Top 20 SKU 출고수량 (개)",
                top_n=min(20, max(1, len(customer_sku))),
                show_share=False,
            ),
            width="stretch",
            key="customer_detail_top20_sku_chart",
        )

    customer_sku_excel = build_customer_sku_excel(
        customer_sku,
        selected_customer_label,
        str(start_date),
        str(end_date),
    )
    customer_filename = safe_download_filename_part(
        selected_customer_summary["거래처명"]
    )
    customer_download_key = hashlib.sha256(
        str(selected_customer).encode("utf-8")
    ).hexdigest()[:12]
    st.download_button(
        "선택 거래처 SKU 분석 엑셀 다운로드",
        data=customer_sku_excel,
        file_name=f"SELLIN_{customer_filename}_SKU_분석.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        key=f"customer_sku_excel_{customer_download_key}",
    )
    st.caption(
        "선택한 거래처의 SKU 순위·코드·제품명·제품군·판매형태·출고수량·"
        "수량 비중을 현재 화면 필터 기준으로 저장합니다."
    )

    st.subheader("거래처 × 월 히트맵")
    heatmap_top_n = st.slider(
        "히트맵 거래처 수",
        min_value=5,
        max_value=max(6, min(30, max(5, customer_summary.shape[0]))),
        value=min(15, max(5, customer_summary.shape[0])),
        key="heatmap_top_n",
    )
    top_customer_keys = customer_summary.head(heatmap_top_n)["거래처"].tolist()
    heatmap_source = filtered[filtered["거래처"].isin(top_customer_keys)].copy()
    heatmap_source["거래처표시"] = (
        heatmap_source["국가"].astype("string").fillna("미지정")
        + " | "
        + heatmap_source["거래처명"].astype("string").fillna("미기재")
    )
    heatmap_df = (
        heatmap_source.pivot_table(
            index="거래처표시",
            columns="연월",
            values="분석수량",
            aggfunc="sum",
            fill_value=0,
        )
        .sort_index()
    )
    if not heatmap_df.empty:
        fig = px.imshow(
            heatmap_df,
            aspect="auto",
            text_auto=".3s",
            title=f"Top {heatmap_top_n} 거래처 월별 출고수량 (개)",
            labels=dict(x="연월", y="거래처", color="출고수량 (개)"),
        )
        fig.update_layout(height=max(450, heatmap_top_n * 28))
        st.plotly_chart(
            fig,
            width="stretch",
            key="customer_monthly_heatmap_chart",
        )

    customer_csv = customer_summary[
        [
            "국가",
            "대륙",
            "거래처명",
            "거래처코드",
            "출고수량",
            "수량비중",
            "SKU수",
            "출고건수",
            "최근출고일",
        ]
    ].to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "거래처 요약 CSV 다운로드",
        data=customer_csv,
        file_name="SELLIN_거래처_요약.csv",
        mime="text/csv",
    )

# ---------------------------------------------------------------------
# SKU 분석
# ---------------------------------------------------------------------
with tab_sku:
    st.subheader("전체 제품군 분석")
    group_left, group_right = st.columns(2)
    with group_left:
        st.plotly_chart(
            top_n_chart(
                category_summary,
                "대분류",
                "출고수량",
                "대분류별 출고수량 (개)",
                top_n=max(1, len(category_summary)),
            ),
            width="stretch",
            key="global_category_ranking_chart",
        )
    with group_right:
        st.plotly_chart(
            top_n_chart(
                product_group_summary,
                "제품군",
                "출고수량",
                "Top 20 제품군 · 출고수량 (개)",
                top_n=min(20, max(1, len(product_group_summary))),
            ),
            width="stretch",
            key="global_product_group_ranking_chart",
        )

    product_group_display = product_group_summary.copy()
    product_group_display.insert(
        0,
        "순위",
        range(1, len(product_group_display) + 1),
    )
    product_group_display = product_group_display.rename(
        columns={
            "출고수량": "출고수량 (개)",
        }
    )
    with st.expander("제품군 전체 순위 표", expanded=False):
        st.dataframe(
            style_table(
                product_group_display[
                    [
                        "순위",
                        "제품군",
                        "출고수량 (개)",
                        "수량비중",
                        "SKU수",
                        "거래처수",
                    ]
                ],
                percent_cols=["수량비중"],
            ),
            width="stretch",
            hide_index=True,
            height=650,
        )

    st.subheader("전체 Top SKU · 출고수량 기준")
    st.caption(
        f"총 {len(sku_summary):,}개 SKU를 수량 순위대로 모두 표시합니다. "
        "표 안에서 아래로 스크롤해 마지막 순위까지 확인할 수 있습니다."
    )

    sku_display = sku_summary.copy()
    sku_display.insert(0, "순위", range(1, len(sku_display) + 1))
    sku_display = sku_display.rename(
        columns={
            "제품명_정리": "제품명",
            "출고수량": "출고수량 (개)",
        }
    )

    st.dataframe(
        style_table(
            sku_display[
                [
                    "순위",
                    "SKU",
                    "제품명",
                    "대분류",
                    "제품군",
                    "판매형태",
                    "출고수량 (개)",
                ]
            ]
        ),
        width="stretch",
        hide_index=True,
        height=780,
    )

    st.plotly_chart(
        top_n_chart(
            sku_summary,
            "제품명_정리",
            "출고수량",
            "전체 Top 20 SKU · 출고수량 (개)",
            top_n=min(20, max(1, len(sku_summary))),
            show_share=False,
        ),
        width="stretch",
        key="sku_analysis_top20_chart",
    )

    st.subheader("거래처별 Top SKU")
    rank_top_n = st.slider(
        "거래처별 Top N",
        min_value=1,
        max_value=20,
        value=5,
        key="customer_sku_rank_top_n",
    )

    customer_sku_rank = make_customer_sku_rank(filtered, rank_top_n)

    customer_for_rank = st.multiselect(
        "표시할 거래처",
        options=customer_summary["거래처"].tolist(),
        default=customer_summary.head(min(5, len(customer_summary)))["거래처"].tolist(),
        format_func=lambda key: customer_label_map.get(key, key),
        help="기본값은 전체 출고수량 상위 거래처입니다.",
    )
    if customer_for_rank:
        customer_sku_rank = customer_sku_rank[
            customer_sku_rank["거래처"].isin(customer_for_rank)
        ]

    customer_sku_display = customer_sku_rank.copy()
    customer_sku_display = customer_sku_display.rename(
        columns={
            "거래처표시": "국가 | 거래처명",
            "제품명_정리": "제품명",
            "출고수량": "출고수량 (개)",
        }
    )
    st.dataframe(
        style_table(
            customer_sku_display[
                [
                    "국가 | 거래처명",
                    "거래처코드",
                    "거래처내순위",
                    "SKU",
                    "제품명",
                    "출고수량 (개)",
                ]
            ]
        ),
        width="stretch",
        hide_index=True,
        height=650,
    )

    st.subheader("SKU 파레토 분석")
    pareto = sku_summary.sort_values("출고수량", ascending=False).copy()
    pareto["누적출고수량"] = pareto["출고수량"].cumsum()
    total_metric = pareto["출고수량"].sum()
    pareto["누적비중"] = (
        pareto["누적출고수량"] / total_metric if total_metric != 0 else 0
    )
    pareto["ABC등급"] = np.select(
        [
            pareto["누적비중"] <= 0.80,
            pareto["누적비중"] <= 0.95,
        ],
        ["A", "B"],
        default="C",
    )
    abc_summary = (
        pareto.groupby("ABC등급", as_index=False)
        .agg(
            SKU수=("SKU", "nunique"),
            출고수량=("출고수량", "sum"),
        )
        .sort_values("ABC등급")
    )
    abc_display = abc_summary.copy()
    abc_display = abc_display.rename(
        columns={
            "출고수량": "출고수량 (개)",
        }
    )
    st.dataframe(
        style_table(abc_display),
        width="stretch",
        hide_index=True,
    )

    sku_csv = sku_summary[
        [
            "SKU",
            "제품명_정리",
            "대분류",
            "제품군",
            "판매형태",
            "에디션",
            "출고수량",
            "수량비중",
            "거래처수",
            "출고건수",
            "최근출고일",
        ]
    ].to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "SKU 요약 CSV 다운로드",
        data=sku_csv,
        file_name="SELLIN_SKU_요약.csv",
        mime="text/csv",
    )

# ---------------------------------------------------------------------
# 조직/지역/창고
# ---------------------------------------------------------------------
with tab_org:
    org_dimension = st.selectbox(
        "분석 기준",
        [
            "대륙",
            "국가",
            "대분류",
            "제품군",
            "판매형태",
            "에디션",
            "판매지역",
            "영업그룹",
            "영업담당자명",
            "창고",
            "제품버전",
        ],
    )
    org_summary = (
        filtered.groupby(org_dimension, as_index=False)
        .agg(
            출고수량=("분석수량", "sum"),
            거래처수=("거래처", "nunique"),
            SKU수=("SKU", "nunique"),
            출고건수=("출고번호", "nunique"),
        )
        .sort_values("출고수량", ascending=False)
    )

    total_selected_metric = org_summary["출고수량"].sum()
    org_summary["비중"] = np.where(
        total_selected_metric != 0,
        org_summary["출고수량"] / total_selected_metric,
        0,
    )

    left, right = st.columns([1.2, 1])
    with left:
        org_chart_df = org_summary.head(20).copy()
        fig = px.bar(
            org_chart_df,
            x="출고수량",
            y=org_dimension,
            orientation="h",
            text_auto=".3s",
            title=f"{org_dimension}별 출고수량 (개)",
        )
        fig.update_layout(
            height=550,
            yaxis_title="",
            xaxis_title="출고수량 (개)",
            margin=dict(l=20, r=20, t=55, b=20),
        )
        fig.update_yaxes(
            categoryorder="array",
            categoryarray=org_chart_df[org_dimension].tolist(),
            autorange="reversed",
        )
        st.plotly_chart(
            fig,
            width="stretch",
            key="organization_quantity_chart",
        )

    with right:
        fig = px.pie(
            org_summary.head(10),
            names=org_dimension,
            values="출고수량",
            hole=0.45,
            title=f"상위 10개 {org_dimension} 출고수량 비중",
        )
        fig.update_layout(height=550)
        st.plotly_chart(
            fig,
            width="stretch",
            key="organization_share_chart",
        )

    org_display = org_summary.copy()
    org_display = org_display.rename(
        columns={
            "출고수량": "출고수량 (개)",
        }
    )
    st.dataframe(
        style_table(org_display, percent_cols=["비중"]),
        width="stretch",
        hide_index=True,
    )

    st.subheader("담당자 × 거래처")
    owner_customer = (
        filtered.groupby(
            ["영업담당자명", "대륙", "국가", "거래처명"],
            as_index=False,
        )
        .agg(
            출고수량=("분석수량", "sum"),
            SKU수=("SKU", "nunique"),
        )
        .sort_values("출고수량", ascending=False)
    )
    owner_customer["국가 | 거래처명"] = (
        owner_customer["국가"].astype("string").fillna("미지정")
        + " | "
        + owner_customer["거래처명"].astype("string").fillna("미기재")
    )
    owner_customer = owner_customer.rename(
        columns={
            "출고수량": "출고수량 (개)",
        }
    )
    st.dataframe(
        style_table(
            owner_customer.head(100)[
                [
                    "영업담당자명",
                    "국가 | 거래처명",
                    "출고수량 (개)",
                    "SKU수",
                ]
            ]
        ),
        width="stretch",
        hide_index=True,
        height=520,
    )

# ---------------------------------------------------------------------
# 데이터 품질
# ---------------------------------------------------------------------
with tab_quality:
    st.subheader("데이터 품질 점검")

    duplicate_mask, duplicate_key_cols = find_potential_duplicates(
        df,
        bool(quality.get("shipment_number_present", False)),
    )
    duplicate_count = int(duplicate_mask.sum())

    negative_qty_count = int((df["분석수량"] < 0).sum())
    zero_qty_count = int((df["분석수량"] == 0).sum())
    unassigned_country_rows = int(df["국가"].eq("미지정").sum())
    unassigned_continent_rows = int(df["대륙"].eq("미지정").sum())
    numeric_failure_count = int(quality.get("numeric_failure_count", 0))

    sku_name_issue_df = (
        df[df["SKU"].ne("")]
        .groupby("SKU", as_index=False)
        .agg(
            제품명수=("제품명_정리", "nunique"),
            제품명목록=(
                "제품명_정리",
                lambda values: " | ".join(sort_unique(values)),
            ),
        )
    )
    sku_name_issue_df = sku_name_issue_df[
        sku_name_issue_df["제품명수"] > 1
    ].sort_values(["제품명수", "SKU"], ascending=[False, True])
    inconsistent_sku_count = len(sku_name_issue_df)

    q1, q2, q3, q4 = st.columns(4)
    q1.metric("원본 행", format_number(quality["raw_rows"]))
    q2.metric("정리 후 행", format_number(quality["prepared_rows"]))
    q3.metric("출고일 오류/누락", format_number(quality["invalid_date_count"]))
    q4.metric("숫자 변환 실패", format_number(numeric_failure_count))

    q5, q6, q7, q8, q9 = st.columns(5)
    q5.metric("SKU 누락", format_number(quality["invalid_sku_count"]))
    q6.metric("거래처 누락", format_number(quality["invalid_customer_count"]))
    q7.metric("국가 미지정 행", format_number(unassigned_country_rows))
    q8.metric("대륙 미지정 행", format_number(unassigned_continent_rows))
    q9.metric("잠재 중복 행", format_number(duplicate_count))

    st.subheader("제품군 매핑 품질")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("원본 고유 SKU", format_number(product_mapping_quality["total_skus"]))
    m2.metric("제품군 매핑 완료", format_number(product_mapping_quality["matched_skus"]))
    m3.metric(
        "미분류 신규 SKU",
        format_number(product_mapping_quality["unmatched_sku_count"]),
    )
    m4.metric(
        "수동 검토 필요 SKU",
        format_number(product_mapping_quality["review_sku_count"]),
    )
    st.download_button(
        "현재 제품군 매핑표 다운로드",
        data=product_mapping_bytes,
        file_name=product_mapping_name,
        mime=(
            "text/csv"
            if Path(product_mapping_name).suffix.lower() == ".csv"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        key="download_current_product_mapping",
    )

    if product_mapping_quality["unmatched_sku_count"]:
        unmatched_product_csv = product_mapping_quality["unmatched_skus"].to_csv(
            index=False,
            encoding="utf-8-sig",
        )
        st.dataframe(
            product_mapping_quality["unmatched_skus"],
            width="stretch",
            hide_index=True,
        )
        st.download_button(
            "미분류 신규 SKU CSV 다운로드",
            data=unmatched_product_csv,
            file_name="SELLIN_미분류_신규_SKU.csv",
            mime="text/csv",
            key="download_unmatched_product_skus",
        )

    review_mapping = product_mapping[
        product_mapping["검토상태"].eq("검토필요")
    ][
        [
            "품목코드",
            "품목명",
            "대분류",
            "제품군",
            "판매형태",
            "기본분석포함",
            "검토사유",
        ]
    ]
    if not review_mapping.empty:
        with st.expander("수동 검토 필요 제품군 매핑", expanded=False):
            st.dataframe(
                review_mapping,
                width="stretch",
                hide_index=True,
            )

    st.subheader("정상 출고와 반품")
    positive_qty = df.loc[df["분석수량"] > 0, "분석수량"].sum()
    return_qty = -df.loc[df["분석수량"] < 0, "분석수량"].sum()
    net_qty = df["분석수량"].sum()
    r1, r2, r3 = st.columns(3)
    r1.metric("정상 출고수량 (개)", format_number(positive_qty))
    r2.metric("반품수량 (개)", format_number(return_qty))
    r3.metric("순출고수량 (개)", format_number(net_qty))

    issue_table = pd.DataFrame(
        [
            ["출고일 오류/누락", quality["invalid_date_count"], "출고일 파싱 및 원본 셀 확인"],
            [
                "숫자 변환 실패",
                numeric_failure_count,
                "아래 상세 목록에서 원본 값 확인",
            ],
            ["SKU 누락", quality["invalid_sku_count"], "품목 코드 누락 여부 확인"],
            [
                "동일 SKU 제품명 불일치",
                inconsistent_sku_count,
                "순위는 SKU로 통합되며 제품명 이력만 확인",
            ],
            ["거래처 누락", quality["invalid_customer_count"], "판매처/납품처 코드·명 확인"],
            ["국가 미지정", unassigned_country_rows, "거래처별 국가·대륙 매핑 입력"],
            ["대륙 미지정", unassigned_continent_rows, "거래처별 국가·대륙 매핑 입력"],
            [
                "제품군 미분류 SKU",
                product_mapping_quality["unmatched_sku_count"],
                "미분류 CSV 확인 후 제품군 매핑표에 품목코드 추가",
            ],
            ["음수 출고수량", negative_qty_count, "반품·취소 데이터인지 확인"],
            ["0 수량", zero_qty_count, "불필요 행인지 확인"],
            [
                "잠재 중복",
                duplicate_count,
                "중복 기준: " + "·".join(duplicate_key_cols),
            ],
        ],
        columns=["점검항목", "행 수", "확인사항"],
    )
    st.dataframe(issue_table, width="stretch", hide_index=True)

    numeric_issues = quality.get("numeric_issues")
    if isinstance(numeric_issues, pd.DataFrame) and not numeric_issues.empty:
        st.subheader("숫자 변환 실패 상세")
        st.dataframe(
            numeric_issues,
            width="stretch",
            hide_index=True,
        )
        st.download_button(
            "숫자 변환 실패 CSV 다운로드",
            data=numeric_issues.to_csv(index=False, encoding="utf-8-sig"),
            file_name="SELLIN_숫자변환실패.csv",
            mime="text/csv",
        )

    if not sku_name_issue_df.empty:
        st.subheader("동일 SKU 제품명 불일치")
        st.dataframe(
            sku_name_issue_df,
            width="stretch",
            hide_index=True,
        )

    missing_columns = [
        "출고일",
        "출고번호",
        "납품처",
        "납품처명",
        "판매처",
        "판매처명",
        "품목",
        "품목명",
        "출고수량",
        "저장위치",
        "판매지역",
        "영업그룹",
        "영업담당자명",
    ]
    missing_summary = []
    for col in missing_columns:
        if col in df.columns:
            if df[col].dtype == "object" or pd.api.types.is_string_dtype(df[col]):
                missing_mask = (
                    df[col].isna()
                    | df[col].astype("string").fillna("").str.strip().eq("")
                )
                count = int(missing_mask.sum())
            else:
                count = int(df[col].isna().sum())
            missing_summary.append(
                {
                    "컬럼": col,
                    "누락 건수": count,
                    "누락률": count / len(df) if len(df) else 0,
                }
            )
    missing_df = pd.DataFrame(missing_summary).sort_values(
        ["누락률", "누락 건수"],
        ascending=False,
    )
    st.subheader("주요 컬럼 누락 현황")
    st.dataframe(
        style_table(missing_df, percent_cols=["누락률"]),
        width="stretch",
        hide_index=True,
    )

    st.subheader("현재 필터 적용 데이터")
    preview_cols = [
        col
        for col in [
            "출고일",
            "출고번호",
            "거래처코드",
            "거래처명",
            "국가",
            "대륙",
            "SKU",
            "제품명_정리",
            "분석수량",
            "창고",
            "판매지역",
            "영업그룹",
            "영업담당자명",
        ]
        if col in filtered.columns
    ]
    st.dataframe(
        filtered[preview_cols].sort_values("출고일", ascending=False),
        width="stretch",
        hide_index=True,
        height=600,
    )

    quantity_export = filtered.drop(
        columns=[
            col
            for col in [
                "판매단가",
                "출고금액",
                "조정출고금액",
                "분석금액",
                "단가_계산",
            ]
            if col in filtered.columns
        ]
    )
    filtered_csv = quantity_export.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "현재 필터 데이터 CSV 다운로드",
        data=filtered_csv,
        file_name="SELLIN_필터데이터.csv",
        mime="text/csv",
    )

st.caption(
    f"전체 요약 출고금액 기준: {amount_policy}. "
    "국가·대륙은 거래처, 거래처코드, 거래처명 순으로 연결됩니다."
)
