import random

from django.core.exceptions import ValidationError
from django.test import TestCase

from scenarios.dealing import create_deal, shuffled
from scenarios.models import FinalMoveCard, Role, Scenario, ScenarioSize


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
        self.assertLess(content.find("quick-roles"), content.find("ad-rotator"))
        self.assertContains(response, "تقسیم نقش سریع")
        self.assertContains(response, "Icon-Fast.png")
        self.assertContains(response, "quick-roles-gear")
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
        self.assertContains(response, "پخش موسیقی")
        self.assertContains(response, "نوبت گفتگو")
        self.assertContains(response, "نوبت چالش")
        self.assertContains(response, 'data-seconds="30"')
        self.assertContains(response, 'data-seconds="20"')

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
