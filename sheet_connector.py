import streamlit as st
import pandas as pd
import re
import urllib.parse
from typing import Dict, Any, Optional
import config

def get_current_spreadsheet_url() -> str:
    """현재 설정된 스프레드시트 URL 반환"""
    if "spreadsheet_url" in st.session_state and st.session_state["spreadsheet_url"]:
        return st.session_state["spreadsheet_url"].strip()
    if "spreadsheet_url" in st.secrets and st.secrets["spreadsheet_url"]:
        return str(st.secrets["spreadsheet_url"]).strip()
    return ""

def save_spreadsheet_url(new_url: str):
    """스프레드시트 URL 저장 및 세션 갱신"""
    cleaned_url = new_url.strip()
    st.session_state["spreadsheet_url"] = cleaned_url
    
    # .streamlit/secrets.toml 파일 업데이트
    secrets_path = ".streamlit/secrets.toml"
    try:
        with open(secrets_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        if 'spreadsheet_url = ' in content:
            new_content = re.sub(r'spreadsheet_url\s*=\s*".*?"', f'spreadsheet_url = "{cleaned_url}"', content)
        else:
            new_content = content + f'\nspreadsheet_url = "{cleaned_url}"\n'
            
        with open(secrets_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception:
        pass
    
    clear_data_cache()

def get_current_webapp_url() -> str:
    """현재 설정된 Apps Script 웹 앱(양방향 동기화) URL 반환"""
    if "webapp_url" in st.session_state and st.session_state["webapp_url"]:
        return st.session_state["webapp_url"].strip()
    if "webapp_url" in st.secrets and st.secrets["webapp_url"]:
        return str(st.secrets["webapp_url"]).strip()
    return ""

def save_webapp_url(new_url: str):
    """Apps Script 웹 앱 URL 저장 및 secrets.toml 업데이트"""
    cleaned_url = new_url.strip()
    st.session_state["webapp_url"] = cleaned_url
    
    secrets_path = ".streamlit/secrets.toml"
    try:
        with open(secrets_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        if 'webapp_url = ' in content:
            new_content = re.sub(r'webapp_url\s*=\s*".*?"', f'webapp_url = "{cleaned_url}"', content)
        else:
            new_content = content + f'\nwebapp_url = "{cleaned_url}"\n'
            
        with open(secrets_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception:
        pass

def send_to_sheet_api(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    구글 시트의 Apps Script 웹 앱(doPost)으로 데이터를 실시간 전송하여
    스프레드시트에 직접 행을 영구 추가/동기화합니다.
    """
    webapp_url = get_current_webapp_url()
    if not webapp_url:
        return {
            "status": "not_configured",
            "message": "양방향 실시간 동기화 웹 앱 URL이 아직 설정되지 않았습니다."
        }
    
    import requests
    data = {"action": action, **payload}
    try:
        resp = requests.post(webapp_url, json=data, timeout=15, allow_redirects=True)
        clear_data_cache()
        try:
            res_json = resp.json()
            return res_json
        except Exception:
            if resp.status_code in [200, 302]:
                return {"status": "success", "message": "구글 스프레드시트에 정상 기록되었습니다."}
            return {"status": "error", "message": f"시트 응답 코드: {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "message": f"구글 시트 전송 실패: {str(e)}"}


import glob
import json

def get_service_account_credentials() -> Optional[Dict[str, Any]]:
    """secrets.toml 또는 작업 폴더 내의 서비스 계정 JSON 파일 자동 감지"""
    if "gcp_service_account" in st.secrets:
        return dict(st.secrets["gcp_service_account"])
    
    for pattern in ["*.json", ".streamlit/*.json"]:
        for f_path in glob.glob(pattern):
            try:
                with open(f_path, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                    if data.get("type") == "service_account" and "private_key" in data:
                        return data
            except Exception:
                continue
    return None

@st.cache_data(ttl=60)
def load_sheet_data(sheet_name: str, spreadsheet_url: str = "") -> pd.DataFrame:
    """
    구글 스프레드시트의 특정 탭 데이터를 로드하여 DataFrame으로 반환합니다.
    1. Service Account 연동 시도 (완전 비공개 시트 안전 접근)
    2. 시트 링크 기반 (gviz) 연동 시도 (한글 탭명 완벽 인코딩)
    3. 미설정 시 내장 샘플 데이터 자동 제공 (테스트 및 즉시 체험용)
    """
    url = spreadsheet_url or get_current_spreadsheet_url()
    
    # 1. 서비스 계정(gspread) 연결 시도 (100% 비공개 철통 보안)
    creds_info = get_service_account_credentials()
    if creds_info and url:
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
            gc = gspread.authorize(credentials)
            
            sh = gc.open_by_url(url)
            ws = sh.worksheet(sheet_name)
            data = ws.get_all_records()
            if data:
                return clean_sheet_dataframe(pd.DataFrame(data), sheet_name)
        except Exception:
            pass

    # 2. 스프레드시트 URL 기반 (공개 또는 링크 공유 시트) CSV 로드 시도
    if url:
        sheet_id_match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
        if sheet_id_match:
            sheet_id = sheet_id_match.group(1)
            encoded_tab = urllib.parse.quote(sheet_name)
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={encoded_tab}"
            try:
                df = pd.read_csv(csv_url)
                if not df.empty:
                    return clean_sheet_dataframe(df, sheet_name)
            except Exception:
                pass

    # 3. 시트 연동 전이거나 로드 실패 시: 내장 샘플 데이터 제공 (UI가 깨지지 않고 즉시 작동)
    return get_sample_data(sheet_name)

def clean_sheet_dataframe(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    """빈 행이나 수식만 걸려있고 실제 데이터가 없는 공백 행 필터링"""
    if df.empty:
        return df
    
    df.columns = [str(c).strip() for c in df.columns]
    
    if sheet_name == config.SHEET_STUDENTS:
        # 수강생 이름이 있는 행만 유효한 실제 수강생으로 집계
        name_cols = [c for c in df.columns if "이름" in c]
        if name_cols:
            ncol = name_cols[0]
            df = df[df[ncol].notna() & (df[ncol].astype(str).str.strip() != "") & (df[ncol].astype(str).str.strip() != "nan")]
            
    elif sheet_name == config.SHEET_COURSES:
        # 강좌명 또는 강좌ID가 있는 행만 유효
        c_cols = [c for c in df.columns if "강좌" in c]
        if c_cols:
            ccol = c_cols[0]
            df = df[df[ccol].notna() & (df[ccol].astype(str).str.strip() != "") & (df[ccol].astype(str).str.strip() != "nan")]
            
    elif sheet_name == config.SHEET_ATTENDANCE:
        # 출석 일자가 있는 행만 유효
        d_cols = [c for c in df.columns if "일자" in c or "날짜" in c]
        if d_cols:
            dcol = d_cols[0]
            df = df[df[dcol].notna() & (df[dcol].astype(str).str.strip() != "") & (df[dcol].astype(str).str.strip() != "nan")]

    elif sheet_name == config.SHEET_PARKING:
        # 차량번호가 있는 행만 유효
        p_cols = [c for c in df.columns if "차량" in c]
        if p_cols:
            pcol = p_cols[0]
            df = df[df[pcol].notna() & (df[pcol].astype(str).str.strip() != "") & (df[pcol].astype(str).str.strip() != "nan")]

    return df.reset_index(drop=True)

def get_sample_data(sheet_name: str) -> pd.DataFrame:
    """시트 연동 전에도 UI와 기능이 100% 돌아가도록 지원하는 샘플 데이터셋"""
    if sheet_name == config.SHEET_COURSES:
        sample_courses = []
        days_cycle = ["월", "화", "수", "목", "금", "월,수", "화,목"]
        inst_list = ["김민수", "이지은", "박서준", "최유나", "정재현", "한소희", "오세훈"]
        
        for i in range(1, 76):
            c_id = f"C{i:03d}"
            day = days_cycle[(i - 1) % len(days_cycle)]
            inst = inst_list[(i - 1) % len(inst_list)]
            is_12w = (i % 6 == 0)
            c_name = f"생활 영어 회화 {i}반/12주" if is_12w else f"스마트폰 & 컴퓨터 실무 {i}반"
            
            sample_courses.append({
                "강좌ID": c_id,
                "강좌명": c_name,
                "요일": day,
                "시작시간": "10:00",
                "종료시간": "12:00",
                "강사명": inst,
                "강사전화번호": f"010-{1000+i:04d}-5678",
                "강의실": f"{100 + (i % 5)}호",
                "수강료": 50000,
                "정원": 20,
                "수강생수": 15
            })
        return pd.DataFrame(sample_courses)

    elif sheet_name == config.SHEET_STUDENTS:
        sample_students = []
        names = ["강태양", "김영희", "이철수", "박지민", "최동훈", "정수빈", "한가람", "윤서연", "임재범", "송혜교"]
        for i in range(1, 76):
            c_id = f"C{i:03d}"
            for idx, n in enumerate(names):
                sample_students.append({
                    "강좌ID": c_id,
                    "강좌명": f"강좌 {c_id}",
                    "이름": f"{n}{idx+1}",
                    "전화번호": f"010-9999-{1000+idx:04d}",
                    "등록일자": "2026-09-01",
                    "결제여부": "완납",
                    "상태": "수강중"
                })
        return pd.DataFrame(sample_students)

    elif sheet_name == config.SHEET_ATTENDANCE:
        sample_att = [
            {"일자": "2026-09-07", "강좌ID": "C001", "강좌명": "스마트폰 & 컴퓨터 실무 1반", "이름": "강태양1", "전화번호": "1000", "출결상태": "출석", "인증방식": "QR모바일", "체크시간": "09:55:12"},
            {"일자": "2026-09-07", "강좌ID": "C001", "강좌명": "스마트폰 & 컴퓨터 실무 1반", "이름": "김영희2", "전화번호": "1001", "출결상태": "출석", "인증방식": "QR모바일", "체크시간": "09:58:34"},
            {"일자": "2026-09-07", "강좌ID": "C001", "강좌명": "스마트폰 & 컴퓨터 실무 1반", "이름": "이철수3", "전화번호": "1002", "출결상태": "지각", "인증방식": "관리자직접", "체크시간": "10:15:00"},
            {"일자": "2026-09-07", "강좌ID": "C001", "강좌명": "스마트폰 & 컴퓨터 실무 1반", "이름": "박지민4", "전화번호": "1003", "출결상태": "결석", "인증방식": "-", "체크시간": "-"}
        ]
        return pd.DataFrame(sample_att)

    elif sheet_name == config.SHEET_PARKING:
        sample_parking = [
            {"일자": "2026-09-07", "차량번호": "12가3456", "이름": "강태양1", "강좌명": "스마트폰 & 컴퓨터 실무 1반", "등록시간": "09:52:10"},
            {"일자": "2026-09-07", "차량번호": "56나7890", "이름": "이철수3", "강좌명": "스마트폰 & 컴퓨터 실무 1반", "등록시간": "10:12:45"}
        ]
        return pd.DataFrame(sample_parking)

    return pd.DataFrame()

def clear_data_cache():
    """모든 데이터 캐시를 비워 구글 시트의 최신 내용을 강제로 다시 불러옵니다."""
    st.cache_data.clear()

def render_sync_settings_widget():
    """구글 스프레드시트 양방향 실시간 동기화 설정 UI 위젯"""
    webapp_url = get_current_webapp_url()
    
    with st.expander("⚡ 구글 시트 양방향 실시간 동기화 설정 (Streamlit ↔ 구글 시트)", expanded=not bool(webapp_url)):
        if webapp_url:
            st.success("🟢 **양방향 실시간 동기화 활성화됨** (Streamlit에서 등록 시 구글 스프레드시트에 즉시 영구 저장됩니다)")
        else:
            st.info("🟡 **현재 임시 로컬 세션 모드** (아래 Apps Script 웹 앱 배포 URL을 1회 등록하시면 구글 시트에 직접 자동 영구 저장됩니다)")
            
        col1, col2 = st.columns([4, 1])
        with col1:
            input_url = st.text_input(
                "Google Apps Script 웹 앱 URL (배포 URL)",
                value=webapp_url,
                placeholder="https://script.google.com/macros/s/.../exec",
                help="구글 스프레드시트 [확장 프로그램] > [Apps Script] > [배포] > [새 배포] > [웹 앱] 배포 후 발급받은 URL을 입력하세요."
            )
        with col2:
            st.write("")
            st.write("")
            if st.button("💾 URL 저장", key="save_webapp_url_btn", use_container_width=True):
                save_webapp_url(input_url)
                st.success("동기화 URL이 저장되었습니다!")
                st.rerun()

        # 연결 테스트 버튼
        if webapp_url:
            if st.button("🔄 시트 API 연결 테스트 (Ping)", key="test_webapp_ping_btn"):
                import requests
                try:
                    res = requests.get(webapp_url, timeout=10, allow_redirects=True)
                    if res.status_code == 200:
                        st.balloons()
                        st.success(f"🎉 구글 시트 양방향 API 연동 확인 완료! 응답: {res.text}")
                    else:
                        st.error(f"연결 응답 코드: {res.status_code}")
                except Exception as e:
                    st.error(f"연결 테스트 실패: {str(e)}")

        st.markdown("""
        ---
        **📌 3단계 초간단 양방향 연동 방법:**
        1. 구글 스프레드시트 메뉴에서 **[확장 프로그램] → [Apps Script]** 클릭
        2. 열린 코드 창에 프로젝트 내 `ALL_IN_ONE_CODE.txt` 파일의 전체 내용을 복사하여 붙여넣고 저장(Ctrl+S)
        3. 우측 상단 **[배포] → [새 배포]** 선택:
           - **유형 선택**: 톱니바퀴 ⚙️ 클릭 → `웹 앱` 선택
           - **실행 주체**: `나(내 이메일)`
           - **액세스 권한**: `모든 사용자 (Anyone)` 선택
           - **[배포]** 클릭 후 나타나는 **웹 앱 URL (`https://script.google.com/.../exec`)**을 복사하여 위 입력란에 붙여넣기!
        """)
