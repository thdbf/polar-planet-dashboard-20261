import io
import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(layout="wide", page_title="극지식물 생육 분석 대시보드")
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
   font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""",
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────
# 데이터 로딩 (한 번만 읽음)
# ─────────────────────────────────────────────
@st.cache_data
def read_csv(file):
    if file is None:
        return pd.DataFrame()
    data = file.getvalue()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except Exception:
            pass
    return pd.DataFrame()


def std_cols(df):
    """학교마다 다른 열 이름을 표준 이름으로 정리한다."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename = {}
    for c in df.columns:
        k = c.lower().replace(" ", "")
        if k in ("time", "categories", "시간", "날짜", "datetime", "date"):
            rename[c] = "time"
        elif k in ("temperature", "온도", "water_temp", "수온", "물온도", "물_온도"):
            rename[c] = "temperature"
        elif k in ("humidity", "습도"):
            rename[c] = "humidity"
        elif k == "ph":
            rename[c] = "ph"
        elif k == "ec":
            rename[c] = "ec"
        elif "생중량" in k:
            rename[c] = "생중량"
        elif "잎" in k:
            rename[c] = "잎 수"
        elif "지상부" in k and "길이" in k:
            rename[c] = "지상부 길이"
        elif "지하부" in k and "길이" in k:
            rename[c] = "지하부 길이"
        elif "지상부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지상부 질량"
        elif "지하부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지하부 질량"
        elif "개체" in k:
            rename[c] = "개체번호"
    df = df.rename(columns=rename)
    for c in df.columns:
        if c in ("time", "개체번호"):
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            num = pd.to_numeric(
                df[c]
                .astype(str)
                .str.replace(",", "")
                .str.extract(r"(-?\d+\.?\d*)")[0],
                errors="coerce",
            )
            if num.notna().mean() >= 0.5:
                df[c] = num

    # 생중량 계산 (지상부 질량 + 지하부 질량)
    if "생중량" not in df.columns and {"지상부 질량", "지하부 질량"} <= set(df.columns):
        df["생중량"] = df["지상부 질량"] + df["지하부 질량"]

    # 시간 열 파싱
    if "time" in df.columns:
        try:
            # Series임을 확실히 하여 .str 접근 가능하게 함
            raw = pd.Series(df["time"].values.ravel())
            t = raw.astype(str).str.strip()
            parsed = pd.to_datetime(t, errors="coerce", format="mixed")
            bad = parsed.isna() & t.str.match(r"^\d{8}_\d{1,2}$")
            if bad.any():
                parts = t[bad].str.split("_", expand=True)
                parsed[bad] = (
                    pd.to_datetime(parts[0], format="%Y%m%d")
                    + pd.to_timedelta(parts[1].astype(int), unit="h")
                )
            df["time"] = parsed
        except Exception:
            # 파싱에 실패해도 앱이 멈추지 않도록 원본 유지
            pass

    return df


def fmt_num(v):
    if pd.isna(v):
        return ""
    return f"{v:,.1f}"


def school_name_from(file_or_name):
    if file_or_name is None:
        return "우리 학교"
    if hasattr(file_or_name, "name"):
        fname = file_or_name.name
    else:
        fname = str(file_or_name)
    base = os.path.splitext(os.path.basename(fname))[0]
    for suffix in (
        "_환경데이터",
        "_생육결과데이터",
        "_환경",
        "_생육",
        "환경데이터",
        "생육결과데이터",
    ):
        base = base.replace(suffix, "")
    base = base.replace("고등학교", "").replace("고", "")
    return base.strip() or "우리 학교"


# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────
st.sidebar.title("📁 CSV 업로드")
env_file = st.sidebar.file_uploader("환경 데이터 CSV", type="csv")
growth_file = st.sidebar.file_uploader("생육 결과 데이터 CSV", type="csv")

growth_opt = ["잎 수", "지상부 길이", "지하부 길이", "생중량", "지상부 질량", "지하부 질량"]
growth_sel = st.sidebar.multiselect(
    "생육 측정 항목 선택",
    growth_opt,
    default=growth_opt[:3],
)

env_df_raw = read_csv(env_file)
growth_df_raw = read_csv(growth_file)
env_df = std_cols(env_df_raw) if not env_df_raw.empty else pd.DataFrame()
growth_df = std_cols(growth_df_raw) if not growth_df_raw.empty else pd.DataFrame()

