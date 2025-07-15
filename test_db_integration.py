#!/usr/bin/env python3
"""
DB 연동 테스트 스크립트

샘플 파일을 처리해서 DB 매핑 로직이 정상 작동하는지 확인합니다.
"""

import sys
import json
from pathlib import Path
from app.db_mapper import DatabaseMapper, SupabaseClient, convert_backend_to_db, save_to_supabase
from app.models import (
    DocumentType, 
    FieldData, 
    InvoiceData, 
    TaxInvoiceData,
    BillOfLadingData,
    ExportDeclarationData,
    TransferConfirmationData,
    DocumentDetection,
    PDFProcessingResult,
    ProcessingStatus,
    ExtractionEngine,
    create_field_data
)
from datetime import datetime

def create_sample_invoice_data():
    """샘플 인보이스 데이터 생성"""
    return InvoiceData(
        invoice_number=create_field_data("INV-2024-001", 0.9),
        description=create_field_data("OCEAN FREIGHT", 0.8),
        krw_amount=create_field_data("1500000", 0.9),
        vat_amount=create_field_data("150000", 0.9),
        bl_number=create_field_data("ABCD1234567", 0.8),
        gross_weight=create_field_data("1500.5", 0.8),
        container_number=create_field_data("ABCD1234567", 0.8),
        port_of_loading=create_field_data("BUSAN", 0.9),
        port_of_discharge=create_field_data("LOS ANGELES", 0.9)
    )

def create_sample_tax_invoice_data():
    """샘플 세금계산서 데이터 생성"""
    return TaxInvoiceData(
        tax_invoice_number=create_field_data("20241201-001", 0.9),
        supply_amount=create_field_data("1000000", 0.9),
        tax_amount=create_field_data("100000", 0.9),
        total_amount=create_field_data("1100000", 0.9),
        issue_date=create_field_data("2024-12-01", 0.9),
        supplier_name=create_field_data("(주)테스트물류", 0.8),
        buyer_name=create_field_data("(주)고객사", 0.8)
    )

def create_sample_bl_data():
    """샘플 B/L 데이터 생성"""
    return BillOfLadingData(
        bl_number=create_field_data("ABCD1234567", 0.9),
        port_of_loading=create_field_data("BUSAN", 0.9),
        port_of_discharge=create_field_data("LOS ANGELES", 0.9),
        gross_weight=create_field_data("1500.5", 0.8),
        container_number=create_field_data("ABCD1234567", 0.8),
        vessel_name=create_field_data("HANJIN MIAMI", 0.8),
        voyage_number=create_field_data("024W", 0.8)
    )

def create_sample_export_permit_data():
    """샘플 수출신고필증 데이터 생성"""
    return ExportDeclarationData(
        declaration_number=create_field_data("24112012345678", 0.9),
        invoice_symbol=create_field_data("INV-2024-001", 0.9),
        gross_weight=create_field_data("1500.5", 0.8),
        container_number=create_field_data("ABCD1234567", 0.8),
        loading_port=create_field_data("BUSAN", 0.9),
        destination_country=create_field_data("US", 0.9),
        hs_code=create_field_data("8504409000", 0.8)
    )

def create_sample_payment_conf_data():
    """샘플 이체확인증 데이터 생성"""
    return TransferConfirmationData(
        supplier_name=create_field_data("(주)테스트물류", 0.8),
        buyer_name=create_field_data("2024-12-01", 0.8),  # 이 필드는 실제로는 발급일자
        transfer_date=create_field_data("2024-12-01", 0.9),
        approval_number=create_field_data("123456789", 0.8),
        transfer_amount=create_field_data("1650000", 0.9),
        bank_name=create_field_data("국민은행", 0.8),
        account_number=create_field_data("123-45-678901", 0.8)
    )

