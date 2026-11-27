"""인터넷에 올릴 공개용 홈페이지를 _site 폴더에 만듭니다.

index.html 은 claude.ai 미리보기용이라 문서 맨 앞부분(<!doctype>, <head>, 한글 인코딩)이 빠져 있어요.
이 스크립트가 그 부분을 붙여서 _site 에 완성된 웹페이지를 만들고, 데이터와 지도 조각을 함께 복사합니다.
실행: py build_site.py   (GitHub Actions 도 이 스크립트로 사이트를 만들어 올려요)
"""
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "_site"
PAGES = ["index.html", "포레온_실거래가_정리.html"]
COPY = ["prices_data.js", "listings.js", "tiles"]

# claude.ai 미리보기가 자동으로 넣어 주던 기본 스타일과 같은 내용
BASE_CSS = """<style>
:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
body{margin:0;font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
img{max-width:100%}
[hidden]{display:none!important}
</style>"""

HEAD_TAG = re.compile(r"\s*(<title>.*?</title>|<meta\b[^>]*>|<link\b[^>]*>|<style>.*?</style>)", re.S)


def wrap(src: str) -> str:
    head, pos = [], 0
    while True:                                   # 맨 앞의 title/meta/link/style 를 <head> 로 옮김
        m = HEAD_TAG.match(src, pos)
        if not m:
            break
        head.append(m.group(1))
        pos = m.end()
    body = src[pos:].lstrip("\n")
    title = re.search(r"<title>(.*?)</title>", src, re.S)
    desc = re.search(r'<meta name="description" content="([^"]*)"', src)
    og = []
    if title:
        og.append(f'<meta property="og:title" content="{title.group(1)}">')
    if desc:
        og.append(f'<meta property="og:description" content="{desc.group(1)}">')
    return ("<!doctype html>\n<html lang=\"ko\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
            + "\n".join(og + [BASE_CSS] + head) + "\n</head>\n<body>\n" + body + "\n</body>\n</html>\n")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for name in PAGES:
        src = HERE / name
        if src.exists():
            (OUT / name).write_text(wrap(src.read_text(encoding="utf-8")), encoding="utf-8")
    for name in COPY:
        src = HERE / name
        if src.is_dir():
            shutil.copytree(src, OUT / name, ignore=shutil.ignore_patterns("*.js"))
        elif src.exists():
            shutil.copy2(src, OUT / name)
    (OUT / ".nojekyll").write_text("")            # GitHub Pages 가 파일을 그대로 쓰게 함
    n = sum(1 for _ in OUT.rglob("*") if _.is_file())
    print(f"_site 폴더에 {n}개 파일을 만들었어요.")


if __name__ == "__main__":
    main()
