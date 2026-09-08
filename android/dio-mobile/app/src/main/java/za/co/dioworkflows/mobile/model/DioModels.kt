package za.co.dioworkflows.mobile.model

enum class ConnectionPhase {
    UNCONFIGURED,
    CONNECTING,
    CONNECTED_HELD,
    READY,
    DISCONNECTED,
}

enum class SurfaceId(
    val wireId: String,
    val displayName: String,
    val canonicalUrl: String,
) {
    GOLDENEYE("goldeneye", "GoldenEye", "http://127.0.0.1:8766/"),
    CONTROL_DECK("control-deck", "Control Deck", "http://127.0.0.1:8765/"),
    MARKET_COMMAND("market-command", "Market Command", "http://127.0.0.1:8770/"),
    PRODUCTION_STUDIO(
        "production-studio",
        "Production Studio",
        "http://127.0.0.1:8765/dashboard/production.html",
    );

    companion object {
        fun fromWireId(value: String): SurfaceId =
            entries.firstOrNull { it.wireId == value }
                ?: throw IllegalArgumentException("Unknown DIO surface: $value")
    }
}

data class SurfaceSnapshot(
    val id: SurfaceId,
    val name: String,
    val url: String,
    val ready: Boolean,
)

data class PortfolioSnapshot(
    val verified: Boolean,
    val baseCount: Int,
    val extensionCount: Int,
    val totalCount: Int,
    val rowCount: Int,
    val extensionState: String,
)

data class LauncherSnapshot(
    val schema: String,
    val generatedAt: String,
    val surfaces: List<SurfaceSnapshot>,
    val portfolio: PortfolioSnapshot,
    val surfacesReady: Boolean,
    val ready: Boolean,
    val authorityCreated: Boolean,
    val readOnly: Boolean,
)

data class PortfolioTruth(
    val baseCount: Int,
    val extensionCount: Int,
    val totalCount: Int,
    val verified: Boolean,
    val generatedAt: String,
)

data class DioAppState(
    val phase: ConnectionPhase,
    val portfolio: PortfolioTruth?,
    val surfaces: List<SurfaceSnapshot>,
    val generatedAt: String?,
)
