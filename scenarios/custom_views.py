from pathlib import Path
from uuid import uuid4

from django.core.files.storage import default_storage
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from scenarios.models import (
    GUEST_SCENARIO_KEY,
    FinalMoveCard,
    Role,
    Scenario,
    ScenarioSize,
    SIDE_CITIZEN,
    SIDE_INDEPENDENT,
    SIDE_MAFIA,
    SIDE_WEREWOLF,
)

WIZARD_KEY = "custom_scenario_wizard"
MIN_COUNT = 1
MAX_COUNT = 20
ICON_MAX = 2 * 1024 * 1024
ICON_TYPES = {".jpg": ".jpg", ".jpeg": ".jpg", ".png": ".png", ".webp": ".webp", ".gif": ".gif"}


def _ensure_guest_key(request):
    key = request.session.get(GUEST_SCENARIO_KEY)
    if not key:
        key = uuid4().hex
        request.session[GUEST_SCENARIO_KEY] = key
        request.session.modified = True
    return key


def _icon_owner(request):
    if request.user.is_authenticated:
        return str(request.user.id)
    return _ensure_guest_key(request)


def _owned_scenario(request, scenario_id):
    scenario = get_object_or_404(Scenario, pk=scenario_id)
    if not scenario.can_be_managed_by(request):
        raise Http404
    return scenario


def _draft(request):
    return request.session.get(WIZARD_KEY) or {}


def _save_draft(request, data):
    request.session[WIZARD_KEY] = data
    request.session.modified = True


def _clear_draft(request):
    request.session.pop(WIZARD_KEY, None)


def _read_count(value, min_count=MIN_COUNT):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if min_count <= number <= MAX_COUNT:
        return number
    return None


def _read_names(request, count):
    names = []
    for index in range(count):
        name = (request.POST.get(f"name_{index}") or "").strip()[:80]
        if not name:
            return None
        names.append(name)
    return names


def _store_icon(user_id, upload):
    if not upload:
        return ""
    if upload.size > ICON_MAX:
        return None
    suffix = ICON_TYPES.get(Path(upload.name or "").suffix.lower())
    if not suffix:
        return None
    from banners.images import optimize_image
    from django.core.exceptions import ValidationError

    try:
        stored = optimize_image(upload, max_edge=720)
    except ValidationError:
        return None
    return default_storage.save(f"user_scenario_icons/{user_id}/{stored.name}", stored)


def wizard_step(draft):
    if not (draft.get("name") or "").strip():
        return "custom_name"
    if draft.get("mafia_count") is None:
        return "custom_mafia_count"
    if len(draft.get("mafia_names") or []) != draft["mafia_count"]:
        return "custom_mafia_names"
    if draft.get("citizen_count") is None:
        return "custom_citizen_count"
    if len(draft.get("citizen_names") or []) != draft["citizen_count"]:
        return "custom_citizen_names"
    if "has_independent" not in draft:
        return "custom_extras"
    if draft.get("has_independent"):
        if draft.get("independent_count") is None:
            return "custom_independent_count"
        if len(draft.get("independent_names") or []) != draft["independent_count"]:
            return "custom_independent_names"
    if draft.get("has_werewolf"):
        if draft.get("werewolf_count") is None:
            return "custom_werewolf_count"
        if len(draft.get("werewolf_names") or []) != draft["werewolf_count"]:
            return "custom_werewolf_names"
    if "has_final_move" not in draft:
        return "custom_tools"
    if draft.get("has_final_move"):
        if draft.get("final_count") is None:
            return "custom_final_count"
        if len(draft.get("final_names") or []) != draft["final_count"]:
            return "custom_final_names"
    return ""


def _ensure_step(request, expected):
    draft = _draft(request)
    current = wizard_step(draft)
    if current != expected:
        if current:
            return redirect(current)
        return _finish(request, draft)
    return None


def _name_fields(count, values):
    values = values or []
    fields = []
    for index in range(count):
        fields.append({"index": index, "value": values[index] if index < len(values) else ""})
    return fields


