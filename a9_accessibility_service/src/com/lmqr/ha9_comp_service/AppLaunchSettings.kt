package com.lmqr.ha9_comp_service

import android.content.Context
import android.content.Intent
import androidx.preference.ListPreference
import androidx.preference.Preference
import androidx.preference.PreferenceCategory
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
    private val actionLabels = listOf(
        "Top button, single press",
        "Top button, double press",
        "Top button, long press",
        "Top button, single press (screen off)",
        "Top button, double press (screen off)",
        "Top button, long press (screen off)",
        "Bottom button, single press",
        "Bottom button, double press",
        "Bottom button, long press",
        "Bottom button, single press (screen off)",
        "Bottom button, double press (screen off)",
        "Bottom button, long press (screen off)",
    )

    fun populate(fragment: PreferenceFragmentCompat) {
        val context = fragment.requireContext()
        val packageManager = context.packageManager
        val launchIntent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val apps = packageManager.queryIntentActivities(launchIntent, 0)
            .distinctBy { it.activityInfo.packageName }
            .map { it.activityInfo.packageName to it.loadLabel(packageManager) }

        val screen = requireNotNull(fragment.preferenceScreen)
        val category = PreferenceCategory(context).apply {
            title = "Apps to launch with side keys"
            isOrderingAsAdded = true
        }
        screen.addPreference(category)

        actionPreferenceKeys.forEachIndexed { index, actionKey ->
            val actionPreference = requireNotNull(fragment.findPreference<ListPreference>(actionKey))
            val launchActionValue = "launch_app_$actionKey"
            actionPreference.entries = requireNotNull(actionPreference.entries)
                .toList().plus("Launch App").toTypedArray()
            actionPreference.entryValues = requireNotNull(actionPreference.entryValues)
                .toList().plus(launchActionValue).toTypedArray()

            val appPreference = ListPreference(context).apply {
                key = "launch_app_package_$actionKey"
                title = "App to launch for ${actionLabels[index]}"
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
            category.addPreference(appPreference)
        }
    }
}
