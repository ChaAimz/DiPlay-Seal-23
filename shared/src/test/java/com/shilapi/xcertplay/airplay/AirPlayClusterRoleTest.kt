package com.shilapi.xcertplay.airplay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class AirPlayClusterRoleTest {
    @Test
    fun sealClusterIsAdvertisedAsInstrumentDisplayOnly() {
        val info = AirPlayInfoPlist.build(
            AirPlayConfig(
                deviceName = "test",
                deviceId = "02:00:00:00:00:02",
                btMac = "02:00:00:00:00:02",
                sourceVersion = "366.0",
                main = AirPlayDisplayConfig(widthPixels = 1920, heightPixels = 1080),
                cluster = CarPlayClusterDisplay.config(widthPixels = 1920, heightPixels = 720),
            ),
        )

        val displays = (info["displays"] as List<*>).map { it as Map<*, *> }
        val main = displays.single { it["uuid"] == AirPlayInfoPlist.MAIN_UUID }
        val cluster = displays.single { it["uuid"] == AirPlayInfoPlist.ALT_UUID }

        assertFalse(main.containsKey("showsInstruments"))
        assertEquals(true, cluster["showsInstruments"])
        assertEquals(111, cluster["type"])
        assertEquals(CarPlayClusterDisplay.MAP_URL, cluster["initialURL"])
    }

    @Test
    fun ordinaryAuxiliaryDisplayDoesNotBecomeInstrumentClusterImplicitly() {
        val info = AirPlayInfoPlist.build(
            AirPlayConfig(
                deviceName = "test",
                deviceId = "02:00:00:00:00:02",
                btMac = "02:00:00:00:00:02",
                sourceVersion = "366.0",
                main = AirPlayDisplayConfig(widthPixels = 1280, heightPixels = 720),
                cluster = AirPlayDisplayConfig(
                    widthPixels = 960,
                    heightPixels = 360,
                    initialUrl = CarPlayClusterDisplay.MAP_URL,
                ),
            ),
        )

        val cluster = (info["displays"] as List<*>)
            .map { it as Map<*, *> }
            .single { it["uuid"] == AirPlayInfoPlist.ALT_UUID }

        assertFalse(cluster.containsKey("showsInstruments"))
    }
}
