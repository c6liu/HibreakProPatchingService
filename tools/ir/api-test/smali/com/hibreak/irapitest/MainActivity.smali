.class public Lcom/hibreak/irapitest/MainActivity;
.super Landroid/app/Activity;
.implements Landroid/view/View$OnClickListener;

.field private ir:Landroid/hardware/ConsumerIrManager;
.field private status:Landroid/widget/TextView;
.field private button:Landroid/widget/Button;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Landroid/app/Activity;-><init>()V
    return-void
.end method

.method public onCreate(Landroid/os/Bundle;)V
    .locals 5
    invoke-super {p0, p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V
    const-string v0, "consumer_ir"
    invoke-virtual {p0, v0}, Landroid/content/Context;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v0
    check-cast v0, Landroid/hardware/ConsumerIrManager;
    iput-object v0, p0, Lcom/hibreak/irapitest/MainActivity;->ir:Landroid/hardware/ConsumerIrManager;
    new-instance v0, Landroid/widget/LinearLayout;
    invoke-direct {v0, p0}, Landroid/widget/LinearLayout;-><init>(Landroid/content/Context;)V
    const/4 v1, 0x1
    invoke-virtual {v0, v1}, Landroid/widget/LinearLayout;->setOrientation(I)V
    const/16 v1, 0x30
    invoke-virtual {v0, v1, v1, v1, v1}, Landroid/view/View;->setPadding(IIII)V
    new-instance v1, Landroid/widget/TextView;
    invoke-direct {v1, p0}, Landroid/widget/TextView;-><init>(Landroid/content/Context;)V
    const-string v2, "Standard Android IR API test\nNo private properties, JNI, or root.\nOne 38 kHz NECext TCL Volume Up frame per tap.\nFramework return does NOT prove HAL success or TV response."
    invoke-virtual {v1, v2}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->addView(Landroid/view/View;)V
    new-instance v1, Landroid/widget/Button;
    invoke-direct {v1, p0}, Landroid/widget/Button;-><init>(Landroid/content/Context;)V
    iput-object v1, p0, Lcom/hibreak/irapitest/MainActivity;->button:Landroid/widget/Button;
    const/4 v2, 0x0
    invoke-virtual {v1, v2}, Landroid/view/View;->setEnabled(Z)V
    const-string v2, "Send Volume Up via Android API"
    invoke-virtual {v1, v2}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    invoke-virtual {v1, p0}, Landroid/view/View;->setOnClickListener(Landroid/view/View$OnClickListener;)V
    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->addView(Landroid/view/View;)V
    new-instance v1, Landroid/widget/TextView;
    invoke-direct {v1, p0}, Landroid/widget/TextView;-><init>(Landroid/content/Context;)V
    iput-object v1, p0, Lcom/hibreak/irapitest/MainActivity;->status:Landroid/widget/TextView;
    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->addView(Landroid/view/View;)V
    invoke-virtual {p0, v0}, Landroid/app/Activity;->setContentView(Landroid/view/View;)V
    :try_start
    iget-object v0, p0, Lcom/hibreak/irapitest/MainActivity;->ir:Landroid/hardware/ConsumerIrManager;
    if-eqz v0, :unavailable
    invoke-virtual {v0}, Landroid/hardware/ConsumerIrManager;->hasIrEmitter()Z
    move-result v1
    if-eqz v1, :unavailable
    invoke-virtual {v0}, Landroid/hardware/ConsumerIrManager;->getCarrierFrequencies()[Landroid/hardware/ConsumerIrManager$CarrierFrequencyRange;
    move-result-object v0
    if-eqz v0, :unexpected
    array-length v1, v0
    const/4 v2, 0x2
    if-ne v1, v2, :unexpected
    const/4 v1, 0x0
    aget-object v3, v0, v1
    invoke-virtual {v3}, Landroid/hardware/ConsumerIrManager$CarrierFrequencyRange;->getMinFrequency()I
    move-result v1
    const v2, 0x9470
    if-ne v1, v2, :unexpected
    invoke-virtual {v3}, Landroid/hardware/ConsumerIrManager$CarrierFrequencyRange;->getMaxFrequency()I
    move-result v1
    if-ne v1, v2, :unexpected
    const/4 v1, 0x1
    aget-object v3, v0, v1
    invoke-virtual {v3}, Landroid/hardware/ConsumerIrManager$CarrierFrequencyRange;->getMinFrequency()I
    move-result v1
    const v2, 0x954e
    if-ne v1, v2, :unexpected
    invoke-virtual {v3}, Landroid/hardware/ConsumerIrManager$CarrierFrequencyRange;->getMaxFrequency()I
    move-result v1
    if-ne v1, v2, :unexpected
    iget-object v0, p0, Lcom/hibreak/irapitest/MainActivity;->button:Landroid/widget/Button;
    const/4 v1, 0x1
    invoke-virtual {v0, v1}, Landroid/view/View;->setEnabled(Z)V
    const-string v0, "Emitter available; HAL accepts 38000/38222 Hz nominal NEC aliases. Ready for an explicit test."
    goto :show
    :unexpected
    const-string v0, "Unexpected carrier ranges. The NEC adapter may not be loaded. Do not send until checked."
    goto :show
    :unavailable
    const-string v0, "No Android IR emitter service available."
    :show
    iget-object v1, p0, Lcom/hibreak/irapitest/MainActivity;->status:Landroid/widget/TextView;
    invoke-virtual {v1, v0}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    :try_end
    .catch Ljava/lang/RuntimeException; {:try_start .. :try_end} :error
    return-void
    :error
    move-exception v0
    invoke-virtual {v0}, Ljava/lang/Throwable;->toString()Ljava/lang/String;
    move-result-object v0
    iget-object v1, p0, Lcom/hibreak/irapitest/MainActivity;->status:Landroid/widget/TextView;
    invoke-virtual {v1, v0}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    return-void
.end method

.method public onClick(Landroid/view/View;)V
    .locals 7
    const/4 v0, 0x0
    invoke-virtual {p1, v0}, Landroid/view/View;->setEnabled(Z)V
    :try_start
    const/16 v0, 0x43
    new-array v0, v0, [I
    const/4 v1, 0x0
    const/16 v2, 0x2328
    aput v2, v0, v1
    const/4 v1, 0x1
    const/16 v2, 0x1194
    aput v2, v0, v1
    const v1, -0xff03816
    const/4 v2, 0x0
    :loop
    const/16 v3, 0x20
    if-ge v2, v3, :encoded
    mul-int/lit8 v3, v2, 0x2
    add-int/lit8 v3, v3, 0x2
    const/16 v4, 0x230
    aput v4, v0, v3
    add-int/lit8 v3, v3, 0x1
    ushr-int v5, v1, v2
    and-int/lit8 v5, v5, 0x1
    if-eqz v5, :zero
    const/16 v4, 0x69a
    :zero
    aput v4, v0, v3
    add-int/lit8 v2, v2, 0x1
    goto :loop
    :encoded
    const/16 v2, 0x42
    const/16 v3, 0x230
    aput v3, v0, v2
    iget-object v1, p0, Lcom/hibreak/irapitest/MainActivity;->ir:Landroid/hardware/ConsumerIrManager;
    const v2, 0x9470
    invoke-virtual {v1, v2, v0}, Landroid/hardware/ConsumerIrManager;->transmit(I[I)V
    const-string v0, "Android transmit returned. Check TV response and HibreakIR log; the API does not expose HAL failures."
    iget-object v1, p0, Lcom/hibreak/irapitest/MainActivity;->status:Landroid/widget/TextView;
    invoke-virtual {v1, v0}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    :try_end
    .catch Ljava/lang/RuntimeException; {:try_start .. :try_end} :error
    goto :done
    :error
    move-exception v0
    invoke-virtual {v0}, Ljava/lang/Throwable;->toString()Ljava/lang/String;
    move-result-object v0
    iget-object v1, p0, Lcom/hibreak/irapitest/MainActivity;->status:Landroid/widget/TextView;
    invoke-virtual {v1, v0}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    :done
    const/4 v0, 0x1
    invoke-virtual {p1, v0}, Landroid/view/View;->setEnabled(Z)V
    return-void
.end method
