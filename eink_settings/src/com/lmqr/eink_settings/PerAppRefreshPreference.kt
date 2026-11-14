package com.lmqr.eink_settings

import android.content.Context
import androidx.core.content.edit
import androidx.preference.ListPreference

class PerAppRefreshPreference(context: Context) : ListPreference(context) {
    // The popup and RefreshModeManager store these keys as integers, not strings.
    override fun persistString(value: String): Boolean {
        if (value == "-1") {
            requireNotNull(sharedPreferences).edit { remove(key) }
            return true
        }
        return persistInt(value.toInt())
    }

    override fun getPersistedString(defaultReturnValue: String?): String =
        getPersistedInt(-1).toString()
}
