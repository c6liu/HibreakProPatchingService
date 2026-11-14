package com.lmqr.eink_settings.command_runners

interface CommandRunner {
    fun runCommands(cmds: Array<String>)
    fun onDestroy()
}