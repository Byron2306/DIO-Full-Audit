package za.co.dioworkflows.mobile.ssh

import android.content.Context

/** Exact SHA-256 host-key pin store. Existing trust cannot be silently replaced. */
class HostKeyPinStore(private val backend: Backend) {
    interface Backend {
        fun read(): String?
        fun write(value: String?)
    }

    fun pinned(): String? = backend.read()

    fun pin(fingerprint: String) {
        require(isValidSha256Fingerprint(fingerprint)) { "Only SHA-256 SSH host fingerprints are accepted" }
        val existing = backend.read()
        when {
            existing == null -> backend.write(fingerprint)
            existing == fingerprint -> Unit
            else -> throw IllegalStateException("Pinned SSH host identity cannot be replaced without clearing trust")
        }
    }

    fun matches(fingerprint: String): Boolean =
        isValidSha256Fingerprint(fingerprint) && backend.read() == fingerprint

    fun clear() = backend.write(null)

    companion object {
        private val SHA256_PATTERN = Regex("^SHA256:[A-Za-z0-9+/]{43}=?$")

        fun isValidSha256Fingerprint(value: String): Boolean = SHA256_PATTERN.matches(value)

        fun from(context: Context): HostKeyPinStore {
            val prefs = context.applicationContext.getSharedPreferences(
                "dio_mobile_host_pin_v1",
                Context.MODE_PRIVATE,
            )
            return HostKeyPinStore(
                object : Backend {
                    override fun read(): String? = prefs.getString("sha256_fingerprint", null)

                    override fun write(value: String?) {
                        val edit = prefs.edit()
                        if (value == null) edit.remove("sha256_fingerprint")
                        else edit.putString("sha256_fingerprint", value)
                        edit.apply()
                    }
                },
            )
        }
    }
}
