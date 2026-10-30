from urllib.parse import unquote

from django.contrib import messages
from django.db.models import F, Prefetch, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import get_language, gettext as _, override
from django.views.decorators.http import require_POST

from banners.geo import captcha_is_valid, captcha_prompt, consume_captcha, issue_sum_captcha

from scenarios.dealing import (
    FATE_WORDS,
    MODE_CHAIR,
    MODE_ORDER,
    MODE_RANDOM,
    MODES,
    SESSION_KEY,
    card_static,
    create_deal,
    create_large_deal,
    current_number,
    ensure_host_tools,
    final_card_static,
    new_lottery_round,
    open_lottery,
    latest_lottery,
    same_deal,
)
from scenarios.html_safe import plain_page_text
from scenarios.models import FinalMoveCard, Role, Scenario, ScenarioComment, ScenarioSize
from scenarios.pins import (
    MAX_HOME_SCENARIOS,
    home_quick_scenarios,
    listed_official,
    official_queryset,
    remove_from_home,
    replace_home_scenario,
    shown_home_ids,
    toggle_pin as toggle_home_pin,
)


def _visible_scenario(request, scenario_id):
    scenario = get_object_or_404(Scenario, pk=scenario_id)
    if scenario.is_custom() and not scenario.can_be_managed_by(request):
        raise Http404
    return scenario


def _public_scenario_page(request, scenario_id):
    scenario = get_object_or_404(Scenario, pk=scenario_id)
    if scenario.is_custom() and not scenario.can_be_managed_by(request):
        raise Http404
    return scenario


def _redirect_legacy_slug(request, slug, viewname):
    decoded = unquote(slug or "")
    scenario = Scenario.objects.filter(slug__in={slug, decoded}).first()
    if not scenario:
        raise Http404
    if scenario.is_custom() and not scenario.can_be_managed_by(request):
        raise Http404
    return redirect(viewname, scenario_id=scenario.pk)


def _playable_sizes(scenario):
    sizes = []
    for size in scenario.sizes.prefetch_related("roles"):
        if size.counts_match_players() and size.roles_match_counts():
            sizes.append(size)
    return sizes


def _size_or_404(scenario, player_count):
    size = get_object_or_404(ScenarioSize, scenario=scenario, player_count=player_count)
    if not size.counts_match_players() or not size.roles_match_counts():
        raise Http404
    return size


def _board_url(deal):
    if deal.get("large"):
        return redirect("large_play", scenario_id=deal["scenario_id"], mode=deal["mode"])
    return redirect(
        "deal_board",
        scenario_id=deal["scenario_id"],
        player_count=deal["player_count"],
        mode=deal["mode"],
    )


def _pin_state(request, scenario):
    return {
        "scenario_pinned": scenario.id in shown_home_ids(request) and not scenario.is_custom(),
        "can_pin_scenario": not scenario.is_custom(),
    }


def start(request, scenario_id):
    scenario = _visible_scenario(request, scenario_id)
    sizes = _playable_sizes(scenario)
    if len(sizes) == 1:
        return redirect("deal_mode", scenario_id=scenario.id, player_count=sizes[0].player_count)
    context = {"scenario": scenario, "sizes": sizes}
    context.update(_pin_state(request, scenario))
    return render(request, "scenarios/player_count.html", context)


def choose_mode(request, scenario_id, player_count):
    scenario = _visible_scenario(request, scenario_id)
    size = _size_or_404(scenario, player_count)
    context = {"scenario": scenario, "size": size}
    context.update(_pin_state(request, scenario))
    return render(request, "scenarios/mode.html", context)


