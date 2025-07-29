import anthropic
import os

# 환경변수에서 API 키 가져오기
api_key = os.getenv('ANTHROPIC_API_KEY')
if not api_key:
    print("경고: ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
    exit(1)

client = anthropic.Anthropic(api_key=api_key)

message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    system="You are a helpful assistant.",
    messages=[
        {"role": "user", "content": "Hello, world"}
    ]
)

print(message.content)