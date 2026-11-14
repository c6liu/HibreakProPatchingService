package com.lmqr.ha9_comp_service

import android.content.Context
import android.database.ContentObserver
import android.hardware.display.DisplayManager
import android.net.Uri
import android.os.Handler
import android.os.IBinder
import android.os.ParcelFileDescriptor
import android.provider.Settings
import android.util.Log
import android.view.Display
import android.widget.Toast
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.roundToInt

/** Android's effective display brightness (0..1, linear backlight space). */
interface NativeBrightnessSource {
    /** Last known brightness. */
    val brightness: Float

    /** Starts tracking; [onChange] runs on the main thread after [brightness] changes. */
    fun start(onChange: () -> Unit)
    fun refresh()
    fun stop()
    /** Saves Android brightness without changing its automatic/manual mode. */
    fun setBrightness(value: Float): Boolean
}

/**
 * Follows the brightness Android's display power controller sends to the backlight:
 * the system slider, automatic brightness and per-window overrides.
 *
 * The value is read from the hidden `Display.getBrightnessInfo()` when the app may call it
 * (it needs the signature-only CONTROL_DISPLAY_BRIGHTNESS), otherwise from the display
 * service dump (needs DUMP, granted to the privileged app). Changes are signalled by the
 * hidden brightness-only display event. If neither read works, the slider setting is used.
 */
