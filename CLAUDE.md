# Claude Code MCP 설정

이 프로젝트에서 사용할 MCP (Model Context Protocol) 서버들을 정의합니다.

## MCP 서버 설정

<mcp_config>
```json
{
  "mcpServers": {
    "exa": {
      "command": "cmd",
      "args": [
        "/c",
        "npx",
        "-y",
        "@smithery/cli@latest",
        "run",
        "exa",
        "--key",
        "28e89a0f-efe4-449f-9633-f9ad5339dc90"
      ]
    },
    "desktop-commander": {
      "command": "cmd",
      "args": [
        "/c",
        "npx",
        "-y",
        "@smithery/cli@latest",
        "run",
        "@wonderwhy-er/desktop-commander",
        "--key",
        "28e89a0f-efe4-449f-9633-f9ad5339dc90"
      ]
    },
    "puppeteer": {
      "command": "cmd",
      "args": [
        "/c",
        "npx",
        "-y",
        "@smithery/cli@latest",
        "run",
        "@smithery-ai/puppeteer",
        "--key",
        "28e89a0f-efe4-449f-9633-f9ad5339dc90"
      ]
    },
    "context7-mcp": {
      "command": "cmd",
      "args": [
        "/c",
        "npx",
        "-y",
        "@smithery/cli@latest",
        "run",
        "@upstash/context7-mcp",
        "--key",
        "28e89a0f-efe4-449f-9633-f9ad5339dc90"
      ]
    },
    "mcp-taskmanager": {
      "command": "cmd",
      "args": [
        "/c",
        "npx",
        "-y",
        "@smithery/cli@latest",
        "run",
        "@kazuph/mcp-taskmanager",
        "--key",
        "28e89a0f-efe4-449f-9633-f9ad5339dc90"
      ]
    },
    "sequential-thinking": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-sequential-thinking"
      ]
    },
    "notion": {
      "command": "cmd",
      "args": [
        "/c",
        "npx",
        "-y",
        "@smithery/cli@latest",
        "run",
        "@smithery/notion",
        "--key",
        "28e89a0f-efe4-449f-9633-f9ad5339dc90",
        "--profile",
        "sparkling-lemur-rrO1Ik"
      ]
    },
    "supabase-mcp": {
      "command": "cmd",
      "args": [
        "/c",
        "npx",
        "-y",
        "@supabase/mcp-server-supabase@latest",
        "--read-only",
        "--project-ref=lnfdpxtdtmbcefhshmdm"
      ],
      "env": {
        "SUPABASE_ACCESS_TOKEN": "sbp_5ee0af57074c9bb9883b31b238c03dd0df809ab2"
      }
    }
  }
}
```
</mcp_config>c",
      "npx",
      "-y",
      "@smithery/cli@latest",
      "run",
      "exa",
      "--key",
      "28e89a0f-efe4-449f-9633-f9ad5339dc90"
    ]
  },
  "desktop-commander": {
    "command": "cmd",
    "args": [
      "/c",
      "npx",
      "-y",
      "@smithery/cli@latest",
      "run",
      "@wonderwhy-er/desktop-commander",
      "--key",
      "28e89a0f-efe4-449f-9633-f9ad5339dc90"
    ]
  },
  "puppeteer": {
    "command": "cmd",
    "args": [
      "/c",
      "npx",
      "-y",
      "@smithery/cli@latest",
      "run",
      "@smithery-ai/puppeteer",
      "--key",
      "28e89a0f-efe4-449f-9633-f9ad5339dc90"
    ]
  },
  "context7-mcp": {
    "command": "cmd",
    "args": [
      "/c",
      "npx",
      "-y",
      "@smithery/cli@latest",
      "run",
      "@upstash/context7-mcp",
      "--key",
      "28e89a0f-efe4-449f-9633-f9ad5339dc90"
    ]
  },
  "mcp-taskmanager": {
    "command": "cmd",
    "args": [
      "/c",
      "npx",
      "-y",
      "@smithery/cli@latest",
      "run",
      "@kazuph/mcp-taskmanager",
      "--key",
      "28e89a0f-efe4-449f-9633-f9ad5339dc90"
    ]
  },
  "sequential-thinking": {
    "command": "npx",
    "args": [
      "-y",
      "@modelcontextprotocol/server-sequential-thinking"
    ]
  },
  "notion": {
    "command": "cmd",
    "args": [
      "/c",
      "npx",
      "-y",
      "@smithery/cli@latest",
      "run",
      "@smithery/notion",
      "--key",
      "28e89a0f-efe4-449f-9633-f9ad5339dc90",
      "--profile",
      "sparkling-lemur-rrO1Ik"
    ]
  },
  "supabase-mcp": {
    "command": "cmd",
    "args": [
      "/c",
      "npx",
      "-y",
      "@supabase/mcp-server-supabase@latest",
      "--read-only",
      "--project-ref=sparkling-lemur-rrO1Ik"
    ],
    "env": {
      "SUPABASE_ACCESS_TOKEN": "28e89a0f-efe4-449f-9633-f9ad5339dc90"
    }
  }
}
```
</mcp_servers>

## MCP 서버 설명

- **exa**: 웹 검색 및 데이터 수집
- **desktop-commander**: 데스크톱 파일 시스템 작업
- **puppeteer**: 웹 브라우저 자동화
- **context7-mcp**: 컨텍스트 관리 및 문서 검색
- **mcp-taskmanager**: 작업 관리 및 프로젝트 추적
- **sequential-thinking**: 단계별 사고 과정 지원
- **notion**: Notion 워크스페이스 연동
- **supabase-mcp**: Supabase 데이터베이스 연동

## 사용법

Claude Code가 자동으로 이 설정을 읽어 MCP 서버들을 초기화합니다.
각 서버는 해당하는 기능을 수행할 때 자동으로 활성화됩니다.
