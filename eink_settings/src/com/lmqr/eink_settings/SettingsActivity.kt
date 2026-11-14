package com.lmqr.eink_settings

import android.accessibilityservice.AccessibilityServiceInfo
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Bundle
import android.provider.Settings
import android.view.accessibility.AccessibilityManager
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.Toolbar
import androidx.preference.ListPreference
import androidx.preference.Preference
import androidx.preference.PreferenceCategory
import androidx.preference.PreferenceFragmentCompat


class SettingsActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        theme.applyStyle(
            com.google.android.material.R.style.ThemeOverlay_Material3_DynamicColors_DayNight,
            true,
        )
        super.onCreate(savedInstanceState)
        setContentView(R.layout.settings_activity)
        val toolbar = findViewById<Toolbar>(R.id.settings_toolbar)
        if (intent.getBooleanExtra("per_app_page", false)) {
            toolbar.title = "Per-App Refresh Modes"
        }
        toolbar.setNavigationOnClickListener {
            finish()
        }
        if (savedInstanceState == null) {
            supportFragmentManager
                .beginTransaction()
                .replace(R.id.settings, SettingsFragment())
                .commit()
        }
        checkPermissions()
    }

    class SettingsFragment : PreferenceFragmentCompat() {
        @Suppress("DEPRECATION")
        override fun onDisplayPreferenceDialog(preference: Preference) {
            if (preference !is ListPreference) {
                super.onDisplayPreferenceDialog(preference)
                return
            }
            val tag = "androidx.preference.PreferenceFragment.DIALOG"
            if (parentFragmentManager.findFragmentByTag(tag) != null) return
            MaterialListPreferenceDialogFragment().apply {
                arguments = Bundle().apply { putString("key", preference.key) }
                // AndroidX resolves the preference through its target fragment after recreation.
                setTargetFragment(this@SettingsFragment, 0)
            }.show(parentFragmentManager, tag)
        }

        override fun onCreatePreferences(savedInstanceState: Bundle?, rootKey: String?) {
            ButtonActionSettings.migrateScreenOffClear(requireContext())
            setPreferencesFromResource(R.xml.root_preferences, rootKey)
            if (!requireActivity().intent.getBooleanExtra("per_app_page", false)) {
                AppLaunchSettings.populate(this)
                val preset = requireNotNull(findPreference<ListPreference>("accent_color_preset"))
                val custom = requireNotNull(findPreference<Preference>("accent_custom_gray"))
                custom.isVisible = preset.value == "custom"
                preset.setOnPreferenceChangeListener { _, value ->
                    custom.isVisible = value == "custom"
                    true
                }
                return
            }

            setPreferencesFromResource(R.xml.per_app_preferences, null)
            val apps = requireNotNull(findPreference<PreferenceCategory>("per_app_apps"))
            apps.isOrderingAsAdded = false
            val context = apps.context
            val pm = context.packageManager
            val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
            pm.queryIntentActivities(launcher, 0)
                .distinctBy { it.activityInfo.packageName }
                .forEach { app ->
                    apps.addPreference(PerAppRefreshPreference(context).apply {
                        key = "package:${app.activityInfo.packageName}"
                        title = app.loadLabel(pm)
                        entries = arrayOf<CharSequence>("Use default") +
                            resources.getTextArray(R.array.refresh_options)
                        entryValues = arrayOf<CharSequence>("-1") +
                            resources.getTextArray(R.array.refresh_values)
                        summaryProvider = ListPreference.SimpleSummaryProvider.getInstance()
                        setDefaultValue("-1")
                    })
                }
        }

        override fun onResume() {
            super.onResume()
            if (!requireActivity().intent.getBooleanExtra("per_app_page", false)) {
                AppLaunchSettings.refresh(this)
            }
        }
    }

    private fun checkPermissions(){
        if(!isAccessibilityServiceEnabled()) {
            val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_HISTORY)
            try {
                startActivity(intent)
            } catch (e: ActivityNotFoundException) {
                e.printStackTrace()
            }
        }
    }

    private fun isAccessibilityServiceEnabled(): Boolean {
        val am = getSystemService(ACCESSIBILITY_SERVICE) as AccessibilityManager
        val enabledServices =
            am.getEnabledAccessibilityServiceList(AccessibilityServiceInfo.FEEDBACK_ALL_MASK)
        for (enabledService in enabledServices) {
            val enabledServiceInfo: ServiceInfo = enabledService.resolveInfo.serviceInfo
            if (enabledServiceInfo.packageName.equals(packageName))
                return true
        }
        return false
    }
}