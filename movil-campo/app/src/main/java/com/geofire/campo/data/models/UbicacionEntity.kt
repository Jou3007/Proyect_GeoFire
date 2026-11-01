package com.geofire.campo.data.models

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Un punto de ubicacion tomado durante la jornada (rastreo continuo, etapa 2).
 * Igual que los reportes: se guarda aqui primero y se envia cuando hay señal.
 */
@Entity(tableName = "ubicaciones_pendientes")
data class UbicacionEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val latitud: Double,
    val longitud: Double,
    val marcaTiempo: Long,
    val correoUsuario: String,
    val enviado: Boolean = false,
)
