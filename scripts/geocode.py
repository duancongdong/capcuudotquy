# -*- coding: utf-8 -*-
"""
Geocode danh sach benh vien cho du an cong dong ca nhan.
Du an duoc nguoi dung cho biet la co su ho tro cua Hoi dot quy Viet Nam.

Cai dat:
    python3 -m pip install requests

Chay tu thu muc goc cua du an:
    python3 scripts/geocode.py

Chinh sach su dung Nominatim public:
- Chi dung mot luong va mot may.
- Khong vuot qua 1 request moi giay.
- Cung cap User-Agent va email lien he hop le.
- Luu cache, khong gui lai cung mot truy van.

Duong dan mac dinh:
    data/hospitals.json
    data/geocode_cache.json
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Optional

import requests


# ============================================================
# CAU HINH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "hospitals.json"
OUTPUT_FILE = BASE_DIR / "data" / "hospitals.json"
CACHE_FILE = BASE_DIR / "data" / "geocode_cache.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
CONTACT_EMAIL = "khoanam.ce07@gmail.com"
APPLICATION_NAME = "cap-cuu-dot-quy-community-geocoder"
USER_AGENT = f"{APPLICATION_NAME}/1.0 (contact: {CONTACT_EMAIL})"

# Giu tren 1 giay de tranh vuot gioi han vi sai so dong ho/he thong.
REQUEST_INTERVAL_SECONDS = 1.10
CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS = 30
MAX_RETRIES = 4
SAVE_EVERY = 10
CACHE_NOT_FOUND = True


class NominatimForbiddenError(RuntimeError):
    """Nominatim tu choi request voi HTTP 403."""


class NominatimAuthenticationError(RuntimeError):
    """Nominatim hoac proxy yeu cau xac thuc."""


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "vi,en;q=0.8",
        }
    )
    return session


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"JSON khong hop le: {path}; "
            f"dong {exc.lineno}, cot {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"Khong the doc file {path}: {exc}") from exc


def atomic_save_json(path: Path, data: Any) -> None:
    """Ghi qua file tam de han che hong JSON khi chuong trinh bi ngat."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")

    try:
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    except OSError as exc:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError(f"Khong the ghi file {path}: {exc}") from exc


def has_coordinates(hospital: dict[str, Any]) -> bool:
    return hospital.get("lat") is not None and hospital.get("lng") is not None


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" ,")


def normalize_address(address: str) -> str:
    """Chuan hoa nhe, van giu dau tieng Viet de tang kha nang tim thay."""
    if not isinstance(address, str):
        return ""

    value = unicodedata.normalize("NFC", address)
    value = normalize_whitespace(value)

    replacements = (
        (r"\bTP\.?\s*HCM\b", "Thành phố Hồ Chí Minh"),
        (r"\bTP\.?\s*Hồ Chí Minh\b", "Thành phố Hồ Chí Minh"),
        (r"\bTPHCM\b", "Thành phố Hồ Chí Minh"),
        (r"\bQ\.?\s*(\d+)\b", r"Quận \1"),
        (r"\bP\.?\s*(\d+)\b", r"Phường \1"),
    )

    for pattern, replacement in replacements:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)

    value = normalize_whitespace(value)
    lowered = value.casefold()
    if "việt nam" not in lowered and "vietnam" not in lowered:
        value = f"{value}, Việt Nam"
    return value


def make_cache_key(address: str) -> str:
    return normalize_address(address).casefold()


def get_hospital_name(hospital: dict[str, Any]) -> str:
    name = hospital.get("name")
    return name.strip() if isinstance(name, str) and name.strip() else "Không rõ tên"


def get_hospital_address(hospital: dict[str, Any]) -> str:
    address = hospital.get("address")
    return address.strip() if isinstance(address, str) else ""


class SingleThreadRateLimiter:
    def __init__(self, interval_seconds: float) -> None:
        self.interval_seconds = interval_seconds
        self.last_request_started_at: Optional[float] = None

    def wait(self) -> None:
        now = time.monotonic()
        if self.last_request_started_at is not None:
            remaining = self.interval_seconds - (now - self.last_request_started_at)
            if remaining > 0:
                time.sleep(remaining)
        self.last_request_started_at = time.monotonic()


