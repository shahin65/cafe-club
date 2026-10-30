from django.db.models import Prefetch

from scenarios.models import Scenario, ScenarioSize

PIN_SESSION_KEY = "quick_home_ids"
MAX_HOME_SCENARIOS = 6


def official_queryset():
    return Scenario.objects.filter(owner__isnull=True, guest_key="", is_large=False).prefetch_related(
        Prefetch("sizes", queryset=ScenarioSize.objects.prefetch_related("roles", "final_move_cards"))
    )


def listed_official(queryset=None):
    return list(queryset or official_queryset())


def complete_official(queryset=None):
    return [scenario for scenario in listed_official(queryset) if scenario.is_complete()]


def get_pin_ids(request):
    ids = []
    if request.user.is_authenticated:
        profile = getattr(request.user, "club_profile", None)
        if profile and isinstance(profile.home_scenario_ids, list):
            ids = profile.home_scenario_ids
    if not ids:
        ids = request.session.get(PIN_SESSION_KEY) or []
    cleaned = []
    for value in ids:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number not in cleaned:
            cleaned.append(number)
        if len(cleaned) >= MAX_HOME_SCENARIOS:
            break
    return cleaned


def set_pin_ids(request, ids):
    cleaned = []
    for value in ids:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number not in cleaned:
            cleaned.append(number)
        if len(cleaned) >= MAX_HOME_SCENARIOS:
            break
    request.session[PIN_SESSION_KEY] = cleaned
    request.session.modified = True
    if request.user.is_authenticated:
        profile = getattr(request.user, "club_profile", None)
        if profile:
            profile.home_scenario_ids = cleaned
            profile.save(update_fields=["home_scenario_ids"])
    return cleaned


def toggle_pin(request, scenario_id):
    ids = get_pin_ids(request)
    if scenario_id in ids:
        ids = [item for item in ids if item != scenario_id]
        set_pin_ids(request, ids)
        return False, True
    if len(ids) >= MAX_HOME_SCENARIOS:
        return False, False
    ids.append(scenario_id)
    set_pin_ids(request, ids)
    return True, True


def shown_home_ids(request):
    return [scenario.id for scenario in home_quick_scenarios(request)[0]]


def remove_from_home(request, scenario_id):
    current = shown_home_ids(request)
    if scenario_id not in current:
        return False
    kept = [item for item in current if item != scenario_id]
    for scenario in listed_official():
        if scenario.id not in kept and scenario.id != scenario_id:
            kept.append(scenario.id)
        if len(kept) >= MAX_HOME_SCENARIOS:
            break
    set_pin_ids(request, kept)
    return True


def replace_home_scenario(request, add_id, remove_id):
    current = shown_home_ids(request)
    if add_id == remove_id:
        return False
    if add_id in current:
        return True
    if remove_id not in current:
        return False
    set_pin_ids(request, [add_id if item == remove_id else item for item in current])
    return True


def home_quick_scenarios(request):
    official = listed_official()
    by_id = {scenario.id: scenario for scenario in official}
    chosen = [by_id[item] for item in get_pin_ids(request) if item in by_id]
    seen = {item.id for item in chosen}
    for scenario in official:
        if scenario.is_featured and scenario.id not in seen:
            chosen.append(scenario)
            seen.add(scenario.id)
        if len(chosen) >= MAX_HOME_SCENARIOS:
            break
    if len(chosen) < MAX_HOME_SCENARIOS:
        for scenario in official:
            if scenario.id not in seen:
                chosen.append(scenario)
                seen.add(scenario.id)
            if len(chosen) >= MAX_HOME_SCENARIOS:
                break
    return chosen[:MAX_HOME_SCENARIOS], True
