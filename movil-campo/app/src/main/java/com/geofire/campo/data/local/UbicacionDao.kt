package com.geofire.campo.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import androidx.room.Update
import com.geofire.campo.data.models.UbicacionEntity

@Dao
interface UbicacionDao {
    @Insert
    suspend fun insertar(ubicacion: UbicacionEntity): Long

    @Update
    suspend fun actualizar(ubicacion: UbicacionEntity)

    @Query("SELECT * FROM ubicaciones_pendientes WHERE enviado = 0 ORDER BY marcaTiempo ASC LIMIT 50")
    suspend fun pendientes(): List<UbicacionEntity>
}
