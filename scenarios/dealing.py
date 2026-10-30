import random

from django.templatetags.static import static

SESSION_KEY = "role_deal"

MODE_ORDER = "order"
MODE_CHAIR = "chair"
MODE_RANDOM = "random"
MODES = (MODE_ORDER, MODE_CHAIR, MODE_RANDOM)

FATE_WORDS = {"life": "زندگی", "death": "مرگ"}
FINAL_CARD_IMAGE = "Card-Final-Move.webp"

CARD_IMAGES = {
    "citizen": "Card-Cityzen.webp",
    "village": "Card-Cityzen.webp",
    "mafia": "Card-Mafia.webp",
    "independent": "Card-Independent.webp",
    "werewolf": "Card-Werewolf.webp",
}


def shuffled(items, rng=None):
    """Fisher–Yates via Random.shuffle. Each item stays in the list once."""
    result = list(items)
    (rng or random.SystemRandom()).shuffle(result)
    return result


def create_large_deal(scenario, payloads, final_cards=None, mode=MODE_ORDER, rng=None):
    rng = rng or random.SystemRandom()
    roles = shuffled(list(payloads), rng)
    count = len(roles)
    announce = list(range(1, count + 1))
    if mode == MODE_CHAIR:
        announce = shuffled(announce, rng)
    finals = shuffled(list(final_cards or []), rng)
    return {
        "scenario_id": scenario.id,
        "player_count": count,
        "mode": mode if mode in MODES else MODE_ORDER,
        "large": True,
        "slots": roles,
        "announce": announce,
        "revealed": [False] * count,
        "final_slots": finals,
        "final_revealed": [False] * len(finals),
        "lottery_rounds": [],
        "role_payloads": payloads,
        "final_payloads": list(final_cards or []),
    }


def create_deal(size, mode, rng=None):
    rng = rng or random.SystemRandom()
    roles = shuffled(list(size.roles.all()), rng)
    count = size.player_count
    announce = list(range(1, count + 1))
    if mode == MODE_CHAIR:
        announce = shuffled(announce, rng)
    final_cards = shuffled(list(size.final_move_cards.all()), rng)
    return {
        "scenario_id": size.scenario_id,
        "player_count": count,
        "mode": mode,
        "slots": [role.id for role in roles],
        "announce": announce,
        "revealed": [False] * count,
        "final_slots": [card.id for card in final_cards],
        "final_revealed": [False] * len(final_cards),
        "lottery_rounds": [],
    }


def ensure_host_tools(deal, size):
    changed = False
    if deal.get("large"):
        if "lottery_rounds" not in deal:
            deal["lottery_rounds"] = []
            changed = True
        return changed
    if "final_slots" not in deal:
        cards = shuffled(list(size.final_move_cards.all()))
        deal["final_slots"] = [card.id for card in cards]
        deal["final_revealed"] = [False] * len(cards)
        changed = True
    if "lottery_rounds" not in deal:
        deal["lottery_rounds"] = []
        changed = True
    return changed


def new_lottery_round(rng=None):
    return {"outcomes": shuffled(["life", "death"], rng), "picked": None}


def same_deal(deal, scenario_id, player_count, mode):
    return bool(
        deal
        and deal.get("scenario_id") == scenario_id
        and deal.get("player_count") == player_count
        and deal.get("mode") == mode
        and len(deal.get("slots") or []) == player_count
        and len(deal.get("revealed") or []) == player_count
    )


def current_number(deal):
    for number in deal["announce"]:
        if not deal["revealed"][number - 1]:
            return number
    return None


def deal_is_active(deal):
    revealed = (deal or {}).get("revealed") or []
    return bool(revealed) and not all(revealed)


def card_static(side):
    return static(CARD_IMAGES[side])


def final_card_static():
    return static(FINAL_CARD_IMAGE)


def open_lottery(deal):
    rounds = deal.get("lottery_rounds") or []
    if rounds and rounds[-1].get("picked") is None:
        return rounds[-1]
    return None


def latest_lottery(deal):
    rounds = deal.get("lottery_rounds") or []
    return rounds[-1] if rounds else None
