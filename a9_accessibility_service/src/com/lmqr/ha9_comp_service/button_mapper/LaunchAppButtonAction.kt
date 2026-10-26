package com.lmqr.ha9_comp_service.button_mapper

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.util.Log
import android.widget.Toast
import androidx.preference.PreferenceManager

class LaunchAppButtonAction(private val packagePreferenceKey: String) : ButtonAction {
    override fun execute(context: Context) {
        val packageName = PreferenceManager.getDefaultSharedPreferences(context)
            .getString(packagePreferenceKey, null)
        if (packageName.isNullOrBlank()) {
            Log.w(TAG, "No app selected for side-key action $packagePreferenceKey")
            Toast.makeText(context, "Choose an app to launch in E-Ink Settings", Toast.LENGTH_SHORT)
                .show()
            return
        }

        val launchIntent = context.packageManager.getLaunchIntentForPackage(packageName)
        if (launchIntent == null) {
            Log.w(TAG, "No launcher activity found for $packageName")
            Toast.makeText(context, "The selected app cannot be launched", Toast.LENGTH_SHORT).show()
            return
        }

        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED)
        try {
            context.startActivity(launchIntent)
        } catch (e: ActivityNotFoundException) {
            Log.e(TAG, "Unable to launch $packageName", e)
            Toast.makeText(context, "Unable to launch the selected app", Toast.LENGTH_SHORT).show()
        } catch (e: SecurityException) {
            Log.e(TAG, "Permission denied while launching $packageName", e)
            Toast.makeText(context, "Android blocked launching the selected app", Toast.LENGTH_SHORT).show()
        }
    }

    private companion object {
        const val TAG = "A9LaunchAppAction"
    }
}
