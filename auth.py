import streamlit as st
import os
import json
import re
from config import APP_TITLE, DEFAULT_MASTER_PASSWORD

AUTH_FILE = "admin_auth.json"

def get_configured_master_password() -> str:
    """설정된 마스터 비밀번호 반환 (세션 > 로컬JSON > secrets.toml > 기본값)"""
    # 1. 세션 상태
    if "custom_master_password" in st.session_state and st.session_state["custom_master_password"]:
        return str(st.session_state["custom_master_password"]).strip()
    
    # 2. 로컬 persistent 파일 (admin_auth.json)
    if os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "master_password" in data and data["master_password"]:
                    return str(data["master_password"]).strip()
        except Exception:
            pass

    # 3. .streamlit/secrets.toml
    if "master_password" in st.secrets and st.secrets["master_password"]:
        return str(st.secrets["master_password"]).strip()

    return DEFAULT_MASTER_PASSWORD

def verify_password(input_password: str) -> bool:
    """비밀번호 검증 (설정된 마스터 비밀번호 또는 관리자설정 시트의 PIN)"""
    clean_pw = input_password.strip()
    if not clean_pw:
        return False
    
    # 1. 마스터 비밀번호 비교
    target_master = get_configured_master_password()
    if clean_pw == target_master:
        return True

    # 2. 구글 스프레드시트의 '관리자설정' 시트 PIN 비교 (보조 인증)
    try:
        from modules.sheet_connector import load_sheet_data
        admin_df = load_sheet_data("관리자설정")
        if not admin_df.empty:
            pin_cols = [c for c in admin_df.columns if "PIN" in c or "비밀번호" in c or "비번" in c]
            if pin_cols:
                pcol = pin_cols[0]
                valid_pins = [str(p).strip().replace(".0", "") for p in admin_df[pcol].dropna()]
                if clean_pw in valid_pins:
                    return True
    except Exception:
        pass

    return False

