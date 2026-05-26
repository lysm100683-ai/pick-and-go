import os, sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

tsx_files = [
    'frontend/src/app/page.tsx',
    'frontend/src/app/result/page.tsx',
    'frontend/src/app/layout.tsx',
    'frontend/src/app/globals.css',
]

for f in tsx_files:
    try:
        size = os.path.getsize(f)
        with open(f, encoding='utf-8') as fh:
            content = fh.read()
        lines = content.count('\n')
        print(f'[OK] {f}')
        print(f'     size: {size:,} bytes / {lines} lines')

        if 'app/page.tsx' in f and 'result' not in f:
            items = {
                'export default function Home': 'export default function Home' in content,
                'handleSubmit func': 'handleSubmit' in content,
                'insufficientError modal': 'insufficientError' in content,
                '/api/v1/generate call': '/api/v1/generate' in content,
                'router.push /result': 'router.push' in content,
                'formData state': 'formData' in content,
                'generate-relaxed API': 'generate-relaxed' in content,
                'generate-fetch API': 'generate-fetch' in content,
            }
            for k, v in items.items():
                print(f'     {"OK" if v else "MISS"} {k}')

        elif 'result/page.tsx' in f:
            items = {
                'export default ResultPage': 'export default function ResultPage' in content,
                'localStorage read': 'localStorage.getItem' in content,
                'activeTab state': 'activeTab' in content,
                'handleRegenerate': 'handleRegenerate' in content,
                'handleUpdateDB': 'handleUpdateDB' in content,
            }
            for k, v in items.items():
                print(f'     {"OK" if v else "MISS"} {k}')

    except FileNotFoundError:
        print(f'[NOT FOUND] {f}')

print()
print('Frontend check done.')
