package com.geofire.campo.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first

private val Context.preferenciasSesion by preferencesDataStore("geofire_sesion")
private val CLAVE_CORREO = stringPreferencesKey("correo")
private val CLAVE_NOMBRE = stringPreferencesKey("nombre")

/** Guarda quien inicio sesion para no pedirle la clave cada vez que abre la app. */
object SesionRepositorio {

    suspend fun guardar(context: Context, correo: String, nombre: String?) {
        context.preferenciasSesion.edit {
            it[CLAVE_CORREO] = correo
            it[CLAVE_NOMBRE] = nombre ?: correo
        }
    }

    suspend fun correoActual(context: Context): String? =
        context.preferenciasSesion.data.first()[CLAVE_CORREO]

    suspend fun nombreActual(context: Context): String? =
        context.preferenciasSesion.data.first()[CLAVE_NOMBRE]

    suspend fun cerrarSesion(context: Context) {
        context.preferenciasSesion.edit { it.clear() }
    }
}
