"""
Business Settlement PDF Analysis System

무역 정산 PDF 문서 자동 분석 시스템
- Upstage Document AI 기반 고성능 텍스트 추출
- 다중 엔진 자동 폴백 시스템 (Upstage → PyMuPDF → pdfplumber → Tesseract)
- 무역문서 타입 자동 감지 (인보이스, 수출신고필증, 선하증권, 세금계산서, 이체확인증)
- 구조화된 데이터 추출 및 JSON 결과 저장
"""

__version__ = "1.0.0"
__author__ = "Business Settlement Team"

from .models import (
    DocumentType,
    ProcessingStatus,
    ExtractionEngine,
    FieldData,
    InvoiceData,
    ExportDeclarationData,
    BillOfLadingData,
    TaxInvoiceData,
    TransferConfirmationData,
    DocumentDetection,
    PDFProcessingResult,
    BatchProcessingRequest,
    BatchProcessingResult,
    create_field_data,
    get_document_model,
    create_results_directory
)

from .pdf_parser import (
    PDFParsingEngine,
    DocumentTypeDetector,
    PDFProcessor
)

from .utils import (
    validate_pdf_file,
    get_file_info,
    clean_text,
    console,
    save_json_result
)

__all__ = [
    # 핵심 클래스
    "PDFProcessor",
    "PDFParsingEngine",
    "DocumentTypeDetector",
    
    # 데이터 모델
    "DocumentType",
    "ProcessingStatus", 
    "ExtractionEngine",
    "FieldData",
    "InvoiceData",
    "ExportDeclarationData",
    "BillOfLadingData",
    "TaxInvoiceData",
    "TransferConfirmationData",
    "DocumentDetection",
    "PDFProcessingResult",
    "BatchProcessingRequest",
    "BatchProcessingResult",
    
    # 유틸리티 함수
    "create_field_data",
    "get_document_model",
    "create_results_directory",
    "validate_pdf_file",
    "get_file_info",
    "clean_text",
    "save_json_result",
    "console"
]