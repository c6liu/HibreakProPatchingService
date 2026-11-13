package com.lmqr.ha9_comp_service

import android.view.View
import android.view.LayoutInflater
import android.widget.Button
import android.widget.SeekBar
import android.widget.CompoundButton

/**
 * This class replaces the generated data binding class for floating_menu_layout.xml
 * and provides direct access to the views in the layout.
 */
class FloatingMenuViewAccessor(val root: View) {
    val button1: Button = root.findViewById(R.id.button1)
    val button2: Button = root.findViewById(R.id.button2)
    val button3: Button = root.findViewById(R.id.button3)
    val button4: Button = root.findViewById(R.id.button4)
    val button5: Button = root.findViewById(R.id.button5)
    
    val autoRefresh: CompoundButton = root.findViewById(R.id.auto_refresh)
    val antiShake: CompoundButton = root.findViewById(R.id.anti_shake)
    val videoOptimizedRefresh: CompoundButton = root.findViewById(R.id.video_optimized_refresh)
    
    val settingsIcon: View = root.findViewById(R.id.settings_icon)
    val closeButton: View = root.findViewById<View>(R.id.close_menu).apply {
        setOnClickListener { root.visibility = View.GONE }
    }
    val lightSeekbar: SeekBar = root.findViewById(R.id.light_seekbar)
    val lightWarmSeekbar: SeekBar = root.findViewById(R.id.light_warm_seekbar)
    val lightTemperatureSeekbar: SeekBar = root.findViewById(R.id.light_temperature_seekbar)
    val independentLightControls: List<View> = listOf(
        root.findViewById(R.id.light_seekbar_container),
        root.findViewById(R.id.light_warm_seekbar_container),
    )
    val nativeLightControls: List<View> = listOf(
        root.findViewById(R.id.light_temperature_seekbar_container),
        root.findViewById(R.id.light_native_hint),
    )
    
    companion object {
        fun inflate(inflater: LayoutInflater): FloatingMenuViewAccessor {
            val view = inflater.inflate(R.layout.floating_menu_layout, null)
            return FloatingMenuViewAccessor(view)
        }
    }
}

fun FloatingMenuViewAccessor?.close() = this?.run {
    root.visibility = View.GONE
}

fun FloatingMenuViewAccessor?.updateButtons(mode: RefreshMode) = this?.run {
    listOf(button1, button2, button3, button4, button5).forEach {
        it.deselect()
    }
    
    when (mode) {
        RefreshMode.SMOOTH -> button1.select()
        RefreshMode.CLEAR -> button2.select()
        RefreshMode.BALANCED -> button3.select()
        RefreshMode.SPEED -> button4.select()
        RefreshMode.HYPER -> button5.select()
    }
}
