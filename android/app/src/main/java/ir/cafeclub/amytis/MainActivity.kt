package ir.cafeclub.amytis

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import org.json.JSONObject

class MainActivity : AppCompatActivity() {
    private lateinit var webView: WebView
    private lateinit var storeBilling: StoreBilling
    private lateinit var fileChooser: WebFileChooser
    private var lastUrl: String = BuildConfig.START_URL
    private var showingOffline = false

    private val prefs by lazy { getSharedPreferences(PREFS, MODE_PRIVATE) }

    private val extraHeaders: Map<String, String>
        get() = mapOf("X-App-Source" to BuildConfig.APP_SOURCE)

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        configureFullscreen()
        lastUrl = prefs.getString(KEY_LAST_URL, BuildConfig.START_URL) ?: BuildConfig.START_URL
        webView = findViewById(R.id.web_view)
        fileChooser = WebFileChooser(this)
        storeBilling = StoreBilling(this) { token, error, originalJson, signature ->
            deliverPurchase(token, error, originalJson, signature)
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
        webView.settings.javaScriptCanOpenWindowsAutomatically = true
        webView.settings.setSupportMultipleWindows(true)
        webView.settings.allowFileAccess = false
        webView.settings.allowContentAccess = false
        webView.settings.cacheMode = WebSettings.LOAD_DEFAULT
        webView.settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
        webView.settings.userAgentString =
            webView.settings.userAgentString +
            " CafeClub/${BuildConfig.VERSION_NAME} (Android; channel/${BuildConfig.APP_SOURCE}; ir.cafeclub.amytis)"
        webView.addJavascriptInterface(Bridge(), "CafeClub")
        webView.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                view: WebView,
                callback: ValueCallback<Array<Uri>>,
                params: FileChooserParams,
            ): Boolean = fileChooser.show(callback, params)