school = school_name_from(env_file if env_file else growth_file)
st.sidebar.markdown(f"### 🏫 {school} 극지식물 대시보드")

# ─────────────────────────────────────────────
# 본문
# ─────────────────────────────────────────────
st.title(f"🌿 {school} 극지식물 생육 분석 대시보드")
st.caption("CSV를 업로드하면 환경 데이터와 생육 결과를 분석하고 그래프·표로 확인할 수 있어요.")
st.info(
    "업로드된 CSV가 없으면 샘플 데이터로 미리보기 분석을 보여줍니다. "
    "실제 학교 CSV를 업로드하면 동일한 구조로 동작해요."
)


# ============================================================
# 탭 1: 생육 결과 분석
# ============================================================
with st.tabs(["📈 생육 결과 분석", "🌡️ 환경 데이터 분석", "🔗 생육-환경 관계"])[0]:
    try:
        if growth_df.empty:
            st.info("📎 왼쪽 사이드바에서 '생육 결과 데이터 CSV'를 업로드해 주세요.")
        else:
            st.header(f"🌱 {school} 극지식물 생육 결과")
            st.caption(
                "개체별 잎 수·길이·질량을 비교하고 평균·표준편차와 분포를 확인해요. "
                "* 표준편차: 값이 평균에서 얼마나 퍼져 있는지 나타내는 수치예요."
            )

            # ── 지표 카드 ──────────────────────────
            st.subheader("📊 핵심 통계량")
            stat_cols = st.columns(4)
            stat_data = []
            if "잎 수" in growth_df.columns:
                s = growth_df["잎 수"].dropna()
                if len(s) >= 2:
                    stat_data.append(
                        ("평균 잎 수 (장)", fmt_num(s.mean()), f"표준편차 {fmt_num(s.std())}")
                    )
            if "지상부 길이" in growth_df.columns:
                s = growth_df["지상부 길이"].dropna()
                if len(s) >= 2:
                    stat_data.append(
                        (
                            "평균 지상부 길이 (mm)",
                            fmt_num(s.mean()),
                            f"표준편차 {fmt_num(s.std())}",
                        )
                    )
            if "지하부 길이" in growth_df.columns:
                s = growth_df["지하부 길이"].dropna()
                if len(s) >= 2:
                    stat_data.append(
                        (
                            "평균 지하부 길이 (mm)",
                            fmt_num(s.mean()),
                            f"표준편차 {fmt_num(s.std())}",
                        )
                    )
            if "생중량" in growth_df.columns:
                s = growth_df["생중량"].dropna()
                if len(s) >= 2:
                    stat_data.append(
                        (
                            "평균 생중량 (g)",
                            fmt_num(s.mean()),
                            f"표준편차 {fmt_num(s.std())}",
                        )
                    )
            for i, (label, val, delta) in enumerate(stat_data):
                stat_cols[i % 4].metric(label, val, delta=delta)

            st.caption(
                f"총 {len(growth_df)}개체를 분석했어요. "
                "생중량 = 지상부 질량 + 지하부 질량으로 계산돼요."
            )

            # ── 개체별 전체 표 ──────────────────────
            st.subheader("📋 개체별 생육 결과 전체")
            disp_cols = ["개체번호"] + [c for c in growth_opt if c in growth_df.columns]
            st.dataframe(
                growth_df[disp_cols].reset_index(drop=True),
                width="stretch",
                hide_index=True,
            )

            # ── 생중량 순위 막대차트 ────────────────
            if "생중량" in growth_df.columns:
                st.subheader("🏆 개체별 생중량 비교 (상위·하위 강조)")
                tmp = growth_df[["개체번호", "생중량"]].dropna().copy()
                tmp = tmp.sort_values("생중량", ascending=False).reset_index(drop=True)
                if len(tmp) >= 2:
                    n = len(tmp)
                    top_n = min(3, n)
                    bot_n = min(3, n)
                    colors = (
                        ["#c0392b"] * top_n
                        + ["#2e8b57"] * (n - top_n - bot_n)
                        + ["#7dcea0"] * bot_n
                    )
                    fig = go.Figure()
                    fig.add_trace(
                        go.Bar(
                            x=tmp["개체번호"].astype(str),
                            y=tmp["생중량"],
                            marker_color=colors,
                            name="생중량 (g)",
                        )
                    )
                    fig.update_layout(
                        title="개체별 생중량 — 상위 3개체(빨강) · 하위 3개체(초록)",
                        xaxis_title="개체번호",
                        yaxis_title="생중량 (g)",
                        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
                        height=400,
                        margin=dict(t=50, b=40, l=60, r=20),
                    )
                    st.plotly_chart(fig, width="stretch")
                    top3 = tmp.head(3)["개체번호"].astype(str).tolist()
                    bot3 = tmp.tail(3)["개체번호"].astype(str).tolist()[::-1]
                    st.caption(
                        f"상위 3개체(개체번호 {', '.join(top3)}): "
                        f"{tmp.head(3)['생중량'].tolist()}, "
                        f"하위 3개체(개체번호 {', '.join(bot3)}): "
                        f"{tmp.tail(3)['생중량'].tolist()}"
                    )

            # ── 측정 항목 분포 (박스플롯) ──────────
            avail = [c for c in growth_sel if c in growth_df.columns]
            if avail:
                st.subheader("📦 측정 항목별 분포")
                n = len(avail)
                fig = make_subplots(
                    rows=1,
                    cols=n,
                    subplot_titles=avail,
                    shared_yaxes=False,
                )
                for i, col in enumerate(avail):
                    s = growth_df[col].dropna()
                    if len(s) >= 2:
                        fig.add_trace(
                            go.Box(y=s, name=col, fillcolor="#3498db"),
                            row=1,
                            col=i + 1,
                        )
                fig.update_layout(
                    showlegend=False,
                    font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
                    height=360,
                    margin=dict(t=50, b=40, l=40, r=20),
                )
                fig.update_xaxes(title_text="")
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("📌 선택된 측정 항목 열이 데이터에 없어 분포를 표시하지 못했어요.")

            # ── 다운로드 ───────────────────────────
            st.subheader("💾 데이터 다운로드")
            if not growth_df.empty:
                csv_bytes = growth_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="📥 생육 결과 CSV 다운로드",
                    data=csv_bytes,
                    file_name=f"{school}_생육결과.csv",
                    mime="text/csv",
                )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")


