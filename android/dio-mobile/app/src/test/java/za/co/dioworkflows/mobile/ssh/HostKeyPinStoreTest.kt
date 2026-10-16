package za.co.dioworkflows.mobile.ssh

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class HostKeyPinStoreTest {
    private class MemoryBackend : HostKeyPinStore.Backend {
        var value: String? = null

        override fun read(): String? = value

        override fun write(value: String?) {
            this.value = value
        }
    }

    @Test
    fun firstPinPersistsExactSha256Fingerprint() {
        val backend = MemoryBackend()
        val store = HostKeyPinStore(backend)
        val fingerprint = "SHA256:oQGbQTujGeNIgh0ONthcEpA/BHxtt3rcYY+NxXTxQjs"

        store.pin(fingerprint)

        assertEquals(fingerprint, store.pinned())
        assertTrue(store.matches(fingerprint))
    }

    @Test(expected = IllegalStateException::class)
    fun differentPinCannotSilentlyReplaceExistingHost() {
        val backend = MemoryBackend()
        val store = HostKeyPinStore(backend)
        store.pin("SHA256:oQGbQTujGeNIgh0ONthcEpA/BHxtt3rcYY+NxXTxQjs")

        store.pin("SHA256:l/SjyCoKP8jAx3d8k8MWH+UZG0gcuIR7TQRE/A3faQo")
    }

    @Test
    fun clearIsRequiredBeforeTrustingReplacementHost() {
        val backend = MemoryBackend()
        val store = HostKeyPinStore(backend)
        val first = "SHA256:oQGbQTujGeNIgh0ONthcEpA/BHxtt3rcYY+NxXTxQjs"
        val second = "SHA256:l/SjyCoKP8jAx3d8k8MWH+UZG0gcuIR7TQRE/A3faQo"
        store.pin(first)

        store.clear()
        assertNull(store.pinned())
        assertFalse(store.matches(first))

        store.pin(second)
        assertEquals(second, store.pinned())
    }

    @Test(expected = IllegalArgumentException::class)
    fun malformedFingerprintIsRejected() {
        HostKeyPinStore(MemoryBackend()).pin("MD5:not-allowed")
    }
}
