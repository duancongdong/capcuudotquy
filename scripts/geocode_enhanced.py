# -*- coding: utf-8 -*-
"""Geocode benh vien theo nhieu chien luoc, co kiem tra do tin cay.

Chay tu thu muc goc du an:
    python3 -m pip install requests
    python3 scripts/geocode_enhanced.py

Tuy chon de tang ty le tim thay (khong ghi khoa vao ma nguon):
    export GEOAPIFY_API_KEY="..."
    export OPENCAGE_API_KEY="..."
    python3 scripts/geocode_enhanced.py

Thu tu xu ly:
1. Nominatim: ten + dia chi, dia chi, ten + dia phuong, ten benh vien.
2. Geoapify neu co GEOAPIFY_API_KEY.
3. OpenCage neu co OPENCAGE_API_KEY.
4. Chi tu dong chap nhan ket qua dat diem tin cay; con lai ghi report.

Luu y: day la du lieu dia diem cap cuu. Chuong trinh khong gan tam toa do
trung tam xa/tinh cho benh vien, vi nhu vay co the tao vi tri sai nguy hiem.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Optional

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "hospitals.json"
CACHE_FILE = BASE_DIR / "data" / "geocode_cache_v2.json"
REVIEW_FILE = BASE_DIR / "data" / "geocode_review.csv"
CONTACT_EMAIL = "khoanam.ce07@gmail.com"
USER_AGENT = f"cap-cuu-dot-quy-community-geocoder/2.0 (contact: {CONTACT_EMAIL})"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
GEOAPIFY_URL = "https://api.geoapify.com/v1/geocode/search"
OPENCAGE_URL = "https://api.opencagedata.com/geocode/v1/json"
GEOAPIFY_KEY = os.getenv("GEOAPIFY_API_KEY", "").strip()
OPENCAGE_KEY = os.getenv("OPENCAGE_API_KEY", "").strip()
CACHE_VERSION = 2
NOMINATIM_INTERVAL = 1.10
TIMEOUT = (10, 35)

STOPWORDS = {
    "benh", "vien", "da", "khoa", "trung", "tam", "y", "te", "khu", "vuc",
    "tinh", "thanh", "pho", "co", "so", "so", "quoc", "te", "viet", "nam",
    "duong", "phuong", "xa", "thi", "tran", "hospital", "medical", "center",
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower().replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def tokens(text: str) -> set[str]:
    return {x for x in fold(text).split() if len(x) >= 2 and x not in STOPWORDS}


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip(" ,")


def address_variants(address: str, province: str) -> list[str]:
    """Tao bien the tu day du den rut gon, khong sua du lieu goc."""
    a = compact(address)
    variants = [a]
    replacements = [
        (r"\bTP\.?\s*HCM\b", "Thành phố Hồ Chí Minh"),
        (r"\bTP\.?\s*Hà Nội\b", "Hà Nội"),
        (r"\bTP\.?\s*", ""),
        (r"\bP\.?\s*", "Phường "),
        (r"\bQ\.?\s*(\d+)\b", r"Quận \1"),
        (r"\bTDP\b", "Tổ dân phố"),
        (r"\bKP\b", "Khu phố"),
        (r"\bQL\s*([0-9]+[A-Z]?)\b", r"Quốc lộ \1"),
    ]
    b = a
    for pattern, repl in replacements:
        b = re.sub(pattern, repl, b, flags=re.I)
    variants.append(compact(b))

    # Bo cac cap dia chi qua chi tiet ma OSM co the chua lap chi muc.
    parts = [compact(x) for x in re.split(r",", b) if compact(x)]
    noisy = re.compile(r"^(so\s+)?(khu pho|khom|ap|thon|to|tdp|khu vuc)\b", re.I)
    simpler = [p for p in parts if not noisy.search(fold(p))]
    if simpler:
        variants.append(", ".join(simpler))

    if province and fold(province) not in fold(b):
        variants.append(f"{b}, {province}")

    out = []
    seen = set()
    for value in variants:
        value = compact(re.sub(r",\s*,", ",", value))
        if value and fold(value) not in seen:
            seen.add(fold(value))
            out.append(value)
    return out


def query_variants(h: dict[str, Any]) -> list[str]:
    name = compact(str(h.get("name", "")))
    address = compact(str(h.get("address", "")))
    province = compact(str(h.get("province", "")))
    av = address_variants(address, province)
    queries = []
    if av:
        queries.append(f"{name}, {av[0]}, Việt Nam")
        queries.extend(f"{x}, Việt Nam" for x in av)
    if province:
        queries.append(f"{name}, {province}, Việt Nam")
    queries.append(f"{name}, Việt Nam")
    out, seen = [], set()
    for q in queries:
        q = compact(q)
        key = fold(q)
        if q and key not in seen:
            seen.add(key)
            out.append(q)
    return out


def candidate_score(h: dict[str, Any], label: str, result_type: str = "") -> float:
    """Diem 0..1. Uu tien khop ten; dia chi chi dong vai tro bo sung."""
    name_t = tokens(str(h.get("name", "")))
    addr_t = tokens(f"{h.get('address', '')} {h.get('province', '')}")
    cand_t = tokens(label)
    name_overlap = len(name_t & cand_t) / max(1, len(name_t))
    addr_overlap = len(addr_t & cand_t) / max(1, min(len(addr_t), 8))
    score = 0.72 * name_overlap + 0.28 * min(addr_overlap, 1.0)
    if result_type in {"hospital", "clinic", "healthcare"}:
        score += 0.08
    return min(score, 1.0)


class RateLimiter:
    def __init__(self, interval: float):
        self.interval = interval
        self.last: Optional[float] = None

    def wait(self) -> None:
        now = time.monotonic()
        if self.last is not None:
            delay = self.interval - (now - self.last)
            if delay > 0:
                time.sleep(delay)
        self.last = time.monotonic()


def nominatim_candidates(session: requests.Session, limiter: RateLimiter, query: str) -> list[dict[str, Any]]:
    limiter.wait()
    r = session.get(NOMINATIM_URL, params={
        "q": query, "format": "jsonv2", "limit": 5, "countrycodes": "vn",
        "addressdetails": 1, "namedetails": 1, "email": CONTACT_EMAIL,
    }, timeout=TIMEOUT)
    if r.status_code == 403:
        raise RuntimeError("Nominatim trả về 403; dừng nguồn Nominatim.")
    if r.status_code == 429:
        time.sleep(max(float(r.headers.get("Retry-After", "3") or 3), 3.0))
        return []
    r.raise_for_status()
    output = []
    for x in r.json():
        output.append({
            "lat": float(x["lat"]), "lng": float(x["lon"]),
            "label": x.get("display_name", ""),
            "type": x.get("type", ""), "provider": "nominatim",
        })
    return output


def geoapify_candidates(session: requests.Session, query: str) -> list[dict[str, Any]]:
    if not GEOAPIFY_KEY:
        return []
    r = session.get(GEOAPIFY_URL, params={
        "text": query, "filter": "countrycode:vn", "lang": "vi",
        "limit": 5, "apiKey": GEOAPIFY_KEY,
    }, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for f in r.json().get("features", []):
        p = f.get("properties", {})
        out.append({
            "lat": float(p["lat"]), "lng": float(p["lon"]),
            "label": p.get("formatted", ""), "type": p.get("result_type", ""),
            "provider": "geoapify", "provider_confidence": p.get("rank", {}).get("confidence"),
        })
    return out


def opencage_candidates(session: requests.Session, query: str) -> list[dict[str, Any]]:
    if not OPENCAGE_KEY:
        return []
    r = session.get(OPENCAGE_URL, params={
        "q": query, "key": OPENCAGE_KEY, "countrycode": "vn", "language": "vi",
        "limit": 5, "no_annotations": 1,
    }, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for x in r.json().get("results", []):
        g = x.get("geometry", {})
        out.append({
            "lat": float(g["lat"]), "lng": float(g["lng"]),
            "label": x.get("formatted", ""), "type": "",
            "provider": "opencage", "provider_confidence": x.get("confidence"),
        })
    return out


def find_best(h: dict[str, Any], session: requests.Session, limiter: RateLimiter) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
    reviewed: list[dict[str, Any]] = []
    queries = query_variants(h)
    providers = ["nominatim"]
    if GEOAPIFY_KEY:
        providers.append("geoapify")
    if OPENCAGE_KEY:
        providers.append("opencage")

    for provider in providers:
        # Nguon fallback chi can cac truy van manh nhat de tranh ton quota.
        provider_queries = queries if provider == "nominatim" else queries[:2] + queries[-2:]
        for query in provider_queries:
            try:
                if provider == "nominatim":
                    candidates = nominatim_candidates(session, limiter, query)
                elif provider == "geoapify":
                    candidates = geoapify_candidates(session, query)
                else:
                    candidates = opencage_candidates(session, query)
            except requests.RequestException as exc:
                print(f"    {provider}: {exc}")
                continue

            for c in candidates:
                c["query"] = query
                c["score"] = round(candidate_score(h, c["label"], c.get("type", "")), 4)
                reviewed.append(c)

            if reviewed:
                reviewed.sort(key=lambda x: x["score"], reverse=True)
                best = reviewed[0]
                # Tu dong nhan khi ten khop manh, hoac diem tong the rat cao.
                name_match = len(tokens(str(h.get("name", ""))) & tokens(best["label"])) / max(1, len(tokens(str(h.get("name", "")))) )
                if best["score"] >= 0.58 and name_match >= 0.45:
                    return best, reviewed

    return None, reviewed


def write_review(rows: list[dict[str, Any]]) -> None:
    REVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
    fields = ["id", "name", "address", "province", "best_provider", "best_score", "candidate_lat", "candidate_lng", "candidate_label", "candidate_query", "action"]
    with REVIEW_FILE.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    hospitals = load_json(DATA_FILE, [])
    if not isinstance(hospitals, list):
        print(f"LỖI: {DATA_FILE} không phải JSON array", file=sys.stderr)
        return 1
    cache = load_json(CACHE_FILE, {"version": CACHE_VERSION, "items": {}})
    if cache.get("version") != CACHE_VERSION:
        cache = {"version": CACHE_VERSION, "items": {}}
    items = cache.setdefault("items", {})
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "vi,en;q=0.8"})
    limiter = RateLimiter(NOMINATIM_INTERVAL)
    review_rows = []
    success = existing = cached_count = 0

    print(f"Tổng: {len(hospitals)} | Geoapify: {'có' if GEOAPIFY_KEY else 'không'} | OpenCage: {'có' if OPENCAGE_KEY else 'không'}")
    try:
        for i, h in enumerate(hospitals, 1):
            name = str(h.get("name", "Không rõ tên"))
            if h.get("lat") is not None and h.get("lng") is not None:
                existing += 1
                continue
            key = str(h.get("id") or fold(name + " " + str(h.get("address", ""))))
            cached = items.get(key)
            if isinstance(cached, dict) and cached.get("found") is True:
                h["lat"], h["lng"] = cached["lat"], cached["lng"]
                h["geocode"] = cached.get("geocode", {})
                cached_count += 1
                print(f"[{i}/{len(hospitals)}] {name}: OK TỪ CACHE")
                continue

            print(f"[{i}/{len(hospitals)}] {name}: đang thử nhiều chiến lược...")
            best, candidates = find_best(h, session, limiter)
            if best:
                h["lat"], h["lng"] = best["lat"], best["lng"]
                h["geocode"] = {
                    "provider": best["provider"], "score": best["score"],
                    "matchedAddress": best["label"], "query": best["query"],
                    "reviewed": False,
                }
                items[key] = {"found": True, "lat": best["lat"], "lng": best["lng"], "geocode": h["geocode"]}
                success += 1
                print(f"    OK {best['provider']} score={best['score']:.2f} ({best['lat']:.6f}, {best['lng']:.6f})")
            else:
                top = candidates[0] if candidates else {}
                review_rows.append({
                    "id": h.get("id", ""), "name": name, "address": h.get("address", ""), "province": h.get("province", ""),
                    "best_provider": top.get("provider", ""), "best_score": top.get("score", ""),
                    "candidate_lat": top.get("lat", ""), "candidate_lng": top.get("lng", ""),
                    "candidate_label": top.get("label", ""), "candidate_query": top.get("query", ""),
                    "action": "VERIFY_AND_FILL",
                })
                # Khong cache ket qua am de lan sau co the thu lai voi API key/OSM moi.
                print("    CHƯA ĐỦ TIN CẬY, đưa vào geocode_review.csv")
            save_json(DATA_FILE, hospitals)
            save_json(CACHE_FILE, cache)
            write_review(review_rows)
    except KeyboardInterrupt:
        print("\nĐã lưu tiến độ. Chạy lại để tiếp tục.")
        return 130
    finally:
        session.close()

    missing = sum(1 for h in hospitals if h.get("lat") is None or h.get("lng") is None)
    print("\n========== KẾT QUẢ ==========")
    print(f"Đã có trước đó : {existing}")
    print(f"Lấy từ cache   : {cached_count}")
    print(f"Tìm mới        : {success}")
    print(f"Cần xác minh   : {missing}")
    print(f"Báo cáo        : {REVIEW_FILE}")
    return 0 if missing == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
