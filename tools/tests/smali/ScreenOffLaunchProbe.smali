.class public final Lhibreak/tests/ScreenOffLaunchProbe;
.super Ljava/lang/Object;

.method public static run(Landroid/content/Context;)V
    .locals 5
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
    invoke-interface {v1}, Landroid/content/SharedPreferences$Editor;->commit()Z
    new-instance v1, Lcom/lmqr/ha9_comp_service/button_mapper/LaunchAppButtonAction;
    invoke-direct {v1, v2}, Lcom/lmqr/ha9_comp_service/button_mapper/LaunchAppButtonAction;-><init>(Ljava/lang/String;)V
    invoke-virtual {v1, p0}, Lcom/lmqr/ha9_comp_service/button_mapper/LaunchAppButtonAction;->execute(Landroid/content/Context;)V
    invoke-virtual {v0}, Landroid/os/PowerManager;->isInteractive()Z
    move-result v1
    if-eqz v1, :not_awake
    return-void
    :not_asleep
    new-instance v0, Ljava/lang/AssertionError;
    const-string v1, "Screen-off launch test must start with the display asleep"
    invoke-direct {v0, v1}, Ljava/lang/AssertionError;-><init>(Ljava/lang/Object;)V
    throw v0
    :not_awake
    new-instance v0, Ljava/lang/AssertionError;
    const-string v1, "App launch did not wake the screen"
    invoke-direct {v0, v1}, Ljava/lang/AssertionError;-><init>(Ljava/lang/Object;)V
    throw v0
.end method
