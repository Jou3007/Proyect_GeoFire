package com.geofire.campo.network

import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part

data class LoginRequest(val correo: String, val clave: String)
data class LoginResponse(val ok: Boolean, val nombre: String? = null, val rol: String? = null, val mensaje: String? = null)
data class ReporteRespuesta(val ok: Boolean, val id: Long? = null)

interface GeoFireApiService {

    @POST("api/campo/login")
    suspend fun iniciarSesion(@Body datos: LoginRequest): Response<LoginResponse>

    /**
     * Envia un reporte de campo. El archivo (foto/audio/video) es opcional: el SOS
     * puede ir solo con la ubicacion.
     */
    @Multipart
    @POST("api/campo/reportes")
    suspend fun enviarReporte(
        @Part("correo") correo: RequestBody,
        @Part("tipo") tipo: RequestBody,
        @Part("latitud") latitud: RequestBody,
        @Part("longitud") longitud: RequestBody,
        @Part("nota") nota: RequestBody,
        @Part("marca_tiempo") marcaTiempo: RequestBody,
        @Part archivo: MultipartBody.Part?,
    ): Response<ReporteRespuesta>
}
