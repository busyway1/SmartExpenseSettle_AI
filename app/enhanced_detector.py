"""
향상된 문서 감지기 - PyMuPDF 스타일의 간단하고 효과적인 로직

각 페이지별로 독립적으로 문서 타입을 감지하고,
여러 문서 타입이 동시에 존재할 수 있도록 합니다.
"""

import re
import logging
from typing import List, Dict, Any, Tuple
from .models import DocumentType

logger = logging.getLogger(__name__)


class EnhancedDocumentDetector:
    """간단하고 효과적인 문서 감지기"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
        # 집계 대상에서 제외할 문서 패턴 (Commercial Invoice, Packing List 등)
        self.excluded_patterns = [
            r'commercial\s*invoice',
            r'packing\s*list',
            r'packing\s*slip',
            r'delivery\s*note',
            r'shipping\s*note'
        ]
        
        # 각 문서 타입별 고유한 식별자 패턴
        self.signature_patterns = {
            DocumentType.INVOICE: {
                'patterns': [
                    r'invoice\s*(?:no\.?|number)',
                    r'freight\s*(?:charge|cost)',
                    r'운임|화물운송료',
                    r'인보이스',
                    r'REMIT\s*TO',
                    r'CLIENT\s*NO',
                    r'CHARGEABLE\s*WGT',
                    r'expeditors',
                    r'TERMINAL\s*HANDLING',
                    r'FORWARDING\s*FEE',
                    r'DOCUMENT\s*FEE',
                    r'PROCESSING\s*FEE',
                    r'VAT\s*CATEGORY'
                ],
                'exclusions': ['세금계산서', 'tax invoice'],
                'min_score': 1
            },
            DocumentType.TAX_INVOICE: {
                'patterns': [
                    r'세금계산서',
                    r'영세율전자세금계산서',
                    r'공급가액',
                    r'공급받는자',
                    r'사업자등록번호\s*\d{3}-\d{2}-\d{5}',
                    r'매출세금계산서',
                    r'부가가치세',
                    r'세액',
                    r'합계금액',
                    r'발급일자',
                    r'공급자상호',
                    r'승인번호.*\d+',
                    r'eTradeInvoice'
                ],
                'exclusions': [],
                'min_score': 1
            },
            DocumentType.BILL_OF_LADING: {
                'patterns': [
                    r'bill\s*of\s*lading',
                    r'b/l\s*(?:no\.?|number)',
                    r'port\s*of\s*loading',
                    r'port\s*of\s*discharge',
                    r'선하증권',
                    r'vessel\s*name'
                ],
                'exclusions': [],
                'min_score': 1
            },
            DocumentType.EXPORT_DECLARATION: {
                'patterns': [
                    r'수출신고필증',
                    r'수출신고서',
                    r'신고번호\s*\d+',
                    r'관세청',
                    r'export\s*declaration',
                    r'통관'
                ],
                'exclusions': [],
                'min_score': 1
            },
            DocumentType.REMITTANCE_ADVICE: {
                'patterns': [
                    r'이체확인증',
                    r'송금확인',
                    r'송금증',
                    r'입금확인',
                    r'확인증',
                    r'출금|입금',
                    r'송금일자',
                    r'계좌번호',
                    r'출금계좌번호',
                    r'입금계좌번호',
                    r'transfer\s*confirmation',
                    r'승인번호\s*\d+',
                    r'한국외환은행',
                    r'우리은행',
                    r'농협|농업협동조합'
                ],
                'exclusions': [],
                'min_score': 1
            }
        }
    
    def detect_documents_in_pages(self, text: str) -> List[Tuple[DocumentType, float, Tuple[int, int]]]:
        """
        하이브리드 문서 감지 - 개별 감지 + 지능적 병합
        
        Args:
            text: 전체 텍스트 (페이지 구분자 포함)
            
        Returns:
            List[(문서_타입, 신뢰도, 페이지_범위)]
        """
        
        # 페이지별로 분리
        pages = self._split_into_pages(text)
        
        if self.verbose:
            logger.info(f"📄 총 {len(pages)}개 페이지 분석 시작")
        
        # 1단계: 각 페이지별 개별 문서 감지 (기존 방식 유지)
        individual_docs = []
        for page_num, page_text in enumerate(pages, 1):
            page_docs = self._detect_individual_documents(page_text, page_num)
            individual_docs.extend(page_docs)
        
        # 2단계: 지능적 병합 (보수적 접근) - 임시로 비활성화
        # merged_docs = self._smart_merge_documents(individual_docs)
        merged_docs = individual_docs  # 병합하지 않고 개별 문서 그대로 사용
        
        if self.verbose:
            logger.info(f"📊 개별 감지: {len(individual_docs)}개")
            for i, (doc_type, conf, page_range) in enumerate(individual_docs):
                logger.info(f"  개별 {i+1}. {doc_type.value} (페이지 {page_range[0]}-{page_range[1]}, 신뢰도: {conf:.2f})")
            
            logger.info(f"🎯 최종 병합: {len(merged_docs)}개 문서")
            for i, (doc_type, conf, page_range) in enumerate(merged_docs):
                logger.info(f"  최종 {i+1}. {doc_type.value} (페이지 {page_range[0]}-{page_range[1]}, 신뢰도: {conf:.2f})")
                
            # 필터링된 문서 통계
            filtered_count = len(individual_docs) - len(merged_docs)
            if filtered_count > 0:
                logger.info(f"🚫 필터링된 문서: {filtered_count}개 (Commercial Invoice, Packing List 등)")
        
        return merged_docs
    
    def _calculate_page_scores(self, page_text: str, page_num: int) -> Dict[DocumentType, Dict[str, Any]]:
        """페이지별 모든 문서 타입 점수 계산 (감지 여부와 무관하게)"""
        
        page_text_lower = page_text.lower()
        scores = {}
        
        if self.verbose:
            logger.info(f"📄 페이지 {page_num} 분석 중...")
        
        # 각 문서 타입별로 점수 계산
        for doc_type, config in self.signature_patterns.items():
            score = 0
            found_patterns = []
            excluded = False
            
            # 패턴 매칭
            for pattern in config['patterns']:
                matches = re.findall(pattern, page_text_lower, re.IGNORECASE | re.MULTILINE)
                if matches:
                    score += len(matches)
                    found_patterns.append(pattern)
            
            # 제외 패턴 확인
            for exclusion in config['exclusions']:
                if exclusion.lower() in page_text_lower:
                    excluded = True
                    if self.verbose:
                        logger.info(f"  ❌ {doc_type.value}: '{exclusion}' 제외 패턴 발견")
                    break
            
            # 제외된 경우 점수를 0으로 설정
            if excluded:
                score = 0
            
            scores[doc_type] = {
                'score': score,
                'found_patterns': found_patterns,
                'excluded': excluded,
                'meets_threshold': score >= config['min_score'] and not excluded
            }
            
            if self.verbose and score > 0:
                logger.info(f"  📊 {doc_type.value}: {score}점 {'✅' if scores[doc_type]['meets_threshold'] else '⚠️'}")
        
        return scores
    
    def _detect_document_boundaries(self, page_scores: List[Tuple[int, str, Dict[DocumentType, Dict[str, Any]]]]) -> List[Tuple[DocumentType, float, Tuple[int, int]]]:
        """문서 경계 감지 및 완전한 페이지 범위 추출"""
        
        detected_docs = []
        
        # 각 문서 타입별로 처리
        for doc_type in DocumentType:
            if doc_type == DocumentType.UNKNOWN:
                continue
                
            # 해당 문서 타입의 강력한 신호가 있는 페이지들 찾기
            strong_pages = []
            weak_pages = []
            
            for page_num, page_text, scores in page_scores:
                score_info = scores.get(doc_type, {})
                score = score_info.get('score', 0)
                meets_threshold = score_info.get('meets_threshold', False)
                
                if meets_threshold:
                    strong_pages.append(page_num)
                elif score > 0:  # 약한 신호지만 관련 패턴 존재
                    weak_pages.append(page_num)
            
            # 강력한 신호가 있는 페이지들을 기준으로 문서 범위 확장
            if strong_pages:
                doc_ranges = self._expand_document_ranges(strong_pages, weak_pages, len(page_scores))
                
                for start_page, end_page in doc_ranges:
                    # 해당 범위의 평균 신뢰도 계산
                    total_score = 0
                    valid_pages = 0
                    
                    for page_num in range(start_page, end_page + 1):
                        if page_num <= len(page_scores):
                            page_score = page_scores[page_num - 1][2].get(doc_type, {}).get('score', 0)
                            total_score += page_score
                            valid_pages += 1
                    
                    if valid_pages > 0:
                        avg_score = total_score / valid_pages
                        confidence = min(0.9, avg_score / 5)  # 5점 만점으로 정규화
                        
                        detected_docs.append((doc_type, confidence, (start_page, end_page)))
                        
                        if self.verbose:
                            logger.info(f"✅ {doc_type.value} 감지: 페이지 {start_page}-{end_page} (평균점수: {avg_score:.1f}, 신뢰도: {confidence:.2f})")
        
        # 신뢰도 순으로 정렬
        detected_docs.sort(key=lambda x: x[1], reverse=True)
        
        return detected_docs
    
    def _expand_document_ranges(self, strong_pages: List[int], weak_pages: List[int], total_pages: int) -> List[Tuple[int, int]]:
        """강력한 신호 페이지를 기준으로 문서 범위 확장 (보수적 접근)"""
        
        if not strong_pages:
            return []
        
        strong_pages.sort()
        weak_pages.sort()
        
        ranges = []
        
        # 보수적 그룹화: 연속된 페이지만 그룹화 (간격 허용 축소)
        groups = []
        current_group = [strong_pages[0]]
        
        for i in range(1, len(strong_pages)):
            if strong_pages[i] <= current_group[-1] + 1:  # 1페이지 이내 간격만 허용 (기존 2 → 1)
                current_group.append(strong_pages[i])
            else:
                groups.append(current_group)
                current_group = [strong_pages[i]]
        groups.append(current_group)
        
        # 각 그룹별로 최소한의 범위 확장
        for group in groups:
            start_page = group[0]
            end_page = group[-1]
            
            # 보수적 확장: 최대 1페이지까지만 (기존 3 → 1)
            # 앞쪽으로 확장 (약한 신호 페이지 포함)
            for weak_page in reversed(weak_pages):
                if weak_page < start_page and weak_page >= start_page - 1:  # 최대 1페이지 앞까지
                    start_page = weak_page
                    break
            
            # 뒤쪽으로 확장 (약한 신호 페이지 포함)
            for weak_page in weak_pages:
                if weak_page > end_page and weak_page <= end_page + 1:  # 최대 1페이지 뒤까지
                    end_page = weak_page
                    break  # 첫 번째만 포함하고 중단
            
            ranges.append((start_page, end_page))
        
        return ranges
    
    def _detect_individual_documents(self, page_text: str, page_num: int) -> List[Tuple[DocumentType, float, Tuple[int, int]]]:
        """개별 페이지에서 문서 감지 (기존 방식 유지)"""
        
        page_text_lower = page_text.lower()
        detected = []
        
        if self.verbose:
            logger.info(f"📄 페이지 {page_num} 개별 분석 중...")
        
        # 각 문서 타입별로 검사
        for doc_type, config in self.signature_patterns.items():
            score = 0
            found_patterns = []
            
            # 패턴 매칭
            for pattern in config['patterns']:
                matches = re.findall(pattern, page_text_lower, re.IGNORECASE | re.MULTILINE)
                if matches:
                    score += len(matches)
                    found_patterns.append(pattern)
            
            # 제외 패턴 확인 (문서 타입별)
            excluded = False
            for exclusion in config['exclusions']:
                if exclusion.lower() in page_text_lower:
                    excluded = True
                    if self.verbose:
                        logger.info(f"  ❌ {doc_type.value}: '{exclusion}' 제외 패턴 발견")
                    break
            
            # 전역 제외 패턴 확인 (Commercial Invoice, Packing List 등) - 임시로 비활성화
            # if not excluded:
            #     for excluded_pattern in self.excluded_patterns:
            #         if re.search(excluded_pattern, page_text_lower, re.IGNORECASE):
            #             excluded = True
            #             if self.verbose:
            #                 logger.info(f"  ❌ {doc_type.value}: '{excluded_pattern}' 전역 제외 패턴 발견")
            #             break
            
            # 점수가 임계값 이상이고 제외되지 않았으면 감지
            if score >= config['min_score'] and not excluded:
                confidence = min(0.9, score / 5)  # 5점 만점으로 정규화
                detected.append((doc_type, confidence, (page_num, page_num)))
                
                if self.verbose:
                    logger.info(f"  ✅ {doc_type.value}: {score}점 (신뢰도: {confidence:.2f})")
                    logger.info(f"     발견된 패턴: {found_patterns}")
        
        return detected
    
    def _smart_merge_documents(self, individual_docs: List[Tuple[DocumentType, float, Tuple[int, int]]]) -> List[Tuple[DocumentType, float, Tuple[int, int]]]:
        """지능적 문서 병합 (엄격한 조건)"""
        
        if not individual_docs:
            return []
        
        # 페이지 순으로 정렬
        individual_docs.sort(key=lambda x: x[2][0])
        
        # 병합하지 않을 문서 타입 (일반적으로 단일 페이지)
        no_merge_types = {
            DocumentType.TAX_INVOICE,      # 세금계산서는 일반적으로 한 장
            DocumentType.REMITTANCE_ADVICE # 송금증도 일반적으로 한 장
        }
        
        merged = []
        i = 0
        
        while i < len(individual_docs):
            current_type, current_conf, (start, end) = individual_docs[i]
            
            # 병합하지 않을 문서 타입은 개별 처리
            if current_type in no_merge_types:
                merged.append((current_type, current_conf, (start, end)))
                i += 1
                continue
            
            # 연속된 페이지 확인 및 문서 식별자 유사성 검사
            j = i + 1
            while j < len(individual_docs):
                next_type, next_conf, (next_start, next_end) = individual_docs[j]
                
                # 1. 동일한 문서 타입이고 바로 다음 페이지인 경우만 병합 후보
                if (next_type == current_type and 
                    next_start == end + 1):  # 바로 다음 페이지
                    
                    # 2. 문서 식별자 유사성 검사 (페이지 내용 기반)
                    if self._should_merge_documents(current_type, start, next_start):
                        end = next_end
                        current_conf = max(current_conf, next_conf)  # 높은 신뢰도 유지
                        j += 1
                    else:
                        # 식별자가 다르면 병합하지 않음
                        break
                else:
                    break
            
            merged.append((current_type, current_conf, (start, end)))
            i = j
        
        return merged
    
    def _should_merge_documents(self, doc_type: DocumentType, page1: int, page2: int) -> bool:
        """문서 식별자 유사성을 기반으로 병합 여부 결정"""
        
        # 현재는 간단한 로직으로 구현
        # 실제로는 페이지 내용에서 B/L NO, Invoice NO 등을 추출하여 비교해야 함
        # 여기서는 보수적으로 접근: 기본적으로 병합하지 않음
        
        # 특정 문서 타입만 병합 허용 (매우 보수적)
        mergeable_types = {
            DocumentType.BILL_OF_LADING,     # B/L은 여러 페이지일 수 있음
            DocumentType.EXPORT_DECLARATION  # 수출신고필증도 여러 페이지일 수 있음
        }
        
        if doc_type not in mergeable_types:
            return False
        
        # TODO: 실제 구현에서는 페이지 내용에서 문서 번호를 추출하여 비교
        # 지금은 매우 보수적으로 병합하지 않음
        return False
    
    def _split_into_pages(self, text: str) -> List[str]:
        """텍스트를 페이지별로 분리 (PyMuPDF 스타일)"""
        
        # 페이지 구분자로 분리
        page_separators = [
            r'--- 페이지 \d+ ---',
            r'page \d+',
            r'\n\s*\d+\s*\n',  # 페이지 번호만 있는 줄
        ]
        
        pages = [text]  # 기본값: 전체를 하나의 페이지로
        
        for separator in page_separators:
            new_pages = []
            for page in pages:
                parts = re.split(separator, page, flags=re.IGNORECASE)
                new_pages.extend([part.strip() for part in parts if part.strip()])
            
            if len(new_pages) > len(pages):
                pages = new_pages
                break
        
        # 빈 페이지 제거
        pages = [page for page in pages if len(page.strip()) > 50]
        
        return pages
    
    def _merge_consecutive_documents(self, detected_docs: List[Tuple[DocumentType, float, Tuple[int, int]]]) -> List[Tuple[DocumentType, float, Tuple[int, int]]]:
        """연속된 같은 문서 타입 병합"""
        
        if not detected_docs:
            return []
        
        # 페이지 순으로 정렬
        detected_docs.sort(key=lambda x: x[2][0])
        
        merged = []
        
        i = 0
        while i < len(detected_docs):
            current_type, current_conf, (start, end) = detected_docs[i]
            
            # 연속된 같은 문서 타입 찾기
            j = i + 1
            while j < len(detected_docs):
                next_type, next_conf, (next_start, next_end) = detected_docs[j]
                
                if (next_type == current_type and 
                    next_start <= end + 1):  # 연속된 페이지
                    end = max(end, next_end)
                    current_conf = max(current_conf, next_conf)  # 높은 신뢰도 유지
                    j += 1
                else:
                    break
            
            merged.append((current_type, current_conf, (start, end)))
            i = j
        
        return merged
    
    def get_debug_info(self, text: str) -> Dict[str, Any]:
        """디버깅 정보 반환"""
        
        pages = self._split_into_pages(text)
        debug_info = {
            "total_pages": len(pages),
            "page_lengths": [len(page) for page in pages],
            "detected_patterns": {}
        }
        
        # 각 페이지별 패턴 매칭 정보
        for page_num, page_text in enumerate(pages, 1):
            page_text_lower = page_text.lower()
            page_patterns = {}
            
            for doc_type, config in self.signature_patterns.items():
                found = []
                for pattern in config['patterns']:
                    matches = re.findall(pattern, page_text_lower, re.IGNORECASE)
                    if matches:
                        found.append(f"{pattern}: {len(matches)}개")
                
                if found:
                    page_patterns[doc_type.value] = found
            
            if page_patterns:
                debug_info["detected_patterns"][f"page_{page_num}"] = page_patterns
        
        return debug_info