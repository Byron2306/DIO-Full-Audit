package za.co.dioworkflows.mobile.truth

import org.junit.Assert.assertEquals
import org.junit.Test

class LauncherStateClientContractTest {
    @Test
    fun clientUsesTheCanonicalLoopbackTruthEndpoint() {
        assertEquals(
            "http://127.0.0.1:8764/api/launcher/state",
            LauncherStateClient.DEFAULT_ENDPOINT.toString(),
        )
    }
}
