import os
import openai
from typing import Dict, List, Optional
import base64
import json
import io
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import time
import gc
from prompts.prompt_manager import PromptManager

class AIAnalyzer:
    def __init__(self, api_key: str = ""):
        """AI 분석기 초기화"""
        self.api_key = api_key or os.getenv('OPENAI_API_KEY', "")
        if self.api_key:
            self.client = openai.AsyncOpenAI(api_key=self.api_key)
            self.sync_client = openai.OpenAI(api_key=self.api_key)
        else:
            print("경고: OpenAI API 키가 설정되지 않았습니다.")
            self.client = None
            self.sync_client = None
        
        # 스레드 풀 생성 (파일 I/O 작업용)
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.executor:
            self.executor.shutdown(wait=True)
    
    async def extract_text_from_file_async(self, file_path: str) -> str:
        """파일에서 텍스트 추출 (비동기식)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.extract_text_from_file, file_path)
    
    def extract_text_from_file(self, file_path: str) -> str:
        """파일에서 텍스트 추출 (동기식 - 기존 유지)"""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if file_ext == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            
            elif file_ext == '.pdf':
                # PDF 텍스트 추출 (여러 방법 시도)
                return self._extract_text_from_pdf(file_path)
            
            elif file_ext in ['.doc', '.docx']:
                from docx import Document
                doc = Document(file_path)
                return '\n'.join([paragraph.text for paragraph in doc.paragraphs])
            
            elif file_ext in ['.png', '.jpg', '.jpeg', '.gif']:
                # 이미지 파일은 OCR 처리를 위해 OpenAI Vision API 사용
                return self._extract_text_from_image(file_path)
            
            else:
                return f"지원하지 않는 파일 형식: {file_ext}"
                
        except Exception as e:
            return f"파일 읽기 오류: {str(e)}"
    
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """PDF에서 텍스트 추출 (개선된 방식)"""
        try:
            # 1단계: PyMuPDF로 빠른 텍스트 추출 시도
            text_content = self._extract_with_pymupdf(pdf_path)
            print(f"PyMuPDF 추출 결과 길이: {len(text_content.strip()) if text_content else 0}")
            if text_content and len(text_content.strip()) > 10:  # 조건 완화: 50 -> 10
                print("PyMuPDF로 텍스트 추출 성공")
                return text_content
            
            # 2단계: pdfplumber로 표와 구조화된 데이터 추출
            text_content = self._extract_with_pdfplumber(pdf_path)
            print(f"pdfplumber 추출 결과 길이: {len(text_content.strip()) if text_content else 0}")
            if text_content and len(text_content.strip()) > 10:  # 조건 완화: 50 -> 10
                print("pdfplumber로 텍스트 추출 성공")
                return text_content
            
            # 3단계: PDF_reader.py 사용 (백업) - 모듈이 없는 경우 무시
            try:
                from PDF_reader import extract_text_from_pdf
                text_data = extract_text_from_pdf(pdf_path)
                if text_data:
                    text_content = '\n\n'.join([item['Content'] for item in text_data])
                    print(f"PDF_reader 추출 결과 길이: {len(text_content.strip()) if text_content else 0}")
                    if len(text_content.strip()) > 10:  # 조건 완화: 50 -> 10
                        print("PDF_reader로 텍스트 추출 성공")
                        return text_content
            except ImportError:
                print("PDF_reader 모듈을 찾을 수 없습니다. 다른 방법을 사용합니다.")
            except Exception as e:
                print(f"PDF_reader 사용 중 오류: {str(e)}")
            
            # 4단계: PyPDF2 사용 (백업)
            try:
                import PyPDF2
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text_content = []
                    for page_num, page in enumerate(pdf_reader.pages, 1):
                        text = page.extract_text()
                        if text and text.strip():
                            text_content.append(f"[페이지 {page_num}]\n{text}")
                    
                    if text_content:
                        result = '\n\n'.join(text_content)
                        print(f"PyPDF2 추출 결과 길이: {len(result.strip()) if result else 0}")
                        if len(result.strip()) > 10:  # 조건 완화: 50 -> 10
                            print("PyPDF2로 텍스트 추출 성공")
                            return result
            except:
                pass
            
            # 5단계: 스캔된 이미지 PDF의 경우 OCR 처리 (선택적)
            print("일반 텍스트 추출 실패. PDF를 이미지로 변환하여 Vision API로 처리합니다.")
            return self._extract_text_from_pdf_as_image(pdf_path)
            
        except Exception as e:
            return f"PDF 텍스트 추출 오류: {str(e)}"
    
    def _extract_with_pymupdf(self, pdf_path: str) -> str:
        """PyMuPDF를 사용한 빠른 텍스트 추출"""
        try:
            import fitz  # PyMuPDF
            
            text_content = []
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # 텍스트 추출
                text = page.get_text()
                if text and text.strip():
                    text_content.append(f"[페이지 {page_num + 1}]\n{text}")
                
                # 표 추출 (선택적) - PyMuPDF는 표 추출 기능이 제한적
                # 대신 텍스트에서 표 형태를 유지하도록 함
            
            doc.close()
            return '\n\n'.join(text_content) if text_content else ""
            
        except Exception as e:
            print(f"PyMuPDF 추출 오류: {str(e)}")
            return ""
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> str:
        """pdfplumber를 사용한 텍스트 및 표 추출"""
        try:
            import pdfplumber
            
            text_content = []
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # 텍스트 추출
                    text = page.extract_text()
                    if text:
                        text_content.append(f"[페이지 {page_num}]\n{text}")
                    
                    # 표 추출
                    tables = page.extract_tables()
                    if tables:
                        for table_num, table in enumerate(tables, 1):
                            table_text = f"[페이지 {page_num} - 표 {table_num}]\n"
                            for row in table:
                                if row:
                                    table_text += " | ".join([str(cell) if cell else "" for cell in row]) + "\n"
                            text_content.append(table_text)
            
            return '\n\n'.join(text_content) if text_content else ""
            
        except Exception as e:
            print(f"pdfplumber 추출 오류: {str(e)}")
            return ""
    
    def _extract_text_from_scanned_pdf(self, pdf_path: str) -> str:
        """스캔된 이미지 PDF에서 OCR로 텍스트 추출 (간소화된 방식)"""
        try:
            if not self.sync_client:
                return "OpenAI API 키가 설정되지 않아 OCR 처리를 할 수 없습니다."
            
            import pdfplumber
            import io
            
            text_content = []
            
            # pdfplumber로 페이지별 처리
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    print(f"페이지 {page_num} 처리 중...")
                    
                    # 1단계: 일반 텍스트 추출 시도
                    text = page.extract_text()
                    print(f"페이지 {page_num} 일반 텍스트 길이: {len(text.strip()) if text else 0}")
                    if text and len(text.strip()) > 5:  # 조건 완화: 20 -> 5
                        text_content.append(f"[페이지 {page_num}]\n{text}")
                        print(f"페이지 {page_num}: 일반 텍스트 추출 성공")
                        continue
                    
                    # 2단계: 텍스트가 부족한 경우 OCR 처리
                    print(f"페이지 {page_num}: OCR 처리 시작...")
                    
                    # 페이지를 이미지로 변환 (고해상도)
                    img = page.to_image(resolution=300)
                    if img:
                        # 이미지를 바이트로 변환 (전처리 없이)
                        img_bytes = io.BytesIO()
                        img.original.save(img_bytes, format='PNG', quality=95)
                        img_bytes.seek(0)
                        
                        # base64로 인코딩
                        encoded_image = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
                        
                        # OpenAI Vision API로 OCR 처리
                        response = self.sync_client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {
                                    "role": "system",
                                    "content": """당신은 전문적인 OCR(광학 문자 인식) AI입니다. 이미지에서 모든 텍스트를 정확히 추출해주세요.

