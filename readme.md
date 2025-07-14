# 🚀 Business Settlement PDF 분석 시스템

**AI 기반 무역문서 자동 파싱 및 데이터 추출 시스템**

## ✨ 주요 특징

### 🎯 **4단계 자동 폴백 엔진**
1. **🥇 Upstage Document Parse** - 0.6초/페이지, 93.48% TEDS 정확도, $0.01/페이지
2. **🥈 PyMuPDF** - 빠른 처리, 대용량 파일 최적화
3. **🥉 pdfplumber** - 정확한 테이블 추출, 복잡한 레이아웃 지원
4. **🔧 Tesseract OCR** - 이미지 기반 PDF 처리, 한국어+영어 지원

### 📊 **다중 파일 처리**
- 여러 PDF 파일 동시 처리 (병렬/순차 선택 가능)
- 단일 PDF 내 여러 문서 타입 혼재 처리
- 파일별 `results` 폴더 자동 생성 및 `[파일명].json` 저장

### 📋 **지원 문서 타입**
- **세금계산서** - 공급가액, 세액, 사업자번호 등
- **인보이스** - 품목, 금액, B/L번호, 컨테이너번호 등  
- **선하증권 (B/L)** - 선적항, 도착항, 선박정보 등
- **수출신고필증** - 신고번호, 세번, 목적국 등
- **이체확인증** - 송금정보, 승인번호, 계좌정보 등

---

## 🛠️ 설치 및 설정

### **1. 시스템 요구사항**
- **Python 3.13.5** (3.12도 지원)
- **OS**: Windows 10+, macOS 10.15+, Ubuntu 20.04+
- **메모리**: 최소 4GB RAM (권장 8GB+)

### **2. 의존성 설치**

**Windows:**
```bash
# Chocolatey 사용
choco install python --version=3.13.5
choco install tesseract poppler

# 또는 수동 설치
# Python: https://www.python.org/downloads/
# Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
# Poppler: https://blog.alivate.com.au/poppler-windows/
```

**macOS:**
```bash
# Homebrew 사용
brew install python@3.13 tesseract poppler

# Python 가상환경 설정
python3.13 -m venv venv
source venv/bin/activate
```

**Linux (Ubuntu/Debian):**
```bash
# 시스템 패키지 설치
sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-dev
sudo apt install -y tesseract-ocr tesseract-ocr-kor poppler-utils

# 가상환경 설정
python3.13 -m venv venv
source venv/bin/activate
```

### **3. Python 패키지 설치**
```bash
# 저장소 클론
git clone <your-repository-url>
cd Code_AI

# 가상환경 활성화
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows

# 의존성 설치
pip install -r requirements.txt
```

### **4. 환경 변수 설정**
```bash
# 환경 파일 생성
cp .env.example .env

# .env 파일 편집 (필수)
nano .env  # 또는 원하는 에디터 사용
```

**필수 설정:**
```bash
# Upstage API 키 설정 (필수)
UPSTAGE_API_KEY=up_your_upstage_api_key_here
```

