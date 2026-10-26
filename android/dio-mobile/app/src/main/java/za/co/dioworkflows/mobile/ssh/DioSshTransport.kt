package za.co.dioworkflows.mobile.ssh

import java.io.Closeable
import java.io.IOException
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.security.MessageDigest
import java.security.PublicKey
import java.util.Base64
import java.util.Collections
import java.util.concurrent.ConcurrentHashMap
import net.schmizz.sshj.SSHClient
import net.schmizz.sshj.common.Buffer
import net.schmizz.sshj.connection.channel.direct.LocalPortForwarder
import net.schmizz.sshj.connection.channel.direct.Parameters
import net.schmizz.sshj.transport.verification.HostKeyVerifier
import za.co.dioworkflows.mobile.security.SecureIdentityStore

data class DioSshProfile(
    val host: String,
    val username: String,
    val port: Int = 22,
) {
    init {
        require(host.isNotBlank()) { "SSH host is required" }
        require(username.isNotBlank()) { "SSH username is required" }
        require(port in 1..65535) { "SSH port is invalid" }
        require(!host.contains("://")) { "SSH host must not be a URL" }
    }
}

/**
 * SSH-only transport for DIO Mobile. This class never opens a shell and never executes commands.
 * Its sole authority is public-key authentication plus the canonical four local forwards.
 */
class DioSshTransport(
    private val identityStore: SecureIdentityStore,
    private val hostKeyPinStore: HostKeyPinStore,
) {
    fun connect(
        profile: DioSshProfile,
        onUntrustedFingerprint: (String) -> Unit,
    ): TransportSession {
        val client = SSHClient(DioSshAlgorithmPolicy.config())
        client.connectTimeout = CONNECT_TIMEOUT_MS
        client.timeout = SOCKET_TIMEOUT_MS
        client.addHostKeyVerifier(pinnedVerifier(onUntrustedFingerprint))

        val sockets = mutableListOf<ServerSocket>()
        val forwarders = mutableListOf<LocalPortForwarder>()
        val threads = mutableListOf<Thread>()
        val listenerErrors = ConcurrentHashMap<Int, Throwable>()

        try {
            client.connect(profile.host, profile.port)
            val keyPair = identityStore.loadKeyPair()
            client.authPublickey(profile.username, client.loadKeys(keyPair))

            DioForwardPlan.REQUIRED.forEach { spec ->
                val socket = ServerSocket().apply {
                    reuseAddress = true
                    bind(InetSocketAddress(spec.localHost, spec.localPort), FORWARD_BACKLOG)
                }
                sockets += socket

                val parameters = Parameters(
                    spec.localHost,
                    spec.localPort,
                    spec.remoteHost,
                    spec.remotePort,
                )
                val forwarder = client.newLocalPortForwarder(parameters, socket)
                forwarders += forwarder
                val thread = Thread(
                    {
                        try {
                            forwarder.listen()
                        } catch (error: Throwable) {
                            if (!socket.isClosed) listenerErrors[spec.localPort] = error
                        }
                    },
                    "dio-forward-${spec.localPort}",
                ).apply { isDaemon = true }
                threads += thread
                thread.start()
                awaitForwarderStarted(forwarder, spec.localPort)
            }

            val session = TransportSession(
                client = client,
                forwarders = forwarders,
                sockets = sockets,
                threads = threads,
                listenerErrors = listenerErrors,
            )
            check(session.isHealthy()) { "DIO SSH transport did not establish every required forward" }
            return session
        } catch (error: Throwable) {
            sockets.forEach { socket -> runCatching { socket.close() } }
            threads.forEach { thread -> thread.interrupt() }
            runCatching { client.close() }
            throw error
        }
    }

    private fun pinnedVerifier(onUntrustedFingerprint: (String) -> Unit): HostKeyVerifier =
        object : HostKeyVerifier {
            override fun verify(hostname: String, port: Int, key: PublicKey): Boolean {
                val fingerprint = sha256Fingerprint(key)
                val trusted = hostKeyPinStore.matches(fingerprint)
                if (!trusted) onUntrustedFingerprint(fingerprint)
                return trusted
            }

            override fun findExistingAlgorithms(hostname: String, port: Int): List<String> =
                Collections.emptyList()
        }

    private fun sha256Fingerprint(key: PublicKey): String {
        val publicBlob = Buffer.PlainBuffer().putPublicKey(key).compactData
        val digest = MessageDigest.getInstance("SHA-256").digest(publicBlob)
        return "SHA256:${Base64.getEncoder().withoutPadding().encodeToString(digest)}"
    }

    private fun awaitForwarderStarted(forwarder: LocalPortForwarder, port: Int) {
        repeat(FORWARD_START_ATTEMPTS) {
            if (forwarder.isRunning) return
            Thread.sleep(FORWARD_START_POLL_MS)
        }
        throw IOException("DIO local forward $port did not start")
    }

    companion object {
        private const val CONNECT_TIMEOUT_MS = 10_000
        private const val SOCKET_TIMEOUT_MS = 10_000
        private const val FORWARD_BACKLOG = 16
        private const val FORWARD_START_ATTEMPTS = 100
        private const val FORWARD_START_POLL_MS = 10L
    }
}

class TransportSession internal constructor(
    private val client: SSHClient,
    private val forwarders: List<LocalPortForwarder>,
    private val sockets: List<ServerSocket>,
    private val threads: List<Thread>,
    private val listenerErrors: Map<Int, Throwable>,
) : Closeable {
    fun isHealthy(): Boolean =
        client.isConnected &&
            client.isAuthenticated &&
            listenerErrors.isEmpty() &&
            forwarders.size == DioForwardPlan.REQUIRED.size &&
            forwarders.all { it.isRunning }

    override fun close() {
        sockets.forEach { socket -> runCatching { socket.close() } }
        forwarders.forEach { forwarder -> runCatching { forwarder.close() } }
        threads.forEach { thread -> thread.interrupt() }
        runCatching { client.close() }
    }
}