def _finish(request, draft):
    mafia = draft["mafia_count"]
    citizen = draft["citizen_count"]
    independent = draft["independent_count"] if draft.get("has_independent") else 0
    werewolf = draft["werewolf_count"] if draft.get("has_werewolf") else 0
    player_count = mafia + citizen + independent + werewolf
    edit_id = draft.get("edit_id")
    if edit_id:
        scenario = _owned_scenario(request, edit_id)
        scenario.name = draft["name"]
        scenario.has_final_move = bool(draft.get("has_final_move"))
        scenario.has_death_lottery = bool(draft.get("has_death_lottery"))
        if draft.get("icon_path"):
            scenario.icon = draft["icon_path"]
        scenario.save()
        scenario.sizes.all().delete()
    else:
        owner = request.user if request.user.is_authenticated else None
        scenario = Scenario(
            name=draft["name"],
            owner=owner,
            guest_key="" if owner else _ensure_guest_key(request),
            has_final_move=bool(draft.get("has_final_move")),
            has_death_lottery=bool(draft.get("has_death_lottery")),
        )
        if draft.get("icon_path"):
            scenario.icon = draft["icon_path"]
        scenario.save()
    size = ScenarioSize.objects.create(
        scenario=scenario,
        player_count=player_count,
        mafia_count=mafia,
        citizen_count=citizen,
        independent_count=independent,
        werewolf_count=werewolf,
        final_move_count=draft.get("final_count") if draft.get("has_final_move") else None,
    )
    for name in draft.get("mafia_names") or []:
        Role.objects.create(size=size, side=SIDE_MAFIA, name=name)
    for name in draft.get("citizen_names") or []:
        Role.objects.create(size=size, side=SIDE_CITIZEN, name=name)
    for name in draft.get("independent_names") or []:
        Role.objects.create(size=size, side=SIDE_INDEPENDENT, name=name)
    for name in draft.get("werewolf_names") or []:
        Role.objects.create(size=size, side=SIDE_WEREWOLF, name=name)
    if draft.get("has_final_move"):
        for index, name in enumerate(draft.get("final_names") or []):
            FinalMoveCard.objects.create(size=size, name=name, sort_order=index)
    _clear_draft(request)
    return redirect("home")


def _count_page(request, key, title, hint, min_count=MIN_COUNT, names_key=None):
    draft = _draft(request)
    error = _("یک عدد بین ۰ تا ۲۰ وارد کنید.") if min_count == 0 else _("یک عدد بین ۱ تا ۲۰ وارد کنید.")
    if request.method == "POST":
        number = _read_count(request.POST.get("count"), min_count)
        if number is None:
            return render(
                request,
                "scenarios/wizard.html",
                {
                    "title": title,
                    "hint": hint,
                    "mode": "count",
                    "min_count": min_count,
                    "error": error,
                    "value": request.POST.get("count", ""),
                },
            )
        draft[key] = number
        if names_key:
            draft[names_key] = (draft.get(names_key) or [])[:number]
        _save_draft(request, draft)
        nxt = wizard_step(draft)
        return _finish(request, draft) if not nxt else redirect(nxt)
    value = "" if draft.get(key) is None else draft.get(key)
    return render(
        request,
        "scenarios/wizard.html",
        {"title": title, "hint": hint, "mode": "count", "min_count": min_count, "value": value},
    )


def _names_page(request, count_key, names_key, title, hint, step_name):
    bounce = _ensure_step(request, step_name)
    if bounce:
        return bounce
    draft = _draft(request)
    count = draft[count_key]
    if request.method == "POST":
        names = _read_names(request, count)
        if not names:
            return render(
                request,
                "scenarios/wizard.html",
                {
                    "title": title,
                    "hint": hint,
                    "mode": "names",
                    "fields": _name_fields(count, [request.POST.get(f"name_{i}", "") for i in range(count)]),
                    "error": _("اسم همهٔ نقش‌ها را وارد کنید."),
                },
            )
        draft[names_key] = names
        _save_draft(request, draft)
        nxt = wizard_step(draft)
        return _finish(request, draft) if not nxt else redirect(nxt)
    return render(
        request,
        "scenarios/wizard.html",
        {"title": title, "hint": hint, "mode": "names", "fields": _name_fields(count, draft.get(names_key))},
    )


