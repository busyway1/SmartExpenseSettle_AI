"""
Business Settlement PDF 분석 시스템 - 유틸리티 함수들

파일 처리, JSON 저장, 데이터 정제 등의 헬퍼 함수들을 제공합니다.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from rich.console import Console

# Rich 콘솔 객체
console = Console()


def save_json_result(data: Any, file_path: str) -> None:
    """
    데이터를 JSON 파일로 저장
    
    Args:
        data: 저장할 데이터 (Pydantic 모델 또는 딕셔너리)
        file_path: 저장할 파일 경로
    """
    
    # Pydantic 모델인 경우 딕셔너리로 변환
    if hasattr(data, 'model_dump'):
        data_dict = data.model_dump()
    else:
        data_dict = data
    
    # JSON 저장
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(
            data_dict,
            f,
            ensure_ascii=False,
            indent=2,
            default=_json_serializer
        )


def _json_serializer(obj: Any) -> Any:
    """JSON 직렬화를 위한 커스텀 시리얼라이저"""
    
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, Path):
        return str(obj)
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    else:
        return str(obj)


def clean_text(text: str) -> str:
    """
    텍스트 정제 (공백, 특수문자 정리)
    
    Args:
        text: 정제할 텍스트
        
    Returns:
        정제된 텍스트
    """
    
    if not text:
        return ""
    
    # 연속된 공백을 하나로 변경
    text = re.sub(r'\s+', ' ', text)
    
    # 앞뒤 공백 제거
    text = text.strip()
    
    return text


def get_file_info(file_path: str) -> Dict[str, Any]:
    """
    파일 정보 조회
    
    Args:
        file_path: 파일 경로
        
    Returns:
        파일 정보 딕셔너리
    """
    
    file_path_obj = Path(file_path)
    
    if not file_path_obj.exists():
        return {"error": "파일이 존재하지 않습니다"}
    
    stat = file_path_obj.stat()
    
    return {
        "name": file_path_obj.name,
        "stem": file_path_obj.stem,
        "suffix": file_path_obj.suffix,
        "size_bytes": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "absolute_path": str(file_path_obj.absolute()),
        "is_pdf": file_path_obj.suffix.lower() == '.pdf'
    }


def validate_pdf_file(file_path: str) -> Dict[str, Any]:
    """
    PDF 파일 유효성 검증
    
    Args:
        file_path: PDF 파일 경로
        
    Returns:
        검증 결과
    """
    
    result = {
        "is_valid": False,
        "error": None,
        "warnings": [],
        "info": {}
    }
    
    try:
        file_path_obj = Path(file_path)
        
        # 파일 존재 확인
        if not file_path_obj.exists():
            result["error"] = "파일이 존재하지 않습니다"
            return result
        
        # 확장자 확인
        if file_path_obj.suffix.lower() != '.pdf':
            result["error"] = "PDF 파일이 아닙니다"
            return result
        
        # 파일 크기 확인
        file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
        if file_size_mb > 50:  # 50MB 제한
            result["warnings"].append(f"파일 크기가 큽니다: {file_size_mb:.1f}MB")
        
        # PDF 파일 구조 확인 (PyMuPDF 사용)
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(file_path)
            page_count = len(doc)
            
            if page_count == 0:
                result["error"] = "PDF에 페이지가 없습니다"
                return result
            
            if page_count > 100:
                result["warnings"].append(f"페이지 수가 많습니다: {page_count}페이지")
            
            result["info"] = {
                "page_count": page_count,
                "file_size_mb": round(file_size_mb, 2),
                "is_encrypted": doc.needs_pass,
                "metadata": doc.metadata
            }
            
            doc.close()
            
        except Exception as e:
            result["error"] = f"PDF 파일이 손상되었거나 읽을 수 없습니다: {str(e)}"
            return result
        
        result["is_valid"] = True
        
    except Exception as e:
        result["error"] = f"파일 검증 오류: {str(e)}"
    
    return result