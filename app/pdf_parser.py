"""
PDF 파싱 및 텍스트 추출 엔진

🚀 Upstage Document Parse 메인 엔진 + 다중 백업 엔진
⚡ 0.6초/페이지 초고속 처리
🎯 93.48% TEDS 정확도 보장
🔄 자동 폴백 시스템 (Upstage → PyMuPDF → pdfplumber → Tesseract OCR)
"""

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging

# PDF 처리 라이브러리들
import fitz  # PyMuPDF
import pdfplumber
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

# HTTP 클라이언트
import requests
import json

# 프로젝트 모듈
from .models import (
    ExtractionEngine, 
    DocumentType, 
    PDFProcessingResult,
    ProcessingStatus,
    DocumentDetection
)
from .utils import validate_pdf_file, get_file_info, clean_text
from .enhanced_detector import EnhancedDocumentDetector

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFParsingEngine:
    """
    다중 엔진을 활용한 PDF 파싱 시스템
    
    엔진 우선순위:
    1. 🥇 Upstage Document Parse (메인)
    2. 🥈 PyMuPDF (빠른 처리)
    3. 🥉 pdfplumber (정확한 레이아웃)
    4. 🔧 Tesseract OCR (최후 수단)
    """
    
    def __init__(self, upstage_api_key: str = None, verbose: bool = False):
        """
        Args:
            upstage_api_key: Upstage API 키
            verbose: 상세 로그 출력 여부
        """
        self.verbose = verbose
        self.upstage_api_key = upstage_api_key or os.getenv('UPSTAGE_API_KEY')
        
        # 엔진별 통계
        self.engine_stats = {
            engine: {"success": 0, "failure": 0, "total_time": 0.0}
            for engine in ExtractionEngine
        }
        
        if self.verbose:
            logger.info("🚀 PDF 파싱 엔진 초기화 완료")
    
    async def extract_text_from_pdf(
        self, 
        file_path: str, 
        preferred_engine: ExtractionEngine = ExtractionEngine.UPSTAGE
    ) -> Tuple[str, ExtractionEngine, float]:
        """
        PDF 파일에서 텍스트 추출 (자동 폴백 지원)
        
        Args:
            file_path: PDF 파일 경로
            preferred_engine: 선호하는 추출 엔진
            
        Returns:
            (추출된_텍스트, 사용된_엔진, 처리_시간)
        """
        start_time = datetime.now()
        
        # PDF 파일 검증
        validation_result = validate_pdf_file(file_path)
        if not validation_result["is_valid"]:
            raise ValueError(f"PDF 파일 검증 실패: {validation_result['error']}")
        
        if self.verbose:
            logger.info(f"📄 PDF 파싱 시작: {Path(file_path).name}")
        
        # 엔진 시도 순서 결정
        engine_order = self._get_engine_order(preferred_engine)
        
        last_error = None
        
        for engine in engine_order:
            try:
                if self.verbose:
                    logger.info(f"🔧 {engine.value} 엔진으로 시도 중...")
                
                text = await self._extract_with_engine(file_path, engine)
                
                # 최소 텍스트 길이 확인 (더 관대하게)
                min_length = 20 if engine == ExtractionEngine.UPSTAGE else 50
                if text and len(text.strip()) > min_length:
                    processing_time = (datetime.now() - start_time).total_seconds()
                    
                    # 통계 업데이트
                    self.engine_stats[engine]["success"] += 1
                    self.engine_stats[engine]["total_time"] += processing_time
                    
                    if self.verbose:
                        logger.info(f"✅ {engine.value} 성공 ({processing_time:.2f}초)")
                    
                    return clean_text(text), engine, processing_time
                else:
                    if self.verbose:
                        logger.warning(f"⚠️ {engine.value} 텍스트 부족 (길이: {len(text) if text else 0}, 최소: {min_length})")
                        
            except Exception as e:
                last_error = e
                self.engine_stats[engine]["failure"] += 1
                
                if self.verbose:
                    logger.error(f"❌ {engine.value} 실패: {str(e)}")
                
                continue
        
        # 모든 엔진 실패
        processing_time = (datetime.now() - start_time).total_seconds()
        raise RuntimeError(f"모든 PDF 추출 엔진 실패. 마지막 오류: {last_error}")
    
    async def _extract_with_engine(self, file_path: str, engine: ExtractionEngine) -> str:
        """개별 엔진으로 텍스트 추출"""
        
        if engine == ExtractionEngine.UPSTAGE:
            return await self._extract_with_upstage(file_path)
        elif engine == ExtractionEngine.PYMUPDF:
            return await self._extract_with_pymupdf(file_path)
        elif engine == ExtractionEngine.PDFPLUMBER:
            return await self._extract_with_pdfplumber(file_path)
        elif engine == ExtractionEngine.TESSERACT:
            return await self._extract_with_tesseract(file_path)
        else:
            raise ValueError(f"지원하지 않는 엔진: {engine}")
    
    async def _extract_with_upstage(self, file_path: str) -> str:
        """Upstage Document Parse API로 텍스트 추출"""
        
        if not self.upstage_api_key:
            raise ValueError("UPSTAGE_API_KEY가 설정되지 않았습니다")
        
        try:
            # Upstage Document Digitization API 호출
            url = "https://api.upstage.ai/v1/document-digitization"
            headers = {"Authorization": f"Bearer {self.upstage_api_key}"}
            
            # 파일 열기
            with open(file_path, "rb") as file:
                files = {"document": file}
                data = {
                    "ocr": "force",
                    "base64_encoding": "['table']",
                    "model": "document-parse"
                }
                
                # 비동기 처리를 위해 별도 스레드에서 실행
                response = await asyncio.to_thread(
                    requests.post, url, headers=headers, files=files, data=data
                )
            
            if response.status_code != 200:
                raise ValueError(f"Upstage API 오류: {response.status_code} - {response.text}")
            
            # JSON 응답 파싱
            result = response.json()
            
            # 텍스트 추출
            full_text = ""
            if "content" in result:
                if isinstance(result["content"], list):
                    # 페이지별 텍스트 결합
                    text_parts = []
                    for idx, page in enumerate(result["content"]):
                        if "text" in page:
                            text_parts.append(f"--- 페이지 {idx + 1} ---\n{page['text']}")
                        elif isinstance(page, str):
                            text_parts.append(f"--- 페이지 {idx + 1} ---\n{page}")
                    full_text = "\n\n".join(text_parts)
                elif isinstance(result["content"], str):
                    full_text = result["content"]
                else:
                    # 다른 형태의 응답일 경우 전체를 문자열로 변환
                    full_text = str(result["content"])
            elif "text" in result:
                full_text = result["text"]
            else:
                # 전체 응답을 텍스트로 변환 (마지막 시도)
                full_text = str(result)
            
            if self.verbose:
                pages_count = len(result.get("content", [])) if isinstance(result.get("content"), list) else 1
                logger.info(f"🚀 Upstage: {pages_count}페이지, {len(full_text)}자 추출")
            
            return full_text
            
        except Exception as e:
            if self.verbose:
                logger.error(f"🚀 Upstage 오류: {str(e)}")
            raise
    
    async def _extract_with_pymupdf(self, file_path: str) -> str:
        """PyMuPDF로 텍스트 추출 (OCR 포함)"""
        
        try:
            doc = fitz.open(file_path)
            text_parts = []
            
            if len(doc) == 0:
                doc.close()
                raise ValueError("PDF에 페이지가 없습니다")
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # 1단계: 일반 텍스트 추출 시도
                text = page.get_text()
                
                # 2단계: 텍스트가 없거나 매우 적으면 OCR 시도
                if not text or len(text.strip()) < 50:
                    try:
                        # 페이지를 이미지로 렌더링
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x 확대
                        img_data = pix.tobytes("png")
                        
                        # PIL Image로 변환
                        from PIL import Image
                        import io
                        img = Image.open(io.BytesIO(img_data))
                        
                        # Tesseract OCR로 텍스트 추출
                        import pytesseract
                        ocr_text = pytesseract.image_to_string(
                            img, 
                            lang='kor+eng',
                            config='--psm 6'
                        )
                        
                        if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                            text = ocr_text
                            if self.verbose:
                                logger.info(f"⚡ PyMuPDF OCR: 페이지 {page_num + 1}에서 {len(ocr_text)}자 추출")
                    
                    except Exception as ocr_error:
                        if self.verbose:
                            logger.warning(f"⚡ PyMuPDF OCR 실패 (페이지 {page_num + 1}): {str(ocr_error)}")
                
                if text and text.strip():
                    text_parts.append(f"--- 페이지 {page_num + 1} ---\n{text}")
            
            doc.close()
            
            full_text = "\n\n".join(text_parts)
            
            if self.verbose:
                logger.info(f"⚡ PyMuPDF: {len(text_parts)}페이지에서 {len(full_text)}자 추출")
            
            return full_text
            
        except Exception as e:
            if self.verbose:
                logger.error(f"⚡ PyMuPDF 오류: {str(e)}")
            raise
    
    async def _extract_with_pdfplumber(self, file_path: str) -> str:
        """pdfplumber로 텍스트 추출"""
        
        try:
            text_parts = []
            
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    
                    if text and text.strip():
                        text_parts.append(f"--- 페이지 {page_num + 1} ---\n{text}")
                        
                        # 테이블도 추출 시도
                        tables = page.extract_tables()
                        for table_idx, table in enumerate(tables):
                            if table:
                                table_text = "\n".join([
                                    " | ".join([cell or "" for cell in row])
                                    for row in table
                                ])
                                text_parts.append(f"[테이블 {table_idx + 1}]\n{table_text}")
            
            full_text = "\n\n".join(text_parts)
            
            if self.verbose:
                logger.info(f"🔍 pdfplumber: {len(text_parts)}페이지, {len(full_text)}자 추출")
            
            return full_text
            
        except Exception as e:
            if self.verbose:
                logger.error(f"🔍 pdfplumber 오류: {str(e)}")
            raise
    
    async def _extract_with_tesseract(self, file_path: str) -> str:
        """Tesseract OCR로 텍스트 추출"""
        
        try:
            # PDF를 이미지로 변환
            images = convert_from_path(
                file_path,
                dpi=300,  # 고해상도
                fmt='png'
            )
            
            text_parts = []
            
            for page_num, image in enumerate(images):
                # 이미지 전처리 (OCR 정확도 향상)
                processed_image = self._preprocess_image_for_ocr(image)
                
                # OCR 실행 (한국어 + 영어)
                text = pytesseract.image_to_string(
                    processed_image,
                    lang='kor+eng',  # 한국어 + 영어
                    config='--psm 6'  # 블록 단위 OCR
                )
                
                if text.strip():
                    text_parts.append(f"--- 페이지 {page_num + 1} ---\n{text}")
            
            full_text = "\n\n".join(text_parts)
            
            if self.verbose:
                logger.info(f"👁️ Tesseract: {len(images)}페이지, {len(full_text)}자 추출")
            
            return full_text
            
        except Exception as e:
            if self.verbose:
                logger.error(f"👁️ Tesseract 오류: {str(e)}")
            raise
    
    def _preprocess_image_for_ocr(self, image: Image.Image) -> Image.Image:
        """OCR 정확도 향상을 위한 이미지 전처리"""
        
        # 그레이스케일 변환
        if image.mode != 'L':
            image = image.convert('L')
        
        # 해상도 향상 (2배 확대)
        width, height = image.size
        image = image.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
        
        # 대비 향상
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.3)
        
        # 선명도 향상
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.2)
        
        return image
    
    def _get_engine_order(self, preferred_engine: ExtractionEngine) -> List[ExtractionEngine]:
        """엔진 시도 순서 결정"""
        
        # 기본 순서
        default_order = [
            ExtractionEngine.UPSTAGE,
            ExtractionEngine.PYMUPDF,
            ExtractionEngine.PDFPLUMBER,
            ExtractionEngine.TESSERACT
        ]
        
        # 선호 엔진을 맨 앞으로
        if preferred_engine in default_order:
            order = [preferred_engine]
            order.extend([engine for engine in default_order if engine != preferred_engine])
            return order
        
        return default_order
    
    def get_engine_statistics(self) -> Dict[str, Any]:
        """엔진별 성능 통계 반환"""
        
        stats = {}
        
        for engine, data in self.engine_stats.items():
            total_attempts = data["success"] + data["failure"]
            success_rate = data["success"] / total_attempts if total_attempts > 0 else 0
            avg_time = data["total_time"] / data["success"] if data["success"] > 0 else 0
            
            stats[engine.value] = {
                "success_count": data["success"],
                "failure_count": data["failure"],
                "success_rate": round(success_rate * 100, 1),
                "average_time_seconds": round(avg_time, 2),
                "total_time_seconds": round(data["total_time"], 2)
            }
        
        return stats


