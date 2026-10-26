.class public final Lcom/lmqr/ha9_comp_service/PerAppRefreshSettings;
.super Ljava/lang/Object;

.method private static prepend(Ljava/lang/String;[Ljava/lang/CharSequence;)[Ljava/lang/CharSequence;
    .locals 4
    array-length v0, p1
    add-int/lit8 v1, v0, 0x1
    new-array v1, v1, [Ljava/lang/CharSequence;
    const/4 v2, 0x0
    aput-object p0, v1, v2
    const/4 v3, 0x1
    invoke-static {p1, v2, v1, v3, v0}, Ljava/lang/System;->arraycopy(Ljava/lang/Object;ILjava/lang/Object;II)V
    return-object v1
.end method

.method public static populate(Landroidx/preference/PreferenceFragmentCompat;)V
    .locals 12
    invoke-virtual {p0}, Landroidx/fragment/app/Fragment;->requireActivity()Landroidx/fragment/app/FragmentActivity;
    move-result-object v2
    invoke-virtual {v2}, Landroid/app/Activity;->getIntent()Landroid/content/Intent;
    move-result-object v3
    const-string v4, "per_app_page"
    const/4 v1, 0x0
    invoke-virtual {v3, v4, v1}, Landroid/content/Intent;->getBooleanExtra(Ljava/lang/String;Z)Z
    move-result v3
    if-nez v3, :page
    return-void
    :page
    const v3, @PER_APP_XML@
    const/4 v4, 0x0
    invoke-virtual {p0, v3, v4}, Landroidx/preference/PreferenceFragmentCompat;->setPreferencesFromResource(ILjava/lang/String;)V
    const v3, @TOOLBAR_ID@
    invoke-virtual {v2, v3}, Landroid/app/Activity;->findViewById(I)Landroid/view/View;
    move-result-object v3
    check-cast v3, Landroidx/appcompat/widget/Toolbar;
    const-string v4, "Per-App Refresh Modes"
    invoke-virtual {v3, v4}, Landroidx/appcompat/widget/Toolbar;->setTitle(Ljava/lang/CharSequence;)V
    const-string v0, "per_app_apps"
    invoke-virtual {p0, v0}, Landroidx/preference/PreferenceFragmentCompat;->findPreference(Ljava/lang/CharSequence;)Landroidx/preference/Preference;
    move-result-object v0
    check-cast v0, Landroidx/preference/PreferenceCategory;
    const/4 v1, 0x0
    invoke-virtual {v0, v1}, Landroidx/preference/PreferenceGroup;->setOrderingAsAdded(Z)V
    invoke-virtual {v0}, Landroidx/preference/Preference;->getContext()Landroid/content/Context;
    move-result-object v2
    invoke-virtual {v2}, Landroid/content/Context;->getPackageManager()Landroid/content/pm/PackageManager;
    move-result-object v3
    invoke-virtual {v2}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;
    move-result-object v4
    const v5, @REFRESH_OPTIONS@
    invoke-virtual {v4, v5}, Landroid/content/res/Resources;->getTextArray(I)[Ljava/lang/CharSequence;
    move-result-object v5
    const-string v6, "Use default"
    invoke-static {v6, v5}, Lcom/lmqr/ha9_comp_service/PerAppRefreshSettings;->prepend(Ljava/lang/String;[Ljava/lang/CharSequence;)[Ljava/lang/CharSequence;
    move-result-object v5
    const v6, @REFRESH_VALUES@
    invoke-virtual {v4, v6}, Landroid/content/res/Resources;->getTextArray(I)[Ljava/lang/CharSequence;
    move-result-object v6
    const-string v7, "-1"
    invoke-static {v7, v6}, Lcom/lmqr/ha9_comp_service/PerAppRefreshSettings;->prepend(Ljava/lang/String;[Ljava/lang/CharSequence;)[Ljava/lang/CharSequence;
    move-result-object v6
    new-instance v4, Landroid/content/Intent;
    const-string v7, "android.intent.action.MAIN"
    invoke-direct {v4, v7}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V
    const-string v7, "android.intent.category.LAUNCHER"
    invoke-virtual {v4, v7}, Landroid/content/Intent;->addCategory(Ljava/lang/String;)Landroid/content/Intent;
    invoke-virtual {v3, v4, v1}, Landroid/content/pm/PackageManager;->queryIntentActivities(Landroid/content/Intent;I)Ljava/util/List;
    move-result-object v4
    invoke-interface {v4}, Ljava/util/List;->iterator()Ljava/util/Iterator;
    move-result-object v4
    :next
    invoke-interface {v4}, Ljava/util/Iterator;->hasNext()Z
    move-result v7
    if-eqz v7, :done
    invoke-interface {v4}, Ljava/util/Iterator;->next()Ljava/lang/Object;
    move-result-object v7
    check-cast v7, Landroid/content/pm/ResolveInfo;
    iget-object v8, v7, Landroid/content/pm/ResolveInfo;->activityInfo:Landroid/content/pm/ActivityInfo;
    iget-object v8, v8, Landroid/content/pm/ActivityInfo;->packageName:Ljava/lang/String;
    const-string v9, "package:"
    invoke-virtual {v9, v8}, Ljava/lang/String;->concat(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v8
    invoke-virtual {v0, v8}, Landroidx/preference/PreferenceGroup;->findPreference(Ljava/lang/CharSequence;)Landroidx/preference/Preference;
    move-result-object v9
    if-nez v9, :next
    new-instance v9, Lcom/lmqr/ha9_comp_service/PerAppRefreshPreference;
    invoke-direct {v9, v2}, Lcom/lmqr/ha9_comp_service/PerAppRefreshPreference;-><init>(Landroid/content/Context;)V
    invoke-virtual {v9, v8}, Landroidx/preference/Preference;->setKey(Ljava/lang/String;)V
    invoke-virtual {v7, v3}, Landroid/content/pm/ResolveInfo;->loadLabel(Landroid/content/pm/PackageManager;)Ljava/lang/CharSequence;
    move-result-object v10
    invoke-virtual {v9, v10}, Landroidx/preference/Preference;->setTitle(Ljava/lang/CharSequence;)V
    invoke-virtual {v9, v5}, Landroidx/preference/ListPreference;->setEntries([Ljava/lang/CharSequence;)V
    invoke-virtual {v9, v6}, Landroidx/preference/ListPreference;->setEntryValues([Ljava/lang/CharSequence;)V
    const-string v10, "-1"
    invoke-virtual {v9, v10}, Landroidx/preference/Preference;->setDefaultValue(Ljava/lang/Object;)V
    invoke-static {}, Landroidx/preference/ListPreference$SimpleSummaryProvider;->getInstance()Landroidx/preference/ListPreference$SimpleSummaryProvider;
    move-result-object v10
    invoke-virtual {v9, v10}, Landroidx/preference/Preference;->setSummaryProvider(Landroidx/preference/Preference$SummaryProvider;)V
    invoke-virtual {v0, v9}, Landroidx/preference/PreferenceGroup;->addPreference(Landroidx/preference/Preference;)Z
    goto :next
    :done
    return-void
.end method
