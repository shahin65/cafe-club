import random

from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.utils.encoding import iri_to_uri
from PIL import Image

from banners.digits import persian_digits
from scenarios.dealing import create_deal, shuffled
from scenarios.large_deal import seed_large_scenarios
from scenarios.models import (
    KIND_ADVANCED,
    KIND_NIGHT,
    KIND_WEREWOLF,
    SIDE_CITIZEN,
    SIDE_MAFIA,
    SIDE_VILLAGE,
    SIDE_WEREWOLF,
    CardBranding,
    FinalMoveCard,
    Role,
    Scenario,
    ScenarioComment,
    ScenarioSize,
)


def make_complete_scenario(name="سناریو بازپرس", featured=False):
    scenario = Scenario.objects.create(
        name=name,
        has_final_move=True,
        has_death_lottery=True,
        is_featured=False,
    )
    size = ScenarioSize.objects.create(
        scenario=scenario,
        player_count=2,
        mafia_count=1,
        citizen_count=1,
        final_move_count=1,
    )
    Role.objects.create(size=size, side="mafia", name="رئیس مافیا")
    Role.objects.create(size=size, side="citizen", name="بازپرس")
    FinalMoveCard.objects.create(size=size, name="حرکت آخر", description="یک توضیح کوتاه")
    if featured:
        scenario.is_featured = True
        scenario.full_clean()
        scenario.save(update_fields=["is_featured"])
    return scenario


class ScenarioRulesTests(TestCase):
    def test_side_counts_must_equal_player_count(self):
        scenario = Scenario.objects.create(name="سناریو بازپرس")
        size = ScenarioSize(
            scenario=scenario,
            player_count=10,
            mafia_count=3,
            citizen_count=5,
            independent_count=1,
            werewolf_count=0,
        )
        self.assertFalse(size.counts_match_players())
        size.citizen_count = 6
        self.assertTrue(size.counts_match_players())

    def test_only_six_scenarios_can_be_featured(self):
        for index in range(6):
            make_complete_scenario(name=f"سناریو {index}", featured=True)
        extra = make_complete_scenario(name="سناریو اضافه")
        extra.is_featured = True
        with self.assertRaises(ValidationError):
            extra.full_clean()

    def test_featured_scenario_must_be_complete(self):
        scenario = Scenario.objects.create(name="ناقص")
        scenario.is_featured = True
        with self.assertRaises(ValidationError):
            scenario.full_clean()

    def test_home_shows_only_featured_scenarios_above_the_slider(self):
        shown = make_complete_scenario(name="سناریو بازپرس", featured=True)
        filler = make_complete_scenario(name="سناریو پنهان", featured=False)
        response = self.client.get("/")
        content = response.content.decode()
        self.assertLess(content.find("نصب اپلیکیشن"), content.find("quick-roles"))
        self.assertLess(content.find("quick-roles"), content.find("large-roles"))
        self.assertLess(content.find("large-roles"), content.find("ad-rotator"))
        self.assertContains(response, "تقسیم نقش سناریو تعداد بالا")
        self.assertContains(response, "Icon-Objective.png")
        self.assertLess(content.find("ad-rotator"), content.find("favorite-scenarios"))
        self.assertLess(content.find("favorite-scenarios"), content.find("tournament-home"))
        self.assertContains(response, "تورنومنت مافیا بساز و همینجا مدیریتش کن")
        self.assertContains(response, "Icon-Tournament.png")
        self.assertContains(response, "تقسیم نقش سریع")
        self.assertContains(response, "سناریو دلخواه من")
        self.assertContains(response, "Icon-Favorite.png")
        self.assertContains(response, "سناریو دلخواهتو بساز")
        self.assertContains(response, "Icon-Fast.png")
        self.assertContains(response, "quick-roles-gear")
        self.assertContains(response, "data-open-settings")
        self.assertContains(response, "Icon-Settings2.png")
        self.assertContains(response, "تغییر لوگو")
        self.assertContains(response, 'value="cafeclub"')
        self.assertContains(response, "Logo.png")
        self.assertContains(response, "Logo-Dun.png")
        self.assertContains(response, "Logo-Legendary.jpg")
        self.assertContains(response, "Logo-Win.jpg")
        self.assertContains(response, shown.name)
        self.assertContains(response, filler.name)
        self.assertNotContains(response, "2 نفره")
        self.assertContains(response, f'href="/deal/{shown.id}/"')
        self.assertContains(response, "مشاهده سایر سناریوها")
        self.assertContains(response, 'href="/scenarios/"')

    def test_home_more_lists_and_pins_scenarios(self):
        for index in range(6):
            make_complete_scenario(name=f"سناریو {index}", featured=True)
        extra = make_complete_scenario(name="سناریو هفتم", featured=False)
        home = self.client.get("/")
        self.assertContains(home, "مشاهده سایر سناریوها")
        self.assertContains(home, 'href="/scenarios/"')
        self.assertNotContains(home, "سناریو هفتم")
        catalog = self.client.get("/scenarios/", {"q": "هفتم"})
        self.assertContains(catalog, "سناریو هفتم")
        self.assertContains(catalog, "جستجو")
        self.assertContains(catalog, "مرتب‌سازی")
        self.assertContains(catalog, "places-bar-btn")
        self.assertContains(catalog, 'data-toggle-panel="search"')
        self.assertContains(catalog, 'data-toggle-panel="sort"')
        alpha = make_complete_scenario(name="آلفا")
        beta = make_complete_scenario(name="بتا")
        beta.play_count = 9
        beta.save(update_fields=["play_count"])
        newest = self.client.get("/scenarios/", {"sort": "newest"})
        self.assertLess(newest.content.decode().find("بتا"), newest.content.decode().find("آلفا"))
        popular = self.client.get("/scenarios/", {"sort": "popular"})
        self.assertLess(popular.content.decode().find("بتا"), popular.content.decode().find("آلفا"))
        named = self.client.get("/scenarios/", {"sort": "name"})
        self.assertLess(named.content.decode().find("آلفا"), named.content.decode().find("بتا"))
        mode = self.client.get(f"/deal/{extra.id}/", follow=True)
        self.assertNotContains(mode, "اضافه به صفحه اصلی")
        catalog_pin = self.client.get("/scenarios/", {"q": "هفتم"})
        self.assertContains(catalog_pin, "اضافه به صفحه اصلی")
        dropped = Scenario.objects.get(name="سناریو 0")
        pinned = self.client.post(
            "/scenarios/pin/replace/",
            {"add_id": extra.id, "remove_id": dropped.id, "next": "/"},
        )
        self.assertRedirects(pinned, "/")
        listed = self.client.get("/")
        self.assertContains(listed, "سناریو هفتم")
        self.assertNotContains(listed, persian_digits("سناریو 0"))

    def test_home_lists_official_admin_scenarios_even_if_roles_are_incomplete(self):
        make_complete_scenario(name="سناریو کامل", featured=True)
        incomplete = Scenario.objects.create(name="سناریو مذاکره", is_featured=True, home_order=2)
        ScenarioSize.objects.create(
            scenario=incomplete,
            player_count=10,
            mafia_count=3,
            citizen_count=7,
        )
        home = self.client.get("/")
        self.assertContains(home, "سناریو مذاکره")
        catalog = self.client.get("/scenarios/")
        self.assertContains(catalog, "سناریو مذاکره")
        self.assertContains(catalog, "Icon-Favorite.png")
        self.assertContains(catalog, "catalog-pin-btn")
        self.assertContains(catalog, "آیا قصد قرار دادن این سناریو در صفحه نخست را دارید")

    def test_scenario_icons_render_on_home_and_catalog(self):
        buffer = BytesIO()
        Image.new("RGB", (64, 64), (180, 40, 50)).save(buffer, format="PNG")
        scenario = make_complete_scenario(name="سناریو نشان‌دار", featured=True)
        scenario.icon.save(
            "badge.png",
            SimpleUploadedFile("badge.png", buffer.getvalue(), content_type="image/png"),
            save=True,
        )
        home = self.client.get("/")
        self.assertContains(home, scenario.icon.url)
        self.assertContains(home, "quick-role-icon")
        catalog = self.client.get("/scenarios/")
        self.assertContains(catalog, scenario.icon.url)
        self.assertContains(catalog, "scenario-icon")

    def test_pinning_more_than_six_is_blocked(self):
        extras = [make_complete_scenario(name=f"پین {index}") for index in range(7)]
        blocked = self.client.post(f"/scenarios/{extras[6].id}/pin/", {"next": "/"})
        self.assertRedirects(blocked, "/")
        home = self.client.get("/")
        self.assertNotContains(home, persian_digits(extras[6].name))
        replaced = self.client.post(
            "/scenarios/pin/replace/",
            {"add_id": extras[6].id, "remove_id": extras[0].id, "next": "/"},
        )
        self.assertRedirects(replaced, "/")
        home = self.client.get("/")
        self.assertContains(home, persian_digits(extras[6].name))
        self.assertNotContains(home, persian_digits(extras[0].name))


