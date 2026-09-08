package za.co.dioworkflows.mobile.truth

import za.co.dioworkflows.mobile.model.ConnectionPhase
import za.co.dioworkflows.mobile.model.DioAppState
import za.co.dioworkflows.mobile.model.LauncherSnapshot
import za.co.dioworkflows.mobile.model.PortfolioTruth
import za.co.dioworkflows.mobile.model.SurfaceId
import za.co.dioworkflows.mobile.model.SurfaceSnapshot

object DioReadinessReducer {
    fun reduce(transportConnected: Boolean, snapshot: LauncherSnapshot?): DioAppState {
        if (!transportConnected) {
            return DioAppState(
                phase = ConnectionPhase.DISCONNECTED,
                portfolio = null,
                surfaces = clearedSurfaces(snapshot),
                generatedAt = null,
            )
        }

        if (snapshot == null) {
            return DioAppState(
                phase = ConnectionPhase.CONNECTED_HELD,
                portfolio = null,
                surfaces = clearedSurfaces(null),
                generatedAt = null,
            )
        }

        val allSurfacesReady = SurfaceId.entries.all { required ->
            snapshot.surfaces.singleOrNull { it.id == required }?.ready == true
        }
        val portfolio = snapshot.portfolio
        val verified68 =
            snapshot.schema == LauncherStateParser.SCHEMA &&
                snapshot.ready &&
                snapshot.surfacesReady &&
                snapshot.readOnly &&
                !snapshot.authorityCreated &&
                allSurfacesReady &&
                portfolio.verified &&
                portfolio.baseCount == 53 &&
                portfolio.extensionCount == 15 &&
                portfolio.totalCount == 68 &&
                portfolio.rowCount == 68 &&
                portfolio.extensionState == "VERIFIED" &&
                portfolio.baseCount + portfolio.extensionCount == portfolio.totalCount

        if (!verified68) {
            return DioAppState(
                phase = ConnectionPhase.CONNECTED_HELD,
                portfolio = null,
                surfaces = snapshot.surfaces,
                generatedAt = snapshot.generatedAt,
            )
        }

        return DioAppState(
            phase = ConnectionPhase.READY,
            portfolio = PortfolioTruth(
                baseCount = portfolio.baseCount,
                extensionCount = portfolio.extensionCount,
                totalCount = portfolio.totalCount,
                verified = true,
                generatedAt = snapshot.generatedAt,
            ),
            surfaces = snapshot.surfaces,
            generatedAt = snapshot.generatedAt,
        )
    }

    private fun clearedSurfaces(snapshot: LauncherSnapshot?): List<SurfaceSnapshot> =
        SurfaceId.entries.map { id ->
            val previous = snapshot?.surfaces?.firstOrNull { it.id == id }
            SurfaceSnapshot(
                id = id,
                name = previous?.name ?: id.displayName,
                url = id.canonicalUrl,
                ready = false,
            )
        }
}
