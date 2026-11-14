package com.lmqr.eink_settings

import android.content.SharedPreferences
import android.view.HapticFeedbackConstants
import android.view.View
import com.google.android.material.slider.Slider
import com.lmqr.eink_settings.command_runners.CommandRunner
import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * Manages frontlight settings and their persistence.
 *
 * Independent mode sets each channel; native mode follows Android brightness and offers
 * live combined-brightness and temperature controls. Only the active mode writes the lights.
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
        const val TEMPERATURE_STEPS = 1000
        private val DEFAULT_TEMPERATURE = FrontlightMixer.NEUTRAL_TEMPERATURE.toFloat()
        /** Drags within this many steps of neutral white snap to it. */
        private const val NEUTRAL_SNAP_STEPS = 30
        val NEUTRAL_PROGRESS = (FrontlightMixer.NEUTRAL_TEMPERATURE * TEMPERATURE_STEPS).roundToInt()

        /** Android brightness requested by a native overlay slider value. */
        fun brightnessForValue(value: Float): Float =
            FrontlightMixer.androidBrightnessForOutput(
                FrontlightMixer.outputForSlider(value / TEMPERATURE_STEPS.toDouble())).toFloat()

        fun sliderValueForBrightness(brightness: Float): Float =
            (FrontlightMixer.sliderForOutput(FrontlightMixer.outputForAndroidBrightness(brightness.toDouble())) *
                TEMPERATURE_STEPS).toFloat()

        fun snapToNeutral(progress: Int): Int =
            if (abs(progress - NEUTRAL_PROGRESS) <= NEUTRAL_SNAP_STEPS) NEUTRAL_PROGRESS else progress
    }

    private var screenOn = true
    private var nativeActive = false
    private var lastCodes: FrontlightMixer.Codes? = null
    private var draggingProgress: Int? = null
    // Display events may lag behind a drag; they must not replace its live brightness.
    private var draggingBrightness: Float? = null
    private var brightnessSlider: Slider? = null

    private val activeTemperature: Double
        get() = temperature.toDouble()

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
            reapplyBrightness()
        } else {
            turnOffBrightness()
        }
    }

    /** Boot/display initialization can overwrite the physical lights without changing Android brightness. */
    fun reapplyBrightness() {
        lastCodes = null
        applyBrightness()
        if (nativeActive) nativeBrightness.refresh()
    }

    /** Called when the control mode preference changes. */
    fun onModeChanged() {
        draggingBrightness = null
        applyBrightness()
    }

    fun release() {
        if (nativeActive) nativeBrightness.stop()
        nativeActive = false
        brightnessSlider = null
    }

    private fun updateNativeSource() {
        val wanted = isNativeMode
        if (wanted == nativeActive) return
        nativeActive = wanted
        if (wanted) {
            nativeBrightness.start {
                if (isNativeMode) {
                    if (draggingBrightness == null) updateBrightnessSlider()
                    if (screenOn) applyNative(activeTemperature)
                }
            }
        } else {
            nativeBrightness.stop()
        }
    }

    private fun applyNative(temperature: Double) {
        val codes = FrontlightMixer.mix(
            (draggingBrightness ?: nativeBrightness.brightness).toDouble(), temperature)
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
    fun updateOverlay(menu: FloatingMenuViewAccessor) {
        val native = isNativeMode
        menu.independentLightControls.forEach { it.visibility = if (native) View.GONE else View.VISIBLE }
        menu.nativeLightControls.forEach { it.visibility = if (native) View.VISIBLE else View.GONE }
        menu.lightSeekbar.value = lightnessForCode(coldBrightness)
        menu.lightWarmSeekbar.value = lightnessForCode(warmBrightness)
        menu.lightTemperatureSeekbar.value = temperature * TEMPERATURE_STEPS
        updateBrightnessSlider()
    }

    private fun lightnessForCode(code: Int): Float =
        (FrontlightMixer.sliderForOutput(FrontlightMixer.outputForCode(code)) * TEMPERATURE_STEPS).toFloat()

    private fun updateBrightnessSlider() {
        brightnessSlider?.value = sliderValueForBrightness(nativeBrightness.brightness)
    }

    private fun codeForValue(value: Float): Int =
        FrontlightMixer.codeForOutput(FrontlightMixer.outputForSlider(value / TEMPERATURE_STEPS.toDouble()))

    fun setupSliders(menu: FloatingMenuViewAccessor) {
        brightnessSlider = menu.lightBrightnessSeekbar
        val sliders = listOf(menu.lightSeekbar, menu.lightWarmSeekbar,
            menu.lightTemperatureSeekbar, menu.lightBrightnessSeekbar)
        sliders.forEach {
            it.valueFrom = 0f
            it.valueTo = TEMPERATURE_STEPS.toFloat()
            it.setLabelFormatter { value -> "${(value / 10).roundToInt()}%" }
        }
        updateOverlay(menu)
        menu.lightTemperatureSeekbar.addOnChangeListener { slider, value, fromUser ->
            if (fromUser && isNativeMode) {
                val snapped = snapToNeutral(value.roundToInt())
                if (snapped == NEUTRAL_PROGRESS && draggingProgress != NEUTRAL_PROGRESS) {
                    slider.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK)
                }
                draggingProgress = snapped
                slider.value = snapped.toFloat()
                temperature = snapped.toFloat() / TEMPERATURE_STEPS
                if (screenOn) applyNative(activeTemperature)
            }
        }
        menu.lightTemperatureSeekbar.addOnSliderTouchListener(object : Slider.OnSliderTouchListener {
            override fun onStartTrackingTouch(slider: Slider) {
                draggingProgress = slider.value.roundToInt()
            }
            override fun onStopTrackingTouch(slider: Slider) {
                draggingProgress = null
            }
        })
        menu.lightBrightnessSeekbar.addOnChangeListener { _, value, fromUser ->
            if (fromUser && isNativeMode) {
                val brightness = brightnessForValue(value)
                val tracking = draggingBrightness != null
                draggingBrightness = brightness
                if (nativeBrightness.setBrightness(brightness)) {
                    if (screenOn) applyNative(activeTemperature)
                } else {
                    draggingBrightness = null
                    updateBrightnessSlider()
                }
                if (!tracking) draggingBrightness = null
            }
        }
        menu.lightBrightnessSeekbar.addOnSliderTouchListener(object : Slider.OnSliderTouchListener {
            override fun onStartTrackingTouch(slider: Slider) {
                draggingBrightness = brightnessForValue(slider.value)
            }
            override fun onStopTrackingTouch(slider: Slider) {
                if (isNativeMode) {
                    draggingBrightness?.let { nativeBrightness.setBrightness(it) }
                }
                draggingBrightness = null
                updateBrightnessSlider()
                if (screenOn && isNativeMode) applyNative(activeTemperature)
            }
        })
        menu.lightSeekbar.addOnChangeListener { _, value, fromUser ->
            if (fromUser && !isNativeMode) {
                coldBrightness = codeForValue(value)
                if (screenOn) commandRunner.runCommands(arrayOf("br_co$coldBrightness"))
            }
        }
        menu.lightWarmSeekbar.addOnChangeListener { _, value, fromUser ->
            if (fromUser && !isNativeMode) {
                warmBrightness = codeForValue(value)
                if (screenOn) commandRunner.runCommands(arrayOf("br_wm$warmBrightness"))
            }
        }
    }
}