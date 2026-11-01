package com.geofire.campo.services

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.geofire.campo.data.local.ReportDatabase
import com.geofire.campo.data.local.UbicacionDao
import com.geofire.campo.network.ConfigServidor
import com.geofire.campo.network.GeoFireApiService
import com.geofire.campo.network.RetrofitClient
import com.geofire.campo.network.UbicacionRequest
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File

/**
 * WorkManager lo activa solo cuando el sistema detecta que hay internet
 * (ver la restriccion NetworkType.CONNECTED al programarlo en GeoFireCampoApp).
 * Lee lo que quedo pendiente en Room y lo manda al servidor.
 */
class SyncWorker(appContext: Context, params: WorkerParameters) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val dao = ReportDatabase.obtener(applicationContext).reportDao()
        val daoUbicacion = ReportDatabase.obtener(applicationContext).ubicacionDao()
        val urlBase = ConfigServidor.urlBaseActual(applicationContext)
        val servicio = RetrofitClient.servicio(urlBase)

        var huboFallo = enviarUbicacionesPendientes(daoUbicacion, servicio)

        val pendientes = dao.pendientes()
        if (pendientes.isEmpty() && !huboFallo) return Result.success()

        for (reporte in pendientes) {
            try {
                val archivoPart = reporte.rutaArchivo?.let { ruta ->
                    val archivo = File(ruta)
                    if (archivo.exists()) {
                        val tipoMedia = when (reporte.tipo) {
                            "FOTO" -> "image/jpeg"
                            "VIDEO" -> "video/mp4"
                            "AUDIO" -> "audio/mp4"
                            else -> "application/octet-stream"
                        }
                        MultipartBody.Part.createFormData(
                            "archivo", archivo.name, archivo.asRequestBody(tipoMedia.toMediaTypeOrNull()),
                        )
                    } else null
                }
                val respuesta = servicio.enviarReporte(
                    correo = reporte.correoUsuario.toRequestBody("text/plain".toMediaTypeOrNull()),
                    tipo = reporte.tipo.toRequestBody("text/plain".toMediaTypeOrNull()),
                    latitud = (reporte.latitud ?: 0.0).toString().toRequestBody("text/plain".toMediaTypeOrNull()),
                    longitud = (reporte.longitud ?: 0.0).toString().toRequestBody("text/plain".toMediaTypeOrNull()),
                    nota = reporte.nota.toRequestBody("text/plain".toMediaTypeOrNull()),
                    marcaTiempo = reporte.marcaTiempo.toString().toRequestBody("text/plain".toMediaTypeOrNull()),
                    archivo = archivoPart,
                )
                if (respuesta.isSuccessful) {
                    dao.actualizar(reporte.copy(enviado = true, ultimoError = null))
                } else {
                    huboFallo = true
                    dao.actualizar(reporte.copy(intentos = reporte.intentos + 1, ultimoError = "HTTP ${respuesta.code()}"))
                }
            } catch (excepcion: Exception) {
                huboFallo = true
                dao.actualizar(reporte.copy(intentos = reporte.intentos + 1, ultimoError = excepcion.message))
            }
        }
        // si algo fallo, WorkManager reintenta mas tarde en cuanto vuelva a haber red
        return if (huboFallo) Result.retry() else Result.success()
    }

    private suspend fun enviarUbicacionesPendientes(dao: UbicacionDao, servicio: GeoFireApiService): Boolean {
        var huboFallo = false
        for (ubicacion in dao.pendientes()) {
            try {
                val respuesta = servicio.enviarUbicacion(
                    UbicacionRequest(ubicacion.correoUsuario, ubicacion.latitud, ubicacion.longitud, ubicacion.marcaTiempo),
                )
                if (respuesta.isSuccessful) {
                    dao.actualizar(ubicacion.copy(enviado = true))
                } else {
                    huboFallo = true
                }
            } catch (_: Exception) {
                huboFallo = true
            }
        }
        return huboFallo
    }
}
