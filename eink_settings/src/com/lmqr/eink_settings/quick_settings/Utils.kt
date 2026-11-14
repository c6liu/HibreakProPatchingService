package com.lmqr.eink_settings.quick_settings

import android.content.SharedPreferences
import androidx.core.content.edit

fun SharedPreferences.toggle(key: String) =
    edit { putBoolean(key, !getBoolean(key, false)) }