class RoleDealTests(TestCase):
    def test_shuffle_keeps_every_role_once_and_changes_order(self):
        roles = list(range(10))
        seen = set()
        for seed in range(40):
            result = shuffled(roles, random.Random(seed))
            self.assertCountEqual(result, roles)
            seen.add(tuple(result))
        self.assertGreater(len(seen), 1)

    def test_a_role_is_not_stuck_beside_the_same_neighbor(self):
        neighbors = set()
        for seed in range(60):
            order = shuffled(list(range(8)), random.Random(seed))
            index = order.index(0)
            if 0 < index < len(order) - 1:
                neighbors.add((order[index - 1], order[index + 1]))
        self.assertGreater(len(neighbors), 1)

    def test_single_player_count_skips_the_choice(self):
        scenario = make_complete_scenario()
        response = self.client.get(f"/deal/{scenario.id}/")
        self.assertRedirects(response, f"/deal/{scenario.id}/2/")

    def test_fresh_deal_counts_as_a_play(self):
        scenario = make_complete_scenario()
        self.client.get(f"/deal/{scenario.id}/2/random/?fresh=1")
        scenario.refresh_from_db()
        self.assertEqual(scenario.play_count, 1)
        self.client.get(f"/deal/{scenario.id}/2/random/")
        scenario.refresh_from_db()
        self.assertEqual(scenario.play_count, 1)

    def test_several_player_counts_are_offered(self):
        scenario = make_complete_scenario()
        size = ScenarioSize.objects.create(
            scenario=scenario,
            player_count=3,
            mafia_count=1,
            citizen_count=2,
        )
        Role.objects.create(size=size, side="mafia", name="مافیا")
        Role.objects.create(size=size, side="citizen", name="شهروند")
        Role.objects.create(size=size, side="citizen", name="دکتر")
        response = self.client.get(f"/deal/{scenario.id}/")
        self.assertContains(response, "۲ نفره")
        self.assertContains(response, "۳ نفره")

    def test_deal_assigns_each_role_once_and_survives_return(self):
        scenario = make_complete_scenario()
        response = self.client.get(f"/deal/{scenario.id}/2/order/?fresh=1", follow=True)
        self.assertContains(response, "نفر شماره")
        self.assertContains(response, "Card-Background.webp")
        self.assertContains(response, "Logo.png")
        self.assertContains(response, "مدیریت بازی")
        self.assertContains(response, "Icon-Home.png")
        self.assertContains(response, "Icon-Refresh.png")
        self.assertContains(response, "آیا از تقسیم نقش منصرف شدید؟")
        self.assertContains(response, "آیا قصد تقسیم نقش مجدد دارید؟")
        self.assertContains(response, "data-deal-play")
        self.assertNotContains(response, "Icon-Advertisement.png")
        self.assertNotContains(response, "Icon-Location.png")
        self.assertNotContains(response, "برای دیدن نقش، شماره را لمس کنید.")
        deal = self.client.session["role_deal"]
        role_ids = list(scenario.sizes.get(player_count=2).roles.values_list("id", flat=True))
        self.assertCountEqual(deal["slots"], role_ids)
        self.assertEqual(self.client.post("/deal/reveal/2/").status_code, 409)
        revealed = self.client.post("/deal/reveal/1/")
        self.assertEqual(revealed.status_code, 200)
        self.assertFalse(revealed.json()["done"])
        self.assertIn(revealed.json()["name"], ["رئیس مافیا", "بازپرس"])
        self.assertTrue(revealed.json()["card"].endswith(".webp"))
        slots = list(deal["slots"])
        self.client.get(f"/deal/{scenario.id}/2/order/")
        kept = self.client.session["role_deal"]
        self.assertEqual(kept["slots"], slots)
        self.assertTrue(kept["revealed"][0])
        skipped = self.client.get("/deal/card/1/")
        self.assertRedirects(skipped, "/deal/card/2/")

    def test_chair_order_is_a_permutation_of_the_seats(self):
        scenario = make_complete_scenario()
        size = scenario.sizes.get()
        orders = set()
        for seed in range(30):
            deal = create_deal(size, "chair", random.Random(seed))
            self.assertCountEqual(deal["announce"], [1, 2])
            self.assertCountEqual(deal["slots"], list(size.roles.values_list("id", flat=True)))
            orders.add(tuple(deal["announce"]))
        self.assertGreater(len(orders), 1)


