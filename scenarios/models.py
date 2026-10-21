from django.core.exceptions import ValidationError
from django.db import models

SIDE_MAFIA = "mafia"
SIDE_CITIZEN = "citizen"
SIDE_INDEPENDENT = "independent"
SIDE_WEREWOLF = "werewolf"

SIDE_CHOICES = [
    (SIDE_MAFIA, "مافیا"),
    (SIDE_CITIZEN, "شهروند"),
    (SIDE_INDEPENDENT, "مستقل"),
    (SIDE_WEREWOLF, "گرگینه"),
]

SIDE_FIELDS = {
    SIDE_MAFIA: "mafia_count",
    SIDE_CITIZEN: "citizen_count",
    SIDE_INDEPENDENT: "independent_count",
    SIDE_WEREWOLF: "werewolf_count",
}


class Scenario(models.Model):
    name = models.CharField(
        "اسم سناریو",
        max_length=120,
        help_text="مثلاً سناریو بازپرس",
        error_messages={"blank": "اسم سناریو را وارد کنید."},
    )
    icon = models.ImageField(
        "آیکون سناریو",
        upload_to="scenario_icons",
        blank=True,
        help_text="این آیکون کنار اسم سناریو در بخش تقسیم نقش سریع صفحه اول دیده می‌شود.",
    )
    has_final_move = models.BooleanField(
        "کارت حرکت آخر دارد",
        default=False,
        help_text="اگر فعال باشد، برای هر حالت تعداد باید کارت‌های حرکت آخر را هم تعریف کنید.",
    )
    has_death_lottery = models.BooleanField("قرعه مرگ دارد", default=False)
    is_featured = models.BooleanField(
        "تأیید برای صفحه اول",
        default=False,
        help_text="حداکثر ۶ سناریوی کامل را می‌توان برای صفحه اول تأیید کرد.",
    )
    home_order = models.PositiveIntegerField(
        "ترتیب در صفحه اول",
        default=0,
        help_text="عدد کوچکتر زودتر نشان داده می‌شود.",
    )

    class Meta:
        verbose_name = "سناریو"
        verbose_name_plural = "سناریوها"
        ordering = ["home_order", "id"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if not self.is_featured:
            return
        others = Scenario.objects.filter(is_featured=True)
        if self.pk:
            others = others.exclude(pk=self.pk)
        if others.count() >= 6:
            raise ValidationError(
                {
                    "is_featured": "سقف صفحه اول ۶ سناریو است. برای تأیید این مورد، تأیید یکی از سناریوهای قبلی را بردارید."
                }
            )
        if self.pk and not self.is_complete():
            raise ValidationError(
                {
                    "is_featured": "تأیید انجام نشد چون نقش‌های این سناریو هنوز کامل نیست. تعداد تأییدها به سه محدود نیست؛ هر سناریوی کامل، تا سقف ۶ تا، قابل تأیید است."
                }
            )

    def is_complete(self):
        sizes = list(self.sizes.all())
        if not 1 <= len(sizes) <= 5:
            return False
        for size in sizes:
            if not size.counts_match_players():
                return False
            if not size.roles_match_counts():
                return False
            if self.has_final_move and not size.final_moves_match_count():
                return False
        return True


class ScenarioSize(models.Model):
    scenario = models.ForeignKey(
        Scenario,
        verbose_name="سناریو",
        related_name="sizes",
        on_delete=models.CASCADE,
    )
    player_count = models.PositiveSmallIntegerField(
        "تعداد نفرات",
        help_text="مثلاً ۱۰ برای حالت ده‌نفره.",
        error_messages={"invalid": "تعداد نفرات باید یک عدد درست باشد."},
    )
    mafia_count = models.PositiveSmallIntegerField("تعداد مافیا", default=0)
    citizen_count = models.PositiveSmallIntegerField("تعداد شهروند", default=0)
    independent_count = models.PositiveSmallIntegerField("تعداد مستقل", default=0)
    werewolf_count = models.PositiveSmallIntegerField("تعداد گرگینه", default=0)
    final_move_count = models.PositiveSmallIntegerField(
        "تعداد کارت حرکت آخر",
        null=True,
        blank=True,
        help_text="فقط وقتی سناریو کارت حرکت آخر دارد لازم است.",
    )

    class Meta:
        verbose_name = "حالت تعداد نفرات"
        verbose_name_plural = "حالت‌های تعداد نفرات"
        ordering = ["player_count", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["scenario", "player_count"],
                name="unique_scenario_player_count",
            )
        ]

    def __str__(self):
        return f"{self.player_count} نفره"

    def side_total(self):
        return (
            self.mafia_count
            + self.citizen_count
            + self.independent_count
            + self.werewolf_count
        )

    def counts_match_players(self):
        return self.player_count and self.side_total() == self.player_count

    def roles_match_counts(self):
        roles = list(self.roles.all())
        for side, field in SIDE_FIELDS.items():
            expected = getattr(self, field)
            actual = sum(1 for role in roles if role.side == side)
            if actual != expected:
                return False
        return True

    def final_moves_match_count(self):
        if not self.final_move_count:
            return False
        return self.final_move_cards.count() == self.final_move_count


class Role(models.Model):
    size = models.ForeignKey(
        ScenarioSize,
        verbose_name="حالت تعداد",
        related_name="roles",
        on_delete=models.CASCADE,
    )
    side = models.CharField("ساید", max_length=20, choices=SIDE_CHOICES)
    name = models.CharField(
        "اسم نقش",
        max_length=80,
        error_messages={"blank": "اسم نقش را وارد کنید."},
    )
    description = models.CharField(
        "توضیح نقش",
        max_length=300,
        blank=True,
        help_text="متن کوتاهی که با دکمه توضیحات نقش روی کارت نقش باز می‌شود.",
    )
    icon = models.ImageField(
        "آیکون نقش",
        upload_to="role_icons",
        blank=True,
        help_text="اسم و این آیکون روی کارت نقش دیده می‌شود.",
    )

    class Meta:
        verbose_name = "نقش"
        verbose_name_plural = "نقش‌ها"
        ordering = ["id"]

    def __str__(self):
        return self.name


class FinalMoveCard(models.Model):
    size = models.ForeignKey(
        ScenarioSize,
        verbose_name="حالت تعداد",
        related_name="final_move_cards",
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        "اسم کارت حرکت آخر",
        max_length=80,
        error_messages={"blank": "اسم کارت حرکت آخر را وارد کنید."},
    )
    description = models.CharField("توضیحات کارت", max_length=300, blank=True)
    sort_order = models.PositiveIntegerField("ترتیب", default=0)

    class Meta:
        verbose_name = "کارت حرکت آخر"
        verbose_name_plural = "کارت‌های حرکت آخر"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name
