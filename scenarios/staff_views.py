from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from scenarios.custom_views import _store_icon
from scenarios.models import (
    KIND_SIDES,
    LARGE_KIND_CHOICES,
    SIDE_CITIZEN,
    SIDE_INDEPENDENT,
    SIDE_MAFIA,
    SIDE_WEREWOLF,
    CatalogFinalCard,
    CatalogRole,
    Role,
    Scenario,
    ScenarioSize,
)
from scenarios.staff import require_staff_flag

SIZE_SLOTS = 5
ROLE_SLOTS = 12
FINAL_SLOTS = 8
QUICK_SIDES = (SIDE_MAFIA, SIDE_CITIZEN, SIDE_INDEPENDENT, SIDE_WEREWOLF)


def _official(scenario_id, *, large=None):
    qs = Scenario.objects.filter(pk=scenario_id, owner__isnull=True, guest_key="")
    if large is True:
        qs = qs.filter(is_large=True)
    elif large is False:
        qs = qs.filter(is_large=False)
    return get_object_or_404(qs)


def _split_names(raw, limit=80):
    names = []
    for line in (raw or "").replace(",", "\n").splitlines():
        name = line.strip()[:80]
        if name:
            names.append(name)
        if len(names) >= limit:
            break
    return names


def _read_int(raw, default=None):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _save_icon(request, scenario):
    uploaded = request.FILES.get("icon")
    if not uploaded:
        return True
    stored = _store_icon(f"staff-{request.user.id}", uploaded)
    if stored is None:
        return False
    scenario.icon = stored
    return True


@require_http_methods(["GET", "POST"])
@require_staff_flag("can_manage_quick")
def quick_edit(request, scenario_id=None):
    scenario = _official(scenario_id, large=False) if scenario_id else None
    error = ""
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()[:120]
        if not name:
            error = "اسم سناریو را وارد کنید."
        else:
            sizes = []
            for index in range(SIZE_SLOTS):
                player_count = _read_int(request.POST.get(f"player_{index}"))
                if not player_count:
                    continue
                counts = {
                    SIDE_MAFIA: max(0, _read_int(request.POST.get(f"mafia_count_{index}"), 0) or 0),
                    SIDE_CITIZEN: max(0, _read_int(request.POST.get(f"citizen_count_{index}"), 0) or 0),
                    SIDE_INDEPENDENT: max(0, _read_int(request.POST.get(f"independent_count_{index}"), 0) or 0),
                    SIDE_WEREWOLF: max(0, _read_int(request.POST.get(f"werewolf_count_{index}"), 0) or 0),
                }
                names = {side: _split_names(request.POST.get(f"{side}_names_{index}")) for side in QUICK_SIDES}
                total = sum(counts.values())
                if total != player_count:
                    error = f"جمع نقش‌های حالت {player_count} نفره باید با تعداد نفرات یکی باشد."
                    break
                for side in QUICK_SIDES:
                    if len(names[side]) != counts[side]:
                        error = "تعداد اسم نقش‌ها باید با شمارش هر ساید یکی باشد. هر نقش را در یک خط بنویسید."
                        break
                if error:
                    break
                sizes.append({"player_count": player_count, "counts": counts, "names": names})
            if not error and not sizes:
                error = "حداقل یک حالت تعداد نفرات با نقش کامل وارد کنید."
            if not error:
                created = scenario is None
                if created:
                    scenario = Scenario(name=name, is_large=False)
                scenario.name = name
                scenario.has_final_move = request.POST.get("has_final_move") == "1"
                scenario.has_death_lottery = request.POST.get("has_death_lottery") == "1"
                scenario.home_order = max(0, _read_int(request.POST.get("home_order"), 0) or 0)
                if not _save_icon(request, scenario):
                    error = "فقط تصویر کوچک JPG یا PNG انتخاب کنید."
                else:
                    if created:
                        featured_count = Scenario.objects.filter(
                            is_featured=True, owner__isnull=True, guest_key=""
                        ).count()
                        scenario.is_featured = featured_count < 6
                    scenario.save()
                    scenario.sizes.all().delete()
                    for item in sizes:
                        size = ScenarioSize.objects.create(
                            scenario=scenario,
                            player_count=item["player_count"],
                            mafia_count=item["counts"][SIDE_MAFIA],
                            citizen_count=item["counts"][SIDE_CITIZEN],
                            independent_count=item["counts"][SIDE_INDEPENDENT],
                            werewolf_count=item["counts"][SIDE_WEREWOLF],
                            final_move_count=None,
                        )
                        for side in QUICK_SIDES:
                            for role_name in item["names"][side]:
                                Role.objects.create(size=size, side=side, name=role_name)
                    messages.success(request, "سناریو تقسیم نقش سریع ذخیره شد.")
                    return redirect("home")
    size_forms = []
    existing = list(scenario.sizes.all()) if scenario else []
    for index in range(SIZE_SLOTS):
        size = existing[index] if index < len(existing) else None
        roles = list(size.roles.all()) if size else []
        row = {
            "player": size.player_count if size else "",
            "mafia": size.mafia_count if size else 0,
            "citizen": size.citizen_count if size else 0,
            "independent": size.independent_count if size else 0,
            "werewolf": size.werewolf_count if size else 0,
        }
        for side in QUICK_SIDES:
            row[f"{side}_names"] = "\n".join(role.name for role in roles if role.side == side)
        size_forms.append(row)
    return render(
        request,
        "scenarios/staff_quick.html",
        {
            "scenario": scenario,
            "size_forms": size_forms,
            "error": error,
            "title": "ویرایش تقسیم نقش سریع" if scenario else "سناریو جدید تقسیم نقش سریع",
        },
    )


