package za.co.dioworkflows.mobile.ssh

data class ForwardSpec(
    val localHost: String,
    val localPort: Int,
    val remoteHost: String,
    val remotePort: Int,
)

object DioForwardPlan {
    val REQUIRED: List<ForwardSpec> = listOf(
        ForwardSpec("127.0.0.1", 8764, "127.0.0.1", 8764),
        ForwardSpec("127.0.0.1", 8765, "127.0.0.1", 8765),
        ForwardSpec("127.0.0.1", 8766, "127.0.0.1", 8766),
        ForwardSpec("127.0.0.1", 8770, "127.0.0.1", 8770),
    )

    fun allRequiredActive(activePorts: Set<Int>): Boolean =
        REQUIRED.all { it.localPort in activePorts }
}
