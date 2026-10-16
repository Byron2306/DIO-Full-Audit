package za.co.dioworkflows.mobile.ssh

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DioForwardPlanTest {
    @Test
    fun forwardPlanIncludesAllSixLoopbackMappings() {
        assertEquals(listOf(8764, 8765, 8766, 8767, 8770, 8771), DioForwardPlan.REQUIRED.map { it.localPort })
        assertTrue(
            DioForwardPlan.REQUIRED.all {
                it.localHost == "127.0.0.1" &&
                    it.remoteHost == "127.0.0.1" &&
                    it.localPort == it.remotePort
            },
        )
    }

    @Test
    fun everyRequiredForwardMustBeActive() {
        assertTrue(DioForwardPlan.allRequiredActive(setOf(8764, 8765, 8766, 8767, 8770, 8771)))
        assertTrue(!DioForwardPlan.allRequiredActive(setOf(8764, 8765, 8766)))
    }
}
