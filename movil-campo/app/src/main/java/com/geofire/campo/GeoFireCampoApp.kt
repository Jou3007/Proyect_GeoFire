package com.geofire.campo

import android.app.Application
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.geofire.campo.services.SyncWorker
import java.util.concurrent.TimeUnit

class GeoFireCampoApp : Application() {

    override fun onCreate() {
        super.onCreate()
        programarSincronizacion()
    }

    /**
     * El SyncWorker corre cada 15 minutos como respaldo (es el minimo que permite
     * Android para trabajo periodico). Para que un reporte no espere ese intervalo
     * si ya hay señal en el momento, DashboardScreen dispara ademas un envio
     * inmediato con intentarEnviarAhora() justo despues de guardar cada reporte.
     */
    private fun programarSincronizacion() {
        val restricciones = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
        val tarea = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
            .setConstraints(restricciones)
            .build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "sincronizar_reportes_geofire",
            ExistingPeriodicWorkPolicy.KEEP,
            tarea,
        )
    }
}
