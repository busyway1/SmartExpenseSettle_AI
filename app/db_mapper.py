"""
DB 매핑 로직 - Backend output을 Supabase DB input 형태로 변환

Backend의 FieldData 기반 추출 결과를 Supabase 테이블에 맞는 형태로 변환합니다.
각 문서 타입별로 특화된 매핑 로직을 제공합니다.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from decimal import Decimal

from .models import (
    DocumentType,
    FieldData,
    InvoiceData,
    TaxInvoiceData,
    BillOfLadingData,
    ExportDeclarationData,
    TransferConfirmationData,
    PDFProcessingResult
)


class DatabaseMapper:
    """Backend output을 DB input 형태로 변환하는 매퍼"""
    
    def __init__(self):
        self.supabase_url = "https://lnfdpxtdtmbcefhshmdm.supabase.co"
        self.supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxuZmRweHRkdG1iY2VmaHNobWRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI0NTQ4NzUsImV4cCI6MjA2ODAzMDg3NX0.dX7XtJ_Dj8PSD9PihPj26UFKLYXBJAy7b6d8Dez5FSg"
    
    def generate_id(self) -> str:
        """고유 ID 생성"""
        return str(uuid.uuid4())[:8]
    
    def extract_field_value(self, field: Optional[FieldData]) -> Any:
        """FieldData에서 실제 값을 추출"""
        if field is None:
            return None
            
        # field.value 접근 전에 hasattr로 확인
        if not hasattr(field, 'value') or field.value is None:
            return None
        
        value = field.value
        if isinstance(value, str):
            value = value.strip()
            # HTML 태그 제거
            import re
            value = re.sub(r'<[^>]+>', '', value)
            # 연속된 공백 제거
            value = re.sub(r'\s+', ' ', value)
            value = value.strip()
            if not value:
                return None
        
        return value
    
    def safe_convert_to_number(self, value: Any) -> Optional[Union[int, float]]:
        """안전하게 숫자로 변환"""
        if value is None:
            return None
        
        try:
            # 문자열인 경우 쉼표 제거 후 변환
            if isinstance(value, str):
                clean_value = value.replace(',', '').replace('₩', '').replace('$', '').strip()
                if not clean_value:
                    return None
                return float(clean_value)
            elif isinstance(value, (int, float, Decimal)):
                return float(value)
            else:
                return None
        except (ValueError, TypeError):
            return None
    
    def safe_truncate_string(self, value: str, max_length: int = 40) -> str:
        """문자열을 안전하게 자르기"""
        if not value:
            return value
        if len(value) > max_length:
            return value[:max_length]
        return value
    
    def safe_truncate_char1(self, value: str) -> str:
        """character(1) 필드용 - 첫 번째 문자만 반환"""
        if not value:
            return "N"
        return value[0]  # 첫 번째 문자만
    
    def safe_convert_to_date(self, value: Any) -> Optional[str]:
        """안전하게 날짜 형식으로 변환 (YYYY-MM-DD)"""
        if value is None:
            return None
        
        try:
            if isinstance(value, str):
                # 다양한 날짜 형식 처리
                date_str = value.strip()
                # 한국어 날짜 형식 처리 (2024년 01월 15일)
                if '년' in date_str and '월' in date_str:
                    import re
                    match = re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일?', date_str)
                    if match:
                        year, month, day = match.groups()
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                
                # 기타 날짜 형식 처리
                for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%m/%d/%Y', '%d/%m/%Y']:
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        return dt.strftime('%Y-%m-%d')
                    except ValueError:
                        continue
                
                return None
            return None
        except Exception:
            return None

    def map_invoice_to_db(self, invoice_data: InvoiceData, file_name: str, page_num: int = 1) -> Dict[str, List[Dict[str, Any]]]:
        """인보이스 데이터를 INVOICE_ITEM_TB와 INVOICE_TOTAL_TB에 매핑"""
        
        # 공통 필드 추출 (문자열 필드는 40자 제한)
        invoice_no = self.safe_truncate_string(self.extract_field_value(invoice_data.invoice_number))
        bl_no = self.safe_truncate_string(self.extract_field_value(invoice_data.bl_number))
        gross_wt = self.safe_convert_to_number(self.extract_field_value(invoice_data.gross_weight))
        cont_no = self.safe_truncate_string(self.extract_field_value(invoice_data.container_number))
        origin = self.safe_truncate_string(self.extract_field_value(invoice_data.port_of_loading))
        dest = self.safe_truncate_string(self.extract_field_value(invoice_data.port_of_discharge))
        supply_amt = self.safe_convert_to_number(self.extract_field_value(invoice_data.krw_amount))
        vat_amt = self.safe_convert_to_number(self.extract_field_value(invoice_data.vat_amount))
        
        # INVOICE_TOTAL_TB 레코드 생성
        total_id = self.generate_id()
        invoice_total_record = {
            "id": total_id,
            "invoice_no": invoice_no,
            "file_no": None,  # 필요시 추가
            "bl_no": bl_no,
            "gross_wt": gross_wt,
            "cont_no": cont_no,
            "origin": origin,
            "dest": dest,
            "supply_amt": int(supply_amt) if supply_amt else None,
            "vat_amt": int(vat_amt) if vat_amt else None,
            "company_nm": None,  # 필요시 추가
            "date": None,  # 필요시 추가
            "file_nm": self.safe_truncate_string(file_name),
            "page": page_num,
            "id_page": f"{total_id}_{page_num}"
        }
        
        # INVOICE_ITEM_TB 레코드 생성 (품목별)
        item_records = []
        description = self.extract_field_value(invoice_data.description)
        
        # 1. description 필드가 있는 경우 추가
        if description:
            item_record = {
                "id": self.generate_id(),
                "file_no": None,
                "item": description,
                "item_value": int(supply_amt) if supply_amt else None,
                "item_vat": int(vat_amt) if vat_amt else None,
                "invoice_no": invoice_no,
                "file_nm": self.safe_truncate_string(file_name),
                "page": page_num,
                "id_invoice": total_id
            }
            item_records.append(item_record)
        
        # 2. description이 없어도 기본 아이템 생성 (인보이스 번호 기준)
        if not item_records and invoice_no:
            default_item = {
                "id": self.generate_id(),
                "file_no": None,
                "item": "[기본값] 기본 인보이스 항목",
                "item_value": int(supply_amt) if supply_amt else None,
                "item_vat": int(vat_amt) if vat_amt else None,
                "invoice_no": invoice_no,
                "file_nm": self.safe_truncate_string(file_name),
                "page": page_num,
                "id_invoice": total_id
            }
            item_records.append(default_item)
        
        return {
            "INVOICE_TOTAL_TB": [invoice_total_record],
            "INVOICE_ITEM_TB": item_records
        }
    
    def map_tax_invoice_to_db(self, tax_data: TaxInvoiceData, file_name: str, page_num: int = 1) -> Dict[str, List[Dict[str, Any]]]:
        """세금계산서 데이터를 TAX_INVOICE_TB에 매핑"""
        
        supply_amt = self.safe_convert_to_number(self.extract_field_value(tax_data.supply_amount))
        tax_amt = self.safe_convert_to_number(self.extract_field_value(tax_data.tax_amount))
        total_amt = self.safe_convert_to_number(self.extract_field_value(tax_data.total_amount))
        issue_date = self.safe_convert_to_date(self.extract_field_value(tax_data.issue_date))
        
        # total_amount가 있고 supply_amount가 없는 경우 total_amount를 supply_amount로 사용
        if total_amt and not supply_amt:
            supply_amt = total_amt
        
        record = {
            "id": self.generate_id(),
            "approval_no": self.safe_truncate_char1(self.extract_field_value(tax_data.tax_invoice_number) or "N"),
            "supply_amt": int(supply_amt) if supply_amt else None,
            "vat_amt": int(tax_amt) if tax_amt else None,
            "company_nm": self.safe_truncate_string(self.extract_field_value(tax_data.supplier_name) or "미상", 30),
            "date": issue_date or datetime.now().strftime('%Y-%m-%d'),  # 기본값 설정
            "supplier_biz_no": "N",  # character(1) 제한으로 단일 문자만
            "buyer_reg_no": "N",     # character(1) 제한으로 단일 문자만
            "file_nm": self.safe_truncate_string(file_name),
            "page": page_num
        }
        
        return {
            "TAX_INVOICE_TB": [record]
        }
    
    def map_bl_to_db(self, bl_data: BillOfLadingData, file_name: str, page_num: int = 1) -> Dict[str, List[Dict[str, Any]]]:
        """선하증권 데이터를 BL_TB에 매핑"""
        
        gross_wt = self.safe_convert_to_number(self.extract_field_value(bl_data.gross_weight))
        
        # 모든 문자열 필드에 40자 제한 적용
        bl_no = self.safe_truncate_string(self.extract_field_value(bl_data.bl_number))
        cont_no = self.safe_truncate_string(self.extract_field_value(bl_data.container_number))
        origin = self.safe_truncate_string(self.extract_field_value(bl_data.port_of_loading))
        dest = self.safe_truncate_string(self.extract_field_value(bl_data.port_of_discharge))
        file_nm = self.safe_truncate_string(file_name)
        
        record = {
            "id": self.generate_id(),
            "bl_no": bl_no,
            "invoice_no": None,  # 필요시 추가
            "gross_wt": gross_wt,
            "cont_no": cont_no,
            "origin": origin,
            "dest": dest,
            "date": None,  # 필요시 추가
            "file_nm": file_nm,
            "page": page_num
        }
        
        return {
            "BL_TB": [record]
        }
    
    def map_export_permit_to_db(self, export_data: ExportDeclarationData, file_name: str, page_num: int = 1) -> Dict[str, List[Dict[str, Any]]]:
        """수출신고필증 데이터를 EXPORT_PERMIT_BASIC_TB와 EXPORT_PERMIT_DETAILS_TB에 매핑"""
        
        decl_no = self.safe_truncate_string(self.extract_field_value(export_data.declaration_number))
        gross_wt = self.safe_convert_to_number(self.extract_field_value(export_data.gross_weight))
        
        # EXPORT_PERMIT_BASIC_TB 레코드
        basic_record = {
            "id": self.generate_id(),
            "decl_no": decl_no,
            "invoice_no": self.safe_truncate_string(self.extract_field_value(export_data.invoice_symbol)),
            "gross_wt": gross_wt,
            "cont_no": self.safe_truncate_string(self.extract_field_value(export_data.container_number)),
            "origin": self.safe_truncate_string(self.extract_field_value(export_data.loading_port)),
            "dest": self.safe_truncate_string(self.extract_field_value(export_data.destination_country)),
            "date": None,  # 필요시 추가
            "file_nm": self.safe_truncate_string(file_name),
            "page": page_num
        }
        
        # EXPORT_PERMIT_DETAILS_TB 레코드
        detail_records = []
        hs_code = self.safe_truncate_string(self.extract_field_value(export_data.hs_code))
        if hs_code:
            detail_record = {
                "id": self.generate_id(),
                "decl_no": decl_no,
                "hs_code": hs_code,
                "line_no": "1",  # 기본값
                "net_wt": gross_wt  # gross_wt를 net_wt로 사용
            }
            detail_records.append(detail_record)
        
        return {
            "EXPORT_PERMIT_BASIC_TB": [basic_record],
            "EXPORT_PERMIT_DETAILS_TB": detail_records
        }
    
    def map_payment_conf_to_db(self, payment_data: TransferConfirmationData, file_name: str, page_num: int = 1) -> Dict[str, List[Dict[str, Any]]]:
        """이체확인증 데이터를 PAYMENT_CONF_TB에 매핑"""
        
        transfer_amt = self.safe_convert_to_number(self.extract_field_value(payment_data.transfer_amount))
        transfer_date = self.safe_convert_to_date(self.extract_field_value(payment_data.transfer_date))
        
        record = {
            "id": self.generate_id(),
            "supply_amt": int(transfer_amt) if transfer_amt else None,
            "company_nm": self.safe_truncate_string(self.extract_field_value(payment_data.supplier_name), 30),  # 30자 제한
            "date": transfer_date or datetime.now().strftime('%Y-%m-%d'),  # 기본값 설정
            "file_nm": self.safe_truncate_string(file_name),
            "page": page_num
        }
        
        return {
            "PAYMENT_CONF_TB": [record]
        }
    
    def map_pdf_result_to_db(self, pdf_result: PDFProcessingResult) -> Dict[str, List[Dict[str, Any]]]:
        """PDFProcessingResult를 DB 테이블들에 매핑"""
        
        all_mappings = {}
        file_name = pdf_result.file_name
        
        print(f"🔍 매핑 시작: {file_name}")
        print(f"  - 감지된 문서 수: {len(pdf_result.detected_documents)}")
        
        for i, doc_detection in enumerate(pdf_result.detected_documents):
            doc_type = doc_detection.document_type
            extracted_data = doc_detection.extracted_data
            page_range = doc_detection.page_range
            page_num = page_range[0] if page_range else 1
            
            print(f"  - 문서 {i+1}: {doc_type}, 페이지: {page_num}")
            print(f"    추출된 데이터 키: {list(extracted_data.keys()) if extracted_data else 'None'}")
            
            try:
                if doc_type == DocumentType.INVOICE and extracted_data:
                    # raw_text 제거하고 FieldData 구조 확인
                    clean_data = {k: v for k, v in extracted_data.items() if k != 'raw_text'}
                    print(f"    인보이스 데이터 변환 시도: {clean_data}")
                    invoice_data = InvoiceData(**clean_data)
                    mapping = self.map_invoice_to_db(invoice_data, file_name, page_num)
                    self._merge_mappings(all_mappings, mapping)
                    
                elif doc_type == DocumentType.TAX_INVOICE and extracted_data:
                    clean_data = {k: v for k, v in extracted_data.items() if k != 'raw_text'}
                    print(f"    세금계산서 데이터 변환 시도: {clean_data}")
                    
                    # tax_invoice_number가 없으면 기본값 생성
                    if 'tax_invoice_number' not in clean_data:
                        from .models import create_field_data
                        clean_data['tax_invoice_number'] = create_field_data("[기본값] 미상", 0.1)
                    
                    tax_data = TaxInvoiceData(**clean_data)
                    mapping = self.map_tax_invoice_to_db(tax_data, file_name, page_num)
                    self._merge_mappings(all_mappings, mapping)
                    
                elif doc_type == DocumentType.BILL_OF_LADING and extracted_data:
                    clean_data = {k: v for k, v in extracted_data.items() if k != 'raw_text'}
                    print(f"    B/L 데이터 변환 시도: {clean_data}")
                    
                    # bl_number가 없으면 기본값 생성
                    if 'bl_number' not in clean_data:
                        from .models import create_field_data
                        clean_data['bl_number'] = create_field_data("[기본값] 미상", 0.1)
                    
                    bl_data = BillOfLadingData(**clean_data)
                    mapping = self.map_bl_to_db(bl_data, file_name, page_num)
                    self._merge_mappings(all_mappings, mapping)
                    
                elif doc_type == DocumentType.EXPORT_DECLARATION and extracted_data:
                    clean_data = {k: v for k, v in extracted_data.items() if k != 'raw_text'}
                    print(f"    수출신고필증 데이터 변환 시도: {clean_data}")
                    
                    # declaration_number가 없으면 기본값 생성
                    if 'declaration_number' not in clean_data:
                        from .models import create_field_data
                        clean_data['declaration_number'] = create_field_data("[기본값] 미상", 0.1)
                    
                    export_data = ExportDeclarationData(**clean_data)
                    mapping = self.map_export_permit_to_db(export_data, file_name, page_num)
                    self._merge_mappings(all_mappings, mapping)
                    
                elif doc_type == DocumentType.REMITTANCE_ADVICE and extracted_data:
                    clean_data = {k: v for k, v in extracted_data.items() if k != 'raw_text'}
                    print(f"    이체확인증 데이터 변환 시도: {clean_data}")
                    
                    # supplier_name이 없으면 기본값 생성
                    if 'supplier_name' not in clean_data:
                        from .models import create_field_data
                        clean_data['supplier_name'] = create_field_data("[기본값] 미상", 0.1)
                    
                    payment_data = TransferConfirmationData(**clean_data)
                    mapping = self.map_payment_conf_to_db(payment_data, file_name, page_num)
                    self._merge_mappings(all_mappings, mapping)
                    
            except Exception as e:
                print(f"    ❌ {doc_type} 매핑 실패: {str(e)}")
                import traceback
                print(f"    스택 트레이스: {traceback.format_exc()}")
        
        print(f"✅ 매핑 완료: {len(all_mappings)}개 테이블")
        return all_mappings
    
    def _merge_mappings(self, target: Dict, source: Dict) -> None:
        """매핑 결과들을 병합"""
        for table_name, records in source.items():
            if table_name not in target:
                target[table_name] = []
            target[table_name].extend(records)


class SupabaseClient:
    """Supabase 클라이언트"""
    
    def __init__(self):
        self.url = "https://lnfdpxtdtmbcefhshmdm.supabase.co"
        self.key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxuZmRweHRkdG1iY2VmaHNobWRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI0NTQ4NzUsImV4cCI6MjA2ODAzMDg3NX0.dX7XtJ_Dj8PSD9PihPj26UFKLYXBJAy7b6d8Dez5FSg"
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
    
    def insert_records(self, table_name: str, records: List[Dict[str, Any]]) -> bool:
        """레코드들을 테이블에 삽입"""
        import requests
        import json
        
        if not records:
            print(f"⚠️ {table_name}: 삽입할 레코드가 없습니다")
            return True
        
        url = f"{self.url}/rest/v1/{table_name}"
        
        # 디버깅용 로그
        print(f"🔍 {table_name} 삽입 시도:")
        print(f"  - URL: {url}")
        print(f"  - 레코드 수: {len(records)}")
        print(f"  - 첫 번째 레코드: {json.dumps(records[0], indent=2, ensure_ascii=False)}")
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                data=json.dumps(records, ensure_ascii=False),
                timeout=30
            )
            
            print(f"📡 응답 상태: {response.status_code}")
            print(f"📡 응답 내용: {response.text}")
            
            if response.status_code in [200, 201]:
                print(f"✅ {table_name}에 {len(records)}개 레코드 삽입 완료")
                return True
            else:
                print(f"❌ {table_name} 삽입 실패: {response.status_code}")
                print(f"   오류 내용: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ {table_name} 삽입 중 예외 발생: {str(e)}")
            import traceback
            print(f"   스택 트레이스: {traceback.format_exc()}")
            return False
    
    def save_all_mappings(self, mappings: Dict[str, List[Dict[str, Any]]]) -> bool:
        """모든 매핑 결과를 DB에 저장"""
        success = True
        
        for table_name, records in mappings.items():
            if records:
                result = self.insert_records(table_name, records)
                success = success and result
        
        return success


def convert_backend_to_db(pdf_result: PDFProcessingResult) -> Dict[str, List[Dict[str, Any]]]:
    """Backend output을 DB input 형태로 변환하는 메인 함수"""
    mapper = DatabaseMapper()
    return mapper.map_pdf_result_to_db(pdf_result)


def save_to_supabase(mappings: Dict[str, List[Dict[str, Any]]]) -> bool:
    """매핑 결과를 Supabase에 저장하는 메인 함수"""
    client = SupabaseClient()
    return client.save_all_mappings(mappings)