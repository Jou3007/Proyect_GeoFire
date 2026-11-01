package com.geofire.campo.services

/**
 * SEGUNDA ETAPA (aun no activada en esta version).
 *
 * Aqui iria un Foreground Service que registre la ubicacion cada X minutos
 * mientras dura la jornada, con su notificacion permanente obligatoria por
 * Android y un interruptor "Iniciar jornada" en la app para encenderlo y
 * apagarlo. No se implementa todavia porque:
 *  - necesita el servidor en la nube ya funcionando (no una laptop con ngrok),
 *  - necesita que el guardaparque sepa cuando esta activo (exigencia de Android,
 *    con notificacion visible que no se puede ocultar),
 *  - consume bateria, y eso hay que medirlo en campo antes de activarlo siempre.
 *
 * Por ahora, la posicion del guardaparque se conoce por la ubicacion que viaja
 * con cada foto, audio, video o SOS que envia (ver DashboardScreen).
 */
object LocationTrackingService
