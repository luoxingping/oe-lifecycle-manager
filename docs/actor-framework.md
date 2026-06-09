# Actor Framework 设计说明

## 目标

Actor Framework 是 Agentless CLI 版本的执行边界框架，用于把任务动作封装为可路由、可测试、可替换调度策略的 Actor。当前实现采用单进程同步调度，优先保证 CLI 快速验证链路稳定可运行。

## 模块边界

已实现职责：

- 注册 Actor。
- 构造消息和信封。
- 支持 `tell()` 投递到内存 mailbox。
- 支持 `ask()` 立即同步调用 Actor。
- 支持 FIFO `run_once()` 和 `drain()` 调度。
- 统一封装 Actor 执行异常。
- 返回结构化 `ActorResult`。

暂不实现职责：

- 不实现线程池、asyncio 或多进程调度。
- 不实现远程 Actor 或网络 RPC。
- 不实现消息持久化。
- 不实现自动重试、超时、熔断。
- 不直接维护升级任务状态，状态仍由 State Manager 负责。
- 不加载插件，插件发现和生命周期留给 Plugin Framework。

## 核心类

| 类 | 说明 |
| --- | --- |
| `ActorSystem` | Actor 注册、消息投递和同步调度入口。 |
| `ActorRegistry` | Actor 注册表。 |
| `InMemoryMailbox` | FIFO 内存消息队列。 |
| `Actor` | Actor 协议。 |
| `BaseActor` | 基础 Actor 类。 |
| `ActorMessage` | 消息载荷。 |
| `ActorEnvelope` | 带路由信息的消息信封。 |
| `ActorResult` | Actor 执行结果。 |
| `ActorNotFoundError` | Actor 不存在错误。 |
| `ActorAlreadyRegisteredError` | Actor 重复注册错误。 |
| `ActorExecutionError` | Actor 执行失败封装错误。 |

## 消息模型

`ActorMessage`：

- `message_type`
- `payload`

`ActorEnvelope`：

- `target`
- `message`
- `sender`
- `correlation_id`
- `created_at`

`ActorResult`：

- `actor_id`
- `message_type`
- `correlation_id`
- `value`

## 使用方式

```python
class InventoryActor(BaseActor):
    def handle(self, envelope):
        return {"message": envelope.message.message_type}


system = ActorSystem()
system.register(InventoryActor("inventory"))
result = system.ask("inventory", ActorMessage("collect", {"host_id": "host-1"}))
```

## ask 时序

```mermaid
sequenceDiagram
    participant CLI
    participant System as ActorSystem
    participant Registry as ActorRegistry
    participant Actor

    CLI->>System: ask(target, message)
    System->>System: create ActorEnvelope
    System->>Registry: get(target)
    Registry-->>System: Actor
    System->>Actor: handle(envelope)
    alt actor succeeded
        Actor-->>System: value
        System-->>CLI: ActorResult
    else actor failed
        Actor-->>System: exception
        System-->>CLI: ActorExecutionError
    end
```

## tell/drain 时序

```mermaid
sequenceDiagram
    participant CLI
    participant System as ActorSystem
    participant Mailbox as InMemoryMailbox
    participant Registry as ActorRegistry
    participant Actor

    CLI->>System: tell(target, message)
    System->>Registry: contains(target)
    Registry-->>System: true
    System->>Mailbox: send(envelope)
    System-->>CLI: ActorEnvelope

    CLI->>System: drain()
    loop each queued envelope
        System->>Mailbox: receive()
        Mailbox-->>System: ActorEnvelope
        System->>Registry: get(target)
        Registry-->>System: Actor
        System->>Actor: handle(envelope)
        Actor-->>System: value
        System->>System: append ActorResult
    end
    System-->>CLI: list[ActorResult]
```

## 与 Workflow Engine / State Manager 的关系

当前推荐组合方式：

- Workflow Engine 负责工作流步骤编排。
- State Manager 负责状态转移和 checkpoint。
- Actor Framework 负责把具体动作包装成 Actor 并提供统一执行边界。

示例组合：

```text
CLI -> StateManager.transition(CREATED -> INVENTORY_COLLECTING)
CLI -> ActorSystem.ask("inventory", ActorMessage("collect"))
CLI -> StateManager.save_step_status("collect", SUCCEEDED)
CLI -> WorkflowEngine.resume(...)
```

后续可扩展：

- 用 Actor 承载每个 workflow step handler。
- 为 ActorSystem 增加异步 dispatcher。
- 为 mailbox 增加 SQLite 或文件持久化。
- 为 ActorExecutionError 增加重试和补偿策略。

## 验证范围

单元测试覆盖：

- `ask()` 立即调度并返回结果。
- `tell()` 入队，`drain()` 按 FIFO 顺序调度。
- 空队列 `run_once()` 返回 `None`。
- 缺失 Actor 被拒绝。
- 重复 Actor 注册被拒绝。
- Actor 抛错会封装为 `ActorExecutionError`。
