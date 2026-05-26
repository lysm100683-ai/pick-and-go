# travel_logic/exceptions.py
"""
Travel Logic 커스텀 예외 클래스
"""


class InsufficientPlacesError(Exception):
    """
    Phase 1 필터링 후 관광지 후보 수가 일정 생성에 필요한 최소 수량에 미달할 때 발생.

    속성:
        city         : 여행 목적지 도시명
        available    : 필터 통과 후 확보된 관광지 수
        required     : 일정 생성에 필요한 최소 관광지 수 (= 여행 일수)
        budget_level : 현재 적용된 예산 수준 ('저' | '중' | '고')
        relaxed      : 이미 조건 완화를 한 번 시도했는지 여부
    """

    def __init__(
        self,
        city: str,
        available: int,
        required: int,
        budget_level: str = '중',
        relaxed: bool = False,
    ):
        self.city = city
        self.available = available
        self.required = required
        self.budget_level = budget_level
        self.relaxed = relaxed  # True이면 완화 재시도 불가 안내
        super().__init__(
            f"장소 부족: '{city}'에서 조건에 맞는 관광지 {available}개 확보 (최소 {required}개 필요)"
        )
