package com.geofire.campo.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val EsquemaGeoFire = darkColorScheme(
    primary = VerdeGeoFire,
    onPrimary = FondoOscuro,
    secondary = NaranjaAlerta,
    error = RojoSos,
    background = FondoOscuro,
    surface = FondoTarjeta,
    onBackground = TextoClaro,
    onSurface = TextoClaro,
    outline = BordeSutil,
)

@Composable
fun GeoFireCampoTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = EsquemaGeoFire,
        content = content,
    )
}
