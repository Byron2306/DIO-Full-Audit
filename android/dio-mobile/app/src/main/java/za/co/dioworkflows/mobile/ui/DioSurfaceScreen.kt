package za.co.dioworkflows.mobile.ui

import android.annotation.SuppressLint
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import java.net.URI
import za.co.dioworkflows.mobile.model.SurfaceId
import za.co.dioworkflows.mobile.web.DioNavigationPolicy

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun DioSurfaceScreen(
    surface: SurfaceId,
    onBack: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 10.dp),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = surface.displayName,
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                )
                Text("Live Debian surface", style = MaterialTheme.typography.bodySmall)
            }
            Button(onClick = onBack) {
                Text("Back to DIO")
            }
        }

        AndroidView(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
            factory = { context ->
                WebView(context).apply {
                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = true
                    settings.allowFileAccess = false
                    settings.allowContentAccess = false
                    settings.javaScriptCanOpenWindowsAutomatically = false
                    settings.setSupportMultipleWindows(false)
                    settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW

                    webViewClient = object : WebViewClient() {
                        override fun shouldOverrideUrlLoading(
                            view: WebView,
                            request: WebResourceRequest,
                        ): Boolean = shouldBlock(request.url.toString())

                        @Deprecated("Compatibility callback for older WebView navigation")
                        override fun shouldOverrideUrlLoading(view: WebView, url: String): Boolean =
                            shouldBlock(url)
                    }

                    loadUrl(DioNavigationPolicy.surfaceUrl(surface))
                }
            },
            onRelease = { webView ->
                webView.stopLoading()
                webView.loadUrl("about:blank")
                webView.destroy()
            },
        )
    }
}

private fun shouldBlock(url: String): Boolean =
    runCatching {
        !DioNavigationPolicy.isInternal(URI(url))
    }.getOrDefault(true)
