package com.lmqr.ha9_comp_service.button_mapper

import android.content.Context
import com.lmqr.ha9_comp_service.command_runners.CommandRunner

class DpadButtonAction(
    private val commandRunner: CommandRunner,
    private val command: String,
) : ButtonAction {
    override fun execute(context: Context) {
        commandRunner.runCommands(arrayOf(command))
    }
}
