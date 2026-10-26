package za.co.dioworkflows.mobile.ssh

import net.schmizz.sshj.common.SecurityUtils
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
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
    fun androidTransportOffersPlatformJceEcdhAcceptedByNativeDebian() {
        assertEquals(
            listOf("ecdh-sha2-nistp256"),
            DioSshAlgorithmPolicy.keyExchangeNames(),
        )
    }

    @Test
    fun androidTransportUsesPlatformJceInsteadOfForcingBouncyCastle() {
        val config = DioSshAlgorithmPolicy.config()
        assertEquals(DioSshAlgorithmPolicy.keyExchangeNames(), config.keyExchangeFactories.map { it.name })
        assertNull(SecurityUtils.getSecurityProvider())
    }
}
