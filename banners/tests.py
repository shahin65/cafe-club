from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import translation

from banners.models import Banner


class BannerSeedTests(TestCase):
    def test_four_banners_are_seeded_in_order(self):
        banners = list(Banner.objects.all())
        self.assertEqual(
            [banner.image.name for banner in banners],
            [
                "banners/Banner1.webp",
                "banners/Banner2.webp",
                "banners/Banner3.webp",
                "banners/Banner4.webp",
            ],
        )
        self.assertEqual(
            [banner.display_order for banner in banners],
            [1, 2, 3, 4],
        )
        self.assertTrue(all(banner.is_active for banner in banners))
        self.assertTrue(all(banner.title_fa and banner.title_en for banner in banners))
        self.assertTrue(all(banner.image.storage.exists(banner.image.name) for banner in banners))

    def test_verbose_names_are_persian(self):
        self.assertEqual(Banner._meta.verbose_name, "بنر")
        self.assertEqual(Banner._meta.verbose_name_plural, "بنرها")
        self.assertEqual(Banner._meta.get_field("title_fa").verbose_name, "عنوان فارسی")
        self.assertEqual(Banner._meta.get_field("title_en").verbose_name, "عنوان انگلیسی")
        self.assertEqual(Banner._meta.get_field("description_fa").verbose_name, "توضیحات فارسی")
        self.assertEqual(Banner._meta.get_field("description_en").verbose_name, "توضیحات انگلیسی")
        self.assertEqual(Banner._meta.get_field("external_url").verbose_name, "نشانی بیرونی")
        self.assertEqual(Banner._meta.get_field("internal_url").verbose_name, "نشانی صفحه داخلی")
        self.assertEqual(Banner._meta.get_field("is_active").verbose_name, "فعال")
        self.assertEqual(Banner._meta.get_field("display_order").verbose_name, "ترتیب نمایش")
        self.assertEqual(Banner._meta.get_field("image").verbose_name, "تصویر بنر")

    def test_internal_url_validation_is_persian(self):
        banner = Banner.objects.get(display_order=1)
        banner.internal_url = "games/"
        with self.assertRaises(ValidationError) as caught:
            banner.full_clean()
        self.assertIn("نشانی صفحه داخلی باید با / شروع شود", str(caught.exception))

    def test_public_site_defaults_to_persian_and_switches_to_english(self):
        persian = self.client.get("/")
        self.assertContains(persian, 'dir="rtl"')
        self.assertContains(persian, "شب‌های مرموز کافه کلاب")
        self.assertContains(persian, "مهمان")
        self.assertContains(persian, "Icon-Home.png")
        self.assertContains(persian, 'aria-current="page"')
        self.assertContains(persian, "Icon-Location.png")
        self.assertContains(persian, "Icon-Advertisement.png")
        self.assertContains(persian, 'href="/location/"')
        self.assertContains(persian, 'href="/ads/"')
        self.assertContains(persian, "Icon-Language.png")
        self.assertContains(persian, "زبان برنامه")
        self.assertContains(persian, 'rel="icon"')
        self.assertContains(persian, "Logo.png")
        self.assertContains(persian, "ثبت کلاب یا کافه")
        self.assertContains(persian, "data-open-app-settings")
        ads = self.client.get("/ads/")
        self.assertContains(ads, "به زودی")
        location = self.client.get("/location/")
        self.assertContains(location, "به زودی")
        self.assertNotContains(persian, "جزئیات")
        self.assertContains(persian, 'data-interval="3000"')
        self.assertContains(persian, 'href="/nights/"')
        self.assertNotContains(persian, "site-nav")

        english = self.client.get("/en/")
        self.assertContains(english, 'dir="ltr"')
        self.assertContains(english, "Mysterious Nights at Cafe Club")
        self.assertContains(english, "Guest")
        self.assertContains(english, 'href="/en/nights/"')
        self.assertContains(english, 'href="/en/games/"')
        self.assertContains(english, 'href="/en/tables/"')

    def test_admin_stays_persian_and_rtl_even_with_english_cookie(self):
        user = User.objects.create_superuser("admin", "admin@example.com", "pass-word-123")
        self.client.force_login(user)
        self.client.cookies["django_language"] = "en"

        dashboard = self.client.get("/admin/")
        self.assertContains(dashboard, "پنل مدیریت کافه کلاب")
        self.assertContains(dashboard, "داشبورد مدیریت کافه کلاب")
        self.assertContains(dashboard, 'dir="rtl"')
        self.assertContains(dashboard, "فعالیتهای اخیر")
        self.assertContains(dashboard, "بنرها")
        self.assertNotContains(dashboard, "Recent actions")

        changelist = self.client.get("/admin/banners/banner/")
        self.assertContains(changelist, "عنوان فارسی")
        self.assertContains(changelist, "عنوان انگلیسی")
        self.assertContains(changelist, "شب‌های مرموز کافه کلاب")
        self.assertContains(changelist, "Hunt in the Dark City")
        self.assertContains(changelist, "banners/Banner1.webp")
        self.assertNotContains(changelist, "Select this object")
        self.assertContains(changelist, "انتخاب این مورد برای یک اقدام")
        positions = [
            changelist.content.decode().find("شب‌های مرموز کافه کلاب"),
            changelist.content.decode().find("ایستگاه بازی کنسول"),
            changelist.content.decode().find("شکار در شهر تاریک"),
            changelist.content.decode().find("میز کارت و استنتاج"),
        ]
        self.assertEqual(positions, sorted(positions))

        change = self.client.get("/admin/banners/banner/1/change/")
        self.assertContains(change, "نشانی بیرونی")
        self.assertContains(change, "نشانی صفحه داخلی")
        self.assertContains(change, "پیش‌نمایش تصویر")
        self.assertContains(change, "ذخیره")

    def test_language_specific_titles(self):
        banner = Banner.objects.get(display_order=2)
        with translation.override("fa"):
            self.assertEqual(banner.title_for_current_language(), "ایستگاه بازی کنسول")
        with translation.override("en"):
            self.assertEqual(banner.title_for_current_language(), "Console Gaming Station")

    def test_profile_username_is_saved_for_the_guest(self):
        saved = self.client.post("/account/username/", {"username": "میزبان", "next": "/"})
        self.assertRedirects(saved, "/")
        named = self.client.get("/")
        self.assertContains(named, "میزبان")
        self.assertNotContains(named, "مهمان")

    def test_profile_redirect_rejects_external_and_backslash_urls(self):
        for target in ("https://example.com/", "//example.com/", "/\\example.com/"):
            with self.subTest(target=target):
                response = self.client.post(
                    "/account/username/", {"username": "guest", "next": target}
                )
                self.assertRedirects(response, "/")

    def test_registration_rejects_backslash_external_redirect(self):
        response = self.client.post(
            "/account/register/",
            {
                "username": "redirectcheck",
                "password1": "Local-only-test-pass-712!",
                "password2": "Local-only-test-pass-712!",
                "next": "/\\example.com/",
            },
        )
        self.assertTrue(User.objects.filter(username="redirectcheck").exists())
        self.assertRedirects(response, "/")
