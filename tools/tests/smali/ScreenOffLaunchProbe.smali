.class public final Lhibreak/tests/ScreenOffLaunchProbe;
.super Ljava/lang/Object;
.implements Ljava/lang/Runnable;

.field private static receiver:Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;
.field private static context:Landroid/content/Context;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method public static run(Landroid/content/Context;)V
    .locals 8
    const-string v0, "power"
    invoke-virtual {p0, v0}, Landroid/content/Context;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v0
    check-cast v0, Landroid/os/PowerManager;
    invoke-virtual {v0}, Landroid/os/PowerManager;->isInteractive()Z
    move-result v1
    if-nez v1, :not_asleep
    invoke-static {p0}, Landroidx/preference/PreferenceManager;->getDefaultSharedPreferences(Landroid/content/Context;)Landroid/content/SharedPreferences;
    move-result-object v1
    invoke-interface {v1}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v1
    const-string v2, "launch_app_package_top_single_press_eink_action_screen_off"
    invoke-virtual {p0}, Landroid/content/Context;->getPackageName()Ljava/lang/String;
    move-result-object v3
    invoke-interface {v1, v2, v3}, Landroid/content/SharedPreferences$Editor;->putString(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    const-string v2, "top_single_press_eink_action_screen_off"
    const-string v3, "launch_app_top_single_press_eink_action_screen_off"
    invoke-interface {v1, v2, v3}, Landroid/content/SharedPreferences$Editor;->putString(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    const-string v2, "top_single_press_eink_action"
    const-string v3, "dummy"
    invoke-interface {v1, v2, v3}, Landroid/content/SharedPreferences$Editor;->putString(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v1}, Landroid/content/SharedPreferences$Editor;->commit()Z
    new-instance v1, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    invoke-direct {v1}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;-><init>()V
    const-class v2, Landroid/content/ContextWrapper;
    const-string v3, "mBase"
    invoke-static {v1, v2, v3, p0}, Lhibreak/tests/PopupProbe;->setField(Ljava/lang/Object;Ljava/lang/Class;Ljava/lang/String;Ljava/lang/Object;)V
    new-instance v2, Lcom/lmqr/ha9_comp_service/command_runners/UnixSocketCommandRunner;
    invoke-direct {v2}, Lcom/lmqr/ha9_comp_service/command_runners/UnixSocketCommandRunner;-><init>()V
    invoke-static {p0}, Landroidx/preference/PreferenceManager;->getDefaultSharedPreferences(Landroid/content/Context;)Landroid/content/SharedPreferences;
    move-result-object v3
    new-instance v4, Lcom/lmqr/ha9_comp_service/RefreshModeManager;
    invoke-direct {v4, v3, v2}, Lcom/lmqr/ha9_comp_service/RefreshModeManager;-><init>(Landroid/content/SharedPreferences;Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;)V
    new-instance v3, Lcom/lmqr/ha9_comp_service/button_mapper/ButtonActionManager;
    invoke-direct {v3, v2, v4}, Lcom/lmqr/ha9_comp_service/button_mapper/ButtonActionManager;-><init>(Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;Lcom/lmqr/ha9_comp_service/RefreshModeManager;)V
    const-class v2, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    const-string v4, "buttonActionManager"
    invoke-static {v1, v2, v4, v3}, Lhibreak/tests/PopupProbe;->setField(Ljava/lang/Object;Ljava/lang/Class;Ljava/lang/String;Ljava/lang/Object;)V
    new-instance v3, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;
    invoke-direct {v3, v1}, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;-><init>(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;)V
    const-string v4, "screenOffKeyReceiver"
    invoke-static {v1, v2, v4, v3}, Lhibreak/tests/PopupProbe;->setField(Ljava/lang/Object;Ljava/lang/Class;Ljava/lang/String;Ljava/lang/Object;)V
    sput-object v3, Lhibreak/tests/ScreenOffLaunchProbe;->receiver:Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;
    sput-object p0, Lhibreak/tests/ScreenOffLaunchProbe;->context:Landroid/content/Context;
    return-void
    :not_asleep
    new-instance v0, Ljava/lang/AssertionError;
    const-string v1, "Screen-off launch test must start with the display asleep"
    invoke-direct {v0, v1}, Ljava/lang/AssertionError;-><init>(Ljava/lang/Object;)V
    throw v0
.end method

.method public static sendKey(Landroid/app/Instrumentation;)V
    .locals 1
    new-instance v0, Lhibreak/tests/ScreenOffLaunchProbe;
    invoke-direct {v0}, Lhibreak/tests/ScreenOffLaunchProbe;-><init>()V
    invoke-virtual {p0, v0}, Landroid/app/Instrumentation;->runOnMainSync(Ljava/lang/Runnable;)V
    return-void
.end method

.method public run()V
    .locals 6
    new-instance v0, Landroid/content/Intent;
    const-string v1, "com.lmqr.ha9_comp_service.SCREEN_OFF_KEY"
    invoke-direct {v0, v1}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V
    const-string v1, "scan_code"
    const/16 v2, 0x3c
    invoke-virtual {v0, v1, v2}, Landroid/content/Intent;->putExtra(Ljava/lang/String;I)Landroid/content/Intent;
    invoke-static {}, Landroid/os/SystemClock;->uptimeMillis()J
    move-result-wide v2
    const-string v1, "event_time"
    invoke-virtual {v0, v1, v2, v3}, Landroid/content/Intent;->putExtra(Ljava/lang/String;J)Landroid/content/Intent;
    const-string v1, "key_action"
    const/4 v2, 0x0
    invoke-virtual {v0, v1, v2}, Landroid/content/Intent;->putExtra(Ljava/lang/String;I)Landroid/content/Intent;
    sget-object v4, Lhibreak/tests/ScreenOffLaunchProbe;->receiver:Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;
    sget-object v5, Lhibreak/tests/ScreenOffLaunchProbe;->context:Landroid/content/Context;
    invoke-virtual {v4, v5, v0}, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->onReceive(Landroid/content/Context;Landroid/content/Intent;)V
    const/4 v2, 0x1
    invoke-virtual {v0, v1, v2}, Landroid/content/Intent;->putExtra(Ljava/lang/String;I)Landroid/content/Intent;
    invoke-virtual {v4, v5, v0}, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->onReceive(Landroid/content/Context;Landroid/content/Intent;)V
    return-void
.end method

.method public static close(Landroid/content/Context;)V
    .locals 2
    sget-object v0, Lhibreak/tests/ScreenOffLaunchProbe;->receiver:Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;
    if-eqz v0, :check_wake
    invoke-virtual {v0}, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->close()V
    :check_wake
    const-string v0, "power"
    invoke-virtual {p0, v0}, Landroid/content/Context;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v0
    check-cast v0, Landroid/os/PowerManager;
    invoke-virtual {v0}, Landroid/os/PowerManager;->isInteractive()Z
    move-result v0
    if-nez v0, :done
    new-instance v0, Ljava/lang/AssertionError;
    const-string v1, "App launch did not wake the screen"
    invoke-direct {v0, v1}, Ljava/lang/AssertionError;-><init>(Ljava/lang/Object;)V
    throw v0
    :done
    return-void
.end method
