package com.lmqr.eink_settings

import android.app.Activity
import android.content.ComponentName
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.LauncherApps
import android.content.pm.ShortcutInfo
import android.net.Uri
import android.os.Looper
import android.os.PowerManager
import android.widget.ListView
import android.widget.TextView
import androidx.preference.ListPreference
import androidx.preference.Preference
import androidx.preference.PreferenceManager
import com.google.android.material.textfield.TextInputEditText
import com.lmqr.eink_settings.button_mapper.ButtonActionManager
import com.lmqr.eink_settings.button_mapper.LaunchAppButtonAction
import com.lmqr.eink_settings.button_mapper.LaunchShortcutButtonAction
import com.lmqr.eink_settings.command_runners.CommandRunner
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowPowerManager
import org.robolectric.shadows.ShadowToast

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35, 36, 37])
class ActionTargetsTest {
    private val context get() = RuntimeEnvironment.getApplication()
    private val preferences get() = PreferenceManager.getDefaultSharedPreferences(context)

    @Before
    fun resetPreferences() {
        preferences.edit().clear().commit()
    }

    @Test
    fun screenOffClearMigratesWithoutChangingOtherAssignments() {
        ButtonActionSettings.actionKeys.forEach { preferences.edit().putString(it, "clear").commit() }
        val preservedKey = "top_long_press_eink_action_screen_off"
        preferences.edit().putString(preservedKey, "next_track").commit()
        ButtonActionSettings.migrateScreenOffClear(context)
        ButtonActionSettings.migrateScreenOffClear(context)
        ButtonActionSettings.actionKeys.forEach { key ->
            assertEquals(when {
                key == preservedKey -> "next_track"
                key.endsWith("_screen_off") -> "dummy"
                else -> "clear"
            }, preferences.getString(key, null))
        }
    }

    @Test
    fun allGesturesHaveAppAndShortcutPickersWithoutChangingOnCancel() {
        val controller = Robolectric.buildActivity(SettingsActivity::class.java).setup()
        try {
            val activity = controller.get()
            val fragment = activity.supportFragmentManager.findFragmentById(R.id.settings)
                as SettingsActivity.SettingsFragment
            for (key in ButtonActionSettings.actionKeys) {
                val action = requireNotNull(fragment.findPreference<ListPreference>(key))
                val original = action.value
                assertTrue(action.entryValues.contains("launch_app_$key"))
                assertTrue(action.entryValues.contains("launch_shortcut_$key"))
                if (key.endsWith("_screen_off")) assertFalse(action.entryValues.contains("clear"))
                assertFalse(action.callChangeListener("launch_shortcut_$key"))
                val picker = shadowOf(activity).nextStartedActivity
                assertEquals(ActionTargetPickerActivity::class.java.name, picker.component?.className)
                assertEquals(key, picker.getStringExtra(ActionTargetPickerActivity.EXTRA_ACTION_KEY))
                assertTrue(picker.getBooleanExtra(ActionTargetPickerActivity.EXTRA_SHORTCUTS, false))
                assertEquals(original, action.value)
            }
            val key = ButtonActionSettings.actionKeys.first()
            ShortcutAssignment.saveLegacy(context, key, "Example shortcut", Intent(Intent.ACTION_VIEW))
            AppLaunchSettings.refresh(fragment)
            assertEquals("launch_shortcut_$key", fragment.findPreference<ListPreference>(key)?.value)
            assertEquals("Example shortcut", fragment.findPreference<Preference>("shortcut_target_$key")?.summary)
            assertTrue(requireNotNull(fragment.findPreference<Preference>("shortcut_target_$key")).isVisible)
        } finally {
            controller.pause().stop().destroy()
        }
    }

