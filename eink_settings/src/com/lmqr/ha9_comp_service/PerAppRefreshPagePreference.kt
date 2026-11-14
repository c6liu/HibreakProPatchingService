package com.lmqr.ha9_comp_service

import android.content.Context
import android.content.Intent
import android.util.AttributeSet
import androidx.preference.Preference

class PerAppRefreshPagePreference(context: Context, attrs: AttributeSet?) :
    Preference(context, attrs) {
    override fun onClick() {
        context.startActivity(Intent(context, SettingsActivity::class.java)
            .putExtra("per_app_page", true))
    }
}
