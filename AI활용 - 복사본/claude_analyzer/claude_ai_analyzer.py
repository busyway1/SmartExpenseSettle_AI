import os
import anthropic
from typing import Dict, List, Optional
import base64
import json
import io
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import time
import gc
import sys

# 상위 디렉토리의 prompts 폴더를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from prompts.prompt_manager import PromptManager
from prompts.document_type_classification import get_document_type_classification_prompt
from prompts.tax_invoice import get_tax_invoice_prompt
from prompts.invoice import get_invoice_prompt
from prompts.bill_of_lading import get_bill_of_lading_prompt
from prompts.transfer_receipt import get_transfer_receipt_prompt
from prompts.export_declaration import get_export_declaration_prompt

from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2
import re

class ClaudeAIAnalyzer:
    def __init__(self, api_key: str = "", use_advanced_opencv: bool = False, enable_rate_limit: bool = False):
        """Claude AI 분석기 초기화"""
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY', "")
        if self.api_key:
            # 타임아웃 설정 추가
            self.client = anthropic.AsyncAnthropic(
                api_key=self.api_key,
                timeout=60.0  # 60초 타임아웃
            )
            self.sync_client = anthropic.Anthropic(
                api_key=self.api_key,
                timeout=60.0  # 60초 타임아웃
            )
        else:
            print("경고: Anthropic API 키가 설정되지 않았습니다.")
            self.client = None
            self.sync_client = None
        
        # 스레드 풀 생성 (파일 I/O 작업용)
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # 속도 제한 관련 설정
        self.max_retries = 5
        self.base_delay = 1.0  # 기본 대기 시간 (초)
        
        # 속도 제한 활성화 여부
        self.enable_rate_limit = enable_rate_limit
        
        # API 호출 제한 설정 (Sonnet 계정 기준 - 더 관대하게 설정)
        self.requests_per_minute = 20  # 분당 최대 요청 수 (5 → 20으로 증가)
        self.requests_per_hour = 200   # 시간당 최대 요청 수 (100 → 200으로 증가)
        self.last_request_time = 0  # 마지막 요청 시간
        self.request_count_minute = 0  # 분당 요청 카운트
        self.request_count_hour = 0  # 시간당 요청 카운트
        
        # 이미지 개선 설정
        self.use_advanced_opencv = use_advanced_opencv
        if use_advanced_opencv:
            print("고급 OpenCV 이미지 개선 모드가 활성화되었습니다.")
        
        if enable_rate_limit:
            print("속도 제한 모드가 활성화되었습니다.")
        else:
            print("속도 제한 모드가 비활성화되었습니다. (최대 속도로 실행)")
    
    async def _rate_limit_check(self):
        """API 호출 속도 제한 확인 및 대기"""
        # 속도 제한이 비활성화된 경우 체크하지 않음
        if not self.enable_rate_limit:
            return
            
        current_time = time.time()
        
        # 1분 타이머 리셋
        if current_time - self.last_request_time >= 60:
            self.request_count_minute = 0
            self.last_request_time = current_time
        
        # 1시간 타이머 리셋
        if current_time - self.last_request_time >= 3600:
            self.request_count_hour = 0
        
        # 분당 제한 확인
        if self.request_count_minute >= self.requests_per_minute:
            wait_time = 60 - (current_time - self.last_request_time)
            if wait_time > 0:
                print(f"분당 속도 제한 도달. {wait_time:.1f}초 대기...")
                await asyncio.sleep(wait_time)
                self.request_count_minute = 0
                self.last_request_time = time.time()
        
        # 시간당 제한 확인
        if self.request_count_hour >= self.requests_per_hour:
            wait_time = 3600 - (current_time - self.last_request_time)
            if wait_time > 0:
                print(f"시간당 속도 제한 도달. {wait_time:.1f}초 대기...")
                await asyncio.sleep(wait_time)
                self.request_count_hour = 0
                self.last_request_time = time.time()
    
    async def _retry_api_call_async(self, api_call_func, *args, **kwargs):
        """비동기 API 호출에 대한 재시도 로직 (속도 제한 포함)"""
        for attempt in range(self.max_retries):
            try:
                # 속도 제한 확인
                await self._rate_limit_check()
                
                # API 호출
                result = await api_call_func(*args, **kwargs)
                
                # 성공 시 카운터 증가
                self.request_count_minute += 1
                self.request_count_hour += 1
                
                return result
                
            except anthropic.RateLimitError as e:
                if attempt < self.max_retries - 1:
                    # 지수 백오프로 대기 시간 계산
                    delay = self.base_delay * (2 ** attempt)
                    print(f"속도 제한 도달. {delay:.1f}초 후 재시도... (시도 {attempt + 1}/{self.max_retries})")
                    await asyncio.sleep(delay)
                else:
                    raise e
            except Exception as e:
                error_msg = str(e).lower()
                if "rate_limit" in error_msg or "429" in error_msg:
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt)
                        print(f"속도 제한 도달. {delay:.1f}초 후 재시도... (시도 {attempt + 1}/{self.max_retries})")
                        await asyncio.sleep(delay)
                    else:
                        raise e
                elif "connection" in error_msg or "timeout" in error_msg or "network" in error_msg:
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt) + 2  # 연결 오류는 추가 대기
                        print(f"연결 오류 발생. {delay:.1f}초 후 재시도... (시도 {attempt + 1}/{self.max_retries})")
                        await asyncio.sleep(delay)
                    else:
                        print(f"최대 재시도 횟수 초과. 연결 오류: {str(e)}")
                        raise e
                else:
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt)
                        print(f"API 오류 발생. {delay:.1f}초 후 재시도... (시도 {attempt + 1}/{self.max_retries}) - 오류: {str(e)}")
                        await asyncio.sleep(delay)
                    else:
                        print(f"최대 재시도 횟수 초과. API 오류: {str(e)}")
                        raise e
    
    def _rate_limit_check_sync(self):
        """동기 API 호출 속도 제한 확인 및 대기"""
        # 속도 제한이 비활성화된 경우 체크하지 않음
        if not self.enable_rate_limit:
            return
            
        current_time = time.time()
        
        # 1분 타이머 리셋
        if current_time - self.last_request_time >= 60:
            self.request_count_minute = 0
            self.last_request_time = current_time
        
        # 1시간 타이머 리셋
        if current_time - self.last_request_time >= 3600:
            self.request_count_hour = 0
        
        # 분당 제한 확인
        if self.request_count_minute >= self.requests_per_minute:
            wait_time = 60 - (current_time - self.last_request_time)
            if wait_time > 0:
                print(f"분당 속도 제한 도달. {wait_time:.1f}초 대기...")
                time.sleep(wait_time)
                self.request_count_minute = 0
                self.last_request_time = time.time()
        
        # 시간당 제한 확인
        if self.request_count_hour >= self.requests_per_hour:
            wait_time = 3600 - (current_time - self.last_request_time)
            if wait_time > 0:
                print(f"시간당 속도 제한 도달. {wait_time:.1f}초 대기...")
                time.sleep(wait_time)
                self.request_count_hour = 0
                self.last_request_time = time.time()
    
    def _retry_api_call_sync(self, api_call_func, *args, **kwargs):
        """동기 API 호출에 대한 재시도 로직 (속도 제한 포함)"""
        for attempt in range(self.max_retries):
            try:
                # 속도 제한 확인
                self._rate_limit_check_sync()
                
                # API 호출
                result = api_call_func(*args, **kwargs)
                
                # 성공 시 카운터 증가
                self.request_count_minute += 1
                self.request_count_hour += 1
                
                return result
                
            except anthropic.RateLimitError as e:
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    print(f"속도 제한 도달. {delay:.1f}초 후 재시도... (시도 {attempt + 1}/{self.max_retries})")
                    time.sleep(delay)
                else:
                    raise e
            except Exception as e:
                error_msg = str(e).lower()
                if "rate_limit" in error_msg or "429" in error_msg:
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt)
                        print(f"속도 제한 도달. {delay:.1f}초 후 재시도... (시도 {attempt + 1}/{self.max_retries})")
                        time.sleep(delay)
                    else:
                        raise e
                elif "connection" in error_msg or "timeout" in error_msg or "network" in error_msg:
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt) + 2  # 연결 오류는 추가 대기
                        print(f"연결 오류 발생. {delay:.1f}초 후 재시도... (시도 {attempt + 1}/{self.max_retries})")
                        time.sleep(delay)
                    else:
                        print(f"최대 재시도 횟수 초과. 연결 오류: {str(e)}")
                        raise e
                else:
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt)
                        print(f"API 오류 발생. {delay:.1f}초 후 재시도... (시도 {attempt + 1}/{self.max_retries}) - 오류: {str(e)}")
                        time.sleep(delay)
                    else:
                        print(f"최대 재시도 횟수 초과. API 오류: {str(e)}")
                        raise e
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.executor:
            self.executor.shutdown(wait=True)
    
    def _enhance_image_for_ocr(self, image: Image.Image) -> Image.Image:
        """OCR 정확도 향상을 위한 이미지 개선 (한글 최적화)"""
        # 이미지 크기 확대 (3배로 증가 - 한글 인식 향상)
        width, height = image.size
        enhanced = image.resize((width * 3, height * 3), Image.Resampling.LANCZOS)
        
        # 대비 향상 (한글 텍스트 가독성 개선)
        enhancer = ImageEnhance.Contrast(enhanced)
        enhanced = enhancer.enhance(1.8)  # 대비 강화
        
        # 선명도 향상 (한글 획 선명도 개선)
        enhancer = ImageEnhance.Sharpness(enhanced)
        enhanced = enhancer.enhance(1.5)  # 선명도 강화
        
        # 밝기 조정 (한글 가독성 향상)
        enhancer = ImageEnhance.Brightness(enhanced)
        enhanced = enhancer.enhance(1.2)  # 밝기 증가
        
        return enhanced
    
    def _enhance_image_with_opencv(self, image: Image.Image) -> Image.Image:
        """OpenCV를 사용한 고급 이미지 개선"""
        # PIL 이미지를 OpenCV 형식으로 변환
        img_array = np.array(image)
        
        # 그레이스케일로 변환
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # 노이즈 제거
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # 적응형 히스토그램 평활화
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # 모폴로지 연산으로 텍스트 선명화
        kernel = np.ones((1,1), np.uint8)
        enhanced = cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, kernel)
        
        # 다시 PIL 이미지로 변환
        enhanced_pil = Image.fromarray(enhanced)
        
        return enhanced_pil
    
    def _enhance_image_advanced_opencv(self, image: Image.Image) -> Image.Image:
        """고급 OpenCV 이미지 개선 (한글 텍스트 최적화)"""
        # PIL 이미지를 OpenCV 형식으로 변환
        img_array = np.array(image)
        
        # 그레이스케일로 변환
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # 이미지 크기 확대 (한글 인식 향상)
        height, width = gray.shape
        enlarged = cv2.resize(gray, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)
        
        # 노이즈 제거 (한글 텍스트 보존)
        denoised = cv2.fastNlMeansDenoising(enlarged, None, 10, 7, 21)
        
        # 적응형 히스토그램 평활화 (한글 대비 개선)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # 이진화 (한글 텍스트 최적화)
        # 방법 1: 적응형 이진화
        binary1 = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 5
        )
        
        # 방법 2: Otsu 이진화
        _, binary2 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 두 방법 결합 (한글 텍스트 보존)
        binary = cv2.bitwise_or(binary1, binary2)
        
        # 모폴로지 연산으로 한글 텍스트 정리
        kernel = np.ones((2,2), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        # 작은 노이즈 제거
        kernel = np.ones((1,1), np.uint8)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
        
        # 다시 PIL 이미지로 변환
        enhanced_pil = Image.fromarray(cleaned)
        
        return enhanced_pil
    

    
    async def extract_text_from_file_async(self, file_path: str) -> str:
        """파일에서 텍스트 추출 (비동기)"""
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, self.extract_text_from_file, file_path
        )
    
    def extract_text_from_file(self, file_path: str) -> str:
        """파일에서 텍스트 추출 (동기)"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.pdf':
                return self._extract_text_from_pdf(file_path)
            elif file_ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif']:
                return self._extract_text_from_image(file_path)
            elif file_ext in ['.txt', '.md']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                return f"지원하지 않는 파일 형식: {file_ext}"
                
        except Exception as e:
            return f"파일 읽기 오류: {str(e)}"
    
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """PDF에서 텍스트 추출"""
        try:
            # PyMuPDF로 먼저 시도
            text = self._extract_with_pymupdf(pdf_path)
            if text.strip():
                return text
            
            # pdfplumber로 시도
            text = self._extract_with_pdfplumber(pdf_path)
            if text.strip():
                return text
            
            # 스캔된 PDF로 간주하고 OCR 처리
            return self._extract_text_from_scanned_pdf(pdf_path)
            
        except Exception as e:
            return f"PDF 처리 오류: {str(e)}"
    
    def _extract_with_pymupdf(self, pdf_path: str) -> str:
        """PyMuPDF를 사용한 텍스트 추출"""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except ImportError:
            return ""
        except Exception:
            return ""
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> str:
        """pdfplumber를 사용한 텍스트 추출"""
        try:
            import pdfplumber
            text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except ImportError:
            return ""
        except Exception:
            return ""
    
    def _extract_text_from_scanned_pdf(self, pdf_path: str) -> str:
        """스캔된 PDF에서 Claude Vision으로 문서 유형별 정보 추출"""
        try:
            if not self.sync_client:
                return "Anthropic API 키가 설정되지 않았습니다."
            
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            text_content = []
            
            # 모든 페이지를 병렬로 처리하기 위한 태스크 생성
            async def process_page_async(page_num: int, page):
                # 페이지를 이미지로 렌더링 (한글 인식 향상을 위한 고해상도)
                mat = fitz.Matrix(2.5, 2.5)  # 2.5배 확대로 한글 인식 향상
                pix = page.get_pixmap(matrix=mat)
                
                # PIL 이미지로 변환
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # 이미지 개선
                if self.use_advanced_opencv:
                    enhanced_img = self._enhance_image_advanced_opencv(img)
                else:
                    enhanced_img = self._enhance_image_for_ocr(img)
                
                # 이미지 압축으로 전송 크기 최소화 (한글 인식 향상을 위한 고품질)
                img_bytes = io.BytesIO()
                enhanced_img.save(img_bytes, format='PNG', quality=100)  # 최고 품질로 한글 인식 향상
                img_bytes.seek(0)
                
                # base64로 인코딩
                encoded_image = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
                
                # 먼저 문서 유형 분류
                async def classify_document_type():
                    return await self.client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=500,
                        system="당신은 문서를 정확히 인식하고 분류하는 전문 AI입니다. 한글 텍스트와 숫자는 특히 매우 정확하게 읽어주세요.",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "이 이미지의 문서 유형을 분류해주세요. 한글 텍스트를 매우 정확하게 읽어서 세금계산서, 인보이스, BL, 송금증, 수출신고필증, Packing List 중에서 선택해주세요. 한글 텍스트 인식에 특별히 주의해주세요."
                                    },
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "image/png",
                                            "data": encoded_image
                                        }
                                    }
                                ]
                            }
                        ]
                    )
                
                # 문서 유형 분류 실행
                classification_response = await self._retry_api_call_async(classify_document_type)
                
                if classification_response and classification_response.content:
                    doc_type = classification_response.content[0].text.strip()
                    
                    # 문서 유형 매핑
                    doc_type_mapping = {
                        "수출신고필증": "수출신고필증",
                        "세금계산서": "세금계산서", 
                        "인보이스": "인보이스",
                        "BL": "BL",
                        "이체확인증": "송금증",
                        "송금증": "송금증",
                        "Packing List": "Packing List",
                        "미분류": "기타"
                    }
                    
                    # 매핑된 문서 유형 사용
                    mapped_type = doc_type_mapping.get(doc_type, doc_type)
                    
                    # 문서 유형별 프롬프트 선택
                    file_name = os.path.basename(pdf_path)
                    if mapped_type == "세금계산서":
                        prompt = get_tax_invoice_prompt("", file_name, page_num + 1)
                    elif mapped_type == "인보이스":
                        prompt = get_invoice_prompt("", file_name, page_num + 1)
                    elif mapped_type == "BL":
                        prompt = get_bill_of_lading_prompt("", file_name, page_num + 1)
                    elif mapped_type == "송금증":
                        prompt = get_transfer_receipt_prompt("", file_name, page_num + 1)
                    elif mapped_type == "수출신고필증":
                        prompt = get_export_declaration_prompt("", file_name, page_num + 1)
                    else:
                        # 기본 프롬프트
                        prompt = f"이 {mapped_type} 문서에서 중요한 정보를 추출해주세요."
                    
                    # 문서 유형별 정보 추출
                    async def extract_document_info():
                        return await self.client.messages.create(
                            model="claude-sonnet-4-20250514",
                            max_tokens=2000,
                            system="당신은 문서를 정확히 분석하는 전문 AI입니다. 한글 텍스트를 매우 정확하게 읽고, 숫자와 한글을 정확히 구분해서 추출해주세요. 특히 한글 회사명, 주소, 금액 등을 정확히 인식해주세요.",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": prompt
                                        },
                                        {
                                            "type": "image",
                                            "source": {
                                                "type": "base64",
                                                "media_type": "image/png",
                                                "data": encoded_image
                                            }
                                        }
                                    ]
                                }
                            ]
                        )
                    
                    # 정보 추출 실행
                    extraction_response = await self._retry_api_call_async(extract_document_info)
                    
                    if extraction_response and extraction_response.content:
                        extracted_info = extraction_response.content[0].text.strip()
                        if extracted_info:
                            return f"[페이지 {page_num + 1}]\n[문서유형: {mapped_type}]\n{extracted_info}"
                
                return None
            
            # 비동기 처리를 위한 이벤트 루프 생성
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # 모든 페이지를 병렬로 처리
                tasks = [process_page_async(page_num, doc[page_num]) for page_num in range(len(doc))]
                results = loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                
                # 결과 수집
                for result in results:
                    if isinstance(result, str) and result:
                        text_content.append(result)
                    elif isinstance(result, Exception):
                        print(f"페이지 처리 오류: {str(result)}")
                
            finally:
                loop.close()
                doc.close()
            
            if text_content:
                return '\n\n'.join(text_content)
            else:
                return "문서 정보 추출에 실패했습니다."
                
        except Exception as e:
            return f"PDF 처리 오류: {str(e)}"
    
    def _extract_text_from_image(self, image_path: str) -> str:
        """이미지에서 문서 유형별 정보 추출 (Claude Vision 최적화)"""
        try:
            if not self.sync_client:
                return "Anthropic API 키가 설정되지 않았습니다."
            
            # 이미지 개선 처리
            try:
                with Image.open(image_path) as img:
                    # 이미지 개선
                    if self.use_advanced_opencv:
                        enhanced_img = self._enhance_image_advanced_opencv(img)
                    else:
                        enhanced_img = self._enhance_image_for_ocr(img)
                    
                    # 이미지 압축으로 전송 크기 최소화 (한글 인식 향상을 위한 고품질)
                    img_bytes = io.BytesIO()
                    enhanced_img.save(img_bytes, format='PNG', quality=100)  # 최고 품질로 한글 인식 향상
                    img_bytes.seek(0)
                    
                    # base64로 인코딩
                    encoded_image = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
                    
                    # 먼저 문서 유형 분류
                    def classify_document_type():
                        return self.sync_client.messages.create(
                            model="claude-sonnet-4-20250514",
                            max_tokens=500,
                            system="당신은 문서를 정확히 인식하고 분류하는 전문 AI입니다. 한글 텍스트를 매우 정확하게 읽어주세요.",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "이 이미지의 문서 유형을 분류해주세요. 한글 텍스트를 매우 정확하게 읽어서 세금계산서, 인보이스, BL, 송금증, 수출신고필증, Packing List 중에서 선택해주세요. 한글 텍스트 인식에 특별히 주의해주세요."
                                        },
                                        {
                                            "type": "image",
                                            "source": {
                                                "type": "base64",
                                                "media_type": "image/png",
                                                "data": encoded_image
                                            }
                                        }
                                    ]
                                }
                            ]
                        )
                    
                    # 문서 유형 분류 실행
                    classification_response = self._retry_api_call_sync(classify_document_type)
                    
                    if classification_response and classification_response.content:
                        doc_type = classification_response.content[0].text.strip()
                        
                        # 문서 유형 매핑
                        doc_type_mapping = {
                            "수출신고필증": "수출신고필증",
                            "세금계산서": "세금계산서", 
                            "인보이스": "인보이스",
                            "BL": "BL",
                            "이체확인증": "송금증",
                            "송금증": "송금증",
                            "Packing List": "Packing List",
                            "미분류": "기타"
                        }
                        
                        # 매핑된 문서 유형 사용
                        mapped_type = doc_type_mapping.get(doc_type, doc_type)
                        
                        # 문서 유형별 프롬프트 선택
                        file_name = os.path.basename(image_path)
                        if mapped_type == "세금계산서":
                            prompt = get_tax_invoice_prompt("", file_name, 1)
                        elif mapped_type == "인보이스":
                            prompt = get_invoice_prompt("", file_name, 1)
                        elif mapped_type == "BL":
                            prompt = get_bill_of_lading_prompt("", file_name, 1)
                        elif mapped_type == "송금증":
                            prompt = get_transfer_receipt_prompt("", file_name, 1)
                        elif mapped_type == "수출신고필증":
                            prompt = get_export_declaration_prompt("", file_name, 1)
                        else:
                            # 기본 프롬프트
                            prompt = f"이 {mapped_type} 문서에서 중요한 정보를 추출해주세요."
                        
                        # 문서 유형별 정보 추출
                        def extract_document_info():
                            return self.sync_client.messages.create(
                                model="claude-sonnet-4-20250514",
                                max_tokens=2000,
                                system="당신은 문서를 정확히 분석하는 전문 AI입니다. 한글 텍스트를 매우 정확하게 읽고, 숫자와 한글을 정확히 구분해서 추출해주세요. 특히 한글 회사명, 주소, 금액 등을 정확히 인식해주세요.",
                                messages=[
                                    {
                                        "role": "user",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": prompt
                                            },
                                            {
                                                "type": "image",
                                                "source": {
                                                    "type": "base64",
                                                    "media_type": "image/png",
                                                    "data": encoded_image
                                                }
                                            }
                                        ]
                                    }
                                ]
                            )
                        
                        # 정보 추출 실행
                        extraction_response = self._retry_api_call_sync(extract_document_info)
                        
                        if extraction_response and extraction_response.content:
                            extracted_info = extraction_response.content[0].text.strip()
                            if extracted_info:
                                return f"[문서유형: {mapped_type}]\n{extracted_info}"
                    
                    return "문서 정보 추출에 실패했습니다."
                        
            except Exception as e:
                return f"이미지 처리 오류: {str(e)}"
                
        except Exception as e:
            return f"문서 정보 추출 오류: {str(e)}"
    
    def analyze_document(self, file_path: str, custom_prompt: Optional[str] = None) -> Dict:
        """문서 분석 (동기)"""
        start_time = time.time()
        
        try:
            # 텍스트 추출
            text = self.extract_text_from_file(file_path)
            if not text or text.startswith("오류"):
                return {"error": text}
            
            # 총 페이지 수 계산
            total_pages = self._count_pages(text)
            
            # 문서 분석
            result = self._analyze_document_by_type(text, file_path)
            
            # 분석 시간 계산
            analysis_time = time.time() - start_time
            
            # 결과에 시간과 페이지 수 정보 추가
            if result.get("success"):
                result["analysis_time"] = analysis_time
                result["total_pages"] = total_pages
                result["analysis"] = self._combine_document_type_results(
                    result.get("detailed_results", {}), 
                    analysis_time, 
                    total_pages
                )
            
            return result
            
        except Exception as e:
            analysis_time = time.time() - start_time
            return {
                "error": f"문서 분석 오류: {str(e)}",
                "analysis_time": analysis_time
            }
    
    def _analyze_document_by_type(self, text: str, file_path: str) -> Dict:
        """문서 타입별 분석 (동기) - 비동기 처리로 개선"""
        try:
            # 문서 타입 분류 (동기)
            doc_types = self._classify_document_types_sync(text)
            
            # 비동기 처리를 위해 이벤트 루프 생성
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # 비동기로 내용 분석 실행
                results = loop.run_until_complete(
                    self._analyze_content_async(doc_types, text, file_path)
                )
                
                # 결과 결합
                combined_result = self._combine_document_type_results(results)
                
                return {
                    "success": True,
                    "document_types": list(results.keys()),
                    "analysis": combined_result,
                    "detailed_results": results
                }
                
            finally:
                loop.close()
            
        except Exception as e:
            return {"error": f"문서 타입별 분석 오류: {str(e)}"}
    
    def _classify_document_types_sync(self, text: str) -> Dict[str, List[int]]:
        """문서 타입 분류 (동기)"""
        try:
            print(f"DEBUG: 텍스트 길이: {len(text)}")
            print(f"DEBUG: 텍스트 시작 부분: {text[:200]}...")
            
            # 페이지별로 분류
            pages = text.split('[페이지')
            print(f"DEBUG: 페이지 분할 결과 - 총 {len(pages)}개 부분")
            
            doc_types = {}
            
            # [페이지 형식이 아닌 경우 전체 텍스트를 하나의 페이지로 처리
            if len(pages) <= 1:
                print(f"DEBUG: [페이지 형식이 아님. 전체 텍스트를 하나의 페이지로 처리")
                page_content = text
                page_num = "1"
                print(f"DEBUG: 전체 텍스트 처리 - 내용길이: {len(page_content)}")
                
                # 기존 프롬프트 사용
                prompt = get_document_type_classification_prompt(page_content[:1000])
                
                def api_call():
                    return self.sync_client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=1000,
                        system="당신은 문서를 정확히 인식하고 분류하는 전문 AI입니다. 한글 텍스트를 매우 정확하게 읽어주세요.",
                        messages=[
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    )
                
                response = self._retry_api_call_sync(api_call)
                
                if response and response.content:
                    doc_type = response.content[0].text.strip()
                    print(f"DEBUG: 전체 텍스트 - API 응답 성공, 문서타입: {doc_type}")
                    
                    # 프롬프트에서 정의된 문서 타입으로 매핑
                    doc_type_mapping = {
                        "수출신고필증": "수출신고필증",
                        "세금계산서": "세금계산서", 
                        "인보이스": "인보이스",
                        "BL": "BL",
                        "이체확인증": "송금증",
                        "Packing List": "Packing List",
                        "미분류": "기타"
                    }
                    
                    mapped_type = doc_type_mapping.get(doc_type, doc_type)
                    page_number = int(page_num) if page_num.isdigit() else 1
                    
                    if mapped_type not in doc_types:
                        doc_types[mapped_type] = []
                    doc_types[mapped_type].append(page_number)
                    print(f"DEBUG: 전체 텍스트 - 매핑된 타입: {mapped_type}, 페이지번호: {page_number}")
                else:
                    print(f"DEBUG: 전체 텍스트 - API 응답 실패 또는 빈 응답")
            else:
                # 기존 [페이지 형식 처리
                for i, page in enumerate(pages[1:], 1):  # 첫 번째는 빈 문자열
                    if not page.strip():
                        print(f"DEBUG: 페이지 {i} - 빈 내용, 건너뜀")
                        continue
                    
                    page_num = page.split(']')[0].strip()
                    page_content = page.split(']', 1)[1] if ']' in page else page
                    print(f"DEBUG: 페이지 {i} 처리 중 - 페이지번호: {page_num}, 내용길이: {len(page_content)}")
                    
                    # 기존 프롬프트 사용
                    prompt = get_document_type_classification_prompt(page_content[:1000])
                    
                    def api_call():
                        return self.sync_client.messages.create(
                            model="claude-sonnet-4-20250514",
                            max_tokens=1000,
                            system="당신은 문서를 정확히 인식하고 분류하는 전문 AI입니다. 한글 텍스트를 매우 정확하게 읽어주세요.",
                            messages=[
                                {
                                    "role": "user",
                                    "content": prompt
                                }
                            ]
                        )
                    
                    response = self._retry_api_call_sync(api_call)
                    
                    if response and response.content:
                        doc_type = response.content[0].text.strip()
                        print(f"DEBUG: 페이지 {i} - API 응답 성공, 문서타입: {doc_type}")
                        
                        # 프롬프트에서 정의된 문서 타입으로 매핑
                        doc_type_mapping = {
                            "수출신고필증": "수출신고필증",
                            "세금계산서": "세금계산서", 
                            "인보이스": "인보이스",
                            "BL": "BL",
                            "이체확인증": "송금증",
                            "Packing List": "Packing List",
                            "미분류": "기타"
                        }
                        
                        mapped_type = doc_type_mapping.get(doc_type, doc_type)
                        page_number = int(page_num) if page_num.isdigit() else None
                        
                        if mapped_type not in doc_types:
                            doc_types[mapped_type] = []
                        doc_types[mapped_type].append(page_number)
                        print(f"DEBUG: 페이지 {i} - 매핑된 타입: {mapped_type}, 페이지번호: {page_number}")
                    else:
                        print(f"DEBUG: 페이지 {i} - API 응답 실패 또는 빈 응답")
                        if response:
                            print(f"DEBUG: 페이지 {i} - 응답 내용: {response}")
                        else:
                            print(f"DEBUG: 페이지 {i} - 응답이 None")
            
            print(f"DEBUG: 최종 분류 결과: {doc_types}")
            return doc_types
            
        except Exception as e:
            print(f"문서 타입 분류 오류: {str(e)}")
            return {}
    
    def _combine_document_type_results(self, results: Dict, analysis_time: float = None, total_pages: int = None) -> str:
        """문서 타입별 결과 결합 (동기)"""
        try:
            if not results:
                print(f"DEBUG: results가 비어있음. results 타입: {type(results)}, 내용: {results}")
                return "분석할 문서를 찾을 수 없습니다. (문서 타입 분류 실패 또는 API 오류)"
            
            print(f"DEBUG: results 내용: {results}")
            print(f"DEBUG: results 키: {list(results.keys())}")
            print(f"DEBUG: 각 키별 결과 수: {[(k, len(v) if isinstance(v, list) else 'N/A') for k, v in results.items()]}")
            
            combined_parts = []
            
            # 분석 요약 정보 추가
            if analysis_time is not None or total_pages is not None:
                combined_parts.append("=" * 80)
                combined_parts.append("📊 분석 요약 정보")
                combined_parts.append("=" * 80)
                
                if analysis_time is not None:
                    combined_parts.append(f"⏱️  분석 소요 시간: {analysis_time:.2f}초")
                
                if total_pages is not None:
                    combined_parts.append(f"📄 총 분석 페이지 수: {total_pages}페이지")
                
                # 문서 타입별 통계
                doc_type_counts = {}
                for doc_type, doc_results in results.items():
                    doc_type_counts[doc_type] = len(doc_results)
                
                combined_parts.append(f"📋 분석된 문서 유형: {', '.join([f'{doc_type}({count}개)' for doc_type, count in doc_type_counts.items()])}")
                combined_parts.append("=" * 80)
                combined_parts.append("")
            
            # 각 문서 타입별 상세 분석 결과
            for doc_type, doc_results in results.items():
                combined_parts.append("🔍" + "=" * 78)
                combined_parts.append(f"📋 {doc_type.upper()} 분석 결과 ({len(doc_results)}개 문서)")
                combined_parts.append("=" * 80)
                
                for i, doc_result in enumerate(doc_results):
                    combined_parts.append(f"\n📄 [문서 {i+1}]")
                    
                    # 페이지 정보
                    if doc_result.get('page_number'):
                        combined_parts.append(f"📍 페이지: {doc_result['page_number']}")
                    
                    # 분석 결과 (가독성 개선)
                    analysis_text = doc_result.get('analysis', '분석 결과 없음')
                    if analysis_text and analysis_text != '분석 결과 없음':
                        # 분석 결과를 줄바꿈으로 구분하여 가독성 향상
                        formatted_analysis = self._format_analysis_text(analysis_text)
                        combined_parts.append(f"\n📝 분석 결과:\n{formatted_analysis}")
                    else:
                        combined_parts.append(f"\n❌ 분석 결과: {analysis_text}")
                    
                    combined_parts.append("-" * 80)
            
            return "\n".join(combined_parts)
            
        except Exception as e:
            return f"결과 결합 오류: {str(e)}"
    
    async def analyze_document_async(self, file_path: str, custom_prompt: Optional[str] = None) -> Dict:
        """문서 분석 (비동기)"""
        start_time = time.time()
        
        try:
            # 텍스트 추출
            text = await self.extract_text_from_file_async(file_path)
            if not text or text.startswith("오류"):
                return {"error": text}
            
            # 총 페이지 수 계산
            total_pages = self._count_pages(text)
            
            # 문서 분석
            result = await self._analyze_document_by_type_async(text, file_path)
            
            # 분석 시간 계산
            analysis_time = time.time() - start_time
            
            # 결과에 시간과 페이지 수 정보 추가
            if result.get("success"):
                result["analysis_time"] = analysis_time
                result["total_pages"] = total_pages
                result["analysis"] = await self._combine_document_type_results_async(
                    result.get("detailed_results", {}), 
                    analysis_time, 
                    total_pages
                )
            
            return result
            
        except Exception as e:
            analysis_time = time.time() - start_time
            return {
                "error": f"문서 분석 오류: {str(e)}",
                "analysis_time": analysis_time
            }
    
    async def _analyze_content_async(self, doc_types: Dict[str, List[int]], text: str, file_path: str) -> Dict:
        """문서 내용 분석 (비동기) - 모든 문서 타입을 병렬로 처리"""
        try:
            print(f"DEBUG: _analyze_content_async 시작 - doc_types: {doc_types}")
            results = {}
            
            # 모든 문서 타입에 대해 병렬로 처리할 태스크 생성
            tasks = []
            
            for doc_type, pages in doc_types.items():
                print(f"DEBUG: 문서 타입 '{doc_type}' 처리 중 - 페이지: {pages}")
                if pages:
                    # 각 문서 타입별로 개별 문서 식별
                    individual_docs = self._identify_individual_documents(doc_type, pages, text)
                    print(f"DEBUG: 개별 문서 식별 결과 - {len(individual_docs)}개 문서")
                    
                    # 각 개별 문서에 대해 분석 태스크 생성
                    for i, doc_info in enumerate(individual_docs):
                        doc_text = doc_info['text']
                        doc_pages = doc_info['pages']
                        print(f"DEBUG: 문서 {i} 분석 태스크 생성 - 텍스트 길이: {len(doc_text)}")
                        
                        task = self._extract_info_by_document_type_async(
                            doc_type, doc_text, i, file_path, doc_pages[0] if doc_pages else None
                        )
                        tasks.append((doc_type, task))
                else:
                    print(f"DEBUG: 문서 타입 '{doc_type}' - 페이지가 없음, 건너뜀")
            
            # 모든 태스크를 병렬로 실행
            print(f"DEBUG: 총 {len(tasks)}개 태스크 실행 예정")
            if tasks:
                # 태스크 실행
                task_results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
                print(f"DEBUG: 태스크 실행 완료 - {len(task_results)}개 결과")
                
                # 결과를 문서 타입별로 정리
                for i, (doc_type, _) in enumerate(tasks):
                    if isinstance(task_results[i], Exception):
                        print(f"DEBUG: 태스크 {i} 오류 - {str(task_results[i])}")
                        # 오류 발생 시 기본 결과 생성
                        result = {
                            "document_type": doc_type,
                            "document_index": i,
                            "page_number": None,
                            "analysis": f"분석 오류: {str(task_results[i])}",
                            "raw_text": ""
                        }
                    else:
                        print(f"DEBUG: 태스크 {i} 성공 - 결과 타입: {type(task_results[i])}")
                        result = task_results[i]
                    
                    if doc_type not in results:
                        results[doc_type] = []
                    results[doc_type].append(result)
            else:
                print(f"DEBUG: 실행할 태스크가 없음")
            
            return results
            
        except Exception as e:
            return {"error": f"문서 내용 분석 오류: {str(e)}"}
    
    async def _analyze_document_by_type_async(self, text: str, file_path: str) -> Dict:
        """문서 타입별 분석 (비동기) - 개선된 버전"""
        try:
            # 문서 타입 분류
            doc_types = await self._classify_document_types_async(text)
            
            # 비동기로 내용 분석 실행
            results = await self._analyze_content_async(doc_types, text, file_path)
            
            # 결과 결합
            combined_result = await self._combine_document_type_results_async(results)
            
            return {
                "success": True,
                "document_types": list(results.keys()),
                "analysis": combined_result,
                "detailed_results": results
            }
            
        except Exception as e:
            return {"error": f"문서 타입별 분석 오류: {str(e)}"}
    
    async def _extract_info_by_document_type_async(self, doc_type: str, text: str, document_index: int, file_path: str = "", page_number: int = None) -> Dict:
        """문서 타입별 정보 추출 (비동기)"""
        try:
            # 파일명 추출
            file_name = os.path.basename(file_path) if file_path else ""
            
            # 문서 타입별로 적절한 프롬프트 선택
            if doc_type == "세금계산서":
                prompt = get_tax_invoice_prompt(text, file_name, page_number)
            elif doc_type == "인보이스":
                prompt = get_invoice_prompt(text, file_name, page_number)
            elif doc_type == "BL":
                prompt = get_bill_of_lading_prompt(text, file_name, page_number)
            elif doc_type == "송금증":
                prompt = get_transfer_receipt_prompt(text, file_name, page_number)
            elif doc_type == "수출신고필증":
                prompt = get_export_declaration_prompt(text, file_name, page_number)
            else:
                # 기본 프롬프트 사용
                prompt = self._create_document_type_prompt(doc_type, text, file_path, page_number)
            
            # Claude API 호출
            async def api_call():
                return await self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4000,
                    system="당신은 문서를 정확히 분석하는 전문 AI입니다. 한글 텍스트를 매우 정확하게 읽고, 숫자와 한글을 정확히 구분해서 추출해주세요. 특히 한글 회사명, 주소, 금액 등을 정확히 인식해주세요.",
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
            
            response = await self._retry_api_call_async(api_call)
            
            if response and response.content:
                result_text = response.content[0].text
                return {
                    "document_type": doc_type,
                    "document_index": document_index,
                    "page_number": page_number,
                    "analysis": result_text,
                    "raw_text": text[:500] + "..." if len(text) > 500 else text
                }
            else:
                return {
                    "document_type": doc_type,
                    "document_index": document_index,
                    "page_number": page_number,
                    "analysis": "분석 실패",
                    "raw_text": text[:500] + "..." if len(text) > 500 else text
                }
                
        except Exception as e:
            return {
                "document_type": doc_type,
                "document_index": document_index,
                "page_number": page_number,
                "analysis": f"분석 오류: {str(e)}",
                "raw_text": text[:500] + "..." if len(text) > 500 else text
            }
    
    async def _combine_document_type_results_async(self, results: Dict, analysis_time: float = None, total_pages: int = None) -> str:
        """문서 타입별 결과 결합 (비동기)"""
        try:
            if not results:
                return "분석할 문서를 찾을 수 없습니다."
            
            combined_parts = []
            
            # 분석 요약 정보 추가
            if analysis_time is not None or total_pages is not None:
                combined_parts.append("=" * 80)
                combined_parts.append("📊 분석 요약 정보")
                combined_parts.append("=" * 80)
                
                if analysis_time is not None:
                    combined_parts.append(f"⏱️  분석 소요 시간: {analysis_time:.2f}초")
                
                if total_pages is not None:
                    combined_parts.append(f"📄 총 분석 페이지 수: {total_pages}페이지")
                
                # 문서 타입별 통계
                doc_type_counts = {}
                for doc_type, doc_results in results.items():
                    doc_type_counts[doc_type] = len(doc_results)
                
                combined_parts.append(f"📋 분석된 문서 유형: {', '.join([f'{doc_type}({count}개)' for doc_type, count in doc_type_counts.items()])}")
                combined_parts.append("=" * 80)
                combined_parts.append("")
            
            # 각 문서 타입별 상세 분석 결과
            for doc_type, doc_results in results.items():
                combined_parts.append("🔍" + "=" * 78)
                combined_parts.append(f"📋 {doc_type.upper()} 분석 결과 ({len(doc_results)}개 문서)")
                combined_parts.append("=" * 80)
                
                for i, doc_result in enumerate(doc_results):
                    combined_parts.append(f"\n📄 [문서 {i+1}]")
                    
                    # 페이지 정보
                    if doc_result.get('page_number'):
                        combined_parts.append(f"📍 페이지: {doc_result['page_number']}")
                    
                    # 분석 결과 (가독성 개선)
                    analysis_text = doc_result.get('analysis', '분석 결과 없음')
                    if analysis_text and analysis_text != '분석 결과 없음':
                        # 분석 결과를 줄바꿈으로 구분하여 가독성 향상
                        formatted_analysis = self._format_analysis_text(analysis_text)
                        combined_parts.append(f"\n📝 분석 결과:\n{formatted_analysis}")
                    else:
                        combined_parts.append(f"\n❌ 분석 결과: {analysis_text}")
                    
                    combined_parts.append("-" * 80)
            
            return "\n".join(combined_parts)
            
        except Exception as e:
            return f"결과 결합 오류: {str(e)}"
    
    def _identify_individual_documents(self, doc_type: str, pages: List[int], full_text: str) -> List[Dict]:
        """개별 문서 식별"""
        print(f"DEBUG: _identify_individual_documents - doc_type: {doc_type}, pages: {pages}")
        
        # 간단한 구현: 페이지별로 분리
        documents = []
        
        # [페이지 형식이 아닌 경우 전체 텍스트를 하나의 문서로 처리
        if not full_text.startswith('[페이지'):
            print(f"DEBUG: [페이지 형식이 아님. 전체 텍스트를 하나의 문서로 처리")
            documents.append({
                'text': full_text,
                'pages': pages if pages else [1]
            })
        else:
            # 기존 [페이지 형식 처리
            for page in pages:
                # 페이지별 텍스트 추출 (실제로는 더 정교한 로직 필요)
                start_idx = full_text.find(f"[페이지 {page}]")
                if start_idx != -1:
                    end_idx = full_text.find(f"[페이지 {page + 1}]")
                    if end_idx == -1:
                        end_idx = len(full_text)
                    
                    page_text = full_text[start_idx:end_idx].strip()
                    documents.append({
                        'text': page_text,
                        'pages': [page]
                    })
        
        print(f"DEBUG: 식별된 문서 수: {len(documents)}")
        return documents
    
    async def _classify_document_types_async(self, text: str) -> Dict[str, List[int]]:
        """문서 타입 분류 (비동기) - 병렬 처리로 개선"""
        try:
            # 페이지별로 분류
            pages = text.split('[페이지')
            doc_types = {}
            
            async def classify_page(page):
                if not page.strip():
                    return None, None
                
                page_num = page.split(']')[0].strip()
                page_content = page.split(']', 1)[1] if ']' in page else page
                
                # 기존 프롬프트 사용
                prompt = get_document_type_classification_prompt(page_content[:1000])
                
                async def api_call():
                    return await self.client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=1000,
                        system="당신은 문서를 정확히 인식하고 분류하는 전문 AI입니다. 한글 텍스트를 매우 정확하게 읽어주세요.",
                        messages=[
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    )
                
                response = await self._retry_api_call_async(api_call)
                
                if response and response.content:
                    doc_type = response.content[0].text.strip()
                    # 프롬프트에서 정의된 문서 타입으로 매핑
                    doc_type_mapping = {
                        "수출신고필증": "수출신고필증",
                        "세금계산서": "세금계산서", 
                        "인보이스": "인보이스",
                        "BL": "BL",
                        "이체확인증": "송금증",
                        "Packing List": "Packing List",
                        "미분류": "기타"
                    }
                    
                    mapped_type = doc_type_mapping.get(doc_type, doc_type)
                    return mapped_type, int(page_num) if page_num.isdigit() else None
                return None, None
            
            # 모든 페이지를 병렬로 분류
            if len(pages) > 1:
                tasks = [classify_page(page) for page in pages[1:]]  # 첫 번째는 빈 문자열
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, tuple) and result[0] and result[1]:
                        doc_type, page_num = result
                        if doc_type not in doc_types:
                            doc_types[doc_type] = []
                        doc_types[doc_type].append(page_num)
            
            return doc_types
            
        except Exception as e:
            print(f"문서 타입 분류 오류: {str(e)}")
            return {}
    
    def _extract_info_by_document_type(self, doc_type: str, text: str, file_path: str = "", page_number: int = None) -> Dict:
        """문서 타입별 정보 추출 (동기)"""
        try:
            # 파일명 추출
            file_name = os.path.basename(file_path) if file_path else ""
            
            # 문서 타입별로 적절한 프롬프트 선택
            if doc_type == "세금계산서":
                prompt = get_tax_invoice_prompt(text, file_name, page_number)
            elif doc_type == "인보이스":
                prompt = get_invoice_prompt(text, file_name, page_number)
            elif doc_type == "BL":
                prompt = get_bill_of_lading_prompt(text, file_name, page_number)
            elif doc_type == "송금증":
                prompt = get_transfer_receipt_prompt(text, file_name, page_number)
            elif doc_type == "수출신고필증":
                prompt = get_export_declaration_prompt(text, file_name, page_number)
            else:
                # 기본 프롬프트 사용
                prompt = self._create_document_type_prompt(doc_type, text, file_path, page_number)
            
            # Claude API 호출
            def api_call():
                return self.sync_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4000,
                    system="당신은 문서를 정확히 분석하는 전문 AI입니다. 한글 텍스트를 매우 정확하게 읽고, 숫자와 한글을 정확히 구분해서 추출해주세요. 특히 한글 회사명, 주소, 금액 등을 정확히 인식해주세요.",
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
            
            response = self._retry_api_call_sync(api_call)
            
            if response and response.content:
                result_text = response.content[0].text
                return {
                    "document_type": doc_type,
                    "page_number": page_number,
                    "analysis": result_text,
                    "raw_text": text[:500] + "..." if len(text) > 500 else text
                }
            else:
                return {
                    "document_type": doc_type,
                    "page_number": page_number,
                    "analysis": "분석 실패",
                    "raw_text": text[:500] + "..." if len(text) > 500 else text
                }
                
        except Exception as e:
            return {
                "document_type": doc_type,
                "page_number": page_number,
                "analysis": f"분석 오류: {str(e)}",
                "raw_text": text[:500] + "..." if len(text) > 500 else text
            }
    
    def _format_analysis_text(self, analysis_text: str) -> str:
        """분석 결과 텍스트를 가독성 좋게 포맷팅"""
        if not analysis_text:
            return analysis_text
        
        # 줄바꿈으로 구분된 항목들을 정리
        lines = analysis_text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 주요 항목들에 이모지 추가
            if any(keyword in line for keyword in ['금액', '가격', '총액', '합계', 'amount', 'price', 'total']):
                formatted_lines.append(f"💰 {line}")
            elif any(keyword in line for keyword in ['날짜', '일자', 'date']):
                formatted_lines.append(f"📅 {line}")
            elif any(keyword in line for keyword in ['번호', '번호:', 'number']):
                formatted_lines.append(f"🔢 {line}")
            elif any(keyword in line for keyword in ['회사', '업체', 'company', 'corp']):
                formatted_lines.append(f"🏢 {line}")
            elif any(keyword in line for keyword in ['주소', 'address']):
                formatted_lines.append(f"📍 {line}")
            elif any(keyword in line for keyword in ['전화', '연락처', 'phone', 'tel']):
                formatted_lines.append(f"📞 {line}")
            elif any(keyword in line for keyword in ['이메일', 'email']):
                formatted_lines.append(f"📧 {line}")
            elif line.startswith('-') or line.startswith('•') or line.startswith('*'):
                formatted_lines.append(f"  • {line[1:].strip()}")
            elif ':' in line and len(line.split(':')) == 2:
                key, value = line.split(':', 1)
                formatted_lines.append(f"  📋 {key.strip()}: {value.strip()}")
            else:
                formatted_lines.append(f"  {line}")
        
        return '\n'.join(formatted_lines)
    
    def _count_pages(self, text: str) -> int:
        """텍스트에서 페이지 수 계산"""
        if not text:
            return 0
        
        # [페이지 X] 패턴으로 페이지 수 계산
        page_pattern = r'\[페이지\s*(\d+)\]'
        page_matches = re.findall(page_pattern, text)
        
        if page_matches:
            # 페이지 번호 중 최대값 반환
            return max(int(page) for page in page_matches)
        else:
            # 페이지 표시가 없으면 텍스트 길이로 추정
            # 일반적으로 한 페이지당 약 2000자로 가정
            estimated_pages = max(1, len(text) // 2000)
            return estimated_pages
    
    def _create_document_type_prompt(self, doc_type: str, text: str, file_path: str = "", page_number: int = None) -> str:
        """문서 타입별 프롬프트 생성"""
        base_prompt = f"다음 {doc_type} 문서를 분석해주세요:\n\n{text}"
        return base_prompt
    
    def get_supported_document_types(self) -> list:
        """지원하는 문서 타입 목록"""
        return ["세금계산서", "인보이스", "송금증", "수출신고필증", "BL", "기타"]
    
    def is_supported_document_type(self, doc_type: str) -> bool:
        """지원하는 문서 타입인지 확인"""
        return doc_type in self.get_supported_document_types() 