    @Test
    fun allTwelveGesturesDispatchTheirOwnShortcut() {
        val commands = mutableListOf<String>()
        val runner = object : CommandRunner {
            override fun runCommands(cmds: Array<String>) { commands.addAll(cmds) }
            override fun onDestroy() {}
        }
        val manager = ButtonActionManager(runner, RefreshModeManager(preferences, runner))
        commands.clear()
        val dispatches: List<(android.content.Context) -> Unit> = listOf(
            manager::executeSinglePressTop, manager::executeDoublePressTop, manager::executeLongPressTop,
            manager::executeSinglePressScreenOffTop, manager::executeDoublePressScreenOffTop,
            manager::executeLongPressScreenOffTop, manager::executeSinglePress, manager::executeDoublePress,
            manager::executeLongPress, manager::executeSinglePressScreenOff,
            manager::executeDoublePressScreenOff, manager::executeLongPressScreenOff,
        )
        ButtonActionSettings.actionKeys.forEachIndexed { index, key ->
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse("example://target/$index"))
                .putExtra("index", index)
            ShortcutAssignment.saveLegacy(context, key, "Shortcut $index", intent)
        }
        dispatches.forEachIndexed { index, dispatch ->
            dispatch(context)
            val launched = shadowOf(context).nextStartedActivity
            assertEquals("example://target/$index", launched.dataString)
            assertEquals(index, launched.getIntExtra("index", -1))
            assertTrue(launched.flags and Intent.FLAG_ACTIVITY_NEW_TASK != 0)
        }
        assertTrue(commands.isEmpty())
    }

    @Test
    fun staleScreenOffClearCannotDispatchRefresh() {
        val commands = mutableListOf<String>()
        val runner = object : CommandRunner {
            override fun runCommands(cmds: Array<String>) { commands.addAll(cmds) }
            override fun onDestroy() {}
        }
        val manager = ButtonActionManager(runner, RefreshModeManager(preferences, runner))
        commands.clear()
        preferences.edit().putString("single_press_eink_action_screen_off", "clear").commit()
        manager.executeSinglePressScreenOff(context)
        assertTrue(commands.isEmpty())
        assertEquals("dummy", preferences.getString("single_press_eink_action_screen_off", null))
    }

    @Test
    fun shortcutWakeLockIsBoundedAndScreenOnDoesNotAcquireOne() {
        val key = ButtonActionSettings.actionKeys.first()
        ShortcutAssignment.saveLegacy(context, key, "Example", Intent(Intent.ACTION_VIEW))
        val power = context.getSystemService(PowerManager::class.java)
        shadowOf(power).turnScreenOn(true)
        ShadowPowerManager.clearWakeLocks()
        LaunchShortcutButtonAction(key).execute(context)
        assertNull(ShadowPowerManager.getLatestWakeLock())
        shadowOf(power).turnScreenOn(false)
        LaunchShortcutButtonAction(key).execute(context)
        val wakeLock = requireNotNull(ShadowPowerManager.getLatestWakeLock())
        assertTrue(wakeLock.isHeld)
        shadowOf(Looper.getMainLooper()).idleFor(java.time.Duration.ofMillis(3001))
        assertFalse(wakeLock.isHeld)
    }

    @Test
    fun malformedShortcutReportsErrorInsteadOfLaunchingApp() {
        val key = ButtonActionSettings.actionKeys.first()
        for (value in listOf("{bad-json", """{"label":"Missing intent"}""")) {
            preferences.edit().putString(ShortcutAssignment.key(key), value).commit()
            assertEquals(context.getString(R.string.unavailable_shortcut), ShortcutAssignment.summary(context, key))
            LaunchShortcutButtonAction(key).execute(context)
            assertEquals(context.getString(R.string.unavailable_shortcut), ShadowToast.getTextOfLatestToast())
            assertNull(shadowOf(context).nextStartedActivity)
        }
    }

    @Test
    fun removedLauncherAssignmentsReportErrorAndCanBeReplaced() {
        val saved = """{"label":"Read example","package":"example.reader","id":"read"}"""
        val keys = listOf("top_single_press_eink_action", "long_press_eink_action_screen_off")
        for (key in keys) {
            preferences.edit()
                .putString(ShortcutAssignment.key(key), saved)
                .putString(key, "launch_shortcut_$key")
                .commit()
            assertEquals(context.getString(R.string.launcher_shortcut_removed),
                ShortcutAssignment.summary(context, key))
            LaunchShortcutButtonAction(key).execute(context)
            assertEquals(context.getString(R.string.launcher_shortcut_removed),
                ShadowToast.getTextOfLatestToast())
            assertNull(shadowOf(context).nextStartedActivity)
            assertEquals(saved, preferences.getString(ShortcutAssignment.key(key), null))
            assertEquals("launch_shortcut_$key", preferences.getString(key, null))
        }
        val controller = Robolectric.buildActivity(SettingsActivity::class.java).setup()
        try {
            val fragment = controller.get().supportFragmentManager.findFragmentById(R.id.settings)
                as SettingsActivity.SettingsFragment
            for (key in keys) {
                val target = requireNotNull(fragment.findPreference<Preference>("shortcut_target_$key"))
                assertTrue(target.isVisible)
                assertEquals(context.getString(R.string.launcher_shortcut_removed), target.summary)
            }
        } finally {
            controller.pause().stop().destroy()
        }
        val key = keys.last()
        ShortcutAssignment.saveLegacy(context, key, "Replacement", Intent(Intent.ACTION_VIEW))
        assertEquals("Replacement", ShortcutAssignment.summary(context, key))
        LaunchShortcutButtonAction(key).execute(context)
        assertEquals(Intent.ACTION_VIEW, shadowOf(context).nextStartedActivity.action)
    }

    @Test
    fun unsupportedShortcutExtrasDoNotOverwriteExistingAssignment() {
        val key = ButtonActionSettings.actionKeys.first()
        ShortcutAssignment.saveLegacy(context, key, "Original", Intent(Intent.ACTION_VIEW))
        val unsupported = Intent(Intent.ACTION_VIEW).putExtra("array", intArrayOf(1, 2))
        assertThrows(IllegalArgumentException::class.java) {
            ShortcutAssignment.saveLegacy(context, key, "Unsupported", unsupported)
        }
        assertEquals("Original", ShortcutAssignment.read(context, key)?.getString("label"))
    }

    @Test
    fun existingPackageAssignmentStillLaunchesTheApp() {
        val packageName = "example.reader"
        addActivity(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
            .setPackage(packageName), packageName, "Reader")
        val key = "launch_app_package_top_single_press_eink_action"
        preferences.edit().putString(key, packageName).commit()
        LaunchAppButtonAction(key).execute(context)
        assertEquals("$packageName.MainActivity", shadowOf(context).nextStartedActivity.component?.className)
        assertEquals(packageName, preferences.getString(key, null))
    }

    @Test
    fun materialPickerSearchesAppsAndSavesTheSelectedPackage() {
        addActivity(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER),
            "example.reader", "Reader")
        val key = ButtonActionSettings.actionKeys.first()
        val controller = Robolectric.buildActivity(ActionTargetPickerActivity::class.java, pickerIntent(key)).setup()
        try {
            val activity = controller.get()
            waitForTargets(activity)
            val search = activity.findViewById<TextInputEditText>(R.id.picker_search)
            val list = activity.findViewById<ListView>(R.id.picker_list)
            search.setText("EXAMPLE.READER")
            assertEquals(1, list.adapter.count)
            list.performItemClick(list.adapter.getView(0, null, list), 0, 0)
            assertEquals("example.reader", preferences.getString("launch_app_package_$key", null))
            assertEquals("launch_app_$key", preferences.getString(key, null))
            assertTrue(activity.isFinishing)
        } finally {
            controller.pause().stop().destroy()
        }
    }

    @Suppress("DEPRECATION")
    @Test
    fun legacyShortcutProviderResultSurvivesRecreation() {
        addActivity(Intent(Intent.ACTION_CREATE_SHORTCUT), "example.shortcuts", "Create example")
        val key = ButtonActionSettings.actionKeys.last()
        val controller = Robolectric.buildActivity(ActionTargetPickerActivity::class.java,
            pickerIntent(key).putExtra(ActionTargetPickerActivity.EXTRA_SHORTCUTS, true)).setup()
        try {
            var activity = controller.get()
            waitForTargets(activity)
            activity.findViewById<TextInputEditText>(R.id.picker_search).setText("example.shortcuts")
            val list = activity.findViewById<ListView>(R.id.picker_list)
            assertEquals(1, list.adapter.count)
            list.performItemClick(list.adapter.getView(0, null, list), 0, 0)
            val requested = shadowOf(activity).nextStartedActivityForResult
            assertEquals(Intent.ACTION_CREATE_SHORTCUT, requested.intent.action)
            controller.recreate()
            activity = controller.get()
            shadowOf(activity).callOnActivityResult(requested.requestCode, Activity.RESULT_OK,
                Intent().putExtra(Intent.EXTRA_SHORTCUT_NAME, "Configured example")
                    .putExtra(Intent.EXTRA_SHORTCUT_INTENT, Intent(Intent.ACTION_VIEW, Uri.parse("example://deep"))))
            assertEquals("Configured example", ShortcutAssignment.read(context, key)?.getString("label"))
            assertEquals("launch_shortcut_$key", preferences.getString(key, null))
        } finally {
            controller.pause().stop().destroy()
        }
    }

    @Suppress("DEPRECATION")
    @Test
    fun cancellingOrInvalidProviderResultsKeepThePreviousAssignment() {
        addActivity(Intent(Intent.ACTION_CREATE_SHORTCUT), "example.shortcuts", "Create example")
        val key = ButtonActionSettings.actionKeys.last()
        ShortcutAssignment.saveLegacy(context, key, "Original", Intent(Intent.ACTION_VIEW))
        val controller = Robolectric.buildActivity(ActionTargetPickerActivity::class.java,
            pickerIntent(key).putExtra(ActionTargetPickerActivity.EXTRA_SHORTCUTS, true)).setup()
        try {
            val activity = controller.get()
            waitForTargets(activity)
            activity.findViewById<TextInputEditText>(R.id.picker_search).setText("example.shortcuts")
            val list = activity.findViewById<ListView>(R.id.picker_list)
            for ((code, result) in listOf(
                Activity.RESULT_CANCELED to Intent(),
                Activity.RESULT_OK to Intent(),
                Activity.RESULT_OK to Intent()
                    .putExtra(Intent.EXTRA_SHORTCUT_NAME, "Unsupported")
                    .putExtra(Intent.EXTRA_SHORTCUT_INTENT,
                        Intent(Intent.ACTION_VIEW).putExtra("array", intArrayOf(1, 2))),
            )) {
                list.performItemClick(list.adapter.getView(0, null, list), 0, 0)
                val request = shadowOf(activity).nextStartedActivityForResult
                shadowOf(activity).callOnActivityResult(request.requestCode, code, result)
                assertFalse(activity.isFinishing)
                assertEquals("Original", ShortcutAssignment.read(context, key)?.getString("label"))
            }
        } finally {
            controller.pause().stop().destroy()
        }
    }

    @Suppress("DEPRECATION")
    @Test
    fun pickerListsOnlyAppProvidersEvenWithShortcutHostPermission() {
        val launcher = context.getSystemService(LauncherApps::class.java)
        val shadow = shadowOf(launcher)
        shadow.setHasShortcutHostPermission(true)
        val shortcut = ShortcutInfo.Builder(context, "read")
            .setShortLabel("Read example")
            .setIntent(Intent(Intent.ACTION_VIEW, Uri.parse("example://read")))
            .build()
        shadow.addDynamicShortcut(shortcut)
        addActivity(Intent(Intent.ACTION_CREATE_SHORTCUT), "example.shortcuts", "Create example")
        val key = ButtonActionSettings.actionKeys.first()
        val controller = Robolectric.buildActivity(ActionTargetPickerActivity::class.java,
            pickerIntent(key).putExtra(ActionTargetPickerActivity.EXTRA_SHORTCUTS, true)).setup()
        try {
            val activity = controller.get()
            waitForTargets(activity, expectedCount = 1)
            assertEquals(context.getString(R.string.shortcut_picker_help),
                activity.findViewById<TextView>(R.id.picker_notice).text)
            val search = activity.findViewById<TextInputEditText>(R.id.picker_search)
            val list = activity.findViewById<ListView>(R.id.picker_list)
            search.setText("Read example")
            assertEquals(0, list.adapter.count)
            search.setText("example.shortcuts")
            assertEquals(1, list.adapter.count)
            list.performItemClick(list.adapter.getView(0, null, list), 0, 0)
            assertEquals(Intent.ACTION_CREATE_SHORTCUT,
                shadowOf(activity).nextStartedActivityForResult.intent.action)
        } finally {
            controller.pause().stop().destroy()
        }
    }

    @Test
    fun shortcutPickerExplainsWhenNoProvidersAreAvailable() {
        val controller = Robolectric.buildActivity(ActionTargetPickerActivity::class.java,
            pickerIntent(ButtonActionSettings.actionKeys.first())
                .putExtra(ActionTargetPickerActivity.EXTRA_SHORTCUTS, true)).setup()
        try {
            val activity = controller.get()
            waitForTargets(activity)
            assertEquals(0, activity.findViewById<ListView>(R.id.picker_list).adapter.count)
            assertEquals(context.getString(R.string.no_shortcuts),
                activity.findViewById<TextView>(R.id.picker_empty).text)
            assertEquals(context.getString(R.string.shortcut_picker_help),
                activity.findViewById<TextView>(R.id.picker_notice).text)
        } finally {
            controller.pause().stop().destroy()
        }
    }

    private fun pickerIntent(key: String) = Intent(context, ActionTargetPickerActivity::class.java)
        .putExtra(ActionTargetPickerActivity.EXTRA_ACTION_KEY, key)

    private fun addActivity(intent: Intent, packageName: String, label: String) {
        val shadow = shadowOf(context.packageManager)
        val component = ComponentName(packageName, "$packageName.MainActivity")
        shadow.addActivityIfNotPresent(component).apply {
            nonLocalizedLabel = label
            exported = true
            enabled = true
            applicationInfo.apply {
                nonLocalizedLabel = label
                enabled = true
            }
        }
        shadow.addIntentFilterForActivity(component, IntentFilter().apply {
            addAction(requireNotNull(intent.action))
            intent.categories?.forEach { addCategory(it) }
        })
    }

    private fun waitForTargets(activity: Activity, expectedCount: Int? = null) {
        val deadline = System.nanoTime() + java.util.concurrent.TimeUnit.SECONDS.toNanos(5)
        do {
            shadowOf(Looper.getMainLooper()).idle()
            val loading = activity.findViewById<TextView>(R.id.picker_empty).text ==
                context.getString(R.string.loading_targets)
            val count = activity.findViewById<ListView>(R.id.picker_list).adapter.count
            if (!loading && (expectedCount == null || count == expectedCount)) return
            Thread.sleep(10)
        } while (System.nanoTime() < deadline)
        fail("Picker did not finish loading")
    }

}
