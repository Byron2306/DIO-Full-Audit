package za.co.dioworkflows.mobile.repository

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DioRuntimeErrorTest {
    @Test
    fun connectionErrorsAreObservableAndClearable() {
        DioRuntime.clearConnectionError()
        assertNull(DioRuntime.connectionError.value)

        DioRuntime.reportConnectionError("TransportException: key exchange failed")
        assertEquals(
            "TransportException: key exchange failed",
            DioRuntime.connectionError.value,
        )

        DioRuntime.clearConnectionError()
        assertNull(DioRuntime.connectionError.value)
    }
}
