package com.lmqr.ha9_comp_service

import android.content.SharedPreferences
import android.widget.CompoundButton
import com.lmqr.ha9_comp_service.command_runners.CommandRunner

class DisplaySettingsManager(
    private val sharedPreferences: SharedPreferences,
    private val commandRunner: CommandRunner,
) : CompoundButton.OnCheckedChangeListener {
    private var packageName = ""
    private var service: A9AccessibilityService? = null
    private val switches = arrayOfNulls<CompoundButton>(3)
    private val keys = arrayOf("auto_refresh_enabled", "anti_shake_enabled", "video_optimized_refresh")

    fun attach(service: A9AccessibilityService) {
        this.service = service
    }

    private fun key(index: Int) = "display:$packageName:${keys[index]}"

    private fun get(index: Int): Boolean {
        val default = index < 2 && sharedPreferences.getBoolean(keys[index], false)
        return sharedPreferences.getBoolean(key(index), default)
    }

    val isAutoRefreshEnabled get() = get(0)
    val isAntiShakeEnabled get() = get(1)
    val isVideoOptimizedEnabled get() = get(2)

    fun onAppChange(value: String) {
        if (value == packageName) return
        packageName = value
        applySettings()
        bind()
    }

    fun applySettings() {
        commandRunner.runCommands(arrayOf(
            if (isAutoRefreshEnabled) "au_br1" else "au_br0",
            if (isAntiShakeEnabled) "an_fl1" else "an_fl0",
        ))
        service?.setVideoOptimizedRefresh(isVideoOptimizedEnabled)
    }

    fun setupSwitches(autoRefresh: CompoundButton, antiShake: CompoundButton) {
        switches[0] = autoRefresh
        switches[1] = antiShake
        bind()
    }

    fun setupVideo(video: CompoundButton) {
        switches[2] = video
        bind()
    }

    private fun bind() {
        switches.forEachIndexed { index, button ->
            button?.apply {
                setOnCheckedChangeListener(null)
                isChecked = get(index)
                isEnabled = packageName.isNotEmpty()
                setOnCheckedChangeListener(this@DisplaySettingsManager)
            }
        }
    }

    override fun onCheckedChanged(button: CompoundButton, checked: Boolean) {
        val index = switches.indexOf(button)
        check(index >= 0 && packageName.isNotEmpty()) { "No active app for display controls" }
        sharedPreferences.edit().putBoolean(key(index), checked).apply()
        applySettings()
    }
}
