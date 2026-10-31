package ir.cafeclub.amytis

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONObject

class MainActivity : AppCompatActivity() {
    private lateinit var webView: WebView
    private lateinit var storeBilling: StoreBilling
    private var lastUrl: String = BuildConfig.START_URL
    private var showingOffline = false

    private val prefs by lazy { getSharedPreferences(PREFS, MODE_PRIVATE) }

    private val extraHeaders: Map<String, String>
        get() = mapOf("X-App-Source" to BuildConfig.APP_SOURCE)

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        lastUrl = prefs.getString(KEY_LAST_URL, BuildConfig.START_URL) ?: BuildConfig.START_URL
        webView = findViewById(R.id.web_view)
        storeBilling = StoreBilling(this) { token, error ->
            deliverPurchase(token, error)
        }
        configureWebView()
        onBackPressedDispatcher.addCallback(
            this,
            object : OnBackPressedCallback(true) {
                override fun handleOnBackPressed() {
                    if (!showingOffline && webView.canGoBack()) {
                        webView.goBack()
                    } else {
                        finish()
                    }
                }
            },
        )
        if (isOnline()) {
            loadSite(initialUrl())
        } else {
            showOffline()
        }
    }

    private fun configureWebView() {
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.settings.databaseEnabled = true
        webView.settings.cacheMode = WebSettings.LOAD_DEFAULT
        webView.settings.mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
        webView.settings.userAgentString =
            webView.settings.userAgentString +
            " CafeClub/${BuildConfig.VERSION_NAME} (Android; channel/${BuildConfig.APP_SOURCE}; ir.cafeclub.amytis)"
        webView.addJavascriptInterface(Bridge(), "CafeClub")
        webView.webViewClient =
            object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    val url = request.url?.toString().orEmpty()
                    if (url.startsWith("intent:") || url.startsWith("bazaar:") || url.startsWith("myket:")) {
                        return true
                    }
                    if (request.isForMainFrame && (url.startsWith("https://") || url.startsWith("http://"))) {
                        view.loadUrl(url, extraHeaders)
                        return true
                    }
                    return false
                }

                override fun onPageFinished(view: WebView, url: String) {
                    if (!isOfflineAsset(url)) {
                        showingOffline = false
                        rememberUrl(url)
                    }
                }

                override fun onReceivedError(
                    view: WebView,
                    request: WebResourceRequest,
                    error: WebResourceError,
                ) {
                    if (request.isForMainFrame) {
                        showOffline()
                    }
                }
            }
    }

    private fun initialUrl(): String {
        return if (prefs.getBoolean(KEY_SOURCE_BOUND, false)) lastUrl else BuildConfig.START_URL
    }

    private fun loadSite(url: String) {
        showingOffline = false
        webView.loadUrl(url, extraHeaders)
    }

    private fun rememberUrl(url: String) {
        if (url.isBlank() || isOfflineAsset(url) || url == "about:blank") {
            return
        }
        lastUrl = url
        prefs.edit()
            .putString(KEY_LAST_URL, url)
            .putBoolean(KEY_SOURCE_BOUND, true)
            .apply()
    }

    private fun showOffline() {
        showingOffline = true
        webView.loadUrl(OFFLINE_ASSET)
    }

    private fun retryLastPage() {
        if (!isOnline()) {
            showOffline()
            return
        }
        loadSite(lastUrl.ifBlank { BuildConfig.START_URL })
    }

    private fun isOnline(): Boolean {
        val manager = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = manager.activeNetwork ?: return false
        val caps = manager.getNetworkCapabilities(network) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        if (!storeBilling.handleActivityResult(requestCode, resultCode, data)) {
            super.onActivityResult(requestCode, resultCode, data)
        }
    }

    override fun onDestroy() {
        if (::storeBilling.isInitialized) {
            storeBilling.destroy()
        }
        super.onDestroy()
    }

    private fun deliverPurchase(token: String?, error: String?) {
        val tokenJs = if (token.isNullOrBlank()) "null" else JSONObject.quote(token)
        val errorJs = if (error.isNullOrBlank()) "null" else JSONObject.quote(error)
        webView.post {
            webView.evaluateJavascript(
                "window.CafeClubOnPurchase && CafeClubOnPurchase($tokenJs, $errorJs);",
                null,
            )
        }
    }

    inner class Bridge {
        @JavascriptInterface
        fun retry() {
            runOnUiThread { retryLastPage() }
        }

        @JavascriptInterface
        fun purchase(sku: String, payload: String) {
            runOnUiThread { storeBilling.purchase(sku, payload) }
        }

        @JavascriptInterface
        fun consume(token: String) {
            runOnUiThread { storeBilling.consume(token) }
        }
    }

    companion object {
        private const val PREFS = "cafeclub"
        private const val KEY_LAST_URL = "last_url"
        private const val KEY_SOURCE_BOUND = "source_bound"
        private const val OFFLINE_ASSET = "file:///android_asset/offline.html"

        private fun isOfflineAsset(url: String): Boolean {
            return url.startsWith("file:///android_asset/") || url.contains("/static/offline.html")
        }
    }
}