@require_POST
@require_staff_flag("can_manage_quick")
def quick_delete(request, scenario_id):
    scenario = _official(scenario_id, large=False)
    scenario.delete()
    messages.success(request, "سناریو حذف شد.")
    return redirect("home")


def _role_rows(scenario, side):
    rows = list(scenario.catalog_roles.filter(side=side)) if scenario else []
    forms = []
    for index in range(ROLE_SLOTS):
        row = rows[index] if index < len(rows) else None
        forms.append(
            {
                "id": row.id if row else "",
                "name": row.name if row else "",
                "description": row.description if row else "",
                "allows_quantity": bool(row.allows_quantity) if row else False,
            }
        )
    return forms


@require_http_methods(["GET", "POST"])
@require_staff_flag("can_manage_large")
def large_edit(request, scenario_id=None):
    scenario = _official(scenario_id, large=True) if scenario_id else None
    error = ""
    kind = (request.POST.get("large_kind") if request.method == "POST" else "") or (
        scenario.large_kind if scenario else "advanced"
    )
    if kind not in dict(LARGE_KIND_CHOICES):
        kind = "advanced"
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()[:120]
        if not name:
            error = "اسم سناریو را وارد کنید."
        else:
            created = scenario is None
            if created:
                scenario = Scenario(name=name, is_large=True, large_kind=kind)
            scenario.name = name
            scenario.is_large = True
            scenario.large_kind = kind
            scenario.has_final_move = request.POST.get("has_final_move") == "1" or kind == "night"
            scenario.has_death_lottery = request.POST.get("has_death_lottery") == "1"
            scenario.home_order = max(0, _read_int(request.POST.get("home_order"), 0) or 0)
            if not _save_icon(request, scenario):
                error = "فقط تصویر کوچک JPG یا PNG انتخاب کنید."
            else:
                scenario.save()
                keep_ids = []
                for side in KIND_SIDES.get(kind) or ():
                    for index in range(ROLE_SLOTS):
                        role_id = _read_int(request.POST.get(f"{side}_id_{index}"))
                        role_name = (request.POST.get(f"{side}_name_{index}") or "").strip()[:80]
                        if not role_name:
                            continue
                        defaults = {
                            "description": (request.POST.get(f"{side}_desc_{index}") or "").strip()[:300],
                            "allows_quantity": request.POST.get(f"{side}_qty_{index}") == "1",
                            "sort_order": index,
                            "side": side,
                        }
                        if role_id:
                            role = CatalogRole.objects.filter(pk=role_id, scenario=scenario).first()
                            if role:
                                for key, value in defaults.items():
                                    setattr(role, key, value)
                                role.name = role_name
                                role.save()
                                keep_ids.append(role.id)
                                continue
                        role = CatalogRole.objects.create(scenario=scenario, name=role_name, **defaults)
                        keep_ids.append(role.id)
                scenario.catalog_roles.exclude(pk__in=keep_ids).delete()
                if scenario.has_final_move:
                    final_ids = []
                    for index in range(FINAL_SLOTS):
                        card_id = _read_int(request.POST.get(f"final_id_{index}"))
                        card_name = (request.POST.get(f"final_name_{index}") or "").strip()[:80]
                        if not card_name:
                            continue
                        description = (request.POST.get(f"final_desc_{index}") or "").strip()[:300]
                        if card_id:
                            card = CatalogFinalCard.objects.filter(pk=card_id, scenario=scenario).first()
                            if card:
                                card.name = card_name
                                card.description = description
                                card.sort_order = index
                                card.save()
                                final_ids.append(card.id)
                                continue
                        card = CatalogFinalCard.objects.create(
                            scenario=scenario, name=card_name, description=description, sort_order=index
                        )
                        final_ids.append(card.id)
                    scenario.catalog_finals.exclude(pk__in=final_ids).delete()
                else:
                    scenario.catalog_finals.all().delete()
                messages.success(request, "سناریو تعداد بالا ذخیره شد.")
                return redirect("home")
    sides = []
    for side in KIND_SIDES.get(kind) or ():
        sides.append(
            {
                "key": side,
                "label": dict(CatalogRole._meta.get_field("side").choices).get(side, side),
                "roles": _role_rows(scenario, side),
            }
        )
    finals = []
    existing_finals = list(scenario.catalog_finals.all()) if scenario else []
    for index in range(FINAL_SLOTS):
        card = existing_finals[index] if index < len(existing_finals) else None
        finals.append(
            {
                "id": card.id if card else "",
                "name": card.name if card else "",
                "description": card.description if card else "",
            }
        )
    return render(
        request,
        "scenarios/staff_large.html",
        {
            "scenario": scenario,
            "error": error,
            "kind": kind,
            "kind_choices": LARGE_KIND_CHOICES,
            "sides": sides,
            "finals": finals,
            "title": "ویرایش سناریو تعداد بالا" if scenario else "سناریو تعداد بالای جدید",
        },
    )


