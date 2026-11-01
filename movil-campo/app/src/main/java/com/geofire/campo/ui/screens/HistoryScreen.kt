package com.geofire.campo.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.geofire.campo.data.local.ReportDatabase
import com.geofire.campo.data.models.ReportEntity
import com.geofire.campo.ui.theme.FondoTarjeta
import com.geofire.campo.ui.theme.TextoSuave
import com.geofire.campo.ui.theme.VerdeGeoFire
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun HistoryScreen(alVolver: () -> Unit) {
    val contexto = LocalContext.current
    val dao = remember { ReportDatabase.obtener(contexto).reportDao() }
    val reportes by dao.historial().collectAsState(initial = emptyList())
    val formato = remember { SimpleDateFormat("dd/MM/yyyy HH:mm", Locale.getDefault()) }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Row {
            IconButton(onClick = alVolver) { Icon(Icons.Default.ArrowBack, contentDescription = "Volver") }
            Spacer(Modifier.width(8.dp))
            Text("Tus reportes", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        }
        Spacer(Modifier.height(10.dp))
        if (reportes.isEmpty()) {
            Text("Todavía no registraste nada en esta jornada.", color = TextoSuave)
        }
        LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(reportes) { reporte -> FilaReporte(reporte, formato) }
        }
    }
}

@Composable
private fun FilaReporte(reporte: ReportEntity, formato: SimpleDateFormat) {
    Card(colors = CardDefaults.cardColors(containerColor = FondoTarjeta), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Row {
                Text(reporte.tipo, fontWeight = FontWeight.Bold, color = VerdeGeoFire)
                Spacer(Modifier.weight(1f))
                Text(
                    if (reporte.enviado) "Enviado" else "Pendiente de señal",
                    color = if (reporte.enviado) VerdeGeoFire else TextoSuave,
                    style = MaterialTheme.typography.labelMedium,
                )
            }
            Text(formato.format(Date(reporte.marcaTiempo)), color = TextoSuave, style = MaterialTheme.typography.bodySmall)
            Text(reporte.nota, style = MaterialTheme.typography.bodyMedium)
            if (reporte.ultimoError != null && !reporte.enviado) {
                Text("Sin señal todavía (${reporte.intentos} intentos)", color = TextoSuave, style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}
