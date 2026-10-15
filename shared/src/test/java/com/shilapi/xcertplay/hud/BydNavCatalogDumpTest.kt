package com.shilapi.xcertplay.hud

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BydNavCatalogDumpTest {
    @Test fun keepsDeviceIdsAndNavigationAndHudFeatures() {
        assertTrue(BydNavCatalogDump.wanted("BYDAutoConstants.BYDAUTO_DEVICE_SETTING"))
        assertTrue(BydNavCatalogDump.wanted("Instrument.INSTRUMENT_SEND_NAVI_STATUS_SET"))
        assertTrue(BydNavCatalogDump.wanted("Instrument.INSTRUMENT_GUIDE_INFO_SIMPLE_SET"))
        assertTrue(BydNavCatalogDump.wanted("Instrument.INSTRUMENT_TARGET_NEXT_PATHNAME_INFO_SET"))
        assertTrue(BydNavCatalogDump.wanted("Setting.SET_HUD_SWITCH_SET"))
        assertFalse(BydNavCatalogDump.wanted("Statistic.STATISTIC_ELEC_PERCENTAGE"))
        assertFalse(BydNavCatalogDump.wanted("BYDAutoConstants.SOMETHING_ELSE"))
    }

    @Test fun reportListsPropertiesNavigationPackagesAndHexIds() {
        val report = BydNavCatalogDump.report(
            fingerprint = "BYD-AUTO/DiLink3.0/test",
            properties = linkedMapOf("apps.setting.product.inswver" to "SX326", "ro.car.protocol" to ""),
            packages = "package:com.example.amapservice\npackage:com.android.settings\npackage:com.byd.clusterdebug\n",
            catalog = "${BydNavCatalogDump.HEADER}\nSetting.SET_HUD_SWITCH_SET=1276174371\n" +
                "BYDAutoConstants.BYDAUTO_DEVICE_SETTING=1023\n",
        )

        assertTrue("apps.setting.product.inswver=SX326" in report)
        assertTrue("ro.car.protocol=(empty)" in report)
        assertTrue("com.example.amapservice" in report)
        assertTrue("com.byd.clusterdebug" in report)
        assertFalse("com.android.settings" in report)
        assertTrue("Feature catalog: 2 entries" in report)
        assertTrue("Setting.SET_HUD_SWITCH_SET=1276174371 [0x4C10E023]" in report)
        assertTrue("BYDAutoConstants.BYDAUTO_DEVICE_SETTING=1023 [0x000003FF]" in report)
    }

    @Test fun reportSaysWhenTheCatalogIsMissing() {
        val report = BydNavCatalogDump.report("fp", emptyMap(), null, "Error: no class")
        assertTrue("(pm list packages failed)" in report)
        assertTrue("Feature catalog: unavailable" in report)
        assertTrue("Error: no class" in report)
    }
}
