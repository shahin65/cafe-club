package ir.cafeclub.amytis

import android.content.Intent
import androidx.appcompat.app.AppCompatActivity
import ir.cafebazaar.poolakey.Connection
import ir.cafebazaar.poolakey.Payment
import ir.cafebazaar.poolakey.config.PaymentConfiguration
import ir.cafebazaar.poolakey.config.SecurityCheck
import ir.cafebazaar.poolakey.request.PurchaseRequest

class StoreBilling(
    private val activity: AppCompatActivity,
    private val onResult: (token: String?, error: String?) -> Unit,
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
            onResult(null, error.message ?: "اتصال به کافه بازار برقرار نشد.")
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
        payment.getPurchasedProducts {
            querySucceed { purchases ->
                val owned = purchases.firstOrNull { it.productId == sku }
                if (owned != null && owned.purchaseToken.isNotBlank()) {
                    onResult(owned.purchaseToken, null)
                } else {
                    launchBuy(sku, payload)
                }
            }
            queryFailed {
                launchBuy(sku, payload)
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

    private fun launchBuy(sku: String, payload: String) {
        payment.purchaseProduct(
            registry = activity.activityResultRegistry,
            request = PurchaseRequest(productId = sku, payload = payload),
        ) {
            purchaseSucceed { purchase ->
                onResult(purchase.purchaseToken, null)
            }
            purchaseCanceled {
                onResult(null, "canceled")
            }
            purchaseFailed { error ->
                onResult(null, error.message ?: "پرداخت کافه بازار ناموفق بود.")
            }
            failedToBeginFlow { error ->
                onResult(null, error.message ?: "درگاه کافه بازار باز نشد.")
            }
        }
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
