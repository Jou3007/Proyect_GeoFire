package com.geofire.campo.network

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

/**
 * AQUI SE CONFIGURA TU URL DE NGROK.
 *
 * Esta es la direccion por defecto si el telefono no logra leer la configuracion
 * remota (ver ConfigServidor.kt). Cambiarla aqui exige recompilar la app; para
 * cambiarla SIN recompilar, edita movil-campo/servidor.json en el repositorio.
 */
const val URL_BASE_POR_DEFECTO = "https://plank-retired-amuck.ngrok-free.dev/"

object RetrofitClient {
    private val cache = mutableMapOf<String, GeoFireApiService>()

    fun servicio(urlBase: String): GeoFireApiService = synchronized(this) {
        val base = if (urlBase.endsWith("/")) urlBase else "$urlBase/"
        cache.getOrPut(base) {
            val registroHttp = HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.BASIC
            }
            val cliente = OkHttpClient.Builder()
                .addInterceptor(registroHttp)
                .connectTimeout(20, TimeUnit.SECONDS)
                .readTimeout(60, TimeUnit.SECONDS)
                .writeTimeout(120, TimeUnit.SECONDS) // subir video puede tardar
                .build()
            Retrofit.Builder()
                .baseUrl(base)
                .client(cliente)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(GeoFireApiService::class.java)
        }
    }
}
