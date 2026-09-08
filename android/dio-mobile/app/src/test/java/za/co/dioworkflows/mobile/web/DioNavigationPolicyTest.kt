package za.co.dioworkflows.mobile.web

import java.net.URI
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import za.co.dioworkflows.mobile.model.SurfaceId

class DioNavigationPolicyTest {
    @Test
    fun canonicalDioSurfacesAreInternal() {
        assertTrue(DioNavigationPolicy.isInternal(URI("http://127.0.0.1:8766/")))
        assertTrue(DioNavigationPolicy.isInternal(URI("http://127.0.0.1:8765/")))
        assertTrue(DioNavigationPolicy.isInternal(URI("http://127.0.0.1:8770/")))
        assertTrue(DioNavigationPolicy.isInternal(URI("http://127.0.0.1:8765/dashboard/production.html")))
    }

    @Test
    fun arbitraryHostsAndPortsAreNeverInternal() {
        assertFalse(DioNavigationPolicy.isInternal(URI("http://192.168.1.20:8765/")))
        assertFalse(DioNavigationPolicy.isInternal(URI("http://localhost:8765/")))
        assertFalse(DioNavigationPolicy.isInternal(URI("http://127.0.0.1:9999/")))
        assertFalse(DioNavigationPolicy.isInternal(URI("https://example.com/")))
    }

    @Test
    fun productionStudioUsesCanonicalBusinessPort() {
        assertEquals(
            "http://127.0.0.1:8765/dashboard/production.html",
            DioNavigationPolicy.surfaceUrl(SurfaceId.PRODUCTION_STUDIO),
        )
    }
}
