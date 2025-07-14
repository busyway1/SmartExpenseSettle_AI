# Business Settlement PDF 분석 시스템 설치 가이드

## 📋 시스템 요구사항

- **Python**: 3.9 이상 (권장: 3.11)
- **운영체제**: Windows 10/11, macOS, Linux
- **메모리**: 최소 4GB RAM (권장: 8GB)
- **디스크**: 최소 2GB 여유 공간

## 🚀 설치 단계

### 1. 저장소 클론
```bash
git clone [repository-url]
cd "Business Settlement/Code_AI"
```

### 2. Python 가상환경 생성
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux  
python3 -m venv venv
source venv/bin/activate
```

### 3. Python 패키지 설치
```bash
pip install -r requirements.txt
```

### 4. 외부 의존성 설치 (수동 설치 필요)

#### 4.1 Tesseract OCR 설치

**Windows:**
1. [Tesseract 다운로드](https://github.com/UB-Mannheim/tesseract/wiki)
2. 설치 후 시스템 PATH에 추가
3. 한국어 언어팩 설치: `kor.traineddata`

**macOS:**
```bash
brew install tesseract
brew install tesseract-lang  # 한국어 포함
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install tesseract-ocr
sudo apt install tesseract-ocr-kor  # 한국어
```

#### 4.2 Poppler 설치 (pdf2image용)

**Windows:**
1. [Poppler Windows 바이너리](https://github.com/oschwartz10612/poppler-windows/releases) 다운로드
2. 압축 해제 후 `bin` 폴더를 시스템 PATH에 추가

**macOS:**
```bash
brew install poppler
```

**Ubuntu/Debian:**
```bash
sudo apt install poppler-utils
```

### 5. 환경 변수 설정

`.env` 파일을 프로젝트 루트에 생성:
```env
# Upstage API 설정 (필수)
UPSTAGE_API_KEY=your_upstage_api_key_here

# 로깅 레벨 (선택)
LOG_LEVEL=INFO

# OCR 설정 (선택)
TESSERACT_CMD=/usr/bin/tesseract  # Linux/macOS
# TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe  # Windows
```

### 6. 샘플 파일 준비

`samples/` 폴더에 테스트할 PDF 파일을 복사:
```
samples/
├── invoice_sample.pdf
├── bl_sample.pdf
└── tax_invoice_sample.pdf
```

## 🔑 API 키 발급

### Upstage Document AI API
1. [Upstage Console](https://console.upstage.ai/) 접속
2. 회원가입/로그인
3. API 키 생성
4. `.env` 파일에 `UPSTAGE_API_KEY` 설정

## ✅ 설치 확인

### 1. 기본 테스트
```bash
python cli.py -f samples/test.pdf --engine pymupdf --verbose
```

### 2. Upstage API 테스트
```bash
python cli.py -f samples/test.pdf --engine upstage --verbose
```

### 3. 의존성 확인 스크립트
```bash
python -c "
import fitz; print('✅ PyMuPDF:', fitz.__version__)
import pdfplumber; print('✅ pdfplumber:', pdfplumber.__version__)
import pytesseract; print('✅ Tesseract:', pytesseract.get_tesseract_version())
import pdf2image; print('✅ pdf2image: OK')
print('🎉 모든 의존성 정상 설치됨')
"
```

## 🛠 문제 해결

### Tesseract 관련 오류
```python
TesseractNotFoundError: tesseract is not installed
```
**해결책**: Tesseract 설치 및 PATH 설정 확인

### Poppler 관련 오류
```python
PDFInfoNotInstalledError: Unable to get page count
```
**해결책**: Poppler 설치 및 PATH 설정 확인

### API 키 오류
```python
UPSTAGE_API_KEY가 설정되지 않았습니다
```
**해결책**: `.env` 파일에 올바른 API 키 설정

### 메모리 부족
```python
MemoryError: Unable to allocate array
```
**해결책**: 
- 더 작은 PDF로 테스트
- 시스템 메모리 증설
- `--max-workers` 옵션으로 병렬 처리 수 감소

## 🚀 사용법

### 기본 사용
```bash
python cli.py -f "document.pdf"
```

### 고급 사용
```bash
# 특정 엔진 사용
python cli.py -f "document.pdf" --engine upstage

# 여러 파일 처리
python cli.py -f "doc1.pdf" -f "doc2.pdf" --parallel

# 상세 로그
python cli.py -f "document.pdf" --verbose

# 출력 디렉토리 지정
python cli.py -f "document.pdf" -o "results/"
```

## 📁 프로젝트 구조

```
Code_AI/
├── app/
│   ├── __init__.py
│   ├── models.py          # 데이터 모델
│   ├── pdf_parser.py      # PDF 파싱 엔진
│   ├── data_extractor.py  # 데이터 추출 로직
│   └── utils.py           # 유틸리티 함수
├── samples/               # 테스트 PDF 파일들 (git 제외)
├── output/               # 결과 JSON 파일들 (git 제외)
├── venv/                 # 가상환경 (git 제외)
├── cli.py                # 메인 CLI 스크립트
├── requirements.txt      # Python 의존성
├── .env                  # 환경 변수 (git 제외)
├── .gitignore           # Git 제외 파일 목록
└── SETUP.md             # 이 파일
```

## 🔄 업데이트

### Git Pull 후
```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

### 새로운 의존성 추가 시
```bash
pip freeze > requirements.txt
```

## 📞 지원

문제가 발생하면 다음을 확인하세요:
1. 모든 의존성이 올바르게 설치되었는지
2. API 키가 올바르게 설정되었는지  
3. PDF 파일이 손상되지 않았는지
4. 충분한 메모리와 디스크 공간이 있는지

상세한 오류 로그는 `--verbose` 옵션으로 확인할 수 있습니다.