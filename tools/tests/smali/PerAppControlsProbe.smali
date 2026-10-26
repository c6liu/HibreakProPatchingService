.class public final Lhibreak/tests/PerAppControlsProbe;
.super Ljava/lang/Object;

.field private static camera:Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;

.method private static assertState(Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;ZZZ)V
    .locals 3
    invoke-virtual {p0}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->isAutoRefreshEnabled()Z
    move-result v0
    if-ne v0, p1, :failed
    invoke-virtual {p0}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->isAntiShakeEnabled()Z
    move-result v0
    if-ne v0, p2, :failed
    invoke-virtual {p0}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->isVideoOptimizedEnabled()Z
    move-result v0
    if-ne v0, p3, :failed
    const-class v0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;
    const-string v1, "videoOptimized"
    invoke-virtual {v0, v1}, Ljava/lang/Class;->getDeclaredField(Ljava/lang/String;)Ljava/lang/reflect/Field;
    move-result-object v0
    const/4 v1, 0x1
    invoke-virtual {v0, v1}, Ljava/lang/reflect/Field;->setAccessible(Z)V
    sget-object v1, Lhibreak/tests/PerAppControlsProbe;->camera:Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;
    invoke-virtual {v0, v1}, Ljava/lang/reflect/Field;->getBoolean(Ljava/lang/Object;)Z
    move-result v0
    if-ne v0, p3, :failed
    return-void
    :failed
    new-instance v0, Ljava/lang/AssertionError;
    const-string p0, "Per-app display settings mismatch"
    invoke-direct {v0, p0}, Ljava/lang/AssertionError;-><init>(Ljava/lang/Object;)V
    throw v0
.end method

