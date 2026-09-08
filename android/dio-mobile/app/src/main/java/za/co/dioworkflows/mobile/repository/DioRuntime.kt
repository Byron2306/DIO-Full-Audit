package za.co.dioworkflows.mobile.repository

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import za.co.dioworkflows.mobile.truth.LauncherStateClient

/** Process-local state hub shared by the foreground transport service and the operator UI. */
object DioRuntime {
    val repository: DioRepository = DioRepository(LauncherStateClient())

    private val mutableUntrustedFingerprint = MutableStateFlow<String?>(null)
    val untrustedFingerprint: StateFlow<String?> = mutableUntrustedFingerprint.asStateFlow()

    fun reportUntrustedFingerprint(value: String) {
        mutableUntrustedFingerprint.value = value
    }

    fun clearUntrustedFingerprint() {
        mutableUntrustedFingerprint.value = null
    }
}
