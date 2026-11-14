package com.lmqr.eink_settings.button_mapper

import android.content.Context
import com.lmqr.eink_settings.command_runners.CommandRunner

class DpadButtonAction(
    private val commandRunner: CommandRunner,
    private val command: String,
) : ButtonAction {
    override fun execute(context: Context) {
        commandRunner.runCommands(arrayOf(command))
    }
}
