package za.co.dioworkflows.mobile.ssh

import android.content.Context

/** Persists only the address and account name needed for SSH public-key authentication. */
class DioProfileStore(private val backend: Backend) {
    interface Backend {
        fun read(): DioSshProfile?
        fun write(profile: DioSshProfile?)
    }

    fun load(): DioSshProfile? = backend.read()

    fun save(profile: DioSshProfile) = backend.write(profile)

    fun clear() = backend.write(null)

    companion object {
        fun from(context: Context): DioProfileStore {
            val prefs = context.applicationContext.getSharedPreferences(
                "dio_mobile_connection_profile_v1",
                Context.MODE_PRIVATE,
            )
            return DioProfileStore(
                object : Backend {
                    override fun read(): DioSshProfile? {
                        val host = prefs.getString("host", null) ?: return null
                        val username = prefs.getString("username", null) ?: return null
                        val port = prefs.getInt("port", -1)
                        if (port !in 1..65535) return null
                        return runCatching { DioSshProfile(host, username, port) }.getOrNull()
                    }

                    override fun write(profile: DioSshProfile?) {
                        val edit = prefs.edit()
                        if (profile == null) {
                            edit.clear()
                        } else {
                            edit.putString("host", profile.host)
                            edit.putString("username", profile.username)
                            edit.putInt("port", profile.port)
                        }
                        edit.apply()
                    }
                },
            )
        }
    }
}