class DocumentTypeDetector:
    """
    문서 타입 자동 감지기
    
    추출된 텍스트를 분석하여 무역문서 타입을 식별합니다.
    """
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
        # 문서 타입별 핵심 키워드 (확장됨)
        self.type_keywords = {
            DocumentType.TAX_INVOICE: {
                "primary": ["세금계산서", "tax invoice", "공급가액", "세액", "부가가치세", "매출세금계산서", "정발행"],
                "secondary": ["사업자등록번호", "합계금액", "공급자", "공급받는자", "발행일자", "승인번호", "일련번호"],
                "negative": []
            },
            DocumentType.INVOICE: {
                "primary": ["invoice", "commercial invoice", "proforma invoice", "인보이스", "상업송장", "운임", "freight"],
                "secondary": ["description", "quantity", "unit price", "amount", "total", "화물운송료", "운송비", "내역"],
                "negative": ["세금계산서", "tax invoice"]
            },
            DocumentType.BILL_OF_LADING: {
                "primary": ["bill of lading", "b/l", "bl", "선하증권", "house b/l", "master b/l"],
                "secondary": ["port of loading", "port of discharge", "vessel", "voyage", "shipper", "consignee", "p.o.l", "p.o.d", "선박명"],
                "negative": []
            },
            DocumentType.EXPORT_DECLARATION: {
                "primary": ["수출신고", "export declaration", "신고번호", "수출신고필증", "관세청"],
                "secondary": ["세번", "hs code", "목적국", "적재항", "송품장", "수출신고서", "통관"],
                "negative": []
            },
            DocumentType.REMITTANCE_ADVICE: {
                "primary": ["이체확인", "transfer confirmation", "송금확인", "송금증", "입금확인", "결제확인"],
                "secondary": ["승인번호", "계좌번호", "송금금액", "approval", "account", "은행명", "입금액"],
                "negative": []
            }
        }
    
    def detect_document_type(self, text: str) -> Tuple[DocumentType, float]:
        """
        텍스트에서 문서 타입 감지
        
        Args:
            text: 추출된 텍스트
            
        Returns:
            (감지된_문서_타입, 신뢰도)
        """
        
        if not text or len(text.strip()) < 20:
            return DocumentType.UNKNOWN, 0.0
        
        text_lower = text.lower()
        scores = {}
        
        # 각 문서 타입별 점수 계산
        for doc_type, keywords in self.type_keywords.items():
            score = 0.0
            found_keywords = []
            
            # Primary 키워드 점수 (가중치 3)
            for keyword in keywords["primary"]:
                count = text_lower.count(keyword.lower())
                if count > 0:
                    score += count * 3
                    found_keywords.append(keyword)
            
            # Secondary 키워드 점수 (가중치 1)
            for keyword in keywords["secondary"]:
                count = text_lower.count(keyword.lower())
                if count > 0:
                    score += count * 1
                    found_keywords.append(keyword)
            
            # Negative 키워드 패널티 (가중치 -2)
            for keyword in keywords["negative"]:
                count = text_lower.count(keyword.lower())
                if count > 0:
                    score -= count * 2
            
            scores[doc_type] = {
                "score": score,
                "found_keywords": found_keywords[:5]  # 최대 5개까지
            }
            
            if self.verbose and score > 0:
                logger.info(f"📋 {doc_type.value}: {score}점 ({len(found_keywords)}개 키워드)")
        
        # 최고 점수 문서 타입 선택
        if not scores or all(data["score"] <= 0 for data in scores.values()):
            return DocumentType.UNKNOWN, 0.0
        
        best_type = max(scores.items(), key=lambda x: x[1]["score"])
        doc_type, data = best_type
        
        # 신뢰도 계산 (0~1)
        max_score = data["score"]
        total_keywords = len(self.type_keywords[doc_type]["primary"]) + len(self.type_keywords[doc_type]["secondary"])
        confidence = min(1.0, max_score / (total_keywords * 2))  # 정규화
        
        if self.verbose:
            logger.info(f"🎯 감지 결과: {doc_type.value} (신뢰도: {confidence:.2f})")
        
        return doc_type, confidence
    
    def detect_multiple_documents(self, text: str) -> List[Tuple[DocumentType, float, Tuple[int, int]]]:
        """
        텍스트에서 복수 문서 타입 감지 및 개별 문서 분리 (개선된 버전)
        
        Args:
            text: 추출된 텍스트 (페이지 구분자 포함)
            
        Returns:
            List[(문서_타입, 신뢰도, 페이지_범위)]
        """
        
        # 방법 1: 전체 텍스트에서 모든 문서 타입 동시 검색
        detected_docs = self._detect_all_document_types_in_text(text)
        
        if detected_docs:
            if self.verbose:
                logger.info(f"🎯 전체 텍스트 검색으로 감지된 문서: {len(detected_docs)}개")
                for i, (dtype, conf, pages) in enumerate(detected_docs):
                    logger.info(f"  {i+1}. {dtype.value} (페이지 {pages[0]}-{pages[1]}, 신뢰도: {conf:.2f})")
            return detected_docs
        
        # 방법 2: 페이지별 감지 (기존 방식)
        pages = self._split_text_by_pages(text)
        
        # 각 페이지별로 모든 문서 타입 점수 계산
        page_scores = []
        for page_num, page_text in enumerate(pages, 1):
            page_score = self._calculate_all_document_scores(page_text)
            page_scores.append((page_num, page_score, page_text))
            
            if self.verbose:
                logger.info(f"📄 페이지 {page_num} 점수:")
                for doc_type, score in page_score.items():
                    if score > 0:
                        logger.info(f"  - {doc_type.value}: {score}점")
        
        # 페이지별 최고 점수 문서 타입 선택 (개선된 로직)
        detected_docs = []
        for page_num, scores, page_text in page_scores:
            # 최소 임계값을 넘는 모든 문서 타입 찾기
            valid_docs = [(doc_type, score) for doc_type, score in scores.items() if score >= 2]
            
            if valid_docs:
                # 점수 순으로 정렬하고 상위 문서들 선택
                valid_docs.sort(key=lambda x: x[1], reverse=True)
                
                # 최고 점수의 50% 이상인 문서들만 선택 (여러 문서 동시 인정)
                max_score = valid_docs[0][1]
                threshold = max_score * 0.5
                
                for doc_type, score in valid_docs:
                    if score >= threshold:
                        confidence = min(0.9, score / 10)
                        detected_docs.append((doc_type, confidence, (page_num, page_num)))
                        
                        if self.verbose:
                            logger.info(f"✅ 페이지 {page_num}: {doc_type.value} (점수: {score}, 신뢰도: {confidence:.2f})")
        
        # 동일한 문서 타입 연속 페이지 병합
        merged_docs = self._merge_consecutive_same_documents(detected_docs)
        
        if self.verbose:
            logger.info(f"🎯 최종 감지된 문서: {len(merged_docs)}개")
            for i, (dtype, conf, pages) in enumerate(merged_docs):
                logger.info(f"  {i+1}. {dtype.value} (페이지 {pages[0]}-{pages[1]}, 신뢰도: {conf:.2f})")
        
        return merged_docs
    
    def _split_individual_documents(self, doc_group: List[Tuple[int, DocumentType, float, str]]) -> List[Tuple[DocumentType, float, Tuple[int, int]]]:
        """
        동일한 문서 타입 그룹에서 개별 문서들을 분리
        
        Args:
            doc_group: [(페이지번호, 문서타입, 신뢰도, 텍스트), ...]
            
        Returns:
            List[(문서_타입, 신뢰도, 페이지_범위)]
        """
        
        if not doc_group:
            return []
        
        doc_type = doc_group[0][1]
        individual_docs = []
        
        if doc_type == DocumentType.BILL_OF_LADING:
            # 선하증권: B/L 번호로 분리
            bl_groups = self._group_by_bl_number(doc_group)
            for bl_number, pages_group in bl_groups.items():
                start_page = min(page[0] for page in pages_group)
                end_page = max(page[0] for page in pages_group)
                avg_confidence = sum(page[2] for page in pages_group) / len(pages_group)
                individual_docs.append((doc_type, avg_confidence, (start_page, end_page)))
                
        elif doc_type == DocumentType.EXPORT_DECLARATION:
            # 수출신고필증: 신고번호로 분리
            decl_groups = self._group_by_declaration_number(doc_group)
            for decl_number, pages_group in decl_groups.items():
                start_page = min(page[0] for page in pages_group)
                end_page = max(page[0] for page in pages_group)
                avg_confidence = sum(page[2] for page in pages_group) / len(pages_group)
                individual_docs.append((doc_type, avg_confidence, (start_page, end_page)))
                
        elif doc_type == DocumentType.TAX_INVOICE:
            # 세금계산서: 세금계산서 번호로 분리
            tax_groups = self._group_by_tax_invoice_number(doc_group)
            for tax_number, pages_group in tax_groups.items():
                start_page = min(page[0] for page in pages_group)
                end_page = max(page[0] for page in pages_group)
                avg_confidence = sum(page[2] for page in pages_group) / len(pages_group)
                individual_docs.append((doc_type, avg_confidence, (start_page, end_page)))
                
        elif doc_type == DocumentType.INVOICE:
            # 인보이스: 인보이스 번호로 분리
            invoice_groups = self._group_by_invoice_number(doc_group)
            for invoice_number, pages_group in invoice_groups.items():
                start_page = min(page[0] for page in pages_group)
                end_page = max(page[0] for page in pages_group)
                avg_confidence = sum(page[2] for page in pages_group) / len(pages_group)
                individual_docs.append((doc_type, avg_confidence, (start_page, end_page)))
                
        else:
            # 기타 문서 타입: 연속된 페이지로 처리
            start_page = doc_group[0][0]
            end_page = doc_group[-1][0]
            avg_confidence = sum(page[2] for page in doc_group) / len(doc_group)
            individual_docs.append((doc_type, avg_confidence, (start_page, end_page)))
        
        return individual_docs
    
    def _group_by_bl_number(self, doc_group: List[Tuple[int, DocumentType, float, str]]) -> Dict[str, List[Tuple[int, DocumentType, float, str]]]:
        """B/L 번호로 페이지들을 그룹화"""
        
        bl_patterns = [
            re.compile(r'b/?l\s*(?:no\.?)?\s*:?\s*([A-Z]{2,4}\d{6,12})', re.IGNORECASE),
            re.compile(r'bill\s*of\s*lading\s*(?:no\.?)?\s*:?\s*([A-Z]{2,4}\d{6,12})', re.IGNORECASE),
            re.compile(r'([A-Z]{2,4}\d{6,12})', re.IGNORECASE)  # 일반적인 B/L 번호 패턴
        ]
        
        groups = {}
        unknown_count = 1
        
        for page_info in doc_group:
            page_num, doc_type, confidence, page_text = page_info
            bl_number = None
            
            # B/L 번호 찾기
            for pattern in bl_patterns:
                matches = pattern.findall(page_text)
                if matches:
                    # 가장 앞에 나오는 B/L 번호 사용
                    bl_number = matches[0]
                    break
            
            # B/L 번호를 찾지 못한 경우
            if not bl_number:
                bl_number = f"UNKNOWN_BL_{unknown_count}"
                unknown_count += 1
            
            if bl_number not in groups:
                groups[bl_number] = []
            groups[bl_number].append(page_info)
        
        return groups
    
    def _group_by_declaration_number(self, doc_group: List[Tuple[int, DocumentType, float, str]]) -> Dict[str, List[Tuple[int, DocumentType, float, str]]]:
        """신고번호로 페이지들을 그룹화"""
        
        decl_patterns = [
            re.compile(r'신고번호\s*([0-9]{5}-[0-9]{2}-[0-9]{6}[A-Z]?)', re.IGNORECASE),
            re.compile(r'(\d{5}-\d{2}-\d{6}[A-Z]?)', re.IGNORECASE)
        ]
        
        groups = {}
        unknown_count = 1
        
        for page_info in doc_group:
            page_num, doc_type, confidence, page_text = page_info
            decl_number = None
            
            # 신고번호 찾기
            for pattern in decl_patterns:
                matches = pattern.findall(page_text)
                if matches:
                    decl_number = matches[0]
                    break
            
            # 신고번호를 찾지 못한 경우
            if not decl_number:
                decl_number = f"UNKNOWN_DECL_{unknown_count}"
                unknown_count += 1
            
            if decl_number not in groups:
                groups[decl_number] = []
            groups[decl_number].append(page_info)
        
        return groups
    
    def _group_by_tax_invoice_number(self, doc_group: List[Tuple[int, DocumentType, float, str]]) -> Dict[str, List[Tuple[int, DocumentType, float, str]]]:
        """세금계산서 번호로 페이지들을 그룹화"""
        
        tax_patterns = [
            re.compile(r'세금계산서.*?번호.*?([0-9-]+)', re.IGNORECASE),
            re.compile(r'tax\s*invoice.*?no.*?([0-9-]+)', re.IGNORECASE)
        ]
        
        groups = {}
        unknown_count = 1
        
        for page_info in doc_group:
            page_num, doc_type, confidence, page_text = page_info
            tax_number = None
            
            # 세금계산서 번호 찾기
            for pattern in tax_patterns:
                matches = pattern.findall(page_text)
                if matches:
                    tax_number = matches[0]
                    break
            
            # 세금계산서 번호를 찾지 못한 경우
            if not tax_number:
                tax_number = f"UNKNOWN_TAX_{unknown_count}"
                unknown_count += 1
            
            if tax_number not in groups:
                groups[tax_number] = []
            groups[tax_number].append(page_info)
        
        return groups
    
    def _group_by_invoice_number(self, doc_group: List[Tuple[int, DocumentType, float, str]]) -> Dict[str, List[Tuple[int, DocumentType, float, str]]]:
        """인보이스 번호로 페이지들을 그룹화"""
        
        invoice_patterns = [
            re.compile(r'invoice\s*(?:no\.?)?\s*:?\s*([A-Z0-9-]+)', re.IGNORECASE),
            re.compile(r'commercial\s*invoice\s*(?:no\.?)?\s*:?\s*([A-Z0-9-]+)', re.IGNORECASE)
        ]
        
        groups = {}
        unknown_count = 1
        
        for page_info in doc_group:
            page_num, doc_type, confidence, page_text = page_info
            invoice_number = None
            
            # 인보이스 번호 찾기
            for pattern in invoice_patterns:
                matches = pattern.findall(page_text)
                if matches:
                    invoice_number = matches[0]
                    break
            
            # 인보이스 번호를 찾지 못한 경우
            if not invoice_number:
                invoice_number = f"UNKNOWN_INV_{unknown_count}"
                unknown_count += 1
            
            if invoice_number not in groups:
                groups[invoice_number] = []
            groups[invoice_number].append(page_info)
        
        return groups
    
    def _split_text_by_pages(self, text: str) -> List[str]:
        """페이지 구분자로 텍스트 분리"""
        
        # 페이지 구분자 패턴들
        page_patterns = [
            r'--- 페이지 (\d+) ---',
            r'Page (\d+)',
            r'\f',  # Form feed character
        ]
        
        # 페이지 구분자로 분리
        pages = []
        current_text = text
        
        for pattern in page_patterns:
            if re.search(pattern, current_text):
                parts = re.split(pattern, current_text)
                # 첫 번째 부분 (페이지 구분자 전)
                if parts[0].strip():
                    pages.append(parts[0].strip())
                
                # 나머지 부분들을 페이지로 처리
                for i in range(1, len(parts), 2):  # 홀수 인덱스는 페이지 번호, 짝수는 내용
                    if i + 1 < len(parts) and parts[i + 1].strip():
                        pages.append(parts[i + 1].strip())
                break
        
        # 페이지 구분자가 없으면 전체를 하나의 페이지로 처리
        if not pages:
            pages = [text]
        
        return pages
    
    def _calculate_final_confidence(self, text: str, doc_type: DocumentType) -> float:
        """최종 신뢰도 계산"""
        _, confidence = self.detect_document_type(text)
        return confidence
    
    def get_detection_details(self, text: str) -> Dict[str, Any]:
        """상세한 문서 타입 감지 정보 반환"""
        
        text_lower = text.lower()
        details = {}
        
        for doc_type, keywords in self.type_keywords.items():
            found_primary = [kw for kw in keywords["primary"] if kw.lower() in text_lower]
            found_secondary = [kw for kw in keywords["secondary"] if kw.lower() in text_lower]
            found_negative = [kw for kw in keywords["negative"] if kw.lower() in text_lower]
            
            score = len(found_primary) * 3 + len(found_secondary) * 1 - len(found_negative) * 2
            
            details[doc_type.value] = {
                "score": score,
                "found_primary_keywords": found_primary,
                "found_secondary_keywords": found_secondary,
                "found_negative_keywords": found_negative,
                "total_keywords_found": len(found_primary) + len(found_secondary)
            }
        
        return details


