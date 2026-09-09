package za.co.dioworkflows.mobile.ssh

import com.hierynomus.sshj.key.KeyAlgorithms
import net.schmizz.sshj.DefaultConfig
import net.schmizz.sshj.transport.kex.ECDHNistP

/**
 * Android-safe SSH algorithm policy for the DIO mobile transport.
 *
 * The spine exposes a pinned RSA host key, so DIO Mobile deliberately negotiates
 * modern RSA-SHA2 host-key algorithms. Android's SSHJ Curve25519 path closes before
 * sending SSH2_MSG_KEX_ECDH_INIT on the target device, so the transport also pins
 * key exchange to the JCE-friendly NIST P-256 ECDH implementation.
 */
object DioSshAlgorithmPolicy {
    fun algorithmNames(): List<String> =
        listOf("rsa-sha2-512", "rsa-sha2-256")

    fun keyExchangeNames(): List<String> =
        listOf("ecdh-sha2-nistp256")

    fun config(): DefaultConfig =
        DefaultConfig().apply {
            setKeyAlgorithms(
                listOf(
                    KeyAlgorithms.RSASHA512(),
                    KeyAlgorithms.RSASHA256(),
                ),
            )
            setKeyExchangeFactories(
                listOf(
                    ECDHNistP.Factory256(),
                ),
            )
        }
}
