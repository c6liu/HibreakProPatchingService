.class public final Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;
.super Ljava/lang/Object;
.implements Landroid/widget/CompoundButton$OnCheckedChangeListener;

.field private final prefs:Landroid/content/SharedPreferences;
.field private final runner:Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;
.field private packageName:Ljava/lang/String;
.field private service:Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
.field private final switches:[Landroid/widget/CompoundButton;

.method public constructor <init>(Landroid/content/SharedPreferences;Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;)V
    .locals 1
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->prefs:Landroid/content/SharedPreferences;
    iput-object p2, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->runner:Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;
    const-string v0, ""
    iput-object v0, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->packageName:Ljava/lang/String;
    const/4 v0, 0x3
    new-array v0, v0, [Landroid/widget/CompoundButton;
    iput-object v0, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->switches:[Landroid/widget/CompoundButton;
    return-void
.end method

.method public final attach(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;)V
    .locals 0
    iput-object p1, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->service:Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    return-void
.end method

.method private name(I)Ljava/lang/String;
    .locals 1
    const-string v0, "auto_refresh_enabled"
    if-eqz p1, :done
    const/4 v0, 0x1
    if-ne p1, v0, :video
    const-string v0, "anti_shake_enabled"
    return-object v0
    :video
    const-string v0, "video_optimized_refresh"
    :done
    return-object v0
.end method

.method private key(I)Ljava/lang/String;
    .locals 2
    new-instance v0, Ljava/lang/StringBuilder;
    const-string v1, "display:"
    invoke-direct {v0, v1}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V
    iget-object v1, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->packageName:Ljava/lang/String;
    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v1, ":"
    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-direct {p0, p1}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->name(I)Ljava/lang/String;
    move-result-object v1
    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v0
    return-object v0
.end method

.method private get(I)Z
    .locals 4
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->prefs:Landroid/content/SharedPreferences;
    const/4 v1, 0x0
    const/4 v2, 0x2
    if-ge p1, v2, :read
    const/4 v1, 0x1
    invoke-direct {p0, p1}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->name(I)Ljava/lang/String;
    move-result-object v2
    invoke-interface {v0, v2, v1}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z
    move-result v1
    :read
    invoke-direct {p0, p1}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->key(I)Ljava/lang/String;
    move-result-object v2
    invoke-interface {v0, v2, v1}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z
    move-result v0
    return v0
.end method

.method public final isAutoRefreshEnabled()Z
    .locals 1
    const/4 v0, 0x0
    invoke-direct {p0, v0}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->get(I)Z
    move-result v0
    return v0
.end method

.method public final isAntiShakeEnabled()Z
    .locals 1
    const/4 v0, 0x1
    invoke-direct {p0, v0}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->get(I)Z
    move-result v0
    return v0
.end method

.method public final isVideoOptimizedEnabled()Z
    .locals 1
    const/4 v0, 0x2
    invoke-direct {p0, v0}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->get(I)Z
    move-result v0
    return v0
.end method

.method public final applySettings()V
    .locals 4
    invoke-virtual {p0}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->isAutoRefreshEnabled()Z
    move-result v0
    const-string v1, "au_br0"
    if-eqz v0, :auto_ready
    const-string v1, "au_br1"
    :auto_ready
    invoke-virtual {p0}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->isAntiShakeEnabled()Z
    move-result v0
    const-string v2, "an_fl0"
    if-eqz v0, :anti_ready
    const-string v2, "an_fl1"
    :anti_ready
    filled-new-array {v1, v2}, [Ljava/lang/String;
    move-result-object v1
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->runner:Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;
    invoke-interface {v0, v1}, Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;->runCommands([Ljava/lang/String;)V
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->service:Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    if-eqz v0, :done
    invoke-virtual {p0}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->isVideoOptimizedEnabled()Z
    move-result v1
    invoke-virtual {v0, v1}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->setVideoOptimizedRefresh(Z)V
    :done
    return-void
.end method

.method public final onAppChange(Ljava/lang/String;)V
    .locals 1
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->packageName:Ljava/lang/String;
    invoke-virtual {p1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :done
    iput-object p1, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->packageName:Ljava/lang/String;
    invoke-virtual {p0}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->applySettings()V
    invoke-direct {p0}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->bind()V
    :done
    return-void
.end method

.method public final setupSwitches(Landroid/widget/CompoundButton;Landroid/widget/CompoundButton;)V
    .locals 2
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->switches:[Landroid/widget/CompoundButton;
    const/4 v1, 0x0
    aput-object p1, v0, v1
    const/4 v1, 0x1
    aput-object p2, v0, v1
    invoke-direct {p0}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->bind()V
    return-void
.end method

.method public final setupVideo(Landroid/widget/CompoundButton;)V
    .locals 2
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->switches:[Landroid/widget/CompoundButton;
    const/4 v1, 0x2
    aput-object p1, v0, v1
    invoke-direct {p0}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->bind()V
    return-void
.end method

.method private bind()V
    .locals 5
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->switches:[Landroid/widget/CompoundButton;
    const/4 v1, 0x0
    :next
    const/4 v2, 0x3
    if-ge v1, v2, :done
    aget-object v2, v0, v1
    if-eqz v2, :advance
    const/4 v3, 0x0
    invoke-virtual {v2, v3}, Landroid/widget/CompoundButton;->setOnCheckedChangeListener(Landroid/widget/CompoundButton$OnCheckedChangeListener;)V
    invoke-direct {p0, v1}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->get(I)Z
    move-result v3
    invoke-virtual {v2, v3}, Landroid/widget/CompoundButton;->setChecked(Z)V
    iget-object v3, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->packageName:Ljava/lang/String;
    invoke-virtual {v3}, Ljava/lang/String;->isEmpty()Z
    move-result v3
    xor-int/lit8 v3, v3, 0x1
    invoke-virtual {v2, v3}, Landroid/widget/CompoundButton;->setEnabled(Z)V
    invoke-virtual {v2, p0}, Landroid/widget/CompoundButton;->setOnCheckedChangeListener(Landroid/widget/CompoundButton$OnCheckedChangeListener;)V
    :advance
    add-int/lit8 v1, v1, 0x1
    goto :next
    :done
    return-void
.end method

.method public onCheckedChanged(Landroid/widget/CompoundButton;Z)V
    .locals 4
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->packageName:Ljava/lang/String;
    invoke-virtual {v0}, Ljava/lang/String;->isEmpty()Z
    move-result v0
    if-nez v0, :invalid
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->switches:[Landroid/widget/CompoundButton;
    const/4 v1, 0x0
    :next
    const/4 v2, 0x3
    if-ge v1, v2, :invalid
    aget-object v2, v0, v1
    if-eq v2, p1, :save
    add-int/lit8 v1, v1, 0x1
    goto :next
    :save
    invoke-direct {p0, v1}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->key(I)Ljava/lang/String;
    move-result-object v1
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->prefs:Landroid/content/SharedPreferences;
    invoke-interface {v0}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v0
    invoke-interface {v0, v1, p2}, Landroid/content/SharedPreferences$Editor;->putBoolean(Ljava/lang/String;Z)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v0}, Landroid/content/SharedPreferences$Editor;->apply()V
    invoke-virtual {p0}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->applySettings()V
    return-void
    :invalid
    new-instance v0, Ljava/lang/IllegalStateException;
    const-string v1, "No active app for display controls"
    invoke-direct {v0, v1}, Ljava/lang/IllegalStateException;-><init>(Ljava/lang/String;)V
    throw v0
.end method
