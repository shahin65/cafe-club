from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from scenarios.dealing import MODES, SESSION_KEY, create_large_deal, current_number, same_deal
from scenarios.large_deal import (
    COUNT_FIELDS,
    DEFAULT_PLAYERS,
    MAX_PLAYERS,
    MIN_PLAYERS,
    SIDE_LABELS,
    WIZARD_KEY,
    catalog_for,
    expand_finals,
    expand_payloads,
    next_side,
    read_int,
    selected_roles,
    side_steps,
)
from scenarios.models import KIND_NIGHT, Scenario


def _scenario(scenario_id):
    scenario = get_object_or_404(Scenario, pk=scenario_id, is_large=True)
    if scenario.is_custom():
        raise Http404
    return scenario


def _draft(request):
    return request.session.get(WIZARD_KEY) or {}


def _save(request, data):
    request.session[WIZARD_KEY] = data
    request.session.modified = True


def _clear(request):
    request.session.pop(WIZARD_KEY, None)


def _bind(request, scenario):
    draft = _draft(request)
    if draft.get("scenario_id") != scenario.id:
        draft = {"scenario_id": scenario.id, "extras": {}, "picks": {}, "qty": {}}
        _save(request, draft)
    draft.setdefault("extras", {})
    draft.setdefault("picks", {})
    draft.setdefault("qty", {})
    return draft


def reverse_roles(scenario_id):
    return reverse("large_roles", kwargs={"scenario_id": scenario_id})


def reverse_qty(scenario_id):
    return reverse("large_qty", kwargs={"scenario_id": scenario_id})


def _first_role_side(scenario, draft):
    for side in side_steps(scenario.large_kind):
        if (draft.get(COUNT_FIELDS[side]) or 0) > 0:
            return side
    return None


def _next_role_side(scenario, draft, current):
    nxt = next_side(scenario.large_kind, current)
    while nxt:
        if (draft.get(COUNT_FIELDS[nxt]) or 0) > 0:
            return nxt
        nxt = next_side(scenario.large_kind, nxt)
    return None


def _after_side(request, scenario, draft, side):
    nxt = _next_role_side(scenario, draft, side)
    if nxt:
        return redirect(f"{reverse_roles(scenario.id)}?side={nxt}")
    if scenario.large_kind == KIND_NIGHT:
        return redirect("large_final", scenario_id=scenario.id)
    return redirect("large_mode", scenario_id=scenario.id)


def _count_rows(scenario, draft):
    rows = [
        {
            "field": "player_count",
            "label": _("تعداد بازیکن"),
            "min": MIN_PLAYERS,
            "max": MAX_PLAYERS,
            "value": draft.get("player_count", DEFAULT_PLAYERS),
        }
    ]
    for side in side_steps(scenario.large_kind):
        rows.append(
            {
                "field": COUNT_FIELDS[side],
                "label": _("تعداد %(side)s") % {"side": SIDE_LABELS[side]},
                "min": 0,
                "max": MAX_PLAYERS,
                "value": draft.get(COUNT_FIELDS[side], 0),
            }
        )
    return rows


@require_http_methods(["GET", "POST"])
def start(request, scenario_id):
    scenario = _scenario(scenario_id)
    if request.GET.get("fresh"):
        _clear(request)
    draft = _bind(request, scenario)
    error = ""
    if request.method == "POST":
        player_count = read_int(request.POST.get("player_count"), MIN_PLAYERS, MAX_PLAYERS)
        if player_count is None:
            error = _("تعداد بازیکن را درست وارد کنید.")
        else:
            sides = {}
            total = 0
            for side in side_steps(scenario.large_kind):
                field = COUNT_FIELDS[side]
                value = read_int(request.POST.get(field), 0, player_count)
                if value is None:
                    error = _("تعداد هر ساید را درست وارد کنید. صفر هم مجاز است.")
                    break
                sides[field] = value
                total += value
            if not error and total != player_count:
                error = _("جمع تعداد سایدها باید با تعداد بازیکن یکی باشد.")
            elif not error:
                draft["player_count"] = player_count
                draft.update(sides)
                for side in side_steps(scenario.large_kind):
                    if sides[COUNT_FIELDS[side]] == 0:
                        draft.setdefault("picks", {})[side] = []
                _save(request, draft)
                first = _first_role_side(scenario, draft)
                if first:
                    return redirect(f"{reverse_roles(scenario.id)}?side={first}")
                if scenario.large_kind == KIND_NIGHT:
                    return redirect("large_final", scenario_id=scenario.id)
                return redirect("large_mode", scenario_id=scenario.id)
    return render(
        request,
        "scenarios/large_wizard.html",
        {
            "scenario": scenario,
            "title": _("تعداد بازیکن و سایدها"),
            "hint": _("تعداد کل و تعداد هر ساید را بنویسید. صفر برای ساید خالی مجاز است."),
            "mode": "counts",
            "fields": _count_rows(scenario, draft),
            "error": error,
        },
    )


