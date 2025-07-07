import streamlit as st
import pandas as pd
from datetime import date
from core.db_queries import get_annual_summary_data
from st_aggrid import AgGrid, GridOptionsBuilder
from core.ui_utils import apply_common_styles

apply_common_styles()
st.set_page_config(layout="wide", page_title="연간 재무 요약")
st.title("📅 연간 재무 요약")
st.markdown("선택된 연도의 수입, 지출, 투자 현황과 현금 흐름을 요약합니다.")
st.markdown("---")

# --- 연도 선택 UI ---
current_year = date.today().year
selected_year = st.selectbox(
    "조회 연도",
    options=range(current_year, 2019, -1),
    index=0
)

st.markdown("---")

# --- 데이터 로드 ---
summary_df = get_annual_summary_data(selected_year)

if summary_df.empty:
    st.warning(f"{selected_year}년에는 분석할 데이터가 없습니다.")
else:
    all_months_of_year = [f"{selected_year}/{str(m).zfill(2)}" for m in range(1, 13)]

    summary_df['연월'] = pd.Categorical(summary_df['연월'], categories=all_months_of_year, ordered=True)

    # 1. 기본 피벗 테이블 생성
    pivot_df = pd.pivot_table(
        summary_df,
        index=['구분', '항목'],
        columns='연월',
        values='금액',
        aggfunc='sum',
        fill_value=0,
        margins=True,
        margins_name='Total',
        dropna=False  # <<< 모든 카테고리(월)를 표시하기 위해 이 옵션 추가
    )

    # 2. '투자가능금액' 행 계산
    income_total = pivot_df.loc[('수입', 'Total')] if ('수입', 'Total') in pivot_df.index else pd.Series(0,
                                                                                                     index=pivot_df.columns)
    expense_total = pivot_df.loc[('지출', 'Total')] if ('지출', 'Total') in pivot_df.index else pd.Series(0,
                                                                                                      index=pivot_df.columns)
    investable_cash_flow = income_total - expense_total
    investable_cash_flow.name = ('현금흐름', '투자가능금액')

    final_df = pd.concat([pivot_df, investable_cash_flow.to_frame().T])
    final_df.sort_index(inplace=True)

    # --- 여기가 수정되었습니다! ---
    # 3. reset_index 전에 인덱스 이름을 명확하게 다시 지정합니다.
    final_df.index.names = ['구분', '항목']
    final_df.reset_index(inplace=True)

    # 4. Pandas 스타일링 적용
    month_cols = [col for col in final_df.columns if col not in ['구분', '항목']]

    styled_df = final_df.style.format("{:,.0f}원", na_rep='-', subset=month_cols) \
        .background_gradient(cmap='Blues', subset=pd.IndexSlice[final_df['구분'] == '수입', month_cols]) \
        .background_gradient(cmap='Reds', subset=pd.IndexSlice[final_df['구분'] == '지출', month_cols]) \
        .background_gradient(cmap='Greens', subset=pd.IndexSlice[final_df['구분'] == '투자', month_cols]) \
        .set_properties(**{
        'text-align': 'right',
        'width': '130px'  # <<< 모든 숫자 컬럼에 고정 너비 부여
    }) \
        .set_table_styles([
        {'selector': 'th.row_heading', 'props': [('text-align', 'left')]},
        {'selector': 'th.col_heading', 'props': [('text-align', 'center')]}
    ])

    # 4. 최종 결과물을 st.dataframe으로 표시
    st.subheader(f"{selected_year}년 월별 요약")
    st.dataframe(
        styled_df,
        use_container_width=True,  # <<< 컨테이너 너비에 맞추되
        hide_index=True  # <<< 인덱스는 확실하게 숨김
    )