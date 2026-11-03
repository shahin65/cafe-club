package ir.cafeclub.amytis

import android.content.Intent
import androidx.appcompat.app.AppCompatActivity

class StoreBilling(
    @Suppress("UNUSED_PARAMETER") activity: AppCompatActivity,
    private val onResult: (token: String?, error: String?, originalJson: String?, signature: String?) -> Unit,
) {
    fun purchase(sku: String, payload: String) {
        onResult(null, "این نسخه از درگاه بیت‌پی در سایت استفاده می‌کند.", null, null)
    }

    fun consume(@Suppress("UNUSED_PARAMETER") token: String) {}

    fun handleActivityResult(
        @Suppress("UNUSED_PARAMETER") requestCode: Int,
        @Suppress("UNUSED_PARAMETER") resultCode: Int,
        @Suppress("UNUSED_PARAMETER") data: Intent?,
    ): Boolean = false

    fun destroy() {}
}
