import asyncio
import os
import sys
sys.path.append('..')  # 상위 디렉토리 추가
from claude_ai_analyzer import ClaudeAIAnalyzer

async def main():
    """Claude AI 분석기 사용 예제"""
    
    # API 키 설정 (환경변수 또는 직접 입력)
    api_key = "your-anthropic-api-key-here"  # 실제 API 키로 변경하세요
    
    # Claude AI 분석기 초기화
    analyzer = ClaudeAIAnalyzer(api_key=api_key, use_advanced_opencv=True)
    
    # 분석할 파일 경로
    file_path = "uploads/example.pdf"  # 실제 파일 경로로 변경하세요
    
    try:
        print("문서 분석을 시작합니다...")
        
        # 비동기 분석
        result = await analyzer.analyze_document_async(file_path)
        
        if result.get("success"):
            print("=== 분석 완료 ===")
            print(f"발견된 문서 타입: {result['document_types']}")
            print("\n=== 상세 분석 결과 ===")
            print(result['analysis'])
            
            # 개별 문서 타입별 결과 출력
            if result.get('detailed_results'):
                print("\n=== 문서 타입별 상세 결과 ===")
                for doc_type, docs in result['detailed_results'].items():
                    print(f"\n{doc_type}:")
                    for i, doc in enumerate(docs):
                        print(f"  문서 {i+1}: {doc.get('analysis', '분석 결과 없음')[:200]}...")
        else:
            print(f"분석 실패: {result.get('error', '알 수 없는 오류')}")
    
    except Exception as e:
        print(f"오류 발생: {str(e)}")
    
    finally:
        # 리소스 정리
        await analyzer.__aexit__(None, None, None)

def sync_example():
    """동기 방식 사용 예제"""
    
    api_key = "your-anthropic-api-key-here"  # 실제 API 키로 변경하세요
    analyzer = ClaudeAIAnalyzer(api_key=api_key)
    
    file_path = "uploads/example.pdf"  # 실제 파일 경로로 변경하세요
    
    try:
        print("동기 방식으로 문서 분석을 시작합니다...")
        
        # 동기 분석
        result = analyzer.analyze_document(file_path)
        
        if result.get("success"):
            print("=== 분석 완료 ===")
            print(result['analysis'])
        else:
            print(f"분석 실패: {result.get('error', '알 수 없는 오류')}")
    
    except Exception as e:
        print(f"오류 발생: {str(e)}")

if __name__ == "__main__":
    # 비동기 예제 실행
    print("=== 비동기 방식 예제 ===")
    asyncio.run(main())
    
    print("\n" + "="*50 + "\n")
    
    # 동기 예제 실행
    print("=== 동기 방식 예제 ===")
    sync_example() 