def save_new_master_password(new_password: str) -> dict:
    """새로운 마스터 비밀번호 영구 저장 (세션, 로컬JSON, secrets.toml, Apps Script 클라우드)"""
    clean_pw = new_password.strip()
    st.session_state["custom_master_password"] = clean_pw

    # 1. 로컬 admin_auth.json 저장
    try:
        with open(AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump({"master_password": clean_pw}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # 2. .streamlit/secrets.toml 업데이트
    secrets_path = ".streamlit/secrets.toml"
    try:
        if os.path.exists(secrets_path):
            with open(secrets_path, "r", encoding="utf-8") as f:
                content = f.read()
            if 'master_password = ' in content:
                new_content = re.sub(r'master_password\s*=\s*".*?"', f'master_password = "{clean_pw}"', content)
            else:
                new_content = f'master_password = "{clean_pw}"\n' + content
            with open(secrets_path, "w", encoding="utf-8") as f:
                f.write(new_content)
    except Exception:
        pass

    # 3. 구글 Apps Script Web App API로 클라우드 영구 동기화
    try:
        from modules.sheet_connector import send_to_sheet_api
        send_to_sheet_api("updateMasterPassword", {"newPassword": clean_pw})
    except Exception:
        pass

    return {"status": "success", "message": "비밀번호가 성공적으로 변경되었습니다."}

def check_authentication() -> bool:
    """세션 인증 상태 확인"""
    return st.session_state.get("authenticated", False)

def login_form():
    """군더더기 없이 깔끔하고 모던한 마스터 로그인 화면"""
    st.markdown("""
        <style>
        .login-card {
            max-width: 420px;
            margin: 60px auto 20px auto;
            padding: 36px 32px 28px 32px;
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
            border: 1px solid #e2e8f0;
            text-align: center;
        }
        .login-logo-wrap {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 20px;
        }
        .login-title {
            font-size: 20px;
            font-weight: 700;
            color: #0f172a;
            line-height: 1.4;
            margin-bottom: 8px;
            letter-spacing: -0.5px;
        }
        .login-desc {
            font-size: 13px;
            color: #64748b;
            margin-bottom: 24px;
            line-height: 1.5;
        }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
            <div class="login-card">
                <div class="login-logo-wrap">
                    <svg width="56" height="56" viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <rect width="56" height="56" rx="14" fill="#1e293b"/>
                        <!-- 깔끔한 교육·기관 심볼 (학사모 & 기관 엠블럼) -->
                        <path d="M28 15L14 22L28 29L42 22L28 15Z" fill="#ffffff"/>
                        <path d="M18 26V34C18 37 22.5 40 28 40C33.5 40 38 37 38 34V26L28 31L18 26Z" fill="#94a3b8"/>
                        <path d="M41 24V33" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                </div>
                <div class="login-title">여성행복센터 교육프로그램 관리 시스템</div>
                <div class="login-desc">관리자 마스터 비밀번호를 입력해 주세요.</div>
            </div>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            password = st.text_input(
                "비밀번호",
                type="password",
                placeholder="비밀번호 입력",
                label_visibility="collapsed"
            )
            submit_btn = st.form_submit_button("로그인", use_container_width=True, type="primary")

            if submit_btn:
                if verify_password(password):
                    st.session_state["authenticated"] = True
                    st.success("인증 완료되었습니다.")
                    st.rerun()
                else:
                    st.error("비밀번호가 올바르지 않습니다.")

        st.caption("비밀번호는 시스템 설정 및 [비밀번호 변경] 메뉴에서 언제든 변경할 수 있습니다.")

def render_logout_sidebar():
    """사이드바 상단에 관리자 인증 상태 및 로그아웃 버튼"""
    with st.sidebar:
        st.markdown("""
            <div style="padding: 10px; background: #f1f5f9; border-radius: 8px; margin-bottom: 12px; border-left: 4px solid #0f172a;">
                <span style="font-size: 12.5px; font-weight: bold; color: #0f172a;">관리자 모드 접속 중</span><br>
                <span style="font-size: 11px; color: #64748b;">전체 메뉴 접근 권한 활성</span>
            </div>
        """, unsafe_allow_html=True)
        
        if st.button("로그아웃", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()
        st.markdown("---")

def render_change_password_page():
    """비밀번호 변경 전용 화면"""
    st.title("🔐 관리자 비밀번호 변경")
    st.caption("시스템 접속에 사용하는 관리자 마스터 비밀번호를 안전하게 변경합니다.")

    col1, col2 = st.columns([2, 1])

    with col1:
        with st.form("change_password_form", clear_on_submit=True):
            st.markdown("#### 🔑 비밀번호 변경 정보 입력")
            
            cur_password = st.text_input("현재 비밀번호 확인 *", type="password", placeholder="현재 사용 중인 비밀번호")
            new_password = st.text_input("새로운 비밀번호 *", type="password", placeholder="새 비밀번호 입력 (4자리 이상)")
            confirm_password = st.text_input("새로운 비밀번호 재확인 *", type="password", placeholder="새 비밀번호 다시 입력")

            st.write("")
            submit_pw = st.form_submit_button("🔒 비밀번호 변경 완료", use_container_width=True, type="primary")

            if submit_pw:
                if not cur_password.strip():
                    st.error("현재 비밀번호를 입력해 주세요.")
                elif not verify_password(cur_password):
                    st.error("현재 비밀번호가 일치하지 않습니다. 다시 확인해 주세요.")
                elif not new_password.strip():
                    st.error("새로운 비밀번호를 입력해 주세요.")
                elif len(new_password.strip()) < 4:
                    st.error("새 비밀번호는 최소 4자리 이상이어야 합니다.")
                elif new_password.strip() != confirm_password.strip():
                    st.error("새 비밀번호와 재확인 비밀번호가 서로 일치하지 않습니다.")
                elif new_password.strip() == cur_password.strip():
                    st.warning("현재 사용 중인 비밀번호와 동일합니다. 다른 비밀번호를 입력해 주세요.")
                else:
                    save_new_master_password(new_password.strip())
                    st.balloons()
                    st.success("🎉 비밀번호가 성공적으로 변경되었습니다! 다음 접속 시부터 변경된 새 비밀번호로 로그인하실 수 있습니다.")
                    st.toast("✅ 비밀번호 변경 완료!", icon="🔐")

    with col2:
        st.markdown("#### 💡 보안 안내사항")
        st.info("""
        * **즉시 영구 반영**: 비밀번호 변경 즉시 설정 파일 및 클라우드 동기화 시스템에 반영됩니다.
        * **분실 방지**: 변경하신 비밀번호는 별도로 메모해 두시길 권장합니다.
        * **초기 비밀번호 복구**: 만약 비밀번호를 잊으신 경우 스프레드시트의 `관리자설정` 시트에 등록된 관리자 PIN으로도 로그인하실 수 있습니다.
        """)

def require_auth():
    """인증 강제 게이트웨이: 인증되지 않으면 로그인 화면만 띄우고 앱 실행 중단"""
    if not check_authentication():
        login_form()
        st.stop()
    render_logout_sidebar()
