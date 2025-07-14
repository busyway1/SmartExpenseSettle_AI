#!/usr/bin/env python3
"""
Business Settlement PDF 분석 시스템 - CLI 인터페이스

무역 관련 문서(인보이스, 수출신고필증, 선하증권, 세금계산서, 이체확인증)에서
핵심 데이터를 추출하여 구조화된 JSON 형태로 출력합니다.

사용법:
    python cli.py -f "path/to/document.pdf"
    python cli.py -f "invoice.pdf" --engine upstage --verbose
"""

import asyncio
import click
import json
import sys
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from datetime import datetime
import traceback

# 환경 변수 로드
from dotenv import load_dotenv
load_dotenv()

# 프로젝트 모듈 임포트
from app.pdf_parser import PDFProcessor
from app.models import (
    DocumentType, 
    ExtractionEngine, 
    ProcessingStatus,
    PDFProcessingResult
)
from app.utils import console, save_json_result
from app.data_extractor import DataExtractor

# 지원하는 문서 타입
SUPPORTED_TYPES = {
    "invoice": "인보이스",
    "export_declaration": "수출신고필증", 
    "bill_of_lading": "선하증권",
    "tax_invoice": "세금계산서",
    "transfer_confirmation": "이체확인증",
    "mixed": "혼재 문서",
    "unknown": "알 수 없음"
}

# 지원하는 엔진
SUPPORTED_ENGINES = {
    "upstage": "Upstage Document Parse (메인)",
    "pymupdf": "PyMuPDF (빠른 처리)",
    "pdfplumber": "pdfplumber (정확한 레이아웃)",
    "tesseract": "Tesseract OCR (최후 수단)"
}


@click.command()
@click.option(
    '--files', '-f',
    multiple=True,
    required=True,
    type=click.Path(exists=True),
    help='분석할 PDF 파일 경로들 (여러 파일 지원: -f file1.pdf -f file2.pdf)'
)
@click.option(
    '--engine',
    type=click.Choice(['upstage', 'pymupdf', 'pdfplumber', 'tesseract']),
    default='upstage',
    help='사용할 추출 엔진 (기본값: upstage)'
)
@click.option(
    '--output-dir', '-o',
    type=click.Path(),
    help='결과 저장 디렉토리 (기본값: ./output)'
)
@click.option(
    '--parallel/--sequential',
    default=False,
    help='병렬 처리 여부 (기본값: 순차)'
)
@click.option(
    '--max-workers',
    type=int,
    default=4,
    help='최대 워커 수 (병렬 처리 시, 기본값: 4)'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='상세한 로그 출력'
)
def main(
    files: tuple[str, ...], 
    engine: str,
    output_dir: str | None,
    parallel: bool,
    max_workers: int,
    verbose: bool
):
    """
    PDF 문서에서 무역 관련 데이터를 추출하는 CLI 도구
    
    ✨ 여러 PDF 파일 동시 처리 지원
    ✨ Upstage Document AI 연동으로 최고 성능
    ✨ 4개 엔진 자동 폴백 시스템
    """
    
    # 파일이 지정되지 않았을 때
    if not files:
        console.print("[red]❌ 처리할 PDF 파일을 지정해주세요.[/red]")
        console.print("사용법: python cli.py -f file1.pdf -f file2.pdf")
        return
    
    # 시작 메시지
    console.print(Panel.fit(
        "[bold blue]Business Settlement PDF 분석 시스템[/bold blue]\n"
        f"[cyan]Upstage Document AI 연동 | 4개 엔진 자동 폴백[/cyan]\n"
        f"처리 대상: {len(files)}개 파일 | 메인 엔진: {SUPPORTED_ENGINES.get(engine, engine)}",
        border_style="blue"
    ))
    
    # 출력 디렉토리 설정
    if not output_dir:
        output_dir = "./output"
    
    # 출력 디렉토리 생성
    Path(output_dir).mkdir(exist_ok=True)
    
    try:
        # 비동기 처리 실행
        asyncio.run(process_files(
            files, engine, output_dir, parallel, max_workers, verbose
        ))
        
    except Exception as e:
        console.print(f"[red]✗ 처리 오류: {str(e)}[/red]")
        if verbose:
            console.print("[red]상세 오류 정보:[/red]")
            console.print(traceback.format_exc())
        sys.exit(1)


async def process_files(
    files: tuple[str, ...],
    engine: str,
    output_dir: str,
    parallel: bool,
    max_workers: int,
    verbose: bool
):
    """파일 처리 메인 로직"""
    
    # Upstage API 키 확인
    upstage_api_key = os.getenv('UPSTAGE_API_KEY')
    if engine == 'upstage' and not upstage_api_key:
        console.print("[red]❌ UPSTAGE_API_KEY가 설정되지 않았습니다.[/red]")
        console.print("UPSTAGE_API_KEY를 .env 파일에 설정하거나 환경변수로 설정해주세요.")
        console.print("백업 엔진(pymupdf, pdfplumber)을 사용하세요.")
        return
    
    # 백업 엔진 사용 시에는 API 키가 없어도 됨
    if engine != 'upstage':
        upstage_api_key = None
    
    processor = PDFProcessor(upstage_api_key=upstage_api_key, verbose=verbose)
    extractor = DataExtractor(verbose=verbose)
    
    selected_engine = ExtractionEngine(engine)
    results = []
    
    if parallel and len(files) > 1:
        # 병렬 처리
        results = await process_files_parallel(
            files, processor, extractor, selected_engine, max_workers, verbose
        )
    else:
        # 순차 처리
        results = await process_files_sequential(
            files, processor, extractor, selected_engine, verbose
        )
    
    # 결과 저장 및 출력
    await save_and_display_results(results, output_dir, verbose)


