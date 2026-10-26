.class public final Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;
.super Landroid/hardware/camera2/CameraManager$AvailabilityCallback;
.implements Ljava/lang/Runnable;

.field private final service:Landroid/content/Context;
.field private final handler:Landroid/os/Handler;
.field private final busy:Ljava/util/HashSet;
.field private view:Landroid/view/View;
.field private toggle:Z
.field private screenOn:Z
.field private videoOptimized:Z

.method public constructor <init>(Landroid/content/Context;)V
    .locals 2
    invoke-direct {p0}, Landroid/hardware/camera2/CameraManager$AvailabilityCallback;-><init>()V
    iput-object p1, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->service:Landroid/content/Context;
    new-instance v0, Landroid/os/Handler;
    invoke-static {}, Landroid/os/Looper;->getMainLooper()Landroid/os/Looper;
    move-result-object v1
    invoke-direct {v0, v1}, Landroid/os/Handler;-><init>(Landroid/os/Looper;)V
    iput-object v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->handler:Landroid/os/Handler;
    new-instance v0, Ljava/util/HashSet;
    invoke-direct {v0}, Ljava/util/HashSet;-><init>()V
    iput-object v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->busy:Ljava/util/HashSet;
    const/4 v0, 0x1
    iput-boolean v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->screenOn:Z
    return-void
.end method

.method private cameraManager()Landroid/hardware/camera2/CameraManager;
    .locals 2
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->service:Landroid/content/Context;
    const-string v1, "camera"
    invoke-virtual {v0, v1}, Landroid/content/Context;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v0
    check-cast v0, Landroid/hardware/camera2/CameraManager;
    return-object v0
.end method

.method private windowManager()Landroid/view/WindowManager;
    .locals 2
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->service:Landroid/content/Context;
    const-string v1, "window"
    invoke-virtual {v0, v1}, Landroid/content/Context;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v0
    check-cast v0, Landroid/view/WindowManager;
    return-object v0
.end method

