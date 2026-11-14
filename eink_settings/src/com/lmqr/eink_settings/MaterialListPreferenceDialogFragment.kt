package com.lmqr.eink_settings

import android.app.Dialog
import android.content.DialogInterface
import android.os.Bundle
import androidx.preference.ListPreferenceDialogFragmentCompat
import com.google.android.material.dialog.MaterialAlertDialogBuilder

/** Retains AndroidX's saved choices, change listeners and persistence with a Material dialog. */
class MaterialListPreferenceDialogFragment : ListPreferenceDialogFragmentCompat() {
    override fun onCreateDialog(savedInstanceState: Bundle?): Dialog {
        val builder = MaterialAlertDialogBuilder(requireContext())
            .setTitle(preference.dialogTitle)
            .setIcon(preference.dialogIcon)
            .setNegativeButton(preference.negativeButtonText, this)
        val content = onCreateDialogView(builder.context)
        if (content != null) {
            onBindDialogView(content)
            builder.setView(content)
        } else {
            builder.setMessage(preference.dialogMessage)
        }
        onPrepareDialogBuilder(builder)
        return builder.create().also { onClick(it, DialogInterface.BUTTON_NEGATIVE) }
    }
}
