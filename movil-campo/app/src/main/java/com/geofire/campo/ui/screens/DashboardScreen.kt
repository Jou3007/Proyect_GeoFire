package com.geofire.campo.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import android.media.MediaRecorder
import android.net.Uri
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import com.geofire.campo.data.SesionRepositorio
import com.geofire.campo.data.local.ReportDatabase
import com.geofire.campo.data.models.ReportEntity
import com.geofire.campo.services.LocationTrackingService
import com.geofire.campo.services.intentarEnviarAhora
import com.geofire.campo.ui.theme.*
import com.google.android.gms.location.LocationServices
import kotlinx.coroutines.launch
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun DashboardScreen(alVerHistorial: () -> Unit, alCerrarSesion: () -> Unit) {
    val contexto = LocalContext.current
    val alcance = rememberCoroutineScope()

    var nombre by remember { mutableStateOf("") }
    var correo by remember { mutableStateOf("") }
    var lat by remember { mutableStateOf<Double?>(null) }
    var lon by remember { mutableStateOf<Double?>(null) }
    var mensaje by remember { mutableStateOf<String?>(null) }
    var grabandoAudio by remember { mutableStateOf(false) }
    var grabadorAudio by remember { mutableStateOf<MediaRecorder?>(null) }
    var rutaAudioActual by remember { mutableStateOf<String?>(null) }
    var jornadaActiva by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        correo = SesionRepositorio.correoActual(contexto) ?: ""
        nombre = SesionRepositorio.nombreActual(contexto) ?: correo
        actualizarUbicacion(contexto) { la, lo -> lat = la; lon = lo }
    }

    fun guardarReporte(tipo: String, ruta: String?, nota: String) {
        alcance.launch {
            val dao = ReportDatabase.obtener(contexto).reportDao()
            dao.insertar(
                ReportEntity(
                    tipo = tipo,
                    latitud = lat,
                    longitud = lon,
                    nota = nota,
                    marcaTiempo = System.currentTimeMillis(),
                    rutaArchivo = ruta,
                    correoUsuario = correo,
                ),
            )
            intentarEnviarAhora(contexto) // lo manda ya mismo si hay señal; si no, el respaldo lo hace despues
            mensaje = "Guardado. Se enviará solo o cuando recuperes señal."
        }
    }

    fun nuevoArchivo(extension: String): File {
        val carpeta = File(contexto.getExternalFilesDir(null), "evidencias").apply { mkdirs() }
        val marca = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
        return File(carpeta, "GF_$marca.$extension")
    }

    fun uriPara(archivo: File): Uri =
        FileProvider.getUriForFile(contexto, "com.geofire.campo.fileprovider", archivo)

    var archivoFotoActual by remember { mutableStateOf<File?>(null) }
    val lanzadorFoto = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { tomada ->
        if (tomada && archivoFotoActual != null) {
            guardarReporte("FOTO", archivoFotoActual!!.absolutePath, "Evidencia fotográfica de campo")
        }
    }

    var archivoVideoActual by remember { mutableStateOf<File?>(null) }
    val lanzadorVideo = rememberLauncherForActivityResult(ActivityResultContracts.CaptureVideo()) { tomado ->
        if (tomado && archivoVideoActual != null) {
            guardarReporte("VIDEO", archivoVideoActual!!.absolutePath, "Video de evidencia de campo")
        }
    }

    val permisos = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {}
    val permisoUbicacionFondo = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}

    fun alternarJornada() {
        if (!jornadaActiva) {
            val tieneUbicacion = ContextCompat.checkSelfPermission(contexto, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
            if (!tieneUbicacion) {
                permisos.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.POST_NOTIFICATIONS))
                mensaje = "Dale permiso de ubicación y pulsa de nuevo Iniciar jornada."
                return
            }
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
                permisoUbicacionFondo.launch(Manifest.permission.ACCESS_BACKGROUND_LOCATION)
            }
            LocationTrackingService.iniciar(contexto, correo)
            jornadaActiva = true
            mensaje = "Jornada iniciada: tu ubicación se registra cada 2 minutos."
        } else {
            LocationTrackingService.detener(contexto)
            jornadaActiva = false
            mensaje = "Jornada detenida."
        }
    }

    Column(Modifier.fillMaxSize().padding(20.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.weight(1f)) {
                Text("Hola, $nombre", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text("Jornada de campo", color = TextoSuave, style = MaterialTheme.typography.bodyMedium)
            }
            IconButton(onClick = alVerHistorial) { Icon(Icons.Default.History, contentDescription = "Historial", tint = TextoClaro) }
            IconButton(onClick = { alcance.launch { SesionRepositorio.cerrarSesion(contexto); alCerrarSesion() } }) {
                Icon(Icons.Default.Logout, contentDescription = "Salir", tint = TextoClaro)
            }
        }

        Spacer(Modifier.height(18.dp))
        Card(colors = CardDefaults.cardColors(containerColor = FondoTarjeta), modifier = Modifier.fillMaxWidth()) {
            Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.GpsFixed, contentDescription = null, tint = VerdeGeoFire)
                Spacer(Modifier.width(10.dp))
                Column {
                    Text("Ubicación GPS", color = TextoSuave, style = MaterialTheme.typography.labelMedium)
                    Text(
                        if (lat != null) "%.5f, %.5f".format(lat, lon) else "Buscando señal satelital…",
                        color = TextoClaro,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
        }

        Spacer(Modifier.height(10.dp))
        Card(colors = CardDefaults.cardColors(containerColor = FondoTarjeta), modifier = Modifier.fillMaxWidth()) {
            Row(
                Modifier.padding(16.dp).fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("Jornada de campo", color = TextoSuave, style = MaterialTheme.typography.labelMedium)
                    Text(
                        if (jornadaActiva) "Rastreando tu ubicación" else "Rastreo apagado",
                        color = if (jornadaActiva) VerdeGeoFire else TextoClaro,
                        fontWeight = FontWeight.Bold,
                    )
                }
                Switch(
                    checked = jornadaActiva,
                    onCheckedChange = { alternarJornada() },
                    colors = SwitchDefaults.colors(checkedTrackColor = VerdeGeoFire),
                )
            }
        }

        if (mensaje != null) {
            Spacer(Modifier.height(10.dp))
            Text(mensaje ?: "", color = VerdeGeoFire, style = MaterialTheme.typography.bodyMedium)
        }

        Spacer(Modifier.height(22.dp))
        Text("Registrar evidencia", color = TextoSuave, style = MaterialTheme.typography.labelLarge)
        Spacer(Modifier.height(10.dp))

        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            BotonAccion(
                icono = Icons.Default.PhotoCamera,
                etiqueta = "Foto",
                modifier = Modifier.weight(1f),
            ) {
                permisos.launch(arrayOf(Manifest.permission.CAMERA, Manifest.permission.ACCESS_FINE_LOCATION))
                val archivo = nuevoArchivo("jpg")
                archivoFotoActual = archivo
                lanzadorFoto.launch(uriPara(archivo))
            }
            BotonAccion(
                icono = Icons.Default.Videocam,
                etiqueta = "Video",
                modifier = Modifier.weight(1f),
            ) {
                permisos.launch(arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO))
                val archivo = nuevoArchivo("mp4")
                archivoVideoActual = archivo
                lanzadorVideo.launch(uriPara(archivo))
            }
        }

        Spacer(Modifier.height(12.dp))
        BotonAccion(
            icono = if (grabandoAudio) Icons.Default.Stop else Icons.Default.Mic,
            etiqueta = if (grabandoAudio) "Detener grabación" else "Registrar incidente en audio",
            modifier = Modifier.fillMaxWidth(),
            destacado = grabandoAudio,
        ) {
            if (!grabandoAudio) {
                permisos.launch(arrayOf(Manifest.permission.RECORD_AUDIO))
                val archivo = nuevoArchivo("m4a")
                rutaAudioActual = archivo.absolutePath
                val tienePermiso = ContextCompat.checkSelfPermission(contexto, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
                if (tienePermiso) {
                    val grabador = MediaRecorder()
                    grabador.setAudioSource(MediaRecorder.AudioSource.MIC)
                    grabador.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                    grabador.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
                    grabador.setOutputFile(archivo.absolutePath)
                    grabador.prepare()
                    grabador.start()
                    grabadorAudio = grabador
                    grabandoAudio = true
                }
            } else {
                grabadorAudio?.apply { stop(); release() }
                grabadorAudio = null
                grabandoAudio = false
                guardarReporte("AUDIO", rutaAudioActual, "Audio de incidente registrado en campo")
            }
        }

        Spacer(Modifier.weight(1f))

        Button(
            onClick = {
                guardarReporte("SOS", null, "SOS: emergencia reportada por el guardaparque")
            },
            modifier = Modifier
                .fillMaxWidth()
                .height(76.dp),
            shape = RoundedCornerShape(18.dp),
            colors = ButtonDefaults.buttonColors(containerColor = RojoSos),
        ) {
            Icon(Icons.Default.Warning, contentDescription = null, tint = Color.White)
            Spacer(Modifier.width(10.dp))
            Text("SOS / REPORTAR EMERGENCIA", color = Color.White, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
        }
    }
}