def board(request, scenario_id, player_count, mode):
    if mode not in MODES:
        raise Http404
    scenario = _visible_scenario(request, scenario_id)
    size = _size_or_404(scenario, player_count)
    deal = request.session.get(SESSION_KEY)
    fresh = request.GET.get("fresh") == "1"
    if fresh or not same_deal(deal, scenario.id, size.player_count, mode):
        deal = create_deal(size, mode)
        request.session[SESSION_KEY] = deal
        if not scenario.is_custom():
            Scenario.objects.filter(pk=scenario.pk).update(play_count=F("play_count") + 1)
    if mode in (MODE_ORDER, MODE_CHAIR) and not all(deal["revealed"]):
        return redirect("deal_card", slot=current_number(deal))
    boxes = []
    if mode == MODE_RANDOM:
        boxes = [
            {"number": index + 1, "done": deal["revealed"][index]}
            for index in range(size.player_count)
        ]
    return render(
        request,
        "scenarios/board.html",
        {
            "scenario": scenario,
            "size": size,
            "mode": mode,
            "boxes": boxes,
            "done": all(deal["revealed"]),
        },
    )


def card(request, slot):
    deal = request.session.get(SESSION_KEY)
    if not deal:
        return redirect("home")
    count = deal["player_count"]
    if slot < 1 or slot > count:
        raise Http404
    mode = deal["mode"]
    if mode in (MODE_ORDER, MODE_CHAIR):
        current = current_number(deal)
        if deal["revealed"][slot - 1] and current is not None and slot != current:
            return redirect("deal_card", slot=current)
        if slot != current and not deal["revealed"][slot - 1]:
            return _board_url(deal)
        if current is None and not deal["revealed"][slot - 1]:
            return _board_url(deal)
    continue_label = "بازگشت به کارت‌ها" if mode == MODE_RANDOM else "نفر بعدی"
    return render(
        request,
        "scenarios/card.html",
        {
            "slot": slot,
            "mode": mode,
            "already": deal["revealed"][slot - 1],
            "auto_reveal": mode == MODE_RANDOM,
            "continue_label": continue_label,
            "board_url": _board_url(deal).url,
        },
    )


@require_POST
def reveal(request, slot):
    deal = request.session.get(SESSION_KEY)
    if not deal:
        return JsonResponse({"error": "missing"}, status=404)
    count = deal["player_count"]
    if slot < 1 or slot > count:
        return JsonResponse({"error": "slot"}, status=404)
    mode = deal["mode"]
    if mode in (MODE_ORDER, MODE_CHAIR) and not deal["revealed"][slot - 1]:
        if current_number(deal) != slot:
            return JsonResponse({"error": "wait"}, status=409)
    payload = deal["slots"][slot - 1]
    if isinstance(payload, dict):
        name = payload.get("name") or ""
        description = payload.get("description") or ""
        icon = ""
        side = payload.get("side") or "citizen"
    else:
        role = get_object_or_404(Role, pk=payload, size__player_count=count)
        name = role.name
        description = role.description
        icon = role.icon.url if role.icon else ""
        side = role.side
    deal["revealed"][slot - 1] = True
    request.session[SESSION_KEY] = deal
    request.session.modified = True
    return JsonResponse(
        {
            "name": name,
            "description": description,
            "icon": icon,
            "card": card_static(side),
            "done": all(deal["revealed"]),
        }
    )


def restart(request):
    deal = request.session.get(SESSION_KEY)
    if not deal:
        return redirect("home")
    if deal.get("large"):
        scenario = _visible_scenario(request, deal["scenario_id"])
        mode = deal.get("mode") if deal.get("mode") in MODES else MODE_ORDER
        request.session[SESSION_KEY] = create_large_deal(
            scenario,
            deal.get("role_payloads") or deal.get("slots") or [],
            deal.get("final_payloads") or [],
            mode=mode,
        )
        return redirect("large_play", scenario_id=scenario.id, mode=mode)
    size = get_object_or_404(
        ScenarioSize,
        scenario_id=deal["scenario_id"],
        player_count=deal["player_count"],
    )
    request.session[SESSION_KEY] = create_deal(size, deal["mode"])
    return _board_url(deal)


def cancel(request):
    request.session.pop(SESSION_KEY, None)
    return redirect("home")


def _finished_deal(request):
    deal = request.session.get(SESSION_KEY)
    revealed = (deal or {}).get("revealed") or []
    if not revealed or not all(revealed):
        return None
    return deal


