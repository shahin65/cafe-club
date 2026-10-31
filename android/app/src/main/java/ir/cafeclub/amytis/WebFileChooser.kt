package ir.cafeclub.amytis

import android.app.Activity
import android.content.ClipData
import android.content.Intent
import android.net.Uri
import android.provider.MediaStore
import android.webkit.MimeTypeMap
import android.webkit.ValueCallback
import android.webkit.WebChromeClient.FileChooserParams
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import java.io.File

internal class WebFileChooser(private val activity: AppCompatActivity) {
    private var callback: ValueCallback<Array<Uri>>? = null
    private var cameraFile: File? = null
    private var cameraUri: Uri? = null

    private val launcher = activity.registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val photo = cameraUri?.takeIf { cameraFile?.length()?.let { it > 0L } == true }
        val selected = if (result.resultCode == Activity.RESULT_OK) {
            FileChooserParams.parseResult(result.resultCode, result.data)
                ?.filter { it.scheme == "content" }
                ?.takeIf { it.isNotEmpty() }
                ?.toTypedArray()
                ?: photo?.let { arrayOf(it) }
        } else {
            null
        }
        complete(selected)
    }

    fun show(nextCallback: ValueCallback<Array<Uri>>, params: FileChooserParams): Boolean {
        cancel()
        callback = nextCallback
        try {
            val mimeTypes = params.acceptTypes
                .flatMap { it.split(',') }
                .map { it.trim().lowercase() }
                .filter { it.isNotEmpty() }
                .mapNotNull {
                    if (it.startsWith('.')) {
                        MimeTypeMap.getSingleton().getMimeTypeFromExtension(it.drop(1))
                    } else {
                        it
                    }
                }
                .distinct()
            val picker = params.createIntent().apply {
                if (mimeTypes.isNotEmpty()) {
                    type = mimeTypes.singleOrNull() ?: "*/*"
                    putExtra(Intent.EXTRA_MIME_TYPES, mimeTypes.toTypedArray())
                }
                putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.mode == FileChooserParams.MODE_OPEN_MULTIPLE)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            val acceptsImages = mimeTypes.isEmpty() || mimeTypes.any { it == "*/*" || it.startsWith("image/") }
            val camera = if (acceptsImages && params.mode == FileChooserParams.MODE_OPEN) cameraIntent() else null
            val launchIntent = if (params.isCaptureEnabled && camera != null && mimeTypes.all { it.startsWith("image/") }) {
                camera
            } else {
                Intent.createChooser(picker, activity.getString(R.string.select_upload_file)).apply {
                    if (camera != null) putExtra(Intent.EXTRA_INITIAL_INTENTS, arrayOf(camera))
                }
            }
            launcher.launch(launchIntent)
        } catch (_: Exception) {
            cancel()
            Toast.makeText(activity, R.string.file_chooser_unavailable, Toast.LENGTH_LONG).show()
        }
        return true
    }

    private fun cameraIntent(): Intent? {
        val intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
        if (intent.resolveActivity(activity.packageManager) == null) return null
        val folder = File(activity.cacheDir, "web_uploads").apply { mkdirs() }
        val file = File.createTempFile("capture-", ".jpg", folder)
        val uri = FileProvider.getUriForFile(activity, "${activity.packageName}.fileprovider", file)
        cameraFile = file
        cameraUri = uri
        return intent.apply {
            putExtra(MediaStore.EXTRA_OUTPUT, uri)
            clipData = ClipData.newRawUri("photo", uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        }
    }

    fun cancel() = complete(null)

    private fun complete(uris: Array<Uri>?) {
        val pending = callback
        callback = null
        // Keep a successfully captured file available until WebView finishes uploading it.
        if (cameraUri == null || uris?.contains(cameraUri) != true) cameraFile?.delete()
        cameraFile = null
        cameraUri = null
        pending?.onReceiveValue(uris)
    }
}