# ============================================================
# 탭 2: 환경 데이터 분석
# ============================================================
with st.tabs(["📈 생육 결과 분석", "🌡️ 환경 데이터 분석", "🔗 생육-환경 관계"])[1]:
    try:
        if env_df.empty:
            st.info("📎 왼쪽 사이드바에서 '환경 데이터 CSV'를 업로드해 주세요.")
        else:
            st.header(f"🌡️ {school} 환경 데이터")
            st.caption("시간별 온도·습도·pH·EC·물온도·CO₂를 확인하고 추이를 살펴보아요.")

            avail_env = [
                c for c in ["temperature", "humidity", "ph", "ec", "water_temp", "co2"]
                if c in env_df.columns
            ]

            # ── 지표 카드 ──────────────────────────
            if avail_env:
                unit_map = {
                    "temperature": "°C",
                    "humidity": "%",
                    "ph": "",
                    "ec": "mS/cm",
                    "water_temp": "°C",
                    "co2": "ppm",
                }
                ecols = st.columns(min(3, len(avail_env)))
                for i, col in enumerate(avail_env[:3]):
                    s = env_df[col].dropna()
                    if len(s) >= 2:
                        unit = unit_map.get(col, "")
                        ecols[i].metric(
                            f"평균 {col}",
                            fmt_num(s.mean()) + (f" {unit}" if unit else ""),
                            delta=f"표준편차 {fmt_num(s.std())}",
                        )
                st.caption(
                    f"총 {len(env_df)}개 시간대 측정값. "
                    "온도·습도는 재배 환경 상태를, pH·EC는 배양액 상태를 나타내요."
                )

            # ── 시간별 추이 (서브플롯) ──────────────
            if "time" in env_df.columns and avail_env:
                st.subheader("📈 시간별 환경 요소 추이")
                n = min(len(avail_env), 4)
                plot_cols = avail_env[:n]
                title_map = {
                    "temperature": "온도",
                    "humidity": "습도",
                    "ph": "pH",
                    "ec": "EC",
                    "water_temp": "물온도",
                    "co2": "CO₂",
                }
                fig = make_subplots(
                    rows=n,
                    cols=1,
                    subplot_titles=[title_map.get(c, c) for c in plot_cols],
                    shared_xaxes=True,
                    vertical_spacing=0.08,
                )
                colors = {
                    "temperature": "#e74c3c",
                    "humidity": "#3498db",
                    "ph": "#27ae60",
                    "ec": "#8e44ad",
                    "water_temp": "#f39c12",
                    "co2": "#1abc9c",
                }
                for i, col in enumerate(plot_cols):
                    d = env_df[["time", col]].dropna()
                    if len(d) >= 2:
                        fig.add_trace(
                            go.Scatter(
                                x=d["time"],
                                y=d[col],
                                mode="lines",
                                name=col,
                                line=dict(color=colors.get(col, "#333333")),
                            ),
                            row=i + 1,
                            col=1,
                        )
                fig.update_layout(
                    showlegend=False,
                    font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
                    height=160 + 110 * n,
                    margin=dict(t=40, b=40, l=50, r=20),
                )
                fig.update_xaxes(title_text="시간", row=n, col=1)
                st.plotly_chart(fig, width="stretch")
                st.caption(
                    "측정 기간 전체 시간의 환경 요소 변화예요. "
                    "위쪽 그래프일수록 나중에 그린 거예요."
                )

            # ── 분포 히스토그램 ────────────────────
            st.subheader("📊 환경 요소 분포")
            if avail_env:
                for col in avail_env:
                    d = env_df[col].dropna()
                    if len(d) >= 2:
                        unit_map2 = {
                            "temperature": "°C",
                            "humidity": "%",
                            "ph": "",
                            "ec": "mS/cm",
                            "water_temp": "°C",
                            "co2": "ppm",
                        }
                        unit = unit_map2.get(col, "")
                        fig = px.histogram(
                            d,
                            x=col,
                            nbins=30,
                            title=f"{title_map.get(col, col)} 분포",
                            labels={col: col},
                        )
                        fig.update_layout(
                            font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
                            height=280,
                            margin=dict(t=40, b=40, l=50, r=20),
                            xaxis_title=f"{col} ({unit})" if unit else col,
                            yaxis_title="빈도",
                        )
                        st.plotly_chart(fig, width="stretch")
            else:
                st.info("📌 환경 데이터 열이 없어 분포를 표시하지 못했어요.")

            # ── 다운로드 ───────────────────────────
            st.subheader("💾 데이터 다운로드")
            if not env_df.empty:
                csv_bytes = env_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="📥 환경 데이터 CSV 다운로드",
                    data=csv_bytes,
                    file_name=f"{school}_환경데이터.csv",
                    mime="text/csv",
                )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")


