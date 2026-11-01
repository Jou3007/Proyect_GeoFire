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

    /** El SyncWorker solo se activa cuando Android avisa que ya hay internet. */
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
