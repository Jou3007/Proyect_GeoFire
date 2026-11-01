package com.geofire.campo.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import com.geofire.campo.data.models.ReportEntity

@Database(entities = [ReportEntity::class], version = 1, exportSchema = false)
abstract class ReportDatabase : RoomDatabase() {
    abstract fun reportDao(): ReportDao

    companion object {
        @Volatile private var instancia: ReportDatabase? = null

        fun obtener(context: Context): ReportDatabase =
            instancia ?: synchronized(this) {
                instancia ?: Room.databaseBuilder(
                    context.applicationContext,
                    ReportDatabase::class.java,
                    "geofire_campo.db",
                ).build().also { instancia = it }
            }
    }
}