@require_http_methods(["GET", "POST"])
def custom_name(request):
    if request.GET.get("fresh") == "1":
        _clear_draft(request)
    draft = _draft(request)
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()[:120]
        if not name:
            return render(
                request,
                "scenarios/wizard.html",
                {"title": _("اسم سناریو"), "hint": _("یک اسم انتخاب کنید و اگر خواستید عکس آیکون را از گوشی بردارید."), "mode": "name", "error": _("اسم سناریو را وارد کنید."), "value": name},
            )
        icon_path = draft.get("icon_path") or ""
        uploaded = request.FILES.get("icon")
        if uploaded:
            stored = _store_icon(_icon_owner(request), uploaded)
            if stored is None:
                return render(
                    request,
                    "scenarios/wizard.html",
                    {"title": _("اسم سناریو"), "hint": _("یک اسم انتخاب کنید و اگر خواستید عکس آیکون را از گوشی بردارید."), "mode": "name", "error": _("فقط تصویر کوچک JPG یا PNG از دستگاه خودتان انتخاب کنید."), "value": name},
                )
            icon_path = stored
        draft["name"] = name
        if icon_path:
            draft["icon_path"] = icon_path
        _save_draft(request, draft)
        return redirect(wizard_step(draft))
    return render(
        request,
        "scenarios/wizard.html",
        {"title": _("اسم سناریو"), "hint": _("این سناریو روی همین دستگاه می‌ماند. عکس آیکون از روی همین دستگاه خوانده می‌شود."), "mode": "name", "value": draft.get("name") or ""},
    )


def custom_edit(request, scenario_id):
    scenario = _owned_scenario(request, scenario_id)
    size = scenario.sizes.first()
    if not size:
        return redirect("custom_name")
    roles = list(size.roles.all())

    def names(side):
        return [role.name for role in roles if role.side == side]

    draft = {
        "edit_id": scenario.id,
        "name": scenario.name,
        "icon_path": scenario.icon.name if scenario.icon else "",
        "mafia_count": size.mafia_count,
        "mafia_names": names(SIDE_MAFIA),
        "citizen_count": size.citizen_count,
        "citizen_names": names(SIDE_CITIZEN),
        "has_independent": bool(size.independent_count),
        "independent_count": size.independent_count or None,
        "independent_names": names(SIDE_INDEPENDENT),
        "has_werewolf": bool(size.werewolf_count),
        "werewolf_count": size.werewolf_count or None,
        "werewolf_names": names(SIDE_WEREWOLF),
        "has_final_move": scenario.has_final_move,
        "has_death_lottery": scenario.has_death_lottery,
        "final_count": size.final_move_count if scenario.has_final_move else None,
        "final_names": [card.name for card in size.final_move_cards.all()],
    }
    _save_draft(request, draft)
    return redirect("custom_name")


@require_http_methods(["GET", "POST"])
def custom_mafia_count(request):
    bounce = _ensure_step(request, "custom_mafia_count")
    if bounce:
        return bounce
    return _count_page(request, "mafia_count", _("تعداد مافیا"), _("بازی شما چند تا مافیا دارد؟"), min_count=0, names_key="mafia_names")


@require_http_methods(["GET", "POST"])
def custom_mafia_names(request):
    return _names_page(request, "mafia_count", "mafia_names", _("نقش‌های مافیا"), _("به تعداد مافیا، اسم نقش‌ها را وارد کنید."), "custom_mafia_names")


@require_http_methods(["GET", "POST"])
def custom_citizen_count(request):
    bounce = _ensure_step(request, "custom_citizen_count")
    if bounce:
        return bounce
    return _count_page(request, "citizen_count", _("تعداد شهروند"), _("بازی شما چند شهروند دارد؟"), min_count=0, names_key="citizen_names")


@require_http_methods(["GET", "POST"])
def custom_citizen_names(request):
    return _names_page(request, "citizen_count", "citizen_names", _("نقش‌های شهروند"), _("به تعداد شهروند، اسم نقش‌ها را وارد کنید."), "custom_citizen_names")


