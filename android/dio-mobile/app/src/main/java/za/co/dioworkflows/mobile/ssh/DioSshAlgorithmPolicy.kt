package za.co.dioworkflows.mobile.ssh

import com.hierynomus.sshj.key.KeyAlgorithms
import com.hierynomus.sshj.transport.kex.DHGroups
import net.schmizz.sshj.DefaultConfig
import net.schmizz.sshj.common.SecurityUtils

object DioSshAlgorithmPolicy {
    fun algorithmNames(): List<String> =
        listOf("rsa-sha2-512", "rsa-sha2-256")

    fun keyExchangeNames(): List<String> =
        listOf("diffie-hellman-group14-sha256")

    fun config(): DefaultConfig {
        SecurityUtils.setRegisterBouncyCastle(false)
        return DefaultConfig().apply {
            setKeyAlgorithms(
                listOf(
                    KeyAlgorithms.RSASHA512(),
                    KeyAlgorithms.RSASHA256(),
                ),
            )
            setKeyExchangeFactories(
                listOf(
                    DHGroups.Group14SHA256(),
                ),
            )
        }
    }
}
