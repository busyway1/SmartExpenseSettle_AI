"""
문서유형 AI 분류 프롬프트
"""

def get_document_type_classification_prompt(text: str) -> str:
    return f"""
다음 텍스트는 무역/회계 관련 문서의 한 페이지 또는 전체 내용입니다.

아래 문서 유형 중에서 가장 적합한 유형을 한글로 정확히 골라주세요:
- 수출신고필증
- 세금계산서
- 인보이스
- BL
- 이체확인증
- Packing List
- 미분류

📋 문서 유형별 고유 키워드
1. 수출신고필증
수출신고필증 - 문서 제목에서 직접 확인
신고번호 - 수출신고 고유 번호 필드
적재항 - 수출 관련 항구 정보

2. 세금계산서
세금계산서 - 문서 제목
부가가치세 - 세금계산서 특유 항목
공급가액 - 세금계산서 필수 항목

3. 인보이스
INVOICE - 기본 인보이스
PRO FORMA INVOICE - 견적서 성격의 인보이스
- 'COMMERCIAL INVOICE'는 인보이스가 아닙니다.

4. BL
BILL OF LADING,Bill of Lading, Way Bill, B/L- 선하증권 영문명 (문서 제목)
SHIPPER - 화주(송하인)
CONSIGNEE - 수하인

5. 이체확인증
이체확인증, 이체확인서, 입출금내역 명세서, 이체결과리스트, 이체결과확인서, 무통장단체입금확인서, 확인증 - 문서 제목
송금인 - 송금하는 사람
수취인, 받는분, 받으시는분 - 받는 사람

6. Packing List
PACKING LIST - 문서 제목

문서 내용:
{text}

정답 예시: \"Packing List\"
반드시 위 목록 중 하나만, 추가 설명 없이 한글로만 답변하세요.
""" 