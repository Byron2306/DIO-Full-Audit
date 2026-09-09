package za.co.dioworkflows.mobile

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import za.co.dioworkflows.mobile.model.ConnectionPhase
import za.co.dioworkflows.mobile.model.SurfaceId
import za.co.dioworkflows.mobile.repository.DioRuntime
import za.co.dioworkflows.mobile.security.SecureIdentityStore
import za.co.dioworkflows.mobile.service.DioConnectionService
import za.co.dioworkflows.mobile.ssh.DioProfileStore
import za.co.dioworkflows.mobile.ssh.DioSshProfile
import za.co.dioworkflows.mobile.ssh.HostKeyPinStore
import za.co.dioworkflows.mobile.ui.DioHomeScreen
import za.co.dioworkflows.mobile.ui.DioSurfaceScreen
import za.co.dioworkflows.mobile.ui.SetupScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface {
                    DioOperatorApp()
                }
            }
        }
    }
}

@Composable
private fun DioOperatorApp() {
    val context = LocalContext.current
    val identityStore = remember(context) { SecureIdentityStore(context) }
    val profileStore = remember(context) { DioProfileStore.from(context) }
    val hostKeyPinStore = remember(context) { HostKeyPinStore.from(context) }

    var savedProfile by remember { mutableStateOf(profileStore.load()) }
    var publicIdentity by remember {
        mutableStateOf(runCatching { identityStore.publicIdentity() }.getOrNull())
    }
    var pinnedFingerprint by remember { mutableStateOf(hostKeyPinStore.pinned()) }
    var showSetup by remember {
        mutableStateOf(
            savedProfile == null || publicIdentity == null || pinnedFingerprint == null,
        )
    }
    var currentSurface by remember { mutableStateOf<SurfaceId?>(null) }

    val appState by DioRuntime.repository.state.collectAsState()
    val untrustedFingerprint by DioRuntime.untrustedFingerprint.collectAsState()
    val connectionError by DioRuntime.connectionError.collectAsState()

    val configured =
        savedProfile != null && publicIdentity != null && pinnedFingerprint != null

    LaunchedEffect(configured, showSetup) {
        if (configured && !showSetup) {
            startConnection(context)
        }
    }

    LaunchedEffect(appState.phase, currentSurface) {
        if (currentSurface != null && appState.phase != ConnectionPhase.READY) {
            currentSurface = null
        }
    }

    BackHandler(enabled = currentSurface != null) {
        currentSurface = null
    }

    val surface = currentSurface
    when {
        surface != null -> {
            DioSurfaceScreen(
                surface = surface,
                onBack = { currentSurface = null },
            )
        }

        showSetup -> {
            SetupScreen(
                profile = savedProfile,
                publicIdentity = publicIdentity,
                untrustedFingerprint = untrustedFingerprint,
                pinnedFingerprint = pinnedFingerprint,
                connectionError = connectionError,
                onCreateIdentity = {
                    publicIdentity = identityStore.createIdentity()
                },
                onCopyPublicKey = { value -> copyText(context, value) },
                onProbeHost = { host, port, username ->
                    val profile = DioSshProfile(
                        host = host.trim(),
                        username = username.trim(),
                        port = port,
                    )
                    profileStore.save(profile)
                    savedProfile = profile
                    if (publicIdentity == null) {
                        publicIdentity = identityStore.createIdentity()
                    }
                    DioRuntime.clearUntrustedFingerprint()
                    DioRuntime.clearConnectionError()
                    startConnection(context)
                },
                onTrustHost = { fingerprint ->
                    hostKeyPinStore.pin(fingerprint)
                    pinnedFingerprint = fingerprint
                    DioRuntime.clearUntrustedFingerprint()
                    DioRuntime.clearConnectionError()
                },
                onResetTrust = {
                    stopConnection(context)
                    hostKeyPinStore.clear()
                    pinnedFingerprint = null
                    DioRuntime.clearConnectionError()
                },
                onContinue = {
                    if (savedProfile != null && publicIdentity != null && pinnedFingerprint != null) {
                        showSetup = false
                        startConnection(context)
                    }
                },
            )
        }

        else -> {
            DioHomeScreen(
                state = appState,
                onOpenSurface = { id -> currentSurface = id },
                onDisconnect = { stopConnection(context) },
                onReconnect = { startConnection(context) },
                onSettings = { showSetup = true },
                hostIdentityWarning = untrustedFingerprint,
            )
        }
    }
}

private fun startConnection(context: Context) {
    val intent = Intent(context, DioConnectionService::class.java).apply {
        action = DioConnectionService.ACTION_CONNECT
    }
    context.startForegroundService(intent)
}

private fun stopConnection(context: Context) {
    val intent = Intent(context, DioConnectionService::class.java).apply {
        action = DioConnectionService.ACTION_DISCONNECT
    }
    context.startService(intent)
}

private fun copyText(context: Context, value: String) {
    val clipboard = context.getSystemService(ClipboardManager::class.java)
    clipboard.setPrimaryClip(ClipData.newPlainText("DIO Mobile public key", value))
}