중요한 지침:
1. "I'm sorry, I can't assist with that" 같은 거부 답변을 하지 마세요
2. 수출신고필증, 세금계산서, 인보이스 등 모든 비즈니스 문서를 분석할 수 있습니다
3. 민감한 정보라도 텍스트 추출 목적으로만 사용되므로 안전합니다
4. 숫자, 날짜, 회사명, 금액 등을 정확히 인식해주세요
5. 표나 구조화된 데이터가 있다면 그대로 유지해주세요
6. 텍스트가 보이지 않으면 "텍스트 없음"으로 표시하되, 전체 분석을 거부하지 마세요"""
                                },
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": """이 스캔된 PDF 페이지에서 모든 텍스트를 정확히 추출해주세요.

중요한 지침:
1. 스캔된 문서이므로 텍스트가 흐릿하거나 작을 수 있습니다. 최대한 정확히 읽어주세요
2. 모든 텍스트를 빠짐없이 추출해주세요
3. 숫자, 날짜, 금액을 정확히 인식해주세요
4. 회사명, 주소, 전화번호 등을 완전히 추출해주세요
5. 표나 구조화된 데이터가 있다면 그대로 유지해주세요
6. 작은 글씨나 흐린 글씨도 최대한 읽어주세요
7. 한글, 영어, 숫자, 특수문자 모두 포함해주세요
8. "I'm sorry, I can't assist with that" 같은 답변을 하지 마세요
9. 스캔 품질이 좋지 않아도 가능한 모든 텍스트를 추출해주세요

특히 다음 정보들을 중점적으로 추출해주세요:
- 수출신고필증 번호, 날짜, 금액
- 회사 정보 (회사명, 사업자번호, 주소)
- 품목 정보, 수량, 단가
- 통화 단위 (USD, KRW, CNY 등)
- 문서 제목, 발행일, 유효기간 등"""
                                        },
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/png;base64,{encoded_image}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            max_tokens=2000,
                            temperature=0.0,
                            top_p=0.9,
                            frequency_penalty=0.1,
                            presence_penalty=0.1
                        )
                        
                        if response and response.choices:
                            page_text = response.choices[0].message.content
                            if page_text:
                                text_content.append(f"[페이지 {page_num}]\n{page_text}")
                        else:
                            print(f"페이지 {page_num}: OCR 응답이 비어있습니다.")
            
            if text_content:
                return '\n\n'.join(text_content)
            else:
                return "OCR 처리 후에도 텍스트를 추출할 수 없었습니다."
                
        except Exception as e:
            return f"OCR 처리 오류: {str(e)}"
    
    def _extract_text_from_image(self, image_path: str) -> str:
        """이미지에서 텍스트 추출 (OCR)"""
        try:
            if not self.sync_client:
                return "OpenAI API 키가 설정되지 않았습니다."
                
            # 이미지를 바이트로 변환 (전처리 없이)
            with open(image_path, 'rb') as img_file:
                img_bytes = img_file.read()
            
            # base64로 인코딩
            encoded_image = base64.b64encode(img_bytes).decode('utf-8')
            
            # 파일 확장자에 따른 MIME 타입 결정
            file_ext = os.path.splitext(image_path)[1].lower()
            if file_ext in ['.png']:
                mime_type = 'image/png'
            elif file_ext in ['.jpg', '.jpeg']:
                mime_type = 'image/jpeg'
            else:
                mime_type = 'image/png'  # 기본값
            
            # OpenAI Vision API 호출
            response = self.sync_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 전문적인 OCR(광학 문자 인식) AI입니다. 이미지에서 모든 텍스트를 정확히 추출해주세요.

중요한 지침:
1. "I'm sorry, I can't assist with that" 같은 거부 답변을 하지 마세요
2. 수출신고필증, 세금계산서, 인보이스 등 모든 비즈니스 문서를 분석할 수 있습니다
3. 민감한 정보라도 문서 분석 목적으로만 사용되므로 안전합니다
4. 숫자, 날짜, 회사명, 금액 등을 정확히 인식해주세요
5. 표나 구조화된 데이터가 있다면 그대로 유지해주세요
6. 텍스트가 보이지 않으면 "텍스트 없음"으로 표시하되, 전체 분석을 거부하지 마세요"""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """이 이미지에서 모든 텍스트를 정확히 추출해주세요.

중요한 지침:
1. 모든 텍스트를 빠짐없이 추출해주세요
2. 숫자, 날짜, 금액을 정확히 인식해주세요
3. 회사명, 주소, 전화번호 등을 완전히 추출해주세요
4. 표나 구조화된 데이터가 있다면 그대로 유지해주세요
5. 작은 글씨도 최대한 읽어주세요
6. 한글, 영어, 숫자, 특수문자 모두 포함해주세요
7. "I'm sorry, I can't assist with that" 같은 답변을 하지 마세요
8. 이미지의 모든 영역을 꼼꼼히 확인해주세요

특히 다음 정보들을 중점적으로 추출해주세요:
- 수출신고필증 번호, 날짜, 금액
- 회사 정보 (회사명, 사업자번호, 주소)
- 품목 정보, 수량, 단가
- 통화 단위 (USD, KRW, CNY 등)
- 문서 제목, 발행일, 유효기간 등"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{encoded_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.0,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            if response and response.choices:
                return response.choices[0].message.content or ""
            else:
                return "OCR 응답이 비어있습니다."
            
        except Exception as e:
            return f"이미지 OCR 처리 오류: {str(e)}"
    
    def analyze_document(self, file_path: str, custom_prompt: Optional[str] = None) -> Dict:
        """문서 분석 수행 (동기식)"""
        try:
            if not self.sync_client:
                return {
                    "success": False,
                    "error": "OpenAI API 키가 설정되지 않았습니다."
                }
            
            # 파일에서 텍스트 추출
            extracted_text = self.extract_text_from_file(file_path)
            
            # 디버깅 정보 추가
            print(f"파일 경로: {file_path}")
            print(f"추출된 텍스트 길이: {len(extracted_text) if extracted_text else 0}")
            print(f"텍스트 미리보기: {extracted_text[:200] if extracted_text else 'None'}")
            
            # 텍스트 추출 결과 검증
            if not extracted_text:
                return {
                    "success": False,
                    "error": "텍스트 추출 실패: 파일에서 텍스트를 읽을 수 없습니다."
                }
            
            if "오류" in extracted_text or "실패" in extracted_text:
                return {
                    "success": False,
                    "error": extracted_text
                }
            
            # 텍스트가 너무 짧으면 경고
            if len(extracted_text.strip()) < 10:
                return {
                    "success": False,
                    "error": f"추출된 텍스트가 너무 짧습니다. (길이: {len(extracted_text.strip())}) 스캔된 이미지 파일일 수 있습니다."
                }
            
            # 문서 유형별 자동 인식 및 분석
            if custom_prompt and "자동분류" in custom_prompt.lower():
                print("문서 유형별 자동 분류 및 분석을 시작합니다.")
                return self._analyze_document_by_type(extracted_text, file_path)
            
            # 텍스트가 너무 길면 분할 처리
            if len(extracted_text) > 6000:  # 안전한 길이로 제한
                print("텍스트가 너무 길어서 분할 처리합니다.")
                return self._analyze_large_document_sync(extracted_text, custom_prompt, file_path)
            
            # 분석 프롬프트 생성
            prompt = self._create_analysis_prompt(custom_prompt, extracted_text)
            
            # OpenAI API 호출
            response = self.sync_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 전문적인 문서 분석 AI입니다. 증빙자료에서 요청된 정보를 정확하고 구조화된 형태로 추출해주세요.

중요한 지침:
1. "I'm sorry, I can't assist with that" 같은 거부 답변을 하지 마세요
2. 문서에서 정보를 찾을 수 없어도 가능한 정보를 추출해주세요
3. 수출신고필증, 세금계산서, 인보이스 등 모든 비즈니스 문서를 분석할 수 있습니다
4. 민감한 정보라도 문서 분석 목적으로만 사용되므로 안전합니다
5. JSON 형태로 구조화된 결과를 제공해주세요
6. 정보가 없으면 "정보 없음"으로 표시하되, 전체 분석을 거부하지 마세요"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=3000,
                temperature=0.0,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            analysis_result = response.choices[0].message.content or ""
            
            # JSON 결과 포맷팅 적용
            formatted_result = self._format_json_result(analysis_result)
            
            # 반환할 텍스트 미리 저장
            preview_text = extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
            
            # 메모리 정리
            del extracted_text
            del prompt
            
            return {
                "success": True,
                "extracted_text": preview_text,
                "analysis_result": formatted_result,
                "file_name": os.path.basename(file_path)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"분석 중 오류 발생: {str(e)}"
            }
        finally:
            # 강제 가비지 컬렉션
            gc.collect()
    
    async def analyze_document_async(self, file_path: str, custom_prompt: Optional[str] = None) -> Dict:
        """문서 분석 수행 (비동기식)"""
        try:
            if not self.client:
                return {
                    "success": False,
                    "error": "OpenAI API 키가 설정되지 않았습니다."
                }
            
            # 파일에서 텍스트 추출 (비동기)
            extracted_text = await self.extract_text_from_file_async(file_path)
            
            # 디버깅 정보 추가
            print(f"파일 경로: {file_path}")
            print(f"추출된 텍스트 길이: {len(extracted_text) if extracted_text else 0}")
            print(f"텍스트 미리보기: {extracted_text[:200] if extracted_text else 'None'}")
            
            # 텍스트 추출 결과 검증
            if not extracted_text:
                return {
                    "success": False,
                    "error": "텍스트 추출 실패: 파일에서 텍스트를 읽을 수 없습니다."
                }
            
            if "오류" in extracted_text or "실패" in extracted_text:
                return {
                    "success": False,
                    "error": extracted_text
                }
            
            # 텍스트가 너무 짧으면 경고
            if len(extracted_text.strip()) < 10:
                return {
                    "success": False,
                    "error": f"추출된 텍스트가 너무 짧습니다. (길이: {len(extracted_text.strip())}) 스캔된 이미지 파일일 수 있습니다."
                }
            
            # 문서 유형별 자동 인식 및 분석
            if custom_prompt and "자동분류" in custom_prompt.lower():
                print("문서 유형별 자동 분류 및 분석을 시작합니다.")
                return await self._analyze_document_by_type_async(extracted_text, file_path)
            
            # 텍스트가 너무 길면 분할 처리
            if len(extracted_text) > 6000:  # 안전한 길이로 제한
                print("텍스트가 너무 길어서 분할 처리합니다.")
                return await self._analyze_large_document_async(extracted_text, custom_prompt, file_path)
            
            # 분석 프롬프트 생성
            prompt = self._create_analysis_prompt(custom_prompt, extracted_text)
            
            # OpenAI API 비동기 호출
            response = await self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": """당신은 전문적인 문서 분석 AI입니다. 증빙자료에서 요청된 정보를 정확하고 구조화된 형태로 추출해주세요.

