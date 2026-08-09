package com.metatron.agent

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.navigation.NavController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import kotlinx.coroutines.*
import java.net.URL

// ─── Color palette ────────────────────────────────────────────────────────────
object SeraphColors {
    val bg         = androidx.compose.ui.graphics.Color(0xFF02050D)
    val card       = androidx.compose.ui.graphics.Color(0xFF0A1220)
    val cyan       = androidx.compose.ui.graphics.Color(0xFF00F0FF)
    val pink       = androidx.compose.ui.graphics.Color(0xFFFF2BD6)
    val purple     = androidx.compose.ui.graphics.Color(0xFFBC13FE)
    val green      = androidx.compose.ui.graphics.Color(0xFF39FF14)
    val orange     = androidx.compose.ui.graphics.Color(0xFFFF8C00)
    val textPri    = androidx.compose.ui.graphics.Color(0xFFE0F8FF)
    val textSec    = androidx.compose.ui.graphics.Color(0xFF6AAFBD)
    val border     = androidx.compose.ui.graphics.Color(0x5000F0FF)
}

// ─── Preferences ─────────────────────────────────────────────────────────────
private const val PREFS = "seraph_agent_prefs"
private const val KEY_BACKEND = "backend_url"
private const val KEY_ENROLL  = "enrollment_key"
private const val KEY_SETUP_DONE = "setup_complete"

private fun prefs(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

// ─── Termux helpers ──────────────────────────────────────────────────────────
private const val TERMUX_PKG = "com.termux"
private const val TERMUX_BOOT_PKG = "com.termux.boot"
private const val WIREGUARD_PKG = "com.wireguard.android"
private const val FDROID_URL = "https://f-droid.org/packages/com.termux/"
private const val TERMUX_BOOT_FDROID = "https://f-droid.org/packages/com.termux.boot/"
private const val WIREGUARD_PLAY = "https://play.google.com/store/apps/details?id=com.wireguard.android"

private fun isInstalled(ctx: Context, pkg: String): Boolean = try {
    ctx.packageManager.getPackageInfo(pkg, 0)
    true
} catch (e: PackageManager.NameNotFoundException) { false }

private fun openUrl(ctx: Context, url: String) {
    ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
        flags = Intent.FLAG_ACTIVITY_NEW_TASK
    })
}

private fun openApp(ctx: Context, pkg: String) {
    val intent = ctx.packageManager.getLaunchIntentForPackage(pkg)
    if (intent != null) {
        intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
        ctx.startActivity(intent)
    }
}

/** Send a bash command to Termux via its RUN_COMMAND API */
private fun runInTermux(ctx: Context, command: String) {
    try {
        val intent = Intent().apply {
            setClassName(TERMUX_PKG, "com.termux.app.RunCommandService")
            action = "com.termux.RUN_COMMAND"
            putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/bash")
            putExtra("com.termux.RUN_COMMAND_ARGUMENTS", arrayOf("-c", command))
            putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home")
            putExtra("com.termux.RUN_COMMAND_TERMINAL", true)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        ctx.startActivity(intent)
    } catch (_: Exception) {
        openApp(ctx, TERMUX_PKG)
    }
}

/** Build the one-shot bootstrap script sent into Termux */
private fun buildBootstrapScript(backendUrl: String, enrollKey: String): String {
    val safe = backendUrl.trimEnd('/')
    val key  = enrollKey.ifBlank { "dev-agent-secret-change-in-production" }
    return """
pkg update -y && pkg upgrade -y
pkg install -y python wget curl openssh wireguard-tools iproute2
pip install --upgrade pip
pip install requests aiohttp flask flask-cors websockets psutil cryptography pyyaml

mkdir -p ~/seraph-agent && cd ~/seraph-agent
curl -fsSL -H 'ngrok-skip-browser-warning: 1' '$safe/api/unified/agent/download' -o agent.tar.gz
tar -xzf agent.tar.gz && rm -f agent.tar.gz

cat > start.sh <<'STARTEOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/seraph-agent
export REMOTE_SERVER_URL='$safe'
export BACKEND_URL='$safe'
export SERAPH_ENROLLMENT_KEY='$key'
export LOCAL_DASHBOARD_PORT=5000
python ui/web/app.py --port 5000 2>&1 | tee ~/seraph-agent/agent.log
STARTEOF
chmod +x start.sh

# Termux:Boot autostart
mkdir -p ~/.termux/boot
cp start.sh ~/.termux/boot/seraph-agent.sh

echo "=== SERAPH AGENT INSTALLED. Starting... ==="
bash start.sh &
echo "Dashboard will be available at http://localhost:5000"
    """.trimIndent()
}

// ─── UI Components ────────────────────────────────────────────────────────────
@Composable
fun SeraphCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(SeraphColors.card, RoundedCornerShape(4.dp))
            .border(1.dp, SeraphColors.border, RoundedCornerShape(4.dp))
            .padding(16.dp),
        content = content
    )
}