def finish_two_player_deal(client, scenario):
    client.get(f"/deal/{scenario.id}/2/order/?fresh=1", follow=True)
    client.post("/deal/reveal/1/")
    client.post("/deal/reveal/2/")


class HostToolsTests(TestCase):
    def test_host_opens_only_after_the_last_role(self):
        scenario = make_complete_scenario()
        self.client.get(f"/deal/{scenario.id}/2/order/?fresh=1", follow=True)
        self.assertRedirects(self.client.get("/deal/host/"), "/")
        finish_two_player_deal(self.client, scenario)
        response = self.client.get("/deal/host/")
        self.assertContains(response, "مدیریت بازی")
        self.assertContains(response, "Icon-Endmove.png")
        self.assertContains(response, "Icon-Lot.png")
        self.assertContains(response, "Icon-Time.png")
        self.assertContains(response, "Icon-Alarm.png")
        self.assertContains(response, "Icon-music.png")
        self.assertNotContains(response, "Icon-Day.png")
        self.assertContains(response, "Icon-Night.png")
        self.assertContains(response, "پخش موسیقی")
        self.assertContains(response, "music-icon-play")
        self.assertContains(response, "music-icon-pause")
        self.assertNotContains(response, "فاز روز")
        self.assertContains(response, "فاز شب")
        self.assertContains(response, "نوبت گفتگو")
        self.assertContains(response, "نوبت چالش")
        self.assertContains(response, 'data-seconds="30"')
        self.assertContains(response, 'data-seconds="20"')
        self.assertContains(response, "Icon-Rules.png")
        self.assertContains(response, "Icon-Search.png")
        self.assertContains(response, "Icon-Comment.png")
        self.assertContains(response, "رول بوک")
        self.assertContains(response, "قوانین")
        self.assertContains(response, "نظر کاربران")
        self.assertContains(response, "تقسیم نقش مجدد")
        self.assertContains(response, 'href="/deal/restart/"')
        self.assertContains(response, "دفترچه یادداشت")
        self.assertContains(response, "Icon-List.png")
        self.assertContains(response, "host-sheet")
        self.assertContains(response, "places-frost")
        self.assertContains(response, "data-rename")
        self.assertContains(response, "music-player.js?v=7")
        self.assertContains(response, f'href="{iri_to_uri(scenario.get_rulebook_url())}"')
        self.assertContains(response, f'href="{iri_to_uri(scenario.get_rules_url())}"')
        self.assertNotContains(response, "Icon-Advertisement.png")
        self.assertNotContains(response, "Icon-Location.png")
        empty_rules = self.client.get(scenario.get_rules_url())
        self.assertContains(empty_rules, "این سناریو فاقد توضیحات میباشد")

    def test_host_hides_tools_the_scenario_does_not_have(self):
        scenario = make_complete_scenario()
        scenario.has_final_move = False
        scenario.has_death_lottery = False
        scenario.save(update_fields=["has_final_move", "has_death_lottery"])
        finish_two_player_deal(self.client, scenario)
        response = self.client.get("/deal/host/")
        self.assertNotContains(response, "Icon-Endmove.png")
        self.assertNotContains(response, "Icon-Lot.png")

    def test_final_move_cards_are_shuffled_once_and_then_checked_off(self):
        scenario = make_complete_scenario()
        size = scenario.sizes.get()
        FinalMoveCard.objects.create(size=size, name="کارت دوم", description="توضیح کوتاه")
        seen = set()
        for seed in range(20):
            deal = create_deal(size, "order", random.Random(seed))
            self.assertCountEqual(
                deal["final_slots"],
                list(size.final_move_cards.values_list("id", flat=True)),
            )
            seen.add(tuple(deal["final_slots"]))
        self.assertGreater(len(seen), 1)
        finish_two_player_deal(self.client, scenario)
        self.client.get("/deal/final/")
        revealed = self.client.post("/deal/final/reveal/1/")
        self.assertEqual(revealed.status_code, 200)
        self.assertTrue(revealed.json()["card"].endswith("Card-Final-Move.webp"))
        self.assertTrue(revealed.json()["description"])
        board = self.client.get("/deal/final/")
        self.assertContains(board, "is-done")

    def test_each_death_lottery_is_one_life_and_one_death(self):
        scenario = make_complete_scenario()
        finish_two_player_deal(self.client, scenario)
        self.client.post("/deal/lottery/")
        self.client.post("/deal/lottery/")
        rounds = self.client.session["role_deal"]["lottery_rounds"]
        self.assertEqual(len(rounds), 1)
        self.assertCountEqual(rounds[0]["outcomes"], ["life", "death"])
        first = self.client.post("/deal/lottery/reveal/0/")
        second = self.client.post("/deal/lottery/reveal/1/")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertIn(first.json()["word"], ["مرگ", "زندگی"])
        self.client.post("/deal/lottery/")
        self.assertEqual(len(self.client.session["role_deal"]["lottery_rounds"]), 2)