중요한 지침:
1. "I'm sorry, I can't assist with that" 같은 거부 답변을 하지 마세요
2. 문서에서 정보를 찾을 수 없어도 가능한 정보를 추출해주세요
3. 수출신고필증, 세금계산서, 인보이스 등 모든 비즈니스 문서를 분석할 수 있습니다
4. 민감한 정보라도 문서 분석 목적으로만 사용되므로 안전합니다
5. JSON 형태로 구조화된 결과를 제공해주세요
6. 정보가 없으면 "정보 없음"으로 표시하되, 전체 분석을 거부하지 마세요"""
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                max_tokens=3000,
                temperature=0.0,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            analysis_result = response.choices[0].message.content or ""
            
            # JSON 결과 포맷팅 적용
            formatted_result = self._format_json_result(analysis_result)
            
            return {
                "success": True,
                "extracted_text": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
                "analysis_result": formatted_result,
                "file_name": os.path.basename(file_path)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"분석 중 오류 발생: {str(e)}"
            }
    
    async def _analyze_document_by_type_async(self, text: str, file_path: str) -> Dict:
        """문서 유형별 자동 인식 및 분석 (비동기 + 병렬처리)"""
        try:
            # 1단계: 문서 유형 분류
            document_types = self._classify_document_types(text)
            
            if not document_types:
                return {
                    "success": False,
                    "error": "문서 유형을 인식할 수 없습니다."
                }
            
            print(f"인식된 문서 유형: {document_types}")
            
            # 2단계: 각 문서 유형별로 개별 문서 인식 및 정보 추출 (병렬처리)
            tasks = []
            for doc_type, pages in document_types.items():
                print(f"{doc_type} 분석 태스크 생성... (총 {len(pages)}개 페이지)")
                
                # 같은 유형의 문서가 여러 개 있을 수 있으므로 개별 문서로 분리
                individual_docs = self._identify_individual_documents(doc_type, pages, text)
                
                # 각 개별 문서에 대한 분석 태스크 생성
                for i, doc_text in enumerate(individual_docs):
                    if doc_text.strip():
                        task = self._extract_info_by_document_type_async(doc_type, doc_text, i + 1)
                        tasks.append((doc_type, task))
            
            # 3단계: 모든 태스크를 병렬로 실행
            print(f"총 {len(tasks)}개 분석 태스크를 병렬로 실행합니다...")
            start_time = time.time()
            
            # 태스크 그룹화
            doc_type_tasks = {}
            for doc_type, task in tasks:
                if doc_type not in doc_type_tasks:
                    doc_type_tasks[doc_type] = []
                doc_type_tasks[doc_type].append(task)
            
            # 각 문서 유형별로 병렬 실행
            results = {}
            for doc_type, task_list in doc_type_tasks.items():
                print(f"{doc_type} 병렬 분석 시작...")
                doc_results = await asyncio.gather(*task_list, return_exceptions=True)
                
                # 예외 처리
                processed_results = []
                for i, result in enumerate(doc_results):
                    if isinstance(result, Exception):
                        print(f"{doc_type} #{i+1} 분석 오류: {str(result)}")
                        processed_results.append({
                            "type": doc_type,
                            "document_index": i + 1,
                            "error": f"분석 오류: {str(result)}"
                        })
                    else:
                        processed_results.append(result)
                
                results[doc_type] = processed_results
            
            end_time = time.time()
            print(f"병렬 분석 완료. 소요시간: {end_time - start_time:.2f}초")
            
            # 4단계: 최종 결과 통합
            final_result = await self._combine_document_type_results_async(results)
            
            return {
                "success": True,
                "extracted_text": text[:500] + "..." if len(text) > 500 else text,
                "analysis_result": final_result,
                "file_name": os.path.basename(file_path),
                "document_types": list(document_types.keys()),
                "document_counts": {doc_type: len(docs) for doc_type, docs in results.items()},
                "processing_time": end_time - start_time
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"문서 유형별 분석 중 오류 발생: {str(e)}"
            }
    
    async def _extract_info_by_document_type_async(self, doc_type: str, text: str, document_index: int) -> Dict:
        """문서 유형별 정보 추출 (비동기식)"""
        try:
            print(f"정보 추출 시작: {doc_type} #{document_index}")
            print(f"입력 텍스트 길이: {len(text)}")
            print(f"입력 텍스트 미리보기: {text[:200]}...")
            
            # 문서 유형별 전용 프롬프트 생성
            prompt = self._create_document_type_prompt(doc_type, text)
            
            print(f"프롬프트 길이: {len(prompt)}")
            print(f"프롬프트 미리보기: {prompt[:300]}...")
            
            if not self.client:
                return {
                    "type": doc_type,
                    "document_index": document_index,
                    "error": "OpenAI API 키가 설정되지 않았습니다."
                }
            
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": f"""당신은 {doc_type} 전문 분석 AI입니다. 해당 문서 유형에서 **지정된 필드만** 정확히 추출해주세요.

