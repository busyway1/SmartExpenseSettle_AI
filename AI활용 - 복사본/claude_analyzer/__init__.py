"""
Claude AI 기반 문서 분석기 패키지

이 패키지는 Anthropic의 Claude-3-5-sonnet 모델을 사용하여
다양한 문서를 분석하는 AI 시스템을 제공합니다.
"""

from .claude_ai_analyzer import ClaudeAIAnalyzer

__version__ = "1.0.0"
__author__ = "SmartExpenseSettle AI Team"

__all__ = ["ClaudeAIAnalyzer"] 