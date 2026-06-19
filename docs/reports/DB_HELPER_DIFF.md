# DB_HELPER_DIFF.md
# app.py 9번 줄 services.db import vs app.py 내부 DB 헬퍼 정의 비교

이 문서는 app.py 9번 줄의
`from services.db import (get_prospect_diagnostics, get_scouting_notes, insert_scouting_note,
query_df, query_one, show_db_error, table_count, preview_table, search_players,
search_players_with_modes, get_distinct_positions, get_player, get_profile_by_player_id,
get_profile_by_name, get_player_profile, money)` (16개 이름)이
app.py 내부 자체 정의(49~501줄)에 의해 전부 shadow되어 dead import인지 검증한 결과다.

비교는 `ast`로 양쪽 함수 정의를 파싱해 소스 텍스트를 **바이트 단위로 비교**했다.

## 비교 결과 (16개 import 이름)

| 함수명 | app.py 정의 존재 | services/db.py 정의 존재 | SQL/반환 컬럼 차이 | profile_id 포함 | 통합 가능 여부 |
|---|---|---|---|---|---|
| query_df | O (64~72) | O (38~46) | 없음 (100% 동일) | n/a | **가능** |
| query_one | O (75~86) | O (49~60) | 없음 (100% 동일) | n/a | **가능** |
| show_db_error | O (105~126) | O (79~99) | 없음 (100% 동일) | n/a | **가능** |
| table_count | O (128~133) | O (102~107) | 없음 (100% 동일, TABLES 상수도 양쪽 동일) | n/a | **가능** |
| preview_table | O (136~141) | O (110~115) | 없음 (100% 동일) | n/a | **가능** |
| search_players | O (144~189) | O (118~163) | 없음 (100% 동일, `pp.profile_id` 포함) | O | **가능** |
| search_players_with_modes | O (192~280) | O (166~254) | 없음 (100% 동일) | O | **가능** |
| get_distinct_positions | O (283~295) | O (257~269) | 없음 (100% 동일) | n/a | **가능** |
| get_player | O (298~306) | O (272~280) | 없음 (100% 동일) | n/a | **가능** |
| get_profile_by_player_id | O (309~317) | O (317~325) | 없음 (100% 동일) | n/a | **가능** |
| get_profile_by_name | O (320~329) | O (328~337) | 없음 (100% 동일) | n/a | **가능** |
| get_player_profile | O (358~371) | O (340~353) | 없음 (100% 동일) | n/a | **가능** |
| insert_scouting_note | O (374~406) | O (380~412) | 없음 (100% 동일) | O | **가능** |
| get_scouting_notes | O (409~427) | O (415~433) | 없음 (100% 동일) | O | **가능** |
| get_prospect_diagnostics | O (430~491) | O (436~497) | 없음 (100% 동일) | n/a | **가능** |
| money | O (494~501) | O (500~507) | 없음 (100% 동일) | n/a | **가능** |

**결론: 9번 줄의 import는 16개 전부 app.py 자체 정의에 의해 100% shadow되는 완전한 dead import였다.**
단, services/db.py 쪽 구현이 app.py active 정의와 한 글자도 다르지 않으므로(전부 SAME),
**app.py 내부 정의 16개를 삭제하고 services.db import를 active로 전환**하는 것이
가장 안전한 정리 방법이다. SQL/반환 컬럼/profile_id 동기화는 이미 완료된 상태라
services/db.py 쪽 추가 수정은 필요 없다.

## 추가로 함께 정리 가능한 항목 (위 16개와 연쇄적으로 dead가 되는 것들)

| 항목 | app.py 정의 존재 | services/db.py 정의 존재 | 비교 결과 | 처리 |
|---|---|---|---|---|
| load_db_url | O (49~56) | O (23~30) | 100% 동일 | app.py 자체 정의 삭제 시, query_df/query_one/execute_one(모두 삭제 대상)에서만 쓰이므로 **dead → 삭제** |
| get_connection | O (59~61) | O (33~35) | 100% 동일 | 위와 동일 이유로 **dead → 삭제** |
| execute_one | O (89~102) | O (63~76) | 100% 동일 | app.py에서 insert_scouting_note(삭제 대상)에서만 호출 → **dead → 삭제** (services.db.insert_scouting_note은 services/db.py 자체 execute_one을 쓰므로 영향 없음) |
| TABLES (상수) | O (25~32) | O (13~20) | 100% 동일 (clubs/players/appearances/player_valuations/player_profiles/scouting_notes) | app.py에서 table_count/preview_table(둘 다 삭제 대상)에서만 사용 → **dead → 삭제**. views/db_status.py는 이미 `from services.db import TABLES`를 사용 중이라 영향 없음 |

## app.py에만 있고 services/db.py에는 없는 함수 (절대 삭제 금지)

| 함수명 | 줄 | profile_id 포함 | 비고 |
|---|---|---|---|
| get_profile_by_name_nationality_position | 332~355 | O (반환 profile dict에 profile_id 포함) | `resolve_selected_player_context()`의 fallback profile matching에서 직접 호출됨 (536번 줄). services/db.py에는 동일 함수가 없음. **app.py에 그대로 유지.** 내부에서 사용하는 `query_one`은 16개 정리 후 9번 줄 import의 `query_one`(services.db, app.py 구현과 100% 동일)으로 자동 연결되므로 동작 변경 없음. |

## 선택 로직 관련 함수 (services/db.py에도 동일 이름이 있으나 app.py 버전이 다름 — 절대 손대지 않음)

`resolve_selected_player_context`/`selected_player_id`/`selected_profile_id`/`selected_entity_type`/
`selected_profile`/`selected_player`/`require_selected_player`/`show_selected_player_banner`는
app.py(504~651)와 services/db.py(510~589)에 **둘 다 존재하지만 구현이 다르다**
(app.py 버전은 `resolve_selected_player_context`의 fallback profile matching 로직을 포함).
이 6개 이름은 **9번 줄 import 목록에 포함되어 있지 않으므로** 충돌이 없고,
이번 세션에서는 **app.py 버전을 그대로 유지**한다 (DO NOT CHANGE 대상).

## 적용 계획 (Step A)

1. app.py에서 다음 16개 함수 정의를 삭제 (services.db import가 active가 됨):
   query_df, query_one, show_db_error, table_count, preview_table, search_players,
   search_players_with_modes, get_distinct_positions, get_player, get_profile_by_player_id,
   get_profile_by_name, get_player_profile, insert_scouting_note, get_scouting_notes,
   get_prospect_diagnostics, money
2. 연쇄적으로 dead가 되는 load_db_url, get_connection, execute_one, TABLES 상수도 함께 삭제.
3. get_profile_by_name_nationality_position(332~355)은 그대로 유지.
4. compileall + test_state_refactor.py + test_analysis_helpers_split.py로 회귀 확인.