class ScenarioPagesAndCommentsTests(TestCase):
    def test_rulebook_and_rules_have_seo_and_language_alternates(self):
        scenario = make_complete_scenario()
        scenario.name_en = "Inspector"
        scenario.rulebook_title_fa = "رول‌بوک بازپرس"
        scenario.rulebook_body_fa = "معرفی کامل سناریو بازپرس برای گرداننده."
        scenario.rulebook_meta_description_fa = "رول‌بوک رسمی سناریو بازپرس کافه کلاب."
        scenario.rules_title_fa = "قوانین بازپرس"
        scenario.rules_body_fa = "قوانین میز بازپرس برای شب و روز."
        scenario.rulebook_title_en = "Inspector rulebook"
        scenario.rulebook_body_en = "The full inspector scenario guide for the host."
        scenario.save()
        rulebook = self.client.get(scenario.get_rulebook_url())
        self.assertContains(rulebook, "رول‌بوک بازپرس")
        self.assertContains(rulebook, "بازگشت به مدیریت بازی")
        self.assertContains(rulebook, "doc-back")
        self.assertContains(rulebook, 'rel="canonical"')
        self.assertContains(rulebook, 'hreflang="en"')
        self.assertContains(rulebook, 'name="description"')
        self.assertContains(rulebook, "application/ld+json")
        self.assertContains(rulebook, "Icon-Rules.png")
        self.assertContains(rulebook, "Icon-Search.png")
        english = self.client.get(f"/en/scenario/{scenario.pk}/rulebook/")
        self.assertContains(english, "Inspector rulebook")
        rules = self.client.get(scenario.get_rules_url())
        self.assertContains(rules, "قوانین بازپرس")
        sitemap = self.client.get("/sitemap.xml")
        self.assertContains(sitemap, f"/scenario/{scenario.pk}/rulebook/")
        self.assertContains(sitemap, "/rulebook/")
        self.assertContains(sitemap, "/rules/")
        self.assertContains(sitemap, "/en/scenario/")
        robots = self.client.get("/robots.txt")
        self.assertContains(robots, "Sitemap:")
        self.assertContains(robots, "Disallow: /admin/")
        self.assertTrue(scenario.slug.isascii())
        self.assertEqual(scenario.get_rulebook_url(), f"/scenario/{scenario.pk}/rulebook/")
        self.assertEqual(scenario.get_rules_url(), f"/scenario/{scenario.pk}/rules/")
        self.assertEqual(scenario.get_comments_url(), f"/scenario/{scenario.pk}/comments/")
        legacy = self.client.get(f"/scenario/{scenario.slug}/rulebook/")
        self.assertRedirects(legacy, scenario.get_rulebook_url())

    def test_comments_need_approval_and_can_be_replied_to(self):
        scenario = make_complete_scenario()
        hidden = ScenarioComment.objects.create(
            scenario=scenario,
            author_name="علی",
            body="این نظر هنوز نباید دیده شود.",
        )
        page = self.client.get(scenario.get_comments_url())
        self.assertNotContains(page, "این نظر هنوز نباید دیده شود.")
        self.assertContains(page, "جمع این دو عدد را بنویسید")
        captcha = self.client.session["venue_comment_captcha"]
        self.client.post(
            scenario.get_comments_url(),
            {"author_name": "سارا", "body": "نظر جدید برای تأیید", "captcha": str(captcha["left"] + captcha["right"])},
        )
        self.assertFalse(ScenarioComment.objects.get(body="نظر جدید برای تأیید").is_approved)
        hidden.is_approved = True
        hidden.save(update_fields=["is_approved"])
        ScenarioComment.objects.create(
            scenario=scenario,
            parent=hidden,
            author_name="مدیریت",
            body="پاسخ رسمی میز",
            is_approved=True,
            is_admin=True,
        )
        approved = self.client.get(scenario.get_comments_url())
        self.assertContains(approved, "این نظر هنوز نباید دیده شود.")
        self.assertContains(approved, "پاسخ رسمی میز")
        self.assertNotContains(approved, "نظر جدید برای تأیید")
        captcha = self.client.session["venue_comment_captcha"]
        self.client.post(
            scenario.get_comments_url(),
            {
                "author_name": "نرگس",
                "body": "پاسخ بازیکن",
                "parent": hidden.id,
                "captcha": str(captcha["left"] + captcha["right"]),
            },
        )
        reply = ScenarioComment.objects.get(body="پاسخ بازیکن")
        self.assertEqual(reply.parent_id, hidden.id)
        self.assertFalse(reply.is_approved)

    def test_logged_in_comment_uses_display_name_without_name_field(self):
        user = get_user_model().objects.create_user("commenter", "commenter@example.com", "pass-word-123")
        user.club_profile.display_name = "میزبان شب"
        user.club_profile.save(update_fields=["display_name"])
        scenario = make_complete_scenario()
        self.client.force_login(user)
        page = self.client.get(scenario.get_comments_url())
        self.assertNotContains(page, 'name="author_name"')
        self.assertContains(page, "میزبان شب")
        captcha = self.client.session["venue_comment_captcha"]
        posted = self.client.post(
            scenario.get_comments_url(),
            {
                "author_name": "نام جعلی",
                "body": "نظر با نام نمایشی",
                "captcha": str(captcha["left"] + captcha["right"]),
            },
            follow=True,
        )
        self.assertContains(posted, "نظر شما با موفقیت ثبت شد و پس از بازبینی در سایت منتشر می‌شود")
        comment = ScenarioComment.objects.get(body="نظر با نام نمایشی")
        self.assertEqual(comment.author_name, "میزبان شب")
        self.assertFalse(comment.is_approved)

    def test_rulebook_keeps_safe_html_and_strips_scripts(self):
        scenario = make_complete_scenario()
        scenario.rulebook_body_fa = (
            '<p style="text-align:center"><strong>متن وسط</strong></p>'
            '<script>alert(1)</script><img src="javascript:alert(1)">'
        )
        scenario.save()
        scenario.refresh_from_db()
        page = self.client.get(scenario.get_rulebook_url())
        self.assertContains(page, "<strong>متن وسط</strong>")
        self.assertContains(page, "text-align:center")
        self.assertNotContains(page, "javascript:alert")
        self.assertNotContains(page, "alert(1)")

    def test_page_image_upload_is_staff_only(self):
        buffer = BytesIO()
        Image.new("RGB", (4, 4), (20, 30, 40)).save(buffer, format="PNG")
        png = buffer.getvalue()
        forbidden = self.client.post(
            "/staff/scenario-page-image/",
            {"upload": SimpleUploadedFile("dot.png", png, content_type="image/png")},
        )
        self.assertEqual(forbidden.status_code, 302)
        user = get_user_model().objects.create_superuser("host", "host@example.com", "pass-word-123")
        self.client.force_login(user)
        uploaded = self.client.post(
            "/staff/scenario-page-image/",
            {"upload": SimpleUploadedFile("dot.png", png, content_type="image/png")},
        )
        self.assertEqual(uploaded.status_code, 200)
        self.assertEqual(uploaded.json()["uploaded"], 1)
        self.assertIn("/media/scenario_pages/", uploaded.json()["url"])


