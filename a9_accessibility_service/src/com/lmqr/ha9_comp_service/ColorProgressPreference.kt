package com.lmqr.ha9_comp_service

import android.content.Context
import android.content.res.TypedArray
import android.util.AttributeSet
import android.widget.TextView
import androidx.preference.Preference
import androidx.preference.PreferenceViewHolder
import com.google.android.material.slider.Slider
import kotlin.math.roundToInt

class ColorProgressPreference(context: Context, attrs: AttributeSet) : Preference(context, attrs) {
    private var progress = 0

    init {
        layoutResource = R.layout.preference_material_color_slider
    }

    override fun onGetDefaultValue(a: TypedArray, index: Int): Any = a.getInt(index, 0)

    override fun onSetInitialValue(defaultValue: Any?) {
        progress = getPersistedInt(defaultValue as? Int ?: 0).coerceIn(0, 100)
        persistInt(progress)
    }

    override fun onBindViewHolder(holder: PreferenceViewHolder) {
        super.onBindViewHolder(holder)
        val slider = holder.findViewById(R.id.color_slider) as Slider
        val valueText = holder.findViewById(R.id.color_value) as TextView
        slider.clearOnChangeListeners()
        slider.clearOnSliderTouchListeners()
        slider.value = progress.toFloat()
        valueText.setColorProgress(progress)
        slider.isEnabled = isEnabled
        slider.contentDescription = title
        slider.setLabelFormatter { "0x${it.roundToInt().progressToHex()}" }
        var dragging = false
        fun commit() {
            val selected = slider.value.roundToInt()
            if (selected != progress && callChangeListener(selected)) {
                progress = selected
                persistInt(selected)
            }
            slider.value = progress.toFloat()
            valueText.setColorProgress(progress)
        }
        slider.addOnChangeListener { _, value, fromUser ->
            if (fromUser) {
                valueText.setColorProgress(value.roundToInt())
                if (!dragging) commit()
            }
        }
        slider.addOnSliderTouchListener(object : Slider.OnSliderTouchListener {
            override fun onStartTrackingTouch(slider: Slider) { dragging = true }
            override fun onStopTrackingTouch(slider: Slider) {
                dragging = false
                commit()
            }
        })
    }
}

fun Int.progressToHex() = (((this * 0xFF / 100) and 0xFF)*0x10101).toString(16).padStart(6, '0').uppercase()

private fun TextView.setColorProgress(v: Int){
    val vStr = "0x${v.progressToHex()}"
    text = vStr
}