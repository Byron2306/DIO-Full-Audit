package za.co.dioworkflows.mobile.ssh

import org.junit.Assert.assertEquals
import org.junit.Test

class DioSshAlgorithmPolicyTest {
    @Test
    fun androidTransportUsesOnlyModernRsaSha2KeyAlgorithms() {
        assertEquals(
            listOf("rsa-sha2-512", "rsa-sha2-256"),
            DioSshAlgorithmPolicy.algorithmNames(),
        )
    }
}
