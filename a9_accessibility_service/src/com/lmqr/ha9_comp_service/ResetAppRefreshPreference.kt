package com.lmqr.ha9_comp_service

import android.app.AlertDialog
import android.content.Context
import android.util.AttributeSet
import androidx.preference.ListPreference
import androidx.preference.Preference
import androidx.preference.PreferenceCategory

class ResetAppRefreshPreference(context: Context, attrs: AttributeSet?) :
    Preference(context, attrs) {
    override fun onClick() {
        AlertDialog.Builder(context)
            .setTitle("Reset all to default?")
            .setMessage("Remove all saved per-app refresh modes? Apps will use Default Refresh Mode. Other settings will not change.")
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton("Reset") { _, _ ->
                val prefs = requireNotNull(sharedPreferences)
                val editor = prefs.edit()
                prefs.all.keys.filter { it.startsWith("package:") && it != "package:None" }
                    .forEach { editor.remove(it) }
                editor.apply()
                val apps = requireNotNull(
                    preferenceManager.findPreference<PreferenceCategory>("per_app_apps"))
                for (index in 0 until apps.preferenceCount) {
                    (apps.getPreference(index) as ListPreference).value = "-1"
                }
            }
            .show()
    }
}
