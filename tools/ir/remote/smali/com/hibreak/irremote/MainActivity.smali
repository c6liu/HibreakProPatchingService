.class public Lcom/hibreak/irremote/MainActivity;
.super Landroid/app/Activity;
.implements Landroid/view/View$OnClickListener;
.implements Ljava/lang/Runnable;

.field private button:Landroid/widget/Button;
.field private status:Landroid/widget/TextView;
.field private handler:Landroid/os/Handler;

.method static constructor <clinit>()V
    .locals 1
    const-string v0, "hibreak_ir_remote"
    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V
    return-void
.end method

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Landroid/app/Activity;-><init>()V
    return-void
.end method

.method private native request()Ljava/lang/String;
.end method

.method private native poll()Ljava/lang/String;
.end method

.method public onCreate(Landroid/os/Bundle;)V
    .locals 5
    invoke-super {p0, p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V
    new-instance v0, Landroid/os/Handler;
    invoke-direct {v0}, Landroid/os/Handler;-><init>()V
    iput-object v0, p0, Lcom/hibreak/irremote/MainActivity;->handler:Landroid/os/Handler;
    new-instance v0, Landroid/widget/LinearLayout;
    invoke-direct {v0, p0}, Landroid/widget/LinearLayout;-><init>(Landroid/content/Context;)V
    const/4 v1, 0x1
    invoke-virtual {v0, v1}, Landroid/widget/LinearLayout;->setOrientation(I)V
    const/16 v1, 0x30
    invoke-virtual {v0, v1, v1, v1, v1}, Landroid/view/View;->setPadding(IIII)V
    const/16 v1, 0x11
    invoke-virtual {v0, v1}, Landroid/widget/LinearLayout;->setGravity(I)V
    new-instance v1, Landroid/widget/TextView;
    invoke-direct {v1, p0}, Landroid/widget/TextView;-><init>(Landroid/content/Context;)V
    const-string v2, "TCL 43S525 - IR test"
    invoke-virtual {v1, v2}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    const/high16 v2, 0x41c00000
    invoke-virtual {v1, v2}, Landroid/widget/TextView;->setTextSize(F)V
    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->addView(Landroid/view/View;)V
    new-instance v1, Landroid/widget/TextView;
    invoke-direct {v1, p0}, Landroid/widget/TextView;-><init>(Landroid/content/Context;)V
    const-string v2, "Experimental HXD mapping of NECext EA C7 / 0F F0.\nPoint the phone's IR port at the TV. Each tap sends ONE candidate Volume Up command.\nNo learning, background sending, or automatic repeats. A written command does not prove the TV received it."
    invoke-virtual {v1, v2}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->addView(Landroid/view/View;)V
    new-instance v1, Landroid/widget/Button;
    invoke-direct {v1, p0}, Landroid/widget/Button;-><init>(Landroid/content/Context;)V
    iput-object v1, p0, Lcom/hibreak/irremote/MainActivity;->button:Landroid/widget/Button;
    const-string v2, "Send Volume Up (experimental)"
    invoke-virtual {v1, v2}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    invoke-virtual {v1, p0}, Landroid/view/View;->setOnClickListener(Landroid/view/View$OnClickListener;)V
    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->addView(Landroid/view/View;)V
    new-instance v1, Landroid/widget/TextView;
    invoke-direct {v1, p0}, Landroid/widget/TextView;-><init>(Landroid/content/Context;)V
    iput-object v1, p0, Lcom/hibreak/irremote/MainActivity;->status:Landroid/widget/TextView;
    const-string v2, "Ready. Requires the matching HiBreak IR remote ROM image."
    invoke-virtual {v1, v2}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->addView(Landroid/view/View;)V
    invoke-virtual {p0, v0}, Landroid/app/Activity;->setContentView(Landroid/view/View;)V
    return-void
.end method

.method public onClick(Landroid/view/View;)V
    .locals 3
    iget-object v0, p0, Lcom/hibreak/irremote/MainActivity;->button:Landroid/widget/Button;
    const/4 v1, 0x0
    invoke-virtual {v0, v1}, Landroid/view/View;->setEnabled(Z)V
    invoke-direct {p0}, Lcom/hibreak/irremote/MainActivity;->request()Ljava/lang/String;
    move-result-object v1
    if-eqz v1, :requested
    iget-object v2, p0, Lcom/hibreak/irremote/MainActivity;->status:Landroid/widget/TextView;
    invoke-virtual {v2, v1}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    const/4 v1, 0x1
    invoke-virtual {v0, v1}, Landroid/view/View;->setEnabled(Z)V
    return-void
    :requested
    iget-object v0, p0, Lcom/hibreak/irremote/MainActivity;->status:Landroid/widget/TextView;
    const-string v1, "Requested one command. Waiting for the service..."
    invoke-virtual {v0, v1}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    invoke-virtual {p0}, Lcom/hibreak/irremote/MainActivity;->run()V
    return-void
.end method

.method public run()V
    .locals 3
    invoke-direct {p0}, Lcom/hibreak/irremote/MainActivity;->poll()Ljava/lang/String;
    move-result-object v0
    if-eqz v0, :pending
    iget-object v1, p0, Lcom/hibreak/irremote/MainActivity;->status:Landroid/widget/TextView;
    invoke-virtual {v1, v0}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    iget-object v1, p0, Lcom/hibreak/irremote/MainActivity;->button:Landroid/widget/Button;
    const/4 v0, 0x1
    invoke-virtual {v1, v0}, Landroid/view/View;->setEnabled(Z)V
    return-void
    :pending
    iget-object v0, p0, Lcom/hibreak/irremote/MainActivity;->handler:Landroid/os/Handler;
    const-wide/16 v1, 0xfa
    invoke-virtual {v0, p0, v1, v2}, Landroid/os/Handler;->postDelayed(Ljava/lang/Runnable;J)Z
    return-void
.end method

.method public onDestroy()V
    .locals 1
    iget-object v0, p0, Lcom/hibreak/irremote/MainActivity;->handler:Landroid/os/Handler;
    invoke-virtual {v0, p0}, Landroid/os/Handler;->removeCallbacks(Ljava/lang/Runnable;)V
    invoke-super {p0}, Landroid/app/Activity;->onDestroy()V
    return-void
.end method
