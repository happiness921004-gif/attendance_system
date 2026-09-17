import streamlit as st
import pandas as pd
import datetime
import io
import re
import config
from modules.sheet_connector import load_sheet_data, clear_data_cache, send_to_sheet_api, render_sync_settings_widget

def get_combined_parking_df() -> pd.DataFrame:
    """기존 시트 주차 데이터와 화면에서 신규 등록된 주차 데이터 결합 (중복 방지)"""
    base_df = load_sheet_data(config.SHEET_PARKING).copy()
    
    if "new_registered_parking" in st.session_state and st.session_state["new_registered_parking"]:
        new_df = pd.DataFrame(st.session_state["new_registered_parking"])
        if "차량번호" in base_df.columns and "차량번호" in new_df.columns:
            # 차량번호와 일시 기준으로 중복 확인
            existing_plates = set(base_df["차량번호"].dropna().astype(str).str.strip().str.replace(" ", ""))
            new_df = new_df[~new_df["차량번호"].astype(str).str.strip().str.replace(" ", "").isin(existing_plates)]
        if not new_df.empty:
            base_df = pd.concat([base_df, new_df], ignore_index=True)
        
    return base_df

def render_parking_page():
    """3단계: 🚗 주차(증) 관리 화면"""
    st.title("🚗 주차(증) 관리")
    st.caption("수강생 및 강사 무료 주차(2시간) 신청 현황 실시간 조회 · 차량번호 검색 · 관리실 제출용 엑셀 다운로드")

    # 양방향 동기화 설정 위젯
    render_sync_settings_widget()

    courses_df = load_sheet_data(config.SHEET_COURSES)
    parking_df = get_combined_parking_df()

    # 오늘 날짜
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    # 오늘 신청 건수 계산
    today_count = 0
    if not parking_df.empty:
        date_cols = [c for c in parking_df.columns if "일시" in c or "일자" in c or "시간" in c]
        if date_cols:
            dcol = date_cols[0]
            today_count = parking_df[parking_df[dcol].astype(str).str.contains(today_str)].shape[0]

    # 상단 요약 KPI 카드
    st.markdown("### 📈 주차 할인 현황 요약")
    p_kpi1, p_kpi2, p_kpi3, p_kpi4 = st.columns(4)
    with p_kpi1:
        st.metric("오늘 신청 차량", f"{today_count:,} 대", delta="2시간 무료 할인 적용")
    with p_kpi2:
        st.metric("누적 신청 건수", f"{len(parking_df):,} 건", delta="실시간 시트 연동")
    with p_kpi3:
        st.metric("무료 주차 시간", "최대 2시간", delta="교육 시간 기준")
    with p_kpi4:
        st.metric("등록 강좌 수", f"{len(courses_df)} 개", delta="전 강좌 연동")

    st.markdown("---")

    # 상단 탭 (차량 조회 & 현장 수기 등록)
    tab_view, tab_add = st.tabs(["🔍 주차 신청 차량 조회 & 엑셀 다운로드", "➕ 현장 주차 차량 즉시 등록"])

    # ==========================================
    # TAB 1: 주차 차량 조회 및 엑셀 다운로드
    # ==========================================
    with tab_view:
        col_s1, col_s2 = st.columns([2, 1])
        with col_s1:
            search_plate = st.text_input("🔍 차량번호 또는 강좌명 검색", placeholder="예: 3456, 12가, 바리스타...")
        with col_s2:
            date_filter = st.selectbox("📅 일자 구분 필터", ["전체 누적 보기", "오늘 신청 차량만 보기"])

        # 필터링 로직
        filtered_parking = parking_df.copy()

        if date_filter == "오늘 신청 차량만 보기" and not filtered_parking.empty:
            date_cols = [c for c in filtered_parking.columns if "일시" in c or "일자" in c or "시간" in c]
            if date_cols:
                dcol = date_cols[0]
                filtered_parking = filtered_parking[filtered_parking[dcol].astype(str).str.contains(today_str)]

        if search_plate.strip() and not filtered_parking.empty:
            q = search_plate.strip().lower()
            mask = filtered_parking.astype(str).apply(lambda row: row.str.lower().str.contains(q, na=False)).any(axis=1)
            filtered_parking = filtered_parking[mask]

        st.markdown(f"**조회된 차량: `{len(filtered_parking):,}` 대**")

        # 깔끔한 테이블 렌더링 (불필요한 Unnamed 컬럼 제외)
        disp_cols = [c for c in filtered_parking.columns if not str(c).startswith("Unnamed")]
        
        if filtered_parking.empty:
            st.info("ℹ️ 조건에 일치하는 주차 신청 차량이 없습니다.")
        else:
            # 스타일링 (차량번호 열 강조)
            st.dataframe(
                filtered_parking[disp_cols],
                use_container_width=True,
                hide_index=True,
                height=400
            )

            # 관리실 제출용 엑셀 다운로드
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                filtered_parking[disp_cols].to_excel(writer, index=False, sheet_name="주차할인신청명단")

            st.download_button(
                label=f"📥 [주차관리실 제출용] 주차 할인 차량 엑셀(.xlsx) 다운로드 ({len(filtered_parking)}대)",
                data=buffer.getvalue(),
                file_name=f"여성행복센터_주차할인차량_{datetime.date.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )

    # ==========================================
    # TAB 2: 현장 수기 즉시 등록 폼
    # ==========================================
    with tab_add:
        st.markdown("### ➕ 현장 주차 등록")
        st.caption("수강생 또는 강사가 안내 데스크에서 직접 차량번호를 제시한 경우 즉시 등록할 수 있습니다.")

        course_choices = ["기타/센터 방문"] + [
            f"[{r.get('강좌ID', '')}] {r.get('강좌명', '')}" for _, r in courses_df.iterrows()
        ]

        with st.form("manual_parking_form", clear_on_submit=True):
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                in_car_num = st.text_input("차량 번호 *", placeholder="예: 12가 3456 (뒷 4자리 포함)")
                in_course = st.selectbox("해당 강좌 선택", course_choices)
            with p_col2:
                in_driver_name = st.text_input("이름 (수강생 또는 강사명)", placeholder="예: 김민수")
                in_time = st.text_input("등록 일시", value=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            submit_parking = st.form_submit_button("🚗 주차 등록", use_container_width=True, type="primary")

            if submit_parking:
                clean_plate = in_car_num.strip().replace(" ", "")
                if not clean_plate:
                    st.error("차량 번호를 입력해 주세요.")
                else:
                    new_parking_record = {
                        "강좌명": in_course.split("] ")[-1] if "] " in in_course else in_course,
                        "강의실": "-",
                        "강사명": in_driver_name.strip() if in_driver_name.strip() else "-",
                        "강의시간": "-",
                        "차량번호": clean_plate,
                        "등록일시": in_time.strip()
                    }

                    course_name_clean = in_course.split("] ")[-1] if "] " in in_course else in_course
                    driver_clean = in_driver_name.strip() if in_driver_name.strip() else "-"

                    # 구글 시트 양방향 실시간 전송 시도
                    api_res = send_to_sheet_api("addParking", {
                        "courseName": course_name_clean,
                        "name": driver_clean,
                        "day": "-",
                        "time": "-",
                        "carNumber": clean_plate,
                        "regDate": in_time.strip()
                    })

                    if "new_registered_parking" not in st.session_state:
                        st.session_state["new_registered_parking"] = []

                    st.session_state["new_registered_parking"].append(new_parking_record)

                    if api_res.get("status") == "success":
                        st.success(f"✅ 차량번호 '{clean_plate}' (2시간 무료 주차) 구글 스프레드시트 영구 저장이 완료되었습니다!")
                        st.toast(f"🚗 구글 시트 반영 완료: {clean_plate}", icon="✅")
                    elif api_res.get("status") == "not_configured":
                        st.success(f"✅ 차량번호 '{clean_plate}' 등록 완료! (상단 Web App URL 설정 시 구글 시트에도 영구 저장됩니다)")
                    else:
                        st.warning(f"⚠️ 구글 시트 전송 알림: {api_res.get('message', '')}")

                    st.rerun()

        # 최근 등록 차량 미리보기
        if "new_registered_parking" in st.session_state and st.session_state["new_registered_parking"]:
            st.markdown("#### 🕒 방금 수기 등록된 차량 목록")
            recent_p_df = pd.DataFrame(st.session_state["new_registered_parking"])
            st.dataframe(recent_p_df, use_container_width=True, hide_index=True)

            if st.button("🗑️ 방금 수기 등록한 차량 목록 초기화", type="secondary"):
                st.session_state["new_registered_parking"] = []
                st.rerun()
