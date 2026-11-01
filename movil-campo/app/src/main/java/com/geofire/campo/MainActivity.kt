package com.geofire.campo

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.geofire.campo.data.SesionRepositorio
import com.geofire.campo.ui.screens.DashboardScreen
import com.geofire.campo.ui.screens.HistoryScreen
import com.geofire.campo.ui.screens.LoginScreen
import com.geofire.campo.ui.theme.FondoOscuro
import com.geofire.campo.ui.theme.GeoFireCampoTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            GeoFireCampoTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = FondoOscuro) {
                    AppNavegacion()
                }
            }
        }
    }
}

@Composable
private fun AppNavegacion() {
    val controlador = rememberNavController()
    val contexto = LocalContext.current
    var hayCorreo by remember { mutableStateOf<Boolean?>(null) }

    LaunchedEffect(Unit) {
        hayCorreo = SesionRepositorio.correoActual(contexto) != null
    }

    if (hayCorreo == null) return // pantalla en blanco un instante mientras lee la sesion guardada

    NavHost(navController = controlador, startDestination = if (hayCorreo == true) "panel" else "ingreso") {
        composable("ingreso") {
            LoginScreen(alIniciarSesion = {
                controlador.navigate("panel") { popUpTo("ingreso") { inclusive = true } }
            })
        }
        composable("panel") {
            DashboardScreen(
                alVerHistorial = { controlador.navigate("historial") },
                alCerrarSesion = { controlador.navigate("ingreso") { popUpTo(0) } },
            )
        }
        composable("historial") {
            HistoryScreen(alVolver = { controlador.popBackStack() })
        }
    }
}
