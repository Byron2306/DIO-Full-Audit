package za.co.dioworkflows.mobile.truth

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LauncherStateParserTest {
    @Test
    fun parsesTheRealDioLauncherSchema() {
        val snapshot = LauncherStateParser.parse(validJson())

        assertEquals("dio.local_launcher.state.v1", snapshot.schema)
        assertTrue(snapshot.ready)
        assertTrue(snapshot.surfacesReady)
        assertFalse(snapshot.authorityCreated)
        assertTrue(snapshot.readOnly)
        assertEquals(4, snapshot.surfaces.size)
        assertEquals(53, snapshot.portfolio.baseCount)
        assertEquals(15, snapshot.portfolio.extensionCount)
        assertEquals(68, snapshot.portfolio.totalCount)
        assertEquals(68, snapshot.portfolio.rowCount)
        assertEquals("VERIFIED", snapshot.portfolio.extensionState)
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsUnknownLauncherSchema() {
        LauncherStateParser.parse(validJson().replace("dio.local_launcher.state.v1", "dio.fake.v9"))
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsMissingRequiredSurface() {
        LauncherStateParser.parse(
            validJson().replace(
                "{\"id\": \"goldeneye\", \"name\": \"GoldenEye\", \"url\": \"http://127.0.0.1:8766/\", \"ready\": true},",
                "",
            ),
        )
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsMalformedCountsInsteadOfCoercingThem() {
        LauncherStateParser.parse(validJson().replace("\"base\": 53", "\"base\": \"53\""))
    }

    private fun validJson(): String =
        """
        {
          "schema": "dio.local_launcher.state.v1",
          "generated_at": "2026-09-08T04:00:00Z",
          "surfaces": [
            {"id": "goldeneye", "name": "GoldenEye", "url": "http://127.0.0.1:8766/", "ready": true},
            {"id": "control-deck", "name": "Control Deck", "url": "http://127.0.0.1:8765/", "ready": true},
            {"id": "market-command", "name": "Market Command", "url": "http://127.0.0.1:8770/", "ready": true},
            {"id": "production-studio", "name": "Production Studio", "url": "http://127.0.0.1:8765/dashboard/production.html", "ready": true}
          ],
          "portfolio": {
            "verified": true,
            "base": 53,
            "extensions": 15,
            "total": 68,
            "row_count": 68,
            "extension_state": "VERIFIED"
          },
          "surfaces_ready": true,
          "ready": true,
          "authority_created": false,
          "read_only": true
        }
        """.trimIndent()
}