@Composable
fun SeraphButton(
    text: String,
    onClick: () -> Unit,
    color: androidx.compose.ui.graphics.Color = SeraphColors.cyan,
    enabled: Boolean = true,
    modifier: Modifier = Modifier,
) {
    Button(
        onClick = onClick,
        enabled = enabled,
        colors = ButtonDefaults.buttonColors(
            backgroundColor = color.copy(alpha = 0.15f),
            disabledBackgroundColor = SeraphColors.card,
        ),
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, if (enabled) color.copy(alpha = 0.8f) else SeraphColors.border, RoundedCornerShape(2.dp)),
        shape = RoundedCornerShape(2.dp),
        elevation = ButtonDefaults.elevation(0.dp, 0.dp, 0.dp),
    ) {
        Text(
            text,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            fontSize = 11.sp,
            color = if (enabled) color else SeraphColors.textSec,
        )
    }
}

@Composable
fun StatusDot(installed: Boolean, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 4.dp)) {
        Box(
            Modifier
                .size(8.dp)
                .background(
                    if (installed) SeraphColors.green else SeraphColors.orange,
                    RoundedCornerShape(50)
                )
        )
        Spacer(Modifier.width(8.dp))
        Text(label, fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = SeraphColors.textPri)
        Spacer(Modifier.weight(1f))
        Text(
            if (installed) "INSTALLED" else "NOT FOUND",
            fontFamily = FontFamily.Monospace,
            fontSize = 9.sp,
            color = if (installed) SeraphColors.green else SeraphColors.orange,
        )
    }
}

