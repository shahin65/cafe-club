import random
from uuid import uuid4

from django.db.models import Count
from django.utils import timezone

from banners.models import Tournament, TournamentPlayer, TournamentRound, TournamentSeat

GUEST_KEY = "custom_guest_key"
WIZARD_KEY = "tournament_wizard"
MIN_PLAYERS = 4
MAX_PLAYERS = 80
MIN_PRIZES = 1
MAX_PRIZES = 8
MAX_OPEN = 3
PLACE_WORDS = ["اول", "دوم", "سوم", "چهارم", "پنجم", "ششم", "هفتم", "هشتم"]

STAGE_META = {
    "round1": {"title": "دور اول", "final": False},
    "round2": {"title": "دور دوم", "final": False},
    "semi": {"title": "نیمه نهایی", "final": False},
    "final": {"title": "فینال", "final": True},
}


def place_label(index):
    if 1 <= index <= len(PLACE_WORDS):
        return f"نفر {PLACE_WORDS[index - 1]}"
    return f"نفر {index}"


def ensure_guest_key(request):
    key = request.session.get(GUEST_KEY)
    if not key:
        key = uuid4().hex
        request.session[GUEST_KEY] = key
        request.session.modified = True
    return key


def owned_tournaments(request):
    if request.user.is_authenticated:
        queryset = Tournament.objects.filter(owner=request.user)
    else:
        key = request.session.get(GUEST_KEY) or ""
        if not key:
            return Tournament.objects.none()
        queryset = Tournament.objects.filter(owner__isnull=True, guest_key=key)
    return queryset.filter(ended_at__isnull=True).annotate(player_count=Count("players"))


def open_count(request):
    return owned_tournaments(request).count()


def can_create_tournament(request):
    return open_count(request) < MAX_OPEN


def read_int(value, minimum, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if minimum <= number <= maximum:
        return number
    return None


def read_names(request, count, prefix="name"):
    names = []
    for index in range(count):
        name = (request.POST.get(f"{prefix}_{index}") or "").strip()[:80]
        if not name:
            return None
        names.append(name)
    return names


def draw_assignments(players, group_count, group_size):
    if group_count < 1 or group_size < 1:
        return None
    if len(players) != group_count * group_size:
        return None
    shuffled = list(players)
    random.shuffle(shuffled)
    seats = []
    for index, player in enumerate(shuffled):
        seats.append((player, index // group_size + 1, index % group_size + 1))
    return seats


def draw_final_seats(players):
    shuffled = list(players)
    random.shuffle(shuffled)
    return [(player, 1, index + 1) for index, player in enumerate(shuffled)]


def next_round_number(tournament):
    last = tournament.rounds.order_by("-number").first()
    return (last.number + 1) if last else 1


def save_round(tournament, kind, group_count, group_size, assignments):
    meta = STAGE_META[kind]
    round_row = TournamentRound.objects.create(
        tournament=tournament,
        number=next_round_number(tournament),
        kind=kind,
        title=meta["title"],
        group_count=group_count,
        group_size=group_size,
        is_final=meta["final"],
    )
    TournamentSeat.objects.bulk_create(
        [
            TournamentSeat(round=round_row, player=player, group_index=group, seat_number=seat)
            for player, group, seat in assignments
        ]
    )
    return round_row


def advance_players(tournament, selected_ids):
    keep = set(selected_ids)
    changed = []
    for player in tournament.active_players():
        if player.id not in keep:
            player.is_active = False
            changed.append(player)
    if changed:
        TournamentPlayer.objects.bulk_update(changed, ["is_active"])
    return len(keep)


def selected_player_ids(request, allowed):
    selected = []
    for raw in request.POST.getlist("advance"):
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value in allowed:
            selected.append(value)
    return selected


def close_tournament(tournament):
    tournament.ended_at = timezone.now()
    tournament.save(update_fields=["ended_at"])