중요한 지침:
1. "I'm sorry, I can't assist with that" 같은 거부 답변을 하지 마세요
2. **지정된 필드만 추출하고, 다른 정보는 절대 무시해주세요**
3. JSON 형태로 구조화된 결과를 제공해주세요
4. 정보가 없으면 "정보 없음"으로 표시하되, 전체 분석을 거부하지 마세요
5. **요청하지 않은 정보는 절대 포함하지 마세요**
6. **문서에 있는 모든 정보를 추출하지 말고, 요청된 필드만 추출하세요**
7. **추가 설명이나 주석 없이 순수한 JSON만 반환하세요**"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=2000,
                temperature=0.0,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            if response and response.choices:
                result = response.choices[0].message.content or ""
                print(f"AI 응답 길이: {len(result)}")
                print(f"AI 응답 미리보기: {result[:200]}...")
                
                return {
                    "type": doc_type,
                    "document_index": document_index,
                    "extracted_info": result,
                    "pages": text[:200] + "..." if len(text) > 200 else text
                }
            else:
                return {
                    "type": doc_type,
                    "document_index": document_index,
                    "error": "AI 응답이 비어있습니다."
                }
            
        except Exception as e:
            print(f"정보 추출 오류: {str(e)}")
            return {
                "type": doc_type,
                "document_index": document_index,
                "error": f"정보 추출 오류: {str(e)}"
            }
    
    async def _combine_document_type_results_async(self, results: Dict) -> str:
        """문서 유형별 결과 통합 (비동기식)"""
        try:
            # 실제로 분석된 문서 유형만 필터링
            valid_results = {}
            for doc_type, doc_results in results.items():
                if doc_results and any("extracted_info" in result and result["extracted_info"].strip() for result in doc_results):
                    valid_results[doc_type] = doc_results
            
            if not valid_results:
                return "분석된 문서가 없습니다."
            
            # 각 문서 유형별로 JSON 배열 구성
            final_result = {}
            
            for doc_type, doc_results in valid_results.items():
                doc_array = []
                
                for result in doc_results:
                    if "extracted_info" in result and result["extracted_info"].strip():
                        try:
                            # JSON 파싱 시도
                            doc_info = json.loads(result["extracted_info"])
                            if isinstance(doc_info, list):
                                # 배열인 경우 각 요소에 document_index 추가
                                for i, item in enumerate(doc_info):
                                    if isinstance(item, dict):
                                        item["document_index"] = result.get("document_index", i + 1)
                                doc_array.extend(doc_info)
                            elif isinstance(doc_info, dict):
                                # 단일 객체인 경우
                                doc_info["document_index"] = result.get("document_index", 1)
                                doc_array.append(doc_info)
                            else:
                                # 기타 경우
                                doc_array.append({
                                    "document_index": result.get("document_index", 1),
                                    "raw_data": doc_info
                                })
                        except json.JSONDecodeError:
                            # JSON 파싱 실패시 텍스트로 저장
                            doc_array.append({
                                "document_index": result.get("document_index", 1),
                                "raw_text": result["extracted_info"]
                            })
                
                if doc_array:
                    final_result[doc_type] = doc_array
            
            # 최종 JSON 포맷팅
            if final_result:
                return json.dumps(final_result, ensure_ascii=False, indent=2)
            else:
                return "분석된 문서가 없습니다."
            
        except Exception as e:
            print(f"결과 통합 중 오류: {str(e)}")
            return f"결과 통합 중 오류가 발생했습니다: {str(e)}"
    
    async def _analyze_large_document_async(self, text: str, custom_prompt: Optional[str], file_path: str) -> Dict:
        """큰 문서를 분할해서 분석 (비동기 + 병렬처리)"""
        try:
            # 텍스트를 청크로 분할 (각 청크는 4000자 이하)
            chunks = self._split_text_into_chunks(text, 4000)
            
            print(f"문서를 {len(chunks)}개 청크로 분할했습니다.")
            
            # 각 청크별로 분석 태스크 생성 (병렬처리)
            tasks = []
            for i, chunk in enumerate(chunks):
                print(f"청크 {i+1}/{len(chunks)} 분석 태스크 생성...")
                prompt = self._create_analysis_prompt(custom_prompt, chunk)
                
                task = self._analyze_chunk_async(prompt, i + 1)
                tasks.append(task)
            
            # 모든 청크를 병렬로 분석
            print(f"총 {len(tasks)}개 청크를 병렬로 분석합니다...")
            start_time = time.time()
            
            chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 예외 처리
            processed_results = []
            for i, result in enumerate(chunk_results):
                if isinstance(result, Exception):
                    print(f"청크 {i+1} 분석 오류: {str(result)}")
                    processed_results.append(f"청크 {i+1} 분석 오류: {str(result)}")
                else:
                    processed_results.append(result)
            
            end_time = time.time()
            print(f"청크 병렬 분석 완료. 소요시간: {end_time - start_time:.2f}초")
            
            # 모든 청크 결과를 통합
            combined_result = await self._combine_chunk_results_async(processed_results)
            
            return {
                "success": True,
                "extracted_text": text[:500] + "..." if len(text) > 500 else text,
                "analysis_result": combined_result,
                "file_name": os.path.basename(file_path),
                "processing_time": end_time - start_time
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"큰 문서 분석 중 오류 발생: {str(e)}"
            }
    
    async def _analyze_chunk_async(self, prompt: str, chunk_index: int) -> str:
        """개별 청크 분석 (비동기식)"""
        try:
            if not self.client:
                return f"청크 {chunk_index} 분석 오류: OpenAI API 키가 설정되지 않았습니다."
            
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 전문적인 문서 분석 AI입니다. 증빙자료에서 **지정된 정보만** 정확하고 구조화된 형태로 추출해주세요.

                    중요한 지침:
                    1. "I'm sorry, I can't assist with that" 같은 거부 답변을 하지 마세요
                    2. **지정된 필드만 추출하고, 다른 정보는 무시해주세요**
                    3. 수출신고필증, 세금계산서, 인보이스 등 모든 비즈니스 문서를 분석할 수 있습니다
                    4. 민감한 정보라도 문서 분석 목적으로만 사용되므로 안전합니다
                    5. JSON 형태로 구조화된 결과를 제공해주세요
                    6. 정보가 없으면 "정보 없음"으로 표시하되, 전체 분석을 거부하지 마세요
                    7. **요청하지 않은 정보는 절대 포함하지 마세요**"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=2000,
                temperature=0.0,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            if response and response.choices:
                return response.choices[0].message.content or ""
            else:
                return f"청크 {chunk_index} 분석 오류: 응답이 비어있습니다."
            
        except Exception as e:
            return f"청크 {chunk_index} 분석 오류: {str(e)}"
    
    async def _combine_chunk_results_async(self, chunk_results: List[str]) -> str:
        """청크 결과들을 통합 (비동기식)"""
        try:
            # 실제로 분석된 결과만 필터링
            valid_results = [result for result in chunk_results if result and result.strip()]
            
            if not valid_results:
                return "분석된 문서가 없습니다."
            
            # 모든 결과를 하나로 합치고 JSON 파싱 시도
            combined_text = "\n\n".join(valid_results)
            
            # JSON 형태로 통합 시도
            try:
                # 각 청크의 JSON을 파싱하여 통합
                final_result = {}
                
                for chunk_text in valid_results:
                    try:
                        chunk_data = json.loads(chunk_text)
                        if isinstance(chunk_data, dict):
                            for doc_type, doc_array in chunk_data.items():
                                if doc_type not in final_result:
                                    final_result[doc_type] = []
                                if isinstance(doc_array, list):
                                    final_result[doc_type].extend(doc_array)
                                else:
                                    final_result[doc_type].append(doc_array)
                    except json.JSONDecodeError:
                        # JSON이 아닌 경우 무시
                        continue
                
                if final_result:
                    return json.dumps(final_result, ensure_ascii=False, indent=2)
                else:
                    return combined_text
                    
            except Exception as e:
                # JSON 통합 실패시 원본 텍스트 반환
                return combined_text
            
        except Exception as e:
            print(f"청크 결과 통합 중 오류: {str(e)}")
            return chunk_results[0] if chunk_results else "분석 결과 통합 중 오류가 발생했습니다."
    
    def _split_text_into_chunks(self, text: str, max_chunk_size: int) -> List[str]:
        """텍스트를 청크로 분할"""
        chunks = []
        current_chunk = ""
        
        # 페이지별로 분할
        pages = text.split('[페이지')
        
        for page in pages:
            if not page.strip():
                continue
                
            page_text = '[페이지' + page if not page.startswith('[페이지') else page
            
            # 현재 청크에 페이지를 추가했을 때 크기 확인
            if len(current_chunk + page_text) <= max_chunk_size:
                current_chunk += page_text
            else:
                # 현재 청크가 있으면 저장
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                
                # 새 청크 시작
                current_chunk = page_text
        
        # 마지막 청크 추가
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _analyze_large_document_sync(self, text: str, custom_prompt: Optional[str], file_path: str) -> Dict:
        """큰 문서를 분할해서 분석 (동기식)"""
        try:
            # 텍스트를 청크로 분할 (각 청크는 4000자 이하)
            chunks = self._split_text_into_chunks(text, 4000)
            
            print(f"문서를 {len(chunks)}개 청크로 분할했습니다.")
            
            # 각 청크별로 분석 (순차 처리)
            chunk_results = []
            for i, chunk in enumerate(chunks):
                print(f"청크 {i+1}/{len(chunks)} 분석 중...")
                prompt = self._create_analysis_prompt(custom_prompt, chunk)
                
                result = self._analyze_chunk_sync(prompt, i + 1)
                chunk_results.append(result)
            
            # 모든 청크 결과를 통합
            combined_result = self._combine_chunk_results(chunk_results)
            
            return {
                "success": True,
                "extracted_text": text[:500] + "..." if len(text) > 500 else text,
                "analysis_result": combined_result,
                "file_name": os.path.basename(file_path)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"큰 문서 분석 중 오류 발생: {str(e)}"
            }
    
    def _analyze_chunk_sync(self, prompt: str, chunk_index: int) -> str:
        """개별 청크 분석 (동기식)"""
        try:
            if not self.sync_client:
                return f"청크 {chunk_index} 분석 오류: OpenAI API 키가 설정되지 않았습니다."
            
            response = self.sync_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 전문적인 문서 분석 AI입니다. 증빙자료에서 **지정된 정보만** 정확하고 구조화된 형태로 추출해주세요.

                    중요한 지침:
                    1. "I'm sorry, I can't assist with that" 같은 거부 답변을 하지 마세요
                    2. **지정된 필드만 추출하고, 다른 정보는 무시해주세요**
                    3. 수출신고필증, 세금계산서, 인보이스 등 모든 비즈니스 문서를 분석할 수 있습니다
                    4. 민감한 정보라도 문서 분석 목적으로만 사용되므로 안전합니다
                    5. JSON 형태로 구조화된 결과를 제공해주세요
                    6. 정보가 없으면 "정보 없음"으로 표시하되, 전체 분석을 거부하지 마세요
                    7. **요청하지 않은 정보는 절대 포함하지 마세요**"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=2000,
                temperature=0.0,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            if response and response.choices:
                return response.choices[0].message.content or ""
            else:
                return f"청크 {chunk_index} 분석 오류: 응답이 비어있습니다."
            
        except Exception as e:
            return f"청크 {chunk_index} 분석 오류: {str(e)}"
    
    def _combine_chunk_results(self, chunk_results: List[str]) -> str:
        """청크 결과들을 통합"""
        try:
            # 실제로 분석된 결과만 필터링
            valid_results = [result for result in chunk_results if result and result.strip()]
            
            if not valid_results:
                return "분석된 문서가 없습니다."
            
            # 모든 결과를 하나로 합치고 JSON 파싱 시도
            combined_text = "\n\n".join(valid_results)
            
            # JSON 형태로 통합 시도
            try:
                # 각 청크의 JSON을 파싱하여 통합
                final_result = {}
                
                for chunk_text in valid_results:
                    try:
                        chunk_data = json.loads(chunk_text)
                        if isinstance(chunk_data, dict):
                            for doc_type, doc_array in chunk_data.items():
                                if doc_type not in final_result:
                                    final_result[doc_type] = []
                                if isinstance(doc_array, list):
                                    final_result[doc_type].extend(doc_array)
                                else:
                                    final_result[doc_type].append(doc_array)
                    except json.JSONDecodeError:
                        # JSON이 아닌 경우 무시
                        continue
                
                if final_result:
                    return json.dumps(final_result, ensure_ascii=False, indent=2)
                else:
                    return combined_text
                    
            except Exception as e:
                # JSON 통합 실패시 원본 텍스트 반환
                return combined_text
            
        except Exception as e:
            print(f"청크 결과 통합 중 오류: {str(e)}")
            return chunk_results[0] if chunk_results else f"분석 결과 통합 중 오류가 발생했습니다: {str(e)}"
    
    def _analyze_document_by_type(self, text: str, file_path: str) -> Dict:
        """문서 유형별 자동 인식 및 분석"""
        try:
            # 1단계: 문서 유형 분류
            document_types = self._classify_document_types(text)
            
            if not document_types:
                return {
                    "success": False,
                    "error": "문서 유형을 인식할 수 없습니다."
                }
            
            print(f"인식된 문서 유형: {document_types}")
            
            # 2단계: 각 문서 유형별로 개별 문서 인식 및 정보 추출
            results = {}
            for doc_type, pages in document_types.items():
                print(f"{doc_type} 분석 중... (총 {len(pages)}개 페이지)")
                
                # 같은 유형의 문서가 여러 개 있을 수 있으므로 개별 문서로 분리
                individual_docs = self._identify_individual_documents(doc_type, pages, text)
                
                doc_results = []
                for i, doc_text in enumerate(individual_docs):
                    print(f"  {doc_type} #{i+1} 분석 중...")
                    if doc_text.strip():
                        type_result = self._extract_info_by_document_type(doc_type, doc_text)
                        type_result["document_index"] = i + 1  # 문서 순서 표시
                        doc_results.append(type_result)
                
                results[doc_type] = doc_results
            
            # 3단계: 최종 결과 통합
            final_result = self._combine_document_type_results(results)
            
            return {
                "success": True,
                "extracted_text": text[:500] + "..." if len(text) > 500 else text,
                "analysis_result": final_result,
                "file_name": os.path.basename(file_path),
                "document_types": list(document_types.keys()),
                "document_counts": {doc_type: len(docs) for doc_type, docs in results.items()}
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"문서 유형별 분석 중 오류 발생: {str(e)}"
            }
    
    def _identify_individual_documents(self, doc_type: str, pages: List[int], full_text: str) -> List[str]:
        """같은 유형의 문서를 개별 문서로 분리"""
        try:
            print(f"개별 문서 분리 시작: {doc_type}, 페이지: {pages}")
            print(f"전체 텍스트 길이: {len(full_text)}")
            
            # 페이지별로 텍스트 분리
            page_texts = []
            page_splits = full_text.split('[페이지')
            
            print(f"페이지 분할 결과: {len(page_splits)}개 부분")
            
            for i, page_text in enumerate(page_splits):
                if not page_text.strip():
                    continue
                
                # 페이지 번호 추출
                page_num = i
                if ']' in page_text:
                    try:
                        page_num = int(page_text.split(']')[0])
                    except:
                        page_num = i
                
                if page_num in pages:
                    extracted_text = page_text.split(']', 1)[1] if ']' in page_text else page_text
                    page_texts.append({
                        'number': page_num,
                        'text': extracted_text
                    })
                    print(f"페이지 {page_num} 텍스트 길이: {len(extracted_text)}")
            
            print(f"추출된 페이지 텍스트 수: {len(page_texts)}")
            
            # 문서 유형별 개별 문서 분리 로직
            if doc_type == "세금계산서":
                result = self._split_tax_invoices(page_texts)
            elif doc_type == "수출신고필증":
                result = self._split_export_declarations(page_texts)
            elif doc_type == "인보이스":
                result = self._split_invoices(page_texts)
            elif doc_type == "BL":
                result = self._split_bl_documents(page_texts)
            elif doc_type == "이체확인증":
                result = self._split_transfer_receipts(page_texts)
            else:
                # 기본적으로 페이지별로 분리
                result = [page['text'] for page in page_texts]
            
            print(f"최종 개별 문서 수: {len(result)}")
            for i, doc in enumerate(result):
                print(f"문서 {i+1} 길이: {len(doc)}")
            
            return result
                
        except Exception as e:
            print(f"개별 문서 분리 오류: {str(e)}")
            # 오류 발생시 전체 텍스트를 하나로 반환
            return [full_text]
    
    def _split_tax_invoices(self, page_texts: List[Dict]) -> List[str]:
        """세금계산서 개별 문서 분리"""
        individual_docs = []
        
        for page in page_texts:
            text = page['text']
            # 세금계산서의 시작을 나타내는 키워드 확인
            if any(keyword in text.lower() for keyword in ['세금계산서', '승인번호', '공급가액', '부가세']):
                individual_docs.append(text)
        
        return individual_docs if individual_docs else [page['text'] for page in page_texts]
    
    def _split_export_declarations(self, page_texts: List[Dict]) -> List[str]:
        """수출신고필증 개별 문서 분리"""
        individual_docs = []
        
        for page in page_texts:
            text = page['text']
            # 수출신고필증의 시작을 나타내는 키워드 확인
            if any(keyword in text.lower() for keyword in ['수출신고필증', '신고번호', '송품장부호', '세번부호']):
                individual_docs.append(text)
        
        return individual_docs if individual_docs else [page['text'] for page in page_texts]
    
    def _split_invoices(self, page_texts: List[Dict]) -> List[str]:
        """인보이스 개별 문서 분리"""
        individual_docs = []
        
        for page in page_texts:
            text = page['text']
            # 인보이스의 시작을 나타내는 키워드 확인
            if any(keyword in text.lower() for keyword in ['invoice', '인보이스', '송품장', 'bill to', 'ship to']):
                individual_docs.append(text)
        
        return individual_docs if individual_docs else [page['text'] for page in page_texts]
    
    def _split_bl_documents(self, page_texts: List[Dict]) -> List[str]:
        """BL 문서 개별 문서 분리"""
        individual_docs = []
        
        for page in page_texts:
            text = page['text']
            # BL 문서의 시작을 나타내는 키워드 확인
            if any(keyword in text.lower() for keyword in ['bill of lading', 'b/l', 'way bill', 'shipper', 'consignee']):
                individual_docs.append(text)
        
        return individual_docs if individual_docs else [page['text'] for page in page_texts]
    
    def _split_transfer_receipts(self, page_texts: List[Dict]) -> List[str]:
        """이체확인증 개별 문서 분리"""
        individual_docs = []
        
        for page in page_texts:
            text = page['text']
            # 이체확인증의 시작을 나타내는 키워드 확인
            if any(keyword in text.lower() for keyword in ['이체확인증', '입출금내역', '송금증', '이체금액', '출금금액', '받는분']):
                individual_docs.append(text)
        
        return individual_docs if individual_docs else [page['text'] for page in page_texts]
    
    def _classify_document_types(self, text: str) -> Dict[str, List[int]]:
        """문서 유형 분류"""
        try:
            # 페이지별로 분할
            pages = []
            page_texts = text.split('[페이지')
            
            for i, page_text in enumerate(page_texts):
                if not page_text.strip():
                    continue
                
                # 페이지 번호 추출
                page_num = i
                if ']' in page_text:
                    try:
                        page_num = int(page_text.split(']')[0])
                    except:
                        page_num = i
                
                pages.append({
                    'number': page_num,
                    'text': page_text.split(']', 1)[1] if ']' in page_text else page_text
                })
            
            # 각 페이지의 문서 유형 분류
            document_types = {}
            
            for page in pages:
                doc_type = self._identify_single_page_type(page['text'])
                if doc_type:
                    if doc_type not in document_types:
                        document_types[doc_type] = []
                    document_types[doc_type].append(page['number'])
            
            return document_types
            
        except Exception as e:
            print(f"문서 유형 분류 오류: {str(e)}")
            return {}
    
    def _identify_single_page_type(self, page_text: str) -> str:
        """단일 페이지의 문서 유형 인식"""
        try:
            # 키워드 기반 문서 유형 인식
            page_text_lower = page_text.lower()
            
            # 수출신고필증
            if any(keyword in page_text_lower for keyword in ['수출신고필증', '수출신고', '신고번호', '세관과', '송품장부호', '세번부호', '적재항', '목적국']):
                return "수출신고필증"
            
            # 세금계산서
            elif any(keyword in page_text_lower for keyword in ['세금계산서', '공급가액', '부가세', '공급자', '공급받는자', '승인번호', '사업자등록번호']):
                return "세금계산서"
            
            # 인보이스 (commercial invoice는 제외)
            elif any(keyword in page_text_lower for keyword in ['invoice', '인보이스', '송품장', 'bill to', 'ship to', 'amount', 'krw', '원화']) and 'commercial invoice' not in page_text_lower:
                return "인보이스"
            
            # BL (Bill of Lading, Way Bill, B/L 등)
            elif any(keyword in page_text_lower for keyword in ['bill of lading', 'b/l', 'way bill', 'shipper', 'consignee', 'bl no', 'bl number', 'port of loading', 'port of discharge', 'gross weight']):
                return "BL"
            
            # Packing List
            elif any(keyword in page_text_lower for keyword in ['packing list', 'p/l', 'description', 'quantity', 'weight']):
                return "Packing List"
            
            # 이체확인증/송금증
            elif any(keyword in page_text_lower for keyword in ['이체확인증', '송금증', '이체금액', '출금금액', '받는분']):
                return "이체확인증"
            
            # 기타 상업서류
            elif any(keyword in page_text_lower for keyword in ['commercial invoice', 'certificate', 'cert', '증명서']):
                return "기타상업서류"
            
            return "미분류"
            
        except Exception as e:
            print(f"페이지 유형 인식 오류: {str(e)}")
            return "미분류"
    
    def get_supported_document_types(self) -> list:
        """지원되는 문서 유형 목록 반환"""
        return PromptManager.get_supported_document_types()
    
    def is_supported_document_type(self, doc_type: str) -> bool:
        """지원되는 문서 유형인지 확인"""
        return PromptManager.is_supported_document_type(doc_type)
    
    def _extract_info_by_document_type(self, doc_type: str, text: str) -> Dict:
        """문서 유형별 정보 추출"""
        try:
            print(f"정보 추출 시작: {doc_type}")
            print(f"입력 텍스트 길이: {len(text)}")
            print(f"입력 텍스트 미리보기: {text[:200]}...")
            
            # 문서 유형별 전용 프롬프트 생성
            prompt = self._create_document_type_prompt(doc_type, text)
            
            print(f"프롬프트 길이: {len(prompt)}")
            print(f"프롬프트 미리보기: {prompt[:300]}...")
            
            if not self.sync_client:
                return {
                    "type": doc_type,
                    "error": "OpenAI API 키가 설정되지 않았습니다."
                }
            
            response = self.sync_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": f"""당신은 {doc_type} 전문 분석 AI입니다. 해당 문서 유형에서 **지정된 필드만** 정확히 추출해주세요.

