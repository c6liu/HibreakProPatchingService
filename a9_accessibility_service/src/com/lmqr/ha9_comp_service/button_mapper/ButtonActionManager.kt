package com.lmqr.ha9_comp_service.button_mapper

import android.content.Context
import androidx.preference.PreferenceManager
import com.lmqr.ha9_comp_service.command_runners.CommandRunner
import com.lmqr.ha9_comp_service.command_runners.Commands
import com.lmqr.ha9_comp_service.RefreshModeManager

class ButtonActionManager(commandRunner: CommandRunner, refreshModeManager: RefreshModeManager) {
    private val buttonCommands = mapOf(
        "clear" to ClearScreenButtonAction(commandRunner, refreshModeManager),
        "next_track" to NextTrackButtonAction(),
        "toggle_music" to TogglePauseButtonAction(),
        "back" to BackButtonAction(),
        "home" to HomeButtonAction(),
        "recents" to RecentsButtonAction(),
        "open_menu" to ToggleMenuButtonAction(),
        "dpad_up" to DpadButtonAction(commandRunner, Commands.DPAD_UP),
        "dpad_down" to DpadButtonAction(commandRunner, Commands.DPAD_DOWN),
        "dpad_left" to DpadButtonAction(commandRunner, Commands.DPAD_LEFT),
        "dpad_right" to DpadButtonAction(commandRunner, Commands.DPAD_RIGHT),
        "previous_track" to PreviousTrackButtonAction(),
    ).withDefault { DummyButtonAction() }

    fun executeLongPress(context: Context){
        buttonCommands[PreferenceManager.getDefaultSharedPreferences(context).getString("long_press_eink_action", "dummy")]?.execute(context)
    }

    fun executeDoublePress(context: Context){
        buttonCommands[PreferenceManager.getDefaultSharedPreferences(context).getString("double_press_eink_action", "open_menu")]?.execute(context)
    }

    fun executeSinglePress(context: Context){
        buttonCommands[PreferenceManager.getDefaultSharedPreferences(context).getString("single_press_eink_action", "clear")]?.execute(context)
    }

    fun executeLongPressScreenOff(context: Context){
        buttonCommands[PreferenceManager.getDefaultSharedPreferences(context).getString("long_press_eink_action_screen_off", "dummy")]?.execute(context)
    }

    fun executeDoublePressScreenOff(context: Context){
        buttonCommands[PreferenceManager.getDefaultSharedPreferences(context).getString("double_press_eink_action_screen_off", "dummy")]?.execute(context)
    }

    fun executeSinglePressScreenOff(context: Context){
        buttonCommands[PreferenceManager.getDefaultSharedPreferences(context).getString("single_press_eink_action_screen_off", "dummy")]?.execute(context)
    }
    fun executeLongPressTop(context: Context){
        buttonCommands[PreferenceManager.getDefaultSharedPreferences(context).getString("top_long_press_eink_action", "dummy")]?.execute(context)
    }

    fun executeDoublePressTop(context: Context){
        buttonCommands[PreferenceManager.getDefaultSharedPreferences(context).getString("top_double_press_eink_action", "open_menu")]?.execute(context)
    }

    fun executeSinglePressTop(context: Context){
        buttonCommands[PreferenceManager.getDefaultSharedPreferences(context).getString("top_single_press_eink_action", "clear")]?.execute(context)
    }

    fun executeLongPressScreenOffTop(context: Context){
        buttonCommands[PreferenceManager.getDefaultSharedPreferences(context).getString("top_long_press_eink_action_screen_off", "dummy")]?.execute(context)
    }

    fun executeDoublePressScreenOffTop(context: Context){
        buttonCommands[PreferenceManager.getDefaultSharedPreferences(context).getString("top_double_press_eink_action_screen_off", "dummy")]?.execute(context)
    }

    fun executeSinglePressScreenOffTop(context: Context){
        buttonCommands[PreferenceManager.getDefaultSharedPreferences(context).getString("top_single_press_eink_action_screen_off", "dummy")]?.execute(context)
    }    
}