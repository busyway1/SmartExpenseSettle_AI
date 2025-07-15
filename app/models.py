"""
Business Settlement PDF 분석 시스템 - 데이터 모델

Python 3.13.5와 Pydantic v2.8.2 기준으로 작성된 데이터 모델들
✨ 다중 PDF 처리 및 Upstage Document AI 연동에 최적화
✨ 여러 파일 경로 지원 + 단일 PDF 내 여러 문서 타입 혼재 처리
✨ 파일별 results 폴더 자동 생성 및 [파일명].json 저장
"""

from enum import Enum
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Dict, Optional
from pathlib import Path
import os

from pydantic import BaseModel, Field, ConfigDict, field_validator
from pydantic.types import PositiveFloat, PositiveInt


class DocumentType(str, Enum):
    """지원하는 무역문서 타입"""
    INVOICE = "invoice"                           # 인보이스
    EXPORT_DECLARATION = "export_declaration"    # 수출신고필증  
    BILL_OF_LADING = "bill_of_lading"           # 선하증권
    TAX_INVOICE = "tax_invoice"                  # 세금계산서
    REMITTANCE_ADVICE = "remittance_advice"  # 송금증
    MIXED = "mixed"                              # 여러 문서 타입 혼재
    UNKNOWN = "unknown"                          # 알 수 없는 문서 타입


class ProcessingStatus(str, Enum):
    """처리 상태"""
    PENDING = "pending"          # 대기 중
    PROCESSING = "processing"    # 처리 중
    COMPLETED = "completed"      # 완료
    FAILED = "failed"           # 실패
    PARTIAL = "partial"         # 부분 완료


class ExtractionEngine(str, Enum):
    """데이터 추출 엔진"""
    UPSTAGE = "upstage"          # Upstage Document AI (메인)
    PDFPLUMBER = "pdfplumber"    # pdfplumber (백업)
    PYMUPDF = "pymupdf"          # PyMuPDF (빠른 처리)
    TESSERACT = "tesseract"      # Tesseract OCR (최후)


class FieldData(BaseModel):
    """개별 필드 데이터 구조"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True
    )
    
    value: str | int | float | Decimal | None = Field(
        default=None,
        description="추출된 값"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="추출 신뢰도 (0.0-1.0)"
    )
    source_location: tuple[int, int] | None = Field(
        default=None,
        description="PDF에서의 위치 (x, y 좌표)"
    )
    extraction_engine: ExtractionEngine = Field(
        default=ExtractionEngine.UPSTAGE,
        description="사용된 추출 엔진"
    )
    page_number: int = Field(
        default=1,
        ge=1,
        description="PDF 페이지 번호"
    )


# 각 문서 타입별 특화 모델들 (기존과 동일하지만 FieldData 업데이트)

class InvoiceData(BaseModel):
    """인보이스 데이터 모델"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    # 기본 정보
    invoice_number: FieldData = Field(description="송품장 번호 (INVOICE)")
    description: Optional[FieldData] = Field(default=None, description="품목 (DESCRIPTION, 내역, 운임내역)")
    
    # 금액 정보  
    krw_amount: Optional[FieldData] = Field(default=None, description="품목별 원화 공급가 (KRW)")
    vat_amount: Optional[FieldData] = Field(default=None, description="품목별 VAT (V.A.T)")
    
    # 물류 정보
    bl_number: Optional[FieldData] = Field(default=None, description="B/L 번호 (M. B/L NO., H. B/L NO., B/L NO.)")
    gross_weight: Optional[FieldData] = Field(default=None, description="총 중량 (WEIGHT, GROSS WEIGHT)")
    container_number: Optional[FieldData] = Field(default=None, description="컨테이너 번호 (CONTAINER)")
    
    # 출발지/목적지
    port_of_loading: Optional[FieldData] = Field(default=None, description="출발지 (P.O.L)")
    port_of_discharge: Optional[FieldData] = Field(default=None, description="도착지 (P.O.D)")


class ExportDeclarationData(BaseModel):
    """수출신고필증 데이터 모델"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    declaration_number: FieldData = Field(description="신고번호")
    invoice_symbol: Optional[FieldData] = Field(default=None, description="송품장 부호") 
    gross_weight: Optional[FieldData] = Field(default=None, description="총 중량")
    container_number: Optional[FieldData] = Field(default=None, description="컨테이너 번호")
    loading_port: Optional[FieldData] = Field(default=None, description="적재항")
    destination_country: Optional[FieldData] = Field(default=None, description="목적국")
    hs_code: Optional[FieldData] = Field(default=None, description="세번부호")


class BillOfLadingData(BaseModel):
    """선하증권 데이터 모델"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    bl_number: FieldData = Field(description="B/L 번호")
    port_of_loading: Optional[FieldData] = Field(default=None, description="PORT OF LOADING")
    port_of_discharge: Optional[FieldData] = Field(default=None, description="PORT OF DISCHARGE") 
    gross_weight: Optional[FieldData] = Field(default=None, description="GROSS WEIGHT")
    container_number: Optional[FieldData] = Field(default=None, description="컨테이너 번호")
    vessel_name: Optional[FieldData] = Field(default=None, description="선박명")
    voyage_number: Optional[FieldData] = Field(default=None, description="항차")


