.class public final Lhibreak/tests/RuntimeInstrumentation;
.super Landroid/app/Instrumentation;
.implements Ljava/lang/Runnable;

.field private failure:Ljava/lang/Throwable;

.field private settingsActivity:Landroid/app/Activity;
.field private wakeTest:Z
.field private launchMonitor:Landroid/app/Instrumentation$ActivityMonitor;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Landroid/app/Instrumentation;-><init>()V
    return-void
.end method

.method public onCreate(Landroid/os/Bundle;)V
    .locals 1
    invoke-super {p0, p1}, Landroid/app/Instrumentation;->onCreate(Landroid/os/Bundle;)V
    const-string v0, "wake_test"
    invoke-virtual {p1, v0}, Landroid/os/Bundle;->getString(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v0
    if-eqz v0, :start
    const/4 v0, 0x1
    iput-boolean v0, p0, Lhibreak/tests/RuntimeInstrumentation;->wakeTest:Z
    :start
    invoke-virtual {p0}, Landroid/app/Instrumentation;->start()V
    return-void
.end method

.method public onStart()V
    .locals 4
    iget-boolean v0, p0, Lhibreak/tests/RuntimeInstrumentation;->wakeTest:Z
    if-eqz v0, :start_settings
    const-string v0, "hibreak.tests.SettingsActivityProbe"
    const/4 v1, 0x0
    const/4 v2, 0x0
    invoke-virtual {p0, v0, v1, v2}, Landroid/app/Instrumentation;->addMonitor(Ljava/lang/String;Landroid/app/Instrumentation$ActivityResult;Z)Landroid/app/Instrumentation$ActivityMonitor;
    move-result-object v0
    iput-object v0, p0, Lhibreak/tests/RuntimeInstrumentation;->launchMonitor:Landroid/app/Instrumentation$ActivityMonitor;
    goto :run_probe
    :start_settings
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
    :run_probe
    invoke-virtual {p0, p0}, Landroid/app/Instrumentation;->runOnMainSync(Ljava/lang/Runnable;)V
    iget-boolean v0, p0, Lhibreak/tests/RuntimeInstrumentation;->wakeTest:Z
    if-eqz v0, :report
    iget-object v0, p0, Lhibreak/tests/RuntimeInstrumentation;->failure:Ljava/lang/Throwable;
    if-nez v0, :report
    iget-object v0, p0, Lhibreak/tests/RuntimeInstrumentation;->launchMonitor:Landroid/app/Instrumentation$ActivityMonitor;
    const-wide/16 v1, 0x1388
    invoke-virtual {p0, v0, v1, v2}, Landroid/app/Instrumentation;->waitForMonitorWithTimeout(Landroid/app/Instrumentation$ActivityMonitor;J)Landroid/app/Activity;
    move-result-object v0
    if-nez v0, :report
    new-instance v0, Ljava/lang/AssertionError;
    const-string v1, "Screen-off app launch did not start the target activity"
    invoke-direct {v0, v1}, Ljava/lang/AssertionError;-><init>(Ljava/lang/Object;)V
    iput-object v0, p0, Lhibreak/tests/RuntimeInstrumentation;->failure:Ljava/lang/Throwable;
    :report
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
    iget-boolean v1, p0, Lhibreak/tests/RuntimeInstrumentation;->wakeTest:Z
    if-eqz v1, :normal_success
    const-string v1, "PASS: screen-off app launch wakes display"
    goto :report_success
    :normal_success
    const-string v1, "PASS: DPAD dispatch, popup inflation and switch setup, screen off/on receiver, settings startup and 12 app-launch pickers"
    :report_success
    invoke-virtual {v0, v2, v1}, Landroid/os/Bundle;->putString(Ljava/lang/String;Ljava/lang/String;)V
    const/4 v3, -0x1
    invoke-virtual {p0, v3, v0}, Landroid/app/Instrumentation;->finish(ILandroid/os/Bundle;)V
    return-void
.end method

.method public run()V
    .locals 1
    :try_start
    iget-boolean v0, p0, Lhibreak/tests/RuntimeInstrumentation;->wakeTest:Z
    if-eqz v0, :normal_probe
    invoke-virtual {p0}, Landroid/app/Instrumentation;->getTargetContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0}, Lhibreak/tests/ScreenOffLaunchProbe;->run(Landroid/content/Context;)V
    goto :probe_done
    :normal_probe
    const/4 v0, 0x0
    invoke-static {v0}, Lhibreak/tests/DpadActionProbe;->main([Ljava/lang/String;)V
    invoke-virtual {p0}, Landroid/app/Instrumentation;->getTargetContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0}, Lhibreak/tests/PopupProbe;->run(Landroid/content/Context;)V
    iget-object v0, p0, Lhibreak/tests/RuntimeInstrumentation;->settingsActivity:Landroid/app/Activity;
    invoke-virtual {v0}, Landroid/app/Activity;->finish()V
    :probe_done
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :failed
    return-void
    :failed
    move-exception v0
    iput-object v0, p0, Lhibreak/tests/RuntimeInstrumentation;->failure:Ljava/lang/Throwable;
    return-void
.end method
