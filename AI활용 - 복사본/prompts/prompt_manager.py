"""
프롬프트 매니저 - 모든 문서 유형별 프롬프트를 통합 관리
"""

from .export_declaration import get_export_declaration_prompt
from .tax_invoice import get_tax_invoice_prompt
from .invoice import get_invoice_prompt
from .bill_of_lading import get_bill_of_lading_prompt
from .transfer_receipt import get_transfer_receipt_prompt
from .general import get_general_prompt

class PromptManager:
    """문서 유형별 프롬프트 관리자"""
    
    @staticmethod
    def get_prompt(doc_type: str, text: str, file_name: str = "", page_number: int = None) -> str:
        """문서 유형에 따른 프롬프트 반환"""
        
        # 문서 유형별 프롬프트 매핑
        prompt_mapping = {
            "수출신고필증": get_export_declaration_prompt,
            "세금계산서": get_tax_invoice_prompt,
            "인보이스": get_invoice_prompt,
            "BL": get_bill_of_lading_prompt,
            "이체확인증": get_transfer_receipt_prompt,
        }
        
        # 해당 문서 유형의 프롬프트 함수가 있으면 사용
        if doc_type in prompt_mapping:
            return prompt_mapping[doc_type](text, file_name, page_number)
        else:
            # 기본 프롬프트 사용
            return get_general_prompt(text, doc_type, file_name, page_number)
    
    @staticmethod
    def get_supported_document_types() -> list:
        """지원되는 문서 유형 목록 반환"""
        return [
            "수출신고필증",
            "세금계산서", 
            "인보이스",
            "BL",
            "이체확인증"
        ]
    
    @staticmethod
    def is_supported_document_type(doc_type: str) -> bool:
        """지원되는 문서 유형인지 확인"""
        return doc_type in PromptManager.get_supported_document_types() 