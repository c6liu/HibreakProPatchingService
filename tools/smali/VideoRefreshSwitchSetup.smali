.class public final Lcom/lmqr/ha9_comp_service/VideoRefreshSwitchSetup;
.super Ljava/lang/Object;

.method public static setup(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;Landroid/widget/Switch;)V
    .locals 3
    invoke-static {p0}, Landroidx/preference/PreferenceManager;->getDefaultSharedPreferences(Landroid/content/Context;)Landroid/content/SharedPreferences;
    move-result-object v0
    const-string v1, "video_optimized_refresh"
    const/4 v2, 0x0
    invoke-interface {v0, v1, v2}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z
    move-result v2
    invoke-virtual {p1, v2}, Landroid/widget/CompoundButton;->setChecked(Z)V
    new-instance v0, Lcom/lmqr/ha9_comp_service/VideoRefreshSwitchListener;
    invoke-direct {v0, p0}, Lcom/lmqr/ha9_comp_service/VideoRefreshSwitchListener;-><init>(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;)V
    invoke-virtual {p1, v0}, Landroid/widget/CompoundButton;->setOnCheckedChangeListener(Landroid/widget/CompoundButton$OnCheckedChangeListener;)V
    return-void
.end method
