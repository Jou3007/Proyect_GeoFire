package com.geofire.campo.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import androidx.room.Update
import com.geofire.campo.data.models.ReportEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface ReportDao {

    @Insert
    suspend fun insertar(reporte: ReportEntity): Long

    @Update
    suspend fun actualizar(reporte: ReportEntity)

    @Query("SELECT * FROM reportes_pendientes WHERE enviado = 0 ORDER BY marcaTiempo ASC")
    suspend fun pendientes(): List<ReportEntity>

    @Query("SELECT * FROM reportes_pendientes ORDER BY marcaTiempo DESC")
    fun historial(): Flow<List<ReportEntity>>

    @Query("SELECT COUNT(*) FROM reportes_pendientes WHERE enviado = 0")
    fun totalPendientes(): Flow<Int>
}
