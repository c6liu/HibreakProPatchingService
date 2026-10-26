.class public final Lcom/lmqr/ha9_comp_service/AppLaunchSettings;
.super Ljava/lang/Object;

.method private static append(Ljava/lang/CharSequence;[Ljava/lang/CharSequence;)[Ljava/lang/CharSequence;
    .locals 4
    array-length v0, p1
    add-int/lit8 v1, v0, 0x1
    new-array v1, v1, [Ljava/lang/CharSequence;
    const/4 v2, 0x0
    add-int/lit8 v0, v0, -0x1
    invoke-static {p1, v2, v1, v2, v0}, Ljava/lang/System;->arraycopy(Ljava/lang/Object;ILjava/lang/Object;II)V
    aput-object p0, v1, v0
    aget-object v3, p1, v0
    add-int/lit8 v0, v0, 0x1
    aput-object v3, v1, v0
    return-object v1
.end method

.method private static toArray(Ljava/util/ArrayList;)[Ljava/lang/CharSequence;
    .locals 2
    const/4 v0, 0x0
    new-array v0, v0, [Ljava/lang/CharSequence;
    invoke-virtual {p0, v0}, Ljava/util/ArrayList;->toArray([Ljava/lang/Object;)[Ljava/lang/Object;
    move-result-object v0
    check-cast v0, [Ljava/lang/CharSequence;
    return-object v0
.end method

.method private static actionKey(I)Ljava/lang/String;
    .locals 1
    packed-switch p0, :key_switch
    const-string v0, "long_press_eink_action_screen_off"
    return-object v0
    :key_0
    const-string v0, "top_single_press_eink_action"
    return-object v0
    :key_1
    const-string v0, "top_double_press_eink_action"
    return-object v0
    :key_2
    const-string v0, "top_long_press_eink_action"
    return-object v0
    :key_3
    const-string v0, "top_single_press_eink_action_screen_off"
    return-object v0
    :key_4
    const-string v0, "top_double_press_eink_action_screen_off"
    return-object v0
    :key_5
    const-string v0, "top_long_press_eink_action_screen_off"
    return-object v0
    :key_6
    const-string v0, "single_press_eink_action"
    return-object v0
    :key_7
    const-string v0, "double_press_eink_action"
    return-object v0
    :key_8
    const-string v0, "long_press_eink_action"
    return-object v0
    :key_9
    const-string v0, "single_press_eink_action_screen_off"
    return-object v0
    :key_10
    const-string v0, "double_press_eink_action_screen_off"
    return-object v0
    :key_11
    const-string v0, "long_press_eink_action_screen_off"
    return-object v0
    :key_switch
    .packed-switch 0x0
        :key_0
        :key_1
        :key_2
        :key_3
        :key_4
        :key_5
        :key_6
        :key_7
        :key_8
        :key_9
        :key_10
        :key_11
    .end packed-switch
.end method

.method private static launcherApps(Landroid/content/Context;)[[Ljava/lang/CharSequence;
    .locals 12
    invoke-virtual {p0}, Landroid/content/Context;->getPackageManager()Landroid/content/pm/PackageManager;
    move-result-object v0
    new-instance v1, Landroid/content/Intent;
    const-string v2, "android.intent.action.MAIN"
    invoke-direct {v1, v2}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V
    const-string v2, "android.intent.category.LAUNCHER"
    invoke-virtual {v1, v2}, Landroid/content/Intent;->addCategory(Ljava/lang/String;)Landroid/content/Intent;
    const/4 v2, 0x0
    invoke-virtual {v0, v1, v2}, Landroid/content/pm/PackageManager;->queryIntentActivities(Landroid/content/Intent;I)Ljava/util/List;
    move-result-object v1
    new-instance v2, Ljava/util/HashSet;
    invoke-direct {v2}, Ljava/util/HashSet;-><init>()V
    new-instance v3, Ljava/util/ArrayList;
    invoke-direct {v3}, Ljava/util/ArrayList;-><init>()V
    new-instance v4, Ljava/util/ArrayList;
    invoke-direct {v4}, Ljava/util/ArrayList;-><init>()V
    invoke-interface {v1}, Ljava/util/List;->iterator()Ljava/util/Iterator;
    move-result-object v5
    :app_loop
    invoke-interface {v5}, Ljava/util/Iterator;->hasNext()Z
    move-result v6
    if-eqz v6, :apps_done
    invoke-interface {v5}, Ljava/util/Iterator;->next()Ljava/lang/Object;
    move-result-object v6
    check-cast v6, Landroid/content/pm/ResolveInfo;
    iget-object v7, v6, Landroid/content/pm/ResolveInfo;->activityInfo:Landroid/content/pm/ActivityInfo;
    iget-object v8, v7, Landroid/content/pm/ActivityInfo;->packageName:Ljava/lang/String;
    invoke-virtual {v2, v8}, Ljava/util/HashSet;->add(Ljava/lang/Object;)Z
    move-result v9
    if-eqz v9, :app_loop
    invoke-virtual {v6, v0}, Landroid/content/pm/ResolveInfo;->loadLabel(Landroid/content/pm/PackageManager;)Ljava/lang/CharSequence;
    move-result-object v9
    if-nez v9, :have_label
    move-object v9, v8
    :have_label
    invoke-virtual {v3, v9}, Ljava/util/ArrayList;->add(Ljava/lang/Object;)Z
    invoke-virtual {v4, v8}, Ljava/util/ArrayList;->add(Ljava/lang/Object;)Z
    goto :app_loop
    :apps_done
    invoke-virtual {v3}, Ljava/util/ArrayList;->isEmpty()Z
    move-result v5
    if-eqz v5, :convert_apps
    const-string v5, "No launchable apps found"
    invoke-virtual {v3, v5}, Ljava/util/ArrayList;->add(Ljava/lang/Object;)Z
    const-string v5, ""
    invoke-virtual {v4, v5}, Ljava/util/ArrayList;->add(Ljava/lang/Object;)Z
    :convert_apps
    invoke-static {v3}, Lcom/lmqr/ha9_comp_service/AppLaunchSettings;->toArray(Ljava/util/ArrayList;)[Ljava/lang/CharSequence;
    move-result-object v5
    invoke-static {v4}, Lcom/lmqr/ha9_comp_service/AppLaunchSettings;->toArray(Ljava/util/ArrayList;)[Ljava/lang/CharSequence;
    move-result-object v6
    const/4 v0, 0x2
    new-array v0, v0, [[Ljava/lang/CharSequence;
    const/4 v1, 0x0
    aput-object v5, v0, v1
    const/4 v1, 0x1
    aput-object v6, v0, v1
    return-object v0
.end method

.method private static addTarget(Landroidx/preference/PreferenceFragmentCompat;I[Ljava/lang/CharSequence;[Ljava/lang/CharSequence;Ljava/lang/String;)V
    .locals 10
    invoke-virtual {p0, p4}, Landroidx/preference/PreferenceFragmentCompat;->findPreference(Ljava/lang/CharSequence;)Landroidx/preference/Preference;
    move-result-object v0
    check-cast v0, Landroidx/preference/ListPreference;
    rem-int/lit8 v1, p1, 0x6
    mul-int/lit8 v1, v1, 0x2
    invoke-virtual {v0, v1}, Landroidx/preference/Preference;->setOrder(I)V
    invoke-static {}, Landroidx/preference/ListPreference$SimpleSummaryProvider;->getInstance()Landroidx/preference/ListPreference$SimpleSummaryProvider;
    move-result-object v1
    invoke-virtual {v0, v1}, Landroidx/preference/Preference;->setSummaryProvider(Landroidx/preference/Preference$SummaryProvider;)V
    invoke-virtual {v0}, Landroidx/preference/ListPreference;->getEntries()[Ljava/lang/CharSequence;
    move-result-object v1
    const-string v2, "Launch App"
    invoke-static {v2, v1}, Lcom/lmqr/ha9_comp_service/AppLaunchSettings;->append(Ljava/lang/CharSequence;[Ljava/lang/CharSequence;)[Ljava/lang/CharSequence;
    move-result-object v1
    invoke-virtual {v0, v1}, Landroidx/preference/ListPreference;->setEntries([Ljava/lang/CharSequence;)V
    invoke-virtual {v0}, Landroidx/preference/ListPreference;->getEntryValues()[Ljava/lang/CharSequence;
    move-result-object v1
    const-string v2, "launch_app_"
    invoke-virtual {v2, p4}, Ljava/lang/String;->concat(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v2
    invoke-static {v2, v1}, Lcom/lmqr/ha9_comp_service/AppLaunchSettings;->append(Ljava/lang/CharSequence;[Ljava/lang/CharSequence;)[Ljava/lang/CharSequence;
    move-result-object v1
    invoke-virtual {v0, v1}, Landroidx/preference/ListPreference;->setEntryValues([Ljava/lang/CharSequence;)V
    new-instance v3, Landroidx/preference/ListPreference;
    invoke-virtual {v0}, Landroidx/preference/Preference;->getContext()Landroid/content/Context;
    move-result-object v4
    const/4 v5, 0x0
    invoke-direct {v3, v4, v5}, Landroidx/preference/ListPreference;-><init>(Landroid/content/Context;Landroid/util/AttributeSet;)V
    const v4, @APP_LAUNCH_LAYOUT@
    invoke-virtual {v3, v4}, Landroidx/preference/Preference;->setLayoutResource(I)V
    const-string v4, "launch_app_package_"
    invoke-virtual {v4, p4}, Ljava/lang/String;->concat(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v4
    invoke-virtual {v3, v4}, Landroidx/preference/Preference;->setKey(Ljava/lang/String;)V
    invoke-virtual {v0}, Landroidx/preference/Preference;->getOrder()I
    move-result v4
    add-int/lit8 v4, v4, 0x1
    invoke-virtual {v3, v4}, Landroidx/preference/Preference;->setOrder(I)V
    const-string v4, "App to launch"
    invoke-virtual {v3, v4}, Landroidx/preference/Preference;->setTitle(Ljava/lang/CharSequence;)V
    const-string v4, "Choose an app to launch"
    invoke-virtual {v3, v4}, Landroidx/preference/DialogPreference;->setDialogTitle(Ljava/lang/CharSequence;)V
    invoke-virtual {v3, p2}, Landroidx/preference/ListPreference;->setEntries([Ljava/lang/CharSequence;)V
    invoke-virtual {v3, p3}, Landroidx/preference/ListPreference;->setEntryValues([Ljava/lang/CharSequence;)V
    const-string v4, ""
    invoke-virtual {v3, v4}, Landroidx/preference/Preference;->setDefaultValue(Ljava/lang/Object;)V
    const/4 v4, 0x0
    aget-object v4, p3, v4
    invoke-static {v4}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z
    move-result v4
    xor-int/lit8 v4, v4, 0x1
    invoke-virtual {v3, v4}, Landroidx/preference/Preference;->setEnabled(Z)V
    new-instance v4, Lcom/lmqr/ha9_comp_service/AppLaunchPreferenceBinding;
    invoke-direct {v4, v3, v2}, Lcom/lmqr/ha9_comp_service/AppLaunchPreferenceBinding;-><init>(Landroidx/preference/ListPreference;Ljava/lang/String;)V
    invoke-virtual {v3, v4}, Landroidx/preference/Preference;->setSummaryProvider(Landroidx/preference/Preference$SummaryProvider;)V
    invoke-virtual {v0}, Landroidx/preference/Preference;->getParent()Landroidx/preference/PreferenceGroup;
    move-result-object v5
    invoke-virtual {v5, v3}, Landroidx/preference/PreferenceGroup;->addPreference(Landroidx/preference/Preference;)Z
    invoke-virtual {v0}, Landroidx/preference/ListPreference;->getValue()Ljava/lang/String;
    move-result-object v5
    invoke-virtual {v4, v0, v5}, Lcom/lmqr/ha9_comp_service/AppLaunchPreferenceBinding;->onPreferenceChange(Landroidx/preference/Preference;Ljava/lang/Object;)Z
    invoke-virtual {v0, v4}, Landroidx/preference/Preference;->setOnPreferenceChangeListener(Landroidx/preference/Preference$OnPreferenceChangeListener;)V
    return-void
.end method

.method public static populate(Landroidx/preference/PreferenceFragmentCompat;)V
    .locals 12
    invoke-virtual {p0}, Landroidx/fragment/app/Fragment;->requireActivity()Landroidx/fragment/app/FragmentActivity;
    move-result-object v0
    invoke-virtual {v0}, Landroid/app/Activity;->getIntent()Landroid/content/Intent;
    move-result-object v1
    const-string v2, "per_app_page"
    const/4 v3, 0x0
    invoke-virtual {v1, v2, v3}, Landroid/content/Intent;->getBooleanExtra(Ljava/lang/String;Z)Z
    move-result v1
    if-nez v1, :done
    invoke-virtual {p0}, Landroidx/fragment/app/Fragment;->requireContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0}, Lcom/lmqr/ha9_comp_service/AppLaunchSettings;->launcherApps(Landroid/content/Context;)[[Ljava/lang/CharSequence;
    move-result-object v1
    const/4 v2, 0x0
    aget-object v2, v1, v2
    const/4 v3, 0x1
    aget-object v3, v1, v3
    const/4 v6, 0x0
    :preference_loop
    const/16 v7, 0xc
    if-ge v6, v7, :done
    invoke-static {v6}, Lcom/lmqr/ha9_comp_service/AppLaunchSettings;->actionKey(I)Ljava/lang/String;
    move-result-object v7
    invoke-static {p0, v6, v2, v3, v7}, Lcom/lmqr/ha9_comp_service/AppLaunchSettings;->addTarget(Landroidx/preference/PreferenceFragmentCompat;I[Ljava/lang/CharSequence;[Ljava/lang/CharSequence;Ljava/lang/String;)V
    add-int/lit8 v6, v6, 0x1
    goto :preference_loop
    :done
    return-void
.end method
