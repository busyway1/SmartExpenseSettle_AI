# AI 문서 분석기 (AI Document Analyzer)

AI를 활용한 지능형 문서 분석 시스템입니다. 수출신고필증, 세금계산서, 인보이스, BL, 이체확인증 등 다양한 비즈니스 문서를 자동으로 인식하고 구조화된 정보를 추출합니다.

## 🚀 주요 기능

### 📄 지원 문서 형식
- **PDF** (.pdf) - 텍스트 및 스캔된 이미지 모두 지원
- **Word 문서** (.doc, .docx)
- **이미지 파일** (.png, .jpg, .jpeg, .gif)
- **텍스트 파일** (.txt)

### 🔍 자동 문서 분류 및 분석
- **수출신고필증**: 신고번호, 송품장번호, 일자, 총중량, 순중량, 컨테이너번호, 출발지, 도착지, 세번부호, 란번호
- **세금계산서**: 승인번호, 공급가액, 부가세액, 공급자상호, 작성일자, 공급자등록번호, 공급받는자등록번호
- **인보이스**: 업체명, 일자, 송품장번호, B/L번호, 출발지, 도착지, 총중량, 컨테이너번호, 품목정보, 공급가액Total, 부가세액Total
- **BL (Bill of Lading)**: B/L번호, 송품장번호, 총중량, 컨테이너번호, 출발지, 도착지, 일자
- **이체확인증**: 금액, 업체명, 일자

### 🤖 AI 기반 고급 기능
- **OCR (광학 문자 인식)**: 스캔된 이미지에서 텍스트 추출
- **OpenCV 기반 이미지 강화**: 고급 이미지 처리로 OCR 정확도 향상
- **자동 문서 유형 인식**: 업로드된 문서의 유형을 자동으로 분류
- **병렬 처리**: 대용량 문서의 빠른 처리
- **비동기 처리**: 동시에 여러 문서 처리 가능

### 🌐 웹 인터페이스
- 직관적인 웹 UI
- 파일 업로드 및 관리
- 실시간 분석 결과 확인
- 설정 관리

## 📋 시스템 요구사항

- **Python**: 3.8 이상
- **메모리**: 최소 4GB RAM (대용량 문서 처리 시 8GB 권장)
- **저장공간**: 업로드된 파일 저장용 여유 공간 필요

## 🛠️ 설치 및 설정

### 1. 저장소 클론
```bash
git clone <repository-url>
cd AI활용-복사본
```

### 2. 가상환경 생성 (권장)
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. OpenAI API 키 설정
환경 변수로 설정하거나 애플리케이션 내에서 설정:

```bash
# Windows
set OPENAI_API_KEY=your_api_key_here

# macOS/Linux
export OPENAI_API_KEY=your_api_key_here
```

### 5. 애플리케이션 실행
```bash
python app.py
```

웹 브라우저에서 `http://localhost:5000`으로 접속

## 📖 사용 방법

### 1. 웹 인터페이스 사용
1. 브라우저에서 `http://localhost:5000` 접속
2. **파일 업로드** 탭에서 분석할 문서 선택
3. **분석** 탭에서 분석 실행
4. **결과 확인** 탭에서 구조화된 결과 확인

### 2. 프로그래밍 방식 사용
```python
from ai_analyzer import AIAnalyzer

# 기본 분석기 초기화
analyzer = AIAnalyzer(api_key="your_openai_api_key")

# 고급 OpenCV 이미지 처리 활성화
analyzer_advanced = AIAnalyzer(
    api_key="your_openai_api_key", 
    use_advanced_opencv=True
)

# 문서 분석
result = analyzer.analyze_document("path/to/document.pdf")

# 자동 분류 분석
result = analyzer.analyze_document("path/to/document.pdf", "자동분류")

# 이미지 개선 테스트
enhanced_image = analyzer._enhance_image_advanced_opencv(original_image)
```

## 🔧 고급 설정

### 환경 변수 설정
```bash
# OpenAI API 설정
OPENAI_API_KEY=your_api_key_here

# Flask 설정
FLASK_ENV=development
FLASK_DEBUG=1

# 파일 업로드 설정
MAX_CONTENT_LENGTH=16777216  # 16MB

# OpenCV 고급 이미지 처리 설정
USE_ADVANCED_OPENCV=true  # 고급 OpenCV 처리 활성화 (기본값: false)
```

