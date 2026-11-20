from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import get_language

SIDE_MAFIA = "mafia"
SIDE_CITIZEN = "citizen"
SIDE_INDEPENDENT = "independent"
SIDE_WEREWOLF = "werewolf"
SIDE_VILLAGE = "village"

GUEST_SCENARIO_KEY = "custom_guest_key"

KIND_ADVANCED = "advanced"
KIND_NIGHT = "night"
KIND_WEREWOLF = "werewolf"

LARGE_KIND_CHOICES = [
    (KIND_ADVANCED, "پیشرفته"),
    (KIND_NIGHT, "شب مافیا"),
    (KIND_WEREWOLF, "گرگینه"),
]

SIDE_CHOICES = [
    (SIDE_MAFIA, "مافیا"),
    (SIDE_CITIZEN, "شهروند"),
    (SIDE_INDEPENDENT, "مستقل"),
    (SIDE_WEREWOLF, "گرگینه"),
    (SIDE_VILLAGE, "روستا"),
]

KIND_SIDES = {
    KIND_ADVANCED: (SIDE_MAFIA, SIDE_CITIZEN, SIDE_INDEPENDENT),
    KIND_NIGHT: (SIDE_MAFIA, SIDE_CITIZEN, SIDE_INDEPENDENT),
    KIND_WEREWOLF: (SIDE_WEREWOLF, SIDE_VILLAGE, SIDE_INDEPENDENT),
}

SIDE_FIELDS = {
    SIDE_MAFIA: "mafia_count",
    SIDE_CITIZEN: "citizen_count",
    SIDE_INDEPENDENT: "independent_count",
    SIDE_WEREWOLF: "werewolf_count",
}


def unique_scenario_slug(name, pk=None, suggested=""):
    suggested = (suggested or "").strip()
    if suggested and not suggested.isascii():
        suggested = ""
    base = slugify(suggested, allow_unicode=False) or slugify(name or "", allow_unicode=False)
    if not base:
        base = f"scenario-{pk}" if pk else "scenario"
    slug = base[:80]
    index = 2
    while True:
        clash = Scenario.objects.filter(slug=slug)
        if pk:
            clash = clash.exclude(pk=pk)
        if not clash.exists():
            return slug
        suffix = f"-{index}"
        slug = f"{base[: max(1, 80 - len(suffix))]}{suffix}"
        index += 1


