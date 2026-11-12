package com.lmqr.ha9_comp_service

import android.content.Context
import android.content.Intent
import android.content.pm.ShortcutInfo
import android.util.Log
import androidx.preference.PreferenceManager
import org.json.JSONException
import org.json.JSONObject

object ShortcutAssignment {
    fun key(actionKey: String) = "shortcut_target_$actionKey"

    fun saveLegacy(context: Context, actionKey: String, label: String, intent: Intent) {
        requireUriCompatible(intent)
        save(context, actionKey, JSONObject()
            .put("label", label)
            .put("intent", intent.toUri(Intent.URI_INTENT_SCHEME)))
    }

    @Suppress("DEPRECATION")
    private fun requireUriCompatible(intent: Intent) {
        require(intent.clipData == null) { "Shortcut requires transient clip data" }
        intent.extras?.let { extras ->
            require(extras.keySet().all { key ->
                when (extras.get(key)) {
                    null, is String, is Boolean, is Byte, is Char, is Double,
                    is Float, is Int, is Long, is Short -> true
                    else -> false
                }
            }) { "Shortcut has extras that Intent.toUri cannot preserve" }
        }
        intent.selector?.let { requireUriCompatible(it) }
    }

    fun saveModern(context: Context, actionKey: String, shortcut: ShortcutInfo) {
        save(context, actionKey, JSONObject()
            .put("label", shortcut.shortLabel?.toString() ?: shortcut.id)
            .put("package", shortcut.`package`)
            .put("id", shortcut.id))
    }

    private fun save(context: Context, actionKey: String, value: JSONObject) {
        require(actionKey in ButtonActionSettings.actionKeys)
        PreferenceManager.getDefaultSharedPreferences(context).edit()
            .putString(key(actionKey), value.toString())
            .putString(actionKey, "launch_shortcut_$actionKey")
            .apply()
    }

    fun read(context: Context, actionKey: String): JSONObject? =
        PreferenceManager.getDefaultSharedPreferences(context).getString(key(actionKey), null)
            ?.let { JSONObject(it) }

    fun summary(context: Context, actionKey: String): String = try {
        read(context, actionKey)?.getString("label") ?: context.getString(R.string.choose_shortcut)
    } catch (e: JSONException) {
        Log.e("A9ShortcutAssignment", "Invalid shortcut for $actionKey", e)
        context.getString(R.string.unavailable_shortcut)
    }
}
