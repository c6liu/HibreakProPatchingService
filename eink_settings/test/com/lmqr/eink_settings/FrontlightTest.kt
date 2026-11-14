package com.lmqr.eink_settings

import android.view.ContextThemeWrapper
import android.view.LayoutInflater
import android.view.View
import android.view.MotionEvent
import android.os.Bundle
import android.provider.Settings
import android.os.Handler
import android.os.Looper
import android.view.accessibility.AccessibilityNodeInfo
import com.google.android.material.slider.Slider
import androidx.preference.PreferenceManager
import com.lmqr.eink_settings.command_runners.CommandRunner
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import kotlin.math.abs

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class FrontlightTest {
    private class RecordingRunner : CommandRunner {
        val commands = mutableListOf<String>()
        override fun runCommands(cmds: Array<String>) { commands += cmds }
        override fun onDestroy() {}
    }

    private class FakeSource(override var brightness: Float) : NativeBrightnessSource {
        var listener: (() -> Unit)? = null
        var refreshAction: (() -> Unit)? = null
        override fun start(onChange: () -> Unit) { listener = onChange }
        override fun refresh() { refreshAction?.invoke() }
        override fun stop() { listener = null }
        override fun setBrightness(value: Float): Boolean { change(value); return true }
        fun change(value: Float) { brightness = value; listener?.invoke() }
    }

    private val prefs by lazy {
        PreferenceManager.getDefaultSharedPreferences(RuntimeEnvironment.getApplication())
    }

    @Before
    fun clearPrefs() {
        prefs.edit().clear().commit()
    }

    private fun total(codes: FrontlightMixer.Codes) =
        FrontlightMixer.outputForCode(codes.cool) * FrontlightMixer.COOL_MAX_OUTPUT +
            FrontlightMixer.outputForCode(codes.warm) * FrontlightMixer.WARM_MAX_OUTPUT

    private val physicalMax = FrontlightMixer.COOL_MAX_OUTPUT + FrontlightMixer.WARM_MAX_OUTPUT

    @Test
    fun exponentialCurveInvertsEveryCode() {
        for (code in 0..255) {
            assertEquals(code, FrontlightMixer.codeForOutput(FrontlightMixer.outputForCode(code)))
        }
        assertEquals(1.0, FrontlightMixer.outputForCode(255), 1e-6)
        assertEquals(0, FrontlightMixer.codeForOutput(0.0))
    }

    @Test
    fun outputIsCappedJustBelowPhysicalMaximum() {
        for (step in 0..100) {
            val codes = FrontlightMixer.mix(1.0, step / 100.0)
            assertTrue(total(codes) <= FrontlightMixer.OUTPUT_CAP * physicalMax * 1.015)
        }
        val brightest = (0..100).maxOf { total(FrontlightMixer.mix(1.0, it / 100.0)) } / physicalMax
        assertEquals(FrontlightMixer.OUTPUT_CAP, brightest, 0.015)
    }

    @Test
    fun brightnessStaysConstantAcrossAchievableTemperatures() {
        for (brightness in listOf(0.05, 0.2, 0.5)) {
            val expected = brightness * FrontlightMixer.OUTPUT_CAP * physicalMax
            for (step in 0..100) {
                val actual = total(FrontlightMixer.mix(brightness, step / 100.0))
                assertTrue("b=$brightness t=$step: $actual vs $expected",
                    abs(actual - expected) / expected < 0.03)
            }
        }
    }

    @Test
    fun saturatedEndpointsDimWithoutChangingTheMix() {
        val neutral = FrontlightMixer.mix(1.0, FrontlightMixer.NEUTRAL_TEMPERATURE)
        assertEquals(neutral.cool, neutral.warm)
        assertEquals(FrontlightMixer.Codes(0, 255), FrontlightMixer.mix(1.0, 1.0))
        assertEquals(FrontlightMixer.Codes(255, 0), FrontlightMixer.mix(1.0, 0.0))
        val temperature = 0.85
        val codes = FrontlightMixer.mix(1.0, temperature)
        assertEquals(255, codes.warm)
        val warmShare = FrontlightMixer.outputForCode(codes.warm) *
            FrontlightMixer.WARM_MAX_OUTPUT / total(codes)
        assertEquals(FrontlightMixer.warmShare(temperature), warmShare, 0.02)
    }

    @Test
    fun temperatureMappingIsMonotonicAndSpansBothLeds() {
        assertEquals(0.0, FrontlightMixer.warmShare(0.0), 0.0)
        assertEquals(1.0, FrontlightMixer.warmShare(1.0), 0.0)
        var previous = -1.0
        for (step in 0..100) {
            val share = FrontlightMixer.warmShare(step / 100.0)
            assertTrue(share > previous)
            previous = share
        }
    }

    @Test
    fun centredNeutralKeepsSensitivityImbalanceSmall() {
        assertEquals(0.0, FrontlightMixer.ease(0.0), 1e-12)
        assertEquals(1.0, FrontlightMixer.ease(1.0), 1e-12)
        val neutral = FrontlightMixer.mix(1.0, 0.5)
        assertEquals(neutral.cool, neutral.warm)
        val h = 1e-4
        val slopes = (0 until 1000).map { i ->
            val p = i / 1000.0
            (FrontlightMixer.ease(p + h) - FrontlightMixer.ease(p)) / h
        }
        assertTrue("slope ratio ${slopes.max() / slopes.min()}", slopes.max() / slopes.min() < 1.5)
    }

    @Test
    fun perceptualBrightnessRoundTripsAndKeepsEqualLightnessSteps() {
        assertEquals(0.0, FrontlightMixer.outputForLightness(0.0), 0.0)
        assertEquals(1.0, FrontlightMixer.outputForLightness(1.0), 1e-12)
        assertEquals(0.18419, FrontlightMixer.outputForLightness(0.5), 0.00001)
        for (step in 0..1000) {
            val position = step / 1000.0
            assertEquals(position, FrontlightMixer.lightnessForOutput(
                FrontlightMixer.outputForLightness(position)), 1e-12)
        }
        for (step in 10..100) {
            val desired = step / 100.0
            val code = FrontlightMixer.codeForOutput(FrontlightMixer.outputForLightness(desired))
            val actual = FrontlightMixer.lightnessForOutput(FrontlightMixer.outputForCode(code))
            assertEquals(desired, actual, 0.006)
        }
    }

    @Test
    fun savingAndroidBrightnessDoesNotChangeAutomaticMode() {
        val context = RuntimeEnvironment.getApplication()
        val resolver = context.contentResolver
        Settings.System.putFloat(resolver, "screen_brightness_float", 0.9f)
        Settings.System.putInt(resolver, Settings.System.SCREEN_BRIGHTNESS, 19)
        val source = DisplayBrightnessSource(context, Handler(Looper.getMainLooper()))
        assertEquals(18 / 254f, source.brightness)
        for (mode in listOf(Settings.System.SCREEN_BRIGHTNESS_MODE_AUTOMATIC,
                Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL)) {
            Settings.System.putInt(resolver, Settings.System.SCREEN_BRIGHTNESS_MODE, mode)
            for ((requested, setting) in listOf(0f to 1, 0.25f to 65, 0.437f to 112, 1f to 255)) {
                assertTrue(source.setBrightness(requested))
                assertEquals(setting, Settings.System.getInt(resolver, Settings.System.SCREEN_BRIGHTNESS))
                assertEquals((setting - 1) / 254f, source.brightness)
                assertEquals(mode, Settings.System.getInt(resolver, Settings.System.SCREEN_BRIGHTNESS_MODE))
            }
        }
    }

    @Test
    fun dumpParserReadsTheDefaultDisplay() {
        val dump = """
            Display Power Controller:
              mDisplayId=2
              mCachedBrightnessInfo.adjustedBrightness=0.9
            Display Power Controller:
              mDisplayId=0
              mCachedBrightnessInfo.brightness=0.7
              mCachedBrightnessInfo.adjustedBrightness=0.25
        """.trimIndent().lineSequence()
        assertEquals(0.25f, DisplayBrightnessSource.parseAdjustedBrightness(dump))
        assertEquals(0f, DisplayBrightnessSource.parseAdjustedBrightness(sequenceOf(
            "mDisplayId=0", "mCachedBrightnessInfo.adjustedBrightness=-1.0")))
        assertNull(DisplayBrightnessSource.parseAdjustedBrightness(sequenceOf("Permission Denial")))
    }

    @Test
    fun modesOwnTheLightsExclusivelyAndPreserveIndependentValues() {
        val runner = RecordingRunner()
        val source = FakeSource(0.5f)
        val manager = BrightnessManager(prefs, runner, source)
        assertTrue(manager.isNativeMode)
        prefs.edit().putBoolean(BrightnessManager.PREF_NATIVE_MODE, false).commit()
        manager.setBrightness(40, 90)
        assertEquals(listOf("br_co40", "br_wm90"), runner.commands)

        runner.commands.clear()
        prefs.edit().putBoolean(BrightnessManager.PREF_NATIVE_MODE, true).commit()
        manager.onModeChanged()
        val neutral = FrontlightMixer.NEUTRAL_TEMPERATURE
        val mixed = FrontlightMixer.mix(0.5, neutral)
        assertEquals(listOf("br_co${mixed.cool}", "br_wm${mixed.warm}"), runner.commands)

        runner.commands.clear()
        source.change(0.2f)
        val dimmer = FrontlightMixer.mix(0.2f.toDouble(), neutral)
        assertEquals(listOf("br_co${dimmer.cool}", "br_wm${dimmer.warm}"), runner.commands)

        runner.commands.clear()
        manager.onScreenStateChanged(false)
        source.change(0.8f)
        assertEquals(listOf("br_co0", "br_wm0"), runner.commands)

        runner.commands.clear()
        manager.onScreenStateChanged(true)
        val restored = FrontlightMixer.mix(0.8f.toDouble(), neutral)
        assertEquals(listOf("br_co${restored.cool}", "br_wm${restored.warm}"), runner.commands)

        runner.commands.clear()
        prefs.edit().putBoolean(BrightnessManager.PREF_NATIVE_MODE, false).commit()
        manager.onModeChanged()
        assertNull(source.listener)
        assertEquals(listOf("br_co40", "br_wm90"), runner.commands)
    }

    @Test
    fun bootReapplyRestoresUnchangedBrightnessAndRefreshesPastTheBootOverride() {
        val runner = RecordingRunner()
        val source = FakeSource(0.1f)
        val manager = BrightnessManager(prefs, runner, source)
        manager.applyBrightness()
        val savedCommands = runner.commands.toList()

        runner.commands.clear()
        manager.reapplyBrightness()
        assertEquals(savedCommands, runner.commands)

        runner.commands.clear()
        source.refreshAction = { source.change(0.2f) }
        manager.reapplyBrightness()
        val refreshed = FrontlightMixer.mix(0.2f.toDouble(), manager.temperature.toDouble())
        assertEquals(listOf("br_co${refreshed.cool}", "br_wm${refreshed.warm}"),
            runner.commands.takeLast(2))

        manager.onScreenStateChanged(false)
        runner.commands.clear()
        manager.reapplyBrightness()
        assertTrue(runner.commands.isEmpty())

        prefs.edit().putBoolean(BrightnessManager.PREF_NATIVE_MODE, false).commit()
        manager.onScreenStateChanged(true)
        runner.commands.clear()
        manager.reapplyBrightness()
        assertEquals(listOf("br_co64", "br_wm64"), runner.commands)
    }

    @Test
    fun overlayShowsOnlyTheActiveModeControls() {
        val context = ContextThemeWrapper(RuntimeEnvironment.getApplication(), R.style.Theme_EinkSettings)
        val menu = FloatingMenuViewAccessor(
            LayoutInflater.from(context).inflate(R.layout.floating_menu_layout, null)
        )
        val runner = RecordingRunner()
        val source = FakeSource(1f)
        val manager = BrightnessManager(prefs, runner, source)
        prefs.edit().putBoolean(BrightnessManager.PREF_NATIVE_MODE, false).commit()
        manager.setupSliders(menu)
        fun update() = manager.updateOverlay(menu)

        update()
        assertTrue(menu.independentLightControls.all { it.visibility == View.VISIBLE })
        assertTrue(menu.nativeLightControls.all { it.visibility == View.GONE })

        changeFromUser(menu.lightSeekbar, 500f)
        val halfLightness = FrontlightMixer.codeForOutput(FrontlightMixer.outputForLightness(0.5))
        assertEquals(listOf("br_co$halfLightness"), runner.commands)
        assertEquals(halfLightness, manager.coldBrightness)

        prefs.edit().putBoolean(BrightnessManager.PREF_NATIVE_MODE, true).commit()
        manager.onModeChanged()
        update()
        assertTrue(menu.independentLightControls.all { it.visibility == View.GONE })
        assertTrue(menu.nativeLightControls.all { it.visibility == View.VISIBLE })
        assertEquals(BrightnessManager.NEUTRAL_PROGRESS.toFloat(), menu.lightTemperatureSeekbar.value)
        val temperatureNode = requireNotNull(
            menu.lightTemperatureSeekbar.accessibilityNodeProvider.createAccessibilityNodeInfo(0))
        assertTrue(temperatureNode.contentDescription.toString().contains("50%"))

        // Drags near neutral white snap to the 4800 K stop where both channels are at full.
        changeFromUser(menu.lightTemperatureSeekbar, BrightnessManager.NEUTRAL_PROGRESS + 20f)
        assertEquals(BrightnessManager.NEUTRAL_PROGRESS.toFloat(), menu.lightTemperatureSeekbar.value)

        runner.commands.clear()
        changeFromUser(menu.lightTemperatureSeekbar, BrightnessManager.TEMPERATURE_STEPS.toFloat())
        val warm = FrontlightMixer.mix(1.0, 1.0)
        assertEquals(listOf("br_co${warm.cool}", "br_wm${warm.warm}"), runner.commands)

        // A brightness change mid-drag keeps the dragged mix rather than the saved one.
        runner.commands.clear()
        source.change(0.3f)
        val dimWarm = FrontlightMixer.mix(0.3f.toDouble(), 1.0)
        assertEquals(listOf("br_co${dimWarm.cool}", "br_wm${dimWarm.warm}"), runner.commands)

        assertEquals(1f, manager.temperature)
    }

    @Test
    fun nativeOverlayBrightnessAppliesImmediatelyAndFollowsLaterAndroidChanges() {
        val context = ContextThemeWrapper(RuntimeEnvironment.getApplication(), R.style.Theme_EinkSettings)
        val menu = FloatingMenuViewAccessor(LayoutInflater.from(context).inflate(R.layout.floating_menu_layout, null))
        val runner = RecordingRunner()
        val source = FakeSource(0.5f)
        val manager = BrightnessManager(prefs, runner, source)
        manager.setupSliders(menu)
        manager.applyBrightness()
        runner.commands.clear()
        changeFromUser(menu.lightBrightnessSeekbar, 500f)
        val expected = FrontlightMixer.mix(FrontlightMixer.outputForLightness(0.5).toFloat().toDouble(), 0.5)
        assertEquals(listOf("br_co${expected.cool}", "br_wm${expected.warm}"), runner.commands)
        assertEquals(FrontlightMixer.outputForLightness(0.5).toFloat(), source.brightness)

        source.change(0.7f)
        assertEquals((FrontlightMixer.lightnessForOutput(0.7f.toDouble()) * 1000).toFloat(),
            menu.lightBrightnessSeekbar.value)
        runner.commands.clear()
        menu.lightBrightnessSeekbar.value = 100f
        assertTrue(runner.commands.isEmpty())
        manager.onScreenStateChanged(false)
        runner.commands.clear()
        changeFromUser(menu.lightBrightnessSeekbar, 400f)
        assertTrue(runner.commands.isEmpty())
    }

    @Test
    fun brightnessDragIgnoresDelayedDisplayEventsAndKeepsLiveTemperature() {
        val context = ContextThemeWrapper(RuntimeEnvironment.getApplication(), R.style.Theme_EinkSettings)
        val menu = FloatingMenuViewAccessor(LayoutInflater.from(context).inflate(R.layout.floating_menu_layout, null))
        val source = FakeSource(0.5f)
        val runner = RecordingRunner()
        val manager = BrightnessManager(prefs, runner, source)
        manager.setupSliders(menu)
        manager.applyBrightness()
        val slider = menu.lightBrightnessSeekbar
        slider.measure(View.MeasureSpec.makeMeasureSpec(600, View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec(100, View.MeasureSpec.EXACTLY))
        slider.layout(0, 0, 600, 100)
        MotionEvent.obtain(0, 0, MotionEvent.ACTION_DOWN, 300f, 50f, 0).let {
            try { assertTrue(slider.onTouchEvent(it)) } finally { it.recycle() }
        }
        val liveBrightness = source.brightness
        runner.commands.clear()
        source.change(0.1f)
        assertTrue(runner.commands.isEmpty())
        assertEquals(500f, slider.value)
        changeFromUser(menu.lightTemperatureSeekbar, 1000f)
        val expected = FrontlightMixer.mix(liveBrightness.toDouble(), 1.0)
        assertEquals(listOf("br_co${expected.cool}", "br_wm${expected.warm}"), runner.commands)
        runner.commands.clear()
        MotionEvent.obtain(0, 10, MotionEvent.ACTION_UP, 300f, 50f, 0).let {
            try { slider.onTouchEvent(it) } finally { it.recycle() }
        }
        assertEquals(liveBrightness, source.brightness)
        assertEquals(500f, slider.value, 0.001f)
        assertTrue(runner.commands.isEmpty())
        source.change(0.4f)
        assertEquals((FrontlightMixer.lightnessForOutput(0.4f.toDouble()) * 1000).toFloat(),
            slider.value)
    }

    private fun changeFromUser(slider: Slider, value: Float) {
        assertTrue(slider.accessibilityNodeProvider.performAction(0,
            AccessibilityNodeInfo.AccessibilityAction.ACTION_SET_PROGRESS.id,
            Bundle().apply { putFloat(AccessibilityNodeInfo.ACTION_ARGUMENT_PROGRESS_VALUE, value) }))
    }
}
