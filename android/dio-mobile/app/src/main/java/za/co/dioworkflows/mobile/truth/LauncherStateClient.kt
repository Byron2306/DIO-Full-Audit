package za.co.dioworkflows.mobile.truth

import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import za.co.dioworkflows.mobile.model.LauncherSnapshot

interface LauncherStateSource {
    fun fetch(): LauncherSnapshot
}

/** Reads only the live DIO launcher truth endpoint over the SSH-owned loopback forward. */
class LauncherStateClient(
    private val endpoint: URL = DEFAULT_ENDPOINT,
) : LauncherStateSource {
    override fun fetch(): LauncherSnapshot {
        val connection = endpoint.openConnection() as HttpURLConnection
        try {
            connection.requestMethod = "GET"
            connection.connectTimeout = CONNECT_TIMEOUT_MS
            connection.readTimeout = READ_TIMEOUT_MS
            connection.useCaches = false
            connection.setRequestProperty("Cache-Control", "no-cache, no-store")
            connection.setRequestProperty("Pragma", "no-cache")
            connection.setRequestProperty("Accept", "application/json")

            val status = connection.responseCode
            if (status != HttpURLConnection.HTTP_OK) {
                throw IOException("DIO launcher returned HTTP $status")
            }

            val body = connection.inputStream
                .bufferedReader(Charsets.UTF_8)
                .use { reader -> reader.readText() }
            require(body.isNotBlank()) { "DIO launcher returned an empty response" }
            return LauncherStateParser.parse(body)
        } finally {
            connection.disconnect()
        }
    }

    companion object {
        val DEFAULT_ENDPOINT: URL = URL("http://127.0.0.1:8764/api/launcher/state")
        private const val CONNECT_TIMEOUT_MS = 3_000
        private const val READ_TIMEOUT_MS = 3_000
    }
}
