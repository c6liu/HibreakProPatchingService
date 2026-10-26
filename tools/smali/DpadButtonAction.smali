.class public final Lcom/lmqr/ha9_comp_service/button_mapper/DpadButtonAction;
.super Ljava/lang/Object;
.implements Lcom/lmqr/ha9_comp_service/button_mapper/ButtonAction;

.field private final command:Ljava/lang/String;
.field private final commandRunner:Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;

.method public constructor <init>(Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;Ljava/lang/String;)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Lcom/lmqr/ha9_comp_service/button_mapper/DpadButtonAction;->commandRunner:Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;
    iput-object p2, p0, Lcom/lmqr/ha9_comp_service/button_mapper/DpadButtonAction;->command:Ljava/lang/String;
    return-void
.end method

.method public execute(Landroid/content/Context;)V
    .locals 2
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/button_mapper/DpadButtonAction;->commandRunner:Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;
    iget-object v1, p0, Lcom/lmqr/ha9_comp_service/button_mapper/DpadButtonAction;->command:Ljava/lang/String;
    filled-new-array {v1}, [Ljava/lang/String;
    move-result-object v1
    invoke-interface {v0, v1}, Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;->runCommands([Ljava/lang/String;)V
    return-void
.end method
