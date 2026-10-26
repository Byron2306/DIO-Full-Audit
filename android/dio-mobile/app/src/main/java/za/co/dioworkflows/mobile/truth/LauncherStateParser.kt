package za.co.dioworkflows.mobile.truth

import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.google.gson.JsonPrimitive
import za.co.dioworkflows.mobile.model.LauncherSnapshot
import za.co.dioworkflows.mobile.model.PortfolioSnapshot
import za.co.dioworkflows.mobile.model.SurfaceId
import za.co.dioworkflows.mobile.model.SurfaceSnapshot

object LauncherStateParser {
    const val SCHEMA = "dio.local_launcher.state.v1"

    fun parse(raw: String): LauncherSnapshot {
        val root = try {
            requireObject(JsonParser.parseString(raw), "launcher state")
        } catch (exc: RuntimeException) {
            throw IllegalArgumentException("Invalid DIO launcher JSON", exc)
        }

        val schema = requireString(root, "schema")
        require(schema == SCHEMA) { "Unsupported DIO launcher schema: $schema" }
        val generatedAt = requireString(root, "generated_at")
        require(generatedAt.isNotBlank()) { "generated_at must not be blank" }

        val surfaces = parseSurfaces(requireArray(root, "surfaces"))
        val portfolioObject = requireObject(root.get("portfolio"), "portfolio")
        val portfolio = PortfolioSnapshot(
            verified = requireBoolean(portfolioObject, "verified"),
            baseCount = requireInt(portfolioObject, "base"),
            extensionCount = requireInt(portfolioObject, "extensions"),
            totalCount = requireInt(portfolioObject, "total"),
            rowCount = requireInt(portfolioObject, "row_count"),
            extensionState = requireString(portfolioObject, "extension_state"),
        )

        return LauncherSnapshot(
            schema = schema,
            generatedAt = generatedAt,
            surfaces = surfaces,
            portfolio = portfolio,
            surfacesReady = requireBoolean(root, "surfaces_ready"),
            ready = requireBoolean(root, "ready"),
            authorityCreated = requireBoolean(root, "authority_created"),
            readOnly = requireBoolean(root, "read_only"),
        )
    }

    private fun parseSurfaces(array: JsonArray): List<SurfaceSnapshot> {
        val seen = mutableSetOf<SurfaceId>()
        val surfaces = array.map { element ->
            val obj = requireObject(element, "surface")
            val id = SurfaceId.fromWireId(requireString(obj, "id"))
            require(seen.add(id)) { "Duplicate DIO surface: ${id.wireId}" }
            val name = requireString(obj, "name")
            val url = requireString(obj, "url")
            require(url == id.canonicalUrl) {
                "Unexpected URL for ${id.wireId}: $url"
            }
            SurfaceSnapshot(
                id = id,
                name = name,
                url = url,
                ready = requireBoolean(obj, "ready"),
            )
        }
        require(seen == SurfaceId.entries.toSet()) { "DIO launcher must report all four required surfaces" }
        return surfaces.sortedBy { it.id.ordinal }
    }

    private fun requireObject(element: JsonElement?, label: String): JsonObject {
        require(element != null && element.isJsonObject) { "$label must be an object" }
        return element.asJsonObject
    }

    private fun requireArray(obj: JsonObject, key: String): JsonArray {
        val element = obj.get(key)
        require(element != null && element.isJsonArray) { "$key must be an array" }
        return element.asJsonArray
    }

    private fun requirePrimitive(obj: JsonObject, key: String): JsonPrimitive {
        val element = obj.get(key)
        require(element != null && element.isJsonPrimitive) { "$key must be a primitive value" }
        return element.asJsonPrimitive
    }

    private fun requireString(obj: JsonObject, key: String): String {
        val value = requirePrimitive(obj, key)
        require(value.isString) { "$key must be a string" }
        return value.asString
    }

    private fun requireBoolean(obj: JsonObject, key: String): Boolean {
        val value = requirePrimitive(obj, key)
        require(value.isBoolean) { "$key must be a boolean" }
        return value.asBoolean
    }

    private fun requireInt(obj: JsonObject, key: String): Int {
        val value = requirePrimitive(obj, key)
        require(value.isNumber) { "$key must be a number" }
        return try {
            value.asBigDecimal.intValueExact()
        } catch (exc: ArithmeticException) {
            throw IllegalArgumentException("$key must be an exact integer", exc)
        } catch (exc: NumberFormatException) {
            throw IllegalArgumentException("$key must be an exact integer", exc)
        }
    }
}
