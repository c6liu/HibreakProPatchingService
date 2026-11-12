package com.lmqr.ha9_comp_service.button_mapper

import android.content.Context
import android.content.Intent
import android.content.pm.LauncherApps
import android.os.Process
import android.util.Log
import android.widget.Toast
import com.lmqr.ha9_comp_service.R
import com.lmqr.ha9_comp_service.ShortcutAssignment
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
            if (target.has("intent")) {
                val intent = Intent.parseUri(target.getString("intent"), Intent.URI_INTENT_SCHEME)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                LaunchTarget.execute(context, TAG) { context.startActivity(intent) }
            } else {
                val packageName = target.getString("package")
                val id = target.getString("id")
                LaunchTarget.execute(context, TAG) {
                    context.getSystemService(LauncherApps::class.java)
                        .startShortcut(packageName, id, null, null, Process.myUserHandle())
                }
            }
        } catch (e: JSONException) {
            LaunchTarget.report(context, TAG, e, R.string.unavailable_shortcut)
        } catch (e: URISyntaxException) {
            LaunchTarget.report(context, TAG, e, R.string.unavailable_shortcut)
        }
    }

    private companion object {
        const val TAG = "A9LaunchShortcut"
    }
}
