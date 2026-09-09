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

    @Test
    fun androidTransportAvoidsCurve25519AndUsesNistP256KeyExchange() {
        assertEquals(
            listOf("ecdh-sha2-nistp256"),
            DioSshAlgorithmPolicy.keyExchangeNames(),
        )
    }
}
