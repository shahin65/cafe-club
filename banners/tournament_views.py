from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from banners.models import Tournament, TournamentPlayer
from banners.tournament import (
    MAX_OPEN,
    MAX_PLAYERS,
    MAX_PRIZES,
    MIN_PLAYERS,
    MIN_PRIZES,
    STAGE_META,
    WIZARD_KEY,
    advance_players,
    can_create_tournament,
    close_tournament,
    draw_assignments,
    draw_final_seats,
    ensure_guest_key,
    place_label,
    read_int,
    read_names,
    save_round,
    selected_player_ids,
)


def _draft(request):
    return request.session.get(WIZARD_KEY) or {}


def _save_draft(request, data):
    request.session[WIZARD_KEY] = data
    request.session.modified = True


def _clear_draft(request):
    request.session.pop(WIZARD_KEY, None)


def _managed(request, tournament_id):
    tournament = get_object_or_404(Tournament, pk=tournament_id, ended_at__isnull=True)
    if not tournament.can_manage(request):
        raise Http404
    return tournament


def _guard_create(request):
    if can_create_tournament(request):
        return None
    messages.error(request, _("حداکثر سه تورنومنت همزمان می‌توانید داشته باشید. یکی را تمام یا حذف کنید."))
    return redirect("home")


def _wizard(request, step):
    blocked = _guard_create(request)
    if blocked:
        return blocked
    draft = _draft(request)
    name = (draft.get("name") or "").strip()
    count = draft.get("count")
    names = draft.get("names") or []
    prize_count = draft.get("prize_count")
    if step != "name" and not name:
        return redirect("tournament_create")
    if step in {"names", "prize_count", "prizes"} and not count:
        return redirect("tournament_count")
    if step in {"prize_count", "prizes"} and len(names) != count:
        return redirect("tournament_names")
    if step == "prizes" and not prize_count:
        return redirect("tournament_prize_count")
    return None


@require_http_methods(["GET", "POST"])
def create_name(request):
    blocked = _guard_create(request)
    if blocked:
        return blocked
    if request.GET.get("fresh"):
        _clear_draft(request)
    draft = _draft(request)
    error = ""
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()[:120]
        if not name:
            error = _("اسم تورنومنت را بنویسید.")
        else:
            draft["name"] = name
            _save_draft(request, draft)
            return redirect("tournament_count")
    return render(
        request,
        "banners/tournament_wizard.html",
        {
            "title": _("اسم تورنومنت"),
            "hint": _("یک نام برای تورنومنت انتخاب کنید."),
            "mode": "name",
            "value": draft.get("name") or "",
            "error": error,
        },
    )


@require_http_methods(["GET", "POST"])
def create_count(request):
    blocked = _wizard(request, "count")
    if blocked:
        return blocked
    draft = _draft(request)
    error = ""
    if request.method == "POST":
        count = read_int(request.POST.get("count"), MIN_PLAYERS, MAX_PLAYERS)
        if count is None:
            error = _("تعداد شرکت‌کننده‌ها باید بین ۴ تا ۸۰ باشد.")
        else:
            draft["count"] = count
            draft["names"] = (draft.get("names") or [])[:count]
            _save_draft(request, draft)
            return redirect("tournament_names")
    return render(
        request,
        "banners/tournament_wizard.html",
        {
            "title": _("تعداد شرکت‌کننده‌ها"),
            "hint": _("چند نفر در تورنومنت بازی می‌کنند؟"),
            "mode": "count",
            "value": draft.get("count") or "",
            "min_count": MIN_PLAYERS,
            "max_count": MAX_PLAYERS,
            "error": error,
        },
    )


@require_http_methods(["GET", "POST"])
def create_names(request):
    blocked = _wizard(request, "names")
    if blocked:
        return blocked
    draft = _draft(request)
    count = draft["count"]
    stored = draft.get("names") or []
    error = ""
    if request.method == "POST":
        names = read_names(request, count)
        if not names:
            error = _("اسم همه شرکت‌کننده‌ها را بنویسید.")
        else:
            draft["names"] = names
            _save_draft(request, draft)
            return redirect("tournament_prize_count")
        stored = [(request.POST.get(f"name_{index}") or "") for index in range(count)]
    fields = [{"index": index, "value": stored[index] if index < len(stored) else ""} for index in range(count)]
    return render(
        request,
        "banners/tournament_wizard.html",
        {
            "title": _("اسم شرکت‌کننده‌ها"),
            "hint": _("به تعداد نفرات، اسم وارد کنید."),
            "mode": "names",
            "field_label": _("شرکت‌کننده"),
            "fields": fields,
            "error": error,
        },
    )


