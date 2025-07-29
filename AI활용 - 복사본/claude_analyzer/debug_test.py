#!/usr/bin/env python3
"""
디버깅용 테스트 파일
"""

import os
import sys
import json

# 현재 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from claude_ai_analyzer import ClaudeAIAnalyzer

def test_analyzer_output():
    """분석기 출력 구조 테스트"""
    
    # 환경변수에서 API 키 가져오기
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("경고: ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
        return None
    
    # 분석기 초기화
    analyzer = ClaudeAIAnalyzer(api_key=api_key)
    
    # 테스트용 더미 데이터
    test_results = {
        "Invoice": [
            {
                "page_number": 1,
                "analysis": "업체명: 테스트 회사\n일자: 2024-01-01\n금액: 100,000원"
            }
        ],
        "Tax Invoice": [
            {
                "page_number": 2,
                "analysis": "업체명: 세금계산서 회사\n일자: 2024-01-02\n공급가액: 90,000원"
            }
        ]
    }
    
    # 결과 결합 테스트
    combined_result = analyzer._combine_document_type_results(
        test_results, 
        analysis_time=10.5, 
        total_pages=2
    )
    
    print("=== 결합된 결과 ===")
    print(combined_result)
    print("\n=== 결과 타입 ===")
    print(f"타입: {type(combined_result)}")
    print(f"길이: {len(combined_result)}")
    
    # 전체 분석 결과 구조 테스트
    full_result = {
        "success": True,
        "document_types": ["Invoice", "Tax Invoice"],
        "analysis": combined_result,
        "detailed_results": test_results,
        "analysis_time": 10.5,
        "total_pages": 2
    }
    
    print("\n=== 전체 결과 구조 ===")
    print(json.dumps(full_result, ensure_ascii=False, indent=2))
    
    return full_result

if __name__ == "__main__":
    test_analyzer_output() 