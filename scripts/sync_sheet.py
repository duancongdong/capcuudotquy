#!/usr/bin/env python3
"""Convert the public hospital Google Sheet export into hospitals.json."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = ("name", "type", "address", "province")
DEFAULT_SOURCE = "Hội Đột Quỵ Việt Nam (VNSA)"


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\ufeff", "").split()).strip()


def unaccent(value: str) -> str:
    value = value.replace("đ", "d").replace("Đ", "D")
    return "".join(
        char for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )


def slugify(value: str) -> str:
    value = unaccent(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value


def normalized_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unaccent(normalize_text(value)).lower())


def parse_updated_at(value: str) -> str:
    value = normalize_text(value)
    match = re.fullmatch(r"(\d{1,2})/(\d{4})", value)
    if match:
        month, year = int(match.group(1)), match.group(2)
        if not 1 <= month <= 12:
            raise ValueError(f"Ngày cập nhật không hợp lệ: {value!r}")
        return f"{year}-{month:02d}"
    match = re.fullmatch(r"(\d{4})-(\d{1,2})", value)
    if match:
        year, month = match.group(1), int(match.group(2))
        if not 1 <= month <= 12:
            raise ValueError(f"Ngày cập nhật không hợp lệ: {value!r}")
        return f"{year}-{month:02d}"
    raise ValueError("C2 phải có dạng MM/YYYY, ví dụ 06/2026")


def normalize_boolean(value: str) -> str:
    value = normalize_text(value).lower()
    return "Có" if value in {"có", "co", "yes", "true", "1", "x"} else "Không"


COORDINATE_PATTERN = re.compile(
    r"^\s*([-+]?(?:\d+(?:\.\d+)?|\.\d+))\s*,\s*"
    r"([-+]?(?:\d+(?:\.\d+)?|\.\d+))\s*$"
)

HOTLINE_EXTENSION_PATTERN = re.compile(
    r"\(\s*(?:nhấn|nhánh|nhan|ext|extension)\s*[:.]?\s*\d+\s*\)",
    re.IGNORECASE,
)


def validate_hotline(value: str, row_number: int) -> None:
    """Validate the two supported hotline formats without changing display text."""
    value = normalize_text(value)
    if not value:
        return
    if re.search(r"\bhoặc\b", value, re.IGNORECASE):
        raise ValueError(
            f"Dòng {row_number} hotline phải dùng '/' để tách số, không dùng 'hoặc': {value!r}"
        )

    for part in value.split("/"):
        part = part.strip()
        base = HOTLINE_EXTENSION_PATTERN.sub("", part).strip()
        if not re.fullmatch(r"[\d\s().+\-]+", base):
            raise ValueError(
                f"Dòng {row_number} hotline chỉ cho phép số, ký tự định dạng và nhánh trong ngoặc: {part!r}"
            )
        digits = re.sub(r"\D", "", base)
        if len(digits) < 3:
            raise ValueError(f"Dòng {row_number} hotline không có số hợp lệ: {part!r}")

        # Ngoặc chứa số ở cuối phải ghi rõ là nhánh, ví dụ (nhấn 211) hoặc (ext 211).
        if re.search(r"\(\s*\d+\s*\)\s*$", base):
            raise ValueError(
                f"Dòng {row_number} hotline có số nhánh nhưng thiếu 'nhấn' hoặc 'ext': {part!r}"
            )


def parse_coordinates(value: str) -> tuple[float, float] | None:
    """Parse Google Maps order: latitude first, longitude second."""
    value = normalize_text(value)
    if not value:
        return None

    match = COORDINATE_PATTERN.fullmatch(value)
    if not match:
        raise ValueError(
            f"Tọa độ phải có dạng 'lat,lng' (ví dụ '10.3872588,105.440206'): {value!r}"
        )

    lat, lng = (float(number) for number in match.groups())
    if not (-90 <= lat <= 90):
        raise ValueError(f"Latitude ngoài phạm vi -90..90: {lat}")
    if not (-180 <= lng <= 180):
        raise ValueError(f"Longitude ngoài phạm vi -180..180: {lng}")
    return lat, lng


def read_rows(csv_path: Path) -> list[list[str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [[normalize_text(cell) for cell in row] for row in csv.reader(handle)]


def find_header(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    aliases = {
        "name": {"tenbenhvien", "benhvien"},
        "type": {"loaihinh", "donvi"},
        "address": {"diachi", "diachibv"},
        "hotline": {"hotline", "dienthoai", "sodienthoai"},
        "thrombolysis": {"bvcontieusoi huyet".replace(" ", ""), "tieusoi huyet".replace(" ", "")},
        "intervention": {"bvco canthiep".replace(" ", ""), "canthiep"},
        "province": {"tinhtp", "tinhthanh", "tinhthanhpho", "tinh"},
        "coordinates": {"toado", "toadolatlng", "latlng", "coordinates"},
    }
    for row_index, row in enumerate(rows):
        columns = {normalized_header(value): index for index, value in enumerate(row) if value}
        if any(alias in columns for alias in aliases["name"]) and any(
            alias in columns for alias in aliases["address"]
        ):
            mapping: dict[str, int] = {}
            for field, field_aliases in aliases.items():
                for alias in field_aliases:
                    if alias in columns:
                        mapping[field] = columns[alias]
                        break
            # The current sheet intentionally leaves some headers blank. Keep
            # the documented B:I layout as a compatible fallback.
            mapping.setdefault("name", 1)
            mapping.setdefault("type", 2)
            mapping.setdefault("address", 3)
            mapping.setdefault("hotline", 4)
            mapping.setdefault("thrombolysis", 5)
            mapping.setdefault("intervention", 6)
            mapping.setdefault("province", 7)
            mapping.setdefault("coordinates", 8)
            return row_index, mapping
    raise ValueError("Không tìm thấy hàng tiêu đề bệnh viện trong file CSV")


def cell(row: list[str], index: int) -> str:
    return row[index] if index < len(row) else ""


def load_existing(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return {item["id"]: item for item in data if isinstance(item, dict) and item.get("id")}


def convert(csv_path: Path, existing_path: Path) -> list[dict[str, Any]]:
    rows = read_rows(csv_path)
    if len(rows) < 3:
        raise ValueError("Google Sheet không có đủ phần metadata và bảng dữ liệu")

    # E2 is the release gate; C2 is the displayed update month.
    release_status = cell(rows[1], 4).casefold()
    if release_status != "released":
        raise ValueError(f"E2 phải là Released, hiện tại là {cell(rows[1], 4)!r}")
    updated_at = parse_updated_at(cell(rows[1], 2))
    header_index, mapping = find_header(rows)
    existing = load_existing(existing_path)
    records: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}

    for row_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        name = cell(row, mapping["name"])
        if not name:
            continue
        record = {
            "name": name,
            "type": cell(row, mapping["type"]),
            "address": cell(row, mapping["address"]),
            "hotline": cell(row, mapping["hotline"]),
            "thrombolysis": normalize_boolean(cell(row, mapping["thrombolysis"])),
            "intervention": normalize_boolean(cell(row, mapping["intervention"])),
            "province": cell(row, mapping["province"]),
        }
        validate_hotline(record["hotline"], row_number)
        missing = [field for field in REQUIRED_FIELDS if not record[field]]
        if missing:
            raise ValueError(f"Dòng {row_number} thiếu: {', '.join(missing)}")

        base_id = slugify(f"{record['name']}-{record['province']}")
        if not base_id:
            raise ValueError(f"Dòng {row_number} không tạo được id")
        occurrence = seen_ids.get(base_id, 0) + 1
        seen_ids[base_id] = occurrence
        record_id = base_id if occurrence == 1 else f"{base_id}-{occurrence}"

        record.update({
            "id": record_id,
            "status": "active",
            "updatedAt": updated_at,
            "source": DEFAULT_SOURCE,
        })

        coordinates = parse_coordinates(cell(row, mapping["coordinates"]))
        old = existing.get(record_id)
        if coordinates:
            record["lat"], record["lng"] = coordinates
        elif old and old.get("name") == record["name"] and old.get("province") == record["province"] and old.get("address") == record["address"]:
            if old.get("lat") is not None and old.get("lng") is not None:
                record["lat"], record["lng"] = old["lat"], old["lng"]

        records.append(record)

    if not records:
        raise ValueError("Không có bệnh viện hợp lệ để đồng bộ")
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        records = convert(args.csv, args.output)
        args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Đã đồng bộ {len(records)} bệnh viện, updatedAt={records[0]['updatedAt']}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"LỖI: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
