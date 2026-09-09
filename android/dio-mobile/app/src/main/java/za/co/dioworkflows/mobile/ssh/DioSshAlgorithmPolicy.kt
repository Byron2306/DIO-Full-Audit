package za.co.dioworkflows.mobile.ssh

import com.hierynomus.sshj.key.KeyAlgorithms
import net.schmizz.sshj.DefaultConfig

/**
 * Android-safe SSH key algorithm policy for the DIO mobile transport.
 *
 * The spine exposes a pinned RSA host key, so DIO Mobile deliberately negotiates
 * modern RSA-SHA2 algorithms and avoids the Android Ed25519 provider path.
 */
object DioSshAlgorithmPolicy {
    fun algorithmNames(): List<String> =
        listOf("rsa-sha2-512", "rsa-sha2-256")

    fun config(): DefaultConfig =
        DefaultConfig().apply {
            setKeyAlgorithms(
                listOf(
                    KeyAlgorithms.RSASHA512(),
                    KeyAlgorithms.RSASHA256(),
                ),
            )
        }
}
