package za.co.dioworkflows.mobile.ssh

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DioProfileStoreTest {
    private class MemoryBackend : DioProfileStore.Backend {
        var saved: DioSshProfile? = null

        override fun read(): DioSshProfile? = saved

        override fun write(profile: DioSshProfile?) {
            saved = profile
        }
    }

    @Test
    fun profileContainsOnlyHostUserAndPort() {
        val backend = MemoryBackend()
        val store = DioProfileStore(backend)
        val profile = DioSshProfile(host = "192.168.1.10", username = "byron", port = 22)

        store.save(profile)

        assertEquals(profile, store.load())
    }

    @Test
    fun clearRemovesProfile() {
        val backend = MemoryBackend()
        val store = DioProfileStore(backend)
        store.save(DioSshProfile("dio-host", "byron", 2222))

        store.clear()

        assertNull(store.load())
    }
}
