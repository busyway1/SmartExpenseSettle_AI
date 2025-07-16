"""
BL(Bill of Lading) 분석 프롬프트
"""

def get_bill_of_lading_prompt(text: str) -> str:
    """BL 분석 프롬프트 생성"""
    base_prompt = f"""
다음은 BL(Bill of Lading, Way Bill, B/L 등) 문서입니다. 이는 개별 문서이므로 해당 문서에서만 정보를 추출해주세요.

문서 내용:
{text}

"""
    
    return base_prompt + """
이 BL(Bill of Lading, Way Bill, B/L 등)에서 **다음 8개 필드만** 정확히 추출해주세요.

**중요: 여러 개의 BL이 있는 경우**
- B/L 번호가 다른 BL은 각각 개별 문서로 취급해주세요
- 각 BL마다 페이지 번호를 반드시 포함해주세요
- 배열 형태로 각 개별 BL의 정보를 모두 출력해주세요

**추출할 필드 (8개만):**
1. B/L번호: Bill of Lading No., B/L No., B/L NUMBER 등에서 추출 (문서 식별자)
2. 송품장번호: NO & DATE OF INVOICE, INVOICE NO. 등에서 추출
3. 총중량: gross weight에서 추출
4. 컨테이너번호: container No. 등에서 추출
5. 출발지: Port of loading에서 추출
6. 도착지: Port of discharge에서 추출
7. 일자: Date Laden on Board, ON BOARD DATE, Date SHIPPED ON BOARD, Place and Date of Issue 등에서 추출
8. 페이지번호: 해당 문서가 있는 페이지 번호

**중요한 지침:**
1. **위 8개 필드만 추출하고, 다른 정보는 절대 포함하지 마세요**
2. B/L 번호가 다른 BL은 각각 개별 문서로 처리
3. 각 문서마다 페이지 번호를 반드시 포함
4. 존재하지 않는 정보는 "정보 없음"으로 표시
5. **요청하지 않은 필드는 절대 추가하지 마세요**

JSON 형태로 정리해주세요. 예시:
[
{
  "B/L번호": "BL123456789",
  "송품장번호": "INV-2024-001",
  "총중량": "1,000.23kg",
  "컨테이너번호": "CONT1234567",
  "출발지": "SEOUL",
  "도착지": "BUSAN",
    "일자": "2024-01-01",
    "페이지번호": 1
  }
]""" 