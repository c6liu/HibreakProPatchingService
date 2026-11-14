package com.lmqr.eink_settings.button_mapper

import android.content.Context
import com.lmqr.eink_settings.EinkAccessibilityService

class ToggleMenuButtonAction : ButtonAction {
    override fun execute(context: Context) {
        (context as? EinkAccessibilityService)?.openFloatingMenu()
    }
}