class CustomScenarioTests(TestCase):
    def test_custom_wizard_is_private_and_plays_without_rulebook_tabs(self):
        owner = get_user_model().objects.create_user("host", "host@example.com", "pass-word-123")
        stranger = get_user_model().objects.create_user("guest", "guest@example.com", "pass-word-123")
        home = self.client.get("/")
        self.assertContains(home, "سناریو دلخواهتو بساز")
        self.assertContains(home, 'href="/my-scenarios/create/?fresh=1"')
        create = self.client.get("/my-scenarios/create/")
        self.assertEqual(create.status_code, 200)
        self.client.force_login(owner)
        self.client.get("/my-scenarios/create/?fresh=1")
        self.assertRedirects(self.client.post("/my-scenarios/create/", {"name": "شب خصوصی"}), "/my-scenarios/create/mafia/")
        self.assertRedirects(self.client.post("/my-scenarios/create/mafia/", {"count": "1"}), "/my-scenarios/create/mafia/roles/")
        self.assertRedirects(self.client.post("/my-scenarios/create/mafia/roles/", {"name_0": "پدرخوانده"}), "/my-scenarios/create/citizens/")
        self.assertRedirects(self.client.post("/my-scenarios/create/citizens/", {"count": "1"}), "/my-scenarios/create/citizens/roles/")
        self.assertRedirects(self.client.post("/my-scenarios/create/citizens/roles/", {"name_0": "شهروند"}), "/my-scenarios/create/extras/")
        self.assertRedirects(self.client.post("/my-scenarios/create/extras/", {}), "/my-scenarios/create/tools/")
        done = self.client.post("/my-scenarios/create/tools/", {})
        self.assertRedirects(done, "/")
        scenario = Scenario.objects.get(name="شب خصوصی")
        self.assertEqual(scenario.owner, owner)
        self.assertFalse(scenario.is_featured)
        listed = self.client.get("/")
        self.assertContains(listed, "شب خصوصی")
        self.assertContains(listed, "favorite-edit")
        self.assertContains(listed, f'href="/deal/{scenario.id}/"')
        self.assertContains(listed, f'href="/my-scenarios/{scenario.id}/edit/"')
        self.assertNotContains(listed, ">ویرایش</a>")
        self.client.logout()
        hidden = self.client.get("/")
        self.assertNotContains(hidden, "شب خصوصی")
        self.assertEqual(self.client.get(f"/deal/{scenario.id}/").status_code, 404)
        self.assertEqual(self.client.get(scenario.get_rulebook_url()).status_code, 404)
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(f"/deal/{scenario.id}/").status_code, 404)
        self.assertNotContains(self.client.get("/"), "شب خصوصی")
        self.client.force_login(owner)
        finish_two_player_deal(self.client, scenario)
        host = self.client.get("/deal/host/")
        self.assertContains(host, "مدیریت بازی")
        self.assertContains(host, "Icon-Home.png")
        self.assertContains(host, "Icon-Rules.png")
        self.assertContains(host, "Icon-Search.png")
        self.assertNotContains(host, "Icon-Comment.png")
        self.assertContains(host, "رول بوک")
        self.assertContains(host, "قوانین")
        self.assertContains(host, f'href="{iri_to_uri(scenario.get_rulebook_url())}"')
        self.assertContains(host, f'href="{iri_to_uri(scenario.get_rules_url())}"')
        self.assertNotContains(host, "نظر کاربران")
        empty = self.client.get(scenario.get_rulebook_url())
        self.assertContains(empty, "این سناریو فاقد توضیحات میباشد")

    def test_guest_can_create_custom_scenario_without_login(self):
        self.client.get("/my-scenarios/create/?fresh=1")
        self.assertRedirects(self.client.post("/my-scenarios/create/", {"name": "شب مهمان"}), "/my-scenarios/create/mafia/")
        self.assertRedirects(self.client.post("/my-scenarios/create/mafia/", {"count": "1"}), "/my-scenarios/create/mafia/roles/")
        self.assertRedirects(self.client.post("/my-scenarios/create/mafia/roles/", {"name_0": "پدرخوانده"}), "/my-scenarios/create/citizens/")
        self.assertRedirects(self.client.post("/my-scenarios/create/citizens/", {"count": "1"}), "/my-scenarios/create/citizens/roles/")
        self.assertRedirects(self.client.post("/my-scenarios/create/citizens/roles/", {"name_0": "شهروند"}), "/my-scenarios/create/extras/")
        self.assertRedirects(self.client.post("/my-scenarios/create/extras/", {}), "/my-scenarios/create/tools/")
        self.assertRedirects(self.client.post("/my-scenarios/create/tools/", {}), "/")
        scenario = Scenario.objects.get(name="شب مهمان")
        self.assertIsNone(scenario.owner_id)
        self.assertTrue(scenario.guest_key)
        listed = self.client.get("/")
        self.assertContains(listed, "شب مهمان")
        self.assertContains(listed, f'href="/deal/{scenario.id}/"')
        stranger = Client()
        self.assertNotContains(stranger.get("/"), "شب مهمان")
        self.assertEqual(stranger.get(f"/deal/{scenario.id}/").status_code, 404)

    def test_mafia_and_citizen_counts_can_be_zero(self):
        owner = get_user_model().objects.create_user("wolf", "wolf@example.com", "pass-word-123")
        self.client.force_login(owner)
        self.client.get("/my-scenarios/create/?fresh=1")
        self.client.post("/my-scenarios/create/", {"name": "فقط گرگینه"})
        self.assertRedirects(self.client.post("/my-scenarios/create/mafia/", {"count": "0"}), "/my-scenarios/create/citizens/")
        self.assertRedirects(self.client.post("/my-scenarios/create/citizens/", {"count": "0"}), "/my-scenarios/create/extras/")
        extras = self.client.post("/my-scenarios/create/extras/", {})
        self.assertContains(extras, "اگر مافیا و شهروند صفر است")
        self.assertRedirects(self.client.post("/my-scenarios/create/extras/", {"has_werewolf": "1"}), "/my-scenarios/create/werewolf/")
        self.assertRedirects(self.client.post("/my-scenarios/create/werewolf/", {"count": "2"}), "/my-scenarios/create/werewolf/roles/")
        self.assertRedirects(
            self.client.post("/my-scenarios/create/werewolf/roles/", {"name_0": "گرگ", "name_1": "آلفا"}),
            "/my-scenarios/create/tools/",
        )
        self.assertRedirects(self.client.post("/my-scenarios/create/tools/", {}), "/")
        scenario = Scenario.objects.get(name="فقط گرگینه")
        size = scenario.sizes.get()
        self.assertEqual(size.mafia_count, 0)
        self.assertEqual(size.citizen_count, 0)
        self.assertEqual(size.werewolf_count, 2)
        self.assertEqual(size.player_count, 2)


