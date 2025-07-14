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
        
        # 문서별 특화 패턴
        self.document_patterns = {
            DocumentType.INVOICE: {
                "invoice_number": re.compile(r'(?:invoice|송품장).*?(?:no\.?|번호).*?([A-Z0-9-]+)', re.IGNORECASE),
                "description": re.compile(r'(?:description|품목|내역).*?:?\s*(.+?)(?:\n|$)', re.IGNORECASE),
                "amount": re.compile(r'(?:amount|금액|가격).*?([₩$]?\s*[\d,]+\.?\d*)', re.IGNORECASE),
            },
            DocumentType.TAX_INVOICE: {
                "tax_number": re.compile(r'(?:세금계산서|tax invoice).*?번호.*?([0-9-]+)', re.IGNORECASE),
                "supply_amount": re.compile(r'공급가액.*?([₩]?\s*[\d,]+)', re.IGNORECASE),
                "tax_amount": re.compile(r'세액.*?([₩]?\s*[\d,]+)', re.IGNORECASE),
                "total_amount": re.compile(r'합계.*?([₩]?\s*[\d,]+)', re.IGNORECASE),
            },
            DocumentType.BILL_OF_LADING: {
                "vessel": re.compile(r'(?:vessel|선박명).*?:?\s*(.+?)(?:\n|$)', re.IGNORECASE),
                "voyage": re.compile(r'(?:voyage|항차).*?:?\s*(.+?)(?:\n|$)', re.IGNORECASE),
                "port_loading": re.compile(r'port.*?loading.*?:?\s*(.+?)(?:\n|$)', re.IGNORECASE),
                "port_discharge": re.compile(r'port.*?discharge.*?:?\s*(.+?)(?:\n|$)', re.IGNORECASE),
            }
        }
    
    def extract_data(
        self, 
        text: str, 
        document_type: DocumentType,
        engine: ExtractionEngine = ExtractionEngine.UPSTAGE
    ) -> Dict[str, Any]:
        """
        문서 타입에 따른 데이터 추출
        
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
        elif document_type == DocumentType.TRANSFER_CONFIRMATION:
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
                    value=match.group(1).strip(),
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
                description = match.group(1).strip()
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
                    value=match.group(1).strip(),
                    confidence=0.9,
                    engine=engine
                )
                break
        
        # 컨테이너 번호 - 표준 형식
        container_pattern = re.compile(r'container\s*(?:no\.?)?\s*:?\s*([A-Z]{4}\d{7})', re.IGNORECASE)
        if match := container_pattern.search(text):
            data["container_number"] = create_field_data(
                value=match.group(1).strip(),
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
                    value=match.group(1).replace(',', ''),
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
                    value=match.group(1).replace(',', ''),
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
                    value=match.group(1).replace(',', ''),
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
                    value=match.group(1).strip(),
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
                    value=match.group(1).strip(),
                    confidence=0.8,
                    engine=engine
                )
                break
        
        if self.verbose and data:
            logger.info(f"📊 인보이스 데이터 {len(data)}개 필드 추출 완료")
        
        return data
    
    def _extract_tax_invoice_data(self, text: str, engine: ExtractionEngine) -> Dict[str, Any]:
        """세금계산서 데이터 추출"""
        
        data = {}
        patterns = self.document_patterns[DocumentType.TAX_INVOICE]
        
        # 세금계산서 번호
        if match := patterns["tax_number"].search(text):
            data["tax_invoice_number"] = create_field_data(
                value=match.group(1).strip(),
                confidence=0.9,
                engine=engine
            )
        
        # 공급가액
        if match := patterns["supply_amount"].search(text):
            value = match.group(1).replace(',', '').replace('₩', '').strip()
            data["supply_amount"] = create_field_data(
                value=value,
                confidence=0.9,
                engine=engine
            )
        
        # 세액
        if match := patterns["tax_amount"].search(text):
            value = match.group(1).replace(',', '').replace('₩', '').strip()
            data["tax_amount"] = create_field_data(
                value=value,
                confidence=0.9,
                engine=engine
            )
        
        # 합계금액
        if match := patterns["total_amount"].search(text):
            value = match.group(1).replace(',', '').replace('₩', '').strip()
            data["total_amount"] = create_field_data(
                value=value,
                confidence=0.9,
                engine=engine
            )
        
        # 발급일자
        if match := self.patterns["date_kr"].search(text):
            data["issue_date"] = create_field_data(
                value=match.group(0).strip(),
                confidence=0.8,
                engine=engine
            )
        
        # 공급자/공급받는자
        supplier_pattern = re.compile(r'공급자.*?상호.*?:?\s*(.+?)(?:\n|$)', re.IGNORECASE)
        if match := supplier_pattern.search(text):
            data["supplier_name"] = create_field_data(
                value=match.group(1).strip(),
                confidence=0.8,
                engine=engine
            )
        
        buyer_pattern = re.compile(r'공급받는자.*?상호.*?:?\s*(.+?)(?:\n|$)', re.IGNORECASE)
        if match := buyer_pattern.search(text):
            data["buyer_name"] = create_field_data(
                value=match.group(1).strip(),
                confidence=0.8,
                engine=engine
            )
        
        if self.verbose and data:
            logger.info(f"📊 세금계산서 데이터 {len(data)}개 필드 추출 완료")
        
        return data
    
    def _extract_bill_of_lading_data(self, text: str, engine: ExtractionEngine) -> Dict[str, Any]:
        """선하증권 데이터 추출"""
        
        data = {}
        patterns = self.document_patterns[DocumentType.BILL_OF_LADING]
        
        # B/L 번호
        if match := self.patterns["bl_number"].search(text):
            data["bl_number"] = create_field_data(
                value=match.group(0).strip(),
                confidence=0.9,
                engine=engine
            )
        
        # 선박명
        if match := patterns["vessel"].search(text):
            data["vessel_name"] = create_field_data(
                value=match.group(1).strip(),
                confidence=0.8,
                engine=engine
            )
        
        # 항차
        if match := patterns["voyage"].search(text):
            data["voyage_number"] = create_field_data(
                value=match.group(1).strip(),
                confidence=0.8,
                engine=engine
            )
        
        # 출발항
        if match := patterns["port_loading"].search(text):
            data["port_of_loading"] = create_field_data(
                value=match.group(1).strip(),
                confidence=0.8,
                engine=engine
            )
        
        # 도착항
        if match := patterns["port_discharge"].search(text):
            data["port_of_discharge"] = create_field_data(
                value=match.group(1).strip(),
                confidence=0.8,
                engine=engine
            )
        
        # 총중량
        weight_pattern = re.compile(r'gross.*?weight.*?([0-9,]+\.?\d*)', re.IGNORECASE)
        if match := weight_pattern.search(text):
            data["gross_weight"] = create_field_data(
                value=match.group(1).replace(',', ''),
                confidence=0.8,
                engine=engine
            )
        
        # 컨테이너 번호
        if match := self.patterns["container"].search(text):
            data["container_number"] = create_field_data(
                value=match.group(0).strip(),
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
                    value=match.group(1).strip(),
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
                    value=match.group(1).strip(),
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
                    value=match.group(1).strip(),
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
                    value=match.group(1).strip(),
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
                    value=match.group(1).strip(),
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
                    value=match.group(1).replace(',', ''),
                    confidence=0.8,
                    engine=engine
                )
                break
        
        # 컨테이너 번호 - 표준 형식
        container_pattern = re.compile(r'([A-Z]{4}\d{7})', re.IGNORECASE)
        if match := container_pattern.search(text):
            data["container_number"] = create_field_data(
                value=match.group(1).strip(),
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
                value=match.group(1).strip(),
                confidence=0.9,
                engine=engine
            )
        
        # 송금금액
        amount_pattern = re.compile(r'(?:송금)?금액.*?([₩$]?\s*[0-9,]+)', re.IGNORECASE)
        if match := amount_pattern.search(text):
            value = match.group(1).replace(',', '').replace('₩', '').replace('$', '').strip()
            data["transfer_amount"] = create_field_data(
                value=value,
                confidence=0.9,
                engine=engine
            )
        
        # 은행명
        bank_pattern = re.compile(r'은행.*?:?\s*(.+?)(?:\n|$)', re.IGNORECASE)
        if match := bank_pattern.search(text):
            data["bank_name"] = create_field_data(
                value=match.group(1).strip(),
                confidence=0.8,
                engine=engine
            )
        
        # 계좌번호
        if match := self.patterns["account"].search(text):
            data["account_number"] = create_field_data(
                value=match.group(0).strip(),
                confidence=0.9,
                engine=engine
            )
        
        # 송금일자
        if match := self.patterns["date_kr"].search(text):
            data["transfer_date"] = create_field_data(
                value=match.group(0).strip(),
                confidence=0.8,
                engine=engine
            )
        
        if self.verbose and data:
            logger.info(f"📊 이체확인증 데이터 {len(data)}개 필드 추출 완료")
        
        return data


# 향후 AI 기반 추출 기능을 추가할 수 있는 공간