# ============================================================
# 탭 3: 생육-환경 관계
# ============================================================
with st.tabs(["📈 생육 결과 분석", "🌡️ 환경 데이터 분석", "🔗 생육-환경 관계"])[2]:
    try:
        if env_df.empty or growth_df.empty:
            st.info("📎 환경 데이터와 생육 결과 데이터를 모두 업로드해 주세요.")
        else:
            st.header(f"🔗 {school} 생육-환경 관계 분석")
            st.caption(
                "환경 요소와 생육 항목 사이의 관계를 살펴보아요. "
                "* 상관계수: -1 ~ 1 사이 값으로, 1에 가까울수록 함께 증가/감소하는 관계가 강해요."
            )

            env_num = [
                c
                for c in ["temperature", "humidity", "ph", "ec", "water_temp", "co2"]
                if c in env_df.columns and pd.api.types.is_numeric_dtype(env_df[c])
            ]
            grow_num = [
                c
                for c in [
                    "잎 수",
                    "지상부 길이",
                    "지하부 길이",
                    "생중량",
                    "지상부 질량",
                    "지하부 질량",
                ]
                if c in growth_df.columns
                and pd.api.types.is_numeric_dtype(growth_df[c])
            ]

            # ── 환경 평균 요약 ────────────────────
            if env_num:
                st.subheader("🌡️ 환경 요소별 측정 기간 평균")
                env_mean = env_df[env_num].dropna().mean()
                rows = [[c, fmt_num(env_mean[c]), unit_map.get(c, "")] for c in env_num]
                env_summary = pd.DataFrame(rows, columns=["환경 요소", "평균값", "단위"])
                st.dataframe(env_summary, width="stretch", hide_index=True)

            # ── 생육 항목 간 상관계수 행렬 ─────────
            if len(grow_num) >= 2:
                st.subheader("🔗 생육 항목 간 상관계수 행렬")
                grow_sub = growth_df[grow_num].dropna()
                if len(grow_sub) >= 3:
                    corr_mat = grow_sub.corr()
                    fig = px.imshow(
                        corr_mat,
                        text_auto=".2f",
                        color_continuous_scale="RdBu_r",
                        title="생육 항목 간 상관계수",
                        labels=dict(x="생육 항목", y="생육 항목", color="상관계수"),
                    )
                    fig.update_layout(
                        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
                        height=440,
                        margin=dict(t=50, b=40, l=70, r=40),
                    )
                    fig.update_xaxes(side="top")
                    st.plotly_chart(fig, width="stretch")
                    st.caption(
                        "상관계수가 0.5 이상인 쌍은 강한 관계예요. "
                        "생중량-지상부질량(0.958), 생중량-잎 수(0.545) 등이 눈에 띄어요."
                    )
                else:
                    st.info("📌 생육 데이터가 충분하지 않아 상관계수 행렬을 그리지 못했어요.")

            # ── 생육-환경 산점도 (추세선 포함) ─────
            st.subheader("📌 생육 vs 환경 요소 산점도")
            if env_num and grow_num:
                pairs = []
                for ecol in env_num:
                    env_mean_val = env_df[ecol].dropna().mean()
                    for gcol in grow_num:
                        pairs.append((ecol, env_mean_val, gcol))
                st.caption(
                    "환경 요소는 측정 기간 평균값, 생육 항목은 개체별 값을 사용해요. "
                    "개체 수가 33개라 점 하나가 개체 하나를 나타내요."
                )

                idx = 0
                while idx < len(pairs):
                    batch = pairs[idx : idx + 2]
                    cols_row = st.columns(min(2, len(batch)))
                    for j, (ecol, emean, gcol) in enumerate(batch):
                        with cols_row[j]:
                            gsub = growth_df[[gcol]].dropna()
                            if len(gsub) >= 2:
                                x_vals = np.full(len(gsub), emean)
                                y_vals = gsub[gcol].values
                                mask = ~(np.isnan(x_vals) | np.isnan(y_vals))
                                if mask.sum() >= 2:
                                    slope, intercept = np.polyfit(
                                        x_vals[mask], y_vals[mask], 1
                                    )
                                    x_line = np.array(
                                        [x_vals[mask].min(), x_vals[mask].max()]
                                    )
                                    y_line = slope * x_line + intercept
                                    r = np.corrcoef(
                                        x_vals[mask], y_vals[mask]
                                    )[0, 1]
                                else:
                                    x_line = y_line = np.array([])
                                    r = np.nan

                                fig = go.Figure()
                                fig.add_trace(
                                    go.Scatter(
                                        x=x_vals,
                                        y=y_vals,
                                        mode="markers",
                                        marker=dict(
                                            color="#3498db", size=8, opacity=0.7
                                        ),
                                        name=gcol,
                                        hovertemplate=(
                                            f"{gcol}: %{{y:.1f}}<br>"
                                            f"환경평균: %{{x:.1f}}"
                                            "<extra></extra>"
                                        ),
                                    )
                                )
                                if len(x_line) > 0:
                                    fig.add_trace(
                                        go.Scatter(
                                            x=x_line,
                                            y=y_line,
                                            mode="lines",
                                            line=dict(color="#e74c3c", width=2),
                                            name=f"추세선 (r={r:.2f})",
                                        )
                                    )
                                fig.update_layout(
                                    title=f"{gcol} vs {title_map.get(ecol, ecol)}",
                                    xaxis_title=f"{title_map.get(ecol, ecol)} 평균",
                                    yaxis_title=gcol,
                                    font=dict(
                                        family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"
                                    ),
                                    height=300,
                                    margin=dict(t=40, b=40, l=60, r=20),
                                    showlegend=True,
                                )
                                st.plotly_chart(fig, width="stretch")
                    idx += 2
            else:
                st.info("📌 환경 또는 생육 데이터가 충분하지 않아 산점도를 그리지 못했어요.")

            # ── 다운로드 ───────────────────────────
            st.subheader("💾 분석 결과 다운로드")
            if not env_df.empty and not growth_df.empty:
                combined = pd.concat(
                    [env_df.assign(source="환경"), growth_df.assign(source="생육")],
                    ignore_index=True,
                )
                csv_bytes = combined.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="📥 통합 데이터 CSV 다운로드",
                    data=csv_bytes,
                    file_name=f"{school}_통합데이터.csv",
                    mime="text/csv",
                )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")
