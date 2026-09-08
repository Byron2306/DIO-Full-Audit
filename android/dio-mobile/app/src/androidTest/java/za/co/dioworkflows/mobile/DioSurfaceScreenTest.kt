package za.co.dioworkflows.mobile

import androidx.compose.ui.test.assertExists
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import za.co.dioworkflows.mobile.model.SurfaceId
import za.co.dioworkflows.mobile.ui.DioSurfaceScreen

@RunWith(AndroidJUnit4::class)
class DioSurfaceScreenTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun goldenEyeSurfaceRendersInsideBoundedOperatorScreen() {
        composeRule.setContent {
            DioSurfaceScreen(
                surface = SurfaceId.GOLDENEYE,
                onBack = {},
            )
        }

        composeRule.onNodeWithText("GoldenEye").assertExists()
        composeRule.onNodeWithText("Back to DIO").assertExists()
    }
}
