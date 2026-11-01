package com.geofire.campo.network

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

private val Context.preferenciasServidor by preferencesDataStore("geofire_servidor")
private val CLAVE_URL = stringPreferencesKey("url_base")

/**
 * Si algun dia el enlace de ngrok cambia, basta con editar
 * movil-campo/servidor.json en GitHub: la app toma el valor nuevo solo,
 * sin que el guardaparque tenga que actualizar nada.
 */
private const val URL_CONFIG_REMOTA =
    "https://raw.githubusercontent.com/Jou3007/Proyect_GeoFire/main/movil-campo/servidor.json"

object ConfigServidor {

    suspend fun urlBaseActual(context: Context): String {
        val guardada = context.preferenciasServidor.data.first()[CLAVE_URL]
        return guardada ?: URL_BASE_POR_DEFECTO
    }

    /** Intenta leer la URL mas reciente de internet; si falla, no cambia nada. */
    suspend fun refrescar(context: Context): String = withContext(Dispatchers.IO) {
        try {
            val conexion = (URL(URL_CONFIG_REMOTA).openConnection() as HttpURLConnection)
            conexion.connectTimeout = 5000
            conexion.readTimeout = 5000
            val texto = conexion.inputStream.bufferedReader().readText()
            val url = Regex("\"url_base\"\\s*:\\s*\"([^\"]+)\"").find(texto)?.groupValues?.get(1)
            if (!url.isNullOrBlank()) {
                context.preferenciasServidor.edit { it[CLAVE_URL] = url }
                url
            } else {
                urlBaseActual(context)
            }
        } catch (_: IOException) {
            urlBaseActual(context)
        }
    }
}
