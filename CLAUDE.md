# Flytotal Mac-side Claude Code Rules

## 当前角色
当前设备是 Mac 辅机，不是主机。
当前主要任务是推进以下内容：
- tools/vision_bridge_视觉桥接.py
- tools/vision_web_server_视觉网页服务.py
- vision_dashboard.html
- tools/false_alarm_baseline_误报率基线测试.py
- 证据链 hash / 一致性核对工具
- docs 下的文档、接口说明、freeze manifest、周报

当前不负责固件主链最终定版，不负责真机烧录验收。

## 文件修改边界
Claude 可以主动修改：
- tools/vision_bridge_视觉桥接.py
- tools/vision_web_server_视觉网页服务.py
- vision_dashboard.html
- tools/*.py（工具脚本）
- docs/*.md

Claude 不要主动修改以下固件主链文件，除非我明确要求：
- include/AppConfig.h
- include/SharedData.h
- lib/HunterAction/HunterAction.cpp
- src/main.cpp

如果任务需要影响上述文件，只能先输出修改建议和 patch 计划，不要直接改。

## Git 规则
当前开发分支是：
- feat/mac-claude

Claude 不要直接修改 main。
Claude 不要主动切换到 main 开发。
Claude 改完代码后，只提醒我执行以下命令，不要擅自执行，除非我明确授权：
- git add -A
- git commit -m "..."
- git push origin feat/mac-claude

如果需要创建或切换分支，先列出将要执行的命令，再等待我确认。

## 工作方式
1. 先分析，再修改。
2. 先告诉我准备修改哪些文件、为什么修改，再开始改。
3. 每次尽量只完成一个小功能块，不要一次改太多文件。
4. 不要为了”顺手优化”去改无关代码。
5. 如果涉及接口字段变化，先更新 docs/interface_contract_nodea.md，再改代码。
6. 如果发现当前任务更适合 Win 主机完成，要明确提醒我，不要硬做。
7. 如果可以用 mock 数据、本地数据、静态数据完成验证，优先采用，不依赖真机。
8. 回答尽量简洁直接，不要长篇空话。
9. 当计划中同时包含 Win 要推进的内容和 Mac 要推进的内容时，只推进 Mac 的部分。Win 的部分只读取、理解，用于了解接口约定和字段定义，不做任何代码修改。

## 当前优先级
当前 Mac 侧优先推进：
1. 视觉桥接半自动引导框
2. vision_state 网页显示与视觉贡献显示
3. 误报率 / E2E 统计脚本
4. evidence_hash 与一致性核对
5. 文档与接口契约整理

## 风险提醒
- 非合作目标被视觉锁定时，不应直接降低风险。
- 视觉状态写回主链时，不要假设可以直接占用串口。
- 不要让 Mac 侧任务变成整个项目的阻塞项。