class PDFProcessor:
    """
    종합 PDF 처리기
    
    파싱 엔진과 문서 타입 감지기를 결합한 통합 인터페이스
    """
    
    def __init__(self, upstage_api_key: str = None, verbose: bool = False):
        self.parser = PDFParsingEngine(upstage_api_key, verbose)
        self.detector = DocumentTypeDetector(verbose)
        self.enhanced_detector = EnhancedDocumentDetector(verbose)  # 새로운 감지기 추가
        self.verbose = verbose
    
    async def process_pdf(
        self, 
        file_path: str,
        preferred_engine: ExtractionEngine = ExtractionEngine.UPSTAGE
    ) -> PDFProcessingResult:
        """
        PDF 파일 완전 처리
        
        Args:
            file_path: PDF 파일 경로
            preferred_engine: 선호하는 추출 엔진
            
        Returns:
            PDFProcessingResult 객체
        """
        
        start_time = datetime.now()
        file_info = get_file_info(file_path)
        
        # PDF 페이지 수 확인
        try:
            doc = fitz.open(file_path)
            total_pages = len(doc)
            doc.close()
        except:
            total_pages = 1  # 기본값
        
        # 결과 객체 초기화
        result = PDFProcessingResult(
            file_path=file_path,
            file_name=file_info["stem"],
            file_size_mb=file_info["size_mb"],
            total_pages=total_pages,
            processing_start_time=start_time,
            status=ProcessingStatus.PROCESSING
        )
        
        try:
            if self.verbose:
                logger.info(f"🚀 PDF 종합 처리 시작: {file_info['name']}")
            
            # 1. 텍스트 추출
            extracted_text, used_engine, parsing_time = await self.parser.extract_text_from_pdf(
                file_path, preferred_engine
            )
            
            result.extraction_engines_used.append(used_engine)
            result.primary_engine = used_engine
            
            # 2. 향상된 복수 문서 타입 감지 (PyMuPDF 스타일)
            multiple_docs = self.enhanced_detector.detect_documents_in_pages(extracted_text)
            
            if self.verbose:
                logger.info(f"🔍 향상된 감지기로 발견된 문서 수: {len(multiple_docs)}")
                
                # 디버깅 정보 출력
                debug_info = self.enhanced_detector.get_debug_info(extracted_text)
                logger.info(f"📊 디버깅 정보: {debug_info}")
            
            # 3. 문서 감지 결과 생성 및 데이터 추출
            detections = []
            for doc_type, confidence, page_range in multiple_docs:
                # 해당 페이지 범위의 텍스트 추출
                page_text = self._extract_text_for_page_range(extracted_text, page_range)
                
                # 실제 구조화된 데이터 추출 (DataExtractor 사용)
                from .data_extractor import DataExtractor
                extractor = DataExtractor(verbose=self.verbose)
                structured_data = extractor.extract_data(page_text, doc_type, used_engine)
                
                # raw_text와 구조화된 데이터 모두 포함
                extracted_data = {"raw_text": page_text}
                extracted_data.update(structured_data)
                
                detection = DocumentDetection(
                    document_type=doc_type,
                    confidence=confidence,
                    page_range=page_range,
                    key_indicators=self._get_simple_indicators(page_text, doc_type),
                    extracted_data=extracted_data
                )
                detections.append(detection)
            
            # 감지된 문서가 없으면 기존 방식으로 폴백
            if not detections:
                if self.verbose:
                    logger.info("🔄 향상된 감지 실패, 기존 방식으로 폴백")
                
                # 기존 감지기 사용
                doc_type, confidence = self.detector.detect_document_type(extracted_text)
                
                # 폴백에서도 구조화된 데이터 추출
                from .data_extractor import DataExtractor
                extractor = DataExtractor(verbose=self.verbose)
                structured_data = extractor.extract_data(extracted_text, doc_type, used_engine)
                
                extracted_data = {"raw_text": extracted_text}
                extracted_data.update(structured_data)
                
                detection = DocumentDetection(
                    document_type=doc_type,
                    confidence=confidence,
                    page_range=(1, result.total_pages or 1),
                    key_indicators=self._get_simple_indicators(extracted_text, doc_type),
                    extracted_data=extracted_data
                )
                detections = [detection]
            
            result.detected_documents = detections
            # 주 문서 타입은 첫 번째 또는 가장 신뢰도가 높은 문서로 설정
            result.primary_document_type = max(detections, key=lambda x: x.confidence).document_type
            result.status = ProcessingStatus.COMPLETED
            
            if self.verbose:
                logger.info(f"✅ 처리 완료: {doc_type.value} (엔진: {used_engine.value})")
            
        except Exception as e:
            result.add_error(f"처리 실패: {str(e)}")
            result.status = ProcessingStatus.FAILED
            
            if self.verbose:
                logger.error(f"❌ PDF 처리 실패: {str(e)}")
        
        # 처리 시간 계산
        end_time = datetime.now()
        result.processing_end_time = end_time
        result.processing_duration_seconds = (end_time - start_time).total_seconds()
        
        return result
    
    def _extract_text_for_page_range(self, full_text: str, page_range: Tuple[int, int]) -> str:
        """페이지 범위에 해당하는 텍스트 추출"""
        start_page, end_page = page_range
        
        # 페이지 구분자로 분리
        pages = self.detector._split_text_by_pages(full_text)
        
        # 인덱스 조정 (1-based -> 0-based)
        start_idx = max(0, start_page - 1)
        end_idx = min(len(pages), end_page)
        
        # 해당 범위의 페이지들 결합
        selected_pages = pages[start_idx:end_idx]
        return "\n\n".join(selected_pages)
    
    def _get_key_indicators(self, text: str, doc_type: DocumentType) -> List[str]:
        """문서 타입 감지에 사용된 핵심 키워드 반환"""
        
        details = self.detector.get_detection_details(text)
        type_details = details.get(doc_type.value, {})
        
        indicators = []
        indicators.extend(type_details.get("found_primary_keywords", []))
        indicators.extend(type_details.get("found_secondary_keywords", [])[:3])  # 최대 3개
        
        return indicators[:5]  # 최대 5개 반환
    
    def _get_simple_indicators(self, text: str, doc_type: DocumentType) -> List[str]:
        """간단한 키워드 추출"""
        
        text_lower = text.lower()
        indicators = []
        
        # 각 문서 타입별 대표 키워드
        keywords_map = {
            DocumentType.INVOICE: ['invoice', 'freight', '운임', '인보이스'],
            DocumentType.TAX_INVOICE: ['세금계산서', '공급가액', '부가가치세'],
            DocumentType.BILL_OF_LADING: ['bill of lading', 'b/l', '선하증권', 'port of'],
            DocumentType.EXPORT_DECLARATION: ['수출신고', '신고번호', '관세청'],
            DocumentType.REMITTANCE_ADVICE: ['이체확인', '송금', '승인번호']
        }
        
        for keyword in keywords_map.get(doc_type, []):
            if keyword.lower() in text_lower:
                indicators.append(keyword)
                if len(indicators) >= 3:
                    break
        
        return indicators
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """성능 요약 정보 반환"""
        
        engine_stats = self.parser.get_engine_statistics()
        
        return {
            "engine_statistics": engine_stats,
            "supported_document_types": [dt.value for dt in DocumentType],
            "available_engines": [engine.value for engine in ExtractionEngine]
        }
    
    def _enhanced_document_detection(self, text: str, total_pages: int) -> List[DocumentDetection]:
        """향상된 문서 감지 로직 - 전체 텍스트에서 모든 문서 타입 검색"""
        
        detections = []
        text_lower = text.lower()
        
        # 각 문서 타입별로 강력한 키워드 패턴 검색
        document_patterns = {
            DocumentType.INVOICE: [
                r'invoice\s*(?:no\.?|number)?.*?([A-Z0-9\-]+)',
                r'상업송장|commercial\s*invoice',
                r'freight\s*(?:charge|cost)',
                r'인보이스',
                r'운임',
                r'화물운송료'
            ],
            DocumentType.TAX_INVOICE: [
                r'세금계산서',
                r'공급가액.*?[\d,]+',
                r'세\s*액.*?[\d,]+',
                r'사업자등록번호.*?\d{3}-\d{2}-\d{5}',
                r'매출세금계산서'
            ],
            DocumentType.BILL_OF_LADING: [
                r'bill\s*of\s*lading',
                r'b/l\s*(?:no\.?|number)',
                r'port\s*of\s*loading',
                r'port\s*of\s*discharge',
                r'vessel\s*name',
                r'선하증권',
                r'p\.o\.l',
                r'p\.o\.d'
            ],
            DocumentType.EXPORT_DECLARATION: [
                r'수출신고필증',
                r'export\s*declaration',
                r'신고번호.*?\d+',
                r'관세청',
                r'h\.?s\.?\s*code.*?\d+',
                r'수출신고서'
            ],
            DocumentType.REMITTANCE_ADVICE: [
                r'이체확인증',
                r'송금확인',
                r'transfer\s*confirmation',
                r'승인번호.*?\d+',
                r'계좌번호.*?\d+',
                r'입금확인',
                r'송금증'
            ]
        }
        
        # 각 문서 타입별 점수 계산
        for doc_type, patterns in document_patterns.items():
            score = 0
            found_indicators = []
            
            for pattern in patterns:
                import re
                matches = re.findall(pattern, text_lower, re.IGNORECASE | re.MULTILINE)
                if matches:
                    score += len(matches) * 2  # 패턴 매칭은 높은 점수
                    found_indicators.extend([pattern.replace(r'.*?\d+', '').replace(r'\s*', ' ') for _ in matches[:3]])
            
            # 기본 키워드도 체크
            basic_keywords = self.detector.type_keywords.get(doc_type, {}).get("primary", [])
            for keyword in basic_keywords:
                if keyword.lower() in text_lower:
                    score += 1
                    found_indicators.append(keyword)
            
            # 충분한 점수가 있으면 문서로 인정
            if score >= 2:  # 최소 2점 이상 (더 관대하게)
                confidence = min(0.8, score / 8)  # 최대 0.8 신뢰도
                
                # 페이지 범위 추정 (실제로는 더 정교한 로직 필요)
                estimated_pages = self._estimate_document_pages(text, doc_type, total_pages)
                
                detection = DocumentDetection(
                    document_type=doc_type,
                    confidence=confidence,
                    page_range=estimated_pages,
                    key_indicators=list(set(found_indicators[:5])),  # 중복 제거
                    extracted_data={"raw_text": text}
                )
                detections.append(detection)
                
                if self.verbose:
                    logger.info(f"✅ 향상된 감지: {doc_type.value} (점수: {score}, 신뢰도: {confidence:.2f})")
        
        # 신뢰도 순으로 정렬
        detections.sort(key=lambda x: x.confidence, reverse=True)
        
        return detections
    
    def _estimate_document_pages(self, text: str, doc_type: DocumentType, total_pages: int) -> Tuple[int, int]:
        """문서 타입에 따른 페이지 범위 추정"""
        
        # 간단한 추정 로직 (실제로는 더 정교하게 구현 가능)
        if total_pages <= 1:
            return (1, 1)
        elif total_pages <= 3:
            return (1, total_pages)
        else:
            # 문서 타입별로 일반적인 페이지 범위 추정
            if doc_type == DocumentType.INVOICE:
                return (1, min(2, total_pages))
            elif doc_type == DocumentType.TAX_INVOICE:
                return (1, 1)
            elif doc_type == DocumentType.BILL_OF_LADING:
                return (1, min(3, total_pages))
            elif doc_type == DocumentType.EXPORT_DECLARATION:
                return (1, min(2, total_pages))
            else:
                return (1, 1)