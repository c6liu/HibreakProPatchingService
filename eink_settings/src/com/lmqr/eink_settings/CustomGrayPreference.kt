package com.lmqr.eink_settings

import android.content.Context
import android.content.res.TypedArray
import android.util.AttributeSet
import android.widget.TextView
import androidx.preference.Preference
import androidx.preference.PreferenceViewHolder
import com.google.android.material.slider.Slider
import kotlin.math.roundToInt

class CustomGrayPreference(context: Context, attrs: AttributeSet) : Preference(context, attrs) {
    companion object {
        fun hexForGray(value: Int): String =
            (value.coerceIn(0, 255) * 0x010101).toString(16).padStart(6, '0').uppercase()
    }

    private var gray = 128

    init {
        layoutResource = R.layout.preference_custom_gray
    }

    override fun onGetDefaultValue(a: TypedArray, index: Int): Any = a.getInt(index, 128)

    override fun onSetInitialValue(defaultValue: Any?) {
        gray = getPersistedInt(defaultValue as? Int ?: 128).coerceIn(0, 255)
        persistInt(gray)
    }

    override fun onBindViewHolder(holder: PreferenceViewHolder) {
        super.onBindViewHolder(holder)
        val slider = holder.findViewById(R.id.custom_gray_slider) as Slider
        val label = holder.findViewById(R.id.custom_gray_value) as TextView
        slider.clearOnChangeListeners()
        slider.clearOnSliderTouchListeners()
        slider.value = gray.toFloat()
        label.text = "#${hexForGray(gray)}"
        slider.isEnabled = isEnabled
        slider.contentDescription = title
        slider.setLabelFormatter { "#${hexForGray(it.roundToInt())}" }
        var dragging = false
        fun commit() {
            val selected = slider.value.roundToInt()
            if (selected != gray && callChangeListener(selected)) {
                gray = selected
                persistInt(gray)
            }
            slider.value = gray.toFloat()
            label.text = "#${hexForGray(gray)}"
        }
        slider.addOnChangeListener { _, value, fromUser ->
            if (fromUser) {
                label.text = "#${hexForGray(value.roundToInt())}"
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
