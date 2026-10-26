package com.lmqr.ha9_comp_service

import android.content.Context
import androidx.preference.ListPreference

class PerAppRefreshPreference(context: Context) : ListPreference(context) {
    // The popup and RefreshModeManager store these keys as integers, not strings.
    override fun persistString(value: String): Boolean {
        if (value == "-1") {
            requireNotNull(sharedPreferences).edit().remove(key).apply()
            return true
        }
        return persistInt(value.toInt())
    }

    override fun getPersistedString(defaultReturnValue: String?): String =
        getPersistedInt(-1).toString()
}