def parse_retry_after(response: requests.Response) -> Optional[float]:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(float(value), REQUEST_INTERVAL_SECONDS)
    except ValueError:
        return None


def retry_delay(attempt: int, response: Optional[requests.Response] = None) -> float:
    if response is not None:
        server_delay = parse_retry_after(response)
        if server_delay is not None:
            return server_delay
    return min(float(2**attempt), 30.0)


def geocode_address(
    session: requests.Session,
    limiter: SingleThreadRateLimiter,
    address: str,
) -> tuple[Optional[float], Optional[float], Optional[str]]:
    normalized = normalize_address(address)
    if not normalized:
        return None, None, None

    params = {
        "q": normalized,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "vn",
        "addressdetails": 1,
        "email": CONTACT_EMAIL,
    }
    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        limiter.wait()
        try:
            response = session.get(
                NOMINATIM_URL,
                params=params,
                timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            delay = retry_delay(attempt)
            print(f"    Lỗi kết nối; thử lại sau {delay:.0f} giây")
            time.sleep(delay)
            continue

        if response.status_code == 403:
            raise NominatimForbiddenError(
                "Nominatim trả về HTTP 403. Chương trình dừng để tránh gửi thêm "
                "request từ IP đang bị từ chối."
            )
        if response.status_code in (401, 407):
            raise NominatimAuthenticationError(
                f"Máy chủ hoặc proxy trả về HTTP {response.status_code}."
            )
        if response.status_code == 429 or 500 <= response.status_code <= 599:
            last_error = RuntimeError(f"HTTP {response.status_code}")
            if attempt == MAX_RETRIES:
                break
            delay = retry_delay(attempt, response)
            print(
                f"    HTTP {response.status_code}; "
                f"thử lại sau {delay:.0f} giây"
            )
            time.sleep(delay)
            continue

        response.raise_for_status()
        try:
            results = response.json()
        except requests.exceptions.JSONDecodeError as exc:
            raise RuntimeError("Nominatim không trả về JSON hợp lệ.") from exc

        if not isinstance(results, list):
            raise RuntimeError("Cấu trúc phản hồi Nominatim không hợp lệ.")
        if not results:
            return None, None, None

        first = results[0]
        try:
            lat = float(first["lat"])
            lng = float(first["lon"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("Phản hồi không có lat/lon hợp lệ.") from exc

        display_name = first.get("display_name")
        if not isinstance(display_name, str):
            display_name = None
        return lat, lng, display_name

    raise RuntimeError(
        f"Không thể geocode sau {MAX_RETRIES} lần: {normalized}; {last_error}"
    )


def load_cache() -> dict[str, dict[str, Any]]:
    cache = load_json(CACHE_FILE, {})
    if not isinstance(cache, dict):
        raise RuntimeError(f"Cache phải là JSON object: {CACHE_FILE}")
    return cache


def get_cached_coordinates(
    cache: dict[str, dict[str, Any]], address: str
) -> tuple[bool, Optional[float], Optional[float]]:
    item = cache.get(make_cache_key(address))
    if not isinstance(item, dict):
        return False, None, None
    if item.get("found") is False:
        return True, None, None
    try:
        lat = float(item["lat"])
        lng = float(item["lng"])
        return True, lat, lng
    except (KeyError, TypeError, ValueError):
        return False, None, None


def save_cache_result(
    cache: dict[str, dict[str, Any]],
    address: str,
    lat: Optional[float],
    lng: Optional[float],
    display_name: Optional[str],
) -> None:
    cache[make_cache_key(address)] = {
        "query": normalize_address(address),
        "found": lat is not None and lng is not None,
        "lat": lat,
        "lng": lng,
        "display_name": display_name,
    }
    atomic_save_json(CACHE_FILE, cache)


def main() -> int:
    hospitals = load_json(INPUT_FILE, [])
    if not isinstance(hospitals, list):
        print(f"LỖI: {INPUT_FILE} phải chứa một JSON array.", file=sys.stderr)
        return 1

    cache = load_cache()
    session = create_session()
    limiter = SingleThreadRateLimiter(REQUEST_INTERVAL_SECONDS)
    total = len(hospitals)
    stats = {
        "already": 0,
        "cache": 0,
        "api": 0,
        "success": 0,
        "not_found": 0,
        "missing": 0,
        "errors": 0,
    }
    pending_saves = 0

    print(f"Dữ liệu: {INPUT_FILE}")
    print(f"Tổng số bệnh viện: {total}")
    print(f"Số truy vấn đã cache: {len(cache)}\n")

    try:
        for index, hospital in enumerate(hospitals, 1):
            if not isinstance(hospital, dict):
                stats["errors"] += 1
                print(f"[{index}/{total}] DỮ LIỆU KHÔNG HỢP LỆ")
                continue

            name = get_hospital_name(hospital)
            address = get_hospital_address(hospital)

            if has_coordinates(hospital):
                stats["already"] += 1
                print(f"[{index}/{total}] {name}: ĐÃ CÓ TỌA ĐỘ")
                continue
            if not address:
                stats["missing"] += 1
                print(f"[{index}/{total}] {name}: THIẾU ĐỊA CHỈ")
                continue

            cached, lat, lng = get_cached_coordinates(cache, address)
            if cached:
                stats["cache"] += 1
                if lat is not None and lng is not None:
                    hospital["lat"], hospital["lng"] = lat, lng
                    stats["success"] += 1
                    pending_saves += 1
                    print(
                        f"[{index}/{total}] {name}: "
                        f"OK TỪ CACHE ({lat:.6f}, {lng:.6f})"
                    )
                else:
                    stats["not_found"] += 1
                    print(f"[{index}/{total}] {name}: KHÔNG TÌM THẤY TRONG CACHE")
            else:
                print(f"[{index}/{total}] {name}: ĐANG TÌM...")
                try:
                    lat, lng, display_name = geocode_address(
                        session, limiter, address
                    )
                    stats["api"] += 1
                except (requests.RequestException, RuntimeError) as exc:
                    stats["errors"] += 1
                    print(f"[{index}/{total}] {name}: LỖI\n    {exc}")
                    continue

                if lat is None or lng is None:
                    stats["not_found"] += 1
                    print(f"[{index}/{total}] {name}: KHÔNG TÌM THẤY")
                    if CACHE_NOT_FOUND:
                        save_cache_result(cache, address, None, None, None)
                else:
                    hospital["lat"], hospital["lng"] = lat, lng
                    stats["success"] += 1
                    pending_saves += 1
                    save_cache_result(cache, address, lat, lng, display_name)
                    print(f"[{index}/{total}] {name}: OK ({lat:.6f}, {lng:.6f})")

            if pending_saves >= SAVE_EVERY:
                atomic_save_json(OUTPUT_FILE, hospitals)
                pending_saves = 0

    except (NominatimForbiddenError, NominatimAuthenticationError) as exc:
        print(f"\nDỪNG: {exc}", file=sys.stderr)
        atomic_save_json(OUTPUT_FILE, hospitals)
        atomic_save_json(CACHE_FILE, cache)
        return 2
    except KeyboardInterrupt:
        print("\nĐã nhận Ctrl+C; đang lưu kết quả hiện tại...")
        atomic_save_json(OUTPUT_FILE, hospitals)
        atomic_save_json(CACHE_FILE, cache)
        print("Đã lưu. Chạy lại cùng lệnh để tiếp tục.")
        return 130
    finally:
        session.close()

    atomic_save_json(OUTPUT_FILE, hospitals)
    atomic_save_json(CACHE_FILE, cache)

    print("\n========== HOÀN TẤT ==========")
    print(f"Tổng bệnh viện      : {total}")
    print(f"Đã có tọa độ        : {stats['already']}")
    print(f"Lấy từ cache        : {stats['cache']}")
    print(f"Request API mới     : {stats['api']}")
    print(f"Cập nhật thành công : {stats['success']}")
    print(f"Không tìm thấy      : {stats['not_found']}")
    print(f"Thiếu địa chỉ       : {stats['missing']}")
    print(f"Lỗi                 : {stats['errors']}")
    print(f"File kết quả        : {OUTPUT_FILE}")
    print(f"File cache          : {CACHE_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