@require_http_methods(["GET", "POST"])
def side_count(request, scenario_id):
    return redirect("large_start", scenario_id=scenario_id)


@require_http_methods(["GET", "POST"])
def roles(request, scenario_id):
    scenario = _scenario(scenario_id)
    draft = _bind(request, scenario)
    if not draft.get("player_count"):
        return redirect("large_start", scenario_id=scenario.id)
    side = request.GET.get("side") or request.POST.get("side") or _first_role_side(scenario, draft)
    if side not in side_steps(scenario.large_kind):
        raise Http404
    needed = draft.get(COUNT_FIELDS[side])
    if needed is None:
        return redirect("large_start", scenario_id=scenario.id)
    if needed == 0:
        return _after_side(request, scenario, draft, side)
    extras = draft.get("extras") or {}
    catalog = catalog_for(scenario, side, extras)
    error = ""
    if request.method == "POST":
        posted = selected_roles(request, catalog_for(scenario, side, extras))
        names = [item["name"] for item in posted]
        if request.POST.get("add_role"):
            name = (request.POST.get("new_role") or "").strip()[:80]
            extras.setdefault(side, [])
            if name and name not in extras[side]:
                extras[side].append(name)
            draft["extras"] = extras
            if name and name not in names:
                names.append(name)
            draft.setdefault("picks", {})[side] = names
            _save(request, draft)
            return redirect(f"{reverse_roles(scenario.id)}?side={side}")
        if not names:
            error = _("حداقل یک نقش انتخاب کنید.")
        else:
            draft.setdefault("picks", {})[side] = names
            _save(request, draft)
            qty_roles = [item for item in posted if item["allows_quantity"]]
            if qty_roles:
                return redirect(f"{reverse_qty(scenario.id)}?side={side}")
            if len(posted) != needed:
                error = _("تعداد نقش‌های انتخاب‌شده باید با تعداد این ساید یکی باشد.")
            else:
                return _after_side(request, scenario, draft, side)
    selected = set(draft.get("picks", {}).get(side) or [])
    return render(
        request,
        "scenarios/large_wizard.html",
        {
            "scenario": scenario,
            "title": _("نقش‌های %(side)s") % {"side": SIDE_LABELS[side]},
            "hint": _("از فهرست انتخاب کنید یا نقش جدید بسازید."),
            "mode": "roles",
            "side": side,
            "needed": needed,
            "roles": catalog,
            "selected": selected,
            "error": error,
        },
    )


@require_http_methods(["GET", "POST"])
def quantities(request, scenario_id):
    scenario = _scenario(scenario_id)
    draft = _bind(request, scenario)
    side = request.GET.get("side") or request.POST.get("side")
    if side not in side_steps(scenario.large_kind):
        raise Http404
    picks = draft.get("picks", {}).get(side) or []
    catalog = {item["name"]: item for item in catalog_for(scenario, side, draft.get("extras") or {})}
    qty_names = [name for name in picks if catalog.get(name, {}).get("allows_quantity")]
    if not qty_names:
        return _after_side(request, scenario, draft, side)
    needed = draft.get(COUNT_FIELDS[side]) or 0
    specials = len(picks) - len(qty_names)
    error = ""
    if request.method == "POST":
        qtys = {}
        total = specials
        for index, name in enumerate(qty_names):
            value = read_int(request.POST.get(f"qty_{index}"), 1, needed)
            if value is None:
                error = _("تعداد نقش‌های ساده را وارد کنید.")
                break
            qtys[name] = value
            total += value
        if not error and total != needed:
            error = _("جمع نقش‌ها باید با تعداد این ساید یکی باشد.")
        elif not error:
            draft.setdefault("qty", {})[side] = qtys
            _save(request, draft)
            return _after_side(request, scenario, draft, side)
    return render(
        request,
        "scenarios/large_wizard.html",
        {
            "scenario": scenario,
            "title": _("تعداد نقش‌های ساده"),
            "hint": _("برای نقش‌هایی مثل مافیای ساده یا شهروند ساده تعداد را بنویسید."),
            "mode": "qty",
            "side": side,
            "fields": [
                {
                    "index": index,
                    "name": name,
                    "value": (draft.get("qty", {}).get(side) or {}).get(name, 1),
                }
                for index, name in enumerate(qty_names)
            ],
            "error": error,
        },
    )


