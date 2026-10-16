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
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import za.co.dioworkflows.mobile.security.SecureIdentityStore.PublicIdentity
import za.co.dioworkflows.mobile.ssh.DioSshProfile

@Composable
fun SetupScreen(
    profile: DioSshProfile?,
    publicIdentity: PublicIdentity?,
    untrustedFingerprint: String?,
    pinnedFingerprint: String?,
    connectionError: String?,
    onCreateIdentity: () -> Unit,
    onCopyPublicKey: (String) -> Unit,
    onProbeHost: (String, Int, String) -> Unit,
    onTrustHost: (String) -> Unit,
    onResetTrust: () -> Unit,
    onContinue: () -> Unit,
) {
    var host by rememberSaveable(profile?.host) { mutableStateOf(profile?.host.orEmpty()) }
    var portText by rememberSaveable(profile?.port) {
        mutableStateOf(profile?.port?.toString() ?: "22")
    }
    var username by rememberSaveable(profile?.username) {
        mutableStateOf(profile?.username ?: "byron")
    }

    val parsedPort = portText.toIntOrNull()
    val profileValid =
        host.isNotBlank() && username.isNotBlank() && parsedPort != null && parsedPort in 1..65535
    val trustChanged =
        pinnedFingerprint != null &&
            untrustedFingerprint != null &&
            pinnedFingerprint != untrustedFingerprint
    val canContinue = profile != null && publicIdentity != null && pinnedFingerprint != null

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text(
            text = "DIO Android",
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Bold,
        )
        Text(
            text = "One-time pairing to your Debian-hosted DIO runtime. Daily use stays inside this app.",
            style = MaterialTheme.typography.bodyLarge,
        )

        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(),
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text("1 · Debian connection", fontWeight = FontWeight.SemiBold)
                OutlinedTextField(
                    value = host,
                    onValueChange = { host = it },
                    label = { Text("Debian host or private IP") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedTextField(
                        value = portText,
                        onValueChange = { portText = it.filter(Char::isDigit).take(5) },
                        label = { Text("SSH port") },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                    )
                    OutlinedTextField(
                        value = username,
                        onValueChange = { username = it },
                        label = { Text("SSH user") },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                    )
                }
            }
        }

        Card(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text("2 · Phone identity", fontWeight = FontWeight.SemiBold)
                Text("DIO generates an app-specific key and protects its private material with Android Keystore.")
                if (publicIdentity == null) {
                    Button(onClick = onCreateIdentity) {
                        Text("Create DIO Mobile identity")
                    }
                } else {
                    Text("Public key", fontWeight = FontWeight.Medium)
                    SelectionContainer {
                        Text(
                            text = publicIdentity.openSshPublicKey,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                    OutlinedButton(onClick = { onCopyPublicKey(publicIdentity.openSshPublicKey) }) {
                        Text("Copy public key")
                    }
                    Text(
                        text = "Add this public key once to ~/.ssh/authorized_keys on Debian, then check the host fingerprint below.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }

        Card(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text("3 · Pin Debian identity", fontWeight = FontWeight.SemiBold)
                Button(
                    enabled = profileValid && publicIdentity != null,
                    onClick = { onProbeHost(host.trim(), parsedPort!!, username.trim()) },
                ) {
                    Text("Save & check host fingerprint")
                }

                connectionError?.let { error ->
                    SelectionContainer {
                        Text(
                            text = "Connection error: $error",
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }

                pinnedFingerprint?.let { pinned ->
                    Text("Pinned host", fontWeight = FontWeight.Medium)
                    SelectionContainer { Text(pinned, style = MaterialTheme.typography.bodySmall) }
                }

                untrustedFingerprint?.let { presented ->
                    HorizontalDivider()
                    Text(
                        text = if (trustChanged) {
                            "Debian presented a different host identity. Reset trust only if you intentionally changed the Debian SSH host key."
                        } else {
                            "Debian presented this host fingerprint. Verify it, then trust it explicitly."
                        },
                    )
                    SelectionContainer { Text(presented, style = MaterialTheme.typography.bodySmall) }

                    if (trustChanged) {
                        OutlinedButton(onClick = onResetTrust) {
                            Text("Reset pinned host key")
                        }
                    } else {
                        Button(onClick = { onTrustHost(presented) }) {
                            Text("Trust this Debian host")
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(4.dp))
        Button(
            enabled = canContinue,
            onClick = onContinue,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Open DIO")
        }
        Text(
            text = "DIO HTTP services remain localhost-only. The app carries them over the encrypted SSH tunnel.",
            style = MaterialTheme.typography.bodySmall,
        )
    }
}
