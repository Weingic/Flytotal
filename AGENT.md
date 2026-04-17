# Flytotal Agent Rules

## 讲解要求
- 每次讲解完实现的功能后，必须追加一段“给小白的解释”。
- “给小白的解释”要用通俗中文，不堆术语，按“这是什么 -> 有什么用 -> 你现在该怎么做”来说明。

## Win/Mac 协作边界
- 当用户给出的计划同时包含 `Win` 推进部分和 `Mac` 推进部分时，只推进 `Win` 侧应推进的内容。
- `Mac` 部分仅做阅读与理解，不执行、不改动、不代做。

## 推进进度汇报规则
- 每次推进计划时，必须明确说明当前推进到计划的哪一部分（例如 Day1/Day2/Day3 的哪个任务点）。
- 每次关键动作后，必须同步当前状态：已完成、进行中、下一步。
- 若出现阻塞，必须明确说明阻塞点、影响范围、下一步处理动作。

## 改代码前确认规则
- 在修改任何代码文件前，必须先向用户请求确认。
- 请求确认时必须明确说明：
  1. 准备修改哪些文件。
  2. 修改目的是什么。
  3. 预期影响范围是什么。
- 用户未明确允许前，不执行代码改动。

## Branch Switch Approval Rule
- 当改动需要切换到其他分支（包括切到 integration 或新建/切换 feature 分支）时，必须在执行前先向用户请求确认。
- 请求确认时必须明确说明：
  1. 为什么需要切到其他分支。
  2. 将切换到哪个目标分支。
  3. 现在是否允许执行这次分支切换。
- 在用户未明确允许前，不得执行任何 checkout / switch / merge 分支切换动作。

## Branch Switch Approval Rule (ASCII)
- Before any branch switch is executed, request user approval first.
- The approval message must include:
  1. Why branch switching is needed.
  2. Which target branch will be used.
  3. Whether the user allows the switch now.
- Without explicit user approval, do not run checkout/switch/merge that changes branch.
