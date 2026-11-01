package com.geofire.campo.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import com.geofire.campo.data.models.ReportEntity
import com.geofire.campo.data.models.UbicacionEntity

@Database(entities = [ReportEntity::class, UbicacionEntity::class], version = 2, exportSchema = false)
abstract class ReportDatabase : RoomDatabase() {
    abstract fun reportDao(): ReportDao
    abstract fun ubicacionDao(): UbicacionDao

    companion object {
        @Volatile private var instancia: ReportDatabase? = null

        fun obtener(context: Context): ReportDatabase =
            instancia ?: synchronized(this) {
                instancia ?: Room.databaseBuilder(
                    context.applicationContext,
                    ReportDatabase::class.java,
                    "geofire_campo.db",
                )
                    // es solo una cola local de envio; si cambia el esquema, se empieza de nuevo
                    .fallbackToDestructiveMigration()
                    .build().also { instancia = it }
            }
    }
}
