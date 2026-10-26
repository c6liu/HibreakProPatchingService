.class public final Lhibreak/tests/SettingsActivityProbe;
.super Landroidx/appcompat/app/AppCompatActivity;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Landroidx/appcompat/app/AppCompatActivity;-><init>()V
    return-void
.end method

.method public onCreate(Landroid/os/Bundle;)V
    .locals 4
    invoke-super {p0, p1}, Landroidx/appcompat/app/AppCompatActivity;->onCreate(Landroid/os/Bundle;)V
    new-instance v0, Lcom/lmqr/ha9_comp_service/SettingsActivity$SettingsFragment;
    invoke-direct {v0}, Lcom/lmqr/ha9_comp_service/SettingsActivity$SettingsFragment;-><init>()V
    invoke-virtual {p0}, Landroidx/fragment/app/FragmentActivity;->getSupportFragmentManager()Landroidx/fragment/app/FragmentManager;
    move-result-object v1
    invoke-virtual {v1}, Landroidx/fragment/app/FragmentManager;->beginTransaction()Landroidx/fragment/app/FragmentTransaction;
    move-result-object v1
    const v2, 0x1020002
    invoke-virtual {v1, v2, v0}, Landroidx/fragment/app/FragmentTransaction;->replace(ILandroidx/fragment/app/Fragment;)Landroidx/fragment/app/FragmentTransaction;
    invoke-virtual {v1}, Landroidx/fragment/app/FragmentTransaction;->commitNow()V
    invoke-static {v0}, Lhibreak/tests/SettingsActivityProbe;->checkLaunchSettings(Landroidx/preference/PreferenceFragmentCompat;)V
    return-void
.end method

.method private static checkLaunchSettings(Landroidx/preference/PreferenceFragmentCompat;)V
    .locals 9
    const-string v0, "top_single_press_eink_action,top_double_press_eink_action,top_long_press_eink_action,top_single_press_eink_action_screen_off,top_double_press_eink_action_screen_off,top_long_press_eink_action_screen_off,single_press_eink_action,double_press_eink_action,long_press_eink_action,single_press_eink_action_screen_off,double_press_eink_action_screen_off,long_press_eink_action_screen_off"
    const-string v1, ","
    invoke-virtual {v0, v1}, Ljava/lang/String;->split(Ljava/lang/String;)[Ljava/lang/String;
    move-result-object v0
    const/4 v1, 0x0
    :next
    array-length v2, v0
    if-ge v1, v2, :done
    aget-object v2, v0, v1
    invoke-virtual {p0, v2}, Landroidx/preference/PreferenceFragmentCompat;->findPreference(Ljava/lang/CharSequence;)Landroidx/preference/Preference;
    move-result-object v3
    check-cast v3, Landroidx/preference/ListPreference;
    const-string v4, "launch_app_"
    invoke-virtual {v4, v2}, Ljava/lang/String;->concat(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v4
    invoke-virtual {v3, v4}, Landroidx/preference/ListPreference;->findIndexOfValue(Ljava/lang/String;)I
    move-result v5
    if-ltz v5, :fail
    invoke-virtual {v3}, Landroidx/preference/ListPreference;->getEntries()[Ljava/lang/CharSequence;
    move-result-object v6
    aget-object v6, v6, v5
    const-string v7, "Launch App"
    invoke-virtual {v7, v6}, Ljava/lang/String;->contentEquals(Ljava/lang/CharSequence;)Z
    move-result v6
    if-eqz v6, :fail
    const-string v4, "launch_app_package_"
    invoke-virtual {v4, v2}, Ljava/lang/String;->concat(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v4
    invoke-virtual {p0, v4}, Landroidx/preference/PreferenceFragmentCompat;->findPreference(Ljava/lang/CharSequence;)Landroidx/preference/Preference;
    move-result-object v3
    check-cast v3, Landroidx/preference/ListPreference;
    if-eqz v3, :fail
    invoke-virtual {v3}, Landroidx/preference/ListPreference;->getEntries()[Ljava/lang/CharSequence;
    move-result-object v4
    array-length v4, v4
    if-eqz v4, :fail
    invoke-virtual {v3}, Landroidx/preference/ListPreference;->getEntryValues()[Ljava/lang/CharSequence;
    move-result-object v5
    array-length v5, v5
    if-ne v4, v5, :fail
    add-int/lit8 v1, v1, 0x1
    goto :next
    :fail
    new-instance v0, Ljava/lang/AssertionError;
    invoke-direct {v0, v2}, Ljava/lang/AssertionError;-><init>(Ljava/lang/Object;)V
    throw v0
    :done
    return-void
.end method
