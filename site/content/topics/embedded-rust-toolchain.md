---
title: "嵌入式 Rust 工具链"
summary: "从宿主机到目标板的一整套工具：rustup target、cargo runner、probe-rs / defmt、以及它们的取舍。"
tags: [ toolchain ]
related: [ probe-rs ]
---

## 定义

指把 Rust 代码变成能在 MCU 上跑起来的一整条链路：交叉编译目标三元组、链接脚本与内存布局、
烧录与调试后端、日志与追踪（defmt / RTT / ITM）、以及包管理与构建配置。

## 组成

- `rustup target add thumbv7em-none-eabihf` 之类的目标三元组
- `.cargo/config.toml`：runner、linker、target 默认值
- `memory.x` + `build.rs`：告诉链接器 Flash/RAM 布局
- 烧录/调试：probe-rs（推荐）、OpenOCD、pyOCD
- 日志：defmt + RTT（低开销、不阻塞），串口 `core::fmt` 作为兜底

## 判断原则

工具链越短越好：能用一个命令跑通就别写脚本；能靠配置解决的别靠记忆。
