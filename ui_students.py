import streamlit as st
import pandas as pd
import datetime
import io
import re
import config
from modules.sheet_connector import load_sheet_data, clear_data_cache, send_to_sheet_api, render_sync_settings_widget

def get_combined_students_df() -> pd.DataFrame:
    """기존 시트 수강생과 화면에서 신규 등록된 수강생 결합 (중복 방지)"""
    base_df = load_sheet_data(config.SHEET_STUDENTS).copy()
    
    if "new_registered_students" in st.session_state and st.session_state["new_registered_students"]:
        new_df = pd.DataFrame(st.session_state["new_registered_students"])
        if "수강생ID" in base_df.columns and "수강생ID" in new_df.columns:
            existing_ids = set(base_df["수강생ID"].dropna().astype(str))
            new_df = new_df[~new_df["수강생ID"].astype(str).isin(existing_ids)]
        if not new_df.empty:
            base_df = pd.concat([base_df, new_df], ignore_index=True)
        
    return base_df

def render_students_page():
    """3단계: 👥 강좌 및 수강생 관리 화면"""
    st.title("👥 강좌 및 수강생 관리")
    st.caption("1,193명 전체 수강생 명부 실시간 검색 · 75개 강좌별 수강생 조회 · 신규 수강생 등록 및 구글 시트 양방향 연동")

    # 양방향 동기화 설정 위젯
    render_sync_settings_widget()

    courses_df = load_sheet_data(config.SHEET_COURSES)
    students_df = get_combined_students_df()

    # 상단 탭 구분
    tab1, tab2 = st.tabs(["📋 수강생 명부 조회 & 검색", "➕ 신규 수강생 등록"])

    # ==========================================
    # TAB 1: 수강생 명부 조회 및 검색
    # ==========================================
    with tab1:
        # 상단 요약 KPI 카드
        kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
        with kpi_col1:
            st.metric("총 등록 수강생", f"{len(students_df):,} 명", delta="1,193명 원본 연동")
        with kpi_col2:
            st.metric("관리 중인 강좌", f"{len(courses_df):,} 개", delta="전 강좌 수강생 배정")
        with kpi_col3:
            new_added_cnt = len(st.session_state.get("new_registered_students", []))
            st.metric("포털 신규 등록", f"{new_added_cnt} 명", delta="실시간 반영 중")

        st.markdown("---")

        # 필터 컨트롤러
        c_filter1, c_filter2 = st.columns([2, 1])
        with c_filter1:
            search_kw = st.text_input("🔍 수강생 검색 (이름, 전화번호 뒷자리, 전체 연락처)", placeholder="예: 홍길동, 6083, 010...")
        with c_filter2:
            course_options = ["전체 강좌 보기"] + [
                f"[{r.get('강좌ID', '')}] {r.get('강좌명', '')}" for _, r in courses_df.iterrows()
            ]
            sel_course_filter = st.selectbox("🏫 강좌별 필터", course_options)

        # 필터링 로직
        filtered_st = students_df.copy()

        if sel_course_filter != "전체 강좌 보기":
            target_cid = sel_course_filter.split("] ")[0].replace("[", "").strip()
            target_cname = sel_course_filter.split("] ")[1].strip()
            
            c_mask = (
                (filtered_st["강좌ID"].astype(str).str.strip() == target_cid) |
                (filtered_st["강좌ID"].astype(str).str.strip() == target_cname)
            )
            if "강좌명" in filtered_st.columns:
                c_mask = c_mask | (filtered_st["강좌명"].astype(str).str.strip() == target_cid) | (filtered_st["강좌명"].astype(str).str.strip() == target_cname)
            filtered_st = filtered_st[c_mask]

        if search_kw.strip():
            q = search_kw.strip().lower()
            mask = filtered_st.astype(str).apply(lambda row: row.str.lower().str.contains(q, na=False)).any(axis=1)
            filtered_st = filtered_st[mask]

        st.markdown(f"**조회 결과: `{len(filtered_st):,}` 명**")

        # 깔끔한 테이블 렌더링
        # 불필요한 Unnamed 컬럼 숨기기
        disp_cols = [c for c in filtered_st.columns if not str(c).startswith("Unnamed")]
        st.dataframe(
            filtered_st[disp_cols],
            use_container_width=True,
            hide_index=True,
            height=450
        )

        # 엑셀 다운로드
        if not filtered_st.empty:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                filtered_st[disp_cols].to_excel(writer, index=False, sheet_name="수강생명부")
            
            st.download_button(
                label=f"📥 현재 조회된 수강생 명부 엑셀(.xlsx) 다운로드 ({len(filtered_st)}명)",
                data=buffer.getvalue(),
                file_name=f"수강생명부_{datetime.date.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="secondary"
            )

    # ==========================================
    # TAB 2: 신규 수강생 등록 폼
    # ==========================================
    with tab2:
        st.markdown("### ➕ 신규 수강생 등록")
        st.caption("새로운 수강생을 시스템에 등록하면 출석부 및 수강생 명부에 즉시 반영됩니다.")

        course_reg_choices = [
            f"[{r.get('강좌ID', '')}] {r.get('강좌명', '')} ({r.get('강사명', '-')} 강사)"
            for _, r in courses_df.iterrows()
        ]

        with st.form("new_student_form", clear_on_submit=True):
            r_col1, r_col2 = st.columns(2)
            with r_col1:
                reg_course = st.selectbox("수강할 강좌 선택 *", course_reg_choices)
                reg_name = st.text_input("수강생 성명 *", placeholder="예: 김민지")
                reg_phone_full = st.text_input("연락처 (전체) *", placeholder="예: 010-1234-5678")
            with r_col2:
                reg_date = st.date_input("등록 일자", datetime.date.today())
                reg_pay = st.selectbox("결제 상태", ["완납", "미납", "분납", "면제(장학생)"])
                reg_memo = st.text_input("비고/메모 (선택)", placeholder="예: 교재비 납부 완료, 중도수강")

            submit_reg = st.form_submit_button("➕ 신규 수강생 등록하기", use_container_width=True, type="primary")

            if submit_reg:
                if not reg_name.strip():
                    st.error("수강생 성명을 입력해 주세요.")
                elif not reg_phone_full.strip():
                    st.error("연락처를 입력해 주세요.")
                else:
                    # 데이터 정제
                    clean_phone_full = reg_phone_full.strip()
                    phone_digits = re.sub(r"[^\d]", "", clean_phone_full)
                    phone_last4 = phone_digits[-4:] if len(phone_digits) >= 4 else phone_digits
                    
                    target_cid = reg_course.split("] ")[0].replace("[", "").strip()
                    target_cname = reg_course.split("] ")[1].split(" (")[0].strip()

                    # 신규 ID 채번 (기존 최대 ID 번호 기반 중복 방지 채번)
                    max_id_num = 0
                    if "수강생ID" in students_df.columns:
                        for sid in students_df["수강생ID"].dropna().astype(str):
                            num_part = re.sub(r"[^\d]", "", sid)
                            if num_part.isdigit():
                                val = int(num_part)
                                if val > max_id_num:
                                    max_id_num = val
                    next_id_num = max(max_id_num + 1, len(students_df) + 1)
                    new_st_id = f"S{next_id_num:04d}"

                    new_student_record = {
                        "수강생ID": new_st_id,
                        "강좌ID": target_cid,
                        "강좌명": target_cname,
                        "수강생이름": reg_name.strip(),
                        "전화번호뒷자리": phone_last4,
                        "연락처(전체)": clean_phone_full,
                        "등록일자": reg_date.strftime("%Y%m%d"),
                        "결제상태": reg_pay,
                        "비고": reg_memo.strip()
                    }

                    # 구글 시트 양방향 실시간 전송 시도
                    api_res = send_to_sheet_api("addStudent", {
                        "id": new_st_id,
                        "courseId": target_cid,
                        "courseName": target_cname,
                        "name": reg_name.strip(),
                        "phoneLast4": phone_last4,
                        "phoneFull": clean_phone_full,
                        "regDate": reg_date.strftime("%Y%m%d"),
                        "payStatus": reg_pay,
                        "memo": reg_memo.strip()
                    })

                    if "new_registered_students" not in st.session_state:
                        st.session_state["new_registered_students"] = []
                    
                    st.session_state["new_registered_students"].append(new_student_record)
                    
                    if api_res.get("status") == "success":
                        st.success(f"🎉 '{reg_name.strip()}' 님이 구글 스프레드시트에 실시간 영구 등록되었습니다! (수강생ID: {new_st_id})")
                        st.toast(f"📊 구글 시트 저장 완료: {reg_name.strip()}", icon="✅")
                    elif api_res.get("status") == "not_configured":
                        st.success(f"🎉 '{reg_name.strip()}' 님이 등록되었습니다! (수강생ID: {new_st_id})")
                        st.info("💡 상단 '구글 시트 양방향 실시간 동기화 설정'에 Web App URL을 입력하시면 스프레드시트에 즉시 영구 저장됩니다.")
                    else:
                        st.warning(f"⚠️ 구글 시트 전송 알림: {api_res.get('message', '')}")
                    
                    st.rerun()

        # 최근 등록된 학생 목록 미리보기
        if "new_registered_students" in st.session_state and st.session_state["new_registered_students"]:
            st.markdown("#### 🕒 방금 등록된 신규 수강생 목록")
            recent_df = pd.DataFrame(st.session_state["new_registered_students"])
            st.dataframe(recent_df, use_container_width=True, hide_index=True)
            
            if st.button("🗑️ 방금 등록한 목록 초기화", type="secondary"):
                st.session_state["new_registered_students"] = []
                st.rerun()
