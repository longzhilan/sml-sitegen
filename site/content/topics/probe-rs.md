---
title: "probe-rs"
summary: "Rust 生态里的调试/烧录工具链：一条命令连上探针、烧录、看 RTT 日志，替代 OpenOCD + gdb 的组合。"
tags: [ probe-rs ]
related: [ embedded-rust-toolchain ]
---

## 定义

probe-rs 是一套用 Rust 写的调试探针驱动与工具集，覆盖 CMSIS-DAP、ST-Link、J-Link 等常见探针，
提供 `probe-rs run` / `probe-rs list` 等命令，并通过 RTT（Real-Time Transfer）在不停机的情况下看日志。

## 为什么用它

- 一条命令完成烧录 + 复位 + 日志，不需要维护 OpenOCD 配置文件
- 与 `cargo run` 集成（`.cargo/config.toml` 里设 runner），日常开发只按一次
- 跨平台，Windows 上不需要装额外驱动包（除探针自身驱动）

## 常见坑

- 探针固件过旧会连不上，先升级固件
- 芯片读保护状态下烧录失败，先解除保护
- `--chip` 型号写错时报的是「找不到目标」，不是「连接失败」