async def process_files_parallel(
    files: tuple[str, ...],
    processor: PDFProcessor,
    extractor: DataExtractor,
    engine: ExtractionEngine,
    max_workers: int,
    verbose: bool
) -> list[PDFProcessingResult]:
    """병렬 파일 처리"""
    
    console.print(f"[cyan]병렬 처리 모드 (최대 {max_workers}개 동시 처리)[/cyan]")
    
    semaphore = asyncio.Semaphore(max_workers)
    results = []
    
    async def process_single_file(file_path: str):
        async with semaphore:
            return await process_single_pdf(file_path, processor, extractor, engine, verbose)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        
        task = progress.add_task(f"{len(files)}개 파일 처리 중...", total=len(files))
        
        tasks = [process_single_file(file_path) for file_path in files]
        
        for completed_task in asyncio.as_completed(tasks):
            result = await completed_task
            results.append(result)
            progress.advance(task, 1)
            
            if result.status == ProcessingStatus.COMPLETED:
                progress.update(task, description=f"성공 {len(results)}/{len(files)} 완료")
            else:
                progress.update(task, description=f"경고 {len(results)}/{len(files)} 처리됨")
    
    return results


async def process_files_sequential(
    files: tuple[str, ...],
    processor: PDFProcessor,
    extractor: DataExtractor,
    engine: ExtractionEngine,
    verbose: bool
) -> list[PDFProcessingResult]:
    """순차 파일 처리"""
    
    console.print("[cyan]순차 처리 모드[/cyan]")
    results = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        
        for i, file_path in enumerate(files, 1):
            task = progress.add_task(f"{Path(file_path).name} 처리 중...", total=None)
            
            result = await process_single_pdf(file_path, processor, extractor, engine, verbose)
            results.append(result)
            
            progress.update(task, description=f"완료 {i}/{len(files)}")
    
    return results


async def process_single_pdf(
    file_path: str,
    processor: PDFProcessor,
    extractor: DataExtractor,
    engine: ExtractionEngine,
    verbose: bool = False
) -> PDFProcessingResult:
    """단일 PDF 파일 처리"""
    
    try:
        # PDF 파싱 및 문서 타입 감지
        result = await processor.process_pdf(file_path, engine)
        
        # 데이터 추출 (각 감지된 문서별로)
        for detection in result.detected_documents:
            if detection.document_type != DocumentType.UNKNOWN:
                # 텍스트에서 구조화된 데이터 추출
                raw_text = detection.extracted_data.get("raw_text", "")
                if raw_text:
                    extracted_data = extractor.extract_data(
                        raw_text, 
                        detection.document_type, 
                        engine
                    )
                    # 기존 raw_text는 유지하고 새로 추출된 데이터만 업데이트
                    for key, value in extracted_data.items():
                        detection.extracted_data[key] = value
        
        return result
        
    except Exception as e:
        # 자세한 오류 정보 출력 (디버깅용)
        if verbose:
            console.print(f"[red]상세 오류: {str(e)}[/red]")
            import traceback
            console.print(f"[red]스택 트레이스: {traceback.format_exc()}[/red]")
        
        # 파일 정보 시도
        try:
            from app.utils import get_file_info
            file_info = get_file_info(file_path)
            file_size_mb = file_info.get("size_mb", 0.0)
            
            # PDF 페이지 수 확인 시도
            try:
                import fitz
                doc = fitz.open(file_path)
                total_pages = len(doc)
                doc.close()
            except:
                total_pages = 1  # 기본값을 1로 설정
        except:
            file_size_mb = 1.0
            total_pages = 1
        
        # 에러 결과 생성
        try:
            error_result = PDFProcessingResult(
                file_path=file_path,
                file_name=Path(file_path).stem,
                file_size_mb=file_size_mb,
                total_pages=total_pages,
                status=ProcessingStatus.FAILED
            )
            error_result.add_error(f"처리 실패: {str(e)}")
            return error_result
        except Exception as model_error:
            # PDFProcessingResult 생성도 실패한 경우
            if verbose:
                console.print(f"[red]모델 생성 오류: {str(model_error)}[/red]")
            # 최소한의 결과 반환
            class SimpleResult:
                def __init__(self):
                    self.file_path = file_path
                    self.file_name = Path(file_path).stem
                    self.file_size_mb = 1.0
                    self.total_pages = 1
                    self.status = ProcessingStatus.FAILED
                    self.errors = [f"처리 실패: {str(e)}"]
                    self.detected_documents = []
                    self.processing_duration_seconds = 0.0
                    self.primary_engine = ExtractionEngine.PYMUPDF
            
            return SimpleResult()


