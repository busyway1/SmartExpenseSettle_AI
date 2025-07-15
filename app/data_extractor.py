"""
AI 기반 데이터 추출 로직

PDF에서 추출된 텍스트를 분석하여 구조화된 데이터로 변환합니다.
- 정규표현식 기반 패턴 매칭
- OpenAI GPT 기반 지능형 추출 (옵션)
- 문서 타입별 특화 추출 로직
"""

import re
import json
import os
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
import logging

from .models import (
    DocumentType,
    FieldData,
    ExtractionEngine,
    InvoiceData,
    ExportDeclarationData,
    BillOfLadingData,
    TaxInvoiceData,
    TransferConfirmationData,
    create_field_data
)

logger = logging.getLogger(__name__)


class DataExtractor:
    """
    무역문서별 데이터 추출기
    
    정규표현식과 패턴 매칭을 통해 PDF 텍스트에서
    구조화된 데이터를 추출합니다.
    """
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
        # 패턴 컴파일 (성능 최적화)
        self._compile_patterns()
    
    def _compile_patterns(self):
        """정규표현식 패턴들을 미리 컴파일"""
        
        # 공통 패턴
        self.patterns = {
            # 숫자 및 금액
            "number": re.compile(r'[\d,]+\.?\d*'),
            "currency": re.compile(r'[₩$¥€]?\s*[\d,]+\.?\d*'),
            "percentage": re.compile(r'[\d,]+\.?\d*\s*%'),
            
            # 날짜
            "date_kr": re.compile(r'\d{4}[-./년]\s*\d{1,2}[-./월]\s*\d{1,2}[-./일]?'),
            "date_en": re.compile(r'\d{1,2}[-./]\d{1,2}[-./]\d{4}'),
            
            # B/L 번호
            "bl_number": re.compile(r'[A-Z]{2,4}\d{6,12}|[A-Z]+\d+[A-Z]*\d*', re.IGNORECASE),
            
            # 컨테이너 번호
            "container": re.compile(r'[A-Z]{4}\d{7}', re.IGNORECASE),
            
            # 계좌번호
            "account": re.compile(r'\d{3,4}-\d{2,4}-\d{4,8}'),
            
            # 사업자등록번호
            "business_number": re.compile(r'\d{3}-\d{2}-\d{5}'),
        }
        
        # 문서별 다중 패턴 시스템 (실용적 접근)
        self.document_patterns = {
            DocumentType.INVOICE: {
                "invoice_number": [
                    re.compile(r'(?:invoice|송품장).*?(?:no\.?|번호).*?([A-Z0-9-]+)', re.IGNORECASE),
                    re.compile(r'invoice.*?([A-Z0-9-]+)', re.IGNORECASE),
                    re.compile(r'([A-Z]\d{2}-\d{4})', re.IGNORECASE),  # 24C-0202 형태
                ],
                "description": [
                    re.compile(r'(?:description|품목|내역).*?:?\s*(.+?)(?:\n|$)', re.IGNORECASE),
                    re.compile(r'(?:commodity|상품).*?:?\s*(.+?)(?:\n|$)', re.IGNORECASE),
                ]
            },
            DocumentType.EXPORT_DECLARATION: {
                "declaration_number": [
                    re.compile(r'(?:신고번호|신고필증).*?(\d{5}-\d{2}-\d{6}[A-Z]?)', re.IGNORECASE),
                    re.compile(r'(\d{5}-\d{2}-\d{6}[A-Z]?)', re.IGNORECASE),  # 단독 패턴
                    re.compile(r'신고.*?(\d{5}-\d{2}-\d{6}[A-Z]?)', re.IGNORECASE),
                ],
                "invoice_symbol": [
                    re.compile(r'(?:송품장.*?부호|invoice.*?symbol).*?([A-Z0-9-]+)', re.IGNORECASE),
                    re.compile(r'([A-Z]\d{2}-\d{4})', re.IGNORECASE),  # 24C-0202 형태
                ],
                "destination_country": [
                    re.compile(r'(?:목적국|destination).*?([A-Z]{2})', re.IGNORECASE),
                    re.compile(r'TW|CN|JP|US|VN', re.IGNORECASE),  # 주요 국가 코드
                ],
                "loading_port": [
                    re.compile(r'(?:적재항|port.*loading).*?([A-Z]{5})', re.IGNORECASE),
                    re.compile(r'KRPUS|KRBER|KRINC', re.IGNORECASE),  # 한국 주요 항구
                ]
            },
            DocumentType.TAX_INVOICE: {
                "tax_invoice_number": [
                    re.compile(r'(?:세금계산서|tax invoice).*?번호.*?([0-9-]+)', re.IGNORECASE),
                    re.compile(r'계산서.*?번호.*?([0-9-]+)', re.IGNORECASE),
                    re.compile(r'번호.*?(\d{4}년.*\d{2}월.*\d{2}일.*\d+)', re.IGNORECASE),
                ],
                "supply_amount": [
                    re.compile(r'공급가액.*?([₩]?\s*[\d,]+)', re.IGNORECASE),
                    re.compile(r'공급.*?가액.*?([₩]?\s*[\d,]+)', re.IGNORECASE),
                ],
                "tax_amount": [
                    re.compile(r'세액.*?([₩]?\s*[\d,]+)', re.IGNORECASE),
                    re.compile(r'부가세.*?([₩]?\s*[\d,]+)', re.IGNORECASE),
                ],
                "total_amount": [
                    re.compile(r'합계.*?([₩]?\s*[\d,]+)', re.IGNORECASE),
                    re.compile(r'총.*?금액.*?([₩]?\s*[\d,]+)', re.IGNORECASE),
                ]
            },
            DocumentType.BILL_OF_LADING: {
                "bl_number": [
                    re.compile(r'(?:b/?l.*?no|bill.*lading.*?no).*?([A-Z0-9-]+)', re.IGNORECASE),
                    re.compile(r'b/?l.*?([A-Z0-9-]+)', re.IGNORECASE),
                ],
                "vessel_name": [
                    re.compile(r'(?:vessel|선박명).*?:?\s*([A-Z\s]+?)(?:\s|VOY|,|\n)', re.IGNORECASE),
                    re.compile(r'(?:M/V|MV)\s*([A-Z\s]+)', re.IGNORECASE),
                ],
                "voyage_number": [
                    re.compile(r'(?:voyage|VOY|항차).*?:?\s*([A-Z0-9]+)', re.IGNORECASE),
                    re.compile(r'VOY:?\s*([A-Z0-9]+)', re.IGNORECASE),
                ],
                "port_of_loading": [
                    re.compile(r'port.*?loading.*?:?\s*([A-Z\s,]+?)(?:\n|Port|$)', re.IGNORECASE),
                    re.compile(r'(?:BUSAN|부산|INCHEON|인천)', re.IGNORECASE),
                ],
                "port_of_discharge": [
                    re.compile(r'port.*?discharge.*?:?\s*([A-Z\s,]+?)(?:\n|Place|$)', re.IGNORECASE),
                    re.compile(r'(?:KEELUNG|기륭|TAIPEI|타이페이)', re.IGNORECASE),
                ],
                "gross_weight": [
                    re.compile(r'(?:gross.*weight|총.*중량).*?([\d,]+\.?\d*)', re.IGNORECASE),
                    re.compile(r'([\d,]+\.?\d*)\s*KGS?', re.IGNORECASE),
                ],
                "container_number": [
                    re.compile(r'(?:container|컨테이너).*?([A-Z]{4}\d{7})', re.IGNORECASE),
                    re.compile(r'([A-Z]{4}\d{7})', re.IGNORECASE),  # 단독 패턴
                ]
            }
        }
    
    def _safe_group_extract(self, match, group_num: int = 1) -> str:
        """안전한 그룹 추출 (그룹이 없으면 전체 매치 반환)"""
        try:
            if group_num == 0:
                return match.group(0).strip()
            elif match.groups() and len(match.groups()) >= group_num:
                return match.group(group_num).strip()
            else:
                return match.group(0).strip()
        except (IndexError, AttributeError):
            return match.group(0).strip() if hasattr(match, 'group') else str(match).strip()
    
    def _try_multiple_patterns(self, patterns_list, text: str, confidence: float = 0.9) -> tuple[str, float] | None:
        """다중 패턴을 순차적으로 시도하여 매칭"""
        for i, pattern in enumerate(patterns_list):
            match = pattern.search(text)
            if match:
                # 첫 번째 패턴일수록 높은 신뢰도
                adjusted_confidence = confidence - (i * 0.1)
                # 안전한 그룹 추출
                value = self._safe_group_extract(match, 1)
                return value, max(0.5, adjusted_confidence)
        return None
    
    def extract_data(
        self, 
        text: str, 
        document_type: DocumentType,
        engine: ExtractionEngine = ExtractionEngine.UPSTAGE
    ) -> Dict[str, Any]:
        """
        문서 타입에 따른 데이터 추출 (다중 패턴 지원)
        
        Args:
            text: 추출된 텍스트
            document_type: 문서 타입
            engine: 사용된 추출 엔진
            
        Returns:
            추출된 구조화 데이터
        """
        
        if self.verbose:
            doc_type_name = document_type.value if hasattr(document_type, 'value') else str(document_type)
            logger.info(f"📊 {doc_type_name} 데이터 추출 시작")
        
        # 문서 타입별 추출 함수 호출
        if document_type == DocumentType.INVOICE:
            return self._extract_invoice_data(text, engine)
        elif document_type == DocumentType.TAX_INVOICE:
            return self._extract_tax_invoice_data(text, engine)
        elif document_type == DocumentType.BILL_OF_LADING:
            return self._extract_bill_of_lading_data(text, engine)
        elif document_type == DocumentType.EXPORT_DECLARATION:
            return self._extract_export_declaration_data(text, engine)
        elif document_type == DocumentType.REMITTANCE_ADVICE:
            return self._extract_transfer_confirmation_data(text, engine)
        else:
            return {}
    
    def _extract_invoice_data(self, text: str, engine: ExtractionEngine) -> Dict[str, Any]:
        """인보이스 데이터 추출"""
        
        data = {}
        
        # 송품장 번호 - 개선된 패턴
        invoice_patterns = [
            re.compile(r'invoice\s*(?:no\.?)?\s*:?\s*([A-Z0-9-]+)', re.IGNORECASE),
            re.compile(r'송품장\s*번호\s*:?\s*([A-Z0-9-]+)', re.IGNORECASE),
            re.compile(r'commercial\s*invoice\s*(?:no\.?)?\s*:?\s*([A-Z0-9-]+)', re.IGNORECASE)
        ]
        for pattern in invoice_patterns:
            if match := pattern.search(text):
                data["invoice_number"] = create_field_data(
                    value=self._safe_group_extract(match, 1).strip(),
                    confidence=0.9,
                    engine=engine
                )
                break
        
        # 품목/내역 - 더 정확한 추출
        description_patterns = [
            re.compile(r'description\s*of\s*goods?\s*:?\s*([^\n]{1,100})', re.IGNORECASE),
            re.compile(r'품목\s*:?\s*([^\n]{1,100})', re.IGNORECASE),
            re.compile(r'commodity\s*:?\s*([^\n]{1,100})', re.IGNORECASE)
        ]
        for pattern in description_patterns:
            if match := pattern.search(text):
                description = self._safe_group_extract(match, 1).strip()
                # 너무 긴 텍스트는 첫 50자만 취함
                if len(description) > 50:
                    description = description[:50] + "..."
                data["description"] = create_field_data(
                    value=description,
                    confidence=0.8,
                    engine=engine
                )
                break
        
        # B/L 번호 - 표준 형식
        bl_patterns = [
            re.compile(r'b/?l\s*(?:no\.?)?\s*:?\s*([A-Z]{2,4}\d{6,12})', re.IGNORECASE),
            re.compile(r'bill\s*of\s*lading\s*(?:no\.?)?\s*:?\s*([A-Z]{2,4}\d{6,12})', re.IGNORECASE)
        ]
        for pattern in bl_patterns:
            if match := pattern.search(text):
                data["bl_number"] = create_field_data(
                    value=self._safe_group_extract(match, 1).strip(),
                    confidence=0.9,
                    engine=engine
                )
                break
        
        # 컨테이너 번호 - 표준 형식
        container_pattern = re.compile(r'container\s*(?:no\.?)?\s*:?\s*([A-Z]{4}\d{7})', re.IGNORECASE)
        if match := container_pattern.search(text):
            data["container_number"] = create_field_data(
                value=self._safe_group_extract(match, 1).strip(),
                confidence=0.9,
                engine=engine
            )
        
        # 중량 정보 - 정확한 숫자 추출
        weight_patterns = [
            re.compile(r'gross\s*weight\s*:?\s*([0-9,]+\.?\d*)\s*(?:kg|kgs)', re.IGNORECASE),
            re.compile(r'weight\s*:?\s*([0-9,]+\.?\d*)\s*(?:kg|kgs)', re.IGNORECASE),
            re.compile(r'총\s*중량\s*:?\s*([0-9,]+\.?\d*)\s*(?:kg|kgs)', re.IGNORECASE)
        ]
        for pattern in weight_patterns:
            if match := pattern.search(text):
                data["gross_weight"] = create_field_data(
                    value=self._safe_group_extract(match, 1).replace(',', ''),
                    confidence=0.8,
                    engine=engine
                )
                break
        
        # 금액 정보 (KRW) - 개선된 패턴
        krw_patterns = [
            re.compile(r'원화\s*공급가\s*:?\s*₩?\s*([0-9,]+)', re.IGNORECASE),
            re.compile(r'krw\s*amount\s*:?\s*₩?\s*([0-9,]+)', re.IGNORECASE),
            re.compile(r'₩\s*([0-9,]+)', re.IGNORECASE)
        ]
        for pattern in krw_patterns:
            if match := pattern.search(text):
                data["krw_amount"] = create_field_data(
                    value=self._safe_group_extract(match, 1).replace(',', ''),
                    confidence=0.8,
                    engine=engine
                )
                break
        
        # VAT 정보 - 정확한 패턴
        vat_patterns = [
            re.compile(r'v\.?a\.?t\.?\s*:?\s*₩?\s*([0-9,]+)', re.IGNORECASE),
            re.compile(r'부가세\s*:?\s*₩?\s*([0-9,]+)', re.IGNORECASE),
            re.compile(r'부가가치세\s*:?\s*₩?\s*([0-9,]+)', re.IGNORECASE)
        ]
        for pattern in vat_patterns:
            if match := pattern.search(text):
                data["vat_amount"] = create_field_data(
                    value=self._safe_group_extract(match, 1).replace(',', ''),
                    confidence=0.8,
                    engine=engine
                )
                break
        
        # 출발지 - 정확한 패턴
        pol_patterns = [
            re.compile(r'port\s*of\s*loading\s*:?\s*([A-Z][^,\n]{1,30})', re.IGNORECASE),
            re.compile(r'p\.?o\.?l\.?\s*:?\s*([A-Z][^,\n]{1,30})', re.IGNORECASE),
            re.compile(r'출발지\s*:?\s*([^,\n]{1,30})', re.IGNORECASE)
        ]
        for pattern in pol_patterns:
            if match := pattern.search(text):
                data["port_of_loading"] = create_field_data(
                    value=self._safe_group_extract(match, 1).strip(),
                    confidence=0.8,
                    engine=engine
                )
                break
        
        # 목적지 - 정확한 패턴
        pod_patterns = [
            re.compile(r'port\s*of\s*discharge\s*:?\s*([A-Z][^,\n]{1,30})', re.IGNORECASE),
            re.compile(r'p\.?o\.?d\.?\s*:?\s*([A-Z][^,\n]{1,30})', re.IGNORECASE),
            re.compile(r'도착지\s*:?\s*([^,\n]{1,30})', re.IGNORECASE)
        ]
        for pattern in pod_patterns:
            if match := pattern.search(text):
                data["port_of_discharge"] = create_field_data(
                    value=self._safe_group_extract(match, 1).strip(),
                    confidence=0.8,
                    engine=engine
                )
                break
        
        if self.verbose and data:
            logger.info(f"📊 인보이스 데이터 {len(data)}개 필드 추출 완료")
        
        return data
    
    def _extract_tax_invoice_data(self, text: str, engine: ExtractionEngine) -> Dict[str, Any]:
        """세금계산서 데이터 추출 (다중 패턴)"""
        
        data = {}
        patterns = self.document_patterns.get(DocumentType.TAX_INVOICE, {})
        
        # 세금계산서 번호 (다중 패턴)
        if "tax_invoice_number" in patterns:
            result = self._try_multiple_patterns(patterns["tax_invoice_number"], text, 0.9)
            if result:
                value, confidence = result
                data["tax_invoice_number"] = create_field_data(
                    value=value,
                    confidence=confidence,
                    engine=engine
                )
        
        # 공급가액 (다중 패턴)
        if "supply_amount" in patterns:
            result = self._try_multiple_patterns(patterns["supply_amount"], text, 0.9)
            if result:
                value, confidence = result
                clean_value = value.replace(',', '').replace('₩', '').strip()
                data["supply_amount"] = create_field_data(
                    value=clean_value,
                    confidence=confidence,
                    engine=engine
                )
        
        # 세액 (다중 패턴)
        if "tax_amount" in patterns:
            result = self._try_multiple_patterns(patterns["tax_amount"], text, 0.9)
            if result:
                value, confidence = result
                clean_value = value.replace(',', '').replace('₩', '').strip()
                data["tax_amount"] = create_field_data(
                    value=clean_value,
                    confidence=confidence,
                    engine=engine
                )
        
        # 합계금액 (다중 패턴)
        if "total_amount" in patterns:
            result = self._try_multiple_patterns(patterns["total_amount"], text, 0.9)
            if result:
                value, confidence = result
                clean_value = value.replace(',', '').replace('₩', '').strip()
                data["total_amount"] = create_field_data(
                    value=clean_value,
                    confidence=confidence,
                    engine=engine
                )
        
        # 발급일자
        if match := self.patterns["date_kr"].search(text):
            data["issue_date"] = create_field_data(
                value=self._safe_group_extract(match, 0).strip(),
                confidence=0.8,
                engine=engine
            )
        
        # 공급자/공급받는자
        supplier_pattern = re.compile(r'공급자.*?상호.*?:?\s*(.+?)(?:\n|$)', re.IGNORECASE)
        if match := supplier_pattern.search(text):
            data["supplier_name"] = create_field_data(
                value=self._safe_group_extract(match, 1).strip(),
                confidence=0.8,
                engine=engine
            )
        
        buyer_pattern = re.compile(r'공급받는자.*?상호.*?:?\s*(.+?)(?:\n|$)', re.IGNORECASE)
        if match := buyer_pattern.search(text):
            data["buyer_name"] = create_field_data(
                value=self._safe_group_extract(match, 1).strip(),
                confidence=0.8,
                engine=engine
            )
        
        if self.verbose and data:
            logger.info(f"📊 세금계산서 데이터 {len(data)}개 필드 추출 완료")
        
        return data
    
    def _extract_bill_of_lading_data(self, text: str, engine: ExtractionEngine) -> Dict[str, Any]:
        """선하증권 데이터 추출 (다중 패턴)"""
        
        data = {}
        patterns = self.document_patterns.get(DocumentType.BILL_OF_LADING, {})
        
        # B/L 번호 (다중 패턴)
        if "bl_number" in patterns:
            result = self._try_multiple_patterns(patterns["bl_number"], text, 0.9)
            if result:
                value, confidence = result
                data["bl_number"] = create_field_data(
                    value=value[:20],  # 길이 제한
                    confidence=confidence,
                    engine=engine
                )
        
        # 선박명 (다중 패턴, 길이 제한: 50자)
        if "vessel_name" in patterns:
            result = self._try_multiple_patterns(patterns["vessel_name"], text, 0.8)
            if result:
                value, confidence = result
                data["vessel_name"] = create_field_data(
                    value=value[:50],
                    confidence=confidence,
                    engine=engine
                )
        
        # 항차 (다중 패턴, 길이 제한: 20자)
        if "voyage_number" in patterns:
            result = self._try_multiple_patterns(patterns["voyage_number"], text, 0.8)
            if result:
                value, confidence = result
                data["voyage_number"] = create_field_data(
                    value=value[:20],
                    confidence=confidence,
                    engine=engine
                )
        
        # 출발항 (다중 패턴, 길이 제한: 50자)
        if "port_of_loading" in patterns:
            result = self._try_multiple_patterns(patterns["port_of_loading"], text, 0.8)
            if result:
                value, confidence = result
                data["port_of_loading"] = create_field_data(
                    value=value[:50],
                    confidence=confidence,
                    engine=engine
                )
        
        # 도착항 (다중 패턴, 길이 제한: 50자)
        if "port_of_discharge" in patterns:
            result = self._try_multiple_patterns(patterns["port_of_discharge"], text, 0.8)
            if result:
                value, confidence = result
                data["port_of_discharge"] = create_field_data(
                    value=value[:50],
                    confidence=confidence,
                    engine=engine
                )
        
        # 총중량
        weight_pattern = re.compile(r'gross.*?weight.*?([0-9,]+\.?\d*)', re.IGNORECASE)
        if match := weight_pattern.search(text):
            data["gross_weight"] = create_field_data(
                value=self._safe_group_extract(match, 1).replace(',', ''),
                confidence=0.8,
                engine=engine
            )
        
        # 컨테이너 번호
        if match := self.patterns["container"].search(text):
            data["container_number"] = create_field_data(
                value=self._safe_group_extract(match, 0).strip(),
                confidence=0.9,
                engine=engine
            )
        
        if self.verbose and data:
            logger.info(f"📊 선하증권 데이터 {len(data)}개 필드 추출 완료")
        
        return data
    
    def _extract_export_declaration_data(self, text: str, engine: ExtractionEngine) -> Dict[str, Any]:
        """수출신고필증 데이터 추출"""
        
        data = {}
        
        # 신고번호 - 더 정확한 패턴
        decl_patterns = [
            re.compile(r'신고번호\s*([0-9]{5}-[0-9]{2}-[0-9]{6}[A-Z]?)', re.IGNORECASE),
            re.compile(r'신고번호\s*(\d{5}-\d{2}-\d{6}[A-Z]?)', re.IGNORECASE),
            re.compile(r'(\d{5}-\d{2}-\d{6}[A-Z]?)(?=\s*\d{3}-[A-Z]\d)', re.IGNORECASE)
        ]
        for pattern in decl_patterns:
            if match := pattern.search(text):
                data["declaration_number"] = create_field_data(
                    value=self._safe_group_extract(match, 1).strip(),
                    confidence=0.9,
                    engine=engine
                )
                break
        
        # 송품장 부호 - 개선된 패턴
        invoice_patterns = [
            re.compile(r'송품장\s*부호\s*([A-Z0-9-]+)', re.IGNORECASE),
            re.compile(r'송품장번호\s*([A-Z0-9-]+)', re.IGNORECASE)
        ]
        for pattern in invoice_patterns:
            if match := pattern.search(text):
                data["invoice_symbol"] = create_field_data(
                    value=self._safe_group_extract(match, 1).strip(),
                    confidence=0.8,
                    engine=engine
                )
                break
        
        # 목적국 - 더 정확한 추출
        country_patterns = [
            re.compile(r'목적국\s+([A-Z]{2,3})\s+', re.IGNORECASE),
            re.compile(r'목적국\s*:?\s*([A-Z]{2,3})(?:\s|$)', re.IGNORECASE),
            re.compile(r'목적국\s*([A-Z]{2,3})\s+\d+', re.IGNORECASE)
        ]
        for pattern in country_patterns:
            if match := pattern.search(text):
                data["destination_country"] = create_field_data(
                    value=self._safe_group_extract(match, 1).strip(),
                    confidence=0.9,
                    engine=engine
                )
                break
        
        # 적재항 - 개선된 패턴
        port_patterns = [
            re.compile(r'적재항\s+([A-Z]{5})\s+', re.IGNORECASE),
            re.compile(r'적재항\s*:?\s*([A-Z]{5})(?:\s|$)', re.IGNORECASE),
            re.compile(r'(\w+항)(?=\s+\(항공사\)|$)', re.IGNORECASE)
        ]
        for pattern in port_patterns:
            if match := pattern.search(text):
                data["loading_port"] = create_field_data(
                    value=self._safe_group_extract(match, 1).strip(),
                    confidence=0.8,
                    engine=engine
                )
                break
        
        # 세번부호 - HS 코드 정확한 패턴
        hs_patterns = [
            re.compile(r'세번부호\s*([0-9]{4}\.?[0-9]{2}\.?[0-9]{2})', re.IGNORECASE),
            re.compile(r'세번\s*([0-9]{4}\.?[0-9]{2}\.?[0-9]{2})', re.IGNORECASE),
            re.compile(r'HS.*?([0-9]{4}\.?[0-9]{2}\.?[0-9]{2})', re.IGNORECASE)
        ]
        for pattern in hs_patterns:
            if match := pattern.search(text):
                data["hs_code"] = create_field_data(
                    value=self._safe_group_extract(match, 1).strip(),
                    confidence=0.8,
                    engine=engine
                )
                break
        
        # 총중량 - 정확한 숫자 추출
        weight_patterns = [
            re.compile(r'총\s*중량\s*([0-9,]+\.?\d*)\s*(?:kg|KG)', re.IGNORECASE),
            re.compile(r'중량\s*([0-9,]+\.?\d*)\s*(?:kg|KG)', re.IGNORECASE)
        ]
        for pattern in weight_patterns:
            if match := pattern.search(text):
                data["gross_weight"] = create_field_data(
                    value=self._safe_group_extract(match, 1).replace(',', ''),
                    confidence=0.8,
                    engine=engine
                )
                break
        
        # 컨테이너 번호 - 표준 형식
        container_pattern = re.compile(r'([A-Z]{4}\d{7})', re.IGNORECASE)
        if match := container_pattern.search(text):
            data["container_number"] = create_field_data(
                value=self._safe_group_extract(match, 1).strip(),
                confidence=0.9,
                engine=engine
            )
        
        if self.verbose and data:
            logger.info(f"📊 수출신고필증 데이터 {len(data)}개 필드 추출 완료")
        
        return data
    
    def _extract_transfer_confirmation_data(self, text: str, engine: ExtractionEngine) -> Dict[str, Any]:
        """이체확인증 데이터 추출"""
        
        data = {}
        
        # 승인번호
        approval_pattern = re.compile(r'승인번호.*?([0-9-]+)', re.IGNORECASE)
        if match := approval_pattern.search(text):
            data["approval_number"] = create_field_data(
                value=self._safe_group_extract(match, 1).strip(),
                confidence=0.9,
                engine=engine
            )
        
        # 송금금액
        amount_pattern = re.compile(r'(?:송금)?금액.*?([₩$]?\s*[0-9,]+)', re.IGNORECASE)
        if match := amount_pattern.search(text):
            value = self._safe_group_extract(match, 1).replace(',', '').replace('₩', '').replace('$', '').strip()
            data["transfer_amount"] = create_field_data(
                value=value,
                confidence=0.9,
                engine=engine
            )
        
        # 은행명
        bank_pattern = re.compile(r'은행.*?:?\s*(.+?)(?:\n|$)', re.IGNORECASE)
        if match := bank_pattern.search(text):
            data["bank_name"] = create_field_data(
                value=self._safe_group_extract(match, 1).strip(),
                confidence=0.8,
                engine=engine
            )
        
        # 계좌번호
        if match := self.patterns["account"].search(text):
            data["account_number"] = create_field_data(
                value=self._safe_group_extract(match, 0).strip(),
                confidence=0.9,
                engine=engine
            )
        
        # 송금일자
        if match := self.patterns["date_kr"].search(text):
            data["transfer_date"] = create_field_data(
                value=self._safe_group_extract(match, 0).strip(),
                confidence=0.8,
                engine=engine
            )
        
        # 예금주 (supplier_name으로 매핑)
        supplier_patterns = [
            re.compile(r'예금주\s*:?\s*(.+?)(?:\n|$)', re.IGNORECASE),
            re.compile(r'수신자\s*:?\s*(.+?)(?:\n|$)', re.IGNORECASE),
            re.compile(r'받는\s*사람\s*:?\s*(.+?)(?:\n|$)', re.IGNORECASE),
            re.compile(r'입금\s*받는\s*자\s*:?\s*(.+?)(?:\n|$)', re.IGNORECASE)
        ]
        for pattern in supplier_patterns:
            if match := pattern.search(text):
                data["supplier_name"] = create_field_data(
                    value=self._safe_group_extract(match, 1).strip(),
                    confidence=0.9,
                    engine=engine
                )
                break
        
        if self.verbose and data:
            logger.info(f"📊 이체확인증 데이터 {len(data)}개 필드 추출 완료")
        
        return data


# 향후 AI 기반 추출 기능을 추가할 수 있는 공간