class TaxInvoiceData(BaseModel):
    """세금계산서 데이터 모델"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    tax_invoice_number: FieldData = Field(description="세금계산서번호")
    supply_amount: Optional[FieldData] = Field(default=None, description="공급가액")
    tax_amount: Optional[FieldData] = Field(default=None, description="세액")
    total_amount: Optional[FieldData] = Field(default=None, description="합계금액")
    issue_date: Optional[FieldData] = Field(default=None, description="발급일자")
    supplier_name: Optional[FieldData] = Field(default=None, description="공급자상호")
    buyer_name: Optional[FieldData] = Field(default=None, description="공급받는자상호")


class TransferConfirmationData(BaseModel):
    """이체확인증 데이터 모델"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    supplier_name: FieldData = Field(description="공급자상호")
    buyer_name: Optional[FieldData] = Field(default=None, description="발급일자")
    transfer_date: Optional[FieldData] = Field(default=None, description="송금일자")
    approval_number: Optional[FieldData] = Field(default=None, description="승인번호")
    transfer_amount: Optional[FieldData] = Field(default=None, description="송금금액")
    bank_name: Optional[FieldData] = Field(default=None, description="은행명")
    account_number: Optional[FieldData] = Field(default=None, description="계좌번호")


class DocumentDetection(BaseModel):
    """단일 PDF 내 문서 감지 결과"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True
    )
    
    document_type: DocumentType = Field(description="감지된 문서 타입")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="감지 신뢰도"
    )
    page_range: tuple[int, int] = Field(description="문서 페이지 범위 (시작, 끝)")
    key_indicators: List[str] = Field(
        default_factory=list,
        description="문서 타입을 판단한 핵심 키워드들"
    )
    extracted_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="추출된 구조화 데이터"
    )


class PDFProcessingResult(BaseModel):
    """단일 PDF 파일 처리 결과"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
        json_encoders={
            datetime: lambda dt: dt.isoformat(),
            Path: lambda p: str(p)
        }
    )
    
    # 파일 기본 정보
    file_path: str = Field(description="원본 PDF 파일 경로")
    file_name: str = Field(description="파일명 (확장자 제외)")
    file_size_mb: float = Field(description="파일 크기 (MB)")
    total_pages: int = Field(description="총 페이지 수")
    
    # 처리 상태 및 시간
    status: ProcessingStatus = Field(description="처리 상태")
    processing_start_time: datetime = Field(
        default_factory=datetime.now,
        description="처리 시작 시간"
    )
    processing_end_time: datetime | None = Field(
        default=None,
        description="처리 완료 시간"
    )
    processing_duration_seconds: float = Field(
        default=0.0,
        description="처리 시간 (초)"
    )
    
    # 문서 감지 결과
    detected_documents: List[DocumentDetection] = Field(
        default_factory=list,
        description="PDF 내 감지된 문서들"
    )
    primary_document_type: DocumentType = Field(
        default=DocumentType.UNKNOWN,
        description="주 문서 타입"
    )
    
    # 추출 엔진 정보
    extraction_engines_used: List[ExtractionEngine] = Field(
        default_factory=list,
        description="사용된 추출 엔진들"
    )
    primary_engine: ExtractionEngine = Field(
        default=ExtractionEngine.UPSTAGE,
        description="주 추출 엔진"
    )
    
    # 결과 저장 정보
    results_saved_to: str | None = Field(
        default=None,
        description="결과 JSON 파일 저장 경로"
    )
    
    # 오류 및 경고
    errors: List[str] = Field(
        default_factory=list,
        description="발생한 오류 목록"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="경고 메시지 목록"
    )
    
    def add_error(self, error_message: str) -> None:
        """오류 메시지 추가"""
        self.errors.append(f"[{datetime.now().isoformat()}] {error_message}")
    
    def add_warning(self, warning_message: str) -> None:
        """경고 메시지 추가"""
        self.warnings.append(f"[{datetime.now().isoformat()}] {warning_message}")
    
    def get_extraction_summary(self) -> Dict[str, Any]:
        """추출 요약 정보 반환"""
        total_documents = len(self.detected_documents)
        successful_extractions = sum(
            1 for doc in self.detected_documents 
            if doc.extracted_data and doc.confidence > 0.5
        )
        
        return {
            "total_documents_detected": total_documents,
            "successful_extractions": successful_extractions,
            "success_rate": successful_extractions / total_documents if total_documents > 0 else 0.0,
            "primary_document_type": self.primary_document_type,
            "processing_time_seconds": self.processing_duration_seconds,
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings)
        }