class CardLogoTests(TestCase):
    def test_preset_logo_is_used_on_final_move_card_back(self):
        scenario = make_complete_scenario()
        self.assertRedirects(self.client.post("/settings/logo/", {"preset": "win"}), "/?logo=1")
        finish_two_player_deal(self.client, scenario)
        card = self.client.get("/deal/final/1/")
        self.assertContains(card, "Logo-Win.jpg")
        self.assertContains(card, "card-back-logo")
        role = self.client.get("/deal/card/1/")
        self.assertContains(role, "Logo-Win.jpg")

    def test_random_board_uses_card_back_and_opens_the_role(self):
        scenario = make_complete_scenario()
        board = self.client.get(f"/deal/{scenario.id}/2/random/?fresh=1")
        self.assertContains(board, "Card-Background.webp")
        self.assertContains(board, "mystery-card-back")
        self.assertNotContains(board, ">؟</a>")
        card = self.client.get("/deal/card/1/")
        self.assertContains(card, "is-instant")
        self.assertContains(card, 'class="card-hint" hidden')

    def test_uploaded_logo_is_kept_for_the_logged_in_user(self):
        user = get_user_model().objects.create_user("brand", "brand@example.com", "pass-word-123")
        user.club_profile.is_verified = True
        user.club_profile.save(update_fields=["is_verified"])
        self.client.force_login(user)
        buffer = BytesIO()
        Image.new("RGB", (8, 8), (10, 20, 30)).save(buffer, format="PNG")
        response = self.client.post(
            "/settings/logo/",
            {"logo": SimpleUploadedFile("cafe.png", buffer.getvalue(), content_type="image/png")},
        )
        self.assertRedirects(response, "/?logo=1")
        self.assertTrue(CardBranding.objects.get(user=user).image)
        home = self.client.get("/")
        self.assertContains(home, "/media/card_logos/")
        self.assertContains(home, "لوگوی من")
        self.assertContains(home, 'name="preset" value="custom"')
        self.assertContains(home, "is-selected")
        self.client.post("/settings/logo/", {"preset": "win"})
        branding = CardBranding.objects.get(user=user)
        self.assertTrue(branding.image)
        self.assertEqual(branding.preset, "win")
        listed = self.client.get("/")
        self.assertContains(listed, "لوگوی من")
        self.assertContains(listed, "Logo-Win.jpg")
        self.client.post("/settings/logo/", {"preset": "custom"})
        branding.refresh_from_db()
        self.assertEqual(branding.preset, "")
        scenario = make_complete_scenario()
        finish_two_player_deal(self.client, scenario)
        card = self.client.get("/deal/final/1/")
        self.assertContains(card, "/media/card_logos/")

    def test_unverified_user_cannot_upload_cafe_logo(self):
        user = get_user_model().objects.create_user("plain", "plain@example.com", "pass-word-123")
        self.client.force_login(user)
        buffer = BytesIO()
        Image.new("RGB", (8, 8), (10, 20, 30)).save(buffer, format="PNG")
        self.client.post(
            "/settings/logo/",
            {"logo": SimpleUploadedFile("cafe.png", buffer.getvalue(), content_type="image/png")},
        )
        self.assertFalse(CardBranding.objects.filter(user=user).exists())


