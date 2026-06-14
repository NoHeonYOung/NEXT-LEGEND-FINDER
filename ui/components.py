import pandas as pd
import streamlit as st


def safe_text(value, fallback="-"):
    if value is None:
        return fallback
    if isinstance(value, float) and pd.isna(value):
        return fallback
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else fallback
    if pd.isna(value):
        return fallback
    return str(value)


def render_status_banner(text, kind="info"):
    if kind == "success":
        st.success(text)
    elif kind == "warning":
        st.warning(text)
    elif kind == "error":
        st.error(text)
    else:
        st.info(text)


def render_feature_card(title, description, button_label, target_page, icon="⚽"):
    st.markdown(
        f"""
        <div style="border: 1px solid #e5e7eb; border-radius: 18px; padding: 1rem; background: linear-gradient(135deg, #ffffff, #f8fbff); box-shadow: 0 8px 20px rgba(15,23,42,0.08); min-height: 170px;">
          <div style="font-size: 0.9rem; color: #2563eb; font-weight: 700; margin-bottom: 0.35rem;">{icon}</div>
          <div style="font-size: 1.15rem; font-weight: 800; color: #111827; margin-bottom: 0.35rem;">{title}</div>
          <div style="font-size: 0.95rem; color: #475569; line-height: 1.4; margin-bottom: 0.8rem;">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(button_label, key=f"feature_{target_page}", use_container_width=True, type="primary"):
        st.session_state["current_page"] = target_page
        try:
            st.rerun()
        except Exception:
            pass


def render_metric_cards(scores):
    cols = st.columns(len(scores))
    for col, (label, value) in zip(cols, scores.items()):
        col.metric(label, value)


def render_player_profile_card(player, profile=None):
    st.markdown(
        """
        <div style="border: 1px solid #e5e7eb; border-radius: 18px; padding: 1rem; background: white; box-shadow: 0 8px 16px rgba(15,23,42,0.06);">
          <div style="font-size: 0.86rem; color: #2563eb; text-transform: uppercase; letter-spacing: 0.18em;">선수 프로필</div>
          <div style="font-size: 1.15rem; font-weight: 800; color: #111827;">{name}</div>
          <div style="color: #475569; font-size: 0.95rem;">{club} · {position}</div>
        </div>
        """.format(
            name=safe_text(player.get('name'), '선수 미지정'),
            club=safe_text(player.get('current_club_name') or profile.get('club') if profile else None, '-'),
            position=safe_text(player.get('position') or profile.get('position') if profile else None, '-'),
        ),
        unsafe_allow_html=True,
    )


def apply_theme():
    st.markdown(
        """
        <style>
        .stApp { background: linear-gradient(180deg, #f8fbff 0%, #f4f7fb 100%); }
        .stAlert, .stMarkdown, .stDataFrame, .block-container { color: #111827; }
        .scout-panel { border: 1px solid #dbe4ef; border-radius: 16px; padding: 0.9rem 1rem; background: white; box-shadow: 0 8px 18px rgba(15,23,42,0.06); margin-bottom: 0.8rem; }
        .badge-row { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 0.45rem; }
        .scout-badge { display: inline-flex; align-items: center; border-radius: 999px; padding: 0.25rem 0.55rem; background: #eff6ff; color: #1d4ed8; font-size: 0.82rem; font-weight: 700; }
        .section-note { border-left: 4px solid #38bdf8; padding: 0.55rem 0.75rem; background: #eff6ff; border-radius: 8px; color: #0f172a; }
        .warning-note { border-left: 4px solid #f59e0b; padding: 0.55rem 0.75rem; background: #fff7ed; border-radius: 8px; color: #92400e; }
        .report-block { border: 1px solid #dbe4ef; border-radius: 18px; padding: 0.9rem; background: white; box-shadow: 0 8px 18px rgba(15,23,42,0.06); margin-bottom: 0.9rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )
