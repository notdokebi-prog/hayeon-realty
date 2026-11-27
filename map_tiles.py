"""포레온 주변 오픈스트리트맵 지도 조각(타일)과 단지 경계를 받아 홈페이지 폴더에 저장합니다.
지도 범위나 확대 단계를 바꿀 때만 다시 실행하면 됩니다.  실행: py map_tiles.py
지도 자료: © OpenStreetMap contributors (ODbL)
"""
import json, math, time, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "realty-homepage-map-builder/1.0"}
# 지도에 담을 범위 (남, 서, 북, 동)
BOX = (37.5135, 127.1270, 37.5320, 127.1520)    # 가까이 볼 때: 포레온 + 올림픽공원역·둔촌동역·둔촌오륜역
WIDE = (37.4900, 127.0750, 37.5600, 127.2000)   # 멀리 볼 때: 송파·강동 일대
# 사무소 (경기도 안양시 동안구 관평로212번길 21) 주변
OFFICE_NEAR = (37.3932, 126.9536, 37.4012, 126.9636)
OFFICE_WIDE = (37.3670, 126.9180, 37.4270, 126.9990)
# 확대 단계별 범위 (포레온 지도의 17단계는 16단계를 확대해서 보여줌)
LEVELS = [(12, WIDE), (13, WIDE), (14, WIDE), (15, BOX), (16, BOX),
          (12, OFFICE_WIDE), (13, OFFICE_WIDE), (14, OFFICE_WIDE),
          (15, OFFICE_NEAR), (16, OFFICE_NEAR), (17, OFFICE_NEAR)]


def tile_xy(lat, lon, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def tiles():
    count = 0
    for z, box in LEVELS:
        x0, y1 = tile_xy(box[0], box[1], z)
        x1, y0 = tile_xy(box[2], box[3], z)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                out = HERE / "tiles" / str(z) / str(x) / f"{y}.png"
                if out.exists():
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                req = urllib.request.Request(f"https://tile.openstreetmap.org/{z}/{x}/{y}.png", headers=UA)
                out.write_bytes(urllib.request.urlopen(req, timeout=30).read())
                count += 1
                time.sleep(0.4)
    return count


def outline():
    q = '[out:json][timeout:25];way["name"~"포레온아파트"](37.51,127.12,37.54,127.16);out geom;'
    req = urllib.request.Request("https://overpass-api.de/api/interpreter",
                                 data=urllib.parse.urlencode({"data": q}).encode(), headers=UA)
    els = json.load(urllib.request.urlopen(req, timeout=60))["elements"]
    shapes = [{"name": e["tags"].get("name", ""),
               "coords": [[round(p["lat"], 6), round(p["lon"], 6)] for p in e["geometry"]]} for e in els]
    (HERE / "tiles" / "foreon_outline.js").write_text(
        "window.FOREON_OUTLINE = " + json.dumps(shapes, ensure_ascii=False) + ";\n", encoding="utf-8")
    return len(shapes)


if __name__ == "__main__":
    print("새로 받은 지도 조각:", tiles())
    try:
        print("단지 경계:", outline(), "개")
    except Exception as e:                       # 경계선은 없어도 지도는 동작함
        print("단지 경계는 받지 못했어요:", e)