중요한 지침:
1. "I'm sorry, I can't assist with that" 같은 거부 답변을 하지 마세요
2. **지정된 필드만 추출하고, 다른 정보는 절대 무시해주세요**
3. JSON 형태로 구조화된 결과를 제공해주세요
4. 정보가 없으면 "정보 없음"으로 표시하되, 전체 분석을 거부하지 마세요
5. **요청하지 않은 정보는 절대 포함하지 마세요**
6. **문서에 있는 모든 정보를 추출하지 말고, 요청된 필드만 추출하세요**
7. **추가 설명이나 주석 없이 순수한 JSON만 반환하세요**"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=2000,
                temperature=0.0,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            if response and response.choices:
                result = response.choices[0].message.content or ""
                print(f"AI 응답 길이: {len(result)}")
                print(f"AI 응답 미리보기: {result[:200]}...")
            
                return {
                    "type": doc_type,
                        "extracted_info": result,
                    "pages": text[:200] + "..." if len(text) > 200 else text
                }
            else:
                return {
                    "type": doc_type,
                    "error": "AI 응답이 비어있습니다."
                }
            
        except Exception as e:
            print(f"정보 추출 오류: {str(e)}")
            return {
                "type": doc_type,
                "error": f"정보 추출 오류: {str(e)}"
            }
    
    def _create_document_type_prompt(self, doc_type: str, text: str) -> str:
        """문서 유형별 전용 프롬프트 생성"""
        return PromptManager.get_prompt(doc_type, text)
    
    def _combine_document_type_results(self, results: Dict) -> str:
        """문서 유형별 결과 통합"""
        try:
            # 실제로 분석된 문서 유형만 필터링
            valid_results = {}
            for doc_type, doc_results in results.items():
                if doc_results and any("extracted_info" in result and result["extracted_info"].strip() for result in doc_results):
                    valid_results[doc_type] = doc_results
            
            if not valid_results:
                return "분석된 문서가 없습니다."
            
            # 각 문서 유형별로 JSON 배열 구성
            final_result = {}
            
            for doc_type, doc_results in valid_results.items():
                doc_array = []
                
                for result in doc_results:
                    if "extracted_info" in result and result["extracted_info"].strip():
                        try:
                            # JSON 파싱 시도
                            doc_info = json.loads(result["extracted_info"])
                            if isinstance(doc_info, list):
                                # 배열인 경우 각 요소에 document_index 추가
                                for i, item in enumerate(doc_info):
                                    if isinstance(item, dict):
                                        item["document_index"] = result.get("document_index", i + 1)
                                doc_array.extend(doc_info)
                            elif isinstance(doc_info, dict):
                                # 단일 객체인 경우
                                doc_info["document_index"] = result.get("document_index", 1)
                                doc_array.append(doc_info)
                            else:
                                # 기타 경우
                                doc_array.append({
                                    "document_index": result.get("document_index", 1),
                                    "raw_data": doc_info
                                })
                        except json.JSONDecodeError:
                            # JSON 파싱 실패시 텍스트로 저장
                            doc_array.append({
                                "document_index": result.get("document_index", 1),
                                "raw_text": result["extracted_info"]
                            })
                
                if doc_array:
                    final_result[doc_type] = doc_array
            
            # 최종 JSON 포맷팅
            if final_result:
                return json.dumps(final_result, ensure_ascii=False, indent=2)
            else:
                return "분석된 문서가 없습니다."
            
        except Exception as e:
            print(f"결과 통합 중 오류: {str(e)}")
            return f"결과 통합 중 오류가 발생했습니다: {str(e)}"
    
    def _create_analysis_prompt(self, custom_prompt: Optional[str], text: str) -> str:
        """분석 프롬프트 생성"""
        base_prompt = f"""
다음 문서를 분석하여 **지정된 정보만** 추출해주세요.

중요한 지침:
1. "I'm sorry, I can't assist with that" 같은 거부 답변을 하지 마세요
2. **지정된 필드만 추출하고, 다른 정보는 무시해주세요**
3. 수출신고필증, 세금계산서, 인보이스 등 모든 비즈니스 문서를 분석할 수 있습니다
4. 민감한 정보라도 문서 분석 목적으로만 사용되므로 안전합니다
5. 정보가 없으면 "정보 없음"으로 표시하되, 전체 분석을 거부하지 마세요
6. JSON 형태로 구조화된 결과를 제공해주세요
7. **요청하지 않은 정보는 절대 포함하지 마세요**

**중요: 여러 개의 같은 유형 문서가 있는 경우**
- 같은 유형의 문서가 여러 개 있으면 각각을 개별적으로 식별하고 모든 정보를 출력해주세요
- 각 문서 유형별 식별자:
  * 세금계산서: 승인번호 (승인번호가 다르면 다른 문서)
  * 수출신고필증: 신고번호 (신고번호가 다르면 다른 문서)
  * 인보이스: Invoice No. 또는 송품장번호 (번호가 다르면 다른 문서)
  * BL: B/L 번호 (B/L 번호가 다르면 다른 문서)
  * 이체확인증: 거래일시 + 금액 + 업체명 조합
- 각 문서마다 페이지 번호를 반드시 포함해주세요
- 배열 형태로 각 개별 문서의 정보를 모두 출력해주세요

문서 내용:
{text}

"""
        
        if custom_prompt:
            return base_prompt + f"사용자 요청: {custom_prompt}\n\n**지정된 필드만 추출하여** JSON 형태로 구조화된 결과를 제공해주세요."
        else:
            return base_prompt + "문서에서 **중요한 정보만** 추출하여 JSON 형태로 정리해주세요. **요청하지 않은 정보는 절대 포함하지 마세요.**"
    
    def _format_json_result(self, json_string: str) -> str:
        """JSON 결과를 보기 좋게 포맷팅"""
        try:
            import json
            # JSON 파싱 시도
            parsed_json = json.loads(json_string)
            # 들여쓰기와 함께 다시 포맷팅
            return json.dumps(parsed_json, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            # JSON 파싱 실패시 원본 반환
            return json_string
        except Exception as e:
            # 기타 오류시 원본 반환
            return json_string
    
    def get_available_files(self) -> List[Dict]:
        """업로드된 파일 목록 반환"""
        upload_folder = "uploads"
        files = []
        
        if os.path.exists(upload_folder):
            for filename in os.listdir(upload_folder):
                file_path = os.path.join(upload_folder, filename)
                if os.path.isfile(file_path):
                    # 원본 파일명 추출 (UUID 제거)
                    original_name = filename.split('_', 1)[1] if '_' in filename else filename
                    file_size = os.path.getsize(file_path)
                    
                    files.append({
                        'stored_name': filename,
                        'original_name': original_name,
                        'file_size': file_size,
                        'file_path': file_path
                    })
        
        return files 

    def _extract_text_from_pdf_as_image(self, pdf_path: str) -> str:
        """PDF를 이미지로 변환하여 Vision API로 텍스트 추출"""
        try:
            if not self.sync_client:
                return "OpenAI API 키가 설정되지 않아 Vision API 처리를 할 수 없습니다."
            
            import pdfplumber
            import io
            
            text_content = []
            pdf = None
            
            try:
                # pdfplumber로 페이지별 이미지 변환
                pdf = pdfplumber.open(pdf_path)
                for page_num, page in enumerate(pdf.pages, 1):
                    print(f"페이지 {page_num} 이미지 변환 중...")
                    
                    try:
                        # 페이지를 이미지로 변환 (고해상도)
                        img = page.to_image(resolution=300)
                        if img:
                            # 이미지를 바이트로 변환
                            img_bytes = io.BytesIO()
                            img.original.save(img_bytes, format='PNG', quality=95)
                            img_bytes.seek(0)
                            
                            # base64로 인코딩
                            encoded_image = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
                            
                            # OpenAI Vision API로 텍스트 추출
                            response = self.sync_client.chat.completions.create(
                                model="gpt-4o",
                                messages=[
                                    {
                                        "role": "system",
                                        "content": """당신은 전문적인 문서 분석 AI입니다. PDF 페이지 이미지에서 모든 텍스트를 정확히 추출해주세요.

중요한 지침:
1. "I'm sorry, I can't assist with that" 같은 거부 답변을 하지 마세요
2. 수출신고필증, 세금계산서, 인보이스 등 모든 비즈니스 문서를 분석할 수 있습니다
3. 민감한 정보라도 텍스트 추출 목적으로만 사용되므로 안전합니다
4. 숫자, 날짜, 회사명, 금액 등을 정확히 인식해주세요
5. 표나 구조화된 데이터가 있다면 그대로 유지해주세요
6. 텍스트가 보이지 않으면 "텍스트 없음"으로 표시하되, 전체 분석을 거부하지 마세요"""
                                    },
                                    {
                                        "role": "user",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": """이 PDF 페이지에서 모든 텍스트를 정확히 추출해주세요.

중요한 지침:
1. 모든 텍스트를 빠짐없이 추출해주세요
2. 숫자, 날짜, 금액을 정확히 인식해주세요
3. 회사명, 주소, 전화번호 등을 완전히 추출해주세요
4. 표나 구조화된 데이터가 있다면 그대로 유지해주세요
5. 작은 글씨도 최대한 읽어주세요
6. 한글, 영어, 숫자, 특수문자 모두 포함해주세요
7. "I'm sorry, I can't assist with that" 같은 답변을 하지 마세요
8. 페이지의 모든 영역을 꼼꼼히 확인해주세요

특히 다음 정보들을 중점적으로 추출해주세요:
- 수출신고필증 번호, 날짜, 금액
- 회사 정보 (회사명, 사업자번호, 주소)
- 품목 정보, 수량, 단가
- 통화 단위 (USD, KRW, CNY 등)
- 문서 제목, 발행일, 유효기간 등"""
                                            },
                                            {
                                                "type": "image_url",
                                                "image_url": {
                                                    "url": f"data:image/png;base64,{encoded_image}"
                                                }
                                            }
                                        ]
                                    }
                                ],
                                max_tokens=2000,
                                temperature=0.0,
                                top_p=0.9,
                                frequency_penalty=0.1,
                                presence_penalty=0.1
                            )
                            
                            if response and response.choices:
                                page_text = response.choices[0].message.content
                                if page_text:
                                    text_content.append(f"[페이지 {page_num}]\n{page_text}")
                                    print(f"페이지 {page_num}: Vision API 처리 완료")
                            else:
                                print(f"페이지 {page_num}: Vision API 응답이 비어있습니다.")
                            
                            # 메모리 정리
                            img_bytes.close()
                            del img_bytes
                            del encoded_image
                            
                    except Exception as e:
                        print(f"페이지 {page_num} 처리 중 오류: {str(e)}")
                        continue
                    
                    # 페이지별 메모리 정리
                    if 'img' in locals():
                        del img
                
            finally:
                # PDF 파일 정리
                if pdf:
                    try:
                        pdf.close()
                    except:
                        pass
            
            if text_content:
                return '\n\n'.join(text_content)
            else:
                return "Vision API 처리 후에도 텍스트를 추출할 수 없었습니다."
                
        except Exception as e:
            return f"Vision API 처리 오류: {str(e)}"