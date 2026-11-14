package com.lmqr.eink_settings

import android.content.res.Configuration
import android.graphics.PixelFormat
import android.graphics.drawable.InsetDrawable
import android.os.Bundle
import android.os.Looper
import android.view.ContextThemeWrapper
import android.view.KeyEvent
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.view.accessibility.AccessibilityNodeInfo
import android.widget.ImageView
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.core.widget.NestedScrollView
import androidx.core.view.descendants
import androidx.preference.ListPreference
import androidx.preference.PreferenceManager
import androidx.preference.PreferenceViewHolder
import com.google.android.material.button.MaterialButton
import com.google.android.material.appbar.MaterialToolbar
import com.google.android.material.color.MaterialColors
import com.google.android.material.materialswitch.MaterialSwitch
import com.google.android.material.shape.MaterialShapeDrawable
import com.google.android.material.slider.Slider
import com.lmqr.eink_settings.command_runners.CommandRunner
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import androidx.preference.SwitchPreferenceCompat
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.util.ReflectionHelpers
import kotlin.math.roundToInt

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class MaterialAndKeyTest {
    @Test
    fun fingerprintF9IsConsumedWithoutDispatch() {
        val service = Robolectric.buildService(EinkAccessibilityService::class.java).get()
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
                app.createConfigurationContext(configuration), R.style.Theme_EinkSettings
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
            val overlay = LayoutInflater.from(context)
                .inflate(R.layout.floating_menu_layout, null) as NestedScrollView
            val binding = FloatingMenuViewAccessor(overlay)
            val iconTint = MaterialColors.getColor(
                context, com.google.android.material.R.attr.colorOnSurfaceVariant, 0
            )
            for (icon in overlay.descendants.filterIsInstance<ImageView>()) {
                assertEquals(iconTint, icon.imageTintList?.defaultColor)
            }
            val buttons = listOf(binding.button1, binding.button2, binding.button3, binding.button4, binding.button5)
            assertTrue(buttons.all { it is MaterialButton })
            assertTrue(binding.autoRefresh is MaterialSwitch)
            assertTrue(binding.antiShake is MaterialSwitch)
            assertTrue(binding.videoOptimizedRefresh is MaterialSwitch)
            assertEquals(context.getString(R.string.close_overlay), binding.closeButton.contentDescription)
            binding.closeButton.performClick()
            assertEquals(android.view.View.GONE, binding.root.visibility)
            binding.root.visibility = android.view.View.VISIBLE
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
        val prefs = PreferenceManager.getDefaultSharedPreferences(RuntimeEnvironment.getApplication())
        prefs.edit().remove("force_accent_color").commit()
        val controller = Robolectric.buildActivity(SettingsActivity::class.java).setup()
        try {
            val activity = controller.get()
            val fragment = activity.supportFragmentManager.findFragmentById(R.id.settings)
                as SettingsActivity.SettingsFragment
            for (key in listOf(
                "camera_live_refresh", "aod_invert", "allow_custom_broadcast",
                "refresh_on_lock", "disable_perapprefresh", "force_accent_color"
            )) {
                val preference = requireNotNull(fragment.findPreference<SwitchPreferenceCompat>(key))
                assertEquals(R.layout.preference_material_switch, preference.widgetLayoutResource)
                val widget = LayoutInflater.from(preference.context).inflate(
                    preference.widgetLayoutResource, null
                )
                assertTrue(widget is MaterialSwitch)
            }
            assertFalse(prefs.getBoolean("force_accent_color", true))
        } finally {
            controller.pause().stop().destroy()
        }
    }

    @Test
    @Config(qualifiers = "w400dp-h900dp-port-mdpi")
    fun popupScrollsInLandscapeWithoutLosingControlState() {
        val context = ContextThemeWrapper(RuntimeEnvironment.getApplication(), R.style.Theme_EinkSettings)
        val menu = FloatingMenuViewAccessor(LayoutInflater.from(context).inflate(R.layout.floating_menu_layout, null))
        val scroll = menu.root as NestedScrollView
        fun layout(width: Int, height: Int) {
            scroll.measure(View.MeasureSpec.makeMeasureSpec(width, View.MeasureSpec.EXACTLY),
                View.MeasureSpec.makeMeasureSpec(height, View.MeasureSpec.AT_MOST))
            scroll.layout(0, 0, scroll.measuredWidth, scroll.measuredHeight)
        }
        menu.lightSeekbar.value = 0.6f
        menu.antiShake.isChecked = true
        layout(400, 900)
        assertTrue(scroll.height < 900)
        layout(800, 320)
        assertTrue(scroll.getChildAt(0).height > scroll.height)
        scroll.scrollTo(0, scroll.getChildAt(0).height)
        assertTrue(scroll.scrollY > 0)
        assertTrue(scroll.scrollY + scroll.height >= scroll.getChildAt(0).height)
        layout(400, 900)
        assertEquals(0, scroll.scrollY)
        assertEquals(0.6f, menu.lightSeekbar.value)
        assertTrue(menu.antiShake.isChecked)
    }

    @Test
    @Config(qualifiers = "w400dp-h900dp-port-mdpi")
    fun popupWidthTracksRotatedWindowBounds() {
        val service = Robolectric.buildService(EinkAccessibilityService::class.java).get()
        val context = ContextThemeWrapper(service, R.style.Theme_EinkSettings)
        val menu = FloatingMenuViewAccessor(LayoutInflater.from(context).inflate(R.layout.floating_menu_layout, null))
        val wm = service.getSystemService(WindowManager::class.java)
        val params = WindowManager.LayoutParams(WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE, PixelFormat.TRANSLUCENT)
        wm.addView(menu.root, params)
        ReflectionHelpers.setField(service, "menuBinding", menu)
        try {
            service.onConfigurationChanged(Configuration(service.resources.configuration))
            assertEquals(400, params.width)
            RuntimeEnvironment.setQualifiers("w900dp-h400dp-land-mdpi")
            service.onConfigurationChanged(Configuration(service.resources.configuration))
            assertEquals(640, params.width)
            RuntimeEnvironment.setQualifiers("w400dp-h900dp-port-mdpi")
            service.onConfigurationChanged(Configuration(service.resources.configuration))
            assertEquals(400, params.width)
        } finally {
            wm.removeViewImmediate(menu.root)
        }
    }

    @Test
    fun customGraySliderRetainsStoredValueAndHonoursChangeVetoAfterRotation() {
        val prefs = PreferenceManager.getDefaultSharedPreferences(RuntimeEnvironment.getApplication())
        prefs.edit().putBoolean("force_accent_color", true)
            .putString("accent_color_preset", "custom").putInt("accent_custom_gray", 27).commit()
        val controller = Robolectric.buildActivity(SettingsActivity::class.java).setup()
        try {
            fun bind(): Pair<Slider, TextView> {
                val activity = controller.get()
                val fragment = activity.supportFragmentManager.findFragmentById(R.id.settings)
                    as SettingsActivity.SettingsFragment
                val preference = requireNotNull(fragment.findPreference<CustomGrayPreference>("accent_custom_gray"))
                val row = LayoutInflater.from(activity).inflate(preference.layoutResource, null)
                val holder = PreferenceViewHolder.createInstanceForTests(row)
                preference.onBindViewHolder(holder)
                preference.onBindViewHolder(holder)
                preference.setOnPreferenceChangeListener { _, value -> value != 70 }
                return row.findViewById<Slider>(R.id.custom_gray_slider) to row.findViewById(R.id.custom_gray_value)
            }
            val (slider, label) = bind()
            assertEquals(27f, slider.value)
            assertTrue(slider.trackHeight < Slider(controller.get()).trackHeight)
            slider.measure(View.MeasureSpec.makeMeasureSpec(600, View.MeasureSpec.EXACTLY),
                View.MeasureSpec.makeMeasureSpec(100, View.MeasureSpec.EXACTLY))
            slider.layout(0, 0, 600, 100)
            fun touch(action: Int) {
                val event = MotionEvent.obtain(0, 0, action, 315.3f, 50f, 0)
                try { slider.onTouchEvent(event) } finally { event.recycle() }
            }
            touch(MotionEvent.ACTION_DOWN)
            assertEquals(27, prefs.getInt("accent_custom_gray", -1))
            assertTrue(slider.value != slider.value.roundToInt().toFloat())
            assertEquals("#${CustomGrayPreference.hexForGray(slider.value.roundToInt())}", label.text.toString())
            touch(MotionEvent.ACTION_UP)
            assertEquals(slider.value.toInt(), prefs.getInt("accent_custom_gray", -1))
            changeSlider(slider, 65f)
            assertEquals(65, prefs.getInt("accent_custom_gray", -1))
            assertEquals("#414141", label.text.toString())
            changeSlider(slider, 70f)
            assertEquals(65f, slider.value)
            assertEquals(65, prefs.getInt("accent_custom_gray", -1))
            controller.configurationChange(Configuration(controller.get().resources.configuration).apply {
                orientation = Configuration.ORIENTATION_LANDSCAPE
                screenWidthDp = 900
                screenHeightDp = 400
            })
            assertEquals(65f, bind().first.value)
        } finally {
            controller.pause().stop().destroy()
        }
    }

    @Test
    fun accentPresetDialogKeepsCustomVisibilityAndSelectionAcrossRotation() {
        val prefs = PreferenceManager.getDefaultSharedPreferences(RuntimeEnvironment.getApplication())
        prefs.edit().putBoolean("force_accent_color", false)
            .putString("accent_color_preset", "808080").commit()
        val controller = Robolectric.buildActivity(SettingsActivity::class.java).setup()
        try {
            fun fragment() = controller.get().supportFragmentManager.findFragmentById(R.id.settings)
                as SettingsActivity.SettingsFragment
            fun preset() = requireNotNull(fragment().findPreference<ListPreference>("accent_color_preset"))
            fun custom() = requireNotNull(fragment().findPreference<CustomGrayPreference>("accent_custom_gray"))
            assertFalse(preset().isEnabled)
            assertFalse(custom().isVisible)
            requireNotNull(fragment().findPreference<SwitchPreferenceCompat>("force_accent_color")).isChecked = true
            assertTrue(preset().isEnabled)
            fragment().onDisplayPreferenceDialog(preset())
            controller.get().supportFragmentManager.executePendingTransactions()
            val dialog = controller.get().supportFragmentManager.fragments
                .filterIsInstance<MaterialListPreferenceDialogFragment>().single().requireDialog() as AlertDialog
            choose(dialog, preset().findIndexOfValue("custom"))
            controller.get().supportFragmentManager.executePendingTransactions()
            assertTrue(custom().isVisible)
            controller.configurationChange(Configuration(controller.get().resources.configuration).apply {
                orientation = Configuration.ORIENTATION_LANDSCAPE
                screenWidthDp = 900
                screenHeightDp = 400
            })
            assertEquals("custom", preset().value)
            assertTrue(custom().isVisible)
            requireNotNull(fragment().findPreference<SwitchPreferenceCompat>("force_accent_color")).isChecked = false
            assertFalse(custom().isEnabled)
            assertFalse(preset().isEnabled)
        } finally {
            controller.pause().stop().destroy()
        }
    }

    @Test
    fun accentWritesAreOptInAndUseAllFivePresetsOrCustomGray() {
        val prefs = PreferenceManager.getDefaultSharedPreferences(RuntimeEnvironment.getApplication())
        prefs.edit().remove("force_accent_color").putInt("color_scheme_color", 27)
            .putString("color_scheme_type", "5").putString("accent_color_preset", "808080").commit()
        val service = Robolectric.buildService(EinkAccessibilityService::class.java).get()
        val commands = mutableListOf<String>()
        val runner = object : CommandRunner {
            override fun runCommands(cmds: Array<String>) { commands.addAll(cmds) }
            override fun onDestroy() {}
        }
        ReflectionHelpers.setField(service, "commandRunner", runner)
        service.onSharedPreferenceChanged(prefs, "force_accent_color")
        service.onSharedPreferenceChanged(prefs, "color_scheme_type")
        assertTrue(commands.isEmpty())
        prefs.edit().putBoolean("force_accent_color", true).commit()
        service.onSharedPreferenceChanged(prefs, "force_accent_color")
        assertEquals(listOf("theme 5 808080"), commands)
        commands.clear()
        for (shade in listOf("000000", "404040", "808080", "BFBFBF", "FFFFFF")) {
            prefs.edit().putString("accent_color_preset", shade).commit()
            service.onSharedPreferenceChanged(prefs, "accent_color_preset")
            assertEquals(listOf("theme 5 $shade"), commands)
            commands.clear()
        }
        prefs.edit().putString("accent_color_preset", "custom").commit()
        for ((gray, hex) in listOf(0 to "000000", 65 to "414141", 255 to "FFFFFF")) {
            prefs.edit().putInt("accent_custom_gray", gray).commit()
            service.onSharedPreferenceChanged(prefs, "accent_custom_gray")
            assertEquals(listOf("theme 5 $hex"), commands)
            commands.clear()
        }
        prefs.edit().putBoolean("force_accent_color", false).commit()
        service.onSharedPreferenceChanged(prefs, "force_accent_color")
        prefs.edit().putInt("accent_custom_gray", 20).putString("color_scheme_type", "0").commit()
        service.onSharedPreferenceChanged(prefs, "accent_custom_gray")
        service.onSharedPreferenceChanged(prefs, "color_scheme_type")
        assertTrue(commands.isEmpty())
        assertEquals(27, prefs.getInt("color_scheme_color", -1))
        prefs.edit().putBoolean("force_accent_color", true)
            .putString("accent_color_preset", "not-a-color").commit()
        service.onSharedPreferenceChanged(prefs, "accent_color_preset")
        assertTrue(commands.isEmpty())
    }

    @Test
    fun materialChoicesPreserveSelectionAcrossRotationAndRespectCancelAndVeto() {
        val prefs = PreferenceManager.getDefaultSharedPreferences(RuntimeEnvironment.getApplication())
        prefs.edit().putString("refresh_setting", "0").commit()
        val controller = Robolectric.buildActivity(SettingsActivity::class.java).setup()
        try {
            fun fragment() = controller.get().supportFragmentManager.findFragmentById(R.id.settings)
                as SettingsActivity.SettingsFragment
            fun dialog(): AlertDialog {
                val fm = controller.get().supportFragmentManager
                fm.executePendingTransactions()
                return fm.fragments.filterIsInstance<MaterialListPreferenceDialogFragment>()
                    .single().requireDialog() as AlertDialog
            }
            fun open() {
                fragment().onDisplayPreferenceDialog(
                    requireNotNull(fragment().findPreference<ListPreference>("refresh_setting")))
            }
            open()
            assertEquals(1, dialog().listView.checkedItemPosition)
            assertTrue((dialog().window!!.decorView.background as InsetDrawable).drawable is MaterialShapeDrawable)
            controller.configurationChange(Configuration(controller.get().resources.configuration).apply {
                orientation = Configuration.ORIENTATION_LANDSCAPE
                screenWidthDp = 900
                screenHeightDp = 400
            })
            assertEquals(1, dialog().listView.checkedItemPosition)
            dialog().cancel()
            shadowOf(Looper.getMainLooper()).idle()
            controller.get().supportFragmentManager.executePendingTransactions()
            assertEquals("0", prefs.getString("refresh_setting", null))
            open()
            choose(dialog(), 2)
            controller.get().supportFragmentManager.executePendingTransactions()
            assertEquals("1", prefs.getString("refresh_setting", null))
            requireNotNull(fragment().findPreference<ListPreference>("refresh_setting"))
                .setOnPreferenceChangeListener { _, _ -> false }
            open()
            choose(dialog(), 3)
            controller.get().supportFragmentManager.executePendingTransactions()
            assertEquals("1", prefs.getString("refresh_setting", null))
        } finally {
            controller.pause().stop().destroy()
        }
    }

    @Test
    fun materialChoiceKeepsPerAppIntegerStorageAndDefaultRemoval() {
        val prefs = PreferenceManager.getDefaultSharedPreferences(RuntimeEnvironment.getApplication())
        val key = "package:example.reader"
        prefs.edit().putInt(key, 3).commit()
        val controller = Robolectric.buildActivity(SettingsActivity::class.java).setup()
        try {
            val fm = controller.get().supportFragmentManager
            val fragment = fm.findFragmentById(R.id.settings) as SettingsActivity.SettingsFragment
            val preference = PerAppRefreshPreference(controller.get()).apply {
                this.key = key
                entries = arrayOf("Default", "HD")
                entryValues = arrayOf("-1", "2")
            }
            fragment.preferenceScreen.addPreference(preference)
            fun open(): AlertDialog {
                fragment.onDisplayPreferenceDialog(preference)
                fm.executePendingTransactions()
                return fm.fragments.filterIsInstance<MaterialListPreferenceDialogFragment>()
                    .single().requireDialog() as AlertDialog
            }
            choose(open(), 1)
            fm.executePendingTransactions()
            assertEquals(2, prefs.getInt(key, -1))
            choose(open(), 0)
            fm.executePendingTransactions()
            assertFalse(prefs.contains(key))
        } finally {
            controller.pause().stop().destroy()
        }
    }

    private fun changeSlider(slider: Slider, value: Float) {
        assertTrue(slider.accessibilityNodeProvider.performAction(0,
            AccessibilityNodeInfo.AccessibilityAction.ACTION_SET_PROGRESS.id,
            Bundle().apply { putFloat(AccessibilityNodeInfo.ACTION_ARGUMENT_PROGRESS_VALUE, value) }))
    }

    private fun choose(dialog: AlertDialog, position: Int) {
        val list = dialog.listView
        list.performItemClick(list.adapter.getView(position, null, list), position, position.toLong())
        shadowOf(Looper.getMainLooper()).idle()
    }
}
