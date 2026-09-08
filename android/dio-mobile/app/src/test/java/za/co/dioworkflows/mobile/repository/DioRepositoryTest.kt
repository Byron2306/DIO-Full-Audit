package za.co.dioworkflows.mobile.repository

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import za.co.dioworkflows.mobile.model.ConnectionPhase
import za.co.dioworkflows.mobile.model.LauncherSnapshot
import za.co.dioworkflows.mobile.model.PortfolioSnapshot
import za.co.dioworkflows.mobile.model.SurfaceId
import za.co.dioworkflows.mobile.model.SurfaceSnapshot
import za.co.dioworkflows.mobile.truth.LauncherStateSource

class DioRepositoryTest {
    private class FakeSource : LauncherStateSource {
        var snapshot: LauncherSnapshot? = readySnapshot()
        var error: RuntimeException? = null

        override fun fetch(): LauncherSnapshot {
            error?.let { throw it }
            return snapshot ?: throw IllegalStateException("no snapshot")
        }
    }

    @Test
    fun refreshPublishesLiveVerifiedTruth() {
        val source = FakeSource()
        val repository = DioRepository(source)

        repository.refreshTruth(transportConnected = true)

        assertEquals(ConnectionPhase.READY, repository.state.value.phase)
        assertEquals(68, repository.state.value.portfolio?.totalCount)
    }

    @Test
    fun disconnectImmediatelyClearsVerifiedTruth() {
        val source = FakeSource()
        val repository = DioRepository(source)
        repository.refreshTruth(transportConnected = true)
        assertEquals(ConnectionPhase.READY, repository.state.value.phase)

        repository.transportDisconnected()

        assertEquals(ConnectionPhase.DISCONNECTED, repository.state.value.phase)
        assertNull(repository.state.value.portfolio)
        assertTrue(repository.state.value.surfaces.all { !it.ready })
    }

    @Test
    fun fetchFailureCannotPreservePreviousVerifiedTruth() {
        val source = FakeSource()
        val repository = DioRepository(source)
        repository.refreshTruth(transportConnected = true)
        source.error = RuntimeException("launcher unavailable")

        repository.refreshTruth(transportConnected = true)

        assertEquals(ConnectionPhase.CONNECTED_HELD, repository.state.value.phase)
        assertNull(repository.state.value.portfolio)
        assertTrue(repository.state.value.surfaces.all { !it.ready })
    }

    companion object {
        private fun readySnapshot(): LauncherSnapshot =
            LauncherSnapshot(
                schema = "dio.local_launcher.state.v1",
                generatedAt = "2026-09-08T05:00:00Z",
                surfaces = SurfaceId.entries.map { id ->
                    SurfaceSnapshot(id, id.displayName, id.canonicalUrl, true)
                },
                portfolio = PortfolioSnapshot(
                    verified = true,
                    baseCount = 53,
                    extensionCount = 15,
                    totalCount = 68,
                    rowCount = 68,
                    extensionState = "VERIFIED",
                ),
                surfacesReady = true,
                ready = true,
                authorityCreated = false,
                readOnly = true,
            )
    }
}
