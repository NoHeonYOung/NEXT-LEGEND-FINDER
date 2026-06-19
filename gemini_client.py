"""Gemini API optional wrapper.

원칙(설계 지시서 기준):
- `.streamlit/secrets.toml`의 `GEMINI_API_KEY`(또는 `GOOGLE_API_KEY`) 또는
  같은 이름의 환경변수가 있을 때만 사용한다.
- API key가 없거나 호출에 실패하면 항상 fallback(rule-based/template)으로
  처리되어야 한다 — 이 모듈은 성공/실패 여부만 반환하고, fallback 자체는
  호출부(evidence_extractor 등)에서 수행한다.
- API key 값은 어디에도 출력하지 않는다.
- 자동/반복 호출을 하지 않는다 — 버튼 클릭 시 1회 호출되는 용도로만 사용한다.
- Gemini를 필수 의존성으로 만들지 않는다 (google-genai 또는 google-generativeai가
  설치되어 있지 않아도 import 자체에서 앱이 죽지 않는다).

SDK 우선순위:
1. google-genai (신규 SDK): `from google import genai`
2. google-generativeai (구 SDK, fallback): `import google.generativeai as genai`

설치 안내: `pip install -U google-genai`
"""

import os

import streamlit as st

DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")


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


def _is_gemini_sdk_installed():
    """google-genai 또는 google-generativeai 중 하나라도 설치되어 있으면 True."""
    try:
        from google import genai  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        import google.generativeai  # noqa: F401
        return True
    except ImportError:
        return False


def is_gemini_available():
    """API key가 설정되어 있고 Gemini SDK를 사용할 수 있는지 확인.

    google-genai 또는 google-generativeai 중 하나라도 설치되어 있으면 True.
    """
    if get_gemini_api_key() is None:
        return False
    return _is_gemini_sdk_installed()


def get_gemini_sdk_unavailable_reason():
    """Gemini를 사용할 수 없는 이유를 반환한다.

    반환값:
    - None: 사용 가능
    - "no_api_key": API key 미설정
    - "sdk_not_installed": SDK 미설치 (key는 있음)
    """
    if get_gemini_api_key() is None:
        return "no_api_key"
    if not _is_gemini_sdk_installed():
        return "sdk_not_installed"
    return None


def generate_gemini_content(prompt, model_name=DEFAULT_GEMINI_MODEL):
    """Gemini API를 1회 호출한다.

    신규 SDK(google-genai)를 우선 사용하고, 없으면 구 SDK(google-generativeai)로
    fallback한다.

    반환: {"success": bool, "text": str|None, "error": str|None}
    - API key 없음: success=False, error에 사유 표시 (key 값은 포함하지 않음)
    - SDK 미설치: success=False, error에 설치 안내 포함
    - 호출 실패: success=False, error에 예외 메시지(요약)
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return {"success": False, "text": None, "error": "GEMINI_API_KEY가 설정되어 있지 않습니다."}

    # 신규 SDK 시도 (google-genai: `from google import genai`)
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model_name, contents=prompt)
        text = getattr(response, "text", None)
        if not text:
            return {"success": False, "text": None, "error": "Gemini 응답에 텍스트가 없습니다."}
        return {"success": True, "text": text, "error": None}
    except ImportError:
        pass  # 신규 SDK 없음 → 구 SDK 시도
    except Exception as exc:
        return {"success": False, "text": None, "error": str(exc)}

    # 구 SDK fallback (google-generativeai: `import google.generativeai as genai`)
    try:
        import google.generativeai as genai_legacy

        genai_legacy.configure(api_key=api_key)
        model = genai_legacy.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        text = getattr(response, "text", None)
        if not text:
            return {"success": False, "text": None, "error": "Gemini 응답에 텍스트가 없습니다."}
        return {"success": True, "text": text, "error": None}
    except ImportError:
        return {
            "success": False,
            "text": None,
            "error": (
                "Gemini SDK가 설치되지 않았습니다. "
                "`pip install -U google-genai` 실행 후 다시 시도하세요."
            ),
        }
    except Exception as exc:
        return {"success": False, "text": None, "error": str(exc)}