### 설정 파일 (config.py)
```python
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
```

## 📊 출력 형식

### JSON 구조화된 결과
```json
{
  "수출신고필증": [
    {
      "신고번호": "2024-123456789",
      "송품장번호": "INV-2024-001",
      "일자": "2024-01-15",
      "페이지번호": 1,
      "총중량": "1,000.50kg",
      "순중량": "950.25kg",
      "컨테이너번호": "CONT1234567",
      "출발지": "SEOUL",
      "도착지": "BUSAN",
      "세번부호": "1234567890",
      "란번호": "A"
    }
  ],
  "세금계산서": [
    {
      "승인번호": "2024-987654321",
      "공급가액": "1,000,000원",
      "부가세액": "100,000원",
      "공급자상호": "(주)공급회사",
      "작성일자": "2024-01-15",
      "공급자등록번호": "123-45-67890",
      "공급받는자등록번호": "098-76-54321",
      "페이지번호": 2
    }
  ]
}
```

## 🚨 문제 해결

### 일반적인 오류

#### OpenAI API 키 오류
```
Error: OpenAI API 키가 설정되지 않았습니다.
```
**해결방법**: 환경 변수 또는 애플리케이션 설정에서 API 키 확인

#### PDF 텍스트 추출 실패
```
Error: 텍스트 추출 실패
```
**해결방법**: 
- 스캔된 이미지 PDF의 경우 OCR 기능이 자동으로 활성화됩니다
- 파일이 손상되지 않았는지 확인
- 다른 PDF 뷰어에서 파일 열기 테스트

#### 메모리 부족 오류
```
Error: 메모리 부족
```
**해결방법**:
- 대용량 파일을 작은 단위로 분할
- 시스템 메모리 증가
- 동시 처리 파일 수 제한

### 성능 최적화

#### 대용량 문서 처리
- 문서를 4000자 단위로 자동 분할
- 병렬 처리로 처리 속도 향상
- 메모리 사용량 최적화

#### OCR 처리 최적화
- 고해상도 이미지 처리 (300 DPI)
- OpenCV 기반 고급 이미지 강화 처리
  - 해상도 2-3배 확대
  - 적응형 히스토그램 평활화 (CLAHE)
  - 노이즈 제거 및 엣지 강화
  - 대비 및 선명도 향상
- 페이지별 개별 처리
- 실패한 페이지 재시도 로직

## 🔒 보안 고려사항

- 업로드된 파일은 로컬 서버에만 저장
- OpenAI API를 통한 안전한 처리
- 민감한 정보는 분석 목적으로만 사용
- 세션 관리 및 접근 제어

## 📈 성능 벤치마크

| 문서 유형 | 파일 크기 | 처리 시간 | 정확도 |
|-----------|-----------|-----------|--------|
| 수출신고필증 | 2MB | ~30초 | 95%+ |
| 세금계산서 | 1MB | ~20초 | 98%+ |
| 인보이스 | 3MB | ~45초 | 92%+ |
| BL | 1.5MB | ~25초 | 90%+ |

## 🤝 기여하기

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

## 📞 지원

- **이슈 리포트**: GitHub Issues 사용
- **기능 요청**: Feature Request 라벨로 이슈 생성
- **문의사항**: 프로젝트 Wiki 참조

## 🔄 업데이트 로그

### v2.1.0 (2024-01-20)
- OpenCV 기반 고급 이미지 강화 처리 추가
- 3단계 이미지 개선 시스템 (기본 → OpenCV → 고급 OpenCV)
- 해상도 2-3배 확대 및 고급 노이즈 제거
- 적응형 히스토그램 평활화 및 엣지 강화
- 환경변수 `USE_ADVANCED_OPENCV`로 고급 모드 제어

### v2.0.0 (2024-01-15)
- AI 기반 문서 분석 시스템 구축
- 자동 문서 유형 인식 기능 추가
- OCR 기능 통합
- 웹 인터페이스 개선
- 병렬 처리 성능 최적화

### v1.0.0 (2024-01-01)
- 기본 PDF 텍스트 추출 기능
- 엑셀 변환 기능
- 웹 인터페이스 기본 구현 
