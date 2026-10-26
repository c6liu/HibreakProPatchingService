.class public final Lcom/lmqr/ha9_comp_service/PerAppRefreshPreference;
.super Landroidx/preference/ListPreference;

.method public constructor <init>(Landroid/content/Context;)V
    .locals 1
    const/4 v0, 0x0
    invoke-direct {p0, p1, v0}, Landroidx/preference/ListPreference;-><init>(Landroid/content/Context;Landroid/util/AttributeSet;)V
    return-void
.end method

# RefreshModeManager and the popup use integer preferences.
.method protected persistString(Ljava/lang/String;)Z
    .locals 2
    const-string v0, "-1"
    invoke-virtual {v0, p1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :mode
    invoke-virtual {p0}, Landroidx/preference/Preference;->getSharedPreferences()Landroid/content/SharedPreferences;
    move-result-object v0
    invoke-interface {v0}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v0
    invoke-virtual {p0}, Landroidx/preference/Preference;->getKey()Ljava/lang/String;
    move-result-object v1
    invoke-interface {v0, v1}, Landroid/content/SharedPreferences$Editor;->remove(Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v0}, Landroid/content/SharedPreferences$Editor;->apply()V
    const/4 v0, 0x1
    return v0
    :mode
    invoke-static {p1}, Ljava/lang/Integer;->parseInt(Ljava/lang/String;)I
    move-result v0
    invoke-virtual {p0, v0}, Landroidx/preference/Preference;->persistInt(I)Z
    move-result v0
    return v0
.end method

.method protected getPersistedString(Ljava/lang/String;)Ljava/lang/String;
    .locals 1
    const/4 v0, -0x1
    invoke-virtual {p0, v0}, Landroidx/preference/Preference;->getPersistedInt(I)I
    move-result v0
    invoke-static {v0}, Ljava/lang/Integer;->toString(I)Ljava/lang/String;
    move-result-object v0
    return-object v0
.end method
