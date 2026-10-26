.class public final Lhibreak/tests/PopupProbe;
.super Landroid/view/ContextThemeWrapper;

.field private resources:Landroid/content/res/Resources;
.field private preferences:Landroid/content/SharedPreferences;

.method public constructor <init>(Landroid/content/Context;Landroid/content/res/Resources;Landroid/content/SharedPreferences;)V
    .locals 1
    const v0, @THEME@
    invoke-direct {p0, p1, v0}, Landroid/view/ContextThemeWrapper;-><init>(Landroid/content/Context;I)V
    iput-object p2, p0, Lhibreak/tests/PopupProbe;->resources:Landroid/content/res/Resources;
    iput-object p3, p0, Lhibreak/tests/PopupProbe;->preferences:Landroid/content/SharedPreferences;
    return-void
.end method

.method public getResources()Landroid/content/res/Resources;
    .locals 1
    iget-object v0, p0, Lhibreak/tests/PopupProbe;->resources:Landroid/content/res/Resources;
    return-object v0
.end method

.method public getSharedPreferences(Ljava/lang/String;I)Landroid/content/SharedPreferences;
    .locals 1
    iget-object v0, p0, Lhibreak/tests/PopupProbe;->preferences:Landroid/content/SharedPreferences;
    return-object v0
.end method

.method public static setField(Ljava/lang/Object;Ljava/lang/Class;Ljava/lang/String;Ljava/lang/Object;)V
    .locals 1
    invoke-virtual {p1, p2}, Ljava/lang/Class;->getDeclaredField(Ljava/lang/String;)Ljava/lang/reflect/Field;
    move-result-object p1
    const/4 v0, 0x1
    invoke-virtual {p1, v0}, Ljava/lang/reflect/Field;->setAccessible(Z)V
    invoke-virtual {p1, p0, p3}, Ljava/lang/reflect/Field;->set(Ljava/lang/Object;Ljava/lang/Object;)V
    return-void
.end method

