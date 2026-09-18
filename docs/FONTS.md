# 字体（MiSans）

## 能不能用

可以。MiSans 由小米发布，**可免费商用，允许网页嵌入与自托管**；限制主要是：
**不能单独售卖字体文件本身**、不能改名字后当成自己的字体发布、不得用于违法用途。
上线前请对照官方《MiSans 字体知识产权许可协议》确认当前条款（许可可能更新，以官方页面为准）。

## 怎么接（当前实现）

```
site/fonts/
├─ src/     源字体（MiSans-Regular.ttf …）—— 不入库（.gitignore），可从官方包重新获取
├─ subset/  子集产物（misans-regular.woff …）—— 入库，体积很小
└─ LICENSE-*  字体自带许可文件（若压缩包内有）—— 入库并随产物发布
```

1. 从压缩包挑权重（不整包解压，只认文件名尾段的权重名，避免 `bold` 命中 `demibold`）：

```bash
python engine/fonts_import.py MiSans.zip --weights Regular,Bold   # → site/fonts/src/
python engine/fonts_import.py MiSans.zip --list                   # 只看包里有什么
```

2. 构建期**子集化**：只保留站点实际用到的字符，产出 `site/fonts/subset/*` + `dist/fonts.css`，
   并在页面 `<head>` 注入样式链接。已实测：MiSans Regular + Bold 源文件 15.4 MB →
   **子集 236 KB**（woff）。

```bash
python -m pip install fonttools   # 子集化依赖；brotli 可选（有则输出 woff2，没有就退化为 woff）
python engine/cli.py build
```

3. **子集提交进仓库，CI 不需要装 fonttools**；本地放了源字体才会重新生成（源文件比子集新时自动重建）。
4. 没有字体文件时**什么都不做**，`font-family` 自动回退到系统字体（PingFang SC / 微软雅黑等）。

为什么必须子集化：MiSans 全字集单权重是十几 MB，直接托管会拖垮首屏。**不引入第三方字体 CDN**——
符合站点「静态资源全自托管」的隐私约定。

## 字体栈

```css
font: 16px/1.75 "MiSans", -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
```

即：优先用子集化的 MiSans；没有该字体（或请求失败）时逐级回退，不影响阅读。

## 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 构建提示「有源字体但缺 fonttools」 | `python -m pip install fonttools`；或只依赖已入库的子集（CI 场景） |
| 提示「缺 brotli，子集改用 woff」 | 正常降级（子集只有一两百 KB，woff 与 woff2 差别可忽略）；要 woff2 就装 brotli |
| 字体没生效 | 看 `dist/fonts.css` 是否生成、`site/fonts/subset/` 是否有文件、`<head>` 是否引用了 `fonts.css` |
| 有字显示成方块 | 子集漏字：站点文字取自构建数据，若在 CSS/JS 里硬编码了额外文字，把它们也纳入子集（改 `engine/build.py` 的 `site_text()`） |
| 体积偏大 | 只放需要的权重（Regular + Bold 够用）；不要提交 `src/` 下的源字体 |
