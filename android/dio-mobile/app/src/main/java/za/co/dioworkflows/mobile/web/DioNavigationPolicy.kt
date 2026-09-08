package za.co.dioworkflows.mobile.web

import java.net.URI
import za.co.dioworkflows.mobile.model.SurfaceId

object DioNavigationPolicy {
    private val internalPorts = setOf(8765, 8766, 8770)

    fun surfaceUrl(id: SurfaceId): String = id.canonicalUrl

    fun isInternal(uri: URI): Boolean =
        uri.scheme == "http" &&
            uri.host == "127.0.0.1" &&
            uri.port in internalPorts &&
            uri.userInfo == null
}
