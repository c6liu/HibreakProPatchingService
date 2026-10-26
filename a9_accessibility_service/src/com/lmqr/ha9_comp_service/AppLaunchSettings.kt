package com.lmqr.ha9_comp_service

import android.content.Intent
import androidx.preference.ListPreference
import androidx.preference.Preference
import androidx.preference.PreferenceFragmentCompat

object AppLaunchSettings {
    private val actionPreferenceKeys = listOf(
        "top_single_press_eink_action",
        "top_double_press_eink_action",
        "top_long_press_eink_action",
        "top_single_press_eink_action_screen_off",
        "top_double_press_eink_action_screen_off",
        "top_long_press_eink_action_screen_off",
        "single_press_eink_action",
        "double_press_eink_action",
        "long_press_eink_action",
        "single_press_eink_action_screen_off",
        "double_press_eink_action_screen_off",
        "long_press_eink_action_screen_off",
    )

    fun populate(fragment: PreferenceFragmentCompat) {
        val context = fragment.requireContext()
        val packageManager = context.packageManager
        val launchIntent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val apps = packageManager.queryIntentActivities(launchIntent, 0)
            .distinctBy { it.activityInfo.packageName }
            .map { it.activityInfo.packageName to it.loadLabel(packageManager) }

        actionPreferenceKeys.forEachIndexed { index, actionKey ->
            val actionPreference = requireNotNull(fragment.findPreference<ListPreference>(actionKey))
            val launchActionValue = "launch_app_$actionKey"
            val entries = requireNotNull(actionPreference.entries).toList()
            val values = requireNotNull(actionPreference.entryValues).toList()
            check(values.last().toString() == "dummy")
            actionPreference.entries = (entries.dropLast(1) + "Launch App" + entries.last()).toTypedArray()
            actionPreference.entryValues = (values.dropLast(1) + launchActionValue + values.last()).toTypedArray()
            actionPreference.order = (index % 6) * 2
            actionPreference.summaryProvider = ListPreference.SimpleSummaryProvider.getInstance()

            val appPreference = ListPreference(context).apply {
                key = "launch_app_package_$actionKey"
                title = "App to launch"
                order = actionPreference.order + 1
                dialogTitle = "Choose an app to launch"
                entries = if (apps.isEmpty()) {
                    arrayOf("No launchable apps found")
                } else {
                    apps.map { it.second }.toTypedArray()
                }
                entryValues = if (apps.isEmpty()) {
                    arrayOf("")
                } else {
                    apps.map { it.first }.toTypedArray()
                }
                setDefaultValue("")
                isEnabled = apps.isNotEmpty()
                summaryProvider = Preference.SummaryProvider<ListPreference> { preference ->
                    preference.entry ?: "Choose an app to launch"
                }
            }
            requireNotNull(actionPreference.parent).addPreference(appPreference)
            appPreference.isVisible = actionPreference.value == launchActionValue
            actionPreference.setOnPreferenceChangeListener { _, newValue ->
                appPreference.isVisible = newValue == launchActionValue
                true
            }
        }
    }
}
