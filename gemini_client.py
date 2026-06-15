"""Gemini API optional wrapper.

원칙(설계 지시서 기준):
- `.streamlit/secrets.toml`의 `GEMINI_API_KEY`(또는 `GOOGLE_API_KEY`) 또는
  같은 이름의 환경변수가 있을 때만 사용한다.
- API key가 없거나 호출에 실패하면 항상 fallback(rule-based/template)으로
  처리되어야 한다 — 이 모듈은 성공/실패 여부만 반환하고, fallback 자체는
  호출부(evidence_extractor 등)에서 수행한다.
- API key 값은 어디에도 출력하지 않는다.
- 자동/반복 호출을 하지 않는다 — 버튼 클릭 시 1회 호출되는 용도로만 사용한다.
- Gemini를 필수 의존성으로 만들지 않는다 (google-generativeai가 설치되어
  있지 않아도 import 자체에서 앱이 죽지 않는다).
"""

import os

import streamlit as st

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


def get_gemini_api_key():
    """secrets -> 환경변수 순서로 GEMINI_API_KEY/GOOGLE_API_KEY를 찾는다.

    값 자체는 반환하되, 호출부에서 화면에 출력해서는 안 된다.
    """
    for key_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        try:
            value = st.secrets.get(key_name)
        except Exception:
            value = None
        if value:
            return value

    for key_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        value = os.environ.get(key_name)
        if value:
            return value

    return None


def is_gemini_available():
    """API key가 설정되어 있고 google-generativeai 패키지를 사용할 수 있는지 확인."""
    if get_gemini_api_key() is None:
        return False

    try:
        import google.generativeai  # noqa: F401
    except ImportError:
        return False

    return True


def generate_gemini_content(prompt, model_name=DEFAULT_GEMINI_MODEL):
    """Gemini API를 1회 호출한다.

    반환: {"success": bool, "text": str|None, "error": str|None}
    - API key 없음: success=False, error에 사유 표시 (key 값은 포함하지 않음)
    - google-generativeai 미설치: success=False, error에 사유 표시
    - 호출 실패: success=False, error에 예외 메시지(요약)
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return {"success": False, "text": None, "error": "GEMINI_API_KEY가 설정되어 있지 않습니다."}

    try:
        import google.generativeai as genai
    except ImportError:
        return {
            "success": False,
            "text": None,
            "error": "google-generativeai 패키지가 설치되어 있지 않습니다.",
        }

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        text = getattr(response, "text", None)

        if not text:
            return {"success": False, "text": None, "error": "Gemini 응답에 텍스트가 없습니다."}

        return {"success": True, "text": text, "error": None}
    except Exception as exc:
        return {"success": False, "text": None, "error": str(exc)}
