title: "SML 写作速查（可选格式）"
group: 写作
order: 2

# 这里是真正的 SML 注释：这一页本身就是 SML 写的。
# 片段：定义一次，多处用 &名字 引用。
@常见链接 {
  repo: "https://gitee.com/rustembed/site"
  sml: "https://sml.swebase.cn"
}

body: [
  topic 什么时候值得用 SML {
    children: [
      para { text: "Markdown 够用的场合就用 Markdown。下面这些情况 SML 更顺手：" }
      ul {
        items: [
          "需要严格字段校验（错字段名会直接报错，而不是被静默忽略）"
          "要写定理 / 证明 / 公式这类结构化内容"
          "同一段内容要在多处复用（片段 &引用）"
          "希望正文与元数据在同一个文件里都是结构化数据"
        ]
      }
    ]
  }

  topic 让人觉得舒服的四个点 {
    children: [
      section 多行文本直接写 {
        children: [
          para { text: "引号里的换行就是换行，不用 \n 转义。段落里想怎么写就怎么写——

第二行照样是同一段文字，缩进也不影响解析（SML 不依赖缩进定界）。

空行也在字符串里原样保留。" }
        ]
      }

      section 裸词即字符串 {
        children: [
          para { text: "中文、邮箱、路径都不用加引号，只有含空格或特殊符号时才需要。" }
          code { lang: sml text: "state: NY\nto: a@b.c\npath: /api/v1/health\ncontain_space: \"才需要引号\"\n含中文的裸词: 也可以" }
        ]
      }

      section 块冒号可省 {
        children: [
          para { text: "address { } 与 address: { } 等价；数组里逗号可选、可换行、可混着写。" }
          code { lang: sml text: "server {\n  host: db1.internal\n  port: 5432\n}\n\ntags: [ urgent internal q3 ]\nports: [ 80, 443, 8080 ]" }
        ]
      }

      section 片段复用 {
        children: [
          para { text: "把重复的部分定义成 @名字，用 &名字 以值的形式引用。本站的成员档案就是这么写的。" }
          code { lang: sml text: "@链接 {\n  repo: \"https://gitee.com/rustembed/site\"\n  sml: \"https://sml.swebase.cn\"\n}\n\n档案 {\n  name: Sal\n  links: &链接\n}" }
          para { text: "参考：{link: https://gitee.com/rustembed/site|本仓库}、{link: https://sml.swebase.cn|SML 官网}。" }
        ]
      }
    ]
  }

  topic 本站支持的块 {
    children: [
      table {
        head: [ 块 用途 ]
        rows: [
          [ "topic / section" "标题，自动进章节树与导图；带 label 生成锚点" ]
          [ "para" "段落（text 字段支持内联角色）" ]
          [ "code { lang text }" "代码块" ]
          [ "quote" "引用" ]
          [ "ul / ol { items: [ … ] }" "列表" ]
          [ "table { head rows }" "表格" ]
          [ "img { src alt caption }" "图片" ]
          [ "video { bvid }" "B 站视频（只接受 BV 号）" ]
          [ "note / tip / warn" "提示框" ]
          [ "theorem / proof / math" "定理、证明、公式" ]
        ]
      }
      para { text: "内联角色：{ref: 锚点|文字}、{term: 术语}、{em: 强调}、{math: \"E = mc^2\"}、{link: url|文字}。" }
    ]
  }
]
