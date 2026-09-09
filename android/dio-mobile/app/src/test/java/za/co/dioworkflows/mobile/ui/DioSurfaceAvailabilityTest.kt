package za.co.dioworkflows.mobile.ui

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import za.co.dioworkflows.mobile.model.ConnectionPhase
import za.co.dioworkflows.mobile.model.DioAppState
import za.co.dioworkflows.mobile.model.SurfaceId
import za.co.dioworkflows.mobile.model.SurfaceSnapshot

class DioSurfaceAvailabilityTest {
    @Test
    fun healthySurfaceRemainsOpenableWhenAnotherSurfaceIsDown() {
        val state = DioAppState(
            phase = ConnectionPhase.CONNECTED_HELD,
            portfolio = null,
            surfaces = SurfaceId.entries.map { id ->
                SurfaceSnapshot(
                    id = id,
                    name = id.displayName,
                    url = id.canonicalUrl,
                    ready = id != SurfaceId.MARKET_COMMAND,
                )
            },
            generatedAt = "2026-09-09T09:00:00Z",
        )

        assertTrue(DioSurfaceAvailability.isOpenable(state, SurfaceId.CONTROL_DECK))
        assertTrue(DioSurfaceAvailability.isOpenable(state, SurfaceId.PRODUCTION_STUDIO))
        assertFalse(DioSurfaceAvailability.isOpenable(state, SurfaceId.MARKET_COMMAND))
    }

    @Test
    fun disconnectedTransportNeverOpensAStaleSurface() {
        val state = DioAppState(
            phase = ConnectionPhase.DISCONNECTED,
            portfolio = null,
            surfaces = listOf(
                SurfaceSnapshot(
                    id = SurfaceId.CONTROL_DECK,
                    name = SurfaceId.CONTROL_DECK.displayName,
                    url = SurfaceId.CONTROL_DECK.canonicalUrl,
                    ready = true,
                ),
            ),
            generatedAt = null,
        )

        assertFalse(DioSurfaceAvailability.isOpenable(state, SurfaceId.CONTROL_DECK))
    }
}
