package com.lmqr.eink_settings

import android.content.Intent
import androidx.preference.ListPreference
import androidx.preference.Preference
import androidx.preference.PreferenceFragmentCompat
import androidx.preference.PreferenceManager

object AppLaunchSettings {
    fun populate(fragment: PreferenceFragmentCompat) {
        val context = fragment.requireContext()
        ButtonActionSettings.actionKeys.forEachIndexed { index, actionKey ->
            val action = requireNotNull(fragment.findPreference<ListPreference>(actionKey))
            val entries = requireNotNull(action.entries).toList()
            val values = requireNotNull(action.entryValues).toList()
            check(values.last().toString() == "dummy")
            action.entries = (entries.dropLast(1) + listOf(
                context.getString(R.string.launch_app),
                context.getString(R.string.launch_shortcut),
            ) + entries.last()).toTypedArray()
            action.entryValues = (values.dropLast(1) + listOf(
                "launch_app_$actionKey", "launch_shortcut_$actionKey",
            ) + values.last()).toTypedArray()
            action.order = (index % 6) * 3
            action.summaryProvider = ListPreference.SimpleSummaryProvider.getInstance()

            for (shortcuts in listOf(false, true)) {
                val target = Preference(context).apply {
                    key = if (shortcuts) "shortcut_target_$actionKey" else "launch_app_package_$actionKey"
                    setTitle(if (shortcuts) R.string.shortcut_to_launch else R.string.app_to_launch)
                    order = action.order + if (shortcuts) 2 else 1
                    setOnPreferenceClickListener {
                        openPicker(fragment, actionKey, shortcuts)
                        true
                    }
                }
                requireNotNull(action.parent).addPreference(target)
            }
            action.setOnPreferenceChangeListener { _, newValue ->
                when (newValue) {
                    "launch_app_$actionKey", "launch_shortcut_$actionKey" -> {
                        openPicker(fragment, actionKey, newValue == "launch_shortcut_$actionKey")
                        false
                    }
                    else -> {
                        updateTargets(fragment, actionKey, newValue.toString())
                        true
                    }
                }
            }
        }
        refresh(fragment)
    }

    fun refresh(fragment: PreferenceFragmentCompat) {
        val preferences = PreferenceManager.getDefaultSharedPreferences(fragment.requireContext())
        ButtonActionSettings.actionKeys.forEach { actionKey ->
            val action = requireNotNull(fragment.findPreference<ListPreference>(actionKey))
            action.value = preferences.getString(actionKey, action.value)
            updateTargets(fragment, actionKey, action.value)
        }
    }

    private fun updateTargets(fragment: PreferenceFragmentCompat, actionKey: String, value: String?) {
        val context = fragment.requireContext()
        val preferences = PreferenceManager.getDefaultSharedPreferences(context)
        requireNotNull(fragment.findPreference<Preference>("launch_app_package_$actionKey")).apply {
            isVisible = value == "launch_app_$actionKey"
            val packageName = preferences.getString(key, null)
            summary = if (packageName.isNullOrBlank()) {
                context.getString(R.string.choose_app)
            } else {
                try {
                    context.packageManager.getApplicationInfo(packageName, 0)
                        .loadLabel(context.packageManager)
                } catch (_: android.content.pm.PackageManager.NameNotFoundException) {
                    context.getString(R.string.unavailable_app)
                }
            }
        }
        requireNotNull(fragment.findPreference<Preference>("shortcut_target_$actionKey")).apply {
            isVisible = value == "launch_shortcut_$actionKey"
            summary = ShortcutAssignment.summary(context, actionKey)
        }
    }

    private fun openPicker(fragment: PreferenceFragmentCompat, actionKey: String, shortcuts: Boolean) {
        fragment.startActivity(Intent(fragment.requireContext(), ActionTargetPickerActivity::class.java)
            .putExtra(ActionTargetPickerActivity.EXTRA_ACTION_KEY, actionKey)
            .putExtra(ActionTargetPickerActivity.EXTRA_SHORTCUTS, shortcuts))
    }
}
