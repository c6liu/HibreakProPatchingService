package com.lmqr.ha9_comp_service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.PowerManager
import android.os.SystemClock
import android.util.Log
import android.view.KeyEvent

class ScreenOffKeyReceiver(private val service: A9AccessibilityService) : BroadcastReceiver() {
    private val owners = IntArray(2)
    private val screenOn = booleanArrayOf(true, true)

    init {
        service.registerReceiver(
            this,
            IntentFilter(ACTION),
            "android.permission.INJECT_EVENTS",
            null,
            Context.RECEIVER_EXPORTED,
        )
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ACTION) return
        val scanCode = intent.getIntExtra("scan_code", -1)
        val action = intent.getIntExtra("key_action", -1)
        val eventTime = intent.getLongExtra("event_time", -1)
        val age = SystemClock.uptimeMillis() - eventTime
        if (scanCode !in 59..60 || action !in 0..1 || eventTime < 0 || age !in 0..5000) {
            Log.w(TAG, "Invalid or stale daemon side-key event")
            return
        }
        dispatch(scanCode, action, eventTime, true)
    }

    fun onKeyEvent(event: KeyEvent): Boolean {
        if (event.scanCode !in 59..60) return false
        if (event.repeatCount == 0) {
            dispatch(event.scanCode, event.action, event.eventTime, false)
        }
        return true
    }

    private fun dispatch(scanCode: Int, action: Int, eventTime: Long, bridged: Boolean) {
        val index = scanCode - 59
        val owner = if (bridged) 2 else 1
        if (action == KeyEvent.ACTION_DOWN) {
            if (owners[index] != 0) return
            val interactive = service.getSystemService(PowerManager::class.java).isInteractive
            if (bridged == interactive) return
            owners[index] = owner
            screenOn[index] = interactive
        } else if (action != KeyEvent.ACTION_UP || owners[index] != owner) {
            return
        }
        service.dispatchSideKey(scanCode, action, eventTime)
        if (action == KeyEvent.ACTION_UP) owners[index] = 0
    }

    fun isScreenOn(scanCode: Int): Boolean = screenOn[scanCode - 59]

    fun close() {
        service.unregisterReceiver(this)
    }

    companion object {
        const val ACTION = "com.lmqr.ha9_comp_service.SCREEN_OFF_KEY"
        private const val TAG = "A9ScreenOffKey"
    }
}