class ScenarioAdminTests(TestCase):
    def test_role_names_and_descriptions_are_on_the_scenario_form(self):
        user = get_user_model().objects.create_superuser("host", "host@example.com", "pass-word-123")
        self.client.force_login(user)
        add = self.client.get("/admin/scenarios/scenario/add/")
        self.assertContains(add, "اسم نقش")
        self.assertContains(add, "توضیح نقش")
        self.assertContains(add, "sizes-0-roles-0-name")
        self.assertContains(add, "sizes-0-roles-0-description")
        self.assertContains(add, "sizes-0-roles-19-name")
        self.assertContains(add, "sizes-0-finals-11-name")
        self.assertContains(add, "اسم کارت")
        self.assertNotContains(add, "sizes-0-finals-0-sort_order")
        self.assertNotContains(add, "عنوان سئو")
        self.assertNotContains(add, "توضیح سئو")
        posted = self.client.post(
            "/admin/scenarios/scenario/add/",
            {
                "name": "سناریو میز ادمین",
                "home_order": "0",
                "sizes-TOTAL_FORMS": "1",
                "sizes-INITIAL_FORMS": "0",
                "sizes-MIN_NUM_FORMS": "0",
                "sizes-MAX_NUM_FORMS": "5",
                "sizes-0-player_count": "2",
                "sizes-0-mafia_count": "1",
                "sizes-0-citizen_count": "1",
                "sizes-0-independent_count": "0",
                "sizes-0-werewolf_count": "0",
                "sizes-0-roles-TOTAL_FORMS": "2",
                "sizes-0-roles-INITIAL_FORMS": "0",
                "sizes-0-roles-MIN_NUM_FORMS": "0",
                "sizes-0-roles-MAX_NUM_FORMS": "20",
                "sizes-0-roles-0-side": "mafia",
                "sizes-0-roles-0-name": "پدرخوانده",
                "sizes-0-roles-0-description": "رئیس میز شب",
                "sizes-0-roles-1-side": "citizen",
                "sizes-0-roles-1-name": "دکتر",
                "sizes-0-roles-1-description": "یک نفر را نجات می‌دهد",
                "sizes-0-finals-TOTAL_FORMS": "0",
                "sizes-0-finals-INITIAL_FORMS": "0",
                "sizes-0-finals-MIN_NUM_FORMS": "0",
                "sizes-0-finals-MAX_NUM_FORMS": "12",
            },
        )
        self.assertEqual(posted.status_code, 302)
        scenario = Scenario.objects.get(name="سناریو میز ادمین")
        roles = list(scenario.sizes.get().roles.order_by("id"))
        self.assertEqual([role.name for role in roles], ["پدرخوانده", "دکتر"])
        self.assertEqual(roles[0].description, "رئیس میز شب")
        change = self.client.get(f"/admin/scenarios/scenario/{scenario.pk}/change/")
        self.assertContains(change, "پدرخوانده")
        self.assertContains(change, "رئیس میز شب")

    def test_admin_can_reply_to_a_user_comment(self):
        user = get_user_model().objects.create_superuser("mod", "mod@example.com", "pass-word-123")
        self.client.force_login(user)
        scenario = make_complete_scenario()
        comment = ScenarioComment.objects.create(
            scenario=scenario,
            author_name="شاهین",
            body="این سناریو بالانس است؟",
        )
        form = self.client.get(f"/admin/scenarios/scenariocomment/{comment.pk}/change/")
        self.assertContains(form, "پاسخ مدیریت")
        self.assertContains(form, "متن پاسخ مدیریت")
        saved = self.client.post(
            f"/admin/scenarios/scenariocomment/{comment.pk}/change/",
            {
                "scenario": str(scenario.pk),
                "author_name": "شاهین",
                "body": "این سناریو بالانس است؟",
                "admin_reply": "بله، این نسخه برای میز ده‌نفره بالانس شده است.",
                "_save": "ذخیره",
            },
        )
        self.assertEqual(saved.status_code, 302)
        comment.refresh_from_db()
        self.assertTrue(comment.is_approved)
        reply = comment.replies.get()
        self.assertTrue(reply.is_admin)
        self.assertTrue(reply.is_approved)
        self.assertEqual(reply.author_name, "مدیریت")
        page = self.client.get(scenario.get_comments_url())
        self.assertContains(page, "این سناریو بالانس است؟")
        self.assertContains(page, "بله، این نسخه برای میز ده‌نفره بالانس شده است.")