@require_POST
@require_staff_flag("can_manage_large")
def large_delete(request, scenario_id):
    scenario = _official(scenario_id, large=True)
    scenario.delete()
    messages.success(request, "سناریو تعداد بالا حذف شد.")
    return redirect("home")


@login_required(login_url="profile")
@require_http_methods(["GET", "POST"])
def page_edit(request, scenario_id, kind):
    flag = "can_edit_rulebook" if kind == "rulebook" else "can_edit_rules"
    if kind not in {"rulebook", "rules"}:
        return redirect("home")
    from scenarios.staff import has_staff_flag

    if not has_staff_flag(request.user, flag):
        messages.error(request, "اجازه این کار را ندارید.")
        return redirect("home")
    if not request.user.is_authenticated:
        return redirect("profile")
    scenario = get_object_or_404(Scenario, pk=scenario_id, owner__isnull=True, guest_key="")
    title_field = f"{kind}_title_fa"
    body_field = f"{kind}_body_fa"
    error = ""
    if request.method == "POST":
        setattr(scenario, title_field, (request.POST.get("title") or "").strip()[:160])
        setattr(scenario, body_field, request.POST.get("body") or "")
        scenario.save()
        messages.success(request, "متن صفحه ذخیره شد.")
        return redirect("scenario_rulebook" if kind == "rulebook" else "scenario_rules", scenario_id=scenario.id)
    return render(
        request,
        "scenarios/staff_page.html",
        {
            "scenario": scenario,
            "kind": kind,
            "title": "ویرایش رول‌بوک" if kind == "rulebook" else "ویرایش قوانین",
            "page_title": getattr(scenario, title_field, ""),
            "page_body": getattr(scenario, body_field, ""),
            "error": error,
        },
    )
