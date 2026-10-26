.class public final Lcom/lmqr/ha9_comp_service/VideoRefreshSwitchListener;
.super Ljava/lang/Object;
.implements Landroid/widget/CompoundButton$OnCheckedChangeListener;

.field private final service:Lcom/lmqr/ha9_comp_service/A9AccessibilityService;

.method public constructor <init>(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Lcom/lmqr/ha9_comp_service/VideoRefreshSwitchListener;->service:Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    return-void
.end method

.method public onCheckedChanged(Landroid/widget/CompoundButton;Z)V
    .locals 1
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/VideoRefreshSwitchListener;->service:Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    invoke-virtual {v0, p2}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->setVideoOptimizedRefresh(Z)V
    return-void
.end method
