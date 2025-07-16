"""
BL(Bill of Lading) 분석 프롬프트
"""

def get_bill_of_lading_prompt(text: str, file_name: str = "", page_number: int = None) -> str:
    """BL 분석 프롬프트 생성"""
    base_prompt = f"""
다음은 BL(Bill of Lading, Way Bill, B/L 등) 문서입니다. 이는 개별 문서이므로 해당 문서에서만 정보를 추출해주세요.

문서 내용:
{text}

"""
    
    # 페이지 번호 정보 추가
    page_info = f"**현재 페이지 번호: {page_number}**" if page_number is not None else ""
    
    return base_prompt + f"""
이 BL(Bill of Lading, Way Bill, B/L 등)에서 **다음 9개 필드만** 정확히 추출해주세요.

{page_info}

**중요: 여러 개의 BL이 있는 경우**
- B/L 번호를 기준으로 번호가 다른 BL은 각각 개별 문서로 취급해주세요
- 배열 형태로 각 개별 BL의 정보를 모두 출력해주세요

**중요: 여러 페이지에 걸친 하나의 B/L 처리**
- 만약 연속된 여러 페이지 중, 첫 번째(또는 중간) 페이지에 B/L 번호가 없고,  
  다음(또는 이전) 페이지에 B/L 번호가 등장한다면,  
  해당 B/L 번호를 B/L 번호가 없는 페이지에도 동일하게 적용하여  
  하나의 B/L 문서로 묶어주세요.
- 즉, 연속된 페이지에서 B/L 번호가 일부 페이지에만 있을 경우,  
  가장 가까운 페이지의 B/L 번호를 참고하여 같은 B/L로 간주합니다.
- 단, B/L 번호가 명확히 다르거나, 페이지가 연속적이지 않으면 별도 문서로 처리하세요.
  [예시] 1페이지: B/L 번호 없음, 2페이지: B/L 번호 12345 → 두 페이지 모두 B/L 번호 12345로 묶어서 하나의 문서로 처리

**추출할 필드 (9개만):**
1. B/L 번호: Bill of Lading No., B/L No., B/L NUMBER 등으로 식별됨.
2. 송품장번호: NO & DATE OF INVOICE, INVOICE NO. 등으로 식별됨.
3. 출발지: Port of loading 
4. 도착지: Port of discharge 
5. 총중량: gross weight 
6. 페이지번호: {page_number if page_number is not None else "실제 파일의 페이지 번호 (예: 1, 2, 3...)"}
7. 컨테이너번호: container No. (보통 Container and Seal No. 로 함께 기재된 경우 '/' 의 구분자로 Seal No.와 구분할 수 있음.)
8. 일자: Date Laden on Board, ON BOARD DATE, Date SHIPPED ON BOARD, Place and Date of Issue 등으로 식별됨. YYYY-MM-DD 형식으로 추출해주세요.
9. 파일명: "{file_name}"

**중요한 지침:**
1. **위 9개 필드만 추출하고, 다른 정보는 절대 포함하지 마세요**
2. B/L 번호가 다른 BL은 각각 개별 문서로 처리
3. 각 문서마다 페이지 번호를 반드시 포함 (실제 파일의 페이지 번호)
4. 존재하지 않는 정보는 "정보 없음"으로 표시
5. **요청하지 않은 필드는 절대 추가하지 마세요**

JSON 형태로 정리해주세요. 예시:
[
{{
  "B/L번호": "BL123456789",
  "송품장번호": "INV-2024-001",
  "총중량": "1,000.23kg",
  "컨테이너번호": "CONT1234567",
  "출발지": "SEOUL",
  "도착지": "BUSAN",
  "일자": "2024-01-01",
  "파일명": "{file_name}",
  "페이지번호": {page_number if page_number is not None else 1}
  }}
]""" 