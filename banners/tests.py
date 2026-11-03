from io import BytesIO
import base64
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone, translation
from PIL import Image

from django.contrib.admin.sites import AdminSite
from django.contrib.staticfiles import finders
from django.test import RequestFactory

from banners.admin import VenueSubmissionAdmin
from banners.digits import persian_digits, persianize_html_digits
from banners.geo import haversine_km
from banners.models import Banner, BlueTickRequest, EventAd, PaymentTransaction, SiteLink, SiteSettings, Tournament, UserProfile, Venue, VenueComment, VenueRating, VenueSubmission


def _future_event_post(days=1, hour="22:00"):
    day = (timezone.localtime() + timedelta(days=days)).date().isoformat()
    return {"event_date": day, "event_hour": hour}


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
        self.assertContains(persian, "کجا برم؟")
        self.assertNotContains(persian, ">مکان</span>")
        self.assertContains(persian, 'href="/ads/"')
        self.assertContains(persian, 'rel="icon"')
        self.assertContains(persian, "Logo.png")
        self.assertContains(persian, 'rel="manifest"')
        self.assertContains(persian, "نصب اپلیکیشن")
        self.assertContains(persian, 'href="/install/"')
        self.assertLess(persian.content.decode().find("نصب اپلیکیشن"), persian.content.decode().find("تقسیم نقش سریع"))
        favicon = self.client.get("/favicon.ico")
        self.assertEqual(favicon.status_code, 200)
        manifest = self.client.get("/manifest.webmanifest")
        self.assertEqual(manifest.status_code, 200)
        self.assertEqual(manifest.json()["short_name"], "کافه کلاب")
        self.assertTrue(any("Logo.png" in icon["src"] for icon in manifest.json()["icons"]))
        worker = self.client.get("/sw.js")
        self.assertEqual(worker.status_code, 200)
        install = self.client.get("/install/")
        self.assertContains(install, "دانلود مستقیم نسخه اندروید")
        self.assertContains(install, 'href="https://cafeclub.amytisapp.ir/downloads/cafeclub.apk"')
        self.assertNotContains(install, "Install app")
        self.assertContains(install, "دانلود مستقیم نسخه آیفون")
        self.assertContains(install, "Share")
        self.assertContains(install, "Add to Home Screen")
        self.assertContains(persian, 'href="/account/profile/"')
        self.assertContains(persian, 'href="/settings/"')
        self.assertContains(persian, "Icon-Settings1.png")
        self.assertContains(persian, "Icon-Settings2.png")
        ads = self.client.get("/ads/")
        self.assertContains(ads, "درج آگهی جدید")
        self.assertContains(ads, "ایوینت مافیا، پانتومیم، گل یا پوچ داری یا تورنومنت برگذار میکنی رایگان آگهی بده")
        self.assertContains(ads, "هنوز آگهی فعالی ثبت نشده است.")
        self.assertContains(ads, "ads-panel")
        location = self.client.get("/location/")
        self.assertContains(location, "کجا برم؟")
        self.assertContains(location, "ثبت کلاب من")
        self.assertNotContains(location, "ثبت کافه یا کلاب من")
        self.assertContains(location, "شهر شما")
        self.assertNotContains(location, "Icon-Search.png")
        self.assertNotContains(location, "نمایش شعب")
        self.assertNotContains(location, "به زودی")
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

        switched = self.client.post("/i18n/setlang/", {"language": "en", "next": "/"})
        self.assertRedirects(switched, "/en/")
        back = self.client.post("/i18n/setlang/", {"language": "fa", "next": "/en/"})
        self.assertRedirects(back, "/")
        nested = self.client.post("/i18n/setlang/", {"language": "fa", "next": "/en/nights/"})
        self.assertRedirects(nested, "/nights/")
        no_slash = self.client.post("/i18n/setlang/", {"language": "fa", "next": "/en"})
        self.assertRedirects(no_slash, "/")
        persian_again = self.client.get("/")
        self.assertContains(persian_again, 'dir="rtl"')
        self.assertContains(persian_again, "شب‌های مرموز کافه کلاب")
        self.client.post("/i18n/setlang/", {"language": "en", "next": "/"})
        bounced = self.client.get("/")
        self.assertRedirects(bounced, "/en/")
        stayed = self.client.get("/", follow=True)
        self.assertContains(stayed, 'dir="ltr"')
        self.assertContains(stayed, "Mysterious Nights at Cafe Club")

    def test_admin_stays_persian_and_rtl_even_with_english_cookie(self):
        user = User.objects.create_superuser("admin", "admin@example.com", "pass-word-123")
        self.client.force_login(user)
        self.client.cookies["django_language"] = "en"

        dashboard = self.client.get("/admin/")
        self.assertContains(dashboard, "پنل مدیریت کافه کلاب")
        self.assertContains(dashboard, "داشبورد مدیریت کافه کلاب")
        self.assertContains(dashboard, 'dir="rtl"')
        self.assertContains(dashboard, "فعالیتهای اخیر")
        self.assertContains(dashboard, "اقدامات دستیار هوش مصنوعی")
        self.assertContains(dashboard, "بازبینی مدیر")
        self.assertContains(dashboard, "فروشگاه و آخرین خریدها")
        dashboard_html = dashboard.content.decode()
        self.assertLess(
            dashboard_html.find("اقدامات دستیار هوش مصنوعی"),
            dashboard_html.find("فروشگاه و آخرین خریدها"),
        )
        self.assertContains(dashboard, "بنرها")
        self.assertContains(dashboard, "تنظیمات")
        self.assertContains(dashboard, "کافه‌ها و کلاب‌ها")
        self.assertContains(dashboard, "آگهی‌ها")
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

    def test_display_name_is_shown_instead_of_username(self):
        user = User.objects.create_user("hostuser", "host@example.com", "pass-word-123")
        self.client.force_login(user)
        page = self.client.get("/account/profile/")
        self.assertContains(page, "نام نمایشی")
        self.assertContains(page, "hostuser")
        saved = self.client.post(
            "/account/username/",
            {"username": "hostuser", "display_name": "میزبان شب", "next": "/account/profile/"},
        )
        self.assertRedirects(saved, "/account/profile/")
        user.club_profile.refresh_from_db()
        self.assertEqual(user.club_profile.display_name, "میزبان شب")
        shown = self.client.get("/")
        self.assertContains(shown, "میزبان شب")
        self.assertNotContains(shown, "hostuser")
        profile = self.client.get("/account/profile/")
        self.assertContains(profile, "میزبان شب")
        self.assertContains(profile, "profile-edit-name")
        self.assertContains(profile, 'name="username"')
        self.assertContains(profile, "hostuser")

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
                "password": "123456",
                "next": "/\\example.com/",
            },
        )
        self.assertTrue(User.objects.filter(username="redirectcheck").exists())
        self.assertRedirects(response, "/account/profile/")
        self.assertTrue(UserProfile.objects.filter(user__username="redirectcheck").exists())
        public_id = User.objects.get(username="redirectcheck").club_profile.public_id
        self.assertGreaterEqual(public_id, 100000)
        self.assertLessEqual(public_id, 999999)


