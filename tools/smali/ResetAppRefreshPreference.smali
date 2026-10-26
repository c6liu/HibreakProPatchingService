.class public final Lcom/lmqr/ha9_comp_service/ResetAppRefreshPreference;
.super Landroidx/preference/Preference;
.implements Landroid/content/DialogInterface$OnClickListener;

.method public constructor <init>(Landroid/content/Context;Landroid/util/AttributeSet;)V
    .locals 0
    invoke-direct {p0, p1, p2}, Landroidx/preference/Preference;-><init>(Landroid/content/Context;Landroid/util/AttributeSet;)V
    return-void
.end method

.method protected onClick()V
    .locals 3
    invoke-virtual {p0}, Landroidx/preference/Preference;->getContext()Landroid/content/Context;
    move-result-object v0
    new-instance v1, Landroid/app/AlertDialog$Builder;
    invoke-direct {v1, v0}, Landroid/app/AlertDialog$Builder;-><init>(Landroid/content/Context;)V
    const-string v0, "Reset all to default?"
    invoke-virtual {v1, v0}, Landroid/app/AlertDialog$Builder;->setTitle(Ljava/lang/CharSequence;)Landroid/app/AlertDialog$Builder;
    const-string v0, "Remove all saved per-app refresh modes? Apps will use Default Refresh Mode. Other settings will not change."
    invoke-virtual {v1, v0}, Landroid/app/AlertDialog$Builder;->setMessage(Ljava/lang/CharSequence;)Landroid/app/AlertDialog$Builder;
    const v0, 0x1040000
    const/4 v2, 0x0
    invoke-virtual {v1, v0, v2}, Landroid/app/AlertDialog$Builder;->setNegativeButton(ILandroid/content/DialogInterface$OnClickListener;)Landroid/app/AlertDialog$Builder;
    const-string v0, "Reset"
    invoke-virtual {v1, v0, p0}, Landroid/app/AlertDialog$Builder;->setPositiveButton(Ljava/lang/CharSequence;Landroid/content/DialogInterface$OnClickListener;)Landroid/app/AlertDialog$Builder;
    invoke-virtual {v1}, Landroid/app/AlertDialog$Builder;->show()Landroid/app/AlertDialog;
    return-void
.end method

.method public onClick(Landroid/content/DialogInterface;I)V
    .locals 6
    invoke-virtual {p0}, Landroidx/preference/Preference;->getSharedPreferences()Landroid/content/SharedPreferences;
    move-result-object v0
    invoke-interface {v0}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v1
    invoke-interface {v0}, Landroid/content/SharedPreferences;->getAll()Ljava/util/Map;
    move-result-object v0
    invoke-interface {v0}, Ljava/util/Map;->keySet()Ljava/util/Set;
    move-result-object v0
    invoke-interface {v0}, Ljava/util/Set;->iterator()Ljava/util/Iterator;
    move-result-object v0
    :next_key
    invoke-interface {v0}, Ljava/util/Iterator;->hasNext()Z
    move-result v2
    if-eqz v2, :apply
    invoke-interface {v0}, Ljava/util/Iterator;->next()Ljava/lang/Object;
    move-result-object v2
    check-cast v2, Ljava/lang/String;
    const-string v3, "package:"
    invoke-virtual {v2, v3}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z
    move-result v3
    if-eqz v3, :next_key
    const-string v3, "package:None"
    invoke-virtual {v2, v3}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v3
    if-nez v3, :next_key
    invoke-interface {v1, v2}, Landroid/content/SharedPreferences$Editor;->remove(Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    goto :next_key
    :apply
    invoke-interface {v1}, Landroid/content/SharedPreferences$Editor;->apply()V
    invoke-virtual {p0}, Landroidx/preference/Preference;->getPreferenceManager()Landroidx/preference/PreferenceManager;
    move-result-object v0
    const-string v1, "per_app_apps"
    invoke-virtual {v0, v1}, Landroidx/preference/PreferenceManager;->findPreference(Ljava/lang/CharSequence;)Landroidx/preference/Preference;
    move-result-object v0
    check-cast v0, Landroidx/preference/PreferenceCategory;
    const/4 v1, 0x0
    invoke-virtual {v0}, Landroidx/preference/PreferenceGroup;->getPreferenceCount()I
    move-result v2
    :next_app
    if-ge v1, v2, :done
    invoke-virtual {v0, v1}, Landroidx/preference/PreferenceGroup;->getPreference(I)Landroidx/preference/Preference;
    move-result-object v3
    check-cast v3, Landroidx/preference/ListPreference;
    const-string v4, "-1"
    invoke-virtual {v3, v4}, Landroidx/preference/ListPreference;->setValue(Ljava/lang/String;)V
    add-int/lit8 v1, v1, 0x1
    goto :next_app
    :done
    return-void
.end method