@require_http_methods(["GET", "POST"])
def create_prize_count(request):
    blocked = _wizard(request, "prize_count")
    if blocked:
        return blocked
    draft = _draft(request)
    error = ""
    max_prizes = min(MAX_PRIZES, max(MIN_PRIZES, draft["count"] - 1))
    if request.method == "POST":
        prize_count = read_int(request.POST.get("count"), MIN_PRIZES, max_prizes)
        if prize_count is None:
            error = _("تعداد جوایز را درست وارد کنید.")
        else:
            draft["prize_count"] = prize_count
            draft["prizes"] = (draft.get("prizes") or [])[:prize_count]
            _save_draft(request, draft)
            return redirect("tournament_prizes")
    return render(
        request,
        "banners/tournament_wizard.html",
        {
            "title": _("تعداد جوایز"),
            "hint": _("چند نفر برتر جایزه می‌گیرند؟"),
            "mode": "count",
            "value": draft.get("prize_count") or "",
            "min_count": MIN_PRIZES,
            "max_count": max_prizes,
            "error": error,
        },
    )


@require_http_methods(["GET", "POST"])
def create_prizes(request):
    blocked = _wizard(request, "prizes")
    if blocked:
        return blocked
    draft = _draft(request)
    count = draft["prize_count"]
    stored = draft.get("prizes") or []
    error = ""
    if request.method == "POST":
        prizes = read_names(request, count, prefix="prize")
        if not prizes:
            error = _("جایزه هر نفر برتر را بنویسید.")
        elif not can_create_tournament(request):
            return _guard_create(request)
        else:
            if request.user.is_authenticated:
                owner = request.user
                guest_key = ""
            else:
                owner = None
                guest_key = ensure_guest_key(request)
            tournament = Tournament.objects.create(
                owner=owner,
                guest_key=guest_key,
                name=draft["name"],
                prizes=prizes,
            )
            TournamentPlayer.objects.bulk_create(
                [TournamentPlayer(tournament=tournament, name=name) for name in draft["names"]]
            )
            _clear_draft(request)
            return redirect("tournament_manage", tournament.id)
        stored = [(request.POST.get(f"prize_{index}") or "") for index in range(count)]
    fields = [
        {
            "index": index,
            "label": place_label(index + 1),
            "value": stored[index] if index < len(stored) else "",
        }
        for index in range(count)
    ]
    return render(
        request,
        "banners/tournament_wizard.html",
        {
            "title": _("جوایز نفرات برتر"),
            "hint": _("مثلاً برای نفر اول بنویسید ۱۰ میلیون تومان."),
            "mode": "prizes",
            "fields": fields,
            "error": error,
        },
    )


def _manage_context(request, tournament, error=""):
    last = tournament.latest_round()
    next_kind = request.GET.get("next") if last and not getattr(last, "is_final", False) else ""
    if next_kind not in {"round2", "semi", "final"}:
        next_kind = ""
    return {
        "tournament": tournament,
        "active_players": list(tournament.active_players()),
        "active_count": tournament.active_players().count(),
        "last_round": last,
        "next_kind": next_kind,
        "next_title": STAGE_META[next_kind]["title"] if next_kind else "",
        "next_is_final": bool(next_kind and STAGE_META[next_kind]["final"]),
        "has_winners": tournament.winners().exists(),
        "error": error,
        "prize_fields": [
            {"index": index, "label": place_label(index + 1), "prize": prize}
            for index, prize in enumerate(tournament.prizes or [])
        ],
    }


def _draw_first(request, tournament):
    if tournament.rounds.exists():
        return _("دور اول قبلاً قرعه شده است.")
    players = list(tournament.active_players())
    group_count = read_int(request.POST.get("group_count"), 1, 20)
    group_size = read_int(request.POST.get("group_size"), 2, 20)
    if group_count is None or group_size is None:
        return _("تعداد گروه و نفرات هر گروه را وارد کنید.")
    assignments = draw_assignments(players, group_count, group_size)
    if assignments is None:
        return _("حاصل‌ضرب تعداد گروه در نفرات هر گروه باید با تعداد افراد حاضر یکی باشد.")
    save_round(tournament, "round1", group_count, group_size, assignments)
    tournament.status = Tournament.STATUS_ACTIVE
    tournament.save(update_fields=["status"])
    return ""