class ProfileAndBlueTickTests(TestCase):
    def test_profile_page_opens_from_header_and_assigns_id_after_login(self):
        home = self.client.get("/")
        self.assertContains(home, 'href="/account/profile/"')
        self.assertContains(home, "Icon-BlueTick-Inactive.png")
        self.assertNotContains(home, "profile-menu")
        page = self.client.get("/account/profile/")
        self.assertContains(page, "پروفایل")
        self.assertContains(page, "profile-sheet")
        self.assertContains(page, "ثبت نام")
        self.assertContains(page, "Icon-Gmail.png")
        self.assertContains(page, "ثبت نام سریع با جیمیل")
        self.assertContains(page, "ثبت نام کاربری و گذرواژه")
        self.assertNotContains(page, "فعالسازی تیک آبی")
        self.assertNotContains(page, "ثبت کلاب یا کافه")
        user = User.objects.create_user("host", "host@gmail.com", "pass-word-123")
        self.client.force_login(user)
        logged = self.client.get("/account/profile/")
        self.assertContains(logged, persian_digits(user.club_profile.public_id_display()))
        self.assertFalse(user.club_profile.is_verified)
        self.assertNotContains(logged, "امکانات تیک آبی")
        self.assertContains(logged, "Icon-BlueTick-Inactive.png")
        self.assertContains(logged, "نام نمایشی")
        self.assertContains(logged, "فعالسازی تیک آبی")
        self.assertContains(logged, "می‌توانی جیمیلت را هم به پروفایل وصل کنی")
        self.assertContains(logged, "خروج")

    def test_simple_password_register_and_unique_username_check(self):
        taken = User.objects.create_user("cafehost", password="123456")
        available = self.client.get("/account/username/available/", {"username": "cafehost"})
        self.assertEqual(available.json()["available"], False)
        free = self.client.get("/account/username/available/", {"username": "clubnew"})
        self.assertEqual(free.json()["available"], True)
        created = self.client.post(
            "/account/register/",
            {"username": "clubnew", "password": "123456", "next": "/account/profile/"},
        )
        self.assertRedirects(created, "/account/profile/")
        self.assertTrue(User.objects.filter(username="clubnew").exists())
        self.client.logout()
        clash = self.client.post("/account/register/", {"username": taken.username, "password": "654321"})
        self.assertContains(clash, "این نام کاربری قبلاً گرفته شده است.")

    def test_rejected_blue_tick_can_be_requested_again(self):
        user = User.objects.create_user("host", "host@example.com", "123456")
        BlueTickRequest.objects.create(
            user=user,
            full_name="علی",
            phone="09120000000",
            biography="میزبان",
            is_reviewed=True,
            status=BlueTickRequest.STATUS_REJECTED,
        )
        self.client.force_login(user)
        page = self.client.get("/account/profile/")
        self.assertContains(page, "درخواست تیک آبی شما رد شد")
        self.assertContains(page, "درخواست مجدد تیک آبی")
        sent = self.client.post(
            "/account/profile/blue-tick/",
            {
                "full_name": "علی میزبان",
                "phone": "09121234567",
                "biography": "گرداننده میز مافیا",
            },
        )
        self.assertRedirects(sent, "/account/profile/")
        waiting = self.client.get("/account/profile/")
        self.assertContains(waiting, "درخواست شما طی ساعات آینده بررسی می‌شود")
        self.assertNotContains(waiting, "blue-tick-activate-btn")

    def test_admin_can_activate_blue_tick_by_public_id(self):
        user = User.objects.create_user("player", "player@example.com", "pass-word-123")
        admin = User.objects.create_superuser("admin", "admin@example.com", "pass-word-123")
        self.client.force_login(admin)
        panel = self.client.get("/admin/banners/userprofile/")
        self.assertContains(panel, "فعال‌سازی تیک آبی")
        public_id = f"{user.club_profile.public_id:06d}"
        activated = self.client.post(
            "/admin/banners/userprofile/activate/",
            {"public_id": public_id, "action": "activate"},
        )
        self.assertRedirects(activated, "/admin/banners/userprofile/")
        user.club_profile.refresh_from_db()
        self.assertTrue(user.club_profile.is_verified)
        self.client.force_login(user)
        verified_header = self.client.get("/")
        self.assertContains(verified_header, "Icon-BlueTick.png")

    def test_verified_user_can_save_optimized_photo_and_bio(self):
        user = User.objects.create_user("star", "star@example.com", "pass-word-123")
        user.club_profile.is_verified = True
        user.club_profile.save(update_fields=["is_verified"])
        self.client.force_login(user)
        buffer = BytesIO()
        Image.new("RGB", (900, 600), (20, 80, 120)).save(buffer, format="PNG")
        uploaded = self.client.post(
            "/account/profile/details/",
            {
                "bio": "گرداننده میز کافه کلاب",
                "photo": SimpleUploadedFile("face.png", buffer.getvalue(), content_type="image/png"),
            },
        )
        self.assertRedirects(uploaded, "/account/profile/")
        user.club_profile.refresh_from_db()
        self.assertEqual(user.club_profile.bio, "گرداننده میز کافه کلاب")
        self.assertTrue(user.club_profile.photo.name.endswith(".webp"))
        with user.club_profile.photo.open("rb") as handle:
            saved = Image.open(handle)
            self.assertLessEqual(max(saved.size), 512)

    def test_one_click_gmail_button_goes_to_google_start(self):
        page = self.client.get("/account/profile/")
        self.assertContains(page, 'href="/account/google/start/?next=/account/profile/"')
        self.assertNotContains(page, "ارسال کد تایید")

    def test_google_start_sends_the_browser_to_google(self):
        from django.test import override_settings

        with override_settings(
            GOOGLE_OAUTH_CLIENT_ID="856339647231-test.apps.googleusercontent.com",
            GOOGLE_OAUTH_CLIENT_SECRET="test-secret",
            GOOGLE_OAUTH_REDIRECT_URI="http://testserver/account/google/callback/",
        ):
            response = self.client.get("/account/google/start/?next=/account/profile/")
        self.assertEqual(response.status_code, 302)
        location = response["Location"]
        self.assertIn("accounts.google.com/o/oauth2/v2/auth", location)
        self.assertIn("client_id=856339647231-test.apps.googleusercontent.com", location)
        self.assertIn("redirect_uri=http%3A%2F%2Ftestserver%2Faccount%2Fgoogle%2Fcallback%2F", location)

    def test_blue_tick_request_saves_and_shows_wait_message(self):
        user = User.objects.create_user("host", "host@example.com", "pass-word-123")
        self.client.force_login(user)
        sent = self.client.post(
            "/account/profile/blue-tick/",
            {
                "full_name": "علی میزبان",
                "phone": "09121234567",
                "biography": "گرداننده میز مافیا در تهران",
            },
        )
        self.assertRedirects(sent, "/account/profile/")
        page = self.client.get("/account/profile/")
        self.assertContains(page, "درخواست شما طی ساعات آینده بررسی می‌شود")
        self.assertNotContains(page, "blue-tick-activate-btn")
        self.assertTrue(BlueTickRequest.objects.filter(user=user, full_name="علی میزبان").exists())

    def test_admin_dashboard_shows_red_counts_for_pending_items(self):
        user = User.objects.create_user("host", "host@example.com", "pass-word-123")
        BlueTickRequest.objects.create(user=user, full_name="علی", phone="09120000000", biography="میزبان")
        buffer = BytesIO()
        Image.new("RGB", (8, 8), (20, 20, 20)).save(buffer, format="PNG")
        VenueSubmission.objects.create(
            name="کلاب نو",
            manager_name="مدیر",
            address="تهران",
            phone="021000",
            hours="۱۸ تا ۲۴",
            logo=SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png"),
        )
        VenueComment.objects.create(venue=make_venue(), author_name="میهمان", body="نظر کافه")
        from scenarios.models import Scenario, ScenarioComment

        scenario = Scenario.objects.create(name="سناریو بازپرس")
        ScenarioComment.objects.create(scenario=scenario, author_name="شاهین", body="یک پیام جدید")
        admin_user = User.objects.create_superuser("alarms", "alarms@example.com", "pass-word-123")
        self.client.force_login(admin_user)
        dashboard = self.client.get("/admin/")
        self.assertContains(dashboard, "ثبت کافه یا کلاب")
        self.assertContains(dashboard, "نظرات کافه")
        self.assertContains(dashboard, "پیام جدید")
        self.assertContains(dashboard, "/admin/scenarios/scenariocomment/?is_approved__exact=0")
        self.assertContains(dashboard, "تیک آبی")
        self.assertContains(dashboard, "admin-alarm-count")
        messages = self.client.get("/admin/scenarios/scenariocomment/?is_approved__exact=0")
        self.assertContains(messages, "یک پیام جدید")


def make_venue(name="کافه شب", city="تهران", lat=35.6892, lng=51.3890, **extra):
    values = {
        "name": name,
        "city": city,
        "address": extra.pop("address", "خیابان آزادی"),
        "phone": extra.pop("phone", "02112345678"),
        "manager_name": extra.pop("manager_name", "مدیر شب"),
        "hours": extra.pop("hours", "شنبه تا پنجشنبه ۱۸ تا ۲۴"),
        "latitude": lat,
        "longitude": lng,
        "is_active": extra.pop("is_active", True),
    }
    values.update(extra)
    return Venue.objects.create(**values)


