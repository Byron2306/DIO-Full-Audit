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
    fun androidTransportAvoidsCurveAndUsesGroup14Sha256KeyExchange() {
        assertEquals(
            listOf("diffie-hellman-group14-sha256"),
            DioSshAlgorithmPolicy.keyExchangeNames(),
        )
    }

    @Test
    fun androidTransportUsesPlatformJceInsteadOfForcingBouncyCastle() {
        DioSshAlgorithmPolicy.config()
        assertNull(SecurityUtils.getSecurityProvider())
    }
}
