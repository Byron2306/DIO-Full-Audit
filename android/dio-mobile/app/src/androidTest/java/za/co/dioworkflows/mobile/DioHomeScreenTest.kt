package za.co.dioworkflows.mobile

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import za.co.dioworkflows.mobile.model.ConnectionPhase
import za.co.dioworkflows.mobile.model.DioAppState
import za.co.dioworkflows.mobile.model.PortfolioTruth
import za.co.dioworkflows.mobile.model.SurfaceId
import za.co.dioworkflows.mobile.model.SurfaceSnapshot
import za.co.dioworkflows.mobile.ui.DioHomeScreen

@RunWith(AndroidJUnit4::class)
class DioHomeScreenTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun disconnectedHomeDoesNotShowVerified68() {
        composeRule.setContent {
            DioHomeScreen(
                state = disconnectedState(),
                onOpenSurface = {},
                onDisconnect = {},
            )
        }

        composeRule.onNodeWithText("DISCONNECTED").assertExists()
        composeRule.onNodeWithText("68 VERIFIED").assertDoesNotExist()
    }

    @Test
    fun readyHomeShowsFourSurfacesAndLiveArithmetic() {
        composeRule.setContent {
            DioHomeScreen(
                state = ready68State(),
                onOpenSurface = {},
                onDisconnect = {},
            )
        }

        composeRule.onNodeWithText("53 + 15 = 68").assertExists()
        composeRule.onNodeWithText("68 VERIFIED").assertExists()
        composeRule.onNodeWithText("GoldenEye").assertExists()
        composeRule.onNodeWithText("Control Deck").assertExists()
        composeRule.onNodeWithText("Market Command").assertExists()
        composeRule.onNodeWithText("Production Studio").assertExists()
    }

    private fun disconnectedState(): DioAppState =
        DioAppState(
            phase = ConnectionPhase.DISCONNECTED,
            portfolio = null,
            surfaces = surfaces(ready = false),
            generatedAt = null,
        )

    private fun ready68State(): DioAppState =
        DioAppState(
            phase = ConnectionPhase.READY,
            portfolio = PortfolioTruth(
                baseCount = 53,
                extensionCount = 15,
                totalCount = 68,
                verified = true,
                generatedAt = "2026-09-08T05:00:00Z",
            ),
            surfaces = surfaces(ready = true),
            generatedAt = "2026-09-08T05:00:00Z",
        )

    private fun surfaces(ready: Boolean): List<SurfaceSnapshot> =
        SurfaceId.entries.map { id ->
            SurfaceSnapshot(
                id = id,
                name = id.displayName,
                url = id.canonicalUrl,
                ready = ready,
            )
        }
}
