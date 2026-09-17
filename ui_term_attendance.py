import streamlit as st
import pandas as pd
import datetime
import io
import config
from modules.sheet_connector import load_sheet_data, clear_data_cache
from modules.term_calculator import calculate_term_sessions

def render_term_attendance_page():
    """2단계: 15주/12주 기수종합 출석부 인터랙티브 화면"""
    
    st.title("📋 15주/12주 기수종합 출석부")
    st.caption("강좌별 전 회차 출결 매트릭스 · 공휴일 자동제외 & 보강일 반영 · 실시간 출결 수정 · 엑셀 다운로드")

    from modules.ui_students import get_combined_students_df
    # 1. 시트 데이터 로드
    courses_df = load_sheet_data(config.SHEET_COURSES)
    students_df = get_combined_students_df()
    att_df = load_sheet_data(config.SHEET_ATTENDANCE)

    if courses_df.empty:
        st.warning("⚠️ 등록된 강좌 목록이 없습니다.")
        return

    # 2. 강좌 선택 셀렉트박스
    course_labels = []
    course_map = {}
    for idx, row in courses_df.iterrows():
        cid = str(row.get("강좌ID", f"C{idx+1:03d}")).strip()
        cname = str(row.get("강좌명", cid)).strip()
        inst = str(row.get("강사명", "-")).strip()
        day = str(row.get("수업요일", row.get("요일", "-"))).strip()
        label = f"[{cid}] {cname} ({inst} 강사 | {day}요일)"
        course_labels.append(label)
        course_map[label] = row

    col_cselect, col_start_d = st.columns([3, 1])
    with col_cselect:
        selected_label = st.selectbox("🎯 강좌 선택 (75개 전 강좌)", course_labels, index=0)
        selected_course = course_map[selected_label]
        sel_c_id = str(selected_course.get("강좌ID", "")).strip()
        sel_c_name = str(selected_course.get("강좌명", "")).strip()
        sel_days = str(selected_course.get("수업요일", selected_course.get("요일", "월"))).strip()
        sel_inst = str(selected_course.get("강사명", "-")).strip()
        sel_room = str(selected_course.get("강의실", "-")).strip()
        sel_time = f"{selected_course.get('시작시간', '')}~{selected_course.get('종료시간', '')}"

    with col_start_d:
        start_date_val = st.date_input("📅 기수 개강일자", datetime.date(2026, 9, 1))
        start_date_str = start_date_val.strftime("%Y-%m-%d")

    # 추가 옵션 (공휴일/보강일 설정)
    with st.expander("⚙️ 공휴일 제외 및 추가 보강일 설정 (선택)", expanded=False):
        c_hol, c_mk = st.columns(2)
        with c_hol:
            custom_hols = st.text_input("추가 휴강일자 (쉼표 구분)", placeholder="예: 2026-09-15, 2026-10-02")
        with c_mk:
            custom_makeups = st.text_input("추가 보강일자 (쉼표 구분)", placeholder="예: 2026-11-28, 2026-12-19")

    # 3. 해당 강좌의 실제 출석 날짜 수집
    import re
    actual_dates = set()
    if not att_df.empty:
        c_att_mask = (
            (att_df["강좌ID"].astype(str).str.strip() == sel_c_id) |
            (att_df["강좌ID"].astype(str).str.strip() == sel_c_name)
        )
        if "강좌명" in att_df.columns:
            c_att_mask = c_att_mask | (att_df["강좌명"].astype(str).str.strip() == sel_c_id) | (att_df["강좌명"].astype(str).str.strip() == sel_c_name)
        c_att = att_df[c_att_mask]
        
        att_date_col = "출석일자" if "출석일자" in c_att.columns else ("일자" if "일자" in c_att.columns else None)
        if not c_att.empty and att_date_col:
            actual_dates = set(c_att[att_date_col].dropna().astype(str).str[:10])

    # 4. 회차 계산 (15주/12주, 공휴일 스킵, 보강일)
    calc_res = calculate_term_sessions(
        course_name=sel_c_name,
        day_of_week_str=sel_days,
        start_date_str=start_date_str,
        custom_holidays_str=custom_hols,
        custom_makeups_str=custom_makeups,
        actual_att_dates=actual_dates
    )
    sessions = calc_res["sessions"]
    is_12_week = calc_res["is_12_week"]
    target_weeks = calc_res["target_weeks"]

    # 5. 수강생 명단 필터링
    c_students = []
    if not students_df.empty:
        st_match_mask = (
            (students_df["강좌ID"].astype(str).str.strip() == sel_c_id) |
            (students_df["강좌ID"].astype(str).str.strip() == sel_c_name)
        )
        if "강좌명" in students_df.columns:
            st_match_mask = st_match_mask | (students_df["강좌명"].astype(str).str.strip() == sel_c_id) | (students_df["강좌명"].astype(str).str.strip() == sel_c_name)
        sub_st = students_df[st_match_mask].copy()
        
        if not sub_st.empty:
            name_col = "수강생이름" if "수강생이름" in sub_st.columns else ("이름" if "이름" in sub_st.columns else None)
            phone_col = "전화번호뒷자리" if "전화번호뒷자리" in sub_st.columns else ("전화번호" if "전화번호" in sub_st.columns else None)
            for _, r in sub_st.iterrows():
                st_name = str(r.get(name_col, "")).strip() if name_col else ""
                raw_phone = str(r.get(phone_col, "")).strip() if phone_col else ""
                st_phone = re.sub(r"\.0$", "", raw_phone)[-4:]
                if st_name and st_name != "nan":
                    c_students.append({
                        "name": st_name,
                        "phone": st_phone,
                        "key": f"{st_name}_{st_phone}"
                    })

    # 학생 가나다순 정렬
    c_students.sort(key=lambda s: s["name"])

    # 강좌 요약 지표 카드
    st.markdown("---")
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("강좌 구분", f"{target_weeks}주 과정", delta="12주 단기" if is_12_week else "15주 정규")
    with m2:
        st.metric("수업 요일/시간", f"{sel_days} {sel_time}")
    with m3:
        st.metric("담당 강사 / 강의실", f"{sel_inst} ({sel_room})")
    with m4:
        st.metric("등록 수강생", f"{len(c_students)} 명")
    with m5:
        st.metric("총 수업 회차", f"{len(sessions)} 회차")

    # 6. 세션 출결 맵 구성 (실시간 수정 지원을 위해 session_state 연동)
    if "custom_term_att" not in st.session_state:
        st.session_state["custom_term_att"] = {}

    today_str = datetime.date.today().strftime("%Y-%m-%d")

    # 기본 출석 기록 맵핑
    att_map = {}
    if not att_df.empty:
        c_att_mask = (
            (att_df["강좌ID"].astype(str).str.strip() == sel_c_id) |
            (att_df["강좌ID"].astype(str).str.strip() == sel_c_name)
        )
        if "강좌명" in att_df.columns:
            c_att_mask = c_att_mask | (att_df["강좌명"].astype(str).str.strip() == sel_c_id) | (att_df["강좌명"].astype(str).str.strip() == sel_c_name)
        c_att = att_df[c_att_mask]

        att_date_col = "출석일자" if "출석일자" in c_att.columns else ("일자" if "일자" in c_att.columns else None)
        att_name_col = "수강생이름" if "수강생이름" in c_att.columns else ("이름" if "이름" in c_att.columns else None)
        att_phone_col = "전화번호뒷자리" if "전화번호뒷자리" in c_att.columns else ("전화번호" if "전화번호" in c_att.columns else None)
        att_status_col = "출석상태" if "출석상태" in c_att.columns else ("출결상태" if "출결상태" in c_att.columns else "상태")

        for _, r in c_att.iterrows():
            d = str(r.get(att_date_col, ""))[:10] if att_date_col else ""
            s_name = str(r.get(att_name_col, "")).strip() if att_name_col else ""
            raw_phone = str(r.get(att_phone_col, "")).strip() if att_phone_col else ""
            s_phone = re.sub(r"\.0$", "", raw_phone)[-4:]
            status = str(r.get(att_status_col, "")).strip()
            
            mark = "△" if status == "지각" else ("✕" if status in ["결석", "취소"] else "○")
            if s_name and d:
                att_map[(s_name, s_phone, d)] = mark
                att_map[(s_name, "", d)] = mark

    # 7. 기수 출석부 매트릭스 테이블 생성
    matrix_rows = []
    for idx, st_info in enumerate(c_students, 1):
        s_name = st_info["name"]
        s_phone = st_info["phone"]
        row_dict = {
            "연번": idx,
            "수강생명": s_name,
            "전화(뒷4자리)": s_phone if s_phone else "-"
        }
        
        p_cnt, l_cnt, a_cnt = 0, 0, 0
        for s in sessions:
            s_d = s["date"]
            s_col = f"{s['label']}\n({s['short_date']})"
            
            # 사용자 실시간 수정값 우선 적용
            state_key = f"{sel_c_id}_{s_name}_{s_phone}_{s_d}"
            if state_key in st.session_state["custom_term_att"]:
                mark = st.session_state["custom_term_att"][state_key]
            else:
                mark = att_map.get((s_name, s_phone, s_d), att_map.get((s_name, "", s_d), ""))
                if not mark:
                    if s_d > today_str:
                        mark = ""  # 미래 세션
                    elif s_d < today_str and s_d in actual_dates:
                        mark = "✕"  # 수업 진행했으나 미체크 -> 결석
            
            if mark == "○": p_cnt += 1
            elif mark == "△": l_cnt += 1
            elif mark == "✕": a_cnt += 1

            row_dict[s_col] = mark

        total_held = p_cnt + l_cnt + a_cnt
        rate = ((p_cnt + l_cnt * 0.5) / total_held * 100) if total_held > 0 else 0.0
        pass_status = "대기" if total_held == 0 else ("수료" if rate >= 80.0 else "미수료")

        row_dict["총수업"] = total_held
        row_dict["출석"] = p_cnt
        row_dict["지각"] = l_cnt
        row_dict["결석"] = a_cnt
        row_dict["출석률"] = f"{rate:.1f}%"
        row_dict["수료여부"] = pass_status

        matrix_rows.append(row_dict)

    matrix_df = pd.DataFrame(matrix_rows)

    st.markdown("### 📊 기수종합 출석부 매트릭스")
    
    if matrix_df.empty:
        st.info("ℹ️ 해당 강좌에 등록된 수강생이 없습니다.")
    else:
        # 데이터프레임 스타일링 (○ 녹색, △ 주황, ✕ 빨강, 수료 강조)
        def highlight_attendance(val):
            if val == "○":
                return "color: #137333; font-weight: bold; text-align: center; background-color: #e6f4ea;"
            elif val == "△":
                return "color: #b06000; font-weight: bold; text-align: center; background-color: #fef7e0;"
            elif val == "✕":
                return "color: #c5221f; font-weight: bold; text-align: center; background-color: #fce8e6;"
            elif val == "수료":
                return "color: #1a73e8; font-weight: bold;"
            elif val == "미수료":
                return "color: #d93025; font-weight: bold;"
            return ""

        styled_df = matrix_df.style.map(highlight_attendance)
        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=450)

    # 8. 엑셀 다운로드 & 일괄 인쇄 버튼
    col_dl, col_print = st.columns(2)
    with col_dl:
        if not matrix_df.empty:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                matrix_df.to_excel(writer, index=False, sheet_name=f"{sel_c_id[:10]}_기수출석부")
            excel_data = buffer.getvalue()
            
            st.download_button(
                label=f"📥 [{sel_c_id}] 기수종합 출석부 엑셀(.xlsx) 다운로드",
                data=excel_data,
                file_name=f"기수종합출석부_{sel_c_id}_{start_date_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )
    with col_print:
        if st.button("🖨️ A4 가로 인쇄 미리보기 화면 열기", use_container_width=True):
            st.session_state["show_print_modal"] = True

    # 9. 원클릭 출결 상태 수정 툴
    st.markdown("---")
    st.markdown("### ✏️ 실시간 출결 수정 (원클릭 반영)")
    with st.expander("출결 기호(○, △, ✕) 즉시 수정하기", expanded=True):
        if not c_students:
            st.write("등록된 수강생이 없어 수정을 진행할 수 없습니다.")
        else:
            e_col1, e_col2, e_col3, e_col4 = st.columns([2, 2, 2, 1])
            with e_col1:
                edit_student = st.selectbox("수강생 선택", [f"{s['name']} ({s['phone']})" for s in c_students])
            with e_col2:
                edit_session = st.selectbox("회차/날짜 선택", [f"{s['label']} ({s['date']})" for s in sessions])
            with e_col3:
                edit_mark = st.radio("출결 상태 변경", ["○ 출석", "△ 지각", "✕ 결석", "빈칸(초기화)"], horizontal=True)
            with e_col4:
                st.write("") # 간격
                if st.button("💾 변경 저장", use_container_width=True, type="secondary"):
                    s_name_sel = edit_student.split(" (")[0]
                    s_phone_sel = edit_student.split(" (")[1].replace(")", "")
                    s_date_sel = edit_session.split(" (")[1].replace(")", "")
                    
                    symbol = "○" if "출석" in edit_mark else ("△" if "지각" in edit_mark else ("✕" if "결석" in edit_mark else ""))
                    state_key = f"{sel_c_id}_{s_name_sel}_{s_phone_sel}_{s_date_sel}"
                    st.session_state["custom_term_att"][state_key] = symbol
                    
                    st.toast(f"✅ {s_name_sel} 님의 {s_date_sel} 출결이 '{symbol}'(으)로 저장되었습니다!", icon="💾")
                    st.rerun()

    # 10. 인쇄용 A4 미리보기 모달 (필요 시)
    if st.session_state.get("show_print_modal", False):
        st.markdown("---")
        st.markdown("### 🖨️ A4 가로 인쇄 미리보기")
        st.caption("브라우저 인쇄(Ctrl+P) 시 깔끔하게 A4 가로 1장에 맞춰 출력됩니다.")
        
        # 간이 HTML 인쇄 테이블 렌더링
        html_table = matrix_df.to_html(classes="print-preview-tbl", index=False)
        st.markdown(f"""
            <style>
            .print-preview-box {{
                background: white;
                padding: 20px;
                border: 2px solid #1a73e8;
                border-radius: 8px;
                overflow-x: auto;
            }}
            .print-preview-tbl {{
                width: 100%;
                border-collapse: collapse;
                font-size: 11px;
                text-align: center;
            }}
            .print-preview-tbl th, .print-preview-tbl td {{
                border: 1px solid #ddd;
                padding: 4px 6px;
            }}
            .print-preview-tbl th {{
                background: #f1f3f4;
                font-weight: bold;
            }}
            </style>
            <div class="print-preview-box">
                <div style="font-size:18px; font-weight:bold; margin-bottom:10px;">
                    {sel_c_name} 기수종합 출석부 (A4 가로 미리보기)
                </div>
                {html_table}
            </div>
        """, unsafe_allow_html=True)
        
        if st.button("닫기 ✖️"):
            st.session_state["show_print_modal"] = False
            st.rerun()
