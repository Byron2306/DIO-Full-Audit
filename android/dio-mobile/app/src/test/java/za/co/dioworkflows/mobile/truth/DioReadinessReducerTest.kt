package za.co.dioworkflows.mobile.truth

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import za.co.dioworkflows.mobile.model.ConnectionPhase

class DioReadinessReducerTest {
    @Test
    fun verified68RequiresLiveBackendProof() {
        val snapshot = LauncherStateParser.parse(readyLauncherJson())
        val state = DioReadinessReducer.reduce(transportConnected = true, snapshot = snapshot)

        assertEquals(ConnectionPhase.READY, state.phase)
        assertEquals(53, state.portfolio?.baseCount)
        assertEquals(15, state.portfolio?.extensionCount)
        assertEquals(68, state.portfolio?.totalCount)
        assertTrue(state.portfolio?.verified == true)
        assertTrue(state.surfaces.all { it.ready })
    }

    @Test
    fun wrongArithmeticCannotBecomeReady() {
        val json = readyLauncherJson().replace("\"total\": 68", "\"total\": 67")
        val snapshot = LauncherStateParser.parse(json)
        val state = DioReadinessReducer.reduce(transportConnected = true, snapshot = snapshot)

        assertEquals(ConnectionPhase.CONNECTED_HELD, state.phase)
        assertNull(state.portfolio)
    }

    @Test
    fun backendAuthorityCreationCannotBecomeReady() {
        val json = readyLauncherJson().replace("\"authority_created\": false", "\"authority_created\": true")
        val snapshot = LauncherStateParser.parse(json)
        val state = DioReadinessReducer.reduce(transportConnected = true, snapshot = snapshot)

        assertEquals(ConnectionPhase.CONNECTED_HELD, state.phase)
        assertNull(state.portfolio)
    }

    @Test
    fun staleVerifiedStateIsClearedOnDisconnect() {
        val snapshot = LauncherStateParser.parse(readyLauncherJson())
        val state = DioReadinessReducer.reduce(transportConnected = false, snapshot = snapshot)

        assertEquals(ConnectionPhase.DISCONNECTED, state.phase)
        assertNull(state.portfolio)
        assertTrue(state.surfaces.all { !it.ready })
    }

    @Test
    fun oneUnreadySurfaceHoldsTheWholeApp() {
        val json = readyLauncherJson().replace(
            "\"id\": \"market-command\", \"name\": \"Market Command\", \"url\": \"http://127.0.0.1:8771/dashboard/market.html\", \"ready\": true",
            "\"id\": \"market-command\", \"name\": \"Market Command\", \"url\": \"http://127.0.0.1:8771/dashboard/market.html\", \"ready\": false",
        )
        val snapshot = LauncherStateParser.parse(json)
        val state = DioReadinessReducer.reduce(transportConnected = true, snapshot = snapshot)

        assertEquals(ConnectionPhase.CONNECTED_HELD, state.phase)
        assertNull(state.portfolio)
        assertFalse(state.surfaces.first { it.id.wireId == "market-command" }.ready)
    }

    @Test
    fun incompletePortfolioStillAllowsHealthyDashboardInspection() {
        val snapshot = LauncherStateParser.parse(readyLauncherJson()).let {
            it.copy(ready = false, portfolio = it.portfolio.copy(verified = false, extensionCount = 0, totalCount = 53, rowCount = 53, extensionState = "NOT_VERIFIED"))
        }
        val state = DioReadinessReducer.reduce(true, snapshot)
        assertEquals(ConnectionPhase.CONNECTED_HELD, state.phase)
        assertNull(state.portfolio)
        assertTrue(state.canOpenSurface(za.co.dioworkflows.mobile.model.SurfaceId.GOLDENEYE))
    }

    @Test
    fun invalidAuthorityClearsInspectionAsWellAsProof() {
        val snapshot = LauncherStateParser.parse(readyLauncherJson()).copy(authorityCreated = true)
        val state = DioReadinessReducer.reduce(true, snapshot)
        assertTrue(state.surfaces.all { !it.ready })
    }

    @Test
    fun disconnectClosesPreviouslyAvailableInspection() {
        val snapshot = LauncherStateParser.parse(readyLauncherJson())
        val state = DioReadinessReducer.reduce(false, snapshot)
        assertFalse(state.canOpenSurface(za.co.dioworkflows.mobile.model.SurfaceId.GOLDENEYE))
    }

    private fun readyLauncherJson(): String =
        """
        {
          "schema": "dio.local_launcher.state.v1",
          "generated_at": "2026-09-08T04:00:00Z",
          "surfaces": [
            {"id": "goldeneye", "name": "GoldenEye", "url": "http://127.0.0.1:8766/", "ready": true},
            {"id": "control-deck", "name": "Control Deck", "url": "http://127.0.0.1:8767/", "ready": true},
            {"id": "market-command", "name": "Market Command", "url": "http://127.0.0.1:8771/dashboard/market.html", "ready": true},
            {"id": "production-studio", "name": "Production Studio", "url": "http://127.0.0.1:8767/dashboard/production.html", "ready": true}
          ],
          "portfolio": {
            "verified": true,
            "base": 53,
            "extensions": 15,
            "total": 68,
            "row_count": 68,
            "extension_state": "VERIFIED"
          },
          "surfaces_ready": true,
          "ready": true,
          "authority_created": false,
          "read_only": true
        }
        """.trimIndent()
}
