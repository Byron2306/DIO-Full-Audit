package za.co.dioworkflows.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import za.co.dioworkflows.mobile.model.ConnectionPhase
import za.co.dioworkflows.mobile.model.DioAppState
import za.co.dioworkflows.mobile.model.SurfaceId

@Composable
fun DioHomeScreen(
    state: DioAppState,
    onOpenSurface: (SurfaceId) -> Unit,
    onDisconnect: () -> Unit,
    onReconnect: () -> Unit = {},
    onSettings: () -> Unit = {},
    hostIdentityWarning: String? = null,
) {
    val phaseLabel = when (state.phase) {
        ConnectionPhase.UNCONFIGURED -> "UNCONFIGURED"
        ConnectionPhase.CONNECTING -> "CONNECTING"
        ConnectionPhase.CONNECTED_HELD -> "HELD"
        ConnectionPhase.READY -> "READY"
        ConnectionPhase.DISCONNECTED -> "DISCONNECTED"
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text(
            text = "DIO",
            style = MaterialTheme.typography.displaySmall,
            fontWeight = FontWeight.Black,
        )
        Text(
            text = "Deterministic Intelligence Operator Console",
            style = MaterialTheme.typography.titleMedium,
        )

        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(),
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text("Connection", style = MaterialTheme.typography.labelLarge)
                Text(
                    text = phaseLabel,
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.Bold,
                )
                state.generatedAt?.let { generatedAt ->
                    Text("Live truth · $generatedAt", style = MaterialTheme.typography.bodySmall)
                }
            }
        }

        hostIdentityWarning?.let {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text("HOST IDENTITY CHECK REQUIRED", fontWeight = FontWeight.Bold)
                    Text("Debian presented an untrusted SSH fingerprint. Open connection settings before reconnecting.")
                }
            }
        }

        val portfolio = state.portfolio
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text("Portfolio truth", style = MaterialTheme.typography.labelLarge)
                if (portfolio != null) {
                    Text(
                        text = "${portfolio.baseCount} + ${portfolio.extensionCount} = ${portfolio.totalCount}",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                    )
                    if (portfolio.verified) {
                        Text(
                            text = "${portfolio.totalCount} VERIFIED",
                            fontWeight = FontWeight.Bold,
                        )
                    }
                } else {
                    Text("No current verified portfolio truth")
                }
            }
        }

        Text(
            text = "Surfaces",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
        )

        SurfaceId.entries.forEach { id ->
            val snapshot = state.surfaces.firstOrNull { it.id == id }
            val ready = state.phase == ConnectionPhase.READY && snapshot?.ready == true
            Card(modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(14.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(id.displayName, fontWeight = FontWeight.SemiBold)
                        Text(
                            text = if (ready) "READY" else "UNAVAILABLE",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                    Button(
                        enabled = ready,
                        onClick = { onOpenSurface(id) },
                    ) {
                        Text("Open")
                    }
                }
            }
        }

        Spacer(Modifier.height(4.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Button(
                onClick = onReconnect,
                modifier = Modifier.weight(1f),
            ) {
                Text("Reconnect")
            }
            OutlinedButton(
                onClick = onDisconnect,
                modifier = Modifier.weight(1f),
            ) {
                Text("Disconnect")
            }
        }
        OutlinedButton(
            onClick = onSettings,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Connection settings")
        }
    }
}