// ─── Screens ─────────────────────────────────────────────────────────────────
@Composable
fun SetupScreen(ctx: Context, onComplete: () -> Unit) {
    val prefs = remember { prefs(ctx) }
    var backendUrl by remember { mutableStateOf(prefs.getString(KEY_BACKEND, "") ?: "") }
    var enrollKey  by remember { mutableStateOf(prefs.getString(KEY_ENROLL, "") ?: "") }
    var status     by remember { mutableStateOf("") }

    val termuxOk    = isInstalled(ctx, TERMUX_PKG)
    val termuxBoot  = isInstalled(ctx, TERMUX_BOOT_PKG)
    val wireguardOk = isInstalled(ctx, WIREGUARD_PKG)

    Column(
        Modifier
            .fillMaxSize()
            .background(SeraphColors.bg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Header
        Text(
            "◈ SERAPH UNIFIED AGENT",
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Black,
            fontSize = 18.sp,
            color = SeraphColors.cyan,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp)
        )
        Text(
            "ONE-SIZE-FITS-ALL ANDROID INSTALLER",
            fontFamily = FontFamily.Monospace,
            fontSize = 9.sp,
            letterSpacing = 0.15.sp,
            color = SeraphColors.textSec,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth()
        )

        Divider(color = SeraphColors.border)

        // Step 1: Dependencies
        SeraphCard {
            Text("STEP 1 — INSTALL DEPENDENCIES",
                fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
                fontSize = 11.sp, color = SeraphColors.pink)
            Spacer(Modifier.height(12.dp))
            StatusDot(termuxOk, "Termux (F-Droid)")
            StatusDot(termuxBoot, "Termux:Boot (autostart)")
            StatusDot(wireguardOk, "WireGuard VPN")
            Spacer(Modifier.height(10.dp))
            if (!termuxOk) {
                SeraphButton("⬇ Install Termux from F-Droid", { openUrl(ctx, FDROID_URL) }, SeraphColors.cyan)
                Spacer(Modifier.height(6.dp))
            }
            if (!termuxBoot) {
                SeraphButton("⬇ Install Termux:Boot from F-Droid", { openUrl(ctx, TERMUX_BOOT_FDROID) }, SeraphColors.purple)
                Spacer(Modifier.height(6.dp))
            }
            if (!wireguardOk) {
                SeraphButton("⬇ Install WireGuard from Play Store", { openUrl(ctx, WIREGUARD_PLAY) }, SeraphColors.pink)
            }
            if (termuxOk && termuxBoot && wireguardOk) {
                Text("✓ All dependencies installed", fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp, color = SeraphColors.green)
            }
        }

        // Step 2: Backend config
        SeraphCard {
            Text("STEP 2 — BACKEND CONFIGURATION",
                fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
                fontSize = 11.sp, color = SeraphColors.pink)
            Spacer(Modifier.height(10.dp))
            Text("Backend URL (ngrok / nginx):", fontFamily = FontFamily.Monospace,
                fontSize = 10.sp, color = SeraphColors.textSec)
            Spacer(Modifier.height(4.dp))
            OutlinedTextField(
                value = backendUrl,
                onValueChange = { backendUrl = it },
                placeholder = { Text("https://xxxx.ngrok-free.app", fontFamily = FontFamily.Monospace, fontSize = 10.sp) },
                textStyle = LocalTextStyle.current.copy(
                    fontFamily = FontFamily.Monospace, fontSize = 10.sp, color = SeraphColors.textPri),
                colors = TextFieldDefaults.outlinedTextFieldColors(
                    focusedBorderColor = SeraphColors.cyan,
                    unfocusedBorderColor = SeraphColors.border,
                    cursorColor = SeraphColors.cyan,
                ),
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            )
            Spacer(Modifier.height(10.dp))
            Text("Enrollment Key (optional):", fontFamily = FontFamily.Monospace,
                fontSize = 10.sp, color = SeraphColors.textSec)
            Spacer(Modifier.height(4.dp))
            OutlinedTextField(
                value = enrollKey,
                onValueChange = { enrollKey = it },
                placeholder = { Text("leave blank to use default", fontFamily = FontFamily.Monospace, fontSize = 10.sp) },
                textStyle = LocalTextStyle.current.copy(
                    fontFamily = FontFamily.Monospace, fontSize = 10.sp, color = SeraphColors.textPri),
                colors = TextFieldDefaults.outlinedTextFieldColors(
                    focusedBorderColor = SeraphColors.cyan,
                    unfocusedBorderColor = SeraphColors.border,
                    cursorColor = SeraphColors.cyan,
                ),
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
        }

        // Step 3: Bootstrap into Termux
        SeraphCard {
            Text("STEP 3 — BOOTSTRAP AGENT IN TERMUX",
                fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
                fontSize = 11.sp, color = SeraphColors.pink)
            Spacer(Modifier.height(8.dp))
            Text(
                "Tapping the button below will save your config, open Termux, and run the full installation script. " +
                "It installs Python, downloads the agent, configures WireGuard, and starts the dashboard on port 5000.",
                fontFamily = FontFamily.Monospace, fontSize = 9.sp, color = SeraphColors.textSec,
            )
            Spacer(Modifier.height(10.dp))
            SeraphButton(
                "▶ INSTALL & LAUNCH AGENT IN TERMUX",
                onClick = {
                    if (backendUrl.isBlank()) {
                        status = "ERROR: Backend URL is required"
                        return@SeraphButton
                    }
                    prefs.edit()
                        .putString(KEY_BACKEND, backendUrl.trimEnd('/'))
                        .putString(KEY_ENROLL, enrollKey)
                        .putBoolean(KEY_SETUP_DONE, true)
                        .apply()
                    val script = buildBootstrapScript(backendUrl, enrollKey)
                    runInTermux(ctx, script)
                    status = "✓ Bootstrap sent to Termux. Check Termux terminal."
                },
                color = SeraphColors.green,
                enabled = termuxOk,
            )
            if (!termuxOk) {
                Text("⚠ Install Termux first (Step 1)", fontFamily = FontFamily.Monospace,
                    fontSize = 9.sp, color = SeraphColors.orange)
            }
            if (status.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text(status, fontFamily = FontFamily.Monospace, fontSize = 9.sp,
                    color = if (status.startsWith("ERROR")) SeraphColors.pink else SeraphColors.green)
            }
        }

        // Step 4: Open dashboard
        SeraphCard {
            Text("STEP 4 — OPEN WEB DASHBOARD",
                fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
                fontSize = 11.sp, color = SeraphColors.pink)
            Spacer(Modifier.height(8.dp))
            Text(
                "After the agent starts in Termux, tap below to open the full Seraph dashboard at localhost:5000.",
                fontFamily = FontFamily.Monospace, fontSize = 9.sp, color = SeraphColors.textSec,
            )
            Spacer(Modifier.height(10.dp))
            SeraphButton("🌐 OPEN WEB DASHBOARD (port 5000)", onComplete, SeraphColors.cyan)
            Spacer(Modifier.height(6.dp))
            val savedUrl = prefs.getString(KEY_BACKEND, "") ?: ""
            if (savedUrl.isNotEmpty()) {
                SeraphButton("☁ OPEN REMOTE DASHBOARD", { openUrl(ctx, "$savedUrl") }, SeraphColors.purple)
            }
        }

        Spacer(Modifier.height(24.dp))
    }
}

@Composable
fun DashboardWebView(ctx: Context, url: String = "http://localhost:5000") {
    var error by remember { mutableStateOf<String?>(null) }

    Box(Modifier.fillMaxSize().background(SeraphColors.bg)) {
        AndroidView(
            factory = { context ->
                WebView(context).apply {
                    settings.apply {
                        javaScriptEnabled = true
                        domStorageEnabled = true
                        loadWithOverviewMode = true
                        useWideViewPort = true
                        builtInZoomControls = false
                        displayZoomControls = false
                        mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                        cacheMode = WebSettings.LOAD_NO_CACHE
                        setBackgroundColor(Color.parseColor("#02050D"))
                    }
                    webViewClient = object : WebViewClient() {
                        override fun onReceivedError(
                            view: WebView?, request: WebResourceRequest?, err: WebResourceError?
                        ) {
                            if (request?.isForMainFrame == true) {
                                error = "Agent not running yet. Start it in Termux first."
                            }
                        }
                    }
                    loadUrl(url)
                }
            },
            modifier = Modifier.fillMaxSize()
        )

        error?.let { msg ->
            Column(
                Modifier.fillMaxSize().background(SeraphColors.bg),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Text("◈", fontSize = 48.sp, color = SeraphColors.cyan)
                Spacer(Modifier.height(16.dp))
                Text("DASHBOARD UNAVAILABLE", fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold, fontSize = 14.sp, color = SeraphColors.pink,
                    textAlign = TextAlign.Center)
                Spacer(Modifier.height(8.dp))
                Text(msg, fontFamily = FontFamily.Monospace, fontSize = 10.sp,
                    color = SeraphColors.textSec, textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 32.dp))
                Spacer(Modifier.height(24.dp))
                Text("Open Termux and run: bash ~/seraph-agent/start.sh",
                    fontFamily = FontFamily.Monospace, fontSize = 9.sp,
                    color = SeraphColors.textSec, textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 32.dp))
            }
        }
    }
}