@require_http_methods(["GET", "POST"])
def custom_extras(request):
    bounce = _ensure_step(request, "custom_extras")
    if bounce:
        return bounce
    draft = _draft(request)
    if request.method == "POST":
        draft["has_independent"] = request.POST.get("has_independent") == "1"
        draft["has_werewolf"] = request.POST.get("has_werewolf") == "1"
        if not draft["has_independent"]:
            draft["independent_count"] = 0
            draft["independent_names"] = []
        if not draft["has_werewolf"]:
            draft["werewolf_count"] = 0
            draft["werewolf_names"] = []
        if (draft.get("mafia_count") or 0) + (draft.get("citizen_count") or 0) == 0 and not draft["has_independent"] and not draft["has_werewolf"]:
            return render(
                request,
                "scenarios/wizard.html",
                {
                    "title": _("نقش‌های ویژه"),
                    "hint": _("اگر بازی شما مستقل یا گرگینه دارد، همان را انتخاب کنید."),
                    "mode": "extras",
                    "has_independent": draft.get("has_independent"),
                    "has_werewolf": draft.get("has_werewolf"),
                    "error": _("اگر مافیا و شهروند صفر است، مستقل یا گرگینه را انتخاب کنید."),
                },
            )
        _save_draft(request, draft)
        nxt = wizard_step(draft)
        return _finish(request, draft) if not nxt else redirect(nxt)
    return render(
        request,
        "scenarios/wizard.html",
        {
            "title": _("نقش‌های ویژه"),
            "hint": _("اگر بازی شما مستقل یا گرگینه دارد، همان را انتخاب کنید."),
            "mode": "extras",
            "has_independent": draft.get("has_independent"),
            "has_werewolf": draft.get("has_werewolf"),
        },
    )


@require_http_methods(["GET", "POST"])
def custom_independent_count(request):
    bounce = _ensure_step(request, "custom_independent_count")
    if bounce:
        return bounce
    return _count_page(request, "independent_count", _("تعداد مستقل"), _("چند نقش مستقل در بازی هست؟"))


@require_http_methods(["GET", "POST"])
def custom_independent_names(request):
    return _names_page(request, "independent_count", "independent_names", _("نقش‌های مستقل"), _("اسم نقش‌های مستقل را وارد کنید."), "custom_independent_names")


@require_http_methods(["GET", "POST"])
def custom_werewolf_count(request):
    bounce = _ensure_step(request, "custom_werewolf_count")
    if bounce:
        return bounce
    return _count_page(request, "werewolf_count", _("تعداد گرگینه"), _("چند نقش گرگینه در بازی هست؟"))


@require_http_methods(["GET", "POST"])
def custom_werewolf_names(request):
    return _names_page(request, "werewolf_count", "werewolf_names", _("نقش‌های گرگینه"), _("اسم نقش‌های گرگینه را وارد کنید."), "custom_werewolf_names")


@require_http_methods(["GET", "POST"])
def custom_tools(request):
    bounce = _ensure_step(request, "custom_tools")
    if bounce:
        return bounce
    draft = _draft(request)
    if request.method == "POST":
        draft["has_final_move"] = request.POST.get("has_final_move") == "1"
        draft["has_death_lottery"] = request.POST.get("has_death_lottery") == "1"
        if not draft["has_final_move"]:
            draft["final_count"] = None
            draft["final_names"] = []
        _save_draft(request, draft)
        nxt = wizard_step(draft)
        return _finish(request, draft) if not nxt else redirect(nxt)
    return render(
        request,
        "scenarios/wizard.html",
        {
            "title": _("ابزار میزبان"),
            "hint": _("اگر بازی شما کارت حرکت آخر یا قرعه مرگ دارد، همان را انتخاب کنید."),
            "mode": "tools",
            "has_final_move": draft.get("has_final_move"),
            "has_death_lottery": draft.get("has_death_lottery"),
        },
    )


@require_http_methods(["GET", "POST"])
def custom_final_count(request):
    bounce = _ensure_step(request, "custom_final_count")
    if bounce:
        return bounce
    return _count_page(request, "final_count", _("تعداد حرکت آخر"), _("چند کارت حرکت آخر در بازی هست؟"))


@require_http_methods(["GET", "POST"])
def custom_final_names(request):
    return _names_page(request, "final_count", "final_names", _("کارت‌های حرکت آخر"), _("اسم کارت‌های حرکت آخر را وارد کنید."), "custom_final_names")