@require_http_methods(["GET", "POST"])
def finals(request, scenario_id):
    scenario = _scenario(scenario_id)
    if scenario.large_kind != KIND_NIGHT:
        return redirect("large_mode", scenario_id=scenario.id)
    draft = _bind(request, scenario)
    cards = list(scenario.catalog_finals.all())
    error = ""
    if request.method == "POST":
        if request.POST.get("select_all"):
            draft["final_all"] = True
            draft["final_picks"] = [card.name for card in cards]
            draft["final_count"] = len(cards)
            _save(request, draft)
            return redirect("large_mode", scenario_id=scenario.id)
        count = read_int(request.POST.get("count"), 0, max(len(cards), 1) + 20)
        picks = request.POST.getlist("card")
        if count is None:
            error = _("تعداد کارت حرکت آخر را وارد کنید.")
        elif len(picks) != count:
            error = _("تعداد کارت‌های انتخاب‌شده باید با عدد واردشده یکی باشد.")
        else:
            draft["final_all"] = False
            draft["final_count"] = count
            draft["final_picks"] = picks
            _save(request, draft)
            return redirect("large_mode", scenario_id=scenario.id)
    return render(
        request,
        "scenarios/large_wizard.html",
        {
            "scenario": scenario,
            "title": _("کارت‌های حرکت آخر"),
            "hint": _("تعداد را بنویسید و کارت‌ها را انتخاب کنید، یا همه را بردارید."),
            "mode": "final",
            "cards": cards,
            "value": draft.get("final_count", ""),
            "selected": set(draft.get("final_picks") or []),
            "error": error,
        },
    )


@require_http_methods(["GET", "POST"])
def done(request, scenario_id):
    return redirect("large_mode", scenario_id=scenario_id)


@require_http_methods(["GET"])
def choose_mode(request, scenario_id):
    scenario = _scenario(scenario_id)
    draft = _bind(request, scenario)
    if not draft.get("player_count"):
        return redirect("large_start", scenario_id=scenario.id)
    payloads = expand_payloads(draft, scenario)
    if len(payloads) != draft["player_count"]:
        return render(
            request,
            "scenarios/large_wizard.html",
            {
                "scenario": scenario,
                "title": _("جمع نقش‌ها درست نیست"),
                "hint": _("جمع نقش‌های سایدها باید با تعداد بازیکن یکی باشد."),
                "mode": "error",
                "error": _("الان %(n)s نقش انتخاب شده است.") % {"n": len(payloads)},
            },
        )
    return render(
        request,
        "scenarios/large_mode.html",
        {"scenario": scenario, "player_count": draft["player_count"]},
    )


@require_http_methods(["GET"])
def play(request, scenario_id, mode):
    if mode not in MODES:
        raise Http404
    scenario = _scenario(scenario_id)
    deal = request.session.get(SESSION_KEY)
    fresh = request.GET.get("fresh") == "1"
    draft = _draft(request)
    if fresh or not same_deal(deal, scenario.id, (deal or {}).get("player_count"), mode) or not (deal or {}).get("large"):
        if draft.get("scenario_id") != scenario.id or not draft.get("player_count"):
            return redirect("large_start", scenario_id=scenario.id)
        payloads = expand_payloads(draft, scenario)
        if len(payloads) != draft["player_count"]:
            return redirect("large_mode", scenario_id=scenario.id)
        finals_payload = expand_finals(draft, scenario) if scenario.large_kind == KIND_NIGHT else []
        deal = create_large_deal(scenario, payloads, finals_payload, mode=mode)
        request.session[SESSION_KEY] = deal
        request.session.modified = True
        if not scenario.is_custom():
            Scenario.objects.filter(pk=scenario.pk).update(play_count=F("play_count") + 1)
        _clear(request)
    if mode in ("order", "chair") and not all(deal["revealed"]):
        return redirect("deal_card", slot=current_number(deal))
    boxes = []
    if mode == "random":
        boxes = [{"number": index + 1, "done": deal["revealed"][index]} for index in range(deal["player_count"])]
    return render(
        request,
        "scenarios/board.html",
        {
            "scenario": scenario,
            "mode": mode,
            "boxes": boxes,
            "done": all(deal["revealed"]),
        },
    )
