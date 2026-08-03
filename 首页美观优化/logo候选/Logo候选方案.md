# NewsEviday Logo 候选方案

状态：用户已选择 A“Signal N”，生产资产已完成接入；其余方案保留为决策记录。

生成日期：2026-08-03  
生成方式：内置图像生成能力，`logo-brand` 概念展示模式  
使用范围：方向讨论，不直接作为生产 SVG

## 1. 方案对比

| 方案 | 核心表达 | 优点 | 主要风险 | 建议 |
| --- | --- | --- | --- | --- |
| A Signal N | N 形信号路径 + 证据节点 | 与首页信号场、证据回链和产品名结合最紧；小尺寸识别清楚 | 需要在生产 SVG 中进一步校准断点与线宽 | **推荐** |
| B Evidence Orbit | NE 字母组合 + 单条轨道 | 跨地域追踪和持续更新的语义直观 | 轨道类标识较常见，独特性弱于 A | 次选 |
| C Proof Prism | 折面棱镜 + 中心证据点 | 图形完整，品牌感强，深浅背景适应性好 | 容易联想到安全、加密或企业服务，需要弱化盾牌感 | 可选 |
| D Daily Pulse | 更新脉冲 + NE 线形 | “每日变化”表达直接，带编辑媒体气质 | 横向图形在 favicon 中不如 A、C 稳定，可能被误读为心电图 | 不优先 |

## 2. 推荐结论

优先选择 A。它把 `News` 的变化信号、`Evidence` 的证据节点和品牌首字母 N 放在同一个简单结构里，也能与已确认的首页粒子和轨道语言形成一致的品牌系统。

如果希望 Logo 更像独立品牌、弱化字母感，可选择 C；生产绘制时需要把图形改得更开放，避免盾牌或加密产品联想。

最终决策：选择 A“Signal N”。生产版本重新校准了线宽、转折、证据圆环和 16-32px 小尺寸表现，没有直接使用生成图中的文字或位图标识。

## 3. 候选稿

- `reference/01-Signal-N.png`
- `reference/02-Evidence-Orbit.png`
- `reference/03-Proof-Prism.png`
- `reference/04-Daily-Pulse.png`

## 4. 已完成的生产步骤

1. [x] 根据入选方向重新绘制确定性 SVG，不直接描摹生成图中的文字。
2. [x] 固定 24px、32px、导航横版和纯图形四种使用方式。
3. [x] 输出深色背景反白、浅色背景深色和 favicon 版本。
4. [x] 替换顶部导航标识、favicon、站点元数据图片，并做 360-1440px 回归。
5. [x] 完成作品集 Demo 范围内的视觉近似检查，并记录商用边界。

## 5. 生产资产

- Vue 导航标识：`apps/web/src/components/BrandMark.vue`
- 浅色背景 SVG：`apps/web/public/brand/newseviday-signal-n.svg`
- 深色背景反白 SVG：`apps/web/public/brand/newseviday-signal-n-inverse.svg`
- 浏览器图标：`apps/web/public/favicon.svg`
- Apple Touch Icon：`apps/web/public/brand/apple-touch-icon.png`
- 分享图源文件：`apps/web/public/brand/newseviday-og-source.svg`
- Open Graph / Twitter 分享图：`apps/web/public/brand/newseviday-og.png`

本次完成产品级视觉近似检查，但不构成正式商标检索或法律意见。项目作为作品集 Demo 使用；如进入商业化阶段，应另行完成商标检索。

## 6. 生成提示词摘要

四组提示词共用约束：NewsEviday AI 产品与技术情报网站；Linear 式简约、现代、大气；深空海军蓝、紫色、浅紫和米白；扁平矢量友好；24px 可识别；同时展示图形标、准确英文 wordmark、深浅色版本和 favicon；禁止 3D、拟物、水印、复杂光效和现有公司相似标志。

- A：一条连续信号路径构成几何 N，转折处设置圆形证据节点。
- B：N 与 E 融合为紧凑字母组合，外部使用一条不闭合椭圆轨道和追踪点。
- C：两到三块折面构成开放棱镜或书签，中间保留一个证据点，负空间隐约形成 N。
- D：水平信号线形成一次克制脉冲，再转折为 N 或 E 局部轮廓，末端设置更新点。