def _save_deal(request, deal):
    request.session[SESSION_KEY] = deal
    request.session.modified = True


def _scenario_and_size(request, deal):
    scenario = _visible_scenario(request, deal["scenario_id"])
    if deal.get("large"):
        return scenario, None
    size = get_object_or_404(
        ScenarioSize,
        scenario=scenario,
        player_count=deal["player_count"],
    )
    return scenario, size


def host(request):
    deal = _finished_deal(request)
    if not deal:
        return redirect("home")
    scenario, size = _scenario_and_size(request, deal)
    if ensure_host_tools(deal, size):
        _save_deal(request, deal)
    return render(
        request,
        "scenarios/host.html",
        {
            "scenario": scenario,
            "show_final": scenario.has_final_move and bool(deal.get("final_slots")),
            "show_lottery": scenario.has_death_lottery,
            "is_custom": scenario.is_custom(),
        },
    )


def final_board(request):
    deal = _finished_deal(request)
    if not deal:
        return redirect("home")
    scenario, size = _scenario_and_size(request, deal)
    if ensure_host_tools(deal, size):
        _save_deal(request, deal)
    if not scenario.has_final_move or not deal.get("final_slots"):
        return redirect("deal_host")
    boxes = [
        {"number": index + 1, "done": deal["final_revealed"][index]}
        for index in range(len(deal["final_slots"]))
    ]
    return render(
        request,
        "scenarios/final_board.html",
        {"scenario": scenario, "boxes": boxes},
    )


def final_card(request, slot):
    deal = _finished_deal(request)
    if not deal:
        return redirect("home")
    count = len(deal.get("final_slots") or [])
    if slot < 1 or slot > count:
        raise Http404
    return render(
        request,
        "scenarios/special_card.html",
        {
            "kind": "final",
            "already": deal["final_revealed"][slot - 1],
            "reveal_url": redirect("deal_final_reveal", slot=slot).url,
            "back_url": redirect("deal_final").url,
        },
    )


@require_POST
def final_reveal(request, slot):
    deal = _finished_deal(request)
    if not deal:
        return JsonResponse({"error": "missing"}, status=404)
    count = len(deal.get("final_slots") or [])
    if slot < 1 or slot > count:
        return JsonResponse({"error": "slot"}, status=404)
    payload = deal["final_slots"][slot - 1]
    if isinstance(payload, dict):
        name = payload.get("name") or ""
        description = payload.get("description") or ""
    else:
        card = get_object_or_404(FinalMoveCard, pk=payload)
        name = card.name
        description = card.description
    deal["final_revealed"][slot - 1] = True
    _save_deal(request, deal)
    return JsonResponse(
        {
            "name": name,
            "description": description,
            "card": final_card_static(),
        }
    )


def lottery(request):
    deal = _finished_deal(request)
    if not deal:
        return redirect("home")
    scenario, size = _scenario_and_size(request, deal)
    if ensure_host_tools(deal, size):
        _save_deal(request, deal)
    if not scenario.has_death_lottery:
        return redirect("deal_host")
    if request.method == "POST" and open_lottery(deal) is None:
        deal.setdefault("lottery_rounds", []).append(new_lottery_round())
        _save_deal(request, deal)
        return redirect("deal_lottery")
    current = open_lottery(deal)
    boxes = []
    if current:
        boxes = [
            {"index": index, "done": current["picked"] not in (None, index)}
            for index in range(2)
        ]
    return render(
        request,
        "scenarios/lottery.html",
        {"scenario": scenario, "boxes": boxes},
    )


def lottery_card(request, index):
    deal = _finished_deal(request)
    if not deal:
        return redirect("home")
    current = latest_lottery(deal)
    if current is None or index not in (0, 1):
        return redirect("deal_lottery")
    if current["picked"] not in (None, index):
        return redirect("deal_lottery")
    return render(
        request,
        "scenarios/special_card.html",
        {
            "kind": "lottery",
            "already": current["picked"] == index,
            "reveal_url": redirect("deal_lottery_reveal", index=index).url,
            "back_url": redirect("deal_lottery").url,
        },
    )