**API 키 발급:** [Upstage Console](https://console.upstage.ai/api-keys)에서 무료 $10 크레딧으로 시작 가능

---

## 🚀 사용법

### **기본 사용법**
```bash
# 단일 파일 처리
python cli.py --files invoice.pdf

# 여러 파일 동시 처리  
python cli.py --files file1.pdf file2.pdf file3.pdf

# 특정 엔진 사용
python cli.py --files document.pdf --engine upstage

# 병렬 처리 (8개 워커)
python cli.py --files *.pdf --parallel --max-workers 8

# 상세 로그 출력
python cli.py --files document.pdf --verbose
```

### **고급 옵션**
```bash
# 엔진 상태 진단
python cli.py --diagnose

# 엔진 성능 테스트
python cli.py --files test.pdf --test-engines

# 특정 문서 타입 지정
python cli.py --files doc.pdf --type tax_invoice

# 순차 처리 (안전 모드)
python cli.py --files *.pdf --sequential
```

### **사용 가능한 옵션**

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--files, -f` | 처리할 PDF 파일들 (필수) | - |
| `--engine` | 사용할 엔진 (upstage/pymupdf/pdfplumber/tesseract) | upstage |
| `--type, -t` | 문서 타입 지정 (자동 감지 우선) | 자동감지 |
| `--parallel/--sequential` | 병렬/순차 처리 | 병렬 |
| `--max-workers` | 최대 워커 수 | 4 |
| `--verbose, -v` | 상세 로그 출력 | False |
| `--diagnose` | 엔진 진단 후 종료 | False |
| `--test-engines` | 엔진 성능 테스트 | False |

---

## 📊 결과 형식

### **출력 구조**
```
PDF파일위치/
├── results/
│   └── 파일명.json          # 구조화된 추출 결과
├── 원본파일.pdf
```

### **JSON 결과 예시**
```json
{
  "file_path": "/path/to/invoice.pdf",
  "file_name": "invoice",
  "primary_document_type": "tax_invoice",
  "status": "completed",
  "processing_duration_seconds": 2.3,
  "detected_documents": [
    {
      "document_type": "tax_invoice",
      "confidence": 0.95,
      "page_range": [1, 1],
      "key_indicators": ["세금계산서", "공급가액", "세액"],
      "extracted_data": {
        "tax_invoice_number": {
          "value": "INV-2025-001",
          "confidence": 0.9,
          "extraction_engine": "upstage",
          "page_number": 1
        },
        "supply_amount": {
          "value": 1000000,
          "confidence": 0.95,
          "extraction_engine": "upstage",
          "page_number": 1
        }
      }
    }
  ],
  "extraction_engines_used": ["upstage"],
  "primary_engine": "upstage"
}
```

---

## 🔧 엔진 성능 비교

| 엔진 | 속도 | 정확도 | 비용 | 특징 |
|------|------|---------|------|------|
| **Upstage** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $0.01/페이지 | 테이블/차트 인식, 구조화 출력 |
| **PyMuPDF** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 무료 | 빠른 처리, 대용량 최적화 |
| **pdfplumber** | ⭐⭐⭐ | ⭐⭐⭐⭐ | 무료 | 정확한 테이블, 복잡한 레이아웃 |
| **Tesseract** | ⭐⭐ | ⭐⭐ | 무료 | 이미지 PDF, 스캔 문서 처리 |

### **엔진 선택 가이드**
- **최고 성능 원함** → Upstage Document Parse
- **무료로 빠르게** → PyMuPDF  
- **정확한 테이블 추출** → pdfplumber
- **스캔된 이미지 문서** → Tesseract OCR

---

## 🧪 테스트 및 진단

### **엔진 진단**
```bash
# 모든 엔진 상태 확인
python cli.py --diagnose
```

출력 예시:
```
🔧 PDF 추출 엔진 진단
┌─────────────┬──────────────┬──────────────┬──────────────┬────────────────┐
│ 엔진        │ 상태         │ 사용 가능    │ 설정         │ 비고           │
├─────────────┼──────────────┼──────────────┼──────────────┼────────────────┤
│ upstage     │ ✅ 활성화    │ 사용 가능    │ 타임아웃:60초│ API 키 설정됨  │
│ pymupdf     │ ✅ 활성화    │ 사용 가능    │ 타임아웃:30초│ -              │
│ pdfplumber  │ ✅ 활성화    │ 사용 가능    │ 타임아웃:45초│ -              │
│ tesseract   │ ✅ 활성화    │ 사용 가능    │ 타임아웃:120초│ 한국어 지원   │
└─────────────┴──────────────┴──────────────┴──────────────┴────────────────┘
```

### **성능 테스트**
```bash
# 단일 파일로 모든 엔진 테스트
python cli.py --files sample.pdf --test-engines

# 디렉토리 전체 벤치마크
python -m app.test_pdf_engines ./test_documents/

# 결과 JSON 저장
python -m app.test_pdf_engines ./test_documents/ --output benchmark_results.json
```

---

## ⚡ 성능 최적화 팁

### **1. 파일 크기별 최적화**
- **1MB 미만**: Upstage 권장 (빠르고 정확)
- **1-10MB**: PyMuPDF 권장 (빠른 처리)  
- **10MB 이상**: 병렬 처리 + PyMuPDF

### **2. 문서 타입별 최적화**
- **세금계산서/인보이스**: Upstage (테이블 정확도)
- **선하증권**: pdfplumber (복잡한 레이아웃)
- **스캔 문서**: Tesseract (OCR 필요)

### **3. 병렬 처리 최적화**
```bash
# CPU 코어 수에 맞춰 조정
python cli.py --files *.pdf --max-workers 8  # 8코어 시스템

# 메모리 부족 시 워커 수 줄이기
python cli.py --files *.pdf --max-workers 2
```

---

## 🔨 문제 해결

### **자주 발생하는 문제**

**1. "UPSTAGE_API_KEY가 설정되지 않았습니다"**
```bash
# .env 파일에 API 키 추가
echo "UPSTAGE_API_KEY=up_your_key_here" >> .env

# 환경변수로 직접 설정
export UPSTAGE_API_KEY=up_your_key_here
```

**2. "tesseract 명령을 찾을 수 없습니다"**
```bash
# Windows
choco install tesseract

# macOS  
brew install tesseract

# Linux
sudo apt install tesseract-ocr tesseract-ocr-kor
```

**3. "한국어 OCR 지원 없음"**
```bash
# 한국어 언어팩 설치
sudo apt install tesseract-ocr-kor  # Linux
brew install tesseract-lang          # macOS
```

**4. "PDF 파일이 손상되었습니다"**
```bash
# 파일 검증
python -c "
from app.utils import validate_pdf_file
result = validate_pdf_file('your_file.pdf')
print(result)
"
```

### **로그 확인**
```bash
# 상세 로그로 실행
python cli.py --files problem_file.pdf --verbose

# 로그 파일 확인 (설정된 경우)
tail -f logs/pdf_parser.log
```

---

## 📈 확장 가능성

### **추가 가능한 엔진**
- **AWS Textract** - AWS 기반 OCR
- **Google Document AI** - Google Cloud 기반  
- **Azure Form Recognizer** - Microsoft Azure 기반

### **커스텀 엔진 추가**
```python
# app/engine_config.py에 새 엔진 설정
class YourCustomEngine(ExtractionEngine):
    CUSTOM = "custom"

# app/pdf_parser.py에 처리 로직 추가
async def _extract_with_custom(self, file_path: str) -> str:
    # 커스텀 엔진 구현
    pass
```

---

## 📄 라이선스

MIT License - 자유롭게 사용, 수정, 배포 가능

---

## 🤝 기여 방법

1. Fork this repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 💬 지원 및 문의

- **이슈 리포트**: GitHub Issues
- **기능 요청**: GitHub Discussions  
- **기술 지원**: [support@yourproject.com](mailto:support@yourproject.com)

---

**🎉 2025년 7월 최신 버전으로 업데이트됨**
- Python 3.13.5 완전 호환
- Upstage Document Parse 연동
- 4단계 자동 폴백 시스템
- 다중 파일 병렬 처리
- 실시간 성능 모니터링