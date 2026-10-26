.class public final Lcom/lmqr/ha9_comp_service/AppLaunchPreferenceBinding;
.super Ljava/lang/Object;
.implements Landroidx/preference/Preference$OnPreferenceChangeListener;
.implements Landroidx/preference/Preference$SummaryProvider;

.field private final target:Landroidx/preference/ListPreference;
.field private final action:Ljava/lang/String;

.method public constructor <init>(Landroidx/preference/ListPreference;Ljava/lang/String;)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Lcom/lmqr/ha9_comp_service/AppLaunchPreferenceBinding;->target:Landroidx/preference/ListPreference;
    iput-object p2, p0, Lcom/lmqr/ha9_comp_service/AppLaunchPreferenceBinding;->action:Ljava/lang/String;
    return-void
.end method

.method public onPreferenceChange(Landroidx/preference/Preference;Ljava/lang/Object;)Z
    .locals 2
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/AppLaunchPreferenceBinding;->action:Ljava/lang/String;
    invoke-virtual {v0, p2}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    iget-object v1, p0, Lcom/lmqr/ha9_comp_service/AppLaunchPreferenceBinding;->target:Landroidx/preference/ListPreference;
    invoke-virtual {v1, v0}, Landroidx/preference/Preference;->setVisible(Z)V
    const/4 v0, 0x1
    return v0
.end method

.method public provideSummary(Landroidx/preference/Preference;)Ljava/lang/CharSequence;
    .locals 1
    check-cast p1, Landroidx/preference/ListPreference;
    invoke-virtual {p1}, Landroidx/preference/ListPreference;->getEntry()Ljava/lang/CharSequence;
    move-result-object v0
    invoke-static {v0}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z
    move-result p1
    if-eqz p1, :done
    const-string v0, "Choose an app to launch"
    :done
    return-object v0
.end method