class DisplayBrightnessSource(
    private val context: Context,
    private val handler: Handler,
) : NativeBrightnessSource {
    companion object {
        private const val TAG = "DisplayBrightness"

        // DisplayManager.PRIVATE_EVENT_TYPE_DISPLAY_BRIGHTNESS
        private const val PRIVATE_EVENT_BRIGHTNESS = 1L shl 0

        private const val ADJUSTED_PREFIX = "mCachedBrightnessInfo.adjustedBrightness="
        private const val DISPLAY_ID_PREFIX = "mDisplayId="

        /**
         * Extracts the default display's adjusted brightness from `dumpsys display` output.
         * Each display power controller prints its id before its cached brightness info.
         */
        fun parseAdjustedBrightness(lines: Sequence<String>): Float? {
            var defaultDisplay = false
            for (raw in lines) {
                val line = raw.trim()
                if (line.startsWith(DISPLAY_ID_PREFIX)) {
                    defaultDisplay = line.removePrefix(DISPLAY_ID_PREFIX) == "0"
                } else if (defaultDisplay && line.startsWith(ADJUSTED_PREFIX)) {
                    return line.removePrefix(ADJUSTED_PREFIX).toFloatOrNull()
                        ?.takeUnless { it.isNaN() }
                        ?.coerceIn(0f, 1f)
                }
            }
            return null
        }
    }

    private val displayManager = context.getSystemService(DisplayManager::class.java)
    private val executor: ExecutorService = Executors.newSingleThreadExecutor()
    private val refreshQueued = AtomicBoolean(false)
    private var onChange: (() -> Unit)? = null
    private var listenerRegistered = false
    private var brightnessInfoAllowed = true
    private var dumpAllowed = true
    private var writeGeneration = 0

    @Volatile
    override var brightness: Float = readSetting()
        private set

    private val displayListener = object : DisplayManager.DisplayListener {
        override fun onDisplayAdded(displayId: Int) {}
        override fun onDisplayRemoved(displayId: Int) {}
        override fun onDisplayChanged(displayId: Int) {
            if (displayId == Display.DEFAULT_DISPLAY) refresh()
        }
    }

    private val settingsObserver = object : ContentObserver(handler) {
        override fun onChange(selfChange: Boolean, uri: Uri?) {
            // Our setting write is already applied locally; the display cache may still be old.
            if (uri == Settings.System.getUriFor(Settings.System.SCREEN_BRIGHTNESS) &&
                readSetting() == brightness) return
            refresh()
        }
    }

    override fun start(onChange: () -> Unit) {
        stop()
        this.onChange = onChange
        listenerRegistered = registerBrightnessListener()
        val resolver = context.contentResolver
        for (name in listOf(Settings.System.SCREEN_BRIGHTNESS, Settings.System.SCREEN_BRIGHTNESS_MODE)) {
            resolver.registerContentObserver(Settings.System.getUriFor(name), false, settingsObserver)
        }
        refresh()
    }

    override fun refresh() {
        // Coalesce bursts of events into one read.
        if (!refreshQueued.compareAndSet(false, true)) return
        val generation = writeGeneration
        executor.execute {
            refreshQueued.set(false)
            val value = readBrightnessInfo() ?: readDump() ?: readSetting()
            handler.post {
                if (generation != writeGeneration) return@post
                if (value != brightness) {
                    brightness = value
                    onChange?.invoke()
                }
            }
        }
    }

    override fun setBrightness(value: Float): Boolean {
        val bounded = value.coerceIn(0f, 1f)
        // Android's BrightnessSynchronizer maps setting 1..255 to linear brightness 0..1.
        val setting = (bounded * 254f).roundToInt() + 1
        try {
            check(Settings.System.putInt(context.contentResolver, Settings.System.SCREEN_BRIGHTNESS, setting)) {
                "Android rejected the brightness setting"
            }
        } catch (e: SecurityException) {
            Log.e(TAG, "Cannot write Android brightness", e)
            Toast.makeText(context, R.string.frontlight_brightness_write_failed, Toast.LENGTH_LONG).show()
            return false
        } catch (e: IllegalStateException) {
            Log.e(TAG, "Cannot save Android brightness", e)
            Toast.makeText(context, R.string.frontlight_brightness_write_failed, Toast.LENGTH_LONG).show()
            return false
        }
        writeGeneration++
        brightness = (setting - 1) / 254f
        onChange?.invoke()
        return true
    }

    override fun stop() {
        if (listenerRegistered) {
            displayManager?.unregisterDisplayListener(displayListener)
            listenerRegistered = false
        }
        context.contentResolver.unregisterContentObserver(settingsObserver)
        onChange = null
    }

    private fun readBrightnessInfo(): Float? {
        if (!brightnessInfoAllowed) return null
        return try {
            val display = displayManager?.getDisplay(Display.DEFAULT_DISPLAY) ?: return null
            val info = Display::class.java.getMethod("getBrightnessInfo").invoke(display)
                ?: return null
            // `brightness` is only the slider setting; adjustedBrightness also reflects
            // auto-brightness and window overrides.
            val value = info.javaClass.getField("adjustedBrightness").getFloat(info)
            if (value.isNaN()) null else value.coerceIn(0f, 1f)
        } catch (e: Exception) {
            // Usually a wrapped SecurityException, which will not change at runtime.
            brightnessInfoAllowed = false
            Log.i(TAG, "BrightnessInfo unavailable; using display dump", e)
            null
        }
    }

    private fun readDump(): Float? {
        if (!dumpAllowed) return null
        return try {
            val binder = Class.forName("android.os.ServiceManager")
                .getMethod("getService", String::class.java)
                .invoke(null, Context.DISPLAY_SERVICE) as? IBinder ?: return null
            val pipe = ParcelFileDescriptor.createPipe()
            ParcelFileDescriptor.AutoCloseInputStream(pipe[0]).bufferedReader().use { reader ->
                // Async dump so the service can write more than a pipe buffer while we read.
                pipe[1].use { binder.dumpAsync(it.fileDescriptor, emptyArray()) }
                parseAdjustedBrightness(reader.lineSequence())
            }
        } catch (e: Exception) {
            dumpAllowed = false
            Log.w(TAG, "Display dump unavailable; using slider setting", e)
            null
        }
    }

    private fun readSetting(): Float {
        val resolver = context.contentResolver
        val value = Settings.System.getInt(resolver, Settings.System.SCREEN_BRIGHTNESS, 128)
        return ((value - 1) / 254f).coerceIn(0f, 1f)
    }

    private fun registerBrightnessListener(): Boolean {
        val manager = displayManager ?: return false
        val longType = Long::class.javaPrimitiveType
        return try {
            DisplayManager::class.java.getMethod("registerDisplayListener",
                DisplayManager.DisplayListener::class.java, Handler::class.java,
                longType, longType)
                .invoke(manager, displayListener, handler, 0L, PRIVATE_EVENT_BRIGHTNESS)
            true
        } catch (e: Exception) {
            Log.w(TAG, "Brightness events unavailable", e)
            false
        }
    }
}
