.class public final Lcom/lmqr/ha9_comp_service/button_mapper/LaunchAppButtonAction;
.super Ljava/lang/Object;
.implements Lcom/lmqr/ha9_comp_service/button_mapper/ButtonAction;

.field private final packagePreferenceKey:Ljava/lang/String;

.method public constructor <init>(Ljava/lang/String;)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Lcom/lmqr/ha9_comp_service/button_mapper/LaunchAppButtonAction;->packagePreferenceKey:Ljava/lang/String;
    return-void
.end method

.method private static showMessage(Landroid/content/Context;Ljava/lang/String;)V
    .locals 2
    const/4 v0, 0x0
    invoke-static {p0, p1, v0}, Landroid/widget/Toast;->makeText(Landroid/content/Context;Ljava/lang/CharSequence;I)Landroid/widget/Toast;
    move-result-object v0
    invoke-virtual {v0}, Landroid/widget/Toast;->show()V
    return-void
.end method

.method public execute(Landroid/content/Context;)V
    .locals 5
    invoke-static {p1}, Landroidx/preference/PreferenceManager;->getDefaultSharedPreferences(Landroid/content/Context;)Landroid/content/SharedPreferences;
    move-result-object v0
    iget-object v1, p0, Lcom/lmqr/ha9_comp_service/button_mapper/LaunchAppButtonAction;->packagePreferenceKey:Ljava/lang/String;
    const/4 v2, 0x0
    invoke-interface {v0, v1, v2}, Landroid/content/SharedPreferences;->getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v1
    invoke-static {v1}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z
    move-result v0
    if-nez v0, :no_app
    invoke-virtual {p1}, Landroid/content/Context;->getPackageManager()Landroid/content/pm/PackageManager;
    move-result-object v0
    invoke-virtual {v0, v1}, Landroid/content/pm/PackageManager;->getLaunchIntentForPackage(Ljava/lang/String;)Landroid/content/Intent;
    move-result-object v2
    if-nez v2, :launch
    const-string v0, "A9LaunchAppAction"
    const-string v3, "Selected app has no launchable activity"
    invoke-static {v0, v3}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I
    const-string v3, "The selected app cannot be launched"
    invoke-static {p1, v3}, Lcom/lmqr/ha9_comp_service/button_mapper/LaunchAppButtonAction;->showMessage(Landroid/content/Context;Ljava/lang/String;)V
    return-void
    :launch
    const v0, 0x10200000
    invoke-virtual {v2, v0}, Landroid/content/Intent;->addFlags(I)Landroid/content/Intent;
    :try_start
    invoke-virtual {p1, v2}, Landroid/content/Context;->startActivity(Landroid/content/Intent;)V
    :try_end
    return-void
    :no_app
    const-string v0, "A9LaunchAppAction"
    const-string v1, "No app selected for side-key action"
    invoke-static {v0, v1}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I
    const-string v1, "Choose an app to launch in E-Ink Settings"
    invoke-static {p1, v1}, Lcom/lmqr/ha9_comp_service/button_mapper/LaunchAppButtonAction;->showMessage(Landroid/content/Context;Ljava/lang/String;)V
    return-void
    :activity_not_found
    move-exception v4
    const-string v0, "A9LaunchAppAction"
    const-string v1, "Unable to launch selected app"
    invoke-static {v0, v1, v4}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    const-string v1, "Unable to launch the selected app"
    invoke-static {p1, v1}, Lcom/lmqr/ha9_comp_service/button_mapper/LaunchAppButtonAction;->showMessage(Landroid/content/Context;Ljava/lang/String;)V
    return-void
    :security_exception
    move-exception v4
    const-string v0, "A9LaunchAppAction"
    const-string v1, "Android blocked launching selected app"
    invoke-static {v0, v1, v4}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    const-string v1, "Android blocked launching the selected app"
    invoke-static {p1, v1}, Lcom/lmqr/ha9_comp_service/button_mapper/LaunchAppButtonAction;->showMessage(Landroid/content/Context;Ljava/lang/String;)V
    return-void
    .catch Landroid/content/ActivityNotFoundException; {:try_start .. :try_end} :activity_not_found
    .catch Ljava/lang/SecurityException; {:try_start .. :try_end} :security_exception
.end method
