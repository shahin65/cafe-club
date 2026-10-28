import random

from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.utils.encoding import iri_to_uri
from PIL import Image

from scenarios.dealing import create_deal, shuffled
from scenarios.models import CardBranding, FinalMoveCard, Role, Scenario, ScenarioComment, ScenarioSize


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
        hidden = make_complete_scenario(name="سناریو پنهان", featured=False)
        response = self.client.get("/")
        content = response.content.decode()
        self.assertLess(content.find("نصب اپلیکیشن"), content.find("quick-roles"))
        self.assertLess(content.find("quick-roles"), content.find("ad-rotator"))
        self.assertLess(content.find("ad-rotator"), content.find("favorite-scenarios"))
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
        self.assertNotContains(response, hidden.name)
        self.assertNotContains(response, "2 نفره")
        self.assertContains(response, f'href="/deal/{shown.id}/"')


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
        self.assertContains(response, "2 نفره")
        self.assertContains(response, "3 نفره")

    def test_deal_assigns_each_role_once_and_survives_return(self):
        scenario = make_complete_scenario()
        response = self.client.get(f"/deal/{scenario.id}/2/order/?fresh=1", follow=True)
        self.assertContains(response, "نفر شماره")
        self.assertContains(response, "Card-Background.webp")
        self.assertContains(response, "Logo.png")
        self.assertContains(response, "مدیریت بازی")
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
        self.assertContains(response, f'href="{iri_to_uri(scenario.get_rulebook_url())}"')
        self.assertContains(response, f'href="{iri_to_uri(scenario.get_rules_url())}"')
        self.assertNotContains(response, "Icon-Advertisement.png")
        self.assertNotContains(response, "Icon-Location.png")
        empty_rules = self.client.get(f"/scenario/{scenario.slug}/rules/")
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
        rulebook = self.client.get(f"/scenario/{scenario.slug}/rulebook/")
        self.assertContains(rulebook, "رول‌بوک بازپرس")
        self.assertContains(rulebook, "بازگشت به مدیریت بازی")
        self.assertContains(rulebook, "doc-back")
        self.assertContains(rulebook, 'rel="canonical"')
        self.assertContains(rulebook, 'hreflang="en"')
        self.assertContains(rulebook, 'name="description"')
        self.assertContains(rulebook, "application/ld+json")
        self.assertContains(rulebook, "Icon-Rules.png")
        self.assertContains(rulebook, "Icon-Search.png")
        english = self.client.get(f"/en/scenario/{scenario.slug}/rulebook/")
        self.assertContains(english, "Inspector rulebook")
        rules = self.client.get(f"/scenario/{scenario.slug}/rules/")
        self.assertContains(rules, "قوانین بازپرس")
        sitemap = self.client.get("/sitemap.xml")
        self.assertContains(sitemap, "/rulebook/")
        self.assertContains(sitemap, "/rules/")
        self.assertContains(sitemap, "/en/scenario/")
        robots = self.client.get("/robots.txt")
        self.assertContains(robots, "Sitemap:")
        self.assertContains(robots, "Disallow: /admin/")

    def test_comments_need_approval_and_can_be_replied_to(self):
        scenario = make_complete_scenario()
        hidden = ScenarioComment.objects.create(
            scenario=scenario,
            author_name="علی",
            body="این نظر هنوز نباید دیده شود.",
        )
        page = self.client.get(f"/scenario/{scenario.slug}/comments/")
        self.assertNotContains(page, "این نظر هنوز نباید دیده شود.")
        self.client.post(
            f"/scenario/{scenario.slug}/comments/",
            {"author_name": "سارا", "body": "نظر جدید برای تأیید"},
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
        approved = self.client.get(f"/scenario/{scenario.slug}/comments/")
        self.assertContains(approved, "این نظر هنوز نباید دیده شود.")
        self.assertContains(approved, "پاسخ رسمی میز")
        self.assertNotContains(approved, "نظر جدید برای تأیید")
        self.client.post(
            f"/scenario/{scenario.slug}/comments/",
            {"author_name": "نرگس", "body": "پاسخ بازیکن", "parent": hidden.id},
        )
        reply = ScenarioComment.objects.get(body="پاسخ بازیکن")
        self.assertEqual(reply.parent_id, hidden.id)
        self.assertFalse(reply.is_approved)

    def test_rulebook_keeps_safe_html_and_strips_scripts(self):
        scenario = make_complete_scenario()
        scenario.rulebook_body_fa = (
            '<p style="text-align:center"><strong>متن وسط</strong></p>'
            '<script>alert(1)</script><img src="javascript:alert(1)">'
        )
        scenario.save()
        scenario.refresh_from_db()
        page = self.client.get(f"/scenario/{scenario.slug}/rulebook/")
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
        self.assertEqual(self.client.get(f"/scenario/{scenario.slug}/rulebook/").status_code, 404)
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
        empty = self.client.get(f"/scenario/{scenario.slug}/rulebook/")
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
        self.assertRedirects(self.client.post("/settings/logo/", {"preset": "win"}), "/")
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
        self.client.force_login(user)
        buffer = BytesIO()
        Image.new("RGB", (8, 8), (10, 20, 30)).save(buffer, format="PNG")
        response = self.client.post(
            "/settings/logo/",
            {"logo": SimpleUploadedFile("cafe.png", buffer.getvalue(), content_type="image/png")},
        )
        self.assertRedirects(response, "/")
        self.assertTrue(CardBranding.objects.get(user=user).image)
        scenario = make_complete_scenario()
        finish_two_player_deal(self.client, scenario)
        card = self.client.get("/deal/final/1/")
        self.assertContains(card, "/media/card_logos/")
