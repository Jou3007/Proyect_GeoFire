package com.geofire.campo.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.geofire.campo.data.SesionRepositorio
import com.geofire.campo.network.ConfigServidor
import com.geofire.campo.network.LoginRequest
import com.geofire.campo.network.RetrofitClient
import com.geofire.campo.ui.theme.NaranjaAlerta
import com.geofire.campo.ui.theme.TextoSuave
import com.geofire.campo.ui.theme.VerdeGeoFire
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(alIniciarSesion: () -> Unit) {
    val contexto = LocalContext.current
    val alcance = rememberCoroutineScope()
    var correo by remember { mutableStateOf("") }
    var clave by remember { mutableStateOf("") }
    var cargando by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 28.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("GeoFire", style = MaterialTheme.typography.displaySmall, color = VerdeGeoFire, fontWeight = FontWeight.Bold)
        Text("Campo · guardaparques", style = MaterialTheme.typography.titleMedium, color = TextoSuave)
        Spacer(Modifier.height(36.dp))

        OutlinedTextField(
            value = correo,
            onValueChange = { correo = it; error = null },
            label = { Text("Correo institucional") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(14.dp))
        OutlinedTextField(
            value = clave,
            onValueChange = { clave = it; error = null },
            label = { Text("Contraseña") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth(),
        )

        if (error != null) {
            Spacer(Modifier.height(10.dp))
            Text(error ?: "", color = NaranjaAlerta, style = MaterialTheme.typography.bodyMedium)
        }

        Spacer(Modifier.height(24.dp))
        Button(
            onClick = {
                error = null
                cargando = true
                alcance.launch {
                    try {
                        val urlBase = ConfigServidor.refrescar(contexto)
                        val servicio = RetrofitClient.servicio(urlBase)
                        val respuesta = servicio.iniciarSesion(LoginRequest(correo.trim(), clave))
                        val cuerpo = respuesta.body()
                        if (respuesta.isSuccessful && cuerpo?.ok == true) {
                            SesionRepositorio.guardar(contexto, correo.trim(), cuerpo.nombre)
                            alIniciarSesion()
                        } else {
                            error = cuerpo?.mensaje ?: "Correo o contraseña incorrectos."
                        }
                    } catch (excepcion: Exception) {
                        error = "No se pudo conectar con el servidor. Revisa tu conexión e intenta de nuevo."
                    } finally {
                        cargando = false
                    }
                }
            },
            enabled = correo.isNotBlank() && clave.isNotBlank() && !cargando,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            colors = ButtonDefaults.buttonColors(containerColor = VerdeGeoFire),
        ) {
            if (cargando) {
                CircularProgressIndicator(modifier = Modifier.size(22.dp), strokeWidth = 2.dp)
            } else {
                Text("Ingresar", fontWeight = FontWeight.Bold)
            }
        }

        Spacer(Modifier.height(14.dp))
        Text(
            "Acceso exclusivo para personal autorizado de GeoFire.",
            style = MaterialTheme.typography.bodySmall,
            color = TextoSuave,
        )
    }
}
