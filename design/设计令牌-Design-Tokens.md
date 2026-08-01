# NewsEviday Design Tokens

| 项目 | 内容 |
|---|---|
| 版本 | v1.0 |
| 状态 | 已冻结，可作为前端实现基线 |
| 冻结日期 | 2026-08-01 |
| 适用主题 | MVP 浅色主题 |
| 实现方式 | Vue 3 + CSS Variables |
| CSS 文件 | `design/tokens/tokens.css` |
| JSON 文件 | `design/tokens/tokens.json` |

## 1. 设计读取

NewsEviday 是面向 AI 产品经理、数据产品经理和招聘者的公开情报产品。视觉语言简约、现代、大气，使用雾紫大画布与高效率信息流。

设计参数：

| 参数 | 数值 | 影响 |
|---|---:|---|
| DESIGN_VARIANCE | 5 | 允许非对称页面和大留白，产品组件保持稳定网格 |
| MOTION_INTENSITY | 4 | 只使用滚动收缩、进入、状态反馈和轻量布局过渡 |
| VISUAL_DENSITY | 6 | 首屏舒展，信息流、证据和 Eval 区域保持较高效率 |

MVP 使用单一浅色主题。深色模式仍属于 Could 范围，后续需要独立视觉确认，不在本次 Token 中预设未确认颜色。

## 2. 命名规则

- CSS 变量统一使用 `--ne-` 前缀；
- Primitive Token 表示原始色阶和尺寸；
- Semantic Token 表示页面角色，组件只消费 Semantic Token；
- 业务状态使用 `success`、`warning`、`danger`，不把品牌紫色当作成功或错误状态；
- 新增 Token 前先确认现有 Token 无法表达，禁止为单个页面创建一次性颜色。

## 3. 色彩

### 3.1 品牌紫色阶

| Token | 数值 | 用途 |
|---|---|---|
| `purple-50` | `#F6F3FF` | 大面积极浅品牌背景 |
| `purple-100` | `#EEE9FF` | 推荐原因、选中背景 |
| `purple-200` | `#DED4FF` | 柔和描边 |
| `purple-300` | `#C7B8F5` | 装饰性细节，不承担正文 |
| `purple-400` | `#9E86E8` | 非主要图表线 |
| `purple-500` | `#7257D5` | 品牌主色、链接、引用、焦点 |
| `purple-600` | `#6246C7` | 主要按钮背景 |
| `purple-700` | `#5135AA` | 按下状态和高对比文字 |
| `purple-800` | `#40298A` | 深色品牌文字 |
| `purple-900` | `#32226A` | 极深品牌文字 |

紫色不使用外发光，不与蓝色组成霓虹渐变。环境光只允许使用 `purple-50` 到 `purple-100`。

### 3.2 中性色与语义色

| Semantic Token | 数值 | 用途 |
|---|---|---|
| `bg-page` | `#F5F3FA` | 页面雾紫背景 |
| `bg-surface` | `#FFFFFF` | 内容主表面 |
| `bg-subtle` | `#FAF9FC` | 次级区域和分组背景 |
| `bg-tinted` | `#F0ECFC` | 推荐、引用和选中区域 |
| `bg-inverse` | `#1B1824` | 反色提示和深色局部表面 |
| `text-strong` | `#1B1824` | 页面标题、重要数字 |
| `text-default` | `#312D3D` | 正文和组件标题 |
| `text-secondary` | `#625D70` | 辅助说明和元数据 |
| `text-muted` | `#706A7B` | 次级标签，不能用于禁用以外的小字号正文 |
| `text-disabled` | `#9B96A5` | 禁用状态 |
| `border-subtle` | `#E9E5EF` | 普通分隔线 |
| `border-default` | `#D9D4E2` | 输入框和容器边界 |
| `border-strong` | `#B9B2C5` | 悬停和需要强调的边界 |
| `focus` | `#8B6FE8` | 键盘焦点 |
| `success` | `#2F7D5A` | 成功和正常状态 |
| `success-subtle` | `#EAF6EF` | 成功状态浅背景 |
| `warning` | `#8A5B12` | 历史快照、延迟和提醒 |
| `warning-subtle` | `#FFF5DF` | 警告状态浅背景 |
| `danger` | `#B54858` | 错误和危险动作 |
| `danger-subtle` | `#FFF0F2` | 错误状态浅背景 |
| `overlay` | `rgb(27 24 36 / 44%)` | 抽屉和弹层遮罩 |

