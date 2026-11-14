package com.lmqr.eink_settings

import android.content.Context
import androidx.preference.PreferenceManager

object ButtonActionSettings {
    val actionKeys = listOf(
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

    fun migrateScreenOffClear(context: Context) {
        val preferences = PreferenceManager.getDefaultSharedPreferences(context)
        val editor = preferences.edit()
        actionKeys.filter { it.endsWith("_screen_off") }.forEach { key ->
            if (preferences.getString(key, null) == "clear") {
                editor.putString(key, "dummy")
            }
        }
        editor.apply()
    }
}