@require_POST
def lottery_reveal(request, index):
    deal = _finished_deal(request)
    if not deal or index not in (0, 1):
        return JsonResponse({"error": "missing"}, status=404)
    current = latest_lottery(deal)
    if current is None:
        return JsonResponse({"error": "round"}, status=404)
    if current["picked"] not in (None, index):
        return JsonResponse({"error": "used"}, status=409)
    current["picked"] = index
    _save_deal(request, deal)
    return JsonResponse(
        {
            "word": FATE_WORDS[current["outcomes"][index]],
            "card": final_card_static(),
        }
    )


def _localized_absolute(request, viewname, scenario_id, language):
    with override(language):
        path = reverse(viewname, kwargs={"scenario_id": scenario_id})
    return request.build_absolute_uri(path)


def _page_seo(request, scenario, kind):
    viewname = "scenario_rulebook" if kind == "rulebook" else "scenario_rules"
    language = (get_language() or "fa").split("-")[0]
    canonical = _localized_absolute(request, viewname, scenario.pk, language)
    image = ""
    if scenario.icon:
        image = request.build_absolute_uri(scenario.icon.url)
    body_html = scenario.page_body_html(kind)
    return {
        "kind": kind,
        "title": scenario.page_title(kind),
        "body": body_html,
        "has_body": bool(plain_page_text(body_html)),
        "meta_title": scenario.page_meta_title(kind),
        "meta_description": scenario.page_meta_description(kind),
        "canonical": canonical,
        "hreflang_fa": _localized_absolute(request, viewname, scenario.pk, "fa"),
        "hreflang_en": _localized_absolute(request, viewname, scenario.pk, "en"),
        "og_image": image,
        "in_language": "en" if language == "en" else "fa",
    }


def scenario_rulebook(request, scenario_id):
    scenario = _public_scenario_page(request, scenario_id)
    return render(
        request,
        "scenarios/scenario_page.html",
        {"scenario": scenario, "page": _page_seo(request, scenario, "rulebook"), "tab_active": "rulebook"},
    )


def scenario_rules(request, scenario_id):
    scenario = _public_scenario_page(request, scenario_id)
    return render(
        request,
        "scenarios/scenario_page.html",
        {"scenario": scenario, "page": _page_seo(request, scenario, "rules"), "tab_active": "rules"},
    )


def scenario_comments(request, scenario_id):
    scenario = _public_scenario_page(request, scenario_id)
    if request.method == "POST":
        if request.POST.get("website"):
            return redirect(scenario.get_comments_url())
        name = (request.POST.get("author_name") or "").strip()[:40]
        body = (request.POST.get("body") or "").strip()[:1000]
        answer = request.POST.get("captcha") or ""
        parent = None
        parent_id = request.POST.get("parent")
        if parent_id:
            parent = ScenarioComment.objects.filter(
                pk=parent_id,
                scenario=scenario,
                is_approved=True,
            ).first()
        if not name or not body:
            messages.error(request, _("نام و متن نظر را وارد کنید."))
            issue_sum_captcha(request)
            return redirect(scenario.get_comments_url())
        if not captcha_is_valid(request, answer):
            messages.error(request, _("جمع دو عدد را درست وارد کنید."))
            issue_sum_captcha(request)
            return redirect(scenario.get_comments_url())
        ScenarioComment.objects.create(
            scenario=scenario,
            parent=parent,
            author_name=name,
            body=body,
        )
        consume_captcha(request)
        messages.success(request, _("نظر شما ثبت شد و پس از تأیید مدیریت نمایش داده می‌شود."))
        return redirect(scenario.get_comments_url())
    roots = scenario.comments.filter(is_approved=True, parent__isnull=True).prefetch_related(
        Prefetch(
            "replies",
            queryset=ScenarioComment.objects.filter(is_approved=True).order_by("created_at", "id"),
        )
    )
    left, right = captcha_prompt(request)
    return render(
        request,
        "scenarios/comments.html",
        {
            "scenario": scenario,
            "comments": roots,
            "tab_active": "comments",
            "captcha_left": left,
            "captcha_right": right,
        },
    )


