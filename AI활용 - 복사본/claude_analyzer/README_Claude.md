# Claude AI 기반 문서 분석기

이 프로젝트는 Anthropic의 Claude Sonnet 4 모델을 사용하여 문서를 분석하는 AI 시스템입니다.

## 📁 폴더 구조

```
claude_analyzer/
├── __init__.py                 # Python 패키지 초기화
├── claude_ai_analyzer.py       # 메인 분석기 클래스
├── claude_example_usage.py     # 사용 예제
├── claude_example.py           # 기본 Claude API 예제
├── run_example.py              # 실행 스크립트
├── requirements_claude.txt     # 의존성 파일
└── README_Claude.md           # 이 파일
```

## 주요 특징

- **Claude Sonnet 4 모델 사용**: 최신 Claude 모델을 활용한 정확한 문서 분석
- **기존 프롬프트 시스템 통합**: prompts 폴더의 검증된 프롬프트들을 그대로 활용
- **다양한 문서 형식 지원**: PDF, 이미지 파일 등
- **OCR 기능**: 스캔된 문서에서 텍스트 추출
- **문서 타입 자동 분류**: 세금계산서, 인보이스, 송금증, 수출신고필증, BL 등
- **비동기/동기 처리**: 대용량 문서 처리 최적화
- **이미지 개선**: OCR 정확도 향상을 위한 이미지 전처리

## 설치 방법

1. **가상환경 생성 및 활성화**
   ```bash
   python -m venv claude-env
   claude-env\Scripts\activate  # Windows
   source claude-env/bin/activate  # Linux/Mac
   ```

2. **의존성 설치**
   ```bash
   pip install -r requirements_claude.txt
   ```

3. **API 키 설정**
   ```bash
   # 환경변수로 설정
   set ANTHROPIC_API_KEY=your-api-key-here  # Windows
   export ANTHROPIC_API_KEY=your-api-key-here  # Linux/Mac
   ```

## 사용 방법

### 기본 사용법

```python
import asyncio
from claude_ai_analyzer import ClaudeAIAnalyzer

async def analyze_document():
    # 분석기 초기화
    analyzer = ClaudeAIAnalyzer(api_key="your-api-key")
    
    # 문서 분석
    result = await analyzer.analyze_document_async("path/to/document.pdf")
    
    if result.get("success"):
        print("분석 결과:", result['analysis'])
    else:
        print("오류:", result.get('error'))

# 실행
asyncio.run(analyze_document())
```

### 동기 방식 사용

```python
from claude_ai_analyzer import ClaudeAIAnalyzer

# 분석기 초기화
analyzer = ClaudeAIAnalyzer(api_key="your-api-key")

# 문서 분석
result = analyzer.analyze_document("path/to/document.pdf")

if result.get("success"):
    print("분석 결과:", result['analysis'])
else:
    print("오류:", result.get('error'))
```

## 지원하는 문서 타입

- **세금계산서**: 승인번호, 공급가액, 부가세액, 공급자상호, 작성일자 등 9개 필드 추출
- **인보이스**: 업체명, 송품장번호, B/L번호, 출발지, 도착지, 품목정보 등 14개 필드 추출
- **송금증**: 금액, 업체명, 일자 등 5개 필드 추출
- **수출신고필증**: 신고번호, 송품장번호, 총중량, 순중량, 컨테이너번호 등 12개 필드 추출
- **BL (Bill of Lading)**: B/L번호, 송품장번호, 출발지, 도착지, 총중량 등 9개 필드 추출
- **기타**: 일반 문서 분석

## 고급 기능

### 이미지 개선 옵션

```python
# 고급 OpenCV 이미지 개선 사용
analyzer = ClaudeAIAnalyzer(
    api_key="your-api-key",
    use_advanced_opencv=True
)
```

### 텍스트 추출만 수행

```python
# PDF에서 텍스트만 추출
text = analyzer.extract_text_from_file("document.pdf")
print("추출된 텍스트:", text)

# 이미지에서 텍스트 추출 (OCR)
text = analyzer._extract_text_from_image("image.png")
print("OCR 결과:", text)
```

## 예제 실행

```bash
python claude_example_usage.py
```

## 주의사항

1. **API 키 보안**: API 키를 코드에 직접 하드코딩하지 마세요
2. **속도 제한**: Anthropic API의 속도 제한을 고려하여 사용하세요
3. **파일 크기**: 대용량 파일의 경우 처리 시간이 오래 걸릴 수 있습니다
4. **이미지 품질**: OCR 정확도는 원본 이미지 품질에 따라 달라집니다

## 기존 GPT-4o 버전과의 차이점

| 기능 | GPT-4o 버전 | Claude 버전 |
|------|-------------|-------------|
| 모델 | GPT-4o | Claude Sonnet 4 |
| API 클라이언트 | OpenAI | Anthropic |
| 이미지 처리 | Vision API | Claude Vision |
| 프롬프트 시스템 | 동일한 prompts 폴더 사용 | 동일한 prompts 폴더 사용 |
| 문서 타입 분류 | 동일한 프롬프트 사용 | 동일한 프롬프트 사용 |
| 비용 | OpenAI 요금 | Anthropic 요금 |
| 성능 | GPT-4o 수준 | Claude Sonnet 4 수준 |

## 프롬프트 시스템

이 Claude 분석기는 기존 GPT-4o 버전과 동일한 프롬프트 시스템을 사용합니다:

### 📁 프롬프트 파일 구조
```
prompts/
├── document_type_classification.py  # 문서 타입 분류
├── tax_invoice.py                   # 세금계산서 분석
├── invoice.py                       # 인보이스 분석
├── bill_of_lading.py               # BL 분석
├── transfer_receipt.py             # 송금증 분석
├── export_declaration.py           # 수출신고필증 분석
└── prompt_manager.py               # 프롬프트 관리
```

### 🔄 프롬프트 재사용
- **문서 타입 분류**: `get_document_type_classification_prompt()`
- **세금계산서**: `get_tax_invoice_prompt()`
- **인보이스**: `get_invoice_prompt()`
- **BL**: `get_bill_of_lading_prompt()`
- **송금증**: `get_transfer_receipt_prompt()`
- **수출신고필증**: `get_export_declaration_prompt()`

### ✨ 장점
- **일관성**: GPT-4o와 동일한 분석 결과 보장
- **유지보수**: 프롬프트 수정 시 한 곳에서만 변경
- **검증됨**: 실제 사용을 통해 검증된 프롬프트 사용
- **확장성**: 새로운 문서 타입 추가 시 기존 구조 활용

## 문제 해결

### 일반적인 오류

1. **API 키 오류**
   ```
   경고: Anthropic API 키가 설정되지 않았습니다.
   ```
   → 환경변수 또는 직접 API 키를 설정하세요

2. **속도 제한 오류**
   ```
   속도 제한 도달. X초 후 재시도...
   ```
   → 자동으로 재시도되므로 잠시 기다리세요

3. **파일 읽기 오류**
   ```
   파일 읽기 오류: [Errno 2] No such file or directory
   ```
   → 파일 경로가 올바른지 확인하세요

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 