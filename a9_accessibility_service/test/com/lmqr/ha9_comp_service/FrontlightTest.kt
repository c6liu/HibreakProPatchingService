package com.lmqr.ha9_comp_service

import android.view.ContextThemeWrapper
import android.view.LayoutInflater
import android.view.View
import androidx.preference.PreferenceManager
import com.lmqr.ha9_comp_service.command_runners.CommandRunner
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
        override fun start(onChange: () -> Unit) { listener = onChange }
        override fun refresh() {}
        override fun stop() { listener = null }
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
    fun overlayShowsOnlyTheActiveModeControls() {
        val context = ContextThemeWrapper(RuntimeEnvironment.getApplication(), R.style.Theme_Ha9_comp_service)
        val menu = FloatingMenuViewAccessor(
            LayoutInflater.from(context).inflate(R.layout.floating_menu_layout, null)
        )
        val runner = RecordingRunner()
        val source = FakeSource(1f)
        val manager = BrightnessManager(prefs, runner, source)
        prefs.edit().putBoolean(BrightnessManager.PREF_NATIVE_MODE, false).commit()
        manager.setupSeekBars(menu.lightSeekbar, menu.lightWarmSeekbar, menu.lightTemperatureSeekbar)
        fun update() = manager.updateOverlay(menu.lightSeekbar, menu.lightWarmSeekbar,
            menu.lightTemperatureSeekbar, menu.independentLightControls, menu.nativeLightControls)

        update()
        assertTrue(menu.independentLightControls.all { it.visibility == View.VISIBLE })
        assertTrue(menu.nativeLightControls.all { it.visibility == View.GONE })

        // Independent sliders write driver codes directly, without a gamma curve.
        shadowListener(menu.lightSeekbar).onProgressChanged(menu.lightSeekbar, 100, true)
        assertEquals(listOf("br_co100"), runner.commands)

        prefs.edit().putBoolean(BrightnessManager.PREF_NATIVE_MODE, true).commit()
        manager.onModeChanged()
        update()
        assertTrue(menu.independentLightControls.all { it.visibility == View.GONE })
        assertTrue(menu.nativeLightControls.all { it.visibility == View.VISIBLE })
        assertEquals(BrightnessManager.NEUTRAL_PROGRESS, menu.lightTemperatureSeekbar.progress)

        // Drags near neutral white snap to the 4800 K stop where both channels are at full.
        val listener = shadowListener(menu.lightTemperatureSeekbar)
        listener.onStartTrackingTouch(menu.lightTemperatureSeekbar)
        listener.onProgressChanged(menu.lightTemperatureSeekbar, BrightnessManager.NEUTRAL_PROGRESS + 20, true)
        assertEquals(BrightnessManager.NEUTRAL_PROGRESS, menu.lightTemperatureSeekbar.progress)

        runner.commands.clear()
        menu.lightTemperatureSeekbar.setProgress(BrightnessManager.TEMPERATURE_STEPS, true)
        // Programmatic changes are not user input; simulate a completed drag instead.
        listener.onProgressChanged(menu.lightTemperatureSeekbar, BrightnessManager.TEMPERATURE_STEPS, true)
        val warm = FrontlightMixer.mix(1.0, 1.0)
        assertEquals(listOf("br_co${warm.cool}", "br_wm${warm.warm}"), runner.commands)

        // A brightness change mid-drag keeps the dragged mix rather than the saved one.
        runner.commands.clear()
        source.change(0.3f)
        val dimWarm = FrontlightMixer.mix(0.3f.toDouble(), 1.0)
        assertEquals(listOf("br_co${dimWarm.cool}", "br_wm${dimWarm.warm}"), runner.commands)

        listener.onStopTrackingTouch(menu.lightTemperatureSeekbar)
        assertEquals(1f, manager.temperature)
    }

    private fun shadowListener(seekBar: android.widget.SeekBar) =
        org.robolectric.Shadows.shadowOf(seekBar).onSeekBarChangeListener
}