class LargeScenarioDealTests(TestCase):
    def setUp(self):
        self.packs = {item.large_kind: item for item in seed_large_scenarios()}

    def test_home_lists_the_three_large_scenarios(self):
        page = self.client.get("/")
        self.assertContains(page, "پیشرفته")
        self.assertContains(page, "شب مافیا")
        self.assertContains(page, "گرگینه")
        self.assertContains(page, f'href="/large/{self.packs[KIND_ADVANCED].id}/?fresh=1"')

    def test_admin_can_edit_catalog_roles_and_night_cards(self):
        user = get_user_model().objects.create_superuser("host", "host@example.com", "pass-word-123")
        self.client.force_login(user)
        advanced = self.packs[KIND_ADVANCED]
        form = self.client.get(f"/admin/scenarios/scenario/{advanced.pk}/change/")
        self.assertContains(form, 'id="catalog_roles-group"')
        self.assertContains(form, "تعدادپذیر")
        self.assertContains(form, 'id="id_icon"')
        night = self.packs[KIND_NIGHT]
        night_form = self.client.get(f"/admin/scenarios/scenario/{night.pk}/change/")
        self.assertContains(night_form, 'id="catalog_finals-group"')

    def test_advanced_wizard_asks_quantity_and_opens_host(self):
        scenario = self.packs[KIND_ADVANCED]
        mismatch = self.client.post(
            f"/large/{scenario.id}/",
            {"player_count": "8", "mafia_count": "3", "citizen_count": "4", "independent_count": "0"},
        )
        self.assertContains(mismatch, "جمع تعداد سایدها باید با تعداد بازیکن یکی باشد")
        start = self.client.post(
            f"/large/{scenario.id}/",
            {"player_count": "8", "mafia_count": "3", "citizen_count": "4", "independent_count": "1"},
        )
        self.assertEqual(start.status_code, 302)
        self.assertIn("/roles/", start.url)
        self.client.post(
            f"/large/{scenario.id}/roles/",
            {"side": SIDE_MAFIA, "role": ["مافیای ساده", "پدرخوانده"]},
        )
        qty = self.client.post(f"/large/{scenario.id}/qty/?side=mafia", {"qty_0": "2", "side": SIDE_MAFIA})
        self.assertEqual(qty.status_code, 302)
        self.client.post(
            f"/large/{scenario.id}/roles/",
            {"side": SIDE_CITIZEN, "role": ["شهروند ساده", "دکتر"]},
        )
        self.client.post(f"/large/{scenario.id}/qty/?side=citizen", {"qty_0": "3", "side": SIDE_CITIZEN})
        self.client.post(
            f"/large/{scenario.id}/roles/",
            {"side": "independent", "role": ["قاتل زنجیره‌ای"]},
        )
        mode = self.client.get(f"/large/{scenario.id}/mode/")
        self.assertContains(mode, "به ترتیب نفرات")
        self.assertContains(mode, "به ترتیب صندلی")
        self.assertContains(mode, "تصادفی")
        play = self.client.get(f"/large/{scenario.id}/play/order/?fresh=1")
        self.assertRedirects(play, "/deal/card/1/")
        card = self.client.get("/deal/card/1/")
        self.assertContains(card, "نفر شماره")
        revealed = self.client.post("/deal/reveal/1/")
        self.assertEqual(revealed.status_code, 200)
        self.assertIn("name", revealed.json())

    def test_night_mafia_selects_all_final_cards(self):
        scenario = self.packs[KIND_NIGHT]
        self.client.post(
            f"/large/{scenario.id}/",
            {"player_count": "6", "mafia_count": "2", "citizen_count": "3", "independent_count": "1"},
        )
        self.client.post(f"/large/{scenario.id}/roles/", {"side": SIDE_MAFIA, "role": ["مافیا", "گادفادر"]})
        self.client.post(
            f"/large/{scenario.id}/roles/",
            {"side": SIDE_CITIZEN, "role": ["شهروند", "اسنایپر", "نگهبان"]},
        )
        add = self.client.post(
            f"/large/{scenario.id}/roles/",
            {"side": "independent", "add_role": "1", "new_role": "نقش سفارشی شب", "role": ["جوکر"]},
        )
        self.assertEqual(add.status_code, 302)
        kept = self.client.get(f"/large/{scenario.id}/roles/?side=independent")
        self.assertContains(kept, 'value="جوکر"')
        self.assertContains(kept, 'value="نقش سفارشی شب"')
        self.assertContains(kept, 'checked')
        self.client.post(f"/large/{scenario.id}/roles/", {"side": "independent", "role": ["نقش سفارشی شب"]})
        finals = self.client.post(f"/large/{scenario.id}/final/", {"select_all": "1"})
        self.assertEqual(finals.status_code, 302)
        self.assertIn("/mode/", finals.url)
        self.client.get(f"/large/{scenario.id}/play/random/?fresh=1")
        deal = self.client.session["role_deal"]
        deal["revealed"] = [True] * deal["player_count"]
        session = self.client.session
        session["role_deal"] = deal
        session.save()
        host = self.client.get("/deal/host/")
        self.assertContains(host, "حرکت آخر")
        board = self.client.get("/deal/final/")
        self.assertContains(board, "/deal/final/1/")
        self.assertEqual(len(self.client.session["role_deal"]["final_slots"]), 4)

    def test_werewolf_asks_village_sides(self):
        scenario = self.packs[KIND_WEREWOLF]
        start = self.client.get(f"/large/{scenario.id}/")
        self.assertContains(start, "تعداد بازیکن")
        self.assertContains(start, "گرگینه")
        self.assertContains(start, "روستا")
        self.assertContains(start, "count-stepper")
        self.assertContains(start, "data-count-step")
        counts = self.client.post(
            f"/large/{scenario.id}/",
            {"player_count": "5", "werewolf_count": "2", "village_count": "2", "independent_count": "1"},
        )
        self.assertEqual(counts.status_code, 302)
        self.client.post(f"/large/{scenario.id}/roles/", {"side": SIDE_WEREWOLF, "role": ["گرگینه", "آلفا"]})
        village = self.client.get(f"/large/{scenario.id}/roles/?side={SIDE_VILLAGE}")
        self.assertContains(village, "روستا")
        self.client.post(f"/large/{scenario.id}/roles/", {"side": SIDE_VILLAGE, "role": ["روستایی", "پیشگو"]})
        self.client.post(f"/large/{scenario.id}/roles/", {"side": "independent", "role": ["گرگ‌نما"]})
        mode = self.client.get(f"/large/{scenario.id}/mode/")
        self.assertContains(mode, "تصادفی")
        self.client.get(f"/large/{scenario.id}/play/random/?fresh=1")
        board = self.client.get(f"/large/{scenario.id}/play/random/")
        self.assertContains(board, "روی کادر دلخواه بزنید")
        deal = self.client.session["role_deal"]
        deal["revealed"] = [True] * deal["player_count"]
        session = self.client.session
        session["role_deal"] = deal
        session.save()
        host = self.client.get("/deal/host/")
        self.assertContains(host, "گرگینه")
        self.assertNotContains(host, "حرکت آخر")
