.class public final Lcom/lmqr/ha9_comp_service/PerAppRefreshPagePreference;
.super Landroidx/preference/Preference;

.method public constructor <init>(Landroid/content/Context;Landroid/util/AttributeSet;)V
    .locals 0
    invoke-direct {p0, p1, p2}, Landroidx/preference/Preference;-><init>(Landroid/content/Context;Landroid/util/AttributeSet;)V
    return-void
.end method

.method protected onClick()V
    .locals 3
    invoke-virtual {p0}, Landroidx/preference/Preference;->getContext()Landroid/content/Context;
    move-result-object v0
    new-instance v1, Landroid/content/Intent;
    const-class v2, Lcom/lmqr/ha9_comp_service/SettingsActivity;
    invoke-direct {v1, v0, v2}, Landroid/content/Intent;-><init>(Landroid/content/Context;Ljava/lang/Class;)V
    const-string v2, "per_app_page"
    const/4 p0, 0x1
    invoke-virtual {v1, v2, p0}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Z)Landroid/content/Intent;
    invoke-virtual {v0, v1}, Landroid/content/Context;->startActivity(Landroid/content/Intent;)V
    return-void
.end method