class BatchProcessingRequest(BaseModel):
    """배치 처리 요청 모델"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    file_paths: List[str] = Field(
        min_length=1,
        description="처리할 PDF 파일 경로들"
    )
    output_directory: str | None = Field(
        default=None,
        description="결과 저장 디렉토리 (기본: 각 파일 경로의 results 폴더)"
    )
    force_engine: ExtractionEngine | None = Field(
        default=None,
        description="강제로 사용할 추출 엔진 (기본: 자동 선택)"
    )
    parallel_processing: bool = Field(
        default=True,
        description="병렬 처리 여부"
    )
    max_workers: int = Field(
        default=4,
        ge=1,
        le=16,
        description="최대 워커 수 (병렬 처리 시)"
    )
    
    @field_validator('file_paths')
    @classmethod
    def validate_file_paths(cls, v: List[str]) -> List[str]:
        """파일 경로 검증"""
        validated_paths = []
        for path_str in v:
            path = Path(path_str)
            if not path.exists():
                raise ValueError(f"파일이 존재하지 않습니다: {path_str}")
            if not path.suffix.lower() == '.pdf':
                raise ValueError(f"PDF 파일이 아닙니다: {path_str}")
            validated_paths.append(str(path.resolve()))
        return validated_paths


class BatchProcessingResult(BaseModel):
    """배치 처리 결과 모델"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
        json_encoders={
            datetime: lambda dt: dt.isoformat()
        }
    )
    
    # 배치 처리 정보
    batch_id: str = Field(description="배치 처리 ID")
    total_files: int = Field(description="총 파일 수")
    
    # 처리 시간
    batch_start_time: datetime = Field(
        default_factory=datetime.now,
        description="배치 처리 시작 시간"
    )
    batch_end_time: datetime | None = Field(
        default=None,
        description="배치 처리 완료 시간"
    )
    total_processing_time_seconds: float = Field(
        default=0.0,
        description="전체 처리 시간 (초)"
    )
    
    # 개별 파일 처리 결과
    file_results: List[PDFProcessingResult] = Field(
        default_factory=list,
        description="각 파일별 처리 결과"
    )
    
    # 요약 통계
    successful_files: int = Field(default=0, description="성공한 파일 수")
    failed_files: int = Field(default=0, description="실패한 파일 수")
    partial_files: int = Field(default=0, description="부분 성공 파일 수")
    
    def get_batch_summary(self) -> Dict[str, Any]:
        """배치 처리 요약 정보"""
        return {
            "batch_id": self.batch_id,
            "total_files": self.total_files,
            "successful_files": self.successful_files,
            "failed_files": self.failed_files,
            "partial_files": self.partial_files,
            "success_rate": self.successful_files / self.total_files if self.total_files > 0 else 0.0,
            "total_processing_time_seconds": self.total_processing_time_seconds,
            "average_time_per_file": self.total_processing_time_seconds / self.total_files if self.total_files > 0 else 0.0,
            "total_documents_extracted": sum(
                len(result.detected_documents) for result in self.file_results
            )
        }


# 문서 타입별 데이터 모델 매핑
DOCUMENT_DATA_MODELS = {
    DocumentType.INVOICE: InvoiceData,
    DocumentType.EXPORT_DECLARATION: ExportDeclarationData,
    DocumentType.BILL_OF_LADING: BillOfLadingData,
    DocumentType.TAX_INVOICE: TaxInvoiceData,
    DocumentType.REMITTANCE_ADVICE: TransferConfirmationData,
}


# 유틸리티 함수들

def create_field_data(
    value: Any = None,
    confidence: float = 0.0,
    location: tuple[int, int] | None = None,
    engine: ExtractionEngine = ExtractionEngine.UPSTAGE,
    page: int = 1
) -> FieldData:
    """FieldData 객체 생성 헬퍼 함수"""
    return FieldData(
        value=value,
        confidence=confidence,
        source_location=location,
        extraction_engine=engine,
        page_number=page
    )


def get_document_model(doc_type: DocumentType) -> type[BaseModel]:
    """문서 타입에 해당하는 데이터 모델 반환"""
    return DOCUMENT_DATA_MODELS.get(doc_type, InvoiceData)


def create_results_directory(file_path: str) -> str:
    """파일 경로에서 results 폴더 생성 및 경로 반환"""
    file_path_obj = Path(file_path)
    results_dir = file_path_obj.parent / "results"
    results_dir.mkdir(exist_ok=True)
    
    json_filename = f"{file_path_obj.stem}.json"
    return str(results_dir / json_filename)


def generate_batch_id() -> str:
    """배치 처리 ID 생성"""
    from datetime import datetime
    import uuid
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"batch_{timestamp}_{short_uuid}"