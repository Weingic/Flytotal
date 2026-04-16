# Flytotal Agent Rules

## 讲解要求
- 每次讲解完实现的功能后，必须追加一段“给小白的解释”。
- “给小白的解释”要用通俗中文，不堆术语，按“这是什么 -> 有什么用 -> 你现在该怎么做”来说明。

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