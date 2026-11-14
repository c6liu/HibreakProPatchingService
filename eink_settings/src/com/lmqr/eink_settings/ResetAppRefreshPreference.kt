package com.lmqr.eink_settings

import com.google.android.material.dialog.MaterialAlertDialogBuilder
import android.content.Context
import android.util.AttributeSet
import androidx.core.content.edit
import androidx.preference.ListPreference
import androidx.preference.Preference
import androidx.preference.PreferenceCategory

class ResetAppRefreshPreference(context: Context, attrs: AttributeSet?) :
    Preference(context, attrs) {
    override fun onClick() {
        MaterialAlertDialogBuilder(context)
            .setTitle("Reset all to default?")
            .setMessage("Remove all saved per-app refresh modes? Apps will use Default Refresh Mode. Other settings will not change.")
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton("Reset") { _, _ ->
                val prefs = requireNotNull(sharedPreferences)
                prefs.edit {
                    prefs.all.keys.filter { it.startsWith("package:") && it != "package:None" }
                        .forEach { remove(it) }
                }
                val apps = requireNotNull(
                    preferenceManager.findPreference<PreferenceCategory>("per_app_apps"))
                for (index in 0 until apps.preferenceCount) {
                    (apps.getPreference(index) as ListPreference).value = "-1"
                }
            }
            .show()
    }
}