            override fun onCreateWindow(
                view: WebView?,
                isDialog: Boolean,
                isUserGesture: Boolean,
                resultMsg: android.os.Message?,
            ): Boolean {
                val trampoline = WebView(this@MainActivity)
                trampoline.webViewClient = object : WebViewClient() {
                    override fun shouldOverrideUrlLoading(v: WebView, request: WebResourceRequest): Boolean {
                        openOutside(request.url.toString())
                        return true
                    }
                }
                (resultMsg?.obj as? WebView.WebViewTransport)?.webView = trampoline
                resultMsg?.sendToTarget()
                return true
            }
        }
        webView.webViewClient =
            object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    val url = request.url?.toString().orEmpty()
                    if (!request.isForMainFrame) {
                        return false
                    }
                    if (isAppUrl(request.url)) {
                        view.loadUrl(url, extraHeaders)
                        return true
                    }
                    openOutside(url)
                    return true
                }

                override fun onPageFinished(view: WebView, url: String) {
                    if (!isOfflineAsset(url) && isAppUrl(Uri.parse(url))) {
                        showingOffline = false
                        rememberUrl(url)
                    }
                }

                override fun onReceivedError(
                    view: WebView,
                    request: WebResourceRequest,
                    error: WebResourceError,
                ) {
                    if (!request.isForMainFrame || showingOffline) return
                    if (!isAppUrl(request.url)) return
                    if (error.errorCode == WebViewClient.ERROR_UNSUPPORTED_SCHEME ||
                        error.errorCode == WebViewClient.ERROR_BAD_URL ||
                        error.errorCode == WebViewClient.ERROR_FILE
                    ) {
                        return
                    }
                    showOffline()
                }
            }
    }

    private fun initialUrl(): String {
        val candidate = if (prefs.getBoolean(KEY_SOURCE_BOUND, false)) lastUrl else BuildConfig.START_URL
        return if (isAppUrl(Uri.parse(candidate))) candidate else BuildConfig.START_URL
    }

    private fun configureFullscreen() {
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val root = findViewById<View>(R.id.root_container)
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val cutout = insets.getInsets(WindowInsetsCompat.Type.displayCutout())
            val keyboard = insets.getInsets(WindowInsetsCompat.Type.ime())
            view.setPadding(cutout.left, cutout.top, cutout.right, maxOf(cutout.bottom, keyboard.bottom))
            insets
        }
        ViewCompat.requestApplyInsets(root)
        hideSystemBars()
    }

    private fun hideSystemBars() {
        WindowCompat.getInsetsController(window, window.decorView).apply {
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            hide(WindowInsetsCompat.Type.systemBars())
        }
    }

    override fun onResume() {
        super.onResume()
        hideSystemBars()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) hideSystemBars()
    }

    private fun isTrustedWebPage(): Boolean {
        return isAppUrl(Uri.parse(webView.url ?: ""))
    }

    private fun isAppUrl(uri: Uri?): Boolean {
        if (uri == null) return false
        val scheme = uri.scheme?.lowercase() ?: return false
        if (scheme != "http" && scheme != "https") return false
        val host = uri.host?.lowercase() ?: return false
        return host == "cafeclub.amytisapp.ir" ||
            host.endsWith(".amytisapp.ir") ||
            host == "127.0.0.1" ||
            host == "localhost" ||
            host == "10.0.2.2"
    }

    private fun openOutside(url: String) {
        if (url.isBlank() || url == "about:blank") return
        try {
            val intent = if (url.startsWith("intent:", ignoreCase = true)) {
                Intent.parseUri(url, Intent.URI_INTENT_SCHEME)
            } else {
                Intent(Intent.ACTION_VIEW, Uri.parse(url))
            }
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            val scheme = intent.data?.scheme?.lowercase().orEmpty()
            if (scheme == "geo" || scheme == "maps") {
                startActivity(Intent.createChooser(intent, null))
            } else {
                startActivity(intent)
            }
        } catch (_: Exception) {
            // Stay on the current Cafe Club page instead of showing the offline screen.
        }
    }

    private fun loadSite(url: String) {
        showingOffline = false
        webView.loadUrl(url, extraHeaders)
    }

    private fun rememberUrl(url: String) {
        if (url.isBlank() || isOfflineAsset(url) || url == "about:blank" || !isAppUrl(Uri.parse(url))) {
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
        val target = lastUrl.ifBlank { BuildConfig.START_URL }
        loadSite(if (isAppUrl(Uri.parse(target))) target else BuildConfig.START_URL)
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
        if (::fileChooser.isInitialized) {
            fileChooser.cancel()
        }
        if (::storeBilling.isInitialized) {
            storeBilling.destroy()
        }
        super.onDestroy()
    }

    private fun deliverPurchase(
        token: String?,
        error: String?,
        originalJson: String? = null,
        signature: String? = null,
    ) {
        val tokenJs = if (token.isNullOrBlank()) "null" else JSONObject.quote(token)
        val errorJs = if (error.isNullOrBlank()) "null" else JSONObject.quote(error)
        val jsonJs = if (originalJson.isNullOrBlank()) "null" else JSONObject.quote(originalJson)
        val sigJs = if (signature.isNullOrBlank()) "null" else JSONObject.quote(signature)
        webView.post {
            webView.evaluateJavascript(
                "window.CafeClubOnPurchase && CafeClubOnPurchase($tokenJs, $errorJs, $jsonJs, $sigJs);",
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
            runOnUiThread {
                if (!isTrustedWebPage()) return@runOnUiThread
                storeBilling.purchase(sku, payload)
            }
        }

        @JavascriptInterface
        fun consume(token: String) {
            runOnUiThread {
                if (!isTrustedWebPage()) return@runOnUiThread
                storeBilling.consume(token)
            }
        }

        @JavascriptInterface
        fun openExternal(url: String) {
            runOnUiThread {
                if (!isTrustedWebPage() && !showingOffline) return@runOnUiThread
                openOutside(url)
            }
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