def scenario_catalog(request):
    query = (request.GET.get("q") or "").strip()
    sort = (request.GET.get("sort") or "name").strip()
    queryset = official_queryset()
    if query:
        queryset = queryset.filter(Q(name__icontains=query) | Q(name_en__icontains=query))
    scenarios = listed_official(queryset)
    if sort == "newest":
        scenarios.sort(key=lambda item: item.pk, reverse=True)
    elif sort == "popular":
        scenarios.sort(key=lambda item: (item.play_count, item.pk), reverse=True)
    else:
        sort = "name"
        scenarios.sort(key=lambda item: (item.display_name() or "").casefold())
    home_items = home_quick_scenarios(request)[0]
    home_ids = [item.id for item in home_items]
    return render(
        request,
        "scenarios/catalog.html",
        {
            "scenarios": scenarios,
            "query": query,
            "sort": sort,
            "pinned_ids": set(home_ids),
            "home_scenarios": home_items,
            "home_full": len(home_ids) >= 6,
        },
    )


@require_POST
def pin_scenario(request, scenario_id):
    scenario = _visible_scenario(request, scenario_id)
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    if not next_url.startswith("/") or not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = "/"
    if scenario.is_custom():
        messages.error(request, _("سناریوی شخصی را نمی‌توان به صفحه اصلی اضافه کرد."))
        return redirect(next_url)
    shown = shown_home_ids(request)
    if scenario.id in shown:
        remove_from_home(request, scenario.id)
        messages.success(request, _("سناریو از صفحه اصلی برداشته شد."))
        return redirect(next_url)
    if len(shown) >= MAX_HOME_SCENARIOS:
        messages.error(request, _("حداکثر ۶ سناریو در تقسیم نقش سریع صفحه اصلی جای می‌گیرد. یکی را جایگزین کنید."))
        return redirect(next_url)
    pinned, ok = toggle_home_pin(request, scenario.id)
    if not ok:
        messages.error(request, _("حداکثر ۶ سناریو در تقسیم نقش سریع صفحه اصلی جای می‌گیرد. یکی را جایگزین کنید."))
    elif pinned:
        messages.success(request, _("سناریو به صفحه اصلی اضافه شد."))
    else:
        messages.success(request, _("سناریو از صفحه اصلی برداشته شد."))
    return redirect(next_url)


def _safe_next(request):
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    if not next_url.startswith("/") or not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return "/"
    return next_url


@require_POST
def pin_scenario_replace(request):
    next_url = _safe_next(request)
    try:
        add_id = int(request.POST.get("add_id") or 0)
        remove_id = int(request.POST.get("remove_id") or 0)
    except (TypeError, ValueError):
        messages.error(request, _("جایگزینی سناریو انجام نشد."))
        return redirect(next_url)
    add_scenario = _visible_scenario(request, add_id)
    if add_scenario.is_custom():
        messages.error(request, _("سناریوی شخصی را نمی‌توان به صفحه اصلی اضافه کرد."))
        return redirect(next_url)
    if replace_home_scenario(request, add_scenario.id, remove_id):
        messages.success(request, _("سناریو در صفحه اصلی جایگزین شد."))
    else:
        messages.error(request, _("یکی از سناریوهای صفحه اصلی را برای حذف انتخاب کنید."))
    return redirect(next_url)


def scenario_rulebook_by_slug(request, slug):
    return _redirect_legacy_slug(request, slug, "scenario_rulebook")


def scenario_rules_by_slug(request, slug):
    return _redirect_legacy_slug(request, slug, "scenario_rules")


def scenario_comments_by_slug(request, slug):
    return _redirect_legacy_slug(request, slug, "scenario_comments")
