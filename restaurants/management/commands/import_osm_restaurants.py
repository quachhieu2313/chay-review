"""
Lấy danh sách quán ăn chay/thuần chay THẬT từ OpenStreetMap (Overpass API).

Đây là nguồn dữ liệu mở (giấy phép ODbL), CHO PHÉP tái sử dụng công khai
(khác với việc scrape Google Maps/Foody/TikTok - vi phạm điều khoản dịch vụ
và bản quyền ảnh/review của người dùng nền tảng đó nên KHÔNG nên làm).

Dữ liệu OSM ở Việt Nam cho quán chay còn thưa (cộng đồng OSM chưa gắn tag
nhiều), nên coi đây là một nguồn khởi điểm miễn phí, không phải nguồn chính.
Sau khi import, các quán đều ở trạng thái "chờ duyệt" (is_published=False)
để bạn kiểm tra lại địa chỉ/giờ mở cửa trước khi công khai - dữ liệu OSM có
thể lỗi thời.
"""

import requests
from django.core.management.base import BaseCommand

from restaurants.models import Category, Restaurant

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Bounding box mặc định: khu vực trung tâm TP.HCM. Có thể truyền bbox khác qua --bbox.
DEFAULT_BBOX = "10.72,106.62,10.87,106.72"  # south,west,north,east

QUERY_TEMPLATE = """
[out:json][timeout:60];
(
  node["amenity"~"restaurant|cafe|fast_food"]["diet:vegetarian"~"yes|only"]({bbox});
  node["amenity"~"restaurant|cafe|fast_food"]["diet:vegan"~"yes|only"]({bbox});
);
out body;
"""


class Command(BaseCommand):
    help = "Import quán chay từ OpenStreetMap Overpass API (dữ liệu mở, miễn phí) trong một khu vực."

    def add_arguments(self, parser):
        parser.add_argument(
            "--bbox",
            type=str,
            default=DEFAULT_BBOX,
            help="Bounding box 'south,west,north,east' (mặc định: trung tâm TP.HCM).",
        )
        parser.add_argument("--province", type=str, default="hcm", help="Mã tỉnh/thành để gán cho các quán import.")

    def handle(self, *args, **options):
        bbox = options["bbox"]
        province = options["province"]

        query = QUERY_TEMPLATE.format(bbox=bbox)
        try:
            response = requests.post(
                OVERPASS_URL,
                data={"data": query},
                headers={"User-Agent": "ChayReview/1.0 (du an ca nhan, xem OpenStreetMap ToU)"},
                timeout=90,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            self.stderr.write(self.style.ERROR(f"Không gọi được Overpass API: {exc}"))
            return

        elements = response.json().get("elements", [])
        chay_category, _ = Category.objects.get_or_create(name="Chay (nguồn OpenStreetMap)")

        created_count = 0
        skipped_count = 0

        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name")
            if not name:
                skipped_count += 1
                continue

            address_parts = [
                tags.get("addr:housenumber", ""),
                tags.get("addr:street", ""),
            ]
            address = " ".join(p for p in address_parts if p).strip() or tags.get("addr:full", "")
            if not address:
                skipped_count += 1
                continue

            if Restaurant.objects.filter(name=name, address=address).exists():
                skipped_count += 1
                continue

            restaurant = Restaurant.objects.create(
                name=name,
                address=address,
                province=province,
                phone=tags.get("contact:phone", tags.get("phone", "")),
                opening_hours=tags.get("opening_hours", ""),
                latitude=el.get("lat"),
                longitude=el.get("lon"),
                is_published=False,
                description="Dữ liệu ban đầu lấy từ OpenStreetMap, cần kiểm tra và bổ sung thêm.",
            )
            restaurant.categories.add(chay_category)
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Đã import {created_count} quán từ OpenStreetMap (chờ duyệt), bỏ qua {skipped_count}."
            )
        )
        self.stdout.write("Nhớ credit 'Dữ liệu bản đồ © OpenStreetMap contributors' theo giấy phép ODbL.")
