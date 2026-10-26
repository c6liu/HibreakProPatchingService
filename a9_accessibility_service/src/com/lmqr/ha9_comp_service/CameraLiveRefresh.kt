package com.lmqr.ha9_comp_service

import android.content.Context
import android.hardware.camera2.CameraManager
import android.graphics.PixelFormat
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import androidx.preference.PreferenceManager

class CameraLiveRefresh(private val context: Context) : CameraManager.AvailabilityCallback(),
    Runnable {
    private val handler = Handler(Looper.getMainLooper())
    private val busyCameras = mutableSetOf<String>()
    private var overlay: View? = null
    private var alternate = false
    private var screenOn = true
    private var videoOptimized = false

    fun start() {
        try {
            cameraManager().registerAvailabilityCallback(this, handler)
        } catch (e: RuntimeException) {
            Log.e(TAG, "Unable to register camera availability callback", e)
        }
        update()
    }

    fun stop() {
        try {
            cameraManager().unregisterAvailabilityCallback(this)
        } catch (e: RuntimeException) {
            Log.e(TAG, "Unable to unregister camera availability callback", e)
        }
        busyCameras.clear()
        screenOn = false
        update()
    }

    fun setScreenOn(enabled: Boolean) {
        screenOn = enabled
        update()
    }

    fun setVideoOptimized(enabled: Boolean) {
        videoOptimized = enabled
        update()
    }

    override fun onCameraUnavailable(cameraId: String) {
        busyCameras.add(cameraId)
        update()
    }

    override fun onCameraAvailable(cameraId: String) {
        busyCameras.remove(cameraId)
        update()
    }

    private fun cameraManager() =
        context.getSystemService(Context.CAMERA_SERVICE) as CameraManager

    private fun windowManager() =
        context.getSystemService(Context.WINDOW_SERVICE) as WindowManager

    private fun update() {
        val cameraEnabled = PreferenceManager.getDefaultSharedPreferences(context)
            .getBoolean("camera_live_refresh", true)
        val shouldRefresh = screenOn &&
            ((busyCameras.isNotEmpty() && cameraEnabled) || videoOptimized)
        if (shouldRefresh && overlay == null) {
            val view = View(context).apply { setBackgroundColor(0x01000000) }
            val params = WindowManager.LayoutParams(
                1,
                1,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT,
            ).apply {
                gravity = Gravity.TOP or Gravity.START
            }
            try {
                windowManager().addView(view, params)
                overlay = view
                handler.post(this)
            } catch (e: WindowManager.BadTokenException) {
                Log.e(TAG, "Unable to add live refresh overlay", e)
            }
        } else if (!shouldRefresh) {
            overlay?.let {
                handler.removeCallbacks(this)
                overlay = null
                try {
                    windowManager().removeView(it)
                } catch (e: IllegalArgumentException) {
                    Log.e(TAG, "Live refresh overlay was not attached", e)
                }
            }
        }
    }

    override fun run() {
        val view = overlay ?: return
        if (!screenOn) {
            update()
            return
        }
        alternate = !alternate
        view.setBackgroundColor(if (alternate) 0x01000000 else 0x02000000)
        handler.postDelayed(this, FRAME_INTERVAL_MS)
    }

    private companion object {
        const val TAG = "CameraLiveRefresh"
        const val FRAME_INTERVAL_MS = 50L
    }
}