.method public static run(Landroid/content/Context;Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;)V
    .locals 12
    const-string v0, "per_app_controls_test"
    const/4 v1, 0x0
    invoke-virtual {p0, v0, v1}, Landroid/content/Context;->getSharedPreferences(Ljava/lang/String;I)Landroid/content/SharedPreferences;
    move-result-object v0
    invoke-interface {v0}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v2
    const/4 v3, 0x1
    const-string v4, "auto_refresh_enabled"
    invoke-interface {v2, v4, v3}, Landroid/content/SharedPreferences$Editor;->putBoolean(Ljava/lang/String;Z)Landroid/content/SharedPreferences$Editor;
    const-string v4, "anti_shake_enabled"
    invoke-interface {v2, v4, v3}, Landroid/content/SharedPreferences$Editor;->putBoolean(Ljava/lang/String;Z)Landroid/content/SharedPreferences$Editor;
    const-string v4, "video_optimized_refresh"
    invoke-interface {v2, v4, v3}, Landroid/content/SharedPreferences$Editor;->putBoolean(Ljava/lang/String;Z)Landroid/content/SharedPreferences$Editor;
    const-string v4, "disable_perapprefresh"
    invoke-interface {v2, v4, v3}, Landroid/content/SharedPreferences$Editor;->putBoolean(Ljava/lang/String;Z)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v2}, Landroid/content/SharedPreferences$Editor;->apply()V
    new-instance v2, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;
    invoke-direct {v2, v0, p1}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;-><init>(Landroid/content/SharedPreferences;Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;)V
    new-instance v10, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    invoke-direct {v10}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;-><init>()V
    new-instance v9, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;
    invoke-direct {v9, p0}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;-><init>(Landroid/content/Context;)V
    invoke-virtual {v9, v1}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->setScreenOn(Z)V
    sput-object v9, Lhibreak/tests/PerAppControlsProbe;->camera:Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;
    const-class v8, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    const-string v7, "cameraLiveRefresh"
    invoke-static {v10, v8, v7, v9}, Lhibreak/tests/PopupProbe;->setField(Ljava/lang/Object;Ljava/lang/Class;Ljava/lang/String;Ljava/lang/Object;)V
    invoke-virtual {v2, v10}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->attach(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;)V
    new-instance v4, Landroid/widget/Switch;
    invoke-direct {v4, p0}, Landroid/widget/Switch;-><init>(Landroid/content/Context;)V
    new-instance v5, Landroid/widget/Switch;
    invoke-direct {v5, p0}, Landroid/widget/Switch;-><init>(Landroid/content/Context;)V
    new-instance v6, Landroid/widget/Switch;
    invoke-direct {v6, p0}, Landroid/widget/Switch;-><init>(Landroid/content/Context;)V
    invoke-virtual {v2, v4, v5}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->setupSwitches(Landroid/widget/CompoundButton;Landroid/widget/CompoundButton;)V
    invoke-virtual {v2, v6}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->setupVideo(Landroid/widget/CompoundButton;)V
    invoke-virtual {v6}, Landroid/widget/Switch;->isEnabled()Z
    move-result v7
    if-nez v7, :failed
    const-string v7, "test.video"
    invoke-virtual {v2, v7}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->onAppChange(Ljava/lang/String;)V
    invoke-static {v2, v3, v3, v1}, Lhibreak/tests/PerAppControlsProbe;->assertState(Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;ZZZ)V
    invoke-virtual {v4, v1}, Landroid/widget/Switch;->setChecked(Z)V
    invoke-virtual {v5, v1}, Landroid/widget/Switch;->setChecked(Z)V
    invoke-virtual {v6, v3}, Landroid/widget/Switch;->setChecked(Z)V
    invoke-static {v2, v1, v1, v3}, Lhibreak/tests/PerAppControlsProbe;->assertState(Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;ZZZ)V
    const-string v8, "test.reader"
    invoke-virtual {v2, v8}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->onAppChange(Ljava/lang/String;)V
    invoke-static {v2, v3, v3, v1}, Lhibreak/tests/PerAppControlsProbe;->assertState(Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;ZZZ)V
    invoke-virtual {v6}, Landroid/widget/Switch;->isChecked()Z
    move-result v9
    if-nez v9, :failed
    invoke-virtual {v4}, Landroid/widget/Switch;->isChecked()Z
    move-result v9
    if-eqz v9, :failed
    invoke-virtual {v5}, Landroid/widget/Switch;->isChecked()Z
    move-result v9
    if-eqz v9, :failed
    invoke-virtual {v2, v7}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->onAppChange(Ljava/lang/String;)V
    invoke-static {v2, v1, v1, v3}, Lhibreak/tests/PerAppControlsProbe;->assertState(Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;ZZZ)V
    invoke-virtual {v6}, Landroid/widget/Switch;->isChecked()Z
    move-result v9
    if-eqz v9, :failed
    new-instance v2, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;
    invoke-direct {v2, v0, p1}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;-><init>(Landroid/content/SharedPreferences;Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;)V
    invoke-virtual {v2, v10}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->attach(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;)V
    invoke-virtual {v2, v7}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->onAppChange(Ljava/lang/String;)V
    invoke-static {v2, v1, v1, v3}, Lhibreak/tests/PerAppControlsProbe;->assertState(Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;ZZZ)V
    invoke-virtual {v2, v8}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->onAppChange(Ljava/lang/String;)V
    invoke-static {v2, v3, v3, v1}, Lhibreak/tests/PerAppControlsProbe;->assertState(Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;ZZZ)V
    invoke-interface {v0}, Landroid/content/SharedPreferences;->getAll()Ljava/util/Map;
    move-result-object v9
    invoke-interface {v9}, Ljava/util/Map;->size()I
    move-result v9
    const/4 v11, 0x7
    if-ne v9, v11, :failed
    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, "PASS: per-app controls migration, isolation, popup rebinding, persistence"
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V
    return-void
    :failed
    new-instance v0, Ljava/lang/AssertionError;
    const-string v1, "Per-app popup state mismatch"
    invoke-direct {v0, v1}, Ljava/lang/AssertionError;-><init>(Ljava/lang/Object;)V
    throw v0
.end method