.method public static run(Landroid/content/Context;)V
    .locals 12
    move-object v0, p0
    invoke-virtual {v0}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;
    move-result-object v4
    new-instance v1, Lhibreak/tests/DpadActionProbe;
    invoke-direct {v1}, Lhibreak/tests/DpadActionProbe;-><init>()V
    const-class v2, Lhibreak/tests/PopupProbe;
    invoke-virtual {v2}, Ljava/lang/Class;->getClassLoader()Ljava/lang/ClassLoader;
    move-result-object v2
    const-class v3, Landroid/content/SharedPreferences;
    filled-new-array {v3}, [Ljava/lang/Class;
    move-result-object v3
    invoke-static {v2, v3, v1}, Ljava/lang/reflect/Proxy;->newProxyInstance(Ljava/lang/ClassLoader;[Ljava/lang/Class;Ljava/lang/reflect/InvocationHandler;)Ljava/lang/Object;
    move-result-object v3
    check-cast v3, Landroid/content/SharedPreferences;
    const-class v5, Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;
    filled-new-array {v5}, [Ljava/lang/Class;
    move-result-object v5
    invoke-static {v2, v5, v1}, Ljava/lang/reflect/Proxy;->newProxyInstance(Ljava/lang/ClassLoader;[Ljava/lang/Class;Ljava/lang/reflect/InvocationHandler;)Ljava/lang/Object;
    move-result-object v5
    check-cast v5, Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;
    new-instance v6, Lhibreak/tests/PopupProbe;
    invoke-direct {v6, v0, v4, v3}, Lhibreak/tests/PopupProbe;-><init>(Landroid/content/Context;Landroid/content/res/Resources;Landroid/content/SharedPreferences;)V
    invoke-static {v6}, Landroid/view/LayoutInflater;->from(Landroid/content/Context;)Landroid/view/LayoutInflater;
    move-result-object v0
    const v1, @LAYOUT@
    const/4 v2, 0x0
    invoke-virtual {v0, v1, v2}, Landroid/view/LayoutInflater;->inflate(ILandroid/view/ViewGroup;)Landroid/view/View;
    move-result-object v0
    new-instance v1, Lcom/lmqr/ha9_comp_service/FloatingMenuViewAccessor;
    invoke-direct {v1, v0}, Lcom/lmqr/ha9_comp_service/FloatingMenuViewAccessor;-><init>(Landroid/view/View;)V
    invoke-virtual {v1}, Lcom/lmqr/ha9_comp_service/FloatingMenuViewAccessor;->getVideoOptimizedRefresh()Landroid/widget/Switch;
    move-result-object v1
    if-nez v1, :switch_found
    new-instance v0, Ljava/lang/AssertionError;
    const-string v2, "Popup video switch is missing"
    invoke-direct {v0, v2}, Ljava/lang/AssertionError;-><init>(Ljava/lang/Object;)V
    throw v0
    :switch_found
    new-instance v7, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    invoke-direct {v7}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;-><init>()V
    const-class v8, Landroid/content/ContextWrapper;
    const-string v9, "mBase"
    invoke-static {v7, v8, v9, v6}, Lhibreak/tests/PopupProbe;->setField(Ljava/lang/Object;Ljava/lang/Class;Ljava/lang/String;Ljava/lang/Object;)V
    new-instance v10, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;
    invoke-direct {v10, v3, v5}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;-><init>(Landroid/content/SharedPreferences;Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;)V
    invoke-virtual {v10, v7}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->attach(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;)V
    const-class v8, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    const-string v9, "displaySettingsManager"
    invoke-static {v7, v8, v9, v10}, Lhibreak/tests/PopupProbe;->setField(Ljava/lang/Object;Ljava/lang/Class;Ljava/lang/String;Ljava/lang/Object;)V
    invoke-static {v7, v1}, Lcom/lmqr/ha9_comp_service/VideoRefreshSwitchSetup;->setup(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;Landroid/widget/Switch;)V
    const-class v8, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    const-string v9, "sharedPreferences"
    invoke-static {v7, v8, v9, v3}, Lhibreak/tests/PopupProbe;->setField(Ljava/lang/Object;Ljava/lang/Class;Ljava/lang/String;Ljava/lang/Object;)V
    new-instance v0, Lcom/lmqr/ha9_comp_service/BrightnessManager;
    invoke-direct {v0, v3, v5}, Lcom/lmqr/ha9_comp_service/BrightnessManager;-><init>(Landroid/content/SharedPreferences;Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;)V
    const-string v9, "brightnessManager"
    invoke-static {v7, v8, v9, v0}, Lhibreak/tests/PopupProbe;->setField(Ljava/lang/Object;Ljava/lang/Class;Ljava/lang/String;Ljava/lang/Object;)V
    new-instance v0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;
    invoke-direct {v0, v6}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;-><init>(Landroid/content/Context;)V
    const-string v9, "cameraLiveRefresh"
    invoke-static {v7, v8, v9, v0}, Lhibreak/tests/PopupProbe;->setField(Ljava/lang/Object;Ljava/lang/Class;Ljava/lang/String;Ljava/lang/Object;)V
    const-string v9, "receiver"
    invoke-virtual {v8, v9}, Ljava/lang/Class;->getDeclaredField(Ljava/lang/String;)Ljava/lang/reflect/Field;
    move-result-object v8
    const/4 v9, 0x1
    invoke-virtual {v8, v9}, Ljava/lang/reflect/Field;->setAccessible(Z)V
    invoke-virtual {v8, v7}, Ljava/lang/reflect/Field;->get(Ljava/lang/Object;)Ljava/lang/Object;
    move-result-object v8
    check-cast v8, Landroid/content/BroadcastReceiver;
    new-instance v9, Landroid/content/Intent;
    const-string v10, "android.intent.action.SCREEN_OFF"
    invoke-direct {v9, v10}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V
    invoke-virtual {v8, v6, v9}, Landroid/content/BroadcastReceiver;->onReceive(Landroid/content/Context;Landroid/content/Intent;)V
    const-string v10, "android.intent.action.SCREEN_ON"
    invoke-virtual {v9, v10}, Landroid/content/Intent;->setAction(Ljava/lang/String;)Landroid/content/Intent;
    invoke-virtual {v8, v6, v9}, Landroid/content/BroadcastReceiver;->onReceive(Landroid/content/Context;Landroid/content/Intent;)V
    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, "PASS: popup inflated, video switch initialized, screen off/on receiver executed"
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V
    invoke-static {p0, v5}, Lhibreak/tests/PerAppControlsProbe;->run(Landroid/content/Context;Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;)V
    return-void
.end method