对比度基线：

| 组合 | 对比度 | 结论 |
|---|---:|---|
| `text-strong` / 白色 | 17.46:1 | 通过 AAA |
| `text-default` / 白色 | 13.35:1 | 通过 AAA |
| `text-secondary` / 白色 | 6.33:1 | 通过 AA |
| `text-muted` / 页面背景 | 4.73:1 | 通过 AA |
| 白色 / `purple-600` | 6.52:1 | 主要按钮通过 AA |
| `purple-500` / 白色 | 5.20:1 | 链接和引用通过 AA |
| `danger` / 白色 | 5.21:1 | 错误文字通过 AA |

## 4. 字体

字体栈：

- 中英文界面：`Geist Sans`、`Noto Sans SC`、`Microsoft YaHei UI`、`PingFang SC`、系统无衬线；
- 等宽：`Geist Mono`、`SFMono-Regular`、`Consolas`、系统等宽。

生产环境优先自托管字体并设置 `font-display: swap`。中文正文不得依赖网络字体才能正常显示。

| Token | 字号 | 行高 Token | 推荐字重 | 用途 |
|---|---|---|---:|---|
| `display` | `clamp(40px, 5vw, 68px)` | `display` = 1.04 | 600/700 | 首页和产品介绍主标题 |
| `h1` | `clamp(34px, 4vw, 52px)` | `heading` = 1.16 | 600/700 | 文章、问答和简报标题 |
| `h2` | `32px` | `heading` = 1.16 | 600 | 页面主要章节 |
| `h3` | `24px` | `heading` = 1.16 | 600 | 内容章节 |
| `title` | `18px` | `title` = 1.35 | 600 | 情报条目和面板标题 |
| `body-lg` | `16px` | `body` = 1.65 | 400 | 长文正文 |
| `body` | `14px` | `body` = 1.65 | 400 | 产品界面正文 |
| `label` | `13px` | `compact` = 1.4 | 500/600 | 按钮、标签、表单标签 |
| `caption` | `12px` | `compact` = 1.4 | 400/500 | 元数据、时间、Trace 技术字段 |

规则：

- 中文大标题最多两行；
- 长文正文最大宽度 `72ch`；
- 产品界面摘要最大宽度 `64ch`；
- 全大写英文眉题最多用于每三个章节中的一个；
- 页面不混用衬线字体；
- 按钮文字不换行。

## 5. 间距

使用 4px 基础网格。

| Token | 数值 | 常见用途 |
|---|---:|---|
| `space-0` | 0 | 重置 |
| `space-1` | 4px | 图标微调 |
| `space-2` | 8px | 标签内部、紧凑元数据 |
| `space-3` | 12px | 按钮间距、表单内部 |
| `space-4` | 16px | 普通组件 padding |
| `space-5` | 20px | 列表条目间距 |
| `space-6` | 24px | 卡片和面板 padding |
| `space-8` | 32px | 栅格 gap、模块间距 |
| `space-10` | 40px | 页面内容分组 |
| `space-12` | 48px | 章节间距 |
| `space-16` | 64px | 页面区块 |
| `space-20` | 80px | 大标题区域 |
| `space-24` | 96px | 产品介绍大章节 |
| `space-32` | 128px | 仅用于宽屏叙事留白 |

## 6. 圆角、边框与阴影

圆角规则：按钮和输入框使用 8—12px，内容容器 16px，大型弹层 24px，标签使用全圆角。

| Token | 数值 |
|---|---|
| `radius-xs` | 6px |
| `radius-sm` | 8px |
| `radius-md` | 12px |
| `radius-lg` | 16px |
| `radius-xl` | 24px |
| `radius-pill` | 999px |
| `border-hairline` | 1px |
| `border-emphasis` | 2px |
| `shadow-xs` | `0 1px 2px rgb(27 24 36 / 5%)` |
| `shadow-sm` | `0 6px 18px rgb(27 24 36 / 7%)` |
| `shadow-md` | `0 16px 40px rgb(27 24 36 / 10%)` |
| `shadow-focus` | `0 0 0 3px rgb(139 111 232 / 28%)` |

普通内容列表使用分隔线和留白，不使用阴影。阴影只用于下拉菜单、抽屉、弹层和悬浮工具栏。

## 7. 布局与断点

