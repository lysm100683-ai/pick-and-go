# Pick & Go — DB부 상세 구조도 (BPMN 2.0)

> **기준일**: 2026년 4월  
> **표기법**: BPMN 2.0 국제 표준  
> **색상**: 품화 주황=신규추가 | 산호 빨갅=방식변경 | 파란테두리=신규레이어 | 점선=미구현/폐기

---

## 설계도

![Pick & Go DB부 BPMN 2.0 설계도](C:/Users/galsh/.gemini/antigravity/brain/a98c86c4-8a4c-4b45-b97c-99443d10c515/db_design_bpmn_standard_1775188305521.png)

---

## 레인별 설명

### 👤 사용자 입력
사용자가 입력하는 여행 조건 (도시, 기간, 이동수단, 동반자, 스타일, 숙소 별점, 예산)이 일정 생성 엔진으로 전달됩니다.

### 🗓 일정 생성 엔진 (itinerary_generator.py)
| 단계 | 함수 | 역할 |
|------|------|------|
| ① | `db_service.ensure_data_exists()` | DB에 장소 데이터 있는지 확인, 없으면 자동 수집 요청 |
| ② | `backend.get_places(city)` | 여행 DB에서 장소 목록 불러오기, 유효 좌표 필터링 |
| ③ | 내부 분류 로직 | 관광지 / 식당 / 카페 / 숙소로 분류 |
| ④ | `_build_themes()` | 사용자 스타일 기반으로 2~4개 테마 자동 결정 |
| ⑤ | `_generate_for_theme()` | 테마별 일차 일정 조합 후 JSON 반환 |

### 📍 장소 수집 흐름
| 단계 | 함수 | 역할 |
|------|------|------|
| 수집 요청 | Streamlit DB업데이트 버튼 | 관리자가 수동으로 수집 시작 |
| API 호출 | `fetch_google()` + `fetch_kakao()` | 병렬로 장소 데이터 수집 |
| 🟠 임시 버퍼 | `_buffer_place()` → `_temp_data_buffer` | 메모리에 모으기 (좌표 0.0 자동 제외) |
| 🔴 일괄 저장 | `save_bulk_data()` — ON CONFLICT | 한 번에 DB 저장, rating·img_url만 갱신 |
| 예정 | `fetch_tourapi()` | 한국관광공사 API (구현 예정) |
| Phase4 | `fetch_amadeus()` | 항공·숙박 예약 (Phase 4 예정) |

### 🚗 이동시간 처리 흐름
| 단계 | 함수 | 역할 |
|------|------|------|
| 계산 요청 | `optimization_service.select_next_place()` | 현재 위치에서 후보 Top10 선정 |
| 캐시 조회 | `get_movement_cache()` | DB에서 캐시된 이동시간 검색 |
| 캐시 HIT | — | 즉시 반환 (API 호출 없음) |
| 캐시 MISS | Kakao/Google Directions API | 실시간 호출 (국내=Kakao, 해외=Google) |
| 캐시 저장 | `save_movement_cache()` | 중복이면 스킵 |
| Cost 계산 | `W_time × 이동시간 + W_score × (100 - 장소점수)` | 최소 Cost 장소 선택 |

### 🗃 스키마 관리 (Alembic) — 🔵 신규 도입
- **현재 버전**: `6d14ff079885 (head)`
- **변경 절차**: `alembic revision --autogenerate -m '설명'` → `alembic upgrade head`
- **롤백**: `alembic downgrade -1`
