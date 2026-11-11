package com.lmqr.ha9_comp_service

import android.content.res.Configuration
import android.view.ContextThemeWrapper
import android.view.KeyEvent
import android.view.LayoutInflater
import com.google.android.material.button.MaterialButton
import com.google.android.material.appbar.MaterialToolbar
import com.google.android.material.color.MaterialColors
import com.google.android.material.materialswitch.MaterialSwitch
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import androidx.preference.SwitchPreferenceCompat
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class MaterialAndKeyTest {
    @Test
    fun fingerprintF9IsConsumedWithoutDispatch() {
        val service = Robolectric.buildService(A9AccessibilityService::class.java).get()
        val receiver = ScreenOffKeyReceiver(service)
        try {
            for (scanCode in listOf(0, 67, 59, 60)) {
                for (action in listOf(KeyEvent.ACTION_DOWN, KeyEvent.ACTION_UP)) {
                    for (repeat in 0..2) {
                        assertTrue(receiver.onKeyEvent(
                            KeyEvent(0, 0, action, KeyEvent.KEYCODE_F9, repeat, 0, 0, scanCode)
                        ))
                    }
                }
            }
            for (key in listOf(KeyEvent.KEYCODE_POWER, KeyEvent.KEYCODE_F8, KeyEvent.KEYCODE_F10)) {
                for (action in listOf(KeyEvent.ACTION_DOWN, KeyEvent.ACTION_UP)) {
                    assertFalse(receiver.onKeyEvent(KeyEvent(action, key)))
                }
            }
        } finally {
            receiver.close()
        }
    }

    @Test
    fun menuUsesMaterialControlsAndPreservesSelection() {
        for (night in listOf(Configuration.UI_MODE_NIGHT_NO, Configuration.UI_MODE_NIGHT_YES)) {
            val app = RuntimeEnvironment.getApplication()
            val configuration = Configuration(app.resources.configuration)
            configuration.uiMode = (configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK.inv()) or night
            val context = ContextThemeWrapper(
                app.createConfigurationContext(configuration), R.style.Theme_Ha9_comp_service
            )
            context.theme.applyStyle(
                com.google.android.material.R.style.ThemeOverlay_Material3_DynamicColors_DayNight,
                true,
            )
            val primary = if (night == Configuration.UI_MODE_NIGHT_NO) {
                android.R.color.system_primary_light
            } else {
                android.R.color.system_primary_dark
            }
            assertEquals(context.getColor(primary), MaterialColors.getColor(
                context, androidx.appcompat.R.attr.colorPrimary, 0
            ))
            val settings = LayoutInflater.from(context).inflate(R.layout.settings_activity, null)
            assertTrue(settings.findViewById<android.view.View>(R.id.settings_toolbar) is MaterialToolbar)
            val binding = FloatingMenuViewAccessor(
                LayoutInflater.from(context).inflate(R.layout.floating_menu_layout, null)
            )
            val buttons = listOf(binding.button1, binding.button2, binding.button3, binding.button4, binding.button5)
            assertTrue(buttons.all { it is MaterialButton })
            assertTrue(binding.autoRefresh is MaterialSwitch)
            assertTrue(binding.antiShake is MaterialSwitch)
            assertTrue(binding.videoOptimizedRefresh is MaterialSwitch)
            for ((index, mode) in listOf(
                RefreshMode.SMOOTH, RefreshMode.CLEAR, RefreshMode.BALANCED, RefreshMode.SPEED, RefreshMode.HYPER
            ).withIndex()) {
                binding.updateButtons(mode)
                for ((buttonIndex, button) in buttons.withIndex()) {
                    assertEquals(index == buttonIndex, button.isActivated)
                    assertEquals(index == buttonIndex, button.isSelected)
                }
            }

        }
    }

    @Test
    fun settingsStartAndUseMaterialPreferenceSwitches() {
        val controller = Robolectric.buildActivity(SettingsActivity::class.java).setup()
        try {
            val activity = controller.get()
            val fragment = activity.supportFragmentManager.findFragmentById(R.id.settings)
                as SettingsActivity.SettingsFragment
            for (key in listOf(
                "camera_live_refresh", "aod_invert", "allow_custom_broadcast",
                "refresh_on_lock", "disable_perapprefresh"
            )) {
                val preference = requireNotNull(fragment.findPreference<SwitchPreferenceCompat>(key))
                assertEquals(R.layout.preference_material_switch, preference.widgetLayoutResource)
                val widget = LayoutInflater.from(preference.context).inflate(
                    preference.widgetLayoutResource, null
                )
                assertTrue(widget is MaterialSwitch)
            }
        } finally {
            controller.pause().stop().destroy()
        }
    }
}
