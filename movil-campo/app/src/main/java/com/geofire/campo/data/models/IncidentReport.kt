package com.geofire.campo.data.models

import androidx.room.Entity
import androidx.room.PrimaryKey

/** Tipo de evidencia que el guardaparque registra en campo. */
enum class TipoReporte {
    FOTO, AUDIO, VIDEO, SOS
}

/**
 * Un reporte generado en el telefono. Se guarda aqui primero porque en la selva
 * puede no haber señal; [SyncWorker] lo envia al servidor en cuanto la recupera.
 */
@Entity(tableName = "reportes_pendientes")
data class ReportEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val tipo: String,
    val latitud: Double?,
    val longitud: Double?,
    val nota: String,
    val marcaTiempo: Long,
    val rutaArchivo: String?,
    val correoUsuario: String,
    val enviado: Boolean = false,
    val intentos: Int = 0,
    val ultimoError: String? = null,
)