@Composable
private fun BotonAccion(
    icono: androidx.compose.ui.graphics.vector.ImageVector,
    etiqueta: String,
    modifier: Modifier = Modifier,
    destacado: Boolean = false,
    onClick: () -> Unit,
) {
    OutlinedButton(
        onClick = onClick,
        modifier = modifier.height(64.dp),
        shape = RoundedCornerShape(14.dp),
        colors = ButtonDefaults.outlinedButtonColors(
            containerColor = if (destacado) NaranjaAlerta.copy(alpha = 0.18f) else FondoTarjeta,
            contentColor = if (destacado) NaranjaAlerta else TextoClaro,
        ),
    ) {
        Icon(icono, contentDescription = null)
        Spacer(Modifier.width(8.dp))
        Text(etiqueta, fontWeight = FontWeight.Medium)
    }
}

private fun actualizarUbicacion(contexto: android.content.Context, aplicar: (Double, Double) -> Unit) {
    val tienePermiso = ContextCompat.checkSelfPermission(contexto, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
    if (!tienePermiso) return
    val cliente = LocationServices.getFusedLocationProviderClient(contexto)
    cliente.lastLocation.addOnSuccessListener { ubicacion ->
        if (ubicacion != null) aplicar(ubicacion.latitude, ubicacion.longitude)
    }
}
