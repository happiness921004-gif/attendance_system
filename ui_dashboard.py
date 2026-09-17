import streamlit as st
import pandas as pd
import config
from modules.sheet_connector import load_sheet_data, clear_data_cache, render_sync_settings_widget

def render_dashboard():
    """1단계: 종합 대시보드 및 75개 강좌 현황판 렌더링"""
    
    # 상단 헤더 및 실시간 동기화 버튼
    col_title, col_btn = st.columns([3, 1])
    with col_title:
        st.title("📊 여성행복센터 종합 현황판")
        st.caption(f"{config.APP_TITLE} • {config.APP_SUBTITLE}")
    with col_btn:
        st.write("") # 간격
        if st.button("🔄 시트 최신 데이터 동기화", use_container_width=True, type="secondary"):
            clear_data_cache()
            st.toast("✅ 구글 시트 최신 데이터를 다시 불러왔습니다!", icon="🔄")
            st.rerun()

    # 구글 시트 양방향 실시간 동기화 설정 위젯
    render_sync_settings_widget()

    from modules.ui_students import get_combined_students_df
    from modules.ui_parking import get_combined_parking_df

    # 데이터 로드
    courses_df = load_sheet_data(config.SHEET_COURSES)
    students_df = get_combined_students_df()
    attendance_df = load_sheet_data(config.SHEET_ATTENDANCE)
    parking_df = get_combined_parking_df()

    # 1. 핵심 KPI 요약 카드
    st.markdown("### 📈 실시간 운영 지표")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    total_courses = len(courses_df)
    total_students = len(students_df)
    today_att_count = len(attendance_df)
    today_parking_count = len(parking_df)

    with kpi1:
        st.metric(label="총 강좌 수", value=f"{total_courses:,} 개", delta="75개 전 강좌 관리")
    with kpi2:
        st.metric(label="총 등록 수강생", value=f"{total_students:,} 명", delta="정원 관리 중")
    with kpi3:
        st.metric(label="오늘 출결 집계", value=f"{today_att_count:,} 건", delta="모바일 + 관리자 합산")
    with kpi4:
        st.metric(label="오늘 주차 신청 차량", value=f"{today_parking_count:,} 대", delta="무료 2시간 등록")

    st.markdown("---")

    # 2. 강좌 목록 검색 및 스마트 필터링
    st.markdown("### 🏫 75개 전 강좌 현황 및 스마트 검색")
    
    col_search, col_day, col_week = st.columns([2, 1, 1])
    with col_search:
        search_query = st.text_input("🔍 강좌명, 강좌ID, 강사명 검색", placeholder="예: 컴퓨터, C001, 김민수...")
    day_col = "수업요일" if "수업요일" in courses_df.columns else ("요일" if "요일" in courses_df.columns else None)
    with col_day:
        day_options = ["전체"] + sorted(list(set(courses_df[day_col].dropna()))) if day_col else ["전체"]
        selected_day = st.selectbox("📅 요일 필터", day_options)
    with col_week:
        selected_week = st.selectbox("⏱️ 기수 구분", ["전체", "15주 정규 강좌", "12주 단기 강좌"])

    # 필터링 로직
    filtered_df = courses_df.copy()
    if search_query and not filtered_df.empty:
        q = search_query.strip().lower()
        mask = filtered_df.astype(str).apply(lambda row: row.str.lower().str.contains(q, na=False)).any(axis=1)
        filtered_df = filtered_df[mask]

    if selected_day != "전체" and day_col:
        filtered_df = filtered_df[filtered_df[day_col] == selected_day]

    if selected_week == "15주 정규 강좌" and "강좌명" in filtered_df.columns:
        filtered_df = filtered_df[~filtered_df["강좌명"].str.contains("12주", na=False)]
    elif selected_week == "12주 단기 강좌" and "강좌명" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["강좌명"].str.contains("12주", na=False)]

    st.markdown(f"**검색 결과: `{len(filtered_df)}` 개 강좌 조회됨**")

    # 인터랙티브 데이터 테이블 렌더링
    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        height=450
    )

    # 3. 구글 시트 연동 안내 및 실시간 URL 입력 카드
    from modules.sheet_connector import get_current_spreadsheet_url, save_spreadsheet_url
    
    current_sheet_url = get_current_spreadsheet_url()
    with st.expander("🔗 구글 스프레드시트 실시간 연동 설정", expanded=(not bool(current_sheet_url))):
        if current_sheet_url:
            st.success(f"✅ 현재 연동된 시트: `{current_sheet_url}`")
            st.info("💡 스프레드시트에서 데이터를 수정하신 후, 상단의 **'🔄 시트 최신 데이터 동기화'** 버튼을 누르시면 0.1초 만에 최신 데이터가 반영됩니다.")
        else:
            st.warning("⚠️ 현재 **샘플(예시) 가상 데이터**로 동작 중입니다. 아래에 실제 구글 스프레드시트 링크를 입력해 주시면 즉시 실제 데이터로 바뀝니다!")

        col_url_in, col_url_btn = st.columns([4, 1])
        with col_url_in:
            input_url = st.text_input(
                "스프레드시트 URL 입력 (링크가 있는 모든 사용자 - 뷰어/편집자 권한 필요)",
                value=current_sheet_url,
                placeholder="https://docs.google.com/spreadsheets/d/1BxiMVs.../edit"
            )
        with col_url_btn:
            st.write("") # 간격
            if st.button("시트 연동 저장 🔗", use_container_width=True, type="primary"):
                if input_url.strip():
                    save_spreadsheet_url(input_url)
                    st.toast("✅ 스프레드시트 연동이 완료되었습니다!", icon="🔗")
                    st.rerun()
                else:
                    st.error("스프레드시트 링크를 입력해 주세요.")
