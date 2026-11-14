package com.lmqr.eink_settings.quick_settings

import android.content.SharedPreferences

fun SharedPreferences.toggle(key: String) =
    edit().putBoolean(key, !getBoolean(key, false)).apply()