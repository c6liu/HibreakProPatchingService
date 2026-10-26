.class public final Lhibreak/tests/RuntimeInstrumentation;
.super Landroid/app/Instrumentation;
.implements Ljava/lang/Runnable;

.field private failure:Ljava/lang/Throwable;

.field private settingsActivity:Landroid/app/Activity;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Landroid/app/Instrumentation;-><init>()V
    return-void
.end method

.method public onCreate(Landroid/os/Bundle;)V
    .locals 0
    invoke-super {p0, p1}, Landroid/app/Instrumentation;->onCreate(Landroid/os/Bundle;)V
    invoke-virtual {p0}, Landroid/app/Instrumentation;->start()V
    return-void
.end method

.method public onStart()V
    .locals 4
    invoke-virtual {p0}, Landroid/app/Instrumentation;->getTargetContext()Landroid/content/Context;
    move-result-object v0
    new-instance v1, Landroid/content/Intent;
    const-class v2, Lhibreak/tests/SettingsActivityProbe;
    invoke-direct {v1, v0, v2}, Landroid/content/Intent;-><init>(Landroid/content/Context;Ljava/lang/Class;)V
    const v0, 0x10000000
    invoke-virtual {v1, v0}, Landroid/content/Intent;->addFlags(I)Landroid/content/Intent;
    invoke-virtual {p0, v1}, Landroid/app/Instrumentation;->startActivitySync(Landroid/content/Intent;)Landroid/app/Activity;
    move-result-object v0
    iput-object v0, p0, Lhibreak/tests/RuntimeInstrumentation;->settingsActivity:Landroid/app/Activity;
    invoke-virtual {p0, p0}, Landroid/app/Instrumentation;->runOnMainSync(Ljava/lang/Runnable;)V
    new-instance v0, Landroid/os/Bundle;
    invoke-direct {v0}, Landroid/os/Bundle;-><init>()V
    iget-object v1, p0, Lhibreak/tests/RuntimeInstrumentation;->failure:Ljava/lang/Throwable;
    const-string v2, "stream"
    if-eqz v1, :success
    invoke-static {v1}, Landroid/util/Log;->getStackTraceString(Ljava/lang/Throwable;)Ljava/lang/String;
    move-result-object v1
    invoke-virtual {v0, v2, v1}, Landroid/os/Bundle;->putString(Ljava/lang/String;Ljava/lang/String;)V
    const/4 v3, 0x0
    invoke-virtual {p0, v3, v0}, Landroid/app/Instrumentation;->finish(ILandroid/os/Bundle;)V
    return-void
    :success
    const-string v1, "PASS: DPAD dispatch, popup inflation and switch setup, screen off/on receiver, settings startup and 12 app-launch pickers"
    invoke-virtual {v0, v2, v1}, Landroid/os/Bundle;->putString(Ljava/lang/String;Ljava/lang/String;)V
    const/4 v3, -0x1
    invoke-virtual {p0, v3, v0}, Landroid/app/Instrumentation;->finish(ILandroid/os/Bundle;)V
    return-void
.end method

.method public run()V
    .locals 1
    :try_start
    const/4 v0, 0x0
    invoke-static {v0}, Lhibreak/tests/DpadActionProbe;->main([Ljava/lang/String;)V
    invoke-virtual {p0}, Landroid/app/Instrumentation;->getTargetContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0}, Lhibreak/tests/PopupProbe;->run(Landroid/content/Context;)V
    iget-object v0, p0, Lhibreak/tests/RuntimeInstrumentation;->settingsActivity:Landroid/app/Activity;
    invoke-virtual {v0}, Landroid/app/Activity;->finish()V
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :failed
    return-void
    :failed
    move-exception v0
    iput-object v0, p0, Lhibreak/tests/RuntimeInstrumentation;->failure:Ljava/lang/Throwable;
    return-void
.end method
