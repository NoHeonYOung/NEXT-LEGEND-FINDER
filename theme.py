import streamlit as st


def apply_theme():
    """Dark Scouting Cockpit 테마 CSS를 적용한다."""
    st.markdown(
        """
        <style>
        .stApp {
            background: #07111F;
            color: #F4F7FA;
        }
        section[data-testid="stSidebar"] {
            background: #0B1220;
            border-right: 1px solid rgba(255, 255, 255, 0.10);
        }
        h1, h2, h3 {
            color: #F4F7FA;
            letter-spacing: 0;
        }
        p, li, span, div {
            color: inherit;
        }
        div[data-testid="stMetric"] {
            background: #102335;
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 8px;
            padding: 14px 16px;
            box-shadow: 0 8px 22px rgba(0, 0, 0, 0.35);
        }
        div[data-testid="stMetric"] label,
        div[data-testid="stMetricLabel"] {
            color: #A8B3C5 !important;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 8px 22px rgba(0, 0, 0, 0.3);
        }
        .scout-panel {
            background: #102335;
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 8px;
            padding: 18px;
            margin: 10px 0 16px 0;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
        }
        .dark-panel {
            background: #0B1220;
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 10px;
            padding: 16px 18px;
            margin: 10px 0 16px 0;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
        }
        .panel-secondary {
            background: #123047;
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 10px;
            padding: 14px 16px;
            margin: 8px 0;
        }
        .profile-card {
            display: grid;
            grid-template-columns: 150px 1fr 260px;
            gap: 22px;
            align-items: center;
        }
        .profile-photo {
            width: 150px;
            height: 150px;
            object-fit: cover;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.10);
            background: #102335;
        }
        .stat-box {
            background: #0B1220;
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 8px;
            padding: 12px;
            margin: 6px 0;
        }
        .badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        .scout-badge {
            display: inline-flex;
            border-radius: 999px;
            padding: 5px 10px;
            background: #0E4D45;
            border: 1px solid #2A9D8F;
            color: #F4F7FA;
            font-size: 0.88rem;
            white-space: nowrap;
        }
        .muted {
            color: #A8B3C5;
            font-size: 0.93rem;
        }
        .section-note {
            color: #F4F7FA;
            background: #0E4D45;
            border-left: 4px solid #2A9D8F;
            border-radius: 8px;
            padding: 13px 15px;
            margin: 8px 0 14px 0;
            line-height: 1.55;
        }
        .warning-note {
            color: #07111F;
            background: #F2C94C;
            border-left: 4px solid #F2C94C;
            border-radius: 8px;
            padding: 13px 15px;
            margin: 8px 0 14px 0;
            line-height: 1.55;
        }
        .report-block {
            background: #102335;
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-left: 4px solid #2A9D8F;
            border-radius: 8px;
            padding: 16px 18px;
            margin-bottom: 12px;
            line-height: 1.58;
            box-shadow: 0 8px 22px rgba(0, 0, 0, 0.3);
        }
        @media (max-width: 900px) {
            .profile-card {
                grid-template-columns: 1fr;
            }
        }
        .app-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            background: linear-gradient(135deg, #102335 0%, #07111F 100%);
            color: #F4F7FA;
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 10px;
            padding: 14px 20px;
            margin: 0 0 18px 0;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        }
        .app-header-brand {
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            color: #48C78E;
        }
        .app-header-page {
            font-size: 0.9rem;
            color: #A8B3C5;
            margin-top: 2px;
        }
        .app-header-status {
            font-size: 0.92rem;
            color: #A8B3C5;
            text-align: right;
        }
        .app-header-status b {
            color: #F4F7FA;
        }
        .home-hero {
            text-align: center;
            margin: 4px 0 18px 0;
        }
        .home-hero p {
            color: #A8B3C5;
            font-size: 1.05rem;
            margin-top: 6px;
        }
        .data-mode-badge {
            display: inline-flex;
            border-radius: 999px;
            padding: 3px 10px;
            font-size: 0.82rem;
            font-weight: 600;
            margin-top: 4px;
            white-space: nowrap;
        }
        .data-mode-matched {
            background: #0E4D45;
            color: #48C78E;
        }
        .data-mode-tm {
            background: #123047;
            color: #7FB3FF;
        }
        .data-mode-fm {
            background: #3A2F0B;
            color: #F2C94C;
        }
        .data-mode-manual {
            background: #2A1F47;
            color: #C9A8FF;
        }
        .data-mode-none {
            background: #123047;
            color: #A8B3C5;
        }
        .nav-chip-row {
            margin-bottom: 6px;
        }
        div[data-testid="stButton"] > button {
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, 0.10);
        }
        .next-step-title {
            color: #48C78E;
            font-weight: 700;
            font-size: 1.0rem;
            margin: 4px 0 10px 0;
        }
        .workflow-step {
            background: #102335;
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 10px;
            padding: 14px;
            margin-bottom: 10px;
            box-shadow: 0 6px 18px rgba(0, 0, 0, 0.3);
        }
        .workflow-step .step-no {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 26px;
            height: 26px;
            border-radius: 50%;
            background: #2A9D8F;
            color: #07111F;
            font-weight: 700;
            font-size: 0.85rem;
            margin-right: 8px;
        }
        .data-mode-card {
            background: #102335;
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-left: 4px solid #2A9D8F;
            border-radius: 10px;
            padding: 14px 16px;
            margin-bottom: 10px;
            box-shadow: 0 6px 18px rgba(0, 0, 0, 0.3);
        }
        .data-mode-card.active {
            border-left-color: #48C78E;
            background: #123047;
        }
        .hero-cta {
            background: linear-gradient(135deg, #0E4D45 0%, #07111F 100%);
            color: #F4F7FA;
            border-radius: 12px;
            padding: 22px 24px;
            margin: 4px 0 18px 0;
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.45);
        }
        .hero-cta h1 {
            color: #F4F7FA;
            margin: 0 0 6px 0;
        }
        .hero-cta p {
            color: #A8B3C5;
            font-size: 1.0rem;
            margin: 0;
        }

        /* ----- 본문 폭 / 패널 간격 ----- */
        .main .block-container {
            max-width: 1180px;
            padding-top: 1.6rem;
            padding-bottom: 3rem;
        }

        /* ----- 버튼 대비 개선 (white pill 버튼 가독성 문제 해결) ----- */
        div[data-testid="stButton"] > button,
        div[data-testid="stFormSubmitButton"] > button,
        div[data-testid="stDownloadButton"] > button {
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, 0.16);
            background: #102335;
            color: #F4F7FA !important;
            font-weight: 600;
            transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
        }
        div[data-testid="stButton"] > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover,
        div[data-testid="stDownloadButton"] > button:hover {
            border-color: #2A9D8F;
            color: #48C78E !important;
            background: #123047;
        }
        div[data-testid="stButton"] > button p,
        div[data-testid="stFormSubmitButton"] > button p,
        div[data-testid="stDownloadButton"] > button p {
            color: inherit;
        }
        /* primary action: teal/green filled */
        button[kind="primary"],
        button[kind="primaryFormSubmit"] {
            background: #2A9D8F !important;
            border: 1px solid #2A9D8F !important;
            color: #07111F !important;
            font-weight: 700;
        }
        button[kind="primary"]:hover,
        button[kind="primaryFormSubmit"]:hover {
            background: #48C78E !important;
            border-color: #48C78E !important;
            color: #07111F !important;
        }
        /* secondary action: dark panel with border */
        button[kind="secondary"],
        button[kind="secondaryFormSubmit"] {
            background: #102335 !important;
            border: 1px solid rgba(255, 255, 255, 0.18) !important;
            color: #F4F7FA !important;
        }
        /* active nav chip (primary + disabled) - tactical green highlight */
        button[kind="primary"]:disabled,
        button[kind="primaryFormSubmit"]:disabled {
            background: #0E4D45 !important;
            border: 1px solid #2A9D8F !important;
            color: #48C78E !important;
            opacity: 1 !important;
            font-weight: 700;
        }
        /* generic disabled button: dark but readable */
        button:disabled,
        button[disabled] {
            background: #0B1220 !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            color: #7C8AA0 !important;
            opacity: 1 !important;
        }

        /* ----- 입력 위젯 대비 개선 ----- */
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] {
            background: #0B1220 !important;
            color: #F4F7FA !important;
            border: 1px solid rgba(255, 255, 255, 0.14) !important;
        }
        div[data-baseweb="select"] svg {
            fill: #A8B3C5;
        }
        ul[data-testid="stSelectboxVirtualDropdown"] {
            background: #102335 !important;
        }

        /* ----- 레이블 / 라디오 / expander 대비 개선 ----- */
        div[data-testid="stWidgetLabel"] label,
        div[data-testid="stWidgetLabel"] p,
        .stRadio label,
        .stCheckbox label {
            color: #F4F7FA !important;
        }
        div[data-testid="stExpander"] {
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 8px;
            background: #0B1220;
        }
        div[data-testid="stExpander"] summary {
            color: #F4F7FA !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