.method public final start()V
    .locals 3
    :try_start
    invoke-direct {p0}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->cameraManager()Landroid/hardware/camera2/CameraManager;
    move-result-object v0
    iget-object v1, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->handler:Landroid/os/Handler;
    invoke-virtual {v0, p0, v1}, Landroid/hardware/camera2/CameraManager;->registerAvailabilityCallback(Landroid/hardware/camera2/CameraManager$AvailabilityCallback;Landroid/os/Handler;)V
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :failed
    invoke-virtual {p0}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->update()V
    return-void
    :failed
    move-exception v0
    const-string v1, "CameraLiveRefresh"
    invoke-static {v1, v1, v0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    invoke-virtual {p0}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->update()V
    return-void
.end method

.method public final stop()V
    .locals 2
    :try_start
    invoke-direct {p0}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->cameraManager()Landroid/hardware/camera2/CameraManager;
    move-result-object v0
    invoke-virtual {v0, p0}, Landroid/hardware/camera2/CameraManager;->unregisterAvailabilityCallback(Landroid/hardware/camera2/CameraManager$AvailabilityCallback;)V
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :ignored
    :ignored
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->busy:Ljava/util/HashSet;
    invoke-virtual {v0}, Ljava/util/HashSet;->clear()V
    const/4 v0, 0x0
    iput-boolean v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->screenOn:Z
    invoke-virtual {p0}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->update()V
    return-void
.end method

.method public final setScreenOn(Z)V
    .locals 0
    iput-boolean p1, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->screenOn:Z
    invoke-virtual {p0}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->update()V
    return-void
.end method

.method public final setVideoOptimized(Z)V
    .locals 0
    iput-boolean p1, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->videoOptimized:Z
    invoke-virtual {p0}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->update()V
    return-void
.end method

.method public onCameraUnavailable(Ljava/lang/String;)V
    .locals 1
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->busy:Ljava/util/HashSet;
    invoke-virtual {v0, p1}, Ljava/util/HashSet;->add(Ljava/lang/Object;)Z
    invoke-virtual {p0}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->update()V
    return-void
.end method

.method public onCameraAvailable(Ljava/lang/String;)V
    .locals 1
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->busy:Ljava/util/HashSet;
    invoke-virtual {v0, p1}, Ljava/util/HashSet;->remove(Ljava/lang/Object;)Z
    invoke-virtual {p0}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->update()V
    return-void
.end method

.method public final update()V
    .locals 9
    iget-boolean v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->screenOn:Z
    if-eqz v0, :disable
    iget-boolean v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->videoOptimized:Z
    if-nez v0, :enable
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->busy:Ljava/util/HashSet;
    invoke-virtual {v0}, Ljava/util/HashSet;->isEmpty()Z
    move-result v0
    if-nez v0, :disable
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->service:Landroid/content/Context;
    invoke-static {v0}, Landroidx/preference/PreferenceManager;->getDefaultSharedPreferences(Landroid/content/Context;)Landroid/content/SharedPreferences;
    move-result-object v0
    const-string v1, "camera_live_refresh"
    const/4 v2, 0x1
    invoke-interface {v0, v1, v2}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z
    move-result v0
    if-eqz v0, :disable
    :enable
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->view:Landroid/view/View;
    if-nez v0, :done
    :try_start_add
    new-instance v0, Landroid/view/View;
    iget-object v1, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->service:Landroid/content/Context;
    invoke-direct {v0, v1}, Landroid/view/View;-><init>(Landroid/content/Context;)V
    const/high16 v1, 0x1000000
    invoke-virtual {v0, v1}, Landroid/view/View;->setBackgroundColor(I)V
    new-instance v1, Landroid/view/WindowManager$LayoutParams;
    const/4 v2, 0x1
    const/4 v3, 0x1
    const/16 v4, 0x7f0
    const/16 v5, 0x318
    const/4 v6, -0x3
    invoke-direct/range {v1 .. v6}, Landroid/view/WindowManager$LayoutParams;-><init>(IIIII)V
    const/16 v2, 0x33
    iput v2, v1, Landroid/view/WindowManager$LayoutParams;->gravity:I
    invoke-direct {p0}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->windowManager()Landroid/view/WindowManager;
    move-result-object v2
    invoke-interface {v2, v0, v1}, Landroid/view/WindowManager;->addView(Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V
    iput-object v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->view:Landroid/view/View;
    iget-object v1, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->handler:Landroid/os/Handler;
    invoke-virtual {v1, p0}, Landroid/os/Handler;->post(Ljava/lang/Runnable;)Z
    :try_end_add
    .catch Ljava/lang/Throwable; {:try_start_add .. :try_end_add} :add_failed
    goto :done
    :add_failed
    move-exception v0
    const-string v1, "CameraLiveRefresh"
    invoke-static {v1, v1, v0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    goto :done
    :disable
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->view:Landroid/view/View;
    if-eqz v0, :done
    iget-object v1, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->handler:Landroid/os/Handler;
    invoke-virtual {v1, p0}, Landroid/os/Handler;->removeCallbacks(Ljava/lang/Runnable;)V
    const/4 v1, 0x0
    iput-object v1, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->view:Landroid/view/View;
    :try_start_remove
    invoke-direct {p0}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->windowManager()Landroid/view/WindowManager;
    move-result-object v1
    invoke-interface {v1, v0}, Landroid/view/WindowManager;->removeView(Landroid/view/View;)V
    :try_end_remove
    .catch Ljava/lang/Throwable; {:try_start_remove .. :try_end_remove} :done
    :done
    return-void
.end method

.method public run()V
    .locals 4
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->view:Landroid/view/View;
    if-nez v0, :tick
    return-void
    :tick
    iget-boolean v1, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->toggle:Z
    xor-int/lit8 v1, v1, 0x1
    iput-boolean v1, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->toggle:Z
    const/high16 v2, 0x1000000
    if-eqz v1, :set
    const/high16 v2, 0x2000000
    :set
    invoke-virtual {v0, v2}, Landroid/view/View;->setBackgroundColor(I)V
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->handler:Landroid/os/Handler;
    const-wide/16 v2, 0x32
    invoke-virtual {v0, p0, v2, v3}, Landroid/os/Handler;->postDelayed(Ljava/lang/Runnable;J)Z
    return-void
.end method