async def save_and_display_results(
    results: list[PDFProcessingResult],
    output_dir: str,
    verbose: bool
):
    """결과 저장 및 화면 출력"""
    
    successful_results = [r for r in results if r.status == ProcessingStatus.COMPLETED]
    failed_results = [r for r in results if r.status == ProcessingStatus.FAILED]
    
    # 파일별 JSON 저장
    saved_files = []
    
    for result in successful_results:
        try:
            # 수행시간을 포함한 JSON 파일 경로 생성
            duration_str = f"{result.processing_duration_seconds:.2f}s"
            timestamp = result.processing_start_time.strftime("%Y%m%d_%H%M%S")
            json_filename = f"{result.file_name}_{timestamp}_{duration_str}.json"
            json_path = Path(output_dir) / json_filename
            
            # JSON 저장
            save_json_result(result.model_dump(), str(json_path))
            result.results_saved_to = str(json_path)
            saved_files.append(str(json_path))
            
        except Exception as e:
            if verbose:
                console.print(f"[red]JSON 저장 실패 ({result.file_name}): {e}[/red]")
    
    # 결과 테이블 출력
    display_results_table(results)
    
    # 요약 통계
    display_final_summary(results, saved_files)


def display_results_table(results: list[PDFProcessingResult]):
    """결과 테이블 출력"""
    
    if not results:
        return
    
    console.print()
    
    # 파일별 결과 테이블
    table = Table(title="파일별 처리 결과", show_header=True, header_style="bold magenta")
    table.add_column("파일명", style="cyan", no_wrap=False, width=30)
    table.add_column("상태", style="green", justify="center", width=10)
    table.add_column("문서 타입", style="yellow", width=15)
    table.add_column("신뢰도", style="blue", justify="center", width=8)
    table.add_column("처리시간", style="white", justify="right", width=10)
    table.add_column("사용 엔진", style="magenta", width=12)
    table.add_column("오류", style="red", width=30)
    
    for result in results:
        status_emoji = {
            ProcessingStatus.COMPLETED: "성공",
            ProcessingStatus.FAILED: "실패", 
            ProcessingStatus.PARTIAL: "부분",
            ProcessingStatus.PROCESSING: "처리중",
            ProcessingStatus.PENDING: "대기"
        }.get(result.status, "알수없음")
        
        # 감지된 문서 정보
        if result.detected_documents:
            first_doc = result.detected_documents[0]
            doc_type = first_doc.document_type.value if hasattr(first_doc.document_type, 'value') else str(first_doc.document_type)
            confidence = f"{first_doc.confidence:.1%}"
        else:
            doc_type = "없음"
            confidence = "0%"
        
        # 오류 메시지
        error_msg = ""
        if result.errors:
            error_msg = result.errors[-1][:50] + "..." if len(result.errors[-1]) > 50 else result.errors[-1]
        
        table.add_row(
            Path(result.file_path).name,
            f"{status_emoji}",
            doc_type,
            confidence,
            f"{result.processing_duration_seconds:.1f}s",
            result.primary_engine.value if result.primary_engine and hasattr(result.primary_engine, 'value') else (str(result.primary_engine) if result.primary_engine else "N/A"),
            error_msg
        )
    
    console.print(table)


def display_final_summary(results: list[PDFProcessingResult], saved_files: list[str]):
    """최종 요약 정보 표시"""
    
    total_files = len(results)
    successful_files = len([r for r in results if r.status == ProcessingStatus.COMPLETED])
    failed_files = len([r for r in results if r.status == ProcessingStatus.FAILED])
    
    success_rate = successful_files / total_files if total_files > 0 else 0
    
    # 성공률 색상 결정
    if success_rate >= 0.9:
        rate_color = "green"
    elif success_rate >= 0.7:
        rate_color = "yellow"
    else:
        rate_color = "red"
    
    # 총 처리 시간
    total_time = sum(r.processing_duration_seconds for r in results)
    avg_time = total_time / total_files if total_files > 0 else 0
    
    # 총 문서 수
    total_documents = sum(len(r.detected_documents) for r in results)
    
    console.print()
    console.print(Panel(
        f"[bold {rate_color}]전체 성공률: {success_rate:.1%}[/bold {rate_color}]\n"
        f"[bold]성공: {successful_files}개 | 실패: {failed_files}개[/bold]\n"
        f"[bold]총 추출 문서: {total_documents}개[/bold]\n"
        f"[bold]총 처리시간: {total_time:.2f}초[/bold]\n"
        f"[bold]평균 처리시간: {avg_time:.2f}초/파일[/bold]\n"
        f"[bold]완료 시간:[/bold] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        title="처리 완료",
        border_style=rate_color
    ))
    
    # 저장된 파일 목록
    if saved_files:
        console.print()
        console.print("[bold cyan]결과 파일 저장 위치:[/bold cyan]")
        for file_path in saved_files:
            console.print(f"  - {file_path}")


if __name__ == "__main__":
    main()