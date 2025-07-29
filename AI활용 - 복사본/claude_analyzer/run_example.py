#!/usr/bin/env python3
"""
Claude AI 분석기 실행 예제

이 스크립트는 claude_analyzer 폴더에서 직접 실행할 수 있습니다.
"""

import asyncio
import os
import sys

# 현재 폴더의 상위 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from claude_ai_analyzer import ClaudeAIAnalyzer

async def main():
    """메인 실행 함수"""
    print("=== Claude AI 문서 분석기 예제 ===")
    
    # API 키 확인
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("경고: ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
        print("환경변수를 설정하거나 아래 코드에서 직접 API 키를 입력하세요.")
        api_key = "your-api-key-here"  # 실제 API 키로 변경하세요
    
    # 분석기 초기화
    analyzer = ClaudeAIAnalyzer(api_key=api_key, use_advanced_opencv=True)
    
    # 테스트할 파일 경로 (실제 파일로 변경하세요)
    test_files = [
        "../uploads/example.pdf",  # 상대 경로
        # "C:/path/to/your/document.pdf",  # 절대 경로 예시
    ]
    
    for file_path in test_files:
        if os.path.exists(file_path):
            print(f"\n📄 파일 분석 중: {file_path}")
            
            try:
                # 비동기 분석 실행
                result = await analyzer.analyze_document_async(file_path)
                
                if result.get("success"):
                    print("✅ 분석 완료!")
                    print(f"📋 발견된 문서 타입: {result['document_types']}")
                    print("\n📊 분석 결과:")
                    print("-" * 50)
                    print(result['analysis'])
                    print("-" * 50)
                else:
                    print(f"❌ 분석 실패: {result.get('error', '알 수 없는 오류')}")
                    
            except Exception as e:
                print(f"❌ 오류 발생: {str(e)}")
        else:
            print(f"⚠️  파일을 찾을 수 없습니다: {file_path}")
            print("   실제 파일 경로로 변경하거나 파일을 업로드하세요.")
    
    # 리소스 정리
    await analyzer.__aexit__(None, None, None)
    print("\n🏁 분석 완료!")

def sync_example():
    """동기 방식 예제"""
    print("\n=== 동기 방식 예제 ===")
    
    api_key = os.getenv('ANTHROPIC_API_KEY', 'your-api-key-here')
    analyzer = ClaudeAIAnalyzer(api_key=api_key)
    
    # 간단한 텍스트 분석 예제
    test_text = """
    이 문서는 테스트용 세금계산서입니다.
    공급가액: 1,000,000원
    부가세: 100,000원
    합계: 1,100,000원
    """
    
    print("📝 텍스트 분석 예제:")
    print(test_text)
    
    # 여기서는 실제 파일 분석 대신 텍스트 분석을 시연
    print("📊 분석 결과: 세금계산서로 분류됨")
    print("   - 공급가액: 1,000,000원")
    print("   - 부가세: 100,000원")
    print("   - 합계: 1,100,000원")

if __name__ == "__main__":
    print("🚀 Claude AI 분석기 시작...")
    
    # 비동기 예제 실행
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 실행 중 오류 발생: {str(e)}")
    
    # 동기 예제 실행
    try:
        sync_example()
    except Exception as e:
        print(f"❌ 동기 예제 오류: {str(e)}")
    
    print("\n📚 사용법:")
    print("1. ANTHROPIC_API_KEY 환경변수 설정")
    print("2. 실제 파일 경로로 test_files 리스트 수정")
    print("3. python run_example.py 실행") 