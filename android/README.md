# کافه کلاب — کلاینت اندروید

سه خروجی با پکیج‌نیم مشترک `ir.cafeclub.amytis` از روی WebView ساخته می‌شود (نه TWA)، تا هدر `X-App-Source` و بازگشت به آخرین صفحه بعد از آفلاین روی همه درخواست‌ها کار کند.

## ورود اول هر کانال

| Flavor | START_URL | APP_SOURCE |
| --- | --- | --- |
| `direct` | `https://cafeclub.amytisapp.ir/app/direct/` | `direct` |
| `bazaar` | `https://cafeclub.amytisapp.ir/app/bazaar/` | `bazaar` |
| `myket` | `https://cafeclub.amytisapp.ir/app/myket/` | `myket` |

## ساینینگ

1. فایل `key.properties.example` را به `android/key.properties` کپی کنید.
2. مسیر keystore و رمزها را در همان فایل بگذارید. این فایل گیت نمی‌شود.
3. یک keystore بسازید (یک‌بار برای هر سه فروشگاه):

```text
keytool -genkeypair -v -keystore cafeclub-release.jks -alias cafeclub -keyalg RSA -keysize 2048 -validity 10000
```

## سینک در Android Studio

1. File → Open → پوشه `android` همین ریپو را انتخاب کنید (نه ریشه Django).
2. اگر SDK پرسیده شد، مسیر Android SDK را تأیید کنید تا `local.properties` ساخته شود.
3. File → Sync Project with Gradle Files
4. Build Variants را باز کنید و یکی از این‌ها را انتخاب کنید:
   - `directDebug` / `directRelease`
   - `bazaarDebug` / `bazaarRelease`
   - `myketDebug` / `myketRelease`
5. خروجی:

```text
./gradlew :app:assembleDirectRelease
./gradlew :app:assembleBazaarRelease
./gradlew :app:assembleMyketRelease
```

APKها در `app/build/outputs/apk/<flavor>/release/` ساخته می‌شوند.

## آیکون

جای‌گذاری نهایی:

- مشترک: `app/src/main/res/mipmap-*`
- اختصاصی هر کانال: `app/src/<flavor>/res/mipmap-xxxhdpi/ic_launcher.png` و `ic_launcher_round.png`

آیکون Cafe Club در منابع مشترک قرار دارد و هر سه کانال از آن استفاده می‌کنند.
اندازه‌های آیکون معمولی و گرد برای mdpi تا xxxhdpi به‌ترتیب 48، 72، 96، 144 و 192 پیکسل است.
آیکون تطبیقی نیز foreground مشترک با فضای امن اطراف تصویر دارد.

برای ساخت از JDK 21 استفاده کنید؛ ابزار lint این نسخه پروژه با JDK 25 سازگار نیست.
در سیستم فعلی، پیش از اجرای دستورهای ساخت در PowerShell:

```powershell
$env:JAVA_HOME = "$env:USERPROFILE\.jdks\jbr-21.0.11"
.\gradlew.bat :app:assembleDirectRelease :app:assembleBazaarRelease :app:assembleMyketRelease
```

بدون `key.properties` خروجی Release با پسوند `-unsigned.apk` ساخته می‌شود؛
برای نصب یا انتشار باید با keystore اصلی برنامه امضا شود.

## خرید درون‌برنامه‌ای

کلیدهای OAuth بازار (`BAZAAR_CLIENT_ID` و …) فقط برای تایید سمت سرور در `.env` هستند.
خرید واقعی با SKU داخل اپ اندروید باز می‌شود:

- نسخه `bazaar`: درگاه کافه بازار (Poolakey) با قیمت محصول ثبت‌شده در پیشخوان بازار
- نسخه `myket`: درگاه مایکت با قیمت محصول ثبت‌شده در پیشخوان مایکت
- نسخه `direct`: ریدایرکت به بیت‌پی با مبلغ همان پلن

کلید RSA عمومی هر فروشگاه را در `key.properties` بگذارید (`bazaarRsa` / `myketRsa`)، نه در `.env`.
شناسه محصولات باید با SKU سرور یکی باشد: `ad_bronze`، `ad_silver`، `ad_gold`، `venue_bronze`، `venue_silver`، `venue_gold`.
