package ir.cafeclub.amytis

import android.content.Intent
import androidx.appcompat.app.AppCompatActivity
import ir.cafebazaar.poolakey.Connection
import ir.cafebazaar.poolakey.Payment
import ir.cafebazaar.poolakey.config.PaymentConfiguration
import ir.cafebazaar.poolakey.config.SecurityCheck
import ir.cafebazaar.poolakey.entity.PurchaseInfo
import ir.cafebazaar.poolakey.request.PurchaseRequest

class StoreBilling(
    private val activity: AppCompatActivity,
    private val onResult: (token: String?, error: String?, originalJson: String?, signature: String?) -> Unit,
) {
    private val payment = Payment(
        context = activity,
        config = PaymentConfiguration(
            localSecurityCheck = securityCheck(),
        ),
    )
    private var ready = false
    private var pending: Pair<String, String>? = null
    private val connection: Connection = payment.connect {
        connectionSucceed {
            ready = true
            pending?.let { queued ->
                pending = null
                purchase(queued.first, queued.second)
            }
        }
        connectionFailed { error ->
            ready = false
            fail(error.message)
        }
        disconnected {
            ready = false
        }
    }

    fun purchase(sku: String, payload: String) {
        if (!ready) {
            pending = sku to payload
            return
        }
        payment.getInAppSkuDetails(listOf(sku)) {
            getSkuDetailsSucceed { details ->
                if (details.none { it.sku == sku }) {
                    fail("این محصول در کافه بازار ثبت نشده است.")
                    return@getSkuDetailsSucceed
                }
                takeOwnedOrBuy(sku, payload)
            }
            getSkuDetailsFailed {
                takeOwnedOrBuy(sku, payload)
            }
        }
    }

    fun consume(token: String) {
        if (token.isBlank()) return
        payment.consumeProduct(token) {
            consumeSucceed { }
            consumeFailed { }
        }
    }

    fun handleActivityResult(
        @Suppress("UNUSED_PARAMETER") requestCode: Int,
        @Suppress("UNUSED_PARAMETER") resultCode: Int,
        @Suppress("UNUSED_PARAMETER") data: Intent?,
    ): Boolean = false

    fun destroy() {
        connection.disconnect()
    }

    private fun takeOwnedOrBuy(sku: String, payload: String) {
        payment.getPurchasedProducts {
            querySucceed { purchases ->
                val owned = purchases.firstOrNull { it.productId == sku }
                if (owned != null && owned.purchaseToken.isNotBlank()) {
                    succeed(owned)
                } else {
                    launchBuy(sku, payload)
                }
            }
            queryFailed {
                launchBuy(sku, payload)
            }
        }
    }

    private fun launchBuy(sku: String, payload: String) {
        payment.purchaseProduct(
            registry = activity.activityResultRegistry,
            request = PurchaseRequest(productId = sku, payload = payload),
        ) {
            purchaseSucceed { purchase ->
                succeed(purchase)
            }
            purchaseCanceled {
                onResult(null, "canceled", null, null)
            }
            purchaseFailed { error ->
                fail(error.message)
            }
            failedToBeginFlow { error ->
                fail(error.message ?: "درگاه کافه بازار باز نشد.")
            }
        }
    }

    private fun succeed(purchase: PurchaseInfo) {
        onResult(purchase.purchaseToken, null, purchase.originalJson, purchase.dataSignature)
    }

    private fun fail(raw: String?) {
        onResult(null, friendlyError(raw), null, null)
    }

    private fun friendlyError(raw: String?): String {
        val text = raw.orEmpty()
        val lower = text.lowercase()
        if (lower.contains("invalid_grant") || lower.contains("invalid grant")) {
            return "تأیید خرید کافه بازار انجام نشد. دوباره تلاش کنید."
        }
        if (lower.contains("not found") || lower.contains("item unavailable")) {
            return "این محصول در کافه بازار پیدا نشد."
        }
        return text.ifBlank { "پرداخت کافه بازار ناموفق بود." }
    }

    private fun securityCheck(): SecurityCheck {
        val rsa = BuildConfig.BAZAAR_RSA
        return if (rsa.isBlank()) {
            SecurityCheck.Disable
        } else {
            SecurityCheck.Enable(rsaPublicKey = rsa)
        }
    }
}
