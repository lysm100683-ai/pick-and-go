"""
주간업무보고서 마크다운 → HTML 변환 후 로컬 서버 실행
Mermaid.js 포함 (xychart-beta, flowchart 지원)
"""
import http.server
import socketserver
import markdown
import re
import os

PORT = 5500
MD_FILE = os.path.join(os.path.dirname(__file__), "weekly_report_2026_05_W5.md")

# ── 마크다운 읽기 ─────────────────────────────────────────────────────
with open(MD_FILE, encoding="utf-8") as f:
    md_text = f.read()

# ── carousel 블록 제거 (일반 코드블록으로 처리되도록) ─────────────────
md_text = re.sub(r"````carousel", "````", md_text)

# ── mermaid 펜스 임시 치환 (markdown 라이브러리가 건드리지 않도록) ────
PLACEHOLDER = "MERMAID_BLOCK_{i}"
mermaid_blocks = []

def extract_mermaid(m):
    mermaid_blocks.append(m.group(1))
    return f"MERMAID_PLACEHOLDER_{len(mermaid_blocks)-1}_END"

md_text_replaced = re.sub(
    r"```mermaid\n(.*?)```",
    extract_mermaid,
    md_text,
    flags=re.DOTALL,
)

# ── 마크다운 → HTML 변환 ──────────────────────────────────────────────
extensions = [
    "tables",
    "fenced_code",
    "md_in_html",
    "attr_list",
    "pymdownx.superfences",
]
try:
    body_html = markdown.markdown(
        md_text_replaced,
        extensions=extensions,
        extension_configs={
            "pymdownx.superfences": {
                "custom_fences": []
            }
        },
    )
except Exception:
    body_html = markdown.markdown(
        md_text_replaced,
        extensions=["tables", "fenced_code"],
    )

# ── mermaid 플레이스홀더 복원 ─────────────────────────────────────────
for i, block in enumerate(mermaid_blocks):
    body_html = body_html.replace(
        f"MERMAID_PLACEHOLDER_{i}_END",
        f'<div class="mermaid">{block}</div>',
    )

# ── 전체 HTML 조립 ────────────────────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>주간업무보고서 2026-05-W5</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>
  body {{
    font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
    max-width: 1000px;
    margin: 40px auto;
    padding: 0 24px 80px;
    line-height: 1.7;
    color: #1a1a2e;
    background: #f9f9fb;
  }}
  h1 {{ font-size: 1.8rem; border-bottom: 3px solid #2563eb; padding-bottom: 8px; }}
  h2 {{ font-size: 1.4rem; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px; margin-top: 2rem; }}
  h3 {{ font-size: 1.15rem; margin-top: 1.6rem; color: #1d4ed8; }}
  h4 {{ font-size: 1rem; margin-top: 1.2rem; color: #374151; }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 1rem 0;
    font-size: 0.93rem;
    background: #fff;
    border-radius: 6px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,.07);
  }}
  th {{
    background: #1e40af;
    color: #fff;
    padding: 10px 12px;
    text-align: left;
  }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #e2e8f0; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:nth-child(even) td {{ background: #f0f6ff; }}
  code {{
    background: #f1f5f9;
    padding: 2px 5px;
    border-radius: 3px;
    font-family: 'Consolas', monospace;
    font-size: 0.88em;
  }}
  pre {{
    background: #1e293b;
    color: #e2e8f0;
    padding: 16px;
    border-radius: 8px;
    overflow-x: auto;
    font-size: 0.88rem;
  }}
  pre code {{ background: none; color: inherit; padding: 0; }}
  blockquote {{
    border-left: 4px solid #2563eb;
    background: #eff6ff;
    margin: 1rem 0;
    padding: 10px 16px;
    border-radius: 0 6px 6px 0;
    color: #1e3a8a;
  }}
  hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 2rem 0; }}
  .mermaid {{
    background: #fff;
    padding: 16px;
    border-radius: 8px;
    margin: 1rem 0;
    box-shadow: 0 1px 4px rgba(0,0,0,.07);
    text-align: center;
  }}
</style>
</head>
<body>
{body_html}
<script>
  mermaid.initialize({{
    startOnLoad: true,
    theme: 'default',
    xychart: {{ width: 700, height: 350 }},
  }});
</script>
</body>
</html>"""

# ── HTTP 서버 ─────────────────────────────────────────────────────────
_STATIC_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "svg": "image/svg+xml",
    "gif": "image/gif",
}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # 이미지 등 정적 파일 요청 처리
        ext = self.path.rsplit(".", 1)[-1].lower() if "." in self.path else ""
        if ext in _STATIC_TYPES:
            file_path = os.path.join(os.path.dirname(__file__), self.path.lstrip("/"))
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", _STATIC_TYPES[ext])
                self.end_headers()
                self.wfile.write(data)
                return
        # 기본: 보고서 HTML 반환
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # 로그 출력 억제

print(f"[preview] http://localhost:{PORT} 에서 보고서를 확인하세요.")
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.serve_forever()
