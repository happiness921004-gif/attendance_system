import datetime
import re
from typing import List, Dict, Set, Tuple

# 대한민국 주요 법정 공휴일 (2026~2027)
KOREAN_HOLIDAYS = {
    "2026-01-01",  # 신정
    "2026-02-16", "2026-02-17", "2026-02-18",  # 설날 연휴
    "2026-03-01", "2026-03-02",  # 삼일절 및 대체공휴일
    "2026-05-05",  # 어린이날
    "2026-05-24", "2026-05-25",  # 부처님오신날 및 대체공휴일
    "2026-06-06",  # 현충일
    "2026-08-15", "2026-08-17",  # 광복절 및 대체공휴일
    "2026-09-24", "2026-09-25", "2026-09-26",  # 추석 연휴
    "2026-10-03", "2026-10-05",  # 개천절 및 대체공휴일
    "2026-10-09",  # 한글날
    "2026-12-25",  # 크리스마스
    "2027-01-01",  # 2027 신정
}

# 요일 한글 매핑 (Python weekday: 0=월, 1=화, ..., 6=일)
WEEKDAY_MAP = {
    "월": 0, "월요일": 0,
    "화": 1, "화요일": 1,
    "수": 2, "수요일": 2,
    "목": 3, "목요일": 3,
    "금": 4, "금요일": 4,
    "토": 5, "토요일": 5,
    "일": 6, "일요일": 6,
}

def parse_course_weekdays(day_str: str) -> List[int]:
    """수업 요일 문자열(예: '월,수', '화/목', '월요일')을 파이썬 weekday 리스트로 변환"""
    if not day_str:
        return [0]
    
    tokens = re.split(r"[,/·\s]+", str(day_str).strip())
    weekdays = []
    for token in tokens:
        clean_token = token.replace("요일", "").strip()
        if clean_token in WEEKDAY_MAP:
            weekdays.append(WEEKDAY_MAP[clean_token])
    
    return sorted(list(set(weekdays))) if weekdays else [0]

def calculate_term_sessions(
    course_name: str,
    day_of_week_str: str,
    start_date_str: str = "2026-09-01",
    custom_holidays_str: str = "",
    custom_makeups_str: str = "",
    actual_att_dates: Set[str] = None
) -> Dict:
    """
    15주 / 12주 요일별 실제 수업 회차 및 날짜 계산 (공휴일 자동 건너뛰기 & 보강일 반영)
    """
    is_12_week = ("12주" in course_name) or ("/12주" in course_name)
    target_weeks = 12 if is_12_week else 15
    weekdays = parse_course_weekdays(day_of_week_str)
    target_session_count = target_weeks * len(weekdays)

    try:
        cur_date = datetime.datetime.strptime(start_date_str[:10], "%Y-%m-%d").date()
    except Exception:
        cur_date = datetime.date.today()

    # 휴일 세트 구성
    holiday_set = set(KOREAN_HOLIDAYS)
    if custom_holidays_str:
        for item in re.split(r"[,;\s]+", str(custom_holidays_str).strip()):
            cleaned = item.strip()
            if len(cleaned) == 10:
                holiday_set.add(cleaned)

    # 실제 출석이 체크된 날은 휴일에서 제외 (실제 수업 진행)
    if actual_att_dates:
        for att_d in actual_att_dates:
            if att_d in holiday_set:
                holiday_set.discard(att_d)

    # 보강일 세트 구성
    makeup_set = set()
    if custom_makeups_str:
        for item in re.split(r"[,;\s]+", str(custom_makeups_str).strip()):
            cleaned = item.strip()
            if len(cleaned) == 10:
                makeup_set.add(cleaned)

    sessions = []
    loop_date = cur_date
    days_checked = 0

    # 정규 회차 채우기 (공휴일 스킵)
    while len(sessions) < target_session_count and days_checked < 365:
        d_str = loop_date.strftime("%Y-%m-%d")
        if loop_date.weekday() in weekdays:
            if d_str not in holiday_set:
                sessions.append({
                    "date": d_str,
                    "short_date": f"{loop_date.month}/{loop_date.day}",
                    "session_index": len(sessions) + 1,
                    "label": f"{len(sessions) + 1}회",
                    "is_makeup": False
                })
        loop_date += datetime.timedelta(days=1)
        days_checked += 1

    # 보강일 추가
    existing_dates = {s["date"] for s in sessions}
    for m_date in sorted(list(makeup_set)):
        if m_date not in existing_dates:
            try:
                m_obj = datetime.datetime.strptime(m_date, "%Y-%m-%d").date()
                sessions.append({
                    "date": m_date,
                    "short_date": f"{m_obj.month}/{m_obj.day}",
                    "session_index": 999,
                    "label": "보강",
                    "is_makeup": True
                })
            except Exception:
                pass

    # 날짜 오름차순 정렬
    sessions.sort(key=lambda s: s["date"])

    return {
        "sessions": sessions,
        "is_12_week": is_12_week,
        "target_weeks": target_weeks,
        "total_target_sessions": target_session_count
    }
