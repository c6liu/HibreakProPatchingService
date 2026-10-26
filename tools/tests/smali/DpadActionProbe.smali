.class public final Lhibreak/tests/DpadActionProbe;
.super Ljava/lang/Object;
.implements Ljava/lang/reflect/InvocationHandler;

.field private lastCommand:Ljava/lang/String;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method public invoke(Ljava/lang/Object;Ljava/lang/reflect/Method;[Ljava/lang/Object;)Ljava/lang/Object;
    .locals 2
    invoke-virtual {p2}, Ljava/lang/reflect/Method;->getName()Ljava/lang/String;
    move-result-object v0
    const-string v1, "runCommands"
    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v1
    if-eqz v1, :preference
    const/4 v0, 0x0
    aget-object v1, p3, v0
    check-cast v1, [Ljava/lang/String;
    aget-object v1, v1, v0
    iput-object v1, p0, Lhibreak/tests/DpadActionProbe;->lastCommand:Ljava/lang/String;
    const/4 v0, 0x0
    return-object v0
    :preference
    const-string v1, "getString"
    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :default_value
    invoke-virtual {p2}, Ljava/lang/reflect/Method;->getName()Ljava/lang/String;
    move-result-object v0
    const-string v1, "getBoolean"
    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v1
    if-nez v1, :default_value
    const-string v1, "getInt"
    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :unexpected
    :default_value
    const/4 v0, 0x1
    aget-object v0, p3, v0
    return-object v0
    :unexpected
    new-instance v0, Ljava/lang/AssertionError;
    invoke-direct {v0, p2}, Ljava/lang/AssertionError;-><init>(Ljava/lang/Object;)V
    throw v0
.end method

.method public static main([Ljava/lang/String;)V
    .locals 9
    new-instance v0, Lhibreak/tests/DpadActionProbe;
    invoke-direct {v0}, Lhibreak/tests/DpadActionProbe;-><init>()V
    const-class v1, Lhibreak/tests/DpadActionProbe;
    invoke-virtual {v1}, Ljava/lang/Class;->getClassLoader()Ljava/lang/ClassLoader;
    move-result-object v1
    const-class v2, Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;
    filled-new-array {v2}, [Ljava/lang/Class;
    move-result-object v2
    invoke-static {v1, v2, v0}, Ljava/lang/reflect/Proxy;->newProxyInstance(Ljava/lang/ClassLoader;[Ljava/lang/Class;Ljava/lang/reflect/InvocationHandler;)Ljava/lang/Object;
    move-result-object v2
    check-cast v2, Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;
    const-class v3, Landroid/content/SharedPreferences;
    filled-new-array {v3}, [Ljava/lang/Class;
    move-result-object v3
    invoke-static {v1, v3, v0}, Ljava/lang/reflect/Proxy;->newProxyInstance(Ljava/lang/ClassLoader;[Ljava/lang/Class;Ljava/lang/reflect/InvocationHandler;)Ljava/lang/Object;
    move-result-object v3
    check-cast v3, Landroid/content/SharedPreferences;
    new-instance v4, Lcom/lmqr/ha9_comp_service/RefreshModeManager;
    invoke-direct {v4, v3, v2}, Lcom/lmqr/ha9_comp_service/RefreshModeManager;-><init>(Landroid/content/SharedPreferences;Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;)V
    new-instance v3, Lcom/lmqr/ha9_comp_service/button_mapper/ButtonActionManager;
    invoke-direct {v3, v2, v4}, Lcom/lmqr/ha9_comp_service/button_mapper/ButtonActionManager;-><init>(Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;Lcom/lmqr/ha9_comp_service/RefreshModeManager;)V
    const-class v1, Lcom/lmqr/ha9_comp_service/button_mapper/ButtonActionManager;
    const-string v2, "buttonCommands"
    invoke-virtual {v1, v2}, Ljava/lang/Class;->getDeclaredField(Ljava/lang/String;)Ljava/lang/reflect/Field;
    move-result-object v1
    const/4 v2, 0x1
    invoke-virtual {v1, v2}, Ljava/lang/reflect/Field;->setAccessible(Z)V
    invoke-virtual {v1, v3}, Ljava/lang/reflect/Field;->get(Ljava/lang/Object;)Ljava/lang/Object;
    move-result-object v1
    check-cast v1, Ljava/util/Map;
    const-string v2, "dpad_up"
    const-string v3, "dpad_down"
    const-string v4, "dpad_left"
    const-string v5, "dpad_right"
    filled-new-array {v2, v3, v4, v5}, [Ljava/lang/String;
    move-result-object v2
    const/4 v3, 0x0
    :next
    array-length v4, v2
    if-ge v3, v4, :passed
    aget-object v4, v2, v3
    const/4 v5, 0x0
    iput-object v5, v0, Lhibreak/tests/DpadActionProbe;->lastCommand:Ljava/lang/String;
    invoke-interface {v1, v4}, Ljava/util/Map;->get(Ljava/lang/Object;)Ljava/lang/Object;
    move-result-object v6
    check-cast v6, Lcom/lmqr/ha9_comp_service/button_mapper/ButtonAction;
    invoke-interface {v6, v5}, Lcom/lmqr/ha9_comp_service/button_mapper/ButtonAction;->execute(Landroid/content/Context;)V
    iget-object v6, v0, Lhibreak/tests/DpadActionProbe;->lastCommand:Ljava/lang/String;
    invoke-virtual {v4, v6}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v5
    if-nez v5, :matched
    new-instance v5, Ljava/lang/AssertionError;
    invoke-direct {v5, v4}, Ljava/lang/AssertionError;-><init>(Ljava/lang/Object;)V
    throw v5
    :matched
    add-int/lit8 v3, v3, 0x1
    goto :next
    :passed
    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, "PASS: all four DPAD actions dispatched through the supplied command runner"
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V
    return-void
.end method