class Scenario(models.Model):
    name = models.CharField(
        "اسم سناریو",
        max_length=120,
        help_text="مثلاً سناریو بازپرس",
        error_messages={"blank": "اسم سناریو را وارد کنید."},
    )
    name_en = models.CharField(
        "اسم انگلیسی سناریو",
        max_length=120,
        blank=True,
        help_text="برای صفحه انگلیسی رول‌بوک، قوانین و نتایج جستجو.",
    )
    slug = models.SlugField(
        "نامک آدرس",
        max_length=80,
        unique=True,
        allow_unicode=False,
        blank=True,
        help_text="شناسه لاتین داخلی. نشانی صفحات رول‌بوک و قوانین با شماره سناریو است تا روی هاست خطای Not Found ندهد.",
    )
    icon = models.ImageField(
        "آیکون سناریو",
        upload_to="scenario_icons",
        blank=True,
        help_text="این آیکون کنار اسم سناریو در صفحه اول دیده می‌شود.",
    )
    is_large = models.BooleanField(
        "سناریو تعداد بالا",
        default=False,
        help_text="در بخش تقسیم نقش سناریو تعداد بالا نشان داده می‌شود.",
    )
    large_kind = models.CharField(
        "نوع تعداد بالا",
        max_length=20,
        blank=True,
        choices=LARGE_KIND_CHOICES,
        help_text="پیشرفته، شب مافیا یا گرگینه.",
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
    play_count = models.PositiveIntegerField("تعداد بازی", default=0, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="سازنده",
        related_name="custom_scenarios",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="خالی یعنی سناریوی رسمی کافه. اگر پر باشد فقط همان کاربر آن را می‌بیند.",
    )
    guest_key = models.CharField(
        "کلید مهمان",
        max_length=64,
        blank=True,
        db_index=True,
        help_text="برای سناریوی دلخواه بدون حساب، به نشست مرورگر گره می‌خورد.",
    )
    rulebook_title_fa = models.CharField("عنوان رول‌بوک فارسی", max_length=160, blank=True)
    rulebook_title_en = models.CharField("عنوان رول‌بوک انگلیسی", max_length=160, blank=True)
    rulebook_body_fa = models.TextField(
        "متن رول‌بوک فارسی",
        blank=True,
        help_text="معرفی سناریو و رول‌بوک به فارسی. برای سئو متن کامل و واضح بنویسید.",
    )
    rulebook_body_en = models.TextField("متن رول‌بوک انگلیسی", blank=True)
    rulebook_meta_title_fa = models.CharField(
        "عنوان سئو رول‌بوک فارسی",
        max_length=70,
        blank=True,
        help_text="حدود ۶۰ نویسه. اگر خالی باشد از عنوان صفحه استفاده می‌شود.",
    )
    rulebook_meta_title_en = models.CharField("عنوان سئو رول‌بوک انگلیسی", max_length=70, blank=True)
    rulebook_meta_description_fa = models.CharField(
        "توضیح سئو رول‌بوک فارسی",
        max_length=170,
        blank=True,
        help_text="حدود ۱۵۵ نویسه برای نتایج جستجو.",
    )
    rulebook_meta_description_en = models.CharField("توضیح سئو رول‌بوک انگلیسی", max_length=170, blank=True)
    rules_title_fa = models.CharField("عنوان قوانین فارسی", max_length=160, blank=True)
    rules_title_en = models.CharField("عنوان قوانین انگلیسی", max_length=160, blank=True)
    rules_body_fa = models.TextField("متن قوانین فارسی", blank=True)
    rules_body_en = models.TextField("متن قوانین انگلیسی", blank=True)
    rules_meta_title_fa = models.CharField("عنوان سئو قوانین فارسی", max_length=70, blank=True)
    rules_meta_title_en = models.CharField("عنوان سئو قوانین انگلیسی", max_length=70, blank=True)
    rules_meta_description_fa = models.CharField("توضیح سئو قوانین فارسی", max_length=170, blank=True)
    rules_meta_description_en = models.CharField("توضیح سئو قوانین انگلیسی", max_length=170, blank=True)

    class Meta:
        verbose_name = "سناریو"
        verbose_name_plural = "سناریوها"
        ordering = ["home_order", "id"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.is_large and not self.large_kind:
            raise ValidationError({"large_kind": "نوع سناریو تعداد بالا را انتخاب کنید."})
        if (self.owner_id or self.guest_key) and self.is_featured:
            raise ValidationError({"is_featured": "سناریوی شخصی کاربر را نمی‌توان برای صفحه اول تأیید کرد."})
        if not self.is_featured:
            return
        others = Scenario.objects.filter(is_featured=True, owner__isnull=True, guest_key="")
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

    def is_custom(self):
        return bool(self.owner_id or self.guest_key)

    def large_sides(self):
        return KIND_SIDES.get(self.large_kind) or KIND_SIDES[KIND_ADVANCED]

    def can_be_managed_by(self, request):
        if not self.is_custom():
            return False
        if self.owner_id:
            return bool(request.user.is_authenticated and self.owner_id == request.user.id)
        return request.session.get(GUEST_SCENARIO_KEY) == self.guest_key

    def save(self, *args, **kwargs):
        from scenarios.html_safe import sanitize_page_html

        if self.owner_id or self.guest_key:
            self.is_featured = False
        if self.is_large:
            self.is_featured = False
            if self.large_kind == KIND_NIGHT:
                self.has_final_move = True
        self.slug = unique_scenario_slug(self.name, self.pk, self.slug)
        for field in (
            "rulebook_body_fa",
            "rulebook_body_en",
            "rules_body_fa",
            "rules_body_en",
        ):
            setattr(self, field, sanitize_page_html(getattr(self, field)))
        super().save(*args, **kwargs)

    def language_is_english(self):
        return False

    def pick_text(self, fa_value, en_value):
        fa_value = (fa_value or "").strip()
        en_value = (en_value or "").strip()
        if self.language_is_english():
            return en_value or fa_value
        return fa_value or en_value

    def display_name(self):
        return self.pick_text(self.name, self.name_en) or self.name

    def page_title(self, kind):
        title = self.pick_text(
            getattr(self, f"{kind}_title_fa"),
            getattr(self, f"{kind}_title_en"),
        )
        if title:
            return title
        if kind == "rulebook":
            return f"رول‌بوک {self.display_name()}" if not self.language_is_english() else f"{self.display_name()} rulebook"
        return f"قوانین {self.display_name()}" if not self.language_is_english() else f"{self.display_name()} rules"

    def page_body(self, kind):
        return self.pick_text(
            getattr(self, f"{kind}_body_fa"),
            getattr(self, f"{kind}_body_en"),
        )

    def page_body_html(self, kind):
        from scenarios.html_safe import sanitize_page_html

        return sanitize_page_html(self.page_body(kind))

    def page_meta_title(self, kind):
        custom = self.pick_text(
            getattr(self, f"{kind}_meta_title_fa"),
            getattr(self, f"{kind}_meta_title_en"),
        )
        return custom or f"{self.page_title(kind)} | کافه کلاب"

    def page_meta_description(self, kind):
        custom = self.pick_text(
            getattr(self, f"{kind}_meta_description_fa"),
            getattr(self, f"{kind}_meta_description_en"),
        )
        if custom:
            return custom
        from scenarios.html_safe import plain_page_text

        body = plain_page_text(self.page_body(kind))
        return body[:155] if body else self.page_title(kind)

    def has_indexable_page(self, kind):
        from scenarios.html_safe import plain_page_text

        return bool(
            plain_page_text(getattr(self, f"{kind}_body_fa", ""))
            or plain_page_text(getattr(self, f"{kind}_body_en", ""))
        )

    def get_rulebook_url(self):
        return reverse("scenario_rulebook", kwargs={"scenario_id": self.pk})

    def get_rules_url(self):
        return reverse("scenario_rules", kwargs={"scenario_id": self.pk})

    def get_comments_url(self):
        return reverse("scenario_comments", kwargs={"scenario_id": self.pk})

    def is_complete(self):
        if self.is_large:
            return self.catalog_roles.exists()
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


class CardBranding(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="کاربر",
        related_name="card_branding",
        on_delete=models.CASCADE,
    )
    preset = models.CharField("لوگوی آماده", max_length=20, blank=True)
    image = models.ImageField("لوگوی اختصاصی", upload_to="card_logos", blank=True)

    class Meta:
        verbose_name = "لوگوی پشت کارت"
        verbose_name_plural = "لوگوهای پشت کارت"

    def __str__(self):
        return self.user.get_username()


class ScenarioComment(models.Model):
    scenario = models.ForeignKey(
        Scenario,
        verbose_name="سناریو",
        related_name="comments",
        on_delete=models.CASCADE,
    )
    parent = models.ForeignKey(
        "self",
        verbose_name="پاسخ به",
        related_name="replies",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    author_name = models.CharField("نام نمایشی", max_length=40)
    body = models.TextField("متن نظر", max_length=1000)
    is_approved = models.BooleanField("تأییدشده", default=False)
    is_admin = models.BooleanField("پاسخ مدیریت", default=False)
    created_at = models.DateTimeField("زمان ارسال", auto_now_add=True)

    class Meta:
        verbose_name = "نظر کاربر"
        verbose_name_plural = "نظرهای کاربران"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.author_name}: {self.body[:40]}"

    def approved_replies(self):
        return self.replies.filter(is_approved=True).order_by("created_at", "id")


class CatalogRole(models.Model):
    scenario = models.ForeignKey(
        Scenario,
        verbose_name="سناریو",
        related_name="catalog_roles",
        on_delete=models.CASCADE,
    )
    side = models.CharField("ساید", max_length=20, choices=SIDE_CHOICES)
    name = models.CharField("اسم نقش", max_length=80)
    description = models.CharField("توضیح نقش", max_length=300, blank=True)
    allows_quantity = models.BooleanField(
        "تعدادپذیر",
        default=False,
        help_text="مثل مافیای ساده یا شهروند ساده که چند تا از آن در بازی باشد.",
    )
    sort_order = models.PositiveIntegerField("ترتیب", default=0)

    class Meta:
        verbose_name = "نقش کاتالوگ تعداد بالا"
        verbose_name_plural = "نقش‌های کاتالوگ تعداد بالا"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class CatalogFinalCard(models.Model):
    scenario = models.ForeignKey(
        Scenario,
        verbose_name="سناریو",
        related_name="catalog_finals",
        on_delete=models.CASCADE,
    )
    name = models.CharField("اسم کارت حرکت آخر", max_length=80)
    description = models.CharField("توضیحات کارت", max_length=300, blank=True)
    sort_order = models.PositiveIntegerField("ترتیب", default=0)

    class Meta:
        verbose_name = "کارت حرکت آخر تعداد بالا"
        verbose_name_plural = "کارت‌های حرکت آخر تعداد بالا"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name

