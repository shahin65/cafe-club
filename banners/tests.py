from io import BytesIO

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone, translation
from PIL import Image

from banners.geo import haversine_km
from banners.models import Banner, BlueTickRequest, EventAd, SiteLink, UserProfile, Venue, VenueComment, VenueRating, VenueSubmission


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
        self.assertContains(ads, "درج آگهی رایگان")
        self.assertContains(ads, "ایوینت مافیا، پانتومیم، گل یا پوچ داری یا تورنومنت برگذار میکنی رایگان آگهی بده")
        self.assertContains(ads, "هنوز آگهی فعالی ثبت نشده است.")
        self.assertContains(ads, "ads-panel")
        location = self.client.get("/location/")
        self.assertContains(location, "کجا برم؟")
        self.assertContains(location, "ثبت کافه یا کلاب من")
        self.assertContains(location, "شهر شما")
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
        self.assertContains(page, "ثبت نام")
        self.assertContains(page, "Icon-Gmail.png")
        self.assertContains(page, "ثبت نام سریع با اتصال اکانت جیمیل")
        self.assertContains(page, "اتصال اکانت جیمیل")
        self.assertContains(page, "درخواست برای فعال سازی تیک آبی")
        self.assertNotContains(page, "ثبت کلاب یا کافه")
        user = User.objects.create_user("host", "host@gmail.com", "pass-word-123")
        self.client.force_login(user)
        logged = self.client.get("/account/profile/")
        self.assertContains(logged, user.club_profile.public_id_display())
        self.assertFalse(user.club_profile.is_verified)
        self.assertNotContains(logged, "امکانات تیک آبی")
        self.assertContains(logged, "Icon-BlueTick-Inactive.png")
        self.assertContains(logged, "نام و نام خانوادگی")

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
        self.assertContains(page, "پس از بررسی طی 72 ساعت آینده با شما تماس حاصل خواهد شد")
        self.assertTrue(BlueTickRequest.objects.filter(user=user, full_name="علی میزبان").exists())


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
        self.assertContains(detail, "جمع این دو عدد را بنویسید")
        self.assertContains(detail, "waze.com")
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
        self.assertRedirects(ok, f"/location/{near.id}/")
        comment = VenueComment.objects.get()
        self.assertFalse(comment.is_approved)
        hidden = self.client.get(f"/location/{near.id}/")
        self.assertNotContains(hidden, "فضای بازی خوب است")
        comment.is_approved = True
        comment.save(update_fields=["is_approved"])
        shown = self.client.get(f"/location/{near.id}/")
        self.assertContains(shown, "فضای بازی خوب است")

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

    def test_owner_can_submit_a_club_for_review(self):
        page = self.client.get("/location/")
        self.assertContains(page, "ثبت کافه یا کلاب من")
        self.assertContains(page, 'href="/location/submit/"')
        form = self.client.get("/location/submit/")
        self.assertContains(form, "اگر شما مالک یک کافه یا کلاب مافیا هستید")
        self.assertContains(form, "نام کلاب")
        self.assertContains(form, "نام مدیر یا سوپروایزر مجموعه")
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
                "logo": SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png"),
            },
        )
        self.assertEqual(sent.status_code, 200)
        self.assertContains(sent, "مورد ارسالی طی 72 ساعت آینده بررسی و به شما اطلاع‌رسانی خواهد شد")
        item = VenueSubmission.objects.get(name="کلاب شبانه")
        self.assertFalse(item.is_reviewed)
        self.assertEqual(item.manager_name, "نیما")
        admin_user = User.objects.create_superuser("owner-admin", "owner-admin@example.com", "pass-word-123")
        self.client.force_login(admin_user)
        board = self.client.get("/admin/banners/venuesubmission/")
        self.assertContains(board, "درخواست‌های ثبت کافه و کلاب")
        self.assertContains(board, "کلاب شبانه")


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
        admin_user = User.objects.create_superuser("setadmin", "setadmin@example.com", "pass-word-123")
        self.client.force_login(admin_user)
        admin_page = self.client.get("/admin/banners/sitelink/")
        self.assertContains(admin_page, "تنظیمات")
        self.assertContains(admin_page, "دانلود مستقیم اپلیکیشن اندروید")
        self.assertContains(admin_page, "اینستاگرام")


def _png_upload(name="event.png"):
    buffer = BytesIO()
    Image.new("RGB", (80, 80), (40, 90, 40)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class EventAdTests(TestCase):
    def test_ads_page_has_green_create_button(self):
        page = self.client.get("/ads/")
        self.assertContains(page, "درج آگهی رایگان")
        self.assertContains(page, 'href="/ads/create/"')
        self.assertContains(page, "places-add-btn")
        self.assertContains(page, "ایوینت مافیا، پانتومیم، گل یا پوچ داری یا تورنومنت برگذار میکنی رایگان آگهی بده")
        self.assertContains(page, "ads-panel")

    def test_unverified_user_sees_blue_tick_form_instead_of_ad_form(self):
        user = User.objects.create_user("host", "host@example.com", "pass-word-123")
        self.client.force_login(user)
        page = self.client.get("/ads/create/")
        self.assertContains(page, "برای درج آگهی رایگان باید تیک آبی اکانتتان را فعال کنید")
        self.assertContains(page, "ارسال درخواست تیک آبی")
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
        self.assertContains(again, "پس از بررسی طی 72 ساعت آینده با شما تماس حاصل خواهد شد")

    def test_verified_user_can_post_ad_and_admin_is_notified(self):
        user = User.objects.create_user("star", "star@example.com", "pass-word-123")
        user.club_profile.is_verified = True
        user.club_profile.save(update_fields=["is_verified"])
        self.client.force_login(user)
        created = self.client.post(
            "/ads/create/",
            {
                "event_name": "شب مافیا",
                "organizer_name": "علی",
                "address": "خیابان ولیعصر",
                "starts_at": "جمعه ۲۲:۰۰",
                "phone": "09121234567",
                "ticket_price": "۲۰۰ هزار تومان",
                "cafe_bank": "کافه شب",
                "image": _png_upload(),
            },
        )
        self.assertRedirects(created, "/ads/")
        listing = self.client.get("/ads/")
        self.assertContains(listing, "شب مافیا")
        self.assertContains(listing, "کافه شب")
        ad = EventAd.objects.get(event_name="شب مافیا")
        self.assertTrue(ad.is_published)
        self.assertTrue(ad.is_new)
        self.assertGreater(ad.expires_at, timezone.now() + timedelta(days=2))
        admin_user = User.objects.create_superuser("adadmin", "adadmin@example.com", "pass-word-123")
        self.client.force_login(admin_user)
        dashboard = self.client.get("/admin/")
        self.assertContains(dashboard, "آگهی جدید")
        board = self.client.get("/admin/banners/eventad/")
        self.assertContains(board, "شب مافیا")
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
                phone="09120000000",
                ticket_price="رایگان",
                cafe_bank="کافه",
                expires_at=now + timedelta(days=3),
            )
        self.client.force_login(user)
        blocked = self.client.post(
            "/ads/create/",
            {
                "event_name": "چهارم",
                "organizer_name": "علی",
                "address": "تهران",
                "starts_at": "۲۲:۰۰",
                "phone": "09120000000",
                "ticket_price": "رایگان",
                "cafe_bank": "کافه",
                "image": _png_upload("fourth.png"),
            },
        )
        self.assertEqual(blocked.status_code, 200)
        self.assertContains(blocked, "سقف سه آگهی رایگان در این ماه پر شده است")
        self.assertEqual(EventAd.objects.filter(user=user).count(), 3)

