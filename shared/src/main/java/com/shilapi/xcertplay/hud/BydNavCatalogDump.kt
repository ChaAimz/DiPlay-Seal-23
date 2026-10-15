package com.shilapi.xcertplay.hud

import android.content.Context
import android.os.Build
import com.shilapi.xcertplay.adb.AdbKeys
import com.shilapi.xcertplay.adb.LocalAdb

/**
 * Read-only dump of the head unit's own navigation and HUD feature ids (BYDAutoFeatureIds and the
 * device ids in BYDAutoConstants), with the properties and packages that decide which guidance path
 * a car has. It compares a car against the ids other projects write before DiPlay writes any of them:
 * nothing here calls a set method or changes a setting.
 */
object BydNavCatalogDump {
    const val ARG = "--nav-catalog"
    const val HEADER = "DIPLAY_BYD_NAV_CATALOG_V1"

    private const val DEVICE_PREFIX = "BYDAutoConstants.BYDAUTO_DEVICE_"
    private val NAME = Regex("HUD|NAVI|GUIDE|PATHNAME|CROSSING|ARRIVE|TARGET_AHEAD|LEAD_MSG|MILEAGE")
    private val PROPERTIES = listOf(
        "apps.setting.product.inswver",
        "ro.car.protocol",
        "sys.car.protocol",
        "ro.build.system.fission_single_os",
        "ro.product.name",
    )
    private val PACKAGES = Regex("amap|telenav|navi|clusterdebug|someip|carsettings|hud", RegexOption.IGNORE_CASE)

    /** Reflected `Class.FIELD` keys to print: every device id and the navigation/HUD feature ids. */
    fun wanted(key: String): Boolean =
        key.startsWith(DEVICE_PREFIX) || NAME.containsMatchIn(key.substringAfterLast('.'))

    /** Runs the dump over the local adbd; returns the report text, or null when ADB is not ready. */
    fun run(context: Context, mayAsk: Boolean): Pair<BydAdbAccess.State, String?> {
        val app = context.applicationContext
        LocalAdb(AdbKeys.load(app)).use { adb ->
            val access = BydAdbAccess.state(adb.connect(mayAsk))
            if (access != BydAdbAccess.State.READY) return access to null
            val catalog = adb.shell(BydVehicleCapabilityProbe.catalogCommand(app, ARG), 15_000)
            val properties = PROPERTIES.associateWith { adb.shell("getprop $it")?.trim().orEmpty() }
            val packages = adb.shell("pm list packages")
            return access to report(Build.FINGERPRINT, properties, packages, catalog)
        }
    }

    internal fun report(
        fingerprint: String,
        properties: Map<String, String>,
        packages: String?,
        catalog: String?,
    ): String = buildString {
        appendLine("DiPlay BYD navigation/HUD catalog (read-only)")
        appendLine("fingerprint=$fingerprint")
        properties.forEach { (key, value) -> appendLine("$key=${value.ifEmpty { "(empty)" }}") }
        appendLine()
        appendLine("Navigation-related packages:")
        val names = packages.orEmpty().lineSequence().map { it.trim().removePrefix("package:") }
            .filter { it.isNotEmpty() && PACKAGES.containsMatchIn(it) }.sorted().toList()
        if (packages == null) appendLine("(pm list packages failed)")
        else if (names.isEmpty()) appendLine("(none)")
        else names.forEach { appendLine(it) }
        appendLine()
        val lines = catalog.orEmpty().lines().map(String::trim)
        if (catalog == null || HEADER !in lines) {
            appendLine("Feature catalog: unavailable (app_process failed or the firmware has no BYDAutoFeatureIds)")
            catalog?.takeIf { it.isNotBlank() }?.let { appendLine(it.trim().take(2_000)) }
            return@buildString
        }
        val entries = lines.filter { '=' in it && it != HEADER }
        appendLine("Feature catalog: ${entries.size} entries (decimal; hex in brackets)")
        entries.forEach { line ->
            val value = line.substringAfterLast('=').toLongOrNull()
            appendLine(if (value == null) line else line + " [0x" + String.format(java.util.Locale.US, "%08X", value.toInt()) + "]")
        }
    }
}
