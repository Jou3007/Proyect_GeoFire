package com.geofire.campo.services

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.Looper
import androidx.core.app.NotificationCompat
import com.geofire.campo.data.SesionRepositorio
import com.geofire.campo.data.local.ReportDatabase
import com.geofire.campo.data.models.UbicacionEntity
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

private const val CANAL_ID = "geofire_rastreo"
private const val ID_NOTIFICACION = 1001
private const val INTERVALO_MS = 2 * 60 * 1000L // cada 2 minutos durante la jornada

/**
 * Jornada de campo (etapa 2): mientras esta encendido, registra la ubicacion
 * cada 2 minutos y la va guardando/enviando. Android exige, por su cuenta, una
 * notificacion visible y permanente en todo momento que este activo: eso es lo
 * que el guardaparque ve en la barra de notificaciones mientras dura la jornada.
 */
class LocationTrackingService : Service() {

    private val alcance = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private lateinit var clienteUbicacion: FusedLocationProviderClient
    private var correoUsuario: String = ""

    private val callbackUbicacion = object : LocationCallback() {
        override fun onLocationResult(resultado: LocationResult) {
            val ubicacion = resultado.lastLocation ?: return
            alcance.launch {
                val dao = ReportDatabase.obtener(applicationContext).ubicacionDao()
                dao.insertar(
                    UbicacionEntity(
                        latitud = ubicacion.latitude,
                        longitud = ubicacion.longitude,
                        marcaTiempo = System.currentTimeMillis(),
                        correoUsuario = correoUsuario,
                    ),
                )
                intentarEnviarAhora(applicationContext)
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        clienteUbicacion = LocationServices.getFusedLocationProviderClient(this)
        crearCanalNotificacion()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        correoUsuario = intent?.getStringExtra(EXTRA_CORREO) ?: correoUsuario
        alcance.launch {
            if (correoUsuario.isBlank()) {
                correoUsuario = SesionRepositorio.correoActual(applicationContext) ?: ""
            }
        }
        startForeground(ID_NOTIFICACION, construirNotificacion())
        iniciarActualizaciones()
        return START_STICKY
    }

    @Suppress("MissingPermission") // la pantalla valida el permiso de ubicacion antes de encender el servicio
    private fun iniciarActualizaciones() {
        val solicitud = LocationRequest.Builder(Priority.PRIORITY_BALANCED_POWER_ACCURACY, INTERVALO_MS).build()
        clienteUbicacion.requestLocationUpdates(solicitud, callbackUbicacion, Looper.getMainLooper())
    }

    override fun onDestroy() {
        clienteUbicacion.removeLocationUpdates(callbackUbicacion)
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun crearCanalNotificacion() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val canal = NotificationChannel(CANAL_ID, "Jornada de campo GeoFire", NotificationManager.IMPORTANCE_LOW)
        getSystemService(NotificationManager::class.java).createNotificationChannel(canal)
    }

    private fun construirNotificacion() =
        NotificationCompat.Builder(this, CANAL_ID)
            .setContentTitle("Jornada de campo activa")
            .setContentText("GeoFire está registrando tu ubicación para tu seguridad.")
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setOngoing(true)
            .build()

    companion object {
        const val EXTRA_CORREO = "correo"

        fun iniciar(context: Context, correo: String) {
            val intent = Intent(context, LocationTrackingService::class.java).putExtra(EXTRA_CORREO, correo)
            context.startForegroundService(intent)
        }

        fun detener(context: Context) {
            context.stopService(Intent(context, LocationTrackingService::class.java))
        }
    }
}