def create_sample_pdf_result():
    """샘플 PDF 처리 결과 생성"""
    # 각 문서 타입별 감지 결과 생성
    invoice_data = create_sample_invoice_data()
    tax_data = create_sample_tax_invoice_data()
    bl_data = create_sample_bl_data()
    export_data = create_sample_export_permit_data()
    payment_data = create_sample_payment_conf_data()
    
    detections = [
        DocumentDetection(
            document_type=DocumentType.INVOICE,
            confidence=0.9,
            page_range=(1, 1),
            key_indicators=["INVOICE", "FREIGHT"],
            extracted_data=invoice_data.model_dump()
        ),
        DocumentDetection(
            document_type=DocumentType.TAX_INVOICE,
            confidence=0.9,
            page_range=(2, 2),
            key_indicators=["세금계산서", "공급가액"],
            extracted_data=tax_data.model_dump()
        ),
        DocumentDetection(
            document_type=DocumentType.BILL_OF_LADING,
            confidence=0.8,
            page_range=(3, 3),
            key_indicators=["BILL OF LADING", "VESSEL"],
            extracted_data=bl_data.model_dump()
        ),
        DocumentDetection(
            document_type=DocumentType.EXPORT_DECLARATION,
            confidence=0.8,
            page_range=(4, 4),
            key_indicators=["수출신고필증", "신고번호"],
            extracted_data=export_data.model_dump()
        ),
        DocumentDetection(
            document_type=DocumentType.REMITTANCE_ADVICE,
            confidence=0.8,
            page_range=(5, 5),
            key_indicators=["이체확인증", "송금"],
            extracted_data=payment_data.model_dump()
        )
    ]
    
    result = PDFProcessingResult(
        file_path="/test/sample_document.pdf",
        file_name="sample_document",
        file_size_mb=2.5,
        total_pages=5,
        status=ProcessingStatus.COMPLETED,
        detected_documents=detections,
        primary_document_type=DocumentType.MIXED,
        extraction_engines_used=[ExtractionEngine.UPSTAGE],
        primary_engine=ExtractionEngine.UPSTAGE,
        processing_duration_seconds=3.5
    )
    
    return result

def test_mapping_logic():
    """매핑 로직 테스트"""
    print("🧪 DB 매핑 로직 테스트 시작...")
    
    # 샘플 데이터 생성
    pdf_result = create_sample_pdf_result()
    
    # 매핑 수행
    mapper = DatabaseMapper()
    mappings = mapper.map_pdf_result_to_db(pdf_result)
    
    print(f"\n📊 매핑 결과:")
    for table_name, records in mappings.items():
        print(f"  - {table_name}: {len(records)}개 레코드")
        if records:
            print(f"    예시: {json.dumps(records[0], indent=2, ensure_ascii=False)}")
    
    return mappings

def test_db_connection():
    """DB 연결 테스트"""
    print("\n🔗 Supabase 연결 테스트...")
    
    client = SupabaseClient()
    
    # 테스트용 데이터 생성
    test_record = {
        "id": "test-connection",
        "company_nm": "연결테스트",
        "date": "2024-12-15",
        "file_nm": "test.pdf",
        "page": 1
    }
    
    try:
        # PAYMENT_CONF_TB에 테스트 레코드 삽입
        success = client.insert_records("PAYMENT_CONF_TB", [test_record])
        if success:
            print("✅ DB 연결 및 삽입 테스트 성공")
        else:
            print("❌ DB 삽입 테스트 실패")
        return success
    except Exception as e:
        print(f"❌ DB 연결 테스트 실패: {str(e)}")
        return False

def test_full_integration():
    """전체 통합 테스트"""
    print("\n🚀 전체 통합 테스트 시작...")
    
    # 1. 매핑 로직 테스트
    mappings = test_mapping_logic()
    
    # 2. DB 연결 테스트
    db_connected = test_db_connection()
    
    if not db_connected:
        print("❌ DB 연결 실패로 통합 테스트 중단")
        return False
    
    # 3. 실제 데이터 저장 테스트
    print("\n💾 실제 데이터 저장 테스트...")
    
    try:
        success = save_to_supabase(mappings)
        if success:
            print("✅ 전체 통합 테스트 성공!")
            print("\n📈 저장된 데이터 요약:")
            total_records = sum(len(records) for records in mappings.values())
            print(f"  - 총 {len(mappings)}개 테이블에 {total_records}개 레코드 저장")
            return True
        else:
            print("❌ 데이터 저장 실패")
            return False
    except Exception as e:
        print(f"❌ 통합 테스트 실패: {str(e)}")
        return False

def main():
    """메인 함수"""
    print("🔬 SmartExpenseSettle DB 연동 테스트")
    print("=" * 50)
    
    try:
        # 전체 통합 테스트 실행
        success = test_full_integration()
        
        if success:
            print("\n🎉 모든 테스트가 성공했습니다!")
            print("이제 실제 PDF 파일로 테스트할 수 있습니다:")
            print("  python cli.py -f samples/sample.pdf --save-to-db")
        else:
            print("\n💥 테스트 실패. 설정을 확인해주세요.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 예상치 못한 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()