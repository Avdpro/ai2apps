# Agent 局部变量、赋值和循环

每个能力可定义 `variables`（JSON Schema object）。变量具有名称、类型、标题、说明，和固定 `default` 或表达式 `initial`。支持 string、integer、number、boolean、array、object、null。变量每次调用重新初始化；子 Agent 有独立的变量作用域，通过参数和步骤输出交换数据。

编辑器的“局部变量”定义这些字段。“步骤类型”可以选择浏览器操作、AI 判断/提取/处理、赋值、条件判断或调用 Agent。赋值步骤逐行选择变量并填写表达式；条件步骤填写一个布尔表达式，并设置真、假、失败三个跳转。普通步骤可将输入值绑定到局部变量。步骤及编译结果仍默认折叠。

赋值和条件判断是确定性的本地数据步骤，直接编译执行，不调用模型或浏览器，不需要确认。AI 判断用于需要模型理解的条件，通过该步骤所选强度运行，模型或结构化结果失败走失败分支。已有浏览器步骤的编译/AI 回退设置继续有效。

## 表达式

- 输入：`input.items`；局部变量：`vars.index`；步骤输出：`steps.fetch.output.items`。
- 数组当前项：`input.items[vars.index]`；对象字段：`vars.item.url`。
- 运算：`+ - * / // %`、比较、`in / not in`、`and / or / not`。
- 函数：`len` / `length`、`min`、`max`、`abs`。
- 字面量：数字、字符串、数组、对象，以及 `true / false / null`。
- 数据绑定 `${vars.item}` 保留原始 JSON 类型；`${vars.items.0.url}` 支持固定数组索引。动态索引通过赋值表达式计算当前项后再绑定。

不执行 Python/JavaScript 代码，不支持方法调用、导入、推导式、幂运算、负数组索引或属性反射。数组越界、缺字段、除零、类型不匹配走失败分支。布尔条件必须产出 boolean，数字 0 不隐式转为 false。

同一赋值步骤中的行按顺序求值，后行可读取前行结果；全部成功才提交。任一行失败回滚整步。初始化表达式只能读取输入，不能引用其他局部变量或此前步骤结果。

## 循环例子

```json
{
  "site_scope": ["https://example.com/**"],
  "inputs": {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {"type": "string"}}},
    "required": ["items"]
  },
  "variables": {
    "type": "object",
    "properties": {
      "index": {"type": "integer", "title": "当前索引", "default": 0},
      "item": {"type": "string", "title": "当前项", "default": ""}
    }
  },
  "steps": [
    {
      "name": "check",
      "operation": "condition",
      "arguments": {"expression": "vars.index < len(input.items)"},
      "on": {"true": "update", "false": "done", "failed": "failed"}
    },
    {
      "name": "update",
      "operation": "assign",
      "arguments": {"assignments": [
        {"variable": "item", "expression": "input.items[vars.index]"},
        {"variable": "index", "expression": "vars.index + 1"}
      ]},
      "on": {"success": "check", "failed": "failed"}
    }
  ]
}
```

需要处理页面时，在 update 与 check 之间插入浏览器步骤，绑定 `${vars.item}`。可直接跳出循环或跳回条件，不需要专门的 break/continue 操作。目前没有单独的 foreach 可视化容器。

## 恢复、测试和边界

执行器根据固定的 IR、调用输入和已完成的模型/浏览器记录重建变量。恢复不会重新提交已经完成的浏览器动作；循环中每轮有不同的动作标识。最终结果另附 `variables`，不改变能力 `outputs` 的结果契约。

赋值/条件步骤可单步“运行此步”：测试变量连续保存在当前编辑器内。“预演”仅求值，不提交测试变量变化；“重置测试变量”让下一次从初始值开始。测试不会修改 Agent 定义。完整运行每次使用独立的变量状态。

保留每次能力调用最多 100 个步骤的现有执行预算（含判断、赋值和循环访问）；还限制变量数量 64、每步赋值 32、表达式长度 4000、AST 节点 128、求值深度 24、JSON 数据 256 KiB。超限明确失败。

Python 服务变更需从 App Dev Helper 重启 Local，再刷新侧栏。无需重新构建 Desktop App。
