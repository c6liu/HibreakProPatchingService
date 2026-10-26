package com.lmqr.ha9_comp_service

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
import androidx.preference.PreferenceCategory
import androidx.preference.PreferenceFragmentCompat


class SettingsActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.settings_activity)
        findViewById<Toolbar>(R.id.settings_toolbar).setNavigationOnClickListener {
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
        override fun onCreatePreferences(savedInstanceState: Bundle?, rootKey: String?) {
            setPreferencesFromResource(R.xml.root_preferences, rootKey)
            val apps = requireNotNull(findPreference<PreferenceCategory>("per_app_refresh_modes"))
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
                        entries = arrayOf("Use default") + resources.getTextArray(R.array.refresh_options)
                        entryValues = arrayOf("-1") + resources.getTextArray(R.array.refresh_values)
                        summaryProvider = ListPreference.SimpleSummaryProvider.getInstance()
                        setDefaultValue("-1")
                    })
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