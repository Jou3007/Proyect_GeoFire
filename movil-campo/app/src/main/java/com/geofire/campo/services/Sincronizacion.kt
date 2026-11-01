package com.geofire.campo.services

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager

/**
 * Se llama justo despues de guardar cualquier reporte (foto, audio, video, SOS o
 * ubicacion). Si en ese momento ya hay señal, lo envia de inmediato; si no la hay,
 * Android simplemente no ejecuta esta tarea todavia y el respaldo cada 15 minutos
 * (programado en GeoFireCampoApp) se encarga despues.
 */
fun intentarEnviarAhora(context: Context) {
    val restricciones = Constraints.Builder()
        .setRequiredNetworkType(NetworkType.CONNECTED)
        .build()
    val tarea = OneTimeWorkRequestBuilder<SyncWorker>()
        .setConstraints(restricciones)
        .build()
    WorkManager.getInstance(context).enqueueUniqueWork(
        "enviar_ahora_geofire",
        ExistingWorkPolicy.APPEND_OR_REPLACE,
        tarea,
    )
}