| Token | 数值 | 说明 |
|---|---:|---|
| `container-max` | 1440px | 页面最大宽度 |
| `content-max` | 1200px | 常规产品内容宽度 |
| `reading-max` | 720px | 长文和回答正文宽度 |
| `gutter-mobile` | 16px | 手机页面边距 |
| `gutter-tablet` | 24px | 平板页面边距 |
| `gutter-desktop` | 32px | PC 页面边距 |
| `header-height-mobile` | 56px | 手机和紧凑 Header |
| `header-height-desktop` | 64px | PC 全局 Header |
| `hero-min-height-desktop` | 496px | 首页 PC 大标题区最小高度 |

断点：

| 名称 | 宽度 | 主要变化 |
|---|---:|---|
| `sm` | 640px | 手机横向空间增强 |
| `md` | 768px | 手机转平板 |
| `lg` | 1024px | 可使用部分双栏 |
| `xl` | 1200px | 完整顶部导航和主要双栏 |
| `2xl` | 1440px | 达到内容最大宽度 |

CSS 自定义属性不能直接用于媒体查询，开发时使用以上固定数值。

## 8. 组件尺寸

| 组件 | 高度 | 水平 padding | 圆角 |
|---|---:|---:|---:|
| Button sm | 36px | 14px | 8px |
| Button md | 44px | 18px | 12px |
| Button lg | 48px | 22px | 12px |
| IconButton | 44px | 0 | 12px |
| TextInput | 44px | 14px | 12px |
| SearchInput | 48px | 16px | 12px |
| FilterChip | 36px | 14px | 999px |
| Tag | 24px | 8px | 999px |
| Desktop Header | 64px | 0 | 0 |
| Compact Header | 56px | 0 | 0 |

组件高度使用 `control-sm` = 36px、`control-md` = 44px、`control-lg` = 48px。图标尺寸只使用 16、20、24px 三档，默认线宽 1.75。一个页面只使用一个图标家族。

## 9. 动效

| Token | 数值 | 用途 |
|---|---|---|
| `duration-fast` | 120ms | hover 和轻反馈 |
| `duration-base` | 180ms | 按钮、筛选、显示隐藏 |
| `duration-slow` | 240ms | 导航收缩、抽屉和布局切换 |
| `duration-emphasis` | 360ms | 页面首次关键内容进入 |
| `ease-standard` | `cubic-bezier(0.2, 0, 0, 1)` | 常规过渡 |
| `ease-enter` | `cubic-bezier(0, 0, 0, 1)` | 页面和弹层进入 |
| `ease-exit` | `cubic-bezier(0.4, 0, 1, 1)` | 页面和弹层退出 |

规则：

- 只动画 `transform` 和 `opacity`；
- 不使用持续漂浮、闪烁和装饰性循环；
- 首页标题收缩使用 IntersectionObserver、CSS scroll-driven animation 或 VueUse 等可清理方案，不监听每帧更新 Vue 状态；
- `prefers-reduced-motion: reduce` 时关闭位移、缩放和滚动动画；
- 按钮按下使用 1px 位移或 `scale(0.98)`，二者只选一个。

## 10. 层级

| Token | 数值 | 用途 |
|---|---:|---|
| `z-base` | 0 | 页面内容 |
| `z-sticky` | 20 | 粘性筛选和上下文条 |
| `z-header` | 30 | 全局 Header |
| `z-drawer` | 50 | 导航和证据 Drawer |
| `z-modal` | 60 | 对话框 |
| `z-toast` | 70 | 全局提示 |
| `z-tooltip` | 80 | Tooltip |

禁止在组件中随意使用 `z-index: 9999`。

## 11. 无障碍底线

- 正文和交互文字达到 WCAG AA；
- 键盘焦点使用 `focus` 色与 3px `shadow-focus`，并确保不被容器裁切；
- hover 必须有 focus 和触屏替代；
- 颜色不作为唯一状态标识；
- 触控目标不小于 44px；
- skeleton 与最终内容尺寸一致，减少 CLS；
- 错误显示在对应字段附近，Toast 只用于短暂反馈；
- 图表必须提供文字摘要或数据表替代。

## 12. 变更规则

本版本冻结后，前端开发不得直接修改 Token 数值。

需要变更时：

1. 在设计文档记录问题和影响组件；
2. 修改 CSS 与 JSON 两个 Token 文件；
3. 更新本文版本；
4. 对 1440、1280、1024、768、390、360 六个视口执行视觉回归；
5. 在项目进度文档记录变更。