@Composable
fun LogsScreen(ctx: Context) {
    var log by remember { mutableStateOf("Loading…") }
    val scope = rememberCoroutineScope()
    LaunchedEffect(Unit) {
        scope.launch(Dispatchers.IO) {
            log = try {
                java.io.File(
                    "/data/data/com.termux/files/home/seraph-agent/agent.log"
                ).takeIf { it.exists() }?.readText()?.takeLast(8000) ?: "No log file found yet."
            } catch (e: Exception) { "Cannot read log: ${e.message}" }
        }
    }
    Column(
        Modifier
            .fillMaxSize()
            .background(SeraphColors.bg)
            .padding(12.dp)
    ) {
        Text("AGENT LOGS", fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
            fontSize = 12.sp, color = SeraphColors.cyan)
        Spacer(Modifier.height(8.dp))
        Text(
            log,
            fontFamily = FontFamily.Monospace, fontSize = 8.sp, color = SeraphColors.textPri,
            modifier = Modifier.verticalScroll(rememberScrollState())
        )
    }
}

// ─── Main ────────────────────────────────────────────────────────────────────
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { SeraphAgentApp(applicationContext) }
    }
}

@Composable
fun SeraphAgentApp(ctx: Context) {
    val nav = rememberNavController()

    Scaffold(
        backgroundColor = SeraphColors.bg,
        bottomBar = {
            val entry by nav.currentBackStackEntryAsState()
            val route = entry?.destination?.route
            BottomNavigation(backgroundColor = SeraphColors.card, elevation = 0.dp) {
                BottomNavigationItem(
                    icon = { Icon(Icons.Filled.Settings, null) },
                    label = { Text("Setup", fontFamily = FontFamily.Monospace, fontSize = 9.sp) },
                    selected = route == "setup",
                    onClick = { nav.navigate("setup") { launchSingleTop = true } },
                    selectedContentColor = SeraphColors.cyan,
                    unselectedContentColor = SeraphColors.textSec,
                )
                BottomNavigationItem(
                    icon = { Icon(Icons.Filled.Home, null) },
                    label = { Text("Dashboard", fontFamily = FontFamily.Monospace, fontSize = 9.sp) },
                    selected = route == "dashboard",
                    onClick = { nav.navigate("dashboard") { launchSingleTop = true } },
                    selectedContentColor = SeraphColors.cyan,
                    unselectedContentColor = SeraphColors.textSec,
                )
                BottomNavigationItem(
                    icon = { Icon(Icons.Filled.List, null) },
                    label = { Text("Logs", fontFamily = FontFamily.Monospace, fontSize = 9.sp) },
                    selected = route == "logs",
                    onClick = { nav.navigate("logs") { launchSingleTop = true } },
                    selectedContentColor = SeraphColors.cyan,
                    unselectedContentColor = SeraphColors.textSec,
                )
            }
        }
    ) { padding ->
        Box(Modifier.padding(padding)) {
            NavHost(nav, startDestination = "setup") {
                composable("setup") {
                    SetupScreen(ctx) { nav.navigate("dashboard") }
                }
                composable("dashboard") {
                    DashboardWebView(ctx, "http://localhost:5000")
                }
                composable("logs") {
                    LogsScreen(ctx)
                }
            }
        }
    }
}
