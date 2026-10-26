.class public final Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;
.super Landroid/content/BroadcastReceiver;

.field private final service:Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
.field private final owners:[I
.field private final screenOn:[Z

.method public constructor <init>(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;)V
    .locals 6
    invoke-direct {p0}, Landroid/content/BroadcastReceiver;-><init>()V
    iput-object p1, p0, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->service:Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    const/4 v0, 0x2
    new-array v1, v0, [I
    iput-object v1, p0, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->owners:[I
    new-array v1, v0, [Z
    const/4 v2, 0x0
    const/4 v3, 0x1
    aput-boolean v3, v1, v2
    aput-boolean v3, v1, v3
    iput-object v1, p0, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->screenOn:[Z
    move-object v0, p1
    move-object v1, p0
    new-instance v2, Landroid/content/IntentFilter;
    const-string v3, "com.lmqr.ha9_comp_service.SCREEN_OFF_KEY"
    invoke-direct {v2, v3}, Landroid/content/IntentFilter;-><init>(Ljava/lang/String;)V
    const-string v3, "android.permission.INJECT_EVENTS"
    const/4 v4, 0x0
    const/4 v5, 0x2
    invoke-virtual/range {v0 .. v5}, Landroid/content/Context;->registerReceiver(Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;Ljava/lang/String;Landroid/os/Handler;I)Landroid/content/Intent;
    return-void
.end method

.method public onReceive(Landroid/content/Context;Landroid/content/Intent;)V
    .locals 10
    invoke-virtual {p2}, Landroid/content/Intent;->getAction()Ljava/lang/String;
    move-result-object v0
    const-string v1, "com.lmqr.ha9_comp_service.SCREEN_OFF_KEY"
    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :done
    const/4 v0, -0x1
    const-string v1, "scan_code"
    invoke-virtual {p2, v1, v0}, Landroid/content/Intent;->getIntExtra(Ljava/lang/String;I)I
    move-result v3
    const/16 v1, 0x3b
    if-lt v3, v1, :invalid
    const/16 v1, 0x3c
    if-gt v3, v1, :invalid
    const-string v1, "key_action"
    invoke-virtual {p2, v1, v0}, Landroid/content/Intent;->getIntExtra(Ljava/lang/String;I)I
    move-result v4
    if-ltz v4, :invalid
    const/4 v0, 0x1
    if-gt v4, v0, :invalid
    const-string v1, "event_time"
    const-wide/16 v5, -0x1
    invoke-virtual {p2, v1, v5, v6}, Landroid/content/Intent;->getLongExtra(Ljava/lang/String;J)J
    move-result-wide v5
    const-wide/16 v7, 0x0
    cmp-long v0, v5, v7
    if-ltz v0, :invalid
    invoke-static {}, Landroid/os/SystemClock;->uptimeMillis()J
    move-result-wide v0
    sub-long/2addr v0, v5
    cmp-long v2, v0, v7
    if-ltz v2, :invalid
    const-wide/16 v7, 0x1388
    cmp-long v2, v0, v7
    if-gtz v2, :invalid
    move-object v2, p0
    const/4 v7, 0x1
    invoke-direct/range {v2 .. v7}, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->dispatch(IIJZ)V
    :done
    return-void
    :invalid
    const-string v0, "A9ScreenOffKey"
    const-string v1, "Invalid or stale daemon side-key event"
    invoke-static {v0, v1}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I
    return-void
.end method

.method public onKeyEvent(Landroid/view/KeyEvent;)Z
    .locals 6
    invoke-virtual {p1}, Landroid/view/KeyEvent;->getScanCode()I
    move-result v1
    const/16 v0, 0x3b
    if-lt v1, v0, :other
    const/16 v0, 0x3c
    if-gt v1, v0, :other
    invoke-virtual {p1}, Landroid/view/KeyEvent;->getRepeatCount()I
    move-result v0
    if-nez v0, :consumed
    move-object v0, p0
    invoke-virtual {p1}, Landroid/view/KeyEvent;->getAction()I
    move-result v2
    invoke-virtual {p1}, Landroid/view/KeyEvent;->getEventTime()J
    move-result-wide v3
    const/4 v5, 0x0
    invoke-direct/range {v0 .. v5}, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->dispatch(IIJZ)V
    :consumed
    const/4 v0, 0x1
    return v0
    :other
    const/4 v0, 0x0
    return v0
.end method

.method private dispatch(IIJZ)V
    .locals 6
    add-int/lit8 v0, p1, -0x3b
    const/4 v1, 0x1
    if-eqz p5, :owner_ready
    const/4 v1, 0x2
    :owner_ready
    iget-object v2, p0, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->owners:[I
    aget v3, v2, v0
    if-nez p2, :up
    if-nez v3, :done
    iget-object v3, p0, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->service:Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    const-string v4, "power"
    invoke-virtual {v3, v4}, Landroid/content/Context;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v3
    check-cast v3, Landroid/os/PowerManager;
    invoke-virtual {v3}, Landroid/os/PowerManager;->isInteractive()Z
    move-result v3
    if-eq p5, v3, :done
    aput v1, v2, v0
    iget-object v4, p0, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->screenOn:[Z
    aput-boolean v3, v4, v0
    goto :dispatch
    :up
    const/4 v4, 0x1
    if-ne p2, v4, :done
    if-ne v3, v1, :done
    :dispatch
    iget-object v1, p0, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->service:Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    invoke-virtual {v1, p1, p2, p3, p4}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->dispatchSideKey(IIJ)V
    if-eqz p2, :done
    const/4 v1, 0x0
    aput v1, v2, v0
    :done
    return-void
.end method

.method public isScreenOn(I)Z
    .locals 1
    add-int/lit8 p1, p1, -0x3b
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->screenOn:[Z
    aget-boolean v0, v0, p1
    return v0
.end method

.method public close()V
    .locals 1
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->service:Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    invoke-virtual {v0, p0}, Landroid/content/Context;->unregisterReceiver(Landroid/content/BroadcastReceiver;)V
    return-void
.end method
