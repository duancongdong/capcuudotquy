# -*- coding: utf-8 -*-
"""
Áp dụng các tọa độ đã review từ data/geocode_review.csv vào data/hospitals.json.

Quy trình:
1. Mở data/geocode_review.csv bằng Excel/LibreOffice.
2. Với từng dòng đã xác minh:
   - sửa candidate_lat và candidate_lng nếu cần;
   - đặt action = APPLY.
3. Giữ action = VERIFY_AND_FILL hoặc để trống nếu chưa xác minh.
4. Chạy:
       python3 scripts/apply_geocode_review.py

Chương trình:
- chỉ cập nhật dòng có action = APPLY;
- đối chiếu theo id duy nhất;
- kiểm tra lat/lng hợp lệ và nằm trong phạm vi gần Việt Nam;
- không ghi đè tọa độ hiện có, trừ khi dùng --overwrite;
- tạo bản sao lưu trước khi ghi;
- ghi metadata xác minh vào trường geocode;
- xuất báo cáo các bản ghi còn thiếu.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_HOSPITALS = BASE_DIR / "data" / "hospitals.json"
DEFAULT_REVIEW = BASE_DIR / "data" / "geocode_review.csv"
DEFAULT_MISSING = BASE_DIR / "data" / "geocode_missing_after_review.csv"

# Khung kiểm tra rộng quanh lãnh thổ Việt Nam, chỉ nhằm phát hiện lỗi nhập rõ ràng.
MIN_LAT, MAX_LAT = 7.0, 24.5
MIN_LNG, MAX_LNG = 101.0, 111.5
APPLY_ACTIONS = {"apply", "approved", "approve", "verified", "xac nhan", "xác nhận"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def atomic_save_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def normalize_action(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def parse_coordinate(value: str, field: str, row_number: int) -> float:
    raw = (value or "").strip().replace(",", ".")
    if not raw:
        raise ValueError(f"dòng {row_number}: thiếu {field}")
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"dòng {row_number}: {field} không hợp lệ: {value!r}") from exc


def validate_coordinates(lat: float, lng: float, row_number: int) -> None:
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError(f"dòng {row_number}: lat/lng nằm ngoài giới hạn địa lý")
    if not (MIN_LAT <= lat <= MAX_LAT and MIN_LNG <= lng <= MAX_LNG):
        raise ValueError(
            f"dòng {row_number}: ({lat}, {lng}) nằm ngoài khung kiểm tra Việt Nam; "
            "hãy xác minh lại hoặc dùng --allow-outside-vietnam"
        )


def backup_file(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.stem}.backup_{timestamp}{path.suffix}")
    shutil.copy2(path, backup)
    return backup


def write_missing_report(path: Path, hospitals: list[dict[str, Any]]) -> int:
    missing = [
        h for h in hospitals
        if h.get("lat") is None or h.get("lng") is None
    ]
    fields = ["id", "name", "address", "province", "lat", "lng"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for h in missing:
            writer.writerow({key: h.get(key, "") for key in fields})
    return len(missing)


def main() -> int:
    parser = argparse.ArgumentParser(description="Áp dụng geocode review vào hospitals.json")
    parser.add_argument("--hospitals", type=Path, default=DEFAULT_HOSPITALS)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--missing-report", type=Path, default=DEFAULT_MISSING)
    parser.add_argument("--overwrite", action="store_true", help="Cho phép thay tọa độ đã có")
    parser.add_argument(
        "--allow-outside-vietnam", action="store_true",
        help="Bỏ kiểm tra khung tọa độ gần Việt Nam"
    )
    parser.add_argument("--dry-run", action="store_true", help="Kiểm tra nhưng không ghi file")
    args = parser.parse_args()

    if not args.hospitals.exists():
        print(f"LỖI: không tìm thấy {args.hospitals}", file=sys.stderr)
        return 1
    if not args.review.exists():
        print(f"LỖI: không tìm thấy {args.review}", file=sys.stderr)
        return 1

    hospitals = load_json(args.hospitals)
    if not isinstance(hospitals, list):
        print("LỖI: hospitals.json phải là một JSON array", file=sys.stderr)
        return 1

    by_id: dict[str, dict[str, Any]] = {}
    duplicate_ids: set[str] = set()
    for hospital in hospitals:
        hospital_id = str(hospital.get("id", "")).strip()
        if not hospital_id:
            print("LỖI: có bệnh viện thiếu id", file=sys.stderr)
            return 1
        if hospital_id in by_id:
            duplicate_ids.add(hospital_id)
        by_id[hospital_id] = hospital
    if duplicate_ids:
        print(f"LỖI: id bị trùng: {', '.join(sorted(duplicate_ids))}", file=sys.stderr)
        return 1

    updated = skipped = unchanged = 0
    errors: list[str] = []
    seen_review_ids: set[str] = set()

    with args.review.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"id", "candidate_lat", "candidate_lng", "action"}
        missing_columns = required - set(reader.fieldnames or [])
        if missing_columns:
            print(f"LỖI: CSV thiếu cột: {', '.join(sorted(missing_columns))}", file=sys.stderr)
            return 1

        for row_number, row in enumerate(reader, start=2):
            action = normalize_action(row.get("action", ""))
            if action not in APPLY_ACTIONS:
                skipped += 1
                continue

            hospital_id = (row.get("id") or "").strip()
            if not hospital_id:
                errors.append(f"dòng {row_number}: thiếu id")
                continue
            if hospital_id in seen_review_ids:
                errors.append(f"dòng {row_number}: id lặp lại trong CSV: {hospital_id}")
                continue
            seen_review_ids.add(hospital_id)

            hospital = by_id.get(hospital_id)
            if hospital is None:
                errors.append(f"dòng {row_number}: không có id trong hospitals.json: {hospital_id}")
                continue

            try:
                lat = parse_coordinate(row.get("candidate_lat", ""), "candidate_lat", row_number)
                lng = parse_coordinate(row.get("candidate_lng", ""), "candidate_lng", row_number)
                if not args.allow_outside_vietnam:
                    validate_coordinates(lat, lng, row_number)
            except ValueError as exc:
                errors.append(str(exc))
                continue

            has_existing = hospital.get("lat") is not None and hospital.get("lng") is not None
            if has_existing and not args.overwrite:
                if float(hospital["lat"]) == lat and float(hospital["lng"]) == lng:
                    unchanged += 1
                else:
                    errors.append(
                        f"dòng {row_number}: {hospital_id} đã có tọa độ khác; "
                        "dùng --overwrite nếu đã xác minh việc thay thế"
                    )
                continue

            hospital["lat"] = lat
            hospital["lng"] = lng
            hospital["geocode"] = {
                "provider": (row.get("best_provider") or "manual-review").strip() or "manual-review",
                "score": row.get("best_score", ""),
                "matchedAddress": (row.get("candidate_label") or "").strip(),
                "query": (row.get("candidate_query") or "").strip(),
                "reviewed": True,
                "reviewedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
                "reviewMethod": "geocode_review.csv",
            }
            updated += 1

    if errors:
        print("KHÔNG GHI FILE vì còn lỗi:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print("Sửa CSV rồi chạy lại. hospitals.json chưa bị thay đổi.", file=sys.stderr)
        return 2

    remaining = sum(
        1 for h in hospitals
        if h.get("lat") is None or h.get("lng") is None
    )

    print(f"Sẽ cập nhật          : {updated}")
    print(f"Bỏ qua chưa duyệt   : {skipped}")
    print(f"Không đổi           : {unchanged}")
    print(f"Còn thiếu tọa độ    : {remaining}")

    if args.dry_run:
        print("DRY RUN: không ghi bất kỳ file nào.")
        return 0 if remaining == 0 else 3

    backup = backup_file(args.hospitals)
    atomic_save_json(args.hospitals, hospitals)
    missing_count = write_missing_report(args.missing_report, hospitals)

    print(f"Đã cập nhật          : {args.hospitals}")
    print(f"Bản sao lưu          : {backup}")
    print(f"Báo cáo còn thiếu    : {args.missing_report} ({missing_count} dòng)")
    if missing_count == 0:
        print("HOÀN TẤT: tất cả bệnh viện đều có lat/lng.")
        return 0
    print("CHƯA HOÀN TẤT: tiếp tục review các dòng trong báo cáo còn thiếu.")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
