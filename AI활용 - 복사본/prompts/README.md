# 프롬프트 모듈 (Prompts Module)

문서 유형별 AI 분석 프롬프트를 관리하는 모듈입니다.

## 📁 파일 구조

```
prompts/
├── __init__.py              # 모듈 초기화 파일
├── prompt_manager.py        # 프롬프트 통합 관리자
├── export_declaration.py    # 수출신고필증 프롬프트
├── tax_invoice.py          # 세금계산서 프롬프트
├── invoice.py              # 인보이스 프롬프트
├── bill_of_lading.py       # BL(Bill of Lading) 프롬프트
├── transfer_receipt.py     # 이체확인증 프롬프트
├── general.py              # 일반 문서 프롬프트
└── README.md               # 이 파일
```

## 🔧 사용법

### 1. 프롬프트 매니저 사용

```python
from prompts.prompt_manager import PromptManager

# 특정 문서 유형의 프롬프트 가져오기
prompt = PromptManager.get_prompt("수출신고필증", document_text)

# 지원되는 문서 유형 확인
supported_types = PromptManager.get_supported_document_types()
# ['수출신고필증', '세금계산서', '인보이스', 'BL', '이체확인증']

# 문서 유형 지원 여부 확인
is_supported = PromptManager.is_supported_document_type("세금계산서")
```

### 2. 개별 프롬프트 파일 사용

```python
from prompts.tax_invoice import get_tax_invoice_prompt
from prompts.invoice import get_invoice_prompt

# 세금계산서 프롬프트
tax_prompt = get_tax_invoice_prompt(document_text)

# 인보이스 프롬프트
invoice_prompt = get_invoice_prompt(document_text)
```

## 📋 지원 문서 유형

### 1. 수출신고필증 (`export_declaration.py`)
- **추출 필드**: 11개
- 신고번호, 송품장번호, 일자, 총중량, 순중량, 컨테이너번호, 출발지, 도착지, 세번부호, 란번호, 페이지번호

### 2. 세금계산서 (`tax_invoice.py`)
- **추출 필드**: 8개
- 승인번호, 공급가액, 부가세액, 공급자상호, 작성일자, 공급자등록번호, 공급받는자등록번호, 페이지번호

### 3. 인보이스 (`invoice.py`)
- **추출 필드**: 12개
- 업체명, 일자, 송품장번호, B/L번호, 출발지, 도착지, 총중량, 컨테이너번호, 페이지번호, 품목정보, 공급가액Total, 부가세액Total

### 4. BL (`bill_of_lading.py`)
- **추출 필드**: 8개
- B/L번호, 송품장번호, 총중량, 컨테이너번호, 출발지, 도착지, 일자, 페이지번호

### 5. 이체확인증 (`transfer_receipt.py`)
- **추출 필드**: 4개
- 금액, 업체명, 일자, 페이지번호

### 6. 일반 문서 (`general.py`)
- 기본적인 문서 정보 추출
- 문서 번호, 날짜, 회사 정보, 금액 정보, 품목 정보 등

## 🔄 프롬프트 수정 방법

### 개별 프롬프트 수정
각 문서 유형별 프롬프트 파일을 직접 수정하면 됩니다:

```python
# prompts/tax_invoice.py 수정
def get_tax_invoice_prompt(text: str) -> str:
    # 여기서 세금계산서 프롬프트 수정
    return "수정된 프롬프트 내용"
```

### 새로운 문서 유형 추가
1. 새로운 프롬프트 파일 생성 (예: `new_document_type.py`)
2. `prompt_manager.py`에 새로운 문서 유형 추가
3. `ai_analyzer.py`의 `_identify_single_page_type` 메서드에 키워드 추가

## 📝 프롬프트 작성 가이드

### 기본 구조
```python
def get_document_type_prompt(text: str) -> str:
    base_prompt = f"""
다음은 [문서유형] 문서입니다. 이는 개별 문서이므로 해당 문서에서만 정보를 추출해주세요.

문서 내용:
{text}

"""
    
    return base_prompt + """
[문서 유형별 상세 지침]

**추출할 필드:**
1. 필드명: 설명
2. 필드명: 설명
...

**중요한 지침:**
1. 지침 내용
2. 지침 내용
...
"""
```

### 주의사항
1. **필드명 일관성**: 각 문서 유형별로 동일한 필드명 사용
2. **JSON 형식**: AI가 JSON 형태로 응답하도록 명시
3. **에러 처리**: 정보가 없을 때 "정보 없음" 처리 방법 명시
4. **페이지 번호**: 각 문서마다 페이지 번호 포함 필수

## 🚀 확장성

이 모듈 구조를 통해:
- 새로운 문서 유형 쉽게 추가 가능
- 기존 프롬프트 개별 수정 가능
- 프롬프트 버전 관리 용이
- 테스트 및 검증 편리 