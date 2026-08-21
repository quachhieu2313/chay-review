import csv

from django.core.management.base import BaseCommand, CommandError

from restaurants.models import Category, PRICE_RANGE_CHOICES, PROVINCE_CHOICES, Restaurant

PROVINCE_LOOKUP = {code: code for code, _ in PROVINCE_CHOICES}
PROVINCE_LOOKUP.update({label.lower(): code for code, label in PROVINCE_CHOICES})

PRICE_LOOKUP = {code: code for code, _ in PRICE_RANGE_CHOICES}
PRICE_LOOKUP.update({label.lower(): code for code, label in PRICE_RANGE_CHOICES})


class Command(BaseCommand):
    help = (
        "Import hàng loạt quán chay từ file CSV do bạn tự thu thập "
        "(xem file mẫu tại data_templates/quan_chay_mau.csv)."
    )

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)
        parser.add_argument(
            "--publish",
            action="store_true",
            help="Đăng công khai ngay (mặc định import ở trạng thái chờ duyệt).",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        publish = options["publish"]

        try:
            f = open(csv_path, encoding="utf-8-sig")
        except OSError as exc:
            raise CommandError(f"Không mở được file {csv_path}: {exc}")

        created_count = 0
        skipped_count = 0

        with f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):
                name = (row.get("name") or "").strip()
                address = (row.get("address") or "").strip()
                if not name or not address:
                    self.stdout.write(self.style.WARNING(f"Dòng {row_num}: thiếu name/address, bỏ qua."))
                    skipped_count += 1
                    continue

                if Restaurant.objects.filter(name=name, address=address).exists():
                    self.stdout.write(self.style.WARNING(f"Dòng {row_num}: '{name}' đã tồn tại, bỏ qua."))
                    skipped_count += 1
                    continue

                province_raw = (row.get("province") or "hcm").strip().lower()
                province = PROVINCE_LOOKUP.get(province_raw, "khac")

                price_raw = (row.get("price_range") or "").strip().lower()
                price_range = PRICE_LOOKUP.get(price_raw, "")

                restaurant = Restaurant.objects.create(
                    name=name,
                    address=address,
                    province=province,
                    description=(row.get("description") or "").strip(),
                    phone=(row.get("phone") or "").strip(),
                    opening_hours=(row.get("opening_hours") or "").strip(),
                    price_range=price_range,
                    is_published=publish,
                )

                category_names = [c.strip() for c in (row.get("categories") or "").split(";") if c.strip()]
                categories = [Category.objects.get_or_create(name=cat_name)[0] for cat_name in category_names]
                if categories:
                    restaurant.categories.set(categories)

                created_count += 1

        status = "công khai" if publish else "chờ duyệt (vào /admin/ để duyệt)"
        self.stdout.write(
            self.style.SUCCESS(
                f"Đã tạo {created_count} quán ({status}), bỏ qua {skipped_count} dòng."
            )
        )
