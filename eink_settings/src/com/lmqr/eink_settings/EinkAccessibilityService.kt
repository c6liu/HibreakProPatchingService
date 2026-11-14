package com.lmqr.eink_settings

import android.accessibilityservice.AccessibilityService
import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.PixelFormat
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log
import android.view.Gravity
import android.view.KeyEvent
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.view.WindowInsets
import android.view.ContextThemeWrapper
import android.view.accessibility.AccessibilityEvent
import android.widget.Button
import android.widget.CompoundButton
import android.widget.TextView
import androidx.core.net.toUri
import androidx.core.view.isVisible
import androidx.preference.PreferenceManager
import com.lmqr.eink_settings.button_mapper.ButtonActionManager
import com.lmqr.eink_settings.command_runners.CommandRunner
import com.lmqr.eink_settings.command_runners.Commands
import com.lmqr.eink_settings.command_runners.UnixSocketCommandRunner
import kotlin.math.max


class EinkAccessibilityService : AccessibilityService(),
    SharedPreferences.OnSharedPreferenceChangeListener {
    private lateinit var commandRunner: CommandRunner
    private lateinit var refreshModeManager: RefreshModeManager
    private lateinit var sharedPreferences: SharedPreferences
    private lateinit var buttonActionManager: ButtonActionManager
    private lateinit var screenOffKeyReceiver: ScreenOffKeyReceiver
    private lateinit var brightnessManager: BrightnessManager
    private lateinit var displaySettingsManager: DisplaySettingsManager
    private var cameraLiveRefresh: CameraLiveRefresh? = null

    private var isScreenOn = true

    private val receiver: BroadcastReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            when (intent.action) {
                Intent.ACTION_BOOT_COMPLETED -> brightnessManager.reapplyBrightness()
                Intent.ACTION_SCREEN_OFF -> {
                    isScreenOn = false
                    cameraLiveRefresh?.setScreenOn(false)
                    menuBinding.close()
                    if (sharedPreferences.getBoolean("refresh_on_lock", false))
                        handler.postDelayed({
                            commandRunner.runCommands(arrayOf(Commands.SPEED_CLEAR))
                        }, 150)
                    brightnessManager.onScreenStateChanged(false)
                }
                Intent.ACTION_SCREEN_ON -> {
                    isScreenOn = true
                    cameraLiveRefresh?.setScreenOn(true)
                    if (sharedPreferences.getBoolean("refresh_on_lock", false))
                        refreshModeManager.applyMode()
                    brightnessManager.onScreenStateChanged(true)
                }
            }
        }
    }
    private val receiverEink: BroadcastReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            if(!sharedPreferences.getBoolean("allow_custom_broadcast", false))
                return

            when (intent.action) {
                "EINK_FORCE_CLEAR" -> {
                    commandRunner.runCommands(arrayOf(Commands.FORCE_CLEAR))
                }

                "EINK_REFRESH_SPEED_CLEAR" -> {
                    refreshModeManager.changeMode(RefreshMode.CLEAR)
                }

                "EINK_REFRESH_SPEED_BALANCED" -> {
                    refreshModeManager.changeMode(RefreshMode.BALANCED)
                }

                "EINK_REFRESH_SPEED_SMOOTH" -> {
                    refreshModeManager.changeMode(RefreshMode.SMOOTH)
                }

                "EINK_REFRESH_SPEED_FAST" -> {
                    refreshModeManager.changeMode(RefreshMode.SPEED)
                }
                "EINK_REFRESH_SPEED_HYPER" -> {
                    refreshModeManager.changeMode(RefreshMode.HYPER)
                }
            }
        }
    }

    private val handler = Handler(Looper.getMainLooper())

    override fun onCreate() {
        super.onCreate()
        commandRunner =
            UnixSocketCommandRunner()
        sharedPreferences = PreferenceManager.getDefaultSharedPreferences(this)
        ButtonActionSettings.migrateScreenOffClear(this)
        sharedPreferences.registerOnSharedPreferenceChangeListener(this)
        refreshModeManager = RefreshModeManager(
            sharedPreferences,
            commandRunner
        )
        buttonActionManager = ButtonActionManager(commandRunner, refreshModeManager)
        brightnessManager = BrightnessManager(
            sharedPreferences,
            commandRunner,
            DisplayBrightnessSource(this, handler),
        )
        displaySettingsManager = DisplaySettingsManager(sharedPreferences, commandRunner)
        displaySettingsManager.attach(this)

        val filterScreen = IntentFilter()
        filterScreen.addAction(Intent.ACTION_SCREEN_ON)
        filterScreen.addAction(Intent.ACTION_SCREEN_OFF)
        filterScreen.addAction(Intent.ACTION_BOOT_COMPLETED)
        registerReceiver(receiver, filterScreen)

        val filterEink = IntentFilter()
        filterEink.addAction("EINK_FORCE_CLEAR")
        filterEink.addAction("EINK_REFRESH_SPEED_CLEAR")
        filterEink.addAction("EINK_REFRESH_SPEED_BALANCED")
        filterEink.addAction("EINK_REFRESH_SPEED_SMOOTH")
        filterEink.addAction("EINK_REFRESH_SPEED_FAST")
        filterEink.addAction("EINK_REFRESH_SPEED_HYPER")
        registerReceiver(receiverEink, filterEink, RECEIVER_EXPORTED)
        screenOffKeyReceiver = ScreenOffKeyReceiver(this)
    }

    override fun onInterrupt() {

    }

    private val hardwareGestureDetector = HardwareGestureDetector(
        object: HardwareGestureDetector.OnGestureListener{
            override fun onSinglePress() {
                if(screenOffKeyReceiver.isScreenOn(59))
                    buttonActionManager.executeSinglePress(this@EinkAccessibilityService)
                else
                    buttonActionManager.executeSinglePressScreenOff(this@EinkAccessibilityService)
            }

            override fun onDoublePress() {
                if(screenOffKeyReceiver.isScreenOn(59))
                    buttonActionManager.executeDoublePress(this@EinkAccessibilityService)
                else
                    buttonActionManager.executeDoublePressScreenOff(this@EinkAccessibilityService)
            }

            override fun onLongPress() {
                if(screenOffKeyReceiver.isScreenOn(59))
                    buttonActionManager.executeLongPress(this@EinkAccessibilityService)
                else
                    buttonActionManager.executeLongPressScreenOff(this@EinkAccessibilityService)
            }
        }
    )

    private val hardwareGestureDetectorTop = HardwareGestureDetector(
        object: HardwareGestureDetector.OnGestureListener{
            override fun onSinglePress() {
                if(screenOffKeyReceiver.isScreenOn(60))
                    buttonActionManager.executeSinglePressTop(this@EinkAccessibilityService)
                else
                    buttonActionManager.executeSinglePressScreenOffTop(this@EinkAccessibilityService)
            }

            override fun onDoublePress() {
                if(screenOffKeyReceiver.isScreenOn(60))
                    buttonActionManager.executeDoublePressTop(this@EinkAccessibilityService)
                else
                    buttonActionManager.executeDoublePressScreenOffTop(this@EinkAccessibilityService)
            }

            override fun onLongPress() {
                if(screenOffKeyReceiver.isScreenOn(60))
                    buttonActionManager.executeLongPressTop(this@EinkAccessibilityService)
                else
                    buttonActionManager.executeLongPressScreenOffTop(this@EinkAccessibilityService)
            }
        }
    )

    override fun onKeyEvent(event: KeyEvent): Boolean {
        if (screenOffKeyReceiver.onKeyEvent(event)) return true
        return super.onKeyEvent(event)
    }

    fun dispatchSideKey(scanCode: Int, action: Int, eventTime: Long) {
        if (!Settings.canDrawOverlays(baseContext)) {
            requestOverlayPermission()
            return
        }
        val detector = if (scanCode == 59) hardwareGestureDetector else hardwareGestureDetectorTop
        detector.onKeyEvent(action, eventTime)
    }

    fun isSideKeyScreenOn(scanCode: Int): Boolean = screenOffKeyReceiver.isScreenOn(scanCode)

    private fun requestOverlayPermission() {
        val intent = Intent(
            Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
            "package:$packageName".toUri()
        )
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        try {
            startActivity(intent)
        } catch (e: ActivityNotFoundException) {
            Log.e("OverlayPermission", "Activity not found exception", e)
        }
    }

    private fun menuWidth(wm: WindowManager): Int {
        val metrics = wm.currentWindowMetrics
        val insets = metrics.windowInsets.getInsetsIgnoringVisibility(
            WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout())
        return minOf(metrics.bounds.width() - insets.left - insets.right,
            resources.getDimensionPixelSize(R.dimen.floating_menu_max_width))
    }

    private var menuBinding: FloatingMenuViewAccessor? = null

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        updateMenuLayout()
    }

    private fun updateMenuLayout() {
        val root = menuBinding?.root ?: return
        val wm = getSystemService(WindowManager::class.java)
        val params = root.layoutParams as WindowManager.LayoutParams
        params.width = menuWidth(wm)
        wm.updateViewLayout(root, params)
    }

    @SuppressLint("ClickableViewAccessibility", "InflateParams")
    fun openFloatingMenu() {
        try {
            menuBinding?.run {
                if (root.isVisible) {
                    root.visibility = View.GONE
                } else {
                    updateMenuLayout()
                    root.visibility = View.VISIBLE
                    updateButtons(refreshModeManager.currentMode)
                    updateLightControls()
                }
            } ?: run {

                val wm = getSystemService(WINDOW_SERVICE) as WindowManager
                val menuContext = ContextThemeWrapper(this, R.style.Theme_EinkSettings)
                menuContext.theme.applyStyle(
                    com.google.android.material.R.style.ThemeOverlay_Material3_DynamicColors_DayNight,
                    true,
                )
                val inflater = LayoutInflater.from(menuContext)
                val view = inflater.inflate(R.layout.floating_menu_layout, null, false)

                val layoutParams = WindowManager.LayoutParams().apply {
                    type = WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY
                    format = PixelFormat.TRANSLUCENT
                    flags =
                        flags or WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH
                    width = menuWidth(wm)
                    height = WindowManager.LayoutParams.WRAP_CONTENT
                    gravity = Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL
                    fitInsetsTypes = WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout()
                    isFitInsetsIgnoringVisibility = true
                }

                menuBinding = FloatingMenuViewAccessor(view).apply {
                    root.setOnTouchListener { v: View, event: MotionEvent ->
                        if (event.action == MotionEvent.ACTION_OUTSIDE)
                            close()
                        false
                    }
                    button1.setOnClickListener {
                        refreshModeManager.changeMode(RefreshMode.SMOOTH)
                        updateButtons(refreshModeManager.currentMode)
                    }
                    button2.setOnClickListener {
                        refreshModeManager.changeMode(RefreshMode.CLEAR)
                        updateButtons(refreshModeManager.currentMode)
                    }
                    button3.setOnClickListener {
                        refreshModeManager.changeMode(RefreshMode.BALANCED)
                        updateButtons(refreshModeManager.currentMode)
                    }
                    button4.setOnClickListener {
                        refreshModeManager.changeMode(RefreshMode.SPEED)
                        updateButtons(refreshModeManager.currentMode)
                    }
                    button5.setOnClickListener {
                        refreshModeManager.changeMode(RefreshMode.HYPER)
                        updateButtons(refreshModeManager.currentMode)
                    }

                    displaySettingsManager.setupSwitches(autoRefresh, antiShake)
                    displaySettingsManager.setupVideo(videoOptimizedRefresh)


                    settingsIcon.setOnClickListener {
                        val settingsIntent = Intent(
                            this@EinkAccessibilityService,
                            SettingsActivity::class.java
                        )
                        settingsIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        close()
                        startActivity(settingsIntent)
                    }


                    brightnessManager.setupSliders(this)
                    updateLightControls()
                    updateButtons(refreshModeManager.currentMode)

                    wm.addView(root, layoutParams)
                }
            }
        } catch (ex: Exception) {
            ex.printStackTrace()
        }
    }

    private fun FloatingMenuViewAccessor.updateLightControls() =
        brightnessManager.updateOverlay(this)

    override fun onDestroy() {
        brightnessManager.release()
        screenOffKeyReceiver.close()
        cameraLiveRefresh?.stop()
        cameraLiveRefresh = null
        commandRunner.onDestroy()
        sharedPreferences.unregisterOnSharedPreferenceChangeListener(this)
        unregisterReceiver(receiver)
        super.onDestroy()
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        Log.d("EinkService", "Service connected - applying all settings")
        updateAodInvert(sharedPreferences)
        cameraLiveRefresh?.stop()
        cameraLiveRefresh = CameraLiveRefresh(this).also {
            it.setScreenOn(isScreenOn)
            it.start()
        }
        displaySettingsManager.applySettings()
        
        handler.postDelayed({
            refreshModeManager.applyMode()
            Log.d("EinkService", "Applied refresh mode: ${refreshModeManager.currentMode}")
            
            handler.postDelayed({
                brightnessManager.applyBrightness()
                Log.d("EinkService", "Applied brightness: native=${brightnessManager.isNativeMode}, cold=${brightnessManager.coldBrightness}, warm=${brightnessManager.warmBrightness}")
                
                handler.postDelayed({
                    displaySettingsManager.applySettings()
                    Log.d("EinkService", "Applied display settings: autoRefresh=${displaySettingsManager.isAutoRefreshEnabled}, antiShake=${displaySettingsManager.isAntiShakeEnabled}")
                    updateColorScheme(sharedPreferences)
                    Log.d("EinkService", "Applied remaining settings")
                }, 500)
            }, 500)
        }, 1000)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        event.letPackageNameClassName { pkgName, clsName ->
            val componentName = ComponentName(
                pkgName,
                clsName
            )
            try {
                packageManager.getActivityInfo(componentName, 0)
                refreshModeManager.onAppChange(pkgName)
                displaySettingsManager.onAppChange(pkgName)
                menuBinding.updateButtons(refreshModeManager.currentMode)
            } catch (_: PackageManager.NameNotFoundException) {
            }
        }
    }

    fun setVideoOptimizedRefresh(enabled: Boolean) {
        cameraLiveRefresh?.setVideoOptimized(enabled)
    }

    private fun updateColorScheme(sharedPreferences: SharedPreferences) = sharedPreferences.run {
        if (!getBoolean("force_accent_color", false)) return@run
        val type = getString("color_scheme_type", "5")
        val preset = getString("accent_color_preset", "808080")
        if (type !in resources.getStringArray(R.array.color_type_values) ||
            preset !in resources.getStringArray(R.array.accent_color_values)) {
            Log.e("EinkService", "Invalid accent preset or color scheme: $preset, $type")
            return@run
        }
        val colorString = if (preset == "custom") {
            CustomGrayPreference.hexForGray(getInt("accent_custom_gray", 128))
        } else preset
        commandRunner.runCommands(arrayOf("theme $type $colorString"))
    }

    private fun updateAodInvert(sharedPreferences: SharedPreferences) {
        commandRunner.runCommands(arrayOf(Commands.AOD_INVERT(sharedPreferences.getBoolean("aod_invert", true))))
    }

    private fun updateMaxBrightness(sharedPreferences: SharedPreferences) = sharedPreferences.run {
        try{
            val brightness = Integer.parseInt(getString("override_max_brightness", "2000")?:"2000")
            commandRunner.runCommands(arrayOf("smb$brightness"))
        } catch (e: NumberFormatException) {
            e.printStackTrace()
        }
    }

    override fun onSharedPreferenceChanged(sharedPreferences: SharedPreferences?, key: String?) {
        when (key) {
            "override_max_brightness" -> {
                sharedPreferences?.let { updateMaxBrightness(it) }
            }

            "force_accent_color", "color_scheme_type", "accent_color_preset", "accent_custom_gray" -> {
                sharedPreferences?.let { updateColorScheme(it) }
            }

            BrightnessManager.PREF_NATIVE_MODE -> {
                brightnessManager.onModeChanged()
                menuBinding?.updateLightControls()
            }

            "aod_invert" -> {
                sharedPreferences?.let { updateAodInvert(it) }
            }

            "camera_live_refresh" -> cameraLiveRefresh?.update()

            "close_status_bar" -> {
                performGlobalAction(GLOBAL_ACTION_DISMISS_NOTIFICATION_SHADE)
            }

            "run_clear_screen" -> {
                performGlobalAction(GLOBAL_ACTION_DISMISS_NOTIFICATION_SHADE)
                handler.postDelayed({
                    commandRunner.runCommands(arrayOf(Commands.FORCE_CLEAR))
                }, 700)
            }
        }
    }
}

fun AccessibilityEvent?.letPackageNameClassName(block: (String, String) -> Unit) {
    this?.run {
        if (eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED)
            this.className?.let { clsName ->
                this.packageName?.let { pkgName -> block(pkgName.toString(), clsName.toString()) }
            }
    }
}

fun Button.deselect() {
    isActivated = false
    isSelected = false
}

fun Button.select() {
    isActivated = true
    isSelected = true
}