package com.lmqr.ha9_comp_service

import android.content.SharedPreferences
import android.view.HapticFeedbackConstants
import android.view.View
import android.widget.SeekBar
import com.lmqr.ha9_comp_service.command_runners.CommandRunner
import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * Manages frontlight settings and their persistence.
 *
 * In the default mode the popup sets the cold and warm channels independently. In native
 * mode Android's effective brightness sets the combined output and the popup only sets the
 * warm/cool mix (see [FrontlightMixer]). Only the active mode writes to the frontlights.
 */
class BrightnessManager(
    private val sharedPreferences: SharedPreferences,
    private val commandRunner: CommandRunner,
    private val nativeBrightness: NativeBrightnessSource,
) {
    companion object {
        const val PREF_NATIVE_MODE = "frontlight_native_brightness"
        private const val PREF_COLD_BRIGHTNESS = "cold_brightness_value"
        private const val PREF_WARM_BRIGHTNESS = "warm_brightness_value"
        private const val PREF_TEMPERATURE = "frontlight_temperature"
        private const val MAX_BRIGHTNESS = 255
        const val TEMPERATURE_STEPS = 1000
        private val DEFAULT_TEMPERATURE = FrontlightMixer.NEUTRAL_TEMPERATURE.toFloat()
        /** Drags within this many steps of neutral white snap to it. */
        private const val NEUTRAL_SNAP_STEPS = 30
        val NEUTRAL_PROGRESS = (FrontlightMixer.NEUTRAL_TEMPERATURE * TEMPERATURE_STEPS).roundToInt()

        fun snapToNeutral(progress: Int): Int =
            if (abs(progress - NEUTRAL_PROGRESS) <= NEUTRAL_SNAP_STEPS) NEUTRAL_PROGRESS else progress
    }

    private var screenOn = true
    private var nativeActive = false
    private var lastCodes: FrontlightMixer.Codes? = null
    // Position of an in-progress temperature drag; saved to preferences on release.
    private var draggingTemperature: Double? = null
    private var draggingProgress: Int? = null

    private val activeTemperature: Double
        get() = draggingTemperature ?: temperature.toDouble()

    val isNativeMode: Boolean
        get() = sharedPreferences.getBoolean(PREF_NATIVE_MODE, true)

    /** Warm/cool position for native mode: 0 = cool, 1 = warm. */
    var temperature: Float
        get() = sharedPreferences.getFloat(PREF_TEMPERATURE, DEFAULT_TEMPERATURE).coerceIn(0f, 1f)
        set(value) {
            sharedPreferences.edit().putFloat(PREF_TEMPERATURE, value.coerceIn(0f, 1f)).apply()
        }

    var coldBrightness: Int
        get() = sharedPreferences.getInt(PREF_COLD_BRIGHTNESS, 64)
        set(value) {
            sharedPreferences.edit().putInt(PREF_COLD_BRIGHTNESS, value).apply()
        }

    var warmBrightness: Int
        get() = sharedPreferences.getInt(PREF_WARM_BRIGHTNESS, 64)
        set(value) {
            sharedPreferences.edit().putInt(PREF_WARM_BRIGHTNESS, value).apply()
        }

    /**
     * Apply current brightness settings to the device
     */
    fun applyBrightness() {
        updateNativeSource()
        if (!screenOn) return
        if (isNativeMode) {
            applyNative(activeTemperature)
        } else {
            lastCodes = null
            commandRunner.runCommands(arrayOf("br_co${coldBrightness}", "br_wm${warmBrightness}"))
        }
    }

    fun onScreenStateChanged(on: Boolean) {
        screenOn = on
        if (on) {
            applyBrightness()
            if (nativeActive) nativeBrightness.refresh()
        } else {
            turnOffBrightness()
        }
    }

    /** Called when the control mode preference changes. */
    fun onModeChanged() {
        applyBrightness()
    }

    fun release() {
        if (nativeActive) nativeBrightness.stop()
        nativeActive = false
    }

    private fun updateNativeSource() {
        val wanted = isNativeMode
        if (wanted == nativeActive) return
        nativeActive = wanted
        if (wanted) {
            nativeBrightness.start {
                if (screenOn && isNativeMode) applyNative(activeTemperature)
            }
        } else {
            nativeBrightness.stop()
        }
    }

    private fun applyNative(temperature: Double) {
        val codes = FrontlightMixer.mix(nativeBrightness.brightness.toDouble(), temperature)
        if (codes == lastCodes) return
        lastCodes = codes
        commandRunner.runCommands(arrayOf("br_co${codes.cool}", "br_wm${codes.warm}"))
    }

    /**
     * Update both brightness values and apply them
     */
    fun setBrightness(coldValue: Int, warmValue: Int) {
        coldBrightness = coldValue
        warmBrightness = warmValue
        applyBrightness()
    }

    /**
     * Turn off both backlights
     */
    fun turnOffBrightness() {
        lastCodes = null
        commandRunner.runCommands(arrayOf("br_co0", "br_wm0"))
    }

    /**
     * Show the controls for the active mode and refresh their positions.
     */
    fun updateOverlay(
        lightSeekbar: SeekBar,
        lightWarmSeekbar: SeekBar,
        temperatureSeekbar: SeekBar,
        independentControls: List<View>,
        nativeControls: List<View>,
    ) {
        val native = isNativeMode
        independentControls.forEach { it.visibility = if (native) View.GONE else View.VISIBLE }
        nativeControls.forEach { it.visibility = if (native) View.VISIBLE else View.GONE }
        lightSeekbar.progress = coldBrightness
        lightWarmSeekbar.progress = warmBrightness
        temperatureSeekbar.progress = (temperature * TEMPERATURE_STEPS).roundToInt()
    }

    /**
     * Configure seekbars with current brightness values and listeners
     */
    fun setupSeekBars(lightSeekbar: SeekBar, lightWarmSeekbar: SeekBar, temperatureSeekbar: SeekBar) {
        temperatureSeekbar.min = 0
        temperatureSeekbar.max = TEMPERATURE_STEPS
        temperatureSeekbar.progress = (temperature * TEMPERATURE_STEPS).roundToInt()
        temperatureSeekbar.setOnSeekBarChangeListener(
            object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                    if (!fromUser) return
                    val snapped = snapToNeutral(progress)
                    if (snapped != progress) seekBar?.progress = snapped
                    if (snapped == NEUTRAL_PROGRESS && draggingProgress != NEUTRAL_PROGRESS) {
                        seekBar?.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK)
                    }
                    draggingProgress = snapped
                    draggingTemperature = FrontlightMixer.temperatureForProgress(snapped, TEMPERATURE_STEPS)
                    if (screenOn && isNativeMode) applyNative(activeTemperature)
                }

                override fun onStartTrackingTouch(seekBar: SeekBar?) {
                    draggingProgress = seekBar?.progress
                }

                override fun onStopTrackingTouch(seekBar: SeekBar?) {
                    temperature = (seekBar?.progress ?: 0).toFloat() / TEMPERATURE_STEPS
                    draggingTemperature = null
                    draggingProgress = null
                    if (screenOn && isNativeMode) applyNative(activeTemperature)
                }
            }
        )

        lightSeekbar.min = 0
        lightSeekbar.max = MAX_BRIGHTNESS
        lightSeekbar.progress = coldBrightness
        lightSeekbar.setOnSeekBarChangeListener(
            object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                    if (fromUser && !isNativeMode) {
                        commandRunner.runCommands(arrayOf("br_co${progress}"))
                    }
                }
                
                override fun onStartTrackingTouch(seekBar: SeekBar?) {}
                
                override fun onStopTrackingTouch(seekBar: SeekBar?) {
                    coldBrightness = seekBar?.progress ?: 0
                }
            }
        )

        lightWarmSeekbar.min = 0
        lightWarmSeekbar.max = MAX_BRIGHTNESS
        lightWarmSeekbar.progress = warmBrightness
        lightWarmSeekbar.setOnSeekBarChangeListener(
            object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                    if (fromUser && !isNativeMode) {
                        commandRunner.runCommands(arrayOf("br_wm${progress}"))
                    }
                }
                
                override fun onStartTrackingTouch(seekBar: SeekBar?) {}
                
                override fun onStopTrackingTouch(seekBar: SeekBar?) {
                    warmBrightness = seekBar?.progress ?: 0
                }
            }
        )
    }
}