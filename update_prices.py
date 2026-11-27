"""올림픽파크 포레온 실거래가를 국토교통부 공공데이터 API에서 가져와
홈페이지가 읽는 prices_data.js 파일로 저장합니다.

사용법
  1. 같은 폴더의 api_key.txt 에 공공데이터포털 인증키(Decoding 키)를 붙여 넣고 저장
  2. update_prices.bat 더블클릭 (또는: python update_prices.py)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

# ---- 설정 ---------------------------------------------------------------
LAWD_CD = "11740"            # 법정동 코드 앞 5자리: 서울 강동구
DONG = "둔촌동"               # 읍면동 이름
NAME_KEYWORD = "포레온"        # 단지명에 이 글자가 들어간 거래만 사용
START_MONTH = (2024, 11)     # 이 달부터 가져옴 (입주 시작: 2024년 11월)

TRADE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
RENT_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"

HERE = Path(__file__).resolve().parent
KEY_FILE = HERE / "api_key.txt"
OUT_FILE = HERE / "prices_data.js"
# -------------------------------------------------------------------------


class ApiError(Exception):
    pass


def read_key() -> str:
    if not KEY_FILE.exists():
        KEY_FILE.write_text("", encoding="utf-8")
    key = KEY_FILE.read_text(encoding="utf-8-sig").strip()
    if not key:
        raise ApiError(
            f"인증키가 없어요. {KEY_FILE.name} 파일을 메모장으로 열어 "
            "공공데이터포털의 인증키(Decoding)를 붙여 넣고 저장해 주세요."
        )
    # Encoding 키를 넣어도 동작하도록 한 번 풀어 둡니다.
    return urllib.parse.unquote(key)


def months_until_now(start):
    y, m = start
    today = date.today()
    while (y, m) <= (today.year, today.month):
        yield f"{y}{m:02d}"
        m += 1
        if m == 13:
            y, m = y + 1, 1


def text(item, tag):
    el = item.find(tag)
    return (el.text or "").strip() if el is not None and el.text else ""


def num(s):
    s = s.replace(",", "").strip()
    return float(s) if s else 0.0


def parse_response(xml_bytes):
    """XML 응답을 (item 목록, 전체 건수)로 바꿉니다. 오류면 ApiError."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        snippet = xml_bytes[:200].decode("utf-8", "replace")
        raise ApiError(f"응답을 읽을 수 없어요: {snippet}")

    # 인증키 오류 등은 OpenAPI_ServiceResponse 형식으로 옵니다.
    auth_msg = root.findtext(".//returnAuthMsg")
    if auth_msg:
        if "NOT_REGISTERED" in auth_msg:
            raise ApiError(
                "인증키가 아직 등록되지 않았어요. 활용신청 승인 후 1~2시간 뒤에 다시 해 보세요. "
                "그래도 안 되면 api_key.txt에 Decoding 키를 넣었는지 확인해 주세요."
            )
        raise ApiError(f"API 오류: {auth_msg}")

    code = root.findtext(".//resultCode") or ""
    if code not in ("00", "000"):
        msg = root.findtext(".//resultMsg") or "알 수 없는 오류"
        raise ApiError(f"API 오류({code}): {msg}")

    total = int(root.findtext(".//totalCount") or 0)
    return root.findall(".//item"), total


def fetch_all(url, key, ymd):
    items, page = [], 1
    while True:
        query = urllib.parse.urlencode({
            "serviceKey": key, "LAWD_CD": LAWD_CD, "DEAL_YMD": ymd,
            "pageNo": page, "numOfRows": 1000,
        })
        try:
            with urllib.request.urlopen(f"{url}?{query}", timeout=30) as res:
                body = res.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise ApiError("인증키가 올바르지 않거나 아직 승인되지 않았어요. 활용신청 상태를 확인해 주세요.")
            raise ApiError(f"서버 오류(HTTP {e.code}). 잠시 뒤 다시 해 보세요.")
        except urllib.error.URLError as e:
            raise ApiError(f"인터넷 연결을 확인해 주세요. ({e.reason})")
        except (TimeoutError, OSError):
            raise ApiError("국토부 서버가 응답하지 않아요(시간 초과). 잠시 뒤 다시 해 보세요.")
        got, total = parse_response(body)
        items += got
        if len(items) >= total or not got:
            return items
        page += 1


def is_target(item):
    return text(item, "umdNm") == DONG and NAME_KEYWORD in text(item, "aptNm").replace(" ", "")


def deal_date(item):
    y, m, d = text(item, "dealYear"), text(item, "dealMonth"), text(item, "dealDay")
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def to_trade(item):
    return {
        "d": deal_date(item),
        "area": round(num(text(item, "excluUseAr")), 2),
        "price": int(num(text(item, "dealAmount"))),           # 만원
        "floor": text(item, "floor"),
        "dong": text(item, "aptDong"),
        "kind": text(item, "dealingGbn"),                       # 중개거래 / 직거래
        "cancel": text(item, "cdealType") == "O",               # 계약 해제
    }


def to_rent(item):
    return {
        "d": deal_date(item),
        "area": round(num(text(item, "excluUseAr")), 2),
        "deposit": int(num(text(item, "deposit"))),            # 만원
        "monthly": int(num(text(item, "monthlyRent"))),        # 만원
        "floor": text(item, "floor"),
        "type": text(item, "contractType"),                     # 신규 / 갱신
    }


LOG_FILE = HERE / "update_log.txt"


def log(msg):
    """자동 실행 결과를 update_log.txt 에 한 줄씩 남깁니다."""
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M}  {msg}\n")


def fetch_everything(key):
    trades, rents = [], []
    for ymd in months_until_now(START_MONTH):
        print(f"{ymd[:4]}년 {ymd[4:]}월 거래 가져오는 중...")
        trades += [to_trade(i) for i in fetch_all(TRADE_URL, key, ymd) if is_target(i)]
        rents += [to_rent(i) for i in fetch_all(RENT_URL, key, ymd) if is_target(i)]
    return trades, rents


def main():
    # 작업 스케줄러로 창 없이(pythonw) 실행되면 출력할 곳이 없으므로 버립니다.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    auto = "--auto" in sys.argv          # 매일 자동 실행: 서버 오류 시 다시 시도하고 기록을 남김
    attempts = 3 if auto else 1
    for n in range(1, attempts + 1):
        try:
            trades, rents = fetch_everything(read_key())
            break
        except ApiError as e:
            print("\n[실패] " + str(e))
            if auto:
                log(f"실패 ({n}/{attempts}회째): {e}")
            if n == attempts:
                return 1
            time.sleep(300)              # 5분 뒤 다시 시도

    trades.sort(key=lambda t: t["d"], reverse=True)
    rents.sort(key=lambda r: r["d"], reverse=True)
    data = {
        "complex": "올림픽파크 포레온",
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "국토교통부 실거래가 공개시스템 (공공데이터포털 API)",
        "trades": trades,
        "rents": rents,
    }
    OUT_FILE.write_text(
        "// update_prices.py 가 자동으로 만든 파일입니다. 직접 고치지 마세요.\n"
        "window.SILGEORAE = " + json.dumps(data, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    print(f"\n[완료] 매매 {len(trades)}건, 전월세 {len(rents)}건을 저장했어요.")
    print(f"홈페이지 파일(index.html)을 새로고침하면 반영돼요.")
    if auto:
        log(f"완료: 매매 {len(trades)}건, 전월세 {len(rents)}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