def _draw_next(request, tournament):
    last = tournament.latest_round()
    if not last or last.is_final:
        return _("الان نمی‌توانید دور بعدی بسازید.")
    kind = request.POST.get("kind") or ""
    if kind not in {"round2", "semi", "final"}:
        return _("نوع دور را انتخاب کنید.")
    allowed = {player.id for player in tournament.active_players()}
    selected = selected_player_ids(request, allowed)
    if len(selected) < max(2, tournament.prize_count()):
        return _("صعودی‌ها را مشخص کنید.")
    advance_players(tournament, selected)
    players = list(tournament.active_players())
    if kind == "final":
        assignments = draw_final_seats(players)
        save_round(tournament, kind, 1, len(players), assignments)
        return ""
    group_count = read_int(request.POST.get("group_count"), 1, 20)
    group_size = read_int(request.POST.get("group_size"), 2, 20)
    if group_count is None or group_size is None:
        return _("تعداد گروه و نفرات هر گروه را وارد کنید.")
    assignments = draw_assignments(players, group_count, group_size)
    if assignments is None:
        return _("حاصل‌ضرب تعداد گروه در نفرات هر گروه باید با تعداد افراد حاضر یکی باشد.")
    save_round(tournament, kind, group_count, group_size, assignments)
    return ""


def _set_winners(request, tournament):
    last = tournament.latest_round()
    if not last or not last.is_final:
        return _("اول فینال را بسازید.")
    remaining = list(tournament.active_players())
    remaining_ids = {player.id for player in remaining}
    chosen = []
    for index in range(tournament.prize_count()):
        value = read_int(request.POST.get(f"place_{index}"), 1, 10**9)
        if value is None or value not in remaining_ids or value in chosen:
            return _("نفرات برتر را بدون تکرار انتخاب کنید.")
        chosen.append(value)
    lookup = {player.id: player for player in remaining}
    winners = []
    for index, player_id in enumerate(chosen, start=1):
        player = lookup[player_id]
        player.place = index
        winners.append(player)
    TournamentPlayer.objects.bulk_update(winners, ["place"])
    return ""


@require_http_methods(["GET", "POST"])
def manage(request, tournament_id):
    tournament = _managed(request, tournament_id)
    error = ""
    if request.method == "POST":
        action = request.POST.get("action") or ""
        if action == "draw_1":
            error = _draw_first(request, tournament)
        elif action == "next_stage":
            error = _draw_next(request, tournament)
        elif action == "set_winners":
            error = _set_winners(request, tournament)
        elif action == "end":
            close_tournament(tournament)
            messages.success(request, _("تورنومنت به پایان رسید."))
            return redirect("home")
        else:
            error = _("این گزینه معتبر نیست.")
        if not error:
            last = tournament.latest_round()
            if action == "set_winners":
                return redirect("tournament_winners", tournament.id)
            if last and last.is_final:
                return redirect("tournament_seats", tournament.id, last.number)
            if last:
                return redirect("tournament_groups", tournament.id, last.number)
            return redirect("tournament_manage", tournament.id)
    return render(request, "banners/tournament_manage.html", _manage_context(request, tournament, error))


@require_POST
def delete_tournament(request, tournament_id):
    tournament = _managed(request, tournament_id)
    tournament.delete()
    messages.success(request, _("تورنومنت از فهرست حذف شد."))
    return redirect("home")


def _board_round(tournament_id, number):
    tournament = get_object_or_404(Tournament, pk=tournament_id, ended_at__isnull=True)
    round_row = tournament.latest_round(number)
    if not round_row:
        raise Http404
    return tournament, round_row


@require_GET
def groups_board(request, tournament_id, number):
    tournament, round_row = _board_round(tournament_id, number)
    return render(
        request,
        "banners/tournament_board.html",
        {
            "tournament": tournament,
            "round": round_row,
            "groups": round_row.grouped_seats(),
            "can_manage": tournament.can_manage(request),
        },
    )


@require_GET
def seats_board(request, tournament_id, number):
    return groups_board(request, tournament_id, number)


@require_GET
def winners_board(request, tournament_id):
    tournament = get_object_or_404(Tournament, pk=tournament_id, ended_at__isnull=True)
    winners = list(tournament.winners())
    if not winners:
        if tournament.can_manage(request):
            return redirect("tournament_manage", tournament.id)
        raise Http404
    rows = []
    prizes = tournament.prizes or []
    for winner in winners:
        prize = prizes[winner.place - 1] if winner.place and winner.place <= len(prizes) else ""
        rows.append({"player": winner, "label": place_label(winner.place), "prize": prize, "place": winner.place})
    return render(
        request,
        "banners/tournament_winners.html",
        {
            "tournament": tournament,
            "rows": rows,
            "can_manage": tournament.can_manage(request),
        },
    )
