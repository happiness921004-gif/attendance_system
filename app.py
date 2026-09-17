import streamlit as st
import importlib
import config
import modules.auth
import modules.sheet_connector
import modules.term_calculator
import modules.ui_dashboard
import modules.ui_term_attendance
import modules.ui_students
import modules.ui_parking

# 파일 수정 시 브라우저에서 즉시 반영되도록 모듈 핫 리로드 (3단계 수강생/주차 관리 반영)
importlib.reload(config)
importlib.reload(modules.auth)
importlib.reload(modules.sheet_connector)
importlib.reload(modules.term_calculator)
importlib.reload(modules.ui_dashboard)
importlib.reload(modules.ui_term_attendance)
importlib.reload(modules.ui_students)
importlib.reload(modules.ui_parking)

from modules.auth import require_auth
from modules.ui_dashboard import render_dashboard
from modules.ui_term_attendance import render_term_attendance_page
from modules.ui_students import render_students_page
from modules.ui_parking import render_parking_page

# 1. 스트림릿 페이지 기본 설정 (와이드 모드, 한글 타이틀, 파비콘)
st.set_page_config(
    page_title=f"{config.APP_TITLE} | 관리 포털",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. [보안 핵심] 마스터 비밀번호 게이트웨이 인증 체크
# (인증되지 않은 사용자는 여기서 로그인 창만 보이고 나머지 코드는 일절 실행되지 않음)
require_auth()

# 3. 사이드바 메인 내비게이션
with st.sidebar:
    st.title("여성행복센터")
    st.caption(f"교육프로그램 관리 시스템 • {config.APP_VERSION}")
    
    menu = st.radio(
        "메뉴 선택",
        [
            "📊 종합 현황판 (대시보드)",
            "📋 15주/12주 기수종합 출석부",
            "👥 강좌 및 수강생 관리",
            "🚗 주차(증) 관리",
            "🔐 비밀번호 변경",
            "⚙️ 시스템 설정 및 백업"
        ],
        index=0
    )

# 4. 선택 메뉴별 화면 렌더링
if menu == "📊 종합 현황판 (대시보드)":
    render_dashboard()

elif menu == "📋 15주/12주 기수종합 출석부":
    render_term_attendance_page()

elif menu == "👥 강좌 및 수강생 관리":
    render_students_page()

elif menu == "🚗 주차(증) 관리":
    render_parking_page()

elif menu == "🔐 비밀번호 변경":
    from modules.auth import render_change_password_page
    render_change_password_page()

elif menu == "⚙️ 시스템 설정 및 백업":
    st.title("⚙️ 시스템 설정 및 백업")
    from modules.sheet_connector import render_sync_settings_widget
    render_sync_settings_widget()
    
    st.markdown("""
        ### 🛡️ 관리자 변경 & 다른 컴퓨터 사용 안내
        * **담당자/관리자가 바뀌는 경우**: 스프레드시트 소유자가 변경되어도 이 시스템은 그대로 작동합니다.
        * **다른 노트북에서 사용할 때**:
          1. 깃허브(GitHub) 및 Streamlit Cloud 무료 배포를 통해 웹 브라우저로 어디서든 접속할 수 있습니다.
          2. 또는 현재 폴더(`busy-davinci`)를 압축하여 다른 노트북으로 전달하여 실행할 수 있습니다.
    """)

# 5. 하단 푸터
st.markdown("---")
st.caption(f"© 2026 {config.APP_TITLE}. All rights reserved. • 안전한 구글 스프레드시트 클라우드 연동 기반")
