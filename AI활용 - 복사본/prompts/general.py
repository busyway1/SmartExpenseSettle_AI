"""
일반 문서 분석 프롬프트
"""

def get_general_prompt(text: str, doc_type: str, file_name: str = "", page_number: int = None) -> str:
    """일반 문서 분석 프롬프트 생성"""
    base_prompt = f"""
다음은 {doc_type} 문서입니다. 이는 개별 문서이므로 해당 문서에서만 정보를 추출해주세요.

문서 내용:
{text}

"""
    
    # 페이지 번호 정보 추가
    page_info = f"**현재 페이지 번호: {page_number}**" if page_number is not None else ""
    
    return base_prompt + f"""
이 {doc_type}에서 중요한 정보를 추출해주세요. 이는 개별 문서이므로 이 문서에만 있는 정보를 추출해주세요:

{page_info}

- 문서 번호
- 날짜
- 관련 회사 정보
- 금액 정보
- 품목 정보
- 파일명: "{file_name}"
- 페이지번호: {page_number if page_number is not None else "실제 파일의 페이지 번호"}
- 기타 중요 정보

JSON 형태로 정리해주세요.""" 