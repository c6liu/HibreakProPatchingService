package com.lmqr.ha9_comp_service.button_mapper

import android.content.ActivityNotFoundException
import android.content.Context
import android.os.PowerManager
import android.util.Log
import android.widget.Toast
import com.lmqr.ha9_comp_service.R

internal object LaunchTarget {
    fun execute(context: Context, tag: String, launch: () -> Unit) {
        try {
            val powerManager = context.getSystemService(PowerManager::class.java)
            if (!powerManager.isInteractive) {
                // Target apps need not opt into Activity.setTurnScreenOn().
                @Suppress("DEPRECATION")
                val wakeLock = powerManager.newWakeLock(
                    PowerManager.SCREEN_BRIGHT_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP,
                    "A9:LaunchTarget",
                )
                wakeLock.acquire(3000)
            }
            launch()
        } catch (e: ActivityNotFoundException) {
            report(context, tag, e, R.string.unavailable_target)
        } catch (e: SecurityException) {
            report(context, tag, e, R.string.blocked_target)
        } catch (e: IllegalStateException) {
            report(context, tag, e, R.string.locked_target)
        }
    }

    fun report(context: Context, tag: String, error: Exception, message: Int) {
        Log.e(tag, context.getString(message), error)
        Toast.makeText(context, message, Toast.LENGTH_LONG).show()
    }
}
