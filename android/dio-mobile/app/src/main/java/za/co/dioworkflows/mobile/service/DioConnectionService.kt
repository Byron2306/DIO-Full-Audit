package za.co.dioworkflows.mobile.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.TimeUnit
import za.co.dioworkflows.mobile.repository.DioRuntime
import za.co.dioworkflows.mobile.security.SecureIdentityStore
import za.co.dioworkflows.mobile.ssh.DioProfileStore
import za.co.dioworkflows.mobile.ssh.DioSshTransport
import za.co.dioworkflows.mobile.ssh.HostKeyPinStore
import za.co.dioworkflows.mobile.ssh.TransportSession

/**
 * User-started, forward-only DIO transport service.
 *
 * The service owns no SSH shell or command channel. Its authority is limited to maintaining
 * the canonical loopback forwards and refreshing the read-only launcher truth endpoint.
 */
class DioConnectionService : Service() {
    private val executor = Executors.newSingleThreadScheduledExecutor { runnable ->
        Thread(runnable, "dio-mobile-connection").apply { isDaemon = true }
    }
    private val lock = Any()

    @Volatile
    private var session: TransportSession? = null
    private var refreshFuture: ScheduledFuture<*>? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CONNECT -> {
                enterForeground()
                executor.execute { connectInternal() }
            }

            ACTION_DISCONNECT -> executor.execute { disconnectInternal(stopService = true) }
            else -> stopSelf(startId)
        }
        return START_NOT_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        refreshFuture?.cancel(true)
        synchronized(lock) {
            session?.close()
            session = null
        }
        DioRuntime.repository.transportDisconnected()
        executor.shutdownNow()
        super.onDestroy()
    }

    private fun connectInternal() {
        disconnectTransportOnly()
        DioRuntime.repository.transportDisconnected()
        DioRuntime.clearUntrustedFingerprint()

        val profile = DioProfileStore.from(this).load()
        if (profile == null) {
            disconnectInternal(stopService = true)
            return
        }

        try {
            val identity = SecureIdentityStore(this)
            identity.createIdentity()
            val transport = DioSshTransport(identity, HostKeyPinStore.from(this))
            val established = transport.connect(profile) { fingerprint ->
                DioRuntime.reportUntrustedFingerprint(fingerprint)
            }
            synchronized(lock) {
                session = established
            }
            check(established.isHealthy()) { "DIO SSH session is not healthy" }

            DioRuntime.repository.refreshTruth(transportConnected = true)
            refreshFuture = executor.scheduleWithFixedDelay(
                { refreshOrFailClosed() },
                REFRESH_SECONDS,
                REFRESH_SECONDS,
                TimeUnit.SECONDS,
            )
        } catch (_: Exception) {
            disconnectInternal(stopService = true)
        }
    }

    private fun refreshOrFailClosed() {
        val active = synchronized(lock) { session }
        if (active?.isHealthy() == true) {
            DioRuntime.repository.refreshTruth(transportConnected = true)
        } else {
            disconnectInternal(stopService = true)
        }
    }

    private fun disconnectInternal(stopService: Boolean) {
        disconnectTransportOnly()
        DioRuntime.repository.transportDisconnected()
        if (stopService) {
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
        }
    }

    private fun disconnectTransportOnly() {
        refreshFuture?.cancel(false)
        refreshFuture = null
        val previous = synchronized(lock) {
            val value = session
            session = null
            value
        }
        previous?.close()
    }

    private fun enterForeground() {
        val notification = Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle("DIO Android")
            .setContentText("Encrypted connection to your DIO runtime")
            .setOngoing(true)
            .setCategory(Notification.CATEGORY_SERVICE)
            .build()

        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE,
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun createNotificationChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                "DIO connection",
                NotificationManager.IMPORTANCE_LOW,
            ).apply {
                description = "Keeps the user-started encrypted DIO connection active"
            },
        )
    }

    companion object {
        const val ACTION_CONNECT = "za.co.dioworkflows.mobile.action.CONNECT"
        const val ACTION_DISCONNECT = "za.co.dioworkflows.mobile.action.DISCONNECT"
        private const val CHANNEL_ID = "dio_connection"
        private const val NOTIFICATION_ID = 6801
        private const val REFRESH_SECONDS = 2L
    }
}
