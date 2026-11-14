package com.lmqr.eink_settings.button_mapper

import android.content.Context
import android.content.Intent
import android.util.Log
import android.widget.Toast
import com.lmqr.eink_settings.R
import com.lmqr.eink_settings.ShortcutAssignment
import org.json.JSONException
import java.net.URISyntaxException

class LaunchShortcutButtonAction(private val actionKey: String) : ButtonAction {
    override fun execute(context: Context) {
        try {
            val target = ShortcutAssignment.read(context, actionKey)
            if (target == null) {
                Log.w(TAG, "No shortcut selected for $actionKey")
                Toast.makeText(context, R.string.choose_shortcut, Toast.LENGTH_LONG).show()
                return
            }
            if (ShortcutAssignment.isRemovedLauncherShortcut(target)) {
                Log.w(TAG, "Launcher shortcut is no longer supported for $actionKey")
                Toast.makeText(context, R.string.launcher_shortcut_removed, Toast.LENGTH_LONG).show()
                return
            }
            val intent = Intent.parseUri(target.getString("intent"), Intent.URI_INTENT_SCHEME)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            LaunchTarget.execute(context, TAG) { context.startActivity(intent) }
        } catch (e: JSONException) {
            LaunchTarget.report(context, TAG, e, R.string.unavailable_shortcut)
        } catch (e: URISyntaxException) {
            LaunchTarget.report(context, TAG, e, R.string.unavailable_shortcut)
        }
    }

    private companion object {
        const val TAG = "EinkLaunchShortcut"
    }
}
