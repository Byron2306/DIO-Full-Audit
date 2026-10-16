package za.co.dioworkflows.mobile.repository

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import za.co.dioworkflows.mobile.model.ConnectionPhase
import za.co.dioworkflows.mobile.model.DioAppState
import za.co.dioworkflows.mobile.model.SurfaceId
import za.co.dioworkflows.mobile.model.SurfaceSnapshot
import za.co.dioworkflows.mobile.truth.DioReadinessReducer
import za.co.dioworkflows.mobile.truth.LauncherStateSource

/** Single in-process presentation state sourced only from the live DIO launcher endpoint. */
class DioRepository(
    private val source: LauncherStateSource,
) {
    private val mutableState = MutableStateFlow(initialState())
    val state: StateFlow<DioAppState> = mutableState.asStateFlow()

    @Synchronized
    fun refreshTruth(transportConnected: Boolean) {
        if (!transportConnected) {
            transportDisconnected()
            return
        }

        val snapshot = try {
            source.fetch()
        } catch (_: Exception) {
            null
        }
        mutableState.value = DioReadinessReducer.reduce(
            transportConnected = true,
            snapshot = snapshot,
        )
    }

    @Synchronized
    fun transportDisconnected() {
        mutableState.value = DioReadinessReducer.reduce(
            transportConnected = false,
            snapshot = null,
        )
    }

    companion object {
        private fun initialState(): DioAppState =
            DioAppState(
                phase = ConnectionPhase.UNCONFIGURED,
                portfolio = null,
                surfaces = SurfaceId.entries.map { id ->
                    SurfaceSnapshot(
                        id = id,
                        name = id.displayName,
                        url = id.canonicalUrl,
                        ready = false,
                    )
                },
                generatedAt = null,
            )
    }
}