class PlacesTests(TestCase):
    def test_admin_can_create_a_cafe_and_pick_coordinates(self):
        admin_user = User.objects.create_superuser("admin", "admin@example.com", "pass-word-123")
        self.client.force_login(admin_user)
        listing = self.client.get("/admin/banners/venue/")
        self.assertContains(listing, "کافه‌ها و کلاب‌ها")
        add = self.client.get("/admin/banners/venue/add/")
        self.assertContains(add, "ثبت موقعیت روی نقشه")
        self.assertContains(add, "id_latitude")
        created = self.client.post(
            "/admin/banners/venue/add/",
            {
                "name": "کلاب باران",
                "city": "تهران",
                "manager_name": "سارا",
                "hours": "هر شب ۱۹ تا ۲",
                "address": "ولیعصر",
                "phone": "021999",
                "latitude": "35.700000",
                "longitude": "51.400000",
                "is_active": "on",
                "_save": "ذخیره",
            },
        )
        self.assertEqual(created.status_code, 302)
        venue = Venue.objects.get(name="کلاب باران")
        self.assertEqual(venue.manager_name, "سارا")
        self.assertEqual(str(venue.latitude), "35.700000")

    def test_city_search_sort_rating_comment_captcha_and_navigation(self):
        near = make_venue(name="کافه نزدیک", lat=35.6892, lng=51.3890)
        far = make_venue(name="کافه دور", lat=35.8000, lng=51.5000)
        make_venue(name="کافه اصفهان", city="اصفهان", lat=32.6546, lng=51.6680)
        VenueRating.objects.create(venue=far, guest_key="abc", stars=5)

        home = self.client.get("/")
        self.assertContains(home, "کجا برم؟")
        self.assertContains(home, 'href="/location/"')

        asked = self.client.get("/location/")
        self.assertContains(asked, "شهر شما")
        self.assertContains(asked, "کافه نزدیک")
        self.assertContains(asked, "کافه اصفهان")
        self.assertContains(asked, "نزدیک‌ترین")
        self.assertContains(asked, "places-bar")
        self.assertNotContains(asked, "نمایش شعب")
        self.assertContains(asked, "بدون امتیاز")
        self.assertContains(asked, "نظر")
        self.assertTrue(near.public_id)
        self.assertContains(asked, persian_digits(near.public_id_display()))
        venue_page = self.client.get(f"/location/{near.id}/")
        self.assertContains(venue_page, persian_digits(near.public_id_display()))

        tehran = self.client.get("/location/", {"city": "تهران"})
        self.assertContains(tehran, "کافه نزدیک")
        self.assertContains(tehran, "کافه دور")
        self.assertNotContains(tehran, "کافه اصفهان")
        self.assertContains(tehran, "جستجوی نام کافه یا کلاب")

        searched = self.client.get("/location/", {"q": "نزدیک", "city": "تهران"})
        self.assertContains(searched, "کافه نزدیک")
        self.assertNotContains(searched, "کافه دور")

        by_name = self.client.get("/location/", {"sort": "name", "city": "تهران"}).content.decode()
        self.assertLess(by_name.find("کافه دور"), by_name.find("کافه نزدیک"))

        by_rating = self.client.get("/location/", {"sort": "rating", "city": "تهران"}).content.decode()
        self.assertLess(by_rating.find("کافه دور"), by_rating.find("کافه نزدیک"))

        by_distance = self.client.get(
            "/location/",
            {"sort": "distance", "city": "تهران", "lat": "35.6892", "lng": "51.3890"},
        )
        html = by_distance.content.decode()
        self.assertLess(html.find("کافه نزدیک"), html.find("کافه دور"))
        self.assertContains(by_distance, "گوگل مپ")

        self.assertGreater(haversine_km(35.6892, 51.3890, 35.8000, 51.5000), 1)

        shown = self.client.get("/location/", {"city": ""})
        self.assertNotContains(shown, "نمایش بیشتر")
        for index in range(11):
            make_venue(name=f"کافه اضافه {index}", city="قم", lat=34.64, lng=50.88)
        paged = self.client.get("/location/", {"city": ""})
        self.assertContains(paged, "نمایش بیشتر")
        self.assertEqual(paged.content.decode().count('class="place-card"'), 10)
        more = self.client.get("/location/", {"city": "", "shown": "20"})
        self.assertGreaterEqual(more.content.decode().count('class="place-card"'), 11)

        detail = self.client.get(f"/location/{near.id}/")
        self.assertContains(detail, "مسیریابی")
        self.assertContains(detail, "venue-nav-btn")
        self.assertContains(detail, "venue-card")
        self.assertContains(detail, "ad-chip")
        self.assertContains(detail, "شهر:")
        self.assertContains(detail, "مدیر:")
        self.assertContains(detail, "ساعات کاری:")
        self.assertContains(detail, "آدرس:")
        self.assertContains(detail, "تلفن:")
        self.assertContains(detail, 'data-call="02112345678"')
        self.assertContains(detail, "آیا می‌خواهید با این شماره تماس بگیرید؟")
        self.assertContains(detail, "جمع این دو عدد را بنویسید")
        self.assertContains(detail, "waze.com")
        self.assertContains(detail, "data-nav-external")
        self.assertContains(detail, "geo:")
        self.assertContains(detail, "maps://")
        captcha = self.client.session["venue_comment_captcha"]
        answer = captcha["left"] + captcha["right"]
        bad = self.client.post(
            f"/location/{near.id}/comment/",
            {"author_name": "میهمان", "body": "عالی بود", "captcha": str(answer + 1)},
        )
        self.assertRedirects(bad, f"/location/{near.id}/")
        self.assertFalse(VenueComment.objects.exists())
        captcha = self.client.session["venue_comment_captcha"]
        ok = self.client.post(
            f"/location/{near.id}/comment/",
            {
                "author_name": "میهمان",
                "body": "فضای بازی خوب است",
                "captcha": str(captcha["left"] + captcha["right"]),
            },
        )
        self.assertRedirects(ok, f"/location/{near.id}/", fetch_redirect_response=False)
        followed = self.client.get(f"/location/{near.id}/")
        self.assertContains(followed, "نظر شما با موفقیت ثبت شد و پس از بازبینی در سایت منتشر می‌شود")
        comment = VenueComment.objects.get()
        self.assertFalse(comment.is_approved)
        hidden = self.client.get(f"/location/{near.id}/")
        self.assertNotContains(hidden, "فضای بازی خوب است")
        comment.is_approved = True
        comment.save(update_fields=["is_approved"])
        shown = self.client.get(f"/location/{near.id}/")
        self.assertContains(shown, "فضای بازی خوب است")
        self.assertContains(shown, "venue-sheet")
        self.assertContains(shown, "nav-sheet")

        rated = self.client.post(f"/location/{near.id}/rate/", {"stars": "4"})
        self.assertRedirects(rated, f"/location/{near.id}/")
        self.assertEqual(VenueRating.objects.get(venue=near).stars, 4)
        again = self.client.post(f"/location/{near.id}/rate/", {"stars": "5"})
        self.assertRedirects(again, f"/location/{near.id}/")
        self.assertEqual(VenueRating.objects.filter(venue=near).count(), 1)
        self.assertEqual(VenueRating.objects.get(venue=near).stars, 5)

        comments_admin = User.objects.create_superuser("mod", "mod@example.com", "pass-word-123")
        self.client.force_login(comments_admin)
        board = self.client.get("/admin/banners/venuecomment/")
        self.assertContains(board, "نظرات کاربران در رابطه با کافه کلاب‌ها")
        self.assertContains(board, "فضای بازی خوب است")

    def test_venue_photos_open_in_viewer(self):
        buffer = BytesIO()
        Image.new("RGB", (40, 40), (10, 80, 20)).save(buffer, format="PNG")
        photo = SimpleUploadedFile("cafe.png", buffer.getvalue(), content_type="image/png")
        venue = make_venue(name="کافه گالری", photo_1=photo)
        page = self.client.get(f"/location/{venue.id}/")
        self.assertContains(page, "data-photo=")
        self.assertContains(page, "data-photo-sheet")
        self.assertContains(page, "venue-photo-btn")

    def test_owner_can_submit_a_club_for_review(self):
        page = self.client.get("/location/")
        self.assertContains(page, "ثبت کلاب من")
        self.assertNotContains(page, "ثبت کافه یا کلاب من")
        self.assertContains(page, 'href="/location/submit/"')
        form = self.client.get("/location/submit/")
        self.assertContains(form, "اگر شما مالک یک کافه یا کلاب مافیا هستید")
        self.assertContains(form, "نام کلاب")
        self.assertContains(form, "نام مدیر یا سوپروایزر مجموعه")
        self.assertContains(form, "id=\"venue-map\"")
        self.assertContains(form, "id_latitude")
        self.assertContains(form, "admin/js/venue-map.js")
        map_js = finders.find("admin/js/venue-map.js")
        with open(map_js, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("tile.openstreetmap.de", source)
        self.assertIn("server.arcgisonline.com", source)
        self.assertNotIn("tile.openstreetmap.org", source)
        buffer = BytesIO()
        Image.new("RGB", (40, 40), (10, 80, 20)).save(buffer, format="PNG")
        sent = self.client.post(
            "/location/submit/",
            {
                "name": "کلاب شبانه",
                "manager_name": "نیما",
                "address": "انقلاب",
                "phone": "021111",
                "hours": "چهارشنبه و پنجشنبه ۲۰ تا ۲",
                "city": "تهران",
                "latitude": "35.689200",
                "longitude": "51.389000",
                "logo": SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png"),
            },
        )
        self.assertEqual(sent.status_code, 200)
        self.assertContains(sent, "مورد ارسالی طی ۷۲ ساعت آینده بررسی و به شما اطلاع‌رسانی خواهد شد")
        item = VenueSubmission.objects.get(name="کلاب شبانه")
        self.assertFalse(item.is_reviewed)
        self.assertEqual(item.manager_name, "نیما")
        self.assertEqual(item.city, "تهران")
        self.assertEqual(str(item.latitude), "35.689200")
        admin_user = User.objects.create_superuser("owner-admin", "owner-admin@example.com", "pass-word-123")
        self.client.force_login(admin_user)
        board = self.client.get("/admin/banners/venuesubmission/")
        self.assertContains(board, "درخواست‌های ثبت کافه و کلاب")
        self.assertContains(board, "کلاب شبانه")
        item.is_reviewed = True
        request = RequestFactory().post("/")
        request.user = admin_user
        VenueSubmissionAdmin(VenueSubmission, AdminSite()).save_model(request, item, None, True)
        self.assertTrue(Venue.objects.filter(name="کلاب شبانه", city="تهران", is_active=True).exists())
        listed = self.client.get("/location/")
        self.assertContains(listed, "کلاب شبانه")

    @override_settings(
        DEBUG=True,
        BITPAY_API_KEY="",
        BAZAAR_CLIENT_ID="",
        BAZAAR_CLIENT_SECRET="",
        BAZAAR_REFRESH_TOKEN="",
        MYKET_ACCESS_TOKEN="",
    )
    def test_venue_promo_plans_existing_id_and_new_gold_on_home(self):
        venue = make_venue(name="کلاب نردبان برنز")
        places = self.client.get("/location/")
        self.assertContains(places, "پلن‌های تبلیغاتی")
        self.assertContains(places, 'href="/location/promo/"')
        guest = self.client.get("/location/promo/")
        self.assertRedirects(guest, "/account/login/?next=/location/promo/")
        user = User.objects.create_user("clubads", "clubads@example.com", "pass-word-123")
        self.client.force_login(user)
        form = self.client.get("/location/promo/")
        self.assertContains(form, "pay-frost")
        self.assertContains(form, "۲۵۰ هزار تومان")
        self.assertContains(form, "۴۵۰ هزار تومان")
        self.assertContains(form, "۸۰۰ هزار تومان")
        bronze = self.client.post(
            "/location/promo/",
            {
                "promo_plan": "bronze",
                "venue_mode": "existing",
                "venue_id": venue.public_id_display(),
            },
        )
        self.assertRedirects(bronze, "/location/")
        venue.refresh_from_db()
        self.assertEqual(venue.promo_plan, "bronze")
        places_listing = self.client.get("/location/")
        self.assertContains(places_listing, "کلاب نردبان برنز")
        self.assertContains(places_listing, "نردبان برنزی کلاب")
        ads_listing = self.client.get("/ads/")
        self.assertNotContains(ads_listing, "نردبان برنزی کلاب")
        self.assertNotContains(ads_listing, "is-club")
        gold = self.client.post(
            "/location/promo/",
            {
                "promo_plan": "gold",
                "venue_mode": "new",
                "name": "کلاب طلایی صفحه اول",
                "manager_name": "سارا",
                "address": "ونک",
                "phone": "021222",
                "hours": "هر شب ۲۰ تا ۲",
                "city": "تهران",
                "latitude": "35.689200",
                "longitude": "51.389000",
                "logo": _png_upload("club-gold.png"),
            },
        )
        self.assertRedirects(gold, "/")
        home = self.client.get("/")
        self.assertContains(home, "کلاب طلایی صفحه اول")
        self.assertContains(home, "کافه / کلاب")
        ads = self.client.get("/ads/")
        self.assertNotContains(ads, "نردبان طلایی کلاب")
        self.assertNotContains(ads, "is-club")
        places_gold = self.client.get("/location/")
        self.assertContains(places_gold, "کلاب طلایی صفحه اول")
        self.assertContains(places_gold, "نردبان طلایی کلاب")


class AppSettingsPageTests(TestCase):
    def test_header_opens_settings_page_with_downloads_socials_and_language_last(self):
        SiteLink.objects.filter(key="android").update(url="https://example.com/app.apk")
        SiteLink.objects.filter(key="instagram").update(url="https://instagram.com/cafeclub")
        home = self.client.get("/")
        self.assertContains(home, 'href="/settings/"')
        self.assertNotContains(home, "دانلود مستقیم اپلیکیشن اندروید")
        page = self.client.get("/settings/")
        html = page.content.decode()
        self.assertContains(page, "دانلود مستقیم اپلیکیشن اندروید")
        self.assertContains(page, "https://example.com/app.apk")
        self.assertContains(page, "ما را در شبکه‌های اجتماعی دنبال کنید")
        self.assertContains(page, "https://instagram.com/cafeclub")
        self.assertContains(page, "زبان برنامه")
        self.assertContains(page, "Icon-Language.png")
        self.assertLess(html.find("دانلود اپلیکیشن"), html.find("شبکه‌های اجتماعی"))
        self.assertLess(html.find("ما را در شبکه‌های اجتماعی"), html.rfind("زبان برنامه"))
        self.assertLess(html.rfind("زبان برنامه"), html.find("سیاست حفظ حریم خصوصی"))
        self.assertContains(page, 'href="/privacy/"')
        self.assertContains(page, 'href="/terms/"')
        self.assertContains(page, "شرایط استفاده از خدمات")
        privacy = self.client.get("/privacy/")
        self.assertContains(privacy, "سیاست حفظ حریم خصوصی")
        terms = self.client.get("/terms/")
        self.assertContains(terms, "شرایط استفاده از خدمات")
        admin_user = User.objects.create_superuser("setadmin", "setadmin@example.com", "pass-word-123")
        self.client.force_login(admin_user)
        admin_page = self.client.get("/admin/banners/sitelink/")
        self.assertContains(admin_page, "تنظیمات")
        self.assertContains(admin_page, "دانلود مستقیم اپلیکیشن اندروید")
        self.assertContains(admin_page, "اینستاگرام")
        legal_admin = self.client.get("/admin/banners/legalpage/")
        self.assertContains(legal_admin, "صفحات حقوقی")
        self.assertContains(legal_admin, "سیاست حفظ حریم خصوصی")


def _png_upload(name="event.png"):
    buffer = BytesIO()
    Image.new("RGB", (80, 80), (40, 90, 40)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class EventAdTests(TestCase):
    def test_ads_page_has_green_create_button(self):
        page = self.client.get("/ads/")
        self.assertContains(page, "درج آگهی جدید")
        self.assertContains(page, 'href="/ads/create/"')
        self.assertContains(page, "places-add-btn")
        self.assertContains(page, "ایوینت مافیا، پانتومیم، گل یا پوچ داری یا تورنومنت برگذار میکنی رایگان آگهی بده")
        self.assertContains(page, "ads-panel")

    def test_unverified_user_sees_blue_tick_form_instead_of_ad_form(self):
        user = User.objects.create_user("host", "host@example.com", "pass-word-123")
        self.client.force_login(user)
        page = self.client.get("/ads/create/")
        self.assertContains(page, "برای درج آگهی رایگان باید تیک آبی اکانتتان را فعال کنید")
        self.assertContains(page, "فعالسازی تیک آبی")
        self.assertNotContains(page, "نام ایونت")
        sent = self.client.post(
            "/account/profile/blue-tick/",
            {
                "full_name": "علی میزبان",
                "phone": "09120000000",
                "biography": "گرداننده میز",
                "next": "/ads/create/",
            },
        )
        self.assertRedirects(sent, "/ads/create/")
        again = self.client.get("/ads/create/")
        self.assertContains(again, "درخواست شما طی ساعات آینده بررسی می‌شود")

    def test_verified_user_can_post_ad_and_admin_is_notified(self):
        user = User.objects.create_user("star", "star@example.com", "pass-word-123")
        user.club_profile.is_verified = True
        user.club_profile.save(update_fields=["is_verified"])
        self.client.force_login(user)
        user.club_profile.display_name = "میزبان شب"
        user.club_profile.save(update_fields=["display_name"])
        payload = {
            "event_name": "شب مافیا",
            "organizer_name": "علی",
            "address": "خیابان ولیعصر",
            "phone": "09121234567",
            "ticket_price": "۲۰۰ هزار تومان",
            "cafe_bank": "کافه شب",
            "city": "تهران",
            "district": "ونک",
            "scenario": "بازپرس",
            "image": _png_upload(),
        }
        payload.update(_future_event_post(days=1, hour="22:00"))
        created = self.client.post("/ads/create/", payload)
        ad = EventAd.objects.get(event_name="شب مافیا")
        self.assertRedirects(created, "/ads/")
        listing = self.client.get("/ads/")
        self.assertContains(listing, "بازپرس")
        self.assertContains(listing, "تهران")
        self.assertContains(listing, "میزبان شب")
        self.assertContains(listing, "۲۲:۰۰")
        self.assertContains(listing, "ad-chip")
        self.assertContains(listing, "تاریخ:")
        self.assertContains(listing, "ساعت:")
        self.assertContains(listing, "شهر:")
        self.assertContains(listing, "ad-avatar")
        self.assertContains(listing, "ads-sheet")
        self.assertContains(listing, "۰۹۱۲۱۲۳۴۵۶۷")
        self.assertContains(listing, 'data-call="09121234567"')
        self.assertContains(listing, "آیا می‌خواهید با این شماره تماس بگیرید؟")
        self.assertNotContains(listing, "کافه شب")
        ad = EventAd.objects.get(event_name="شب مافیا")
        detail = self.client.get(f"/ads/{ad.id}/")
        self.assertContains(detail, "شب مافیا")
        self.assertContains(detail, "کافه شب")
        self.assertContains(detail, "میزبان شب")
        self.assertContains(detail, "ad-detail-grid")
        self.assertContains(detail, "ad-chip")
        self.assertContains(detail, "ورودی:")
        self.assertContains(detail, "بانک کافه:")
        self.assertContains(detail, 'data-call="09121234567"')
        liked = self.client.post(f"/ads/{ad.id}/like/", {"next": "/ads/"})
        self.assertRedirects(liked, "/ads/")
        listing = self.client.get("/ads/")
        self.assertContains(listing, ">۱</span>")
        ad = EventAd.objects.get(event_name="شب مافیا")
        self.assertTrue(ad.is_published)
        self.assertTrue(ad.is_new)
        self.assertEqual(ad.expires_at, ad.event_at + timedelta(hours=12))
        admin_user = User.objects.create_superuser("adadmin", "adadmin@example.com", "pass-word-123")
        self.client.force_login(admin_user)
        dashboard = self.client.get("/admin/")
        self.assertContains(dashboard, "آگهی جدید")
        self.assertContains(dashboard, "admin-alarm-count")
        board = self.client.get("/admin/banners/eventad/")
        self.assertContains(board, "شب مافیا")
        ad.refresh_from_db()
        self.assertFalse(ad.is_new)
        reviewed = self.client.get("/admin/")
        self.assertNotContains(reviewed, "آگهی جدید")
        unpublished = self.client.post(
            "/admin/banners/eventad/",
            {
                "action": "unpublish_ads",
                "_selected_action": [str(ad.pk)],
            },
        )
        self.assertEqual(unpublished.status_code, 302)
        ad.refresh_from_db()
        self.assertFalse(ad.is_published)
        public = self.client.get("/ads/")
        self.assertNotContains(public, "شب مافیا")

    def test_monthly_limit_is_three_free_ads(self):
        user = User.objects.create_user("quota", "quota@example.com", "pass-word-123")
        user.club_profile.is_verified = True
        user.club_profile.save(update_fields=["is_verified"])
        now = timezone.now()
        for index in range(3):
            EventAd.objects.create(
                user=user,
                event_name=f"ایونت {index}",
                organizer_name="علی",
                image=_png_upload(f"event-{index}.png"),
                address="تهران",
                starts_at="۲۲:۰۰",
                event_at=now + timedelta(days=1),
                phone="09120000000",
                ticket_price="رایگان",
                cafe_bank="کافه",
                city="تهران",
                district="مرکز",
                scenario="مافیا",
                expires_at=now + timedelta(days=3),
            )
        self.client.force_login(user)
        blocked_payload = {
            "event_name": "چهارم",
            "organizer_name": "علی",
            "address": "تهران",
            "phone": "09120000000",
            "ticket_price": "رایگان",
            "cafe_bank": "کافه",
            "city": "تهران",
            "district": "مرکز",
            "scenario": "مافیا",
            "image": _png_upload("fourth.png"),
        }
        blocked_payload.update(_future_event_post())
        blocked = self.client.post("/ads/create/", blocked_payload)
        self.assertEqual(blocked.status_code, 200)
        self.assertContains(blocked, "سقف سه آگهی رایگان در این ماه پر شده است")
        self.assertEqual(EventAd.objects.filter(user=user).count(), 3)

    def test_staff_user_is_not_limited_to_three_ads(self):
        admin_user = User.objects.create_superuser("adtester", "adtester@example.com", "pass-word-123")
        admin_user.club_profile.is_verified = True
        admin_user.club_profile.save(update_fields=["is_verified"])
        now = timezone.now()
        for index in range(3):
            EventAd.objects.create(
                user=admin_user,
                event_name=f"آگهی ادمین {index}",
                organizer_name="علی",
                image=_png_upload(f"admin-event-{index}.png"),
                address="تهران",
                starts_at="۲۲:۰۰",
                event_at=now + timedelta(days=1),
                phone="09120000000",
                ticket_price="رایگان",
                cafe_bank="کافه",
                city="تهران",
                district="مرکز",
                scenario="مافیا",
                expires_at=now + timedelta(days=3),
            )
        self.client.force_login(admin_user)
        form = self.client.get("/ads/create/")
        self.assertContains(form, "محدودیت سه آگهی در ماه اعمال نمی‌شود")
        payload = {
            "event_name": "آگهی چهارم ادمین",
            "organizer_name": "علی",
            "address": "تهران",
            "phone": "09120000000",
            "ticket_price": "رایگان",
            "cafe_bank": "کافه",
            "city": "تهران",
            "district": "مرکز",
            "scenario": "مافیا",
            "image": _png_upload("admin-fourth.png"),
        }
        payload.update(_future_event_post())
        created = self.client.post("/ads/create/", payload)
        ad = EventAd.objects.get(event_name="آگهی چهارم ادمین")
        self.assertRedirects(created, "/ads/")
        self.assertEqual(EventAd.objects.filter(user=admin_user).count(), 4)

    @override_settings(DEBUG=True)
    def test_create_form_has_four_plans_and_paid_plan_extends_display(self):
        user = User.objects.create_user("planhost", "planhost@example.com", "pass-word-123")
        user.club_profile.is_verified = True
        user.club_profile.save(update_fields=["is_verified"])
        self.client.force_login(user)
        form = self.client.get("/ads/create/")
        self.assertContains(form, "رایگان")
        self.assertContains(form, "برنزی")
        self.assertContains(form, "نقره‌ای")
        self.assertContains(form, "طلایی")
        self.assertContains(form, 'value="free"')
        self.assertContains(form, "ثبت آگهی برای نمایش")
        payload = {
            "promo_plan": "bronze",
            "event_name": "ایونت برنزی چهارروزه",
            "organizer_name": "علی",
            "address": "تهران",
            "phone": "09120000000",
            "ticket_price": "رایگان",
            "cafe_bank": "کافه",
            "city": "تهران",
            "district": "مرکز",
            "scenario": "مافیا",
            "image": _png_upload("bronze-create.png"),
        }
        payload.update(_future_event_post())
        created = self.client.post("/ads/create/", payload)
        ad = EventAd.objects.get(event_name="ایونت برنزی چهارروزه")
        self.assertRedirects(created, f"/ads/{ad.id}/")
        self.assertEqual(ad.promo_plan, "bronze")
        self.assertEqual(ad.expires_at, ad.event_at + timedelta(days=4))
        gold_payload = {
            "promo_plan": "gold",
            "event_name": "ایونت طلایی از فرم",
            "organizer_name": "علی",
            "address": "تهران",
            "phone": "09120000000",
            "ticket_price": "رایگان",
            "cafe_bank": "کافه",
            "city": "تهران",
            "district": "مرکز",
            "scenario": "مافیا",
            "image": _png_upload("gold-create.png"),
        }
        gold_payload.update(_future_event_post())
        gold_created = self.client.post("/ads/create/", gold_payload)
        gold = EventAd.objects.get(event_name="ایونت طلایی از فرم")
        self.assertRedirects(gold_created, f"/ads/{gold.id}/promo/")
        self.assertEqual(gold.expires_at, gold.event_at + timedelta(days=7))
        self.assertTrue(gold.show_on_home)

    @override_settings(DEBUG=True)
    def test_paid_plan_skips_monthly_free_quota(self):
        user = User.objects.create_user("paidquota", "paidquota@example.com", "pass-word-123")
        user.club_profile.is_verified = True
        user.club_profile.save(update_fields=["is_verified"])
        now = timezone.now()
        for index in range(3):
            EventAd.objects.create(
                user=user,
                event_name=f"ایونت سهمیه {index}",
                organizer_name="علی",
                image=_png_upload(f"quota-paid-{index}.png"),
                address="تهران",
                starts_at="۲۲:۰۰",
                event_at=now + timedelta(days=1),
                phone="09120000000",
                ticket_price="رایگان",
                cafe_bank="کافه",
                city="تهران",
                district="مرکز",
                scenario="مافیا",
                expires_at=now + timedelta(days=3),
            )
        self.client.force_login(user)
        payload = {
            "promo_plan": "silver",
            "event_name": "آگهی نقره‌ای بعد سهمیه",
            "organizer_name": "علی",
            "address": "تهران",
            "phone": "09120000000",
            "ticket_price": "رایگان",
            "cafe_bank": "کافه",
            "city": "تهران",
            "district": "مرکز",
            "scenario": "مافیا",
            "image": _png_upload("silver-quota.png"),
        }
        payload.update(_future_event_post())
        created = self.client.post("/ads/create/", payload)
        ad = EventAd.objects.get(event_name="آگهی نقره‌ای بعد سهمیه")
        self.assertRedirects(created, f"/ads/{ad.id}/promo/")
        self.assertEqual(EventAd.objects.filter(user=user).count(), 4)
        self.assertEqual(ad.expires_at, ad.event_at + timedelta(days=5))

    def test_ads_sort_by_nearest_event_and_purge_after_twelve_hours(self):
        user = User.objects.create_user("timeline", "timeline@example.com", "pass-word-123")
        later = timezone.now() + timedelta(days=2, hours=3)
        sooner = timezone.now() + timedelta(days=1, hours=2)
        EventAd.objects.create(
            user=user,
            event_name="ایونت دور",
            organizer_name="علی",
            image=_png_upload("later.png"),
            address="تهران",
            starts_at="دیر",
            event_at=later,
            phone="09120000000",
            ticket_price="رایگان",
            cafe_bank="کافه",
            city="تهران",
            district="مرکز",
            scenario="مافیا",
            expires_at=later + timedelta(hours=12),
        )
        EventAd.objects.create(
            user=user,
            event_name="ایونت نزدیک",
            organizer_name="علی",
            image=_png_upload("sooner.png"),
            address="تهران",
            starts_at="زود",
            event_at=sooner,
            phone="09120000000",
            ticket_price="رایگان",
            cafe_bank="کافه",
            city="تهران",
            district="مرکز",
            scenario="مافیا",
            expires_at=sooner + timedelta(hours=12),
        )
        listing = self.client.get("/ads/").content.decode()
        self.assertLess(listing.find("ایونت نزدیک"), listing.find("ایونت دور"))
        boosted = EventAd.objects.get(event_name="ایونت دور")
        boosted.is_boosted = True
        boosted.boosted_at = timezone.now()
        boosted.save(update_fields=["is_boosted", "boosted_at"])
        boosted_listing = self.client.get("/ads/").content.decode()
        self.assertLess(boosted_listing.find("ایونت دور"), boosted_listing.find("ایونت نزدیک"))
        self.assertIn("نردبان‌شده", boosted_listing)
        self.assertIn("is-boosted", boosted_listing)
        expired = EventAd.objects.create(
            user=user,
            event_name="ایونت گذشته",
            organizer_name="علی",
            image=_png_upload("old.png"),
            address="تهران",
            starts_at="قدیم",
            event_at=timezone.now() - timedelta(hours=13),
            phone="09120000000",
            ticket_price="رایگان",
            cafe_bank="کافه",
            city="تهران",
            district="مرکز",
            scenario="مافیا",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        gone = self.client.get("/ads/")
        self.assertNotContains(gone, "ایونت گذشته")
        self.assertTrue(EventAd.objects.filter(event_name="ایونت گذشته").exists())
        self.client.force_login(user)
        profile = self.client.get("/account/profile/")
        self.assertContains(profile, "آگهی‌های من")
        self.assertContains(profile, "ایونت نزدیک")
        self.assertContains(profile, "ایونت گذشته")
        self.assertContains(profile, "پایان‌یافته")
        self.assertContains(profile, "در حال نمایش")

    @override_settings(DEBUG=True)
    def test_owner_can_boost_ad_to_the_top(self):
        user = User.objects.create_user("ladder", "ladder@example.com", "pass-word-123")
        user.club_profile.is_verified = True
        user.club_profile.save(update_fields=["is_verified"])
        now = timezone.now()
        later = EventAd.objects.create(
            user=user,
            event_name="ایونت بدون نردبان نزدیک",
            organizer_name="علی",
            image=_png_upload("near-boost.png"),
            address="تهران",
            starts_at="زود",
            event_at=now + timedelta(days=1),
            phone="09120000000",
            ticket_price="رایگان",
            cafe_bank="کافه",
            city="تهران",
            district="مرکز",
            scenario="مافیا",
            expires_at=now + timedelta(days=2),
        )
        sooner = EventAd.objects.create(
            user=user,
            event_name="ایونت نردبان دور",
            organizer_name="علی",
            image=_png_upload("far-boost.png"),
            address="تهران",
            starts_at="دیر",
            event_at=now + timedelta(days=4),
            phone="09120000000",
            ticket_price="رایگان",
            cafe_bank="کافه",
            city="تهران",
            district="مرکز",
            scenario="مافیا",
            expires_at=now + timedelta(days=5),
        )
        self.client.force_login(user)
        offer = self.client.get(f"/ads/{sooner.id}/boost/")
        self.assertContains(offer, "پلن تبلیغاتی")
        self.assertContains(offer, "برنزی")
        self.assertContains(offer, "نقره‌ای")
        self.assertContains(offer, "طلایی")
        self.assertContains(offer, "۱۰۰ هزار تومان")
        self.assertContains(offer, "۲۰۰ هزار تومان")
        self.assertContains(offer, "۲۵۰ هزار تومان")
        paid = self.client.post(f"/ads/{sooner.id}/boost/", {"plan": "bronze"})
        self.assertRedirects(paid, "/ads/")
        sooner.refresh_from_db()
        self.assertTrue(sooner.is_boosted)
        self.assertEqual(sooner.promo_plan, "bronze")
        self.assertTrue(sooner.boost_requested)
        listing = self.client.get("/ads/")
        self.assertContains(listing, "نردبان برنزی")
        self.assertContains(listing, "is-plan-bronze")
        html = listing.content.decode()
        self.assertLess(html.find("ایونت نردبان دور"), html.find("ایونت بدون نردبان نزدیک"))
        detail = self.client.get(f"/ads/{sooner.id}/")
        self.assertContains(detail, "نردبان برنزی")
        stranger = User.objects.create_user("otherboost", "otherboost@example.com", "pass-word-123")
        self.client.force_login(stranger)
        self.assertEqual(self.client.post(f"/ads/{later.id}/boost/").status_code, 404)

    @override_settings(DEBUG=False)
    def test_boost_without_gateway_only_records_the_request(self):
        user = User.objects.create_user("pendingboost", "pendingboost@example.com", "pass-word-123")
        user.club_profile.is_verified = True
        user.club_profile.save(update_fields=["is_verified"])
        now = timezone.now()
        ad = EventAd.objects.create(
            user=user,
            event_name="آگهی منتظر درگاه",
            organizer_name="علی",
            image=_png_upload("pending-boost.png"),
            address="تهران",
            starts_at="۲۲:۰۰",
            event_at=now + timedelta(days=1),
            phone="09120000000",
            ticket_price="رایگان",
            cafe_bank="کافه",
            city="تهران",
            district="مرکز",
            scenario="مافیا",
            expires_at=now + timedelta(days=2),
        )
        self.client.force_login(user)
        response = self.client.post(f"/ads/{ad.id}/boost/", {"plan": "bronze"})
        self.assertRedirects(response, f"/ads/{ad.id}/boost/")
        ad.refresh_from_db()
        self.assertTrue(ad.boost_requested)
        self.assertEqual(ad.pending_plan, "bronze")
        self.assertFalse(ad.is_boosted)

    @override_settings(
        DEBUG=True,
        BITPAY_API_KEY="",
        BAZAAR_CLIENT_ID="",
        BAZAAR_CLIENT_SECRET="",
        BAZAAR_REFRESH_TOKEN="",
        MYKET_ACCESS_TOKEN="",
    )
    def test_gold_plan_appears_on_home_and_silver_gets_navigation_extras(self):
        user = User.objects.create_user("goldhost", "goldhost@example.com", "pass-word-123")
        user.club_profile.is_verified = True
        user.club_profile.save(update_fields=["is_verified"])
        now = timezone.now()
        gold = EventAd.objects.create(
            user=user,
            event_name="ایونت طلایی صفحه اول",
            organizer_name="علی",
            image=_png_upload("gold-home.png"),
            address="تهران",
            starts_at="۲۲:۰۰",
            event_at=now + timedelta(days=1),
            phone="09120000000",
            ticket_price="رایگان",
            cafe_bank="کافه",
            city="تهران",
            district="مرکز",
            scenario="مافیا",
            expires_at=now + timedelta(days=2),
        )
        silver = EventAd.objects.create(
            user=user,
            event_name="ایونت نقره‌ای",
            organizer_name="علی",
            image=_png_upload("silver-nav.png"),
            address="تهران",
            starts_at="۲۲:۰۰",
            event_at=now + timedelta(days=1),
            phone="09120000000",
            ticket_price="رایگان",
            cafe_bank="کافه",
            city="تهران",
            district="مرکز",
            scenario="مافیا",
            expires_at=now + timedelta(days=2),
        )
        self.client.force_login(user)
        gold_paid = self.client.post(f"/ads/{gold.id}/boost/", {"plan": "gold"})
        self.assertRedirects(gold_paid, f"/ads/{gold.id}/promo/")
        gold.refresh_from_db()
        self.assertTrue(gold.show_on_home)
        self.assertEqual(gold.promo_plan, "gold")
        home = self.client.get("/")
        self.assertNotContains(home, "آگهی طلایی")
        self.assertContains(home, "ایونت طلایی صفحه اول")
        self.assertContains(home, "مافیا")
        self.assertContains(home, "home-promo-meta")
        self.assertContains(home, 'data-interval="5000"')
        self.assertContains(home, 'class="is-active"')
        html = home.content.decode()
        self.assertLess(html.find("تقسیم نقش سریع"), html.find("ایونت طلایی صفحه اول"))
        self.assertLess(html.find("ایونت طلایی صفحه اول"), html.find("تقسیم نقش سناریو تعداد بالا"))
        silver_paid = self.client.post(f"/ads/{silver.id}/boost/", {"plan": "silver"})
        self.assertRedirects(silver_paid, f"/ads/{silver.id}/promo/")
        extras = self.client.post(
            f"/ads/{silver.id}/promo/",
            {"latitude": "35.6892", "longitude": "51.3890", "photo_1": _png_upload("extra-1.png")},
        )
        self.assertRedirects(extras, f"/ads/{silver.id}/")
        silver.refresh_from_db()
        self.assertTrue(silver.has_nav())
        self.assertTrue(silver.photo_1)
        detail = self.client.get(f"/ads/{silver.id}/")
        self.assertContains(detail, "مسیریابی")
        self.assertContains(detail, "venue-gallery")
        self.assertContains(detail, "data-nav-external")
        self.assertContains(detail, "geo:")


class AppSourceTests(TestCase):
    def test_referral_links_hide_install_and_bind_the_market_gateway(self):
        SiteLink.objects.filter(key="android").update(url="https://example.com/app.apk")
        SiteLink.objects.filter(key="bazaar").update(url="https://cafebazaar.ir/app/ir.cafeclub.amytis")
        SiteLink.objects.filter(key="myket").update(url="https://myket.ir/app/ir.cafeclub.amytis")
        home = self.client.get("/")
        self.assertContains(home, "نصب اپلیکیشن")
        self.assertContains(home, 'href="/install/"')
        self.assertContains(home, "data-offline-screen")
        self.assertContains(home, "تلاش مجدد")
        bounced = self.client.get("/app/bazaar/")
        self.assertRedirects(bounced, "/")
        self.assertEqual(self.client.session["app_source"], "bazaar")
        self.assertEqual(self.client.cookies["cafeclub_app"].value, "bazaar")
        listed = self.client.get("/")
        self.assertNotContains(listed, "نصب اپلیکیشن")
        self.assertRedirects(self.client.get("/install/"), "/")
        market = self.client.get("/settings/")
        self.assertContains(market, "https://cafebazaar.ir/app/ir.cafeclub.amytis")
        self.assertNotContains(market, "https://example.com/app.apk")
        user = User.objects.create_user("market", "market@example.com", "pass-word-123")
        self.client.force_login(user)
        self.client.get("/")
        user.club_profile.refresh_from_db()
        self.assertEqual(user.club_profile.app_source, "bazaar")
        profile = self.client.get("/account/profile/")
        self.assertContains(profile, "کافه بازار")
        self.assertEqual(self.client.get("/app/unknown/").status_code, 404)
        self.client.get("/app/direct/")
        user.club_profile.refresh_from_db()
        self.assertEqual(user.club_profile.app_source, "direct")
        direct_settings = self.client.get("/settings/")
        self.assertContains(direct_settings, "https://example.com/app.apk")
        self.assertNotContains(direct_settings, "https://cafebazaar.ir/app/ir.cafeclub.amytis")

    def test_android_webview_on_home_binds_direct_like_referral(self):
        ua = (
            "Mozilla/5.0 (Linux; Android 13; Pixel Build/TQ) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Version/4.0 Chrome/120.0.0.0 Mobile Safari/537.36; wv"
        )
        home = self.client.get("/", HTTP_USER_AGENT=ua)
        self.assertEqual(self.client.session["app_source"], "direct")
        self.assertEqual(self.client.cookies["cafeclub_app"].value, "direct")
        self.assertNotContains(home, "نصب اپلیکیشن")

    def test_app_source_header_binds_store_referral(self):
        self.client.get("/", HTTP_X_APP_SOURCE="myket")
        self.assertEqual(self.client.session["app_source"], "myket")


class MaintenanceModeTests(TestCase):
    def test_staff_can_take_the_public_site_offline(self):
        host = User.objects.create_superuser("host", "host@example.com", "pass-word-123")
        self.client.force_login(host)
        dashboard = self.client.get("/admin/")
        self.assertContains(dashboard, "اپلیکیشن در دست تعمیر است")
        self.assertContains(dashboard, 'action="/admin/site-maintenance/"')
        closed = self.client.post("/admin/site-maintenance/", {"maintenance_mode": "1"})
        self.assertRedirects(closed, "/admin/")
        self.assertTrue(SiteSettings.load().maintenance_mode)
        self.assertContains(self.client.get("/"), "اپلیکیشن در دست تعمیر است", status_code=503)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.client.logout()
        public = self.client.get("/")
        self.assertEqual(public.status_code, 503)
        self.assertContains(public, "اپلیکیشن در دست تعمیر است", status_code=503)
        self.assertContains(public, "maintenance-mark", status_code=503)
        self.assertContains(public, "<figcaption>", status_code=503)
        self.assertContains(public, "Icon-Settings1.png", status_code=503)
        self.assertNotContains(public, "تقسیم نقش سریع", status_code=503)
        self.assertNotContains(public, "نوار پایین", status_code=503)
        self.assertEqual(self.client.get("/admin/login/").status_code, 200)
        self.client.force_login(host)
        opened = self.client.post("/admin/site-maintenance/", {})
        self.assertRedirects(opened, "/admin/")
        self.assertFalse(SiteSettings.load().maintenance_mode)
        self.client.logout()
        self.assertEqual(self.client.get("/").status_code, 200)


class BlockedAccountTests(TestCase):
    def test_blocked_user_cannot_log_in_again(self):
        user = User.objects.create_user("locked", "locked@example.com", "pass-word-123")
        user.club_profile.is_blocked = True
        user.club_profile.save(update_fields=["is_blocked"])
        failed = self.client.post("/account/login/", {"username": "locked", "password": "pass-word-123"})
        self.assertEqual(failed.status_code, 200)
        self.assertContains(failed, "این اکانت مسدود شده است")
        self.client.force_login(user)
        bounced = self.client.get("/")
        self.assertRedirects(bounced, "/account/login/")
        admin = User.objects.create_superuser("blocker", "blocker@example.com", "pass-word-123")
        self.client.force_login(admin)
        board = self.client.get("/admin/banners/userprofile/")
        self.assertContains(board, "مسدود")
        self.assertContains(board, "block_accounts")


class PersianDigitsTests(TestCase):
    def test_html_text_becomes_persian_but_attributes_stay_ascii(self):
        html = '<p>12 آگهی</p><a href="/ads/3/">3</a><input value="12">'
        converted = persianize_html_digits(html)
        self.assertIn("<p>۱۲ آگهی</p>", converted)
        self.assertIn('href="/ads/3/"', converted)
        self.assertIn(">۳</a>", converted)
        self.assertIn('value="12"', converted)
        self.assertIn("<code>lab_bazaar_5k</code>", persianize_html_digits("<code>lab_bazaar_5k</code>"))
        self.assertEqual(persian_digits("2026"), "۲۰۲۶")


class TournamentTests(TestCase):
    def test_home_shows_tournament_section_under_custom_scenarios(self):
        home = self.client.get("/")
        html = home.content.decode()
        self.assertLess(html.find("favorite-scenarios"), html.find("tournament-home"))
        self.assertContains(home, "Icon-Tournament.png")
        self.assertContains(home, "تورنومنت مافیا بساز و همینجا مدیریتش کن")
        self.assertContains(home, 'href="/tournament/create/?fresh=1"')
        self.assertContains(home, "tournament-plus")

    def test_create_flexible_stages_and_home_list(self):
        start = self.client.get("/tournament/create/?fresh=1")
        self.assertContains(start, "اسم تورنومنت")
        named = self.client.post("/tournament/create/", {"name": "جام شب"})
        self.assertRedirects(named, "/tournament/create/count/")
        counted = self.client.post("/tournament/create/count/", {"count": "8"})
        self.assertRedirects(counted, "/tournament/create/names/")
        names = {f"name_{index}": f"بازیکن {index + 1}" for index in range(8)}
        named_players = self.client.post("/tournament/create/names/", names)
        self.assertRedirects(named_players, "/tournament/create/prize-count/")
        prize_count = self.client.post("/tournament/create/prize-count/", {"count": "2"})
        self.assertRedirects(prize_count, "/tournament/create/prizes/")
        created = self.client.post(
            "/tournament/create/prizes/",
            {"prize_0": "۱۰ میلیون تومان", "prize_1": "۵ میلیون تومان"},
        )
        tournament = Tournament.objects.get(name="جام شب")
        self.assertRedirects(created, f"/tournament/{tournament.id}/")
        self.assertEqual(tournament.players.count(), 8)
        manage = self.client.get(f"/tournament/{tournament.id}/")
        self.assertContains(manage, "مدیریت دور اول تورنومنت")
        self.assertContains(manage, "tournament-end")
        self.assertContains(manage, "پایان تورنومنت")
        self.assertContains(manage, "از فهرست تورنومنت‌های شما حذف می‌شود")
        drawn = self.client.post(
            f"/tournament/{tournament.id}/",
            {"action": "draw_1", "group_count": "2", "group_size": "4"},
        )
        self.assertRedirects(drawn, f"/tournament/{tournament.id}/round/1/groups/")
        groups = self.client.get(f"/tournament/{tournament.id}/round/1/groups/")
        self.assertContains(groups, "گروه")
        self.assertContains(groups, "صندلی")
        self.assertContains(groups, "tournament-name")
        self.assertContains(groups, "<bdi dir=\"auto\">")
        self.assertContains(groups, "ذخیره")
        self.assertContains(groups, "Icon-Share.png")
        self.assertContains(groups, "data-share-target")
        manage = self.client.get(f"/tournament/{tournament.id}/")
        self.assertContains(manage, "ساخت دور دوم تورنومنت")
        self.assertContains(manage, "ساخت نیمه نهایی")
        self.assertContains(manage, "ساخت فینال")
        players = list(tournament.players.order_by("id"))
        next_round = self.client.post(
            f"/tournament/{tournament.id}/",
            {
                "action": "next_stage",
                "kind": "semi",
                "advance": [str(players[0].id), str(players[1].id), str(players[2].id), str(players[3].id)],
                "group_count": "2",
                "group_size": "2",
            },
        )
        self.assertRedirects(next_round, f"/tournament/{tournament.id}/round/2/groups/")
        tournament.refresh_from_db()
        self.assertEqual(tournament.active_players().count(), 4)
        still = list(tournament.active_players())
        final = self.client.post(
            f"/tournament/{tournament.id}/",
            {
                "action": "next_stage",
                "kind": "final",
                "advance": [str(still[0].id), str(still[1].id)],
            },
        )
        last = tournament.latest_round()
        self.assertRedirects(final, f"/tournament/{tournament.id}/round/{last.number}/seats/")
        manage = self.client.get(f"/tournament/{tournament.id}/")
        self.assertContains(manage, "مشخص کردن نفرات برتر")
        finalists = list(tournament.active_players())
        duplicate = self.client.post(
            f"/tournament/{tournament.id}/",
            {"action": "set_winners", "place_0": str(finalists[0].id), "place_1": str(finalists[0].id)},
        )
        self.assertContains(duplicate, "نمی‌توان یک نفر را در دو رتبه ثبت کرد")
        self.assertContains(duplicate, "نام تکراری")
        winners = self.client.post(
            f"/tournament/{tournament.id}/",
            {"action": "set_winners", "place_0": str(finalists[0].id), "place_1": str(finalists[1].id)},
        )
        self.assertRedirects(winners, f"/tournament/{tournament.id}/winners/")
        board = self.client.get(f"/tournament/{tournament.id}/winners/")
        self.assertContains(board, "نفر اول")
        self.assertContains(board, "۱۰ میلیون تومان")
        self.assertContains(board, "ذخیره")
        home = self.client.get("/")
        self.assertContains(home, "جام شب")
        self.assertContains(home, "۸ نفره")
        self.assertContains(home, "Icon-List.png")
        self.assertContains(home, f'href="/tournament/{tournament.id}/"')

    def test_max_three_open_tournaments(self):
        for index in range(3):
            self.client.get("/tournament/create/?fresh=1")
            self.client.post("/tournament/create/", {"name": f"جام {index}"})
            self.client.post("/tournament/create/count/", {"count": "4"})
            names = {f"name_{n}": f"بازیکن {n}" for n in range(4)}
            self.client.post("/tournament/create/names/", names)
            self.client.post("/tournament/create/prize-count/", {"count": "1"})
            self.client.post("/tournament/create/prizes/", {"prize_0": "جام"})
        self.assertEqual(Tournament.objects.count(), 3)
        blocked = self.client.get("/tournament/create/?fresh=1")
        self.assertRedirects(blocked, "/")
        home = self.client.get("/")
        self.assertContains(home, "تا پایان یا حذف یکی از تورنومنت‌ها")
        first = Tournament.objects.order_by("id").first()
        ended = self.client.post(f"/tournament/{first.id}/", {"action": "end"})
        self.assertRedirects(ended, "/")
        home = self.client.get("/")
        self.assertContains(home, "tournament-plus")
        allowed = self.client.get("/tournament/create/?fresh=1")
        self.assertContains(allowed, "اسم تورنومنت")


def _gateway_http(url, *, data=None, headers=None, method=None, timeout=20):
    if "gateway-send" in url:
        return 200, "88"
    if "gateway-result" in url:
        return 200, json.dumps({"status": 1})
    if "pardakht.cafebazaar.ir/devapi/v2/auth/token/" in url:
        return 200, json.dumps({"access_token": "bazaar-access", "expires_in": 3600})
    if "/api/validate/" in url:
        return 200, json.dumps({"purchaseState": 0})
    if "developer.myket.ir" in url:
        return 200, json.dumps({"purchaseState": 0})
    raise AssertionError(url)


@override_settings(
    BITPAY_API_KEY="demo-bitpay",
    BITPAY_SANDBOX=False,
    BAZAAR_CLIENT_ID="bazaar-id",
    BAZAAR_CLIENT_SECRET="bazaar-secret",
    BAZAAR_REFRESH_TOKEN="bazaar-refresh",
    MYKET_ACCESS_TOKEN="myket-token",
    ANDROID_PACKAGE_NAME="ir.cafeclub.amytis",
)
class PaymentGatewayTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("payer", "payer@example.com", "pass-word-123")
        self.client.force_login(self.user)

    def _ad(self, name="آگهی پولی"):
        now = timezone.now()
        return EventAd.objects.create(
            user=self.user,
            event_name=name,
            organizer_name="علی",
            image=_png_upload("pay-ad.png"),
            address="تهران",
            starts_at="۲۲:۰۰",
            event_at=now + timedelta(days=1),
            phone="09120000000",
            ticket_price="رایگان",
            cafe_bank="کافه",
            city="تهران",
            district="مرکز",
            scenario="مافیا",
            expires_at=now + timedelta(days=2),
        )

    @patch("banners.gateways._request", side_effect=_gateway_http)
    def test_main_site_without_referral_uses_bitpay(self, _mock):
        ad = self._ad("آگهی وب بیت‌پی")
        offer = self.client.get(f"/ads/{ad.id}/boost/")
        self.assertContains(offer, "pay-frost")
        self.assertContains(offer, "بیت‌پی")
        start = self.client.post(f"/ads/{ad.id}/boost/", {"plan": "bronze"})
        self.assertEqual(start.status_code, 302)
        self.assertIn("/payment/gateway-88-get", start["Location"])
        txn = PaymentTransaction.objects.get(event_ad=ad)
        self.assertEqual(txn.gateway, "bitpay")
        self.assertEqual(txn.source, "direct")

    @patch("banners.gateways._request", side_effect=_gateway_http)
    def test_direct_source_sends_ad_plan_to_bitpay(self, _mock):
        self.client.get("/app/direct/")
        ad = self._ad("آگهی بیت‌پی")
        offer = self.client.get(f"/ads/{ad.id}/boost/")
        self.assertContains(offer, "بیت‌پی")
        self.assertNotContains(offer, "ad_bronze")
        start = self.client.post(f"/ads/{ad.id}/boost/", {"plan": "bronze"})
        self.assertEqual(start.status_code, 302)
        self.assertIn("/payment/gateway-88-get", start["Location"])
        txn = PaymentTransaction.objects.get(event_ad=ad)
        self.assertEqual(txn.gateway, "bitpay")
        self.assertEqual(txn.package.sku, "ad_bronze")
        self.assertEqual(txn.status, "pending")
        callback = self.client.get("/pay/bitpay/callback/", {"trans_id": "t-1", "id_get": "88"})
        self.assertRedirects(callback, "/ads/")
        txn.refresh_from_db()
        ad.refresh_from_db()
        self.assertEqual(txn.status, "completed")
        self.assertEqual(ad.promo_plan, "bronze")

    @override_settings(DEBUG=False)
    @patch("banners.gateways._request", side_effect=_gateway_http)
    def test_bazaar_referral_routes_ad_plan_without_showing_sku(self, _mock):
        self.client.get("/app/bazaar/")
        ad = self._ad("آگهی بازار")
        offer = self.client.get(f"/ads/{ad.id}/boost/")
        self.assertContains(offer, "کافه بازار")
        self.assertNotContains(offer, "SKU")
        start = self.client.post(f"/ads/{ad.id}/boost/", {"plan": "bronze"})
        txn = PaymentTransaction.objects.get(event_ad=ad)
        self.assertEqual(txn.package.sku, "ad_bronze")
        self.assertEqual(txn.gateway, "bazaar")
        self.assertRedirects(start, f"/pay/checkout/{txn.id}/")
        checkout = self.client.get(f"/pay/checkout/{txn.id}/")
        self.assertContains(checkout, "پلن آگهی برنزی")
        self.assertContains(checkout, "data-store-checkout")
        self.assertContains(checkout, "pay-frost")
        self.assertContains(checkout, "pay-copy")
        self.assertContains(checkout, 'data-sku="ad_bronze"')
        self.assertContains(checkout, "store-checkout.js")
        self.assertNotContains(checkout, "توکن خرید")
        self.assertNotContains(checkout, "SKU")
        paid = self.client.post(
            "/pay/verify/bazaar/",
            {"sku": "ad_bronze", "purchase_token": "ad-bz-token"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(paid.json()["ok"], True)
        self.assertTrue(paid.json()["next"])
        ad.refresh_from_db()
        self.assertEqual(ad.promo_plan, "bronze")
        self.assertTrue(ad.is_boosted)

    def test_bazaar_invalid_grant_is_hidden_and_refresh_token_is_saved(self):
        from banners.gateways import GatewayError, GatewayHttpError, bazaar_access_token
        import banners.gateways as gateways

        gateways._bazaar_token.update({"access": "", "expires": 0.0})

        def rotate_token(url, **kwargs):
            if "auth/token" in url:
                return 200, json.dumps(
                    {"access_token": "new-access", "expires_in": 3600, "refresh_token": "rotated-refresh"}
                )
            raise AssertionError(url)

        with patch("banners.gateways._request", side_effect=rotate_token):
            self.assertEqual(bazaar_access_token(), "new-access")
        self.assertEqual(SiteSettings.load().bazaar_refresh_token, "rotated-refresh")

        gateways._bazaar_token.update({"access": "", "expires": 0.0})

        def invalid_grant(url, **kwargs):
            if "auth/token" in url:
                raise GatewayHttpError(400, '{"error":"invalid_grant"}')
            raise AssertionError(url)

        with patch("banners.gateways._request", side_effect=invalid_grant):
            with self.assertRaises(GatewayError) as ctx:
                bazaar_access_token()
        message = str(ctx.exception).lower()
        self.assertNotIn("invalid_grant", message)
        self.assertIn("refresh_token", message)

    def test_bazaar_signed_purchase_works_when_oauth_fails(self):
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from banners.gateways import GatewayHttpError, bazaar_verify
        import banners.gateways as gateways

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        rsa_b64 = base64.b64encode(
            key.public_key().public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        ).decode()
        payload = json.dumps(
            {
                "productId": "ad_bronze",
                "purchaseToken": "signed-token",
                "packageName": "ir.cafeclub.amytis",
                "purchaseState": 0,
            },
            separators=(",", ":"),
        )
        signature = base64.b64encode(
            key.sign(payload.encode("utf-8"), padding.PKCS1v15(), hashes.SHA1())
        ).decode()
        gateways._bazaar_token.update({"access": "", "expires": 0.0})

        def oauth_fails(url, **kwargs):
            if "auth/token" in url:
                raise GatewayHttpError(400, '{"error":"invalid_grant"}')
            raise AssertionError(url)

        with override_settings(BAZAAR_RSA=rsa_b64), patch("banners.gateways._request", side_effect=oauth_fails):
            data = bazaar_verify("ad_bronze", "signed-token", original_json=payload, signature=signature)
        self.assertEqual(data["purchaseToken"], "signed-token")

    @override_settings(DEBUG=False)
    @patch("banners.gateways._request", side_effect=_gateway_http)
    def test_myket_referral_verifies_ad_plan(self, _mock):
        self.client.get("/app/myket/")
        ad = self._ad("آگهی مایکت")
        start = self.client.post(f"/ads/{ad.id}/boost/", {"plan": "bronze"})
        txn = PaymentTransaction.objects.get(event_ad=ad)
        self.assertEqual(txn.gateway, "myket")
        self.assertRedirects(start, f"/pay/checkout/{txn.id}/")
        paid = self.client.post(
            "/pay/verify/myket/",
            {"sku": "ad_bronze", "purchase_token": "ad-mk-token"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(paid.json()["ok"], True)
        ad.refresh_from_db()
        self.assertEqual(ad.promo_plan, "bronze")

    def test_admin_sku_report_lists_ad_and_venue_products(self):
        admin = User.objects.create_superuser("sku-admin", "sku-admin@example.com", "pass-word-123")
        self.client.force_login(admin)
        report = self.client.get("/admin/banners/coinpackage/")
        self.assertContains(report, "ir.cafeclub.amytis")
        self.assertContains(report, "ad_bronze")
        self.assertContains(report, "ad_silver")
        self.assertContains(report, "ad_gold")
        self.assertContains(report, "venue_bronze")
        self.assertContains(report, "venue_silver")
        self.assertContains(report, "venue_gold")
        self.assertNotContains(report, "coins_50")
        shop = self.client.get("/admin/banners/paymenttransaction/")
        self.assertContains(shop, "فروشگاه و آخرین خریدها")
        self.assertContains(shop, "توکن خرید")
        self.assertContains(report, "lab_bazaar_5k")
        self.assertContains(report, "lab_myket_5k")


class DevLabTests(TestCase):
    def test_dev_lab_is_staff_only_and_starts_store_checkouts(self):
        guest = self.client.get("/dev-lab/")
        self.assertEqual(guest.status_code, 302)
        self.assertIn("/admin/login/", guest["Location"])
        member = User.objects.create_user("player", "player@example.com", "pass-word-123")
        self.client.force_login(member)
        blocked = self.client.get("/dev-lab/")
        self.assertEqual(blocked.status_code, 302)
        self.assertIn("/admin/login/", blocked["Location"])
        admin = User.objects.create_superuser("lab-admin", "lab-admin@example.com", "pass-word-123")
        self.client.force_login(admin)
        page = self.client.get("/dev-lab/")
        self.assertContains(page, "آزمایشگاه توسعه")
        self.assertContains(page, "lab_bazaar_5k")
        self.assertContains(page, "lab_myket_5k")
        self.assertContains(page, "تست خرید کافه بازار")
        self.assertContains(page, "تست خرید مایکت")
        self.assertContains(page, "ماژول ۱")
        self.assertContains(page, "ماژول ۲")
        bazaar = self.client.post("/dev-lab/buy/lab_bazaar_5k/")
        bazaar_txn = PaymentTransaction.objects.get(package__sku="lab_bazaar_5k")
        self.assertEqual(bazaar_txn.gateway, "bazaar")
        self.assertEqual(bazaar_txn.amount_toman, 5000)
        self.assertRedirects(bazaar, f"/pay/checkout/{bazaar_txn.id}/")
        myket = self.client.post("/dev-lab/buy/lab_myket_5k/")
        myket_txn = PaymentTransaction.objects.get(package__sku="lab_myket_5k")
        self.assertEqual(myket_txn.gateway, "myket")
        self.assertEqual(myket_txn.amount_toman, 5000)
        self.assertRedirects(myket, f"/pay/checkout/{myket_txn.id}/")
        dashboard = self.client.get("/admin/")
        self.assertContains(dashboard, "آزمایشگاه توسعه")
        self.assertContains(dashboard, "/dev-lab/")


