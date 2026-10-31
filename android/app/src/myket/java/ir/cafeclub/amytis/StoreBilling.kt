package ir.cafeclub.amytis

import android.content.Intent
import androidx.appcompat.app.AppCompatActivity
import ir.myket.billingclient.IabHelper
import ir.myket.billingclient.util.IabResult
import ir.myket.billingclient.util.Inventory
import ir.myket.billingclient.util.Purchase

class StoreBilling(
    private val activity: AppCompatActivity,
    private val onResult: (token: String?, error: String?) -> Unit,
) {
    private val helper = IabHelper(activity, BuildConfig.MYKET_RSA)
    private var ready = false
    private var pending: Pair<String, String>? = null

    init {
        helper.startSetup { result: IabResult ->
            if (result.isSuccess) {
                ready = true
                pending?.let { queued ->
                    pending = null
                    purchase(queued.first, queued.second)
                }
            } else {
                onResult(null, result.message ?: "اتصال به مایکت برقرار نشد.")
            }
        }
    }

    fun purchase(sku: String, payload: String) {
        if (!ready) {
            pending = sku to payload
            return
        }
        try {
            helper.queryInventoryAsync(true, listOf(sku)) { result: IabResult, inventory: Inventory? ->
                if (result.isSuccess && inventory != null) {
                    val owned = inventory.getPurchase(sku)
                    val token = owned?.token
                    if (!token.isNullOrBlank()) {
                        onResult(token, null)
                        return@queryInventoryAsync
                    }
                }
                launchBuy(sku, payload)
            }
        } catch (exc: Exception) {
            launchBuy(sku, payload)
        }
    }

    fun consume(token: String) {
        if (token.isBlank() || !ready) return
        try {
            helper.queryInventoryAsync(false) { result: IabResult, inventory: Inventory? ->
                if (!result.isSuccess || inventory == null) return@queryInventoryAsync
                val owned = inventory.allPurchases.firstOrNull { it.token == token } ?: return@queryInventoryAsync
                helper.consumeAsync(owned) { _, _ -> }
            }
        } catch (_: Exception) {
        }
    }

    fun handleActivityResult(
        @Suppress("UNUSED_PARAMETER") requestCode: Int,
        @Suppress("UNUSED_PARAMETER") resultCode: Int,
        @Suppress("UNUSED_PARAMETER") data: Intent?,
    ): Boolean = false

    fun destroy() {
        try {
            helper.dispose()
        } catch (_: Exception) {
        }
    }

    private fun launchBuy(sku: String, payload: String) {
        try {
            helper.launchPurchaseFlow(activity, sku, { result: IabResult, purchase: Purchase? ->
                val token = purchase?.token
                if (result.isSuccess && !token.isNullOrBlank()) {
                    onResult(token, null)
                    return@launchPurchaseFlow
                }
                val message = result.message ?: ""
                if (result.response == IabHelper.IABHELPER_USER_CANCELLED ||
                    result.response == IabHelper.BILLING_RESPONSE_RESULT_USER_CANCELED ||
                    message.contains("cancel", ignoreCase = true) ||
                    message.contains("لغو")
                ) {
                    onResult(null, "canceled")
                } else {
                    onResult(null, message.ifBlank { "درگاه مایکت باز نشد." })
                }
            }, payload)
        } catch (exc: Exception) {
            onResult(null, exc.message ?: "درگاه مایکت باز نشد.")
        }
    }
}
