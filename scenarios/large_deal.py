from scenarios.models import (
    KIND_WEREWOLF,
    SIDE_CITIZEN,
    SIDE_INDEPENDENT,
    SIDE_MAFIA,
    SIDE_VILLAGE,
    SIDE_WEREWOLF,
    Scenario,
)

WIZARD_KEY = "large_deal_wizard"
MIN_PLAYERS = 4
DEFAULT_PLAYERS = 18
MAX_PLAYERS = 80

SIDE_LABELS = {
    SIDE_MAFIA: "مافیا",
    SIDE_CITIZEN: "شهروند",
    SIDE_INDEPENDENT: "مستقل",
    SIDE_WEREWOLF: "گرگینه",
    SIDE_VILLAGE: "روستا",
}

COUNT_FIELDS = {
    SIDE_MAFIA: "mafia_count",
    SIDE_CITIZEN: "citizen_count",
    SIDE_INDEPENDENT: "independent_count",
    SIDE_WEREWOLF: "werewolf_count",
    SIDE_VILLAGE: "village_count",
}


def large_scenarios():
    return Scenario.objects.filter(is_large=True, owner__isnull=True, guest_key="").order_by("home_order", "id")


def read_int(value, minimum, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if minimum <= number <= maximum:
        return number
    return None


def side_steps(kind):
    if kind == KIND_WEREWOLF:
        return [SIDE_WEREWOLF, SIDE_VILLAGE, SIDE_INDEPENDENT]
    return [SIDE_MAFIA, SIDE_CITIZEN, SIDE_INDEPENDENT]


def next_side(kind, current):
    steps = side_steps(kind)
    if current not in steps:
        return steps[0]
    index = steps.index(current) + 1
    if index >= len(steps):
        return None
    return steps[index]


def catalog_for(scenario, side, extras):
    rows = list(scenario.catalog_roles.filter(side=side))
    names = {row.name for row in rows}
    items = [{"id": row.id, "name": row.name, "allows_quantity": row.allows_quantity, "custom": False} for row in rows]
    for name in extras.get(side, []):
        if name not in names:
            items.append({"id": 0, "name": name, "allows_quantity": False, "custom": True})
    return items


def selected_roles(request, catalog):
    picked = []
    posted = set(request.POST.getlist("role"))
    for item in catalog:
        key = item["name"]
        if key in posted:
            picked.append(item)
    return picked


def expand_payloads(draft, scenario):
    payloads = []
    extras = draft.get("extras") or {}
    by_name = {}
    for role in scenario.catalog_roles.all():
        by_name[(role.side, role.name)] = role
    for side in side_steps(scenario.large_kind):
        picks = draft.get("picks", {}).get(side) or []
        qtys = draft.get("qty", {}).get(side) or {}
        for name in picks:
            qty = int(qtys.get(name) or 1)
            source = by_name.get((side, name))
            description = source.description if source else ""
            for _ in range(max(1, qty)):
                payloads.append({"name": name, "side": side, "description": description})
    return payloads


def seed_large_scenarios():
    from scenarios.models import (
        KIND_ADVANCED,
        KIND_NIGHT,
        KIND_WEREWOLF,
        SIDE_CITIZEN,
        SIDE_INDEPENDENT,
        SIDE_MAFIA,
        SIDE_VILLAGE,
        SIDE_WEREWOLF,
        CatalogFinalCard,
        CatalogRole,
        Scenario,
    )

    packs = [
        {
            "kind": KIND_ADVANCED,
            "name": "پیشرفته",
            "roles": [
                (SIDE_MAFIA, "مافیای ساده", True),
                (SIDE_MAFIA, "پدرخوانده", False),
                (SIDE_MAFIA, "دکتر لکتر", False),
                (SIDE_CITIZEN, "شهروند ساده", True),
                (SIDE_CITIZEN, "دکتر", False),
                (SIDE_CITIZEN, "کارآگاه", False),
                (SIDE_INDEPENDENT, "قاتل زنجیره‌ای", False),
            ],
            "finals": [],
        },
        {
            "kind": KIND_NIGHT,
            "name": "شب مافیا",
            "roles": [
                (SIDE_MAFIA, "مافیا", False),
                (SIDE_MAFIA, "گادفادر", False),
                (SIDE_CITIZEN, "شهروند", False),
                (SIDE_CITIZEN, "اسنایپر", False),
                (SIDE_CITIZEN, "نگهبان", False),
                (SIDE_INDEPENDENT, "جوکر", False),
            ],
            "finals": ["سکوت", "افشا", "شلیک", "نجات"],
        },
        {
            "kind": KIND_WEREWOLF,
            "name": "گرگینه",
            "roles": [
                (SIDE_WEREWOLF, "گرگینه", False),
                (SIDE_WEREWOLF, "آلفا", False),
                (SIDE_VILLAGE, "روستایی", False),
                (SIDE_VILLAGE, "پیشگو", False),
                (SIDE_INDEPENDENT, "گرگ‌نما", False),
            ],
            "finals": [],
        },
    ]
    created = []
    for pack in packs:
        scenario = Scenario.objects.filter(
            is_large=True,
            large_kind=pack["kind"],
            owner__isnull=True,
            guest_key="",
        ).first()
        if not scenario:
            scenario = Scenario.objects.create(
                name=pack["name"],
                is_large=True,
                large_kind=pack["kind"],
                has_final_move=pack["kind"] == KIND_NIGHT,
                rulebook_title_fa=f"رول‌بوک {pack['name']}",
                rulebook_body_fa=f"<p>رول‌بوک سناریو {pack['name']} از پنل مدیریت قابل ویرایش است.</p>",
                rules_title_fa=f"قوانین {pack['name']}",
                rules_body_fa=f"<p>قوانین سناریو {pack['name']} از پنل مدیریت قابل ویرایش است.</p>",
            )
        if not scenario.catalog_roles.exists():
            CatalogRole.objects.bulk_create(
                [
                    CatalogRole(scenario=scenario, side=side, name=name, allows_quantity=qty, sort_order=index)
                    for index, (side, name, qty) in enumerate(pack["roles"])
                ]
            )
        if pack["finals"] and not scenario.catalog_finals.exists():
            CatalogFinalCard.objects.bulk_create(
                [
                    CatalogFinalCard(scenario=scenario, name=name, sort_order=index)
                    for index, name in enumerate(pack["finals"])
                ]
            )
        created.append(scenario)
    return created


def expand_finals(draft, scenario):
    names = draft.get("final_picks") or []
    if draft.get("final_all"):
        return [{"name": card.name, "description": card.description} for card in scenario.catalog_finals.all()]
    by_name = {card.name: card for card in scenario.catalog_finals.all()}
    cards = []
    for name in names:
        source = by_name.get(name)
        cards.append({"name": name, "description": source.description if source else ""})
    return cards
