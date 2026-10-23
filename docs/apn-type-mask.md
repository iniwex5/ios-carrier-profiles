# APN `type_mask` 规范

画像里每条 APN 都可能带一个整数 `type_mask`。它是**位掩码**：每一位代表一种用途，一条 APN 可以把几种用途叠在一起。
本文是读取、使用、手工编辑这个字段的唯一依据，写代码或改画像时对照本文，不要再凭名字猜。

## 一句话版本

- **判断一条 APN 能不能用于数据流量：`type_mask & 0x1 != 0`。** 字段缺失、为 `0`、或没有这一位，一律不是数据 APN。
- 专用 APN 只有单独一位：IMS `131072`、紧急 `262144`、彩信 `4`、XCAP/HOS `1048576`、语音信箱 `2`、热点 `16`、管理/OTA `512`。
- 主数据 APN 是 `0x1` 加一些附带位，附带位说明它还兼了什么活，所以**同样是"默认数据"，值会不一样**（`1`、`49`、`53`、`32817`…），见 §3。
- 不要用"等于某个值"判断，也不要用"不含 IMS/紧急位"来排除：`ereseller`（`1081351`）同时带数据、语音信箱、彩信、XCAP 等位，是正经的数据 APN。

## 1. 来源与可信度

数据链路：Apple 运营商包 `carrier.plist` 里 APN 字典的 `type-mask`（连字符）和 `tech-type-mask`
→ 生成器 `carrier-profiles/internal/profile/apn_catalog_mapping.go` 映射为 YAML 的 `type_mask`、`tech_type_mask`
→ 本仓库 `profiles/*.yaml` 的 `common.apns`（可被 `plmn_overrides.<plmn>.apns`、`selector_overrides.<selector>.apns` 整体替换）。

**Apple 没有公开这个字段的文档。** 下面每一位的含义，都是对 2114 条 APN 条目统计"名字与掩码的共现"得到的，并和生成器自带的分类
（`apnCatalogTailRank`：`262144`/`sos` 紧急、`16`/`hotspot` 热点、`1048576`/`hos`/`xcap` XCAP/HOS）互相印证。
所以每一位都标了把握等级：

- **确定**：该用途的 APN 名字几乎总是恰好等于这个单独的位；
- **较确定**：统计支持，但个别运营商可能不遵守；
- **不明**：有出现，但没有可解释的名字规律，**代码不依赖这些位**。

所有数字由 `docs/apn-type-mask-stats.py` 生成（`python3 docs/apn-type-mask-stats.py`，只读），当前数字对应画像仓库提交 `752bc95`。

## 2. 位表

| 位 | 值 | 含义 | 把握 | 依据 |
| --- | --- | --- | --- | --- |
| 0 | `0x1` | **默认数据** | 较确定 | 单独为 `1` 的是 `internet`、`net`、`web.c1.bm`、`phone` 等；名为 `mms` 的 202 条里只有 1 条（复合值）带它；带这一位的条目**从不同时带 IMS 位或紧急位**（0 条） |
| 1 | `0x2` | 语音信箱 | 确定 | 名为 `vvm.*` 的 7 条全是 `2`；另有 `service` ×2 |
| 2 | `0x4` | 彩信 | 确定 | 名为 `mms` 的 202 条里 196 条恰好是 `4`；`Wap`/`CTWAP` 等彩信网关也是 `4` |
| 4 | `0x10` | 热点/共享 | 较确定 | `hotspot`、`nrhotspot`、`*mht`、`tethering.*` 单独为 `16`；名为 `hotspot` 的 23 条是 `16`（18）或 `48`（5） |
| 5 | `0x20` | 不明（总与 `0x10` 同现） | 不明 | 854 条带它，**没有一条不带 `0x10`**；单独出现 0 条。多半是热点相关，但具体含义不确定 |
| 9 | `0x200` | 管理/OTA | 确定 | 单独为 `512` 的 15 条是 `vzwadmin`、`admin.*`、`ota*` |
| 14 | `0x4000` | 运营商应用（推测） | 不明 | 18 条，名字是 `vzwapp`、`vsblapp`（Verizon 系），从不单独出现 |
| 15 | `0x8000` | 不明 | 不明 | 317 条，几乎都叠在数据 APN 上；与 IMS 有相关性（见 §3），含义不明 |
| 17 | `0x20000` | **IMS** | 确定 | 名为 `ims*` 的 393 条里 391 条恰好是 `131072`（另 2 条缺字段）；值为 `131072` 的 393 条，名字全部含 `ims` |
| 18 | `0x40000` | **紧急** | 确定 | 名为 `sos`/`*emergency` 的 177 条里 176 条恰好是 `262144`；值为 `262144` 的 194 条，名字全部是 `sos`/`*emergency`（18 条名字为空） |
| 20 | `0x100000` | XCAP/HOS | 确定 | 单独为 `1048576` 的 186 条，名字是 `hos`、`xcap`，其余多为 `ut`（Ut 接口即 XCAP）、`service`、`netsvcs`；复合出现 314 条 |
| 13、16、22 | `0x2000`、`0x10000`、`0x400000` | 不明 | 不明 | 分别 1、10、21 条，都叠在其他位上，无名字规律 |

没有出现过的位（`0x8`、`0x40`、`0x80`、`0x100`…）没有任何条目使用，不要假设它们的含义（尤其不要套用 Android 的 `ApnSetting.TYPE_*`，两套值不同）。

## 3. 怎么读一个值

### 3.1 专用 APN：单独一位

| 用途 | 值 | 例子 |
| --- | --- | --- |
| IMS | `131072` | `ims` |
| 紧急 | `262144` | `sos`、`vzwemergency` |
| XCAP/HOS | `1048576` | `hos`、`xcap` |
| 彩信 | `4` | `mms`、`Wap` |
| 语音信箱 | `2` | `vvm.clarochile.cl` |
| 热点 | `16` | `hotspot`、`nrhotspot`、`resellermht` |
| 管理/OTA | `512` | `vzwadmin`、`ota` |

### 3.2 主数据 APN：`0x1` + 附带位，为什么值不一样

主数据 APN 一定带 `0x1`，差别是它**还兼了什么**：

| 值 | 组成 | 真实例子 | 为什么 |
| --- | --- | --- | --- |
| `1` | 只有数据 | `cellcom`：`ccinternet 1`，另有单独的 `cchotspot 16`<br>`awcc_af`：`INTERNET 1`，另有 `hotspot 48` | 运营商有**单独的热点 APN**，数据 APN 不必兼热点 |
| `49` | 数据 + 热点（`0x1`+`0x10`+`0x20`） | `8ta_za`：`internet 49`，另有 `mms 4`<br>`alcom_ax`：`internet 49`，`mms 4` | 最常见：同一个 APN 既上网也给热点用 |
| `53` | `49` + 彩信 | `digicel_mq`：只有一条 `digicel 53`<br>`bhartiairtel_lk`：`airtellive 53` | **没有单独的彩信 APN**，数据 APN 兼做彩信 |
| `51` | `49` + 语音信箱位 | `kpn_telfort_nl`：只有一条 `internet 51` | 语音信箱并进了数据 APN（含义按第 1 位推断） |
| `32817` | `49` + `0x8000` | `2degrees_nz`：`internet 32817`，另有 IMS、HOS、sos<br>`ais_th`、`avea_tr`、`batelco_bh` | `0x8000` 含义不明，见下 |
| `32819` | `51` + `0x8000` | `1and1_de`：`internet 32819`<br>`docomo_jp`：`spmode.ne.jp 32819` | 同上，多了语音信箱位 |
| `1081351` | 数据 + 语音信箱 + 彩信 + `0x8000` + XCAP | `ereseller` | 一个 APN 身兼多职，**所以不能按"等于某值"判断** |

统计依据（按"运营商 × 支持的 PLMN"组合，1330 个有数据条目的组合）：

- 运营商**没有单独热点 APN**时，数据 APN 带热点位的是 1163/1173；**有单独热点 APN**时只有 7/157。
- **没有单独彩信 APN**时，数据 APN 带彩信位的是 257/905；**有单独彩信 APN**时只有 33/425（不是所有运营商都合并，方向是对的）。
- `0x8000`：带这一位的数据 APN 所在画像里，有 IMS 条目的是 496/522；不带这一位的是 223/808。它更像"VoLTE/IMS 时代画像"的标记，含义不明。

### 3.3 同名两条：数据条目 + 热点副本

同一个 APN 名字经常出现两次，例如：

```yaml
- apn: internet      # 数据 + 热点
  type_mask: 49
- apn: internet      # 只给热点用的副本，没有数据位
  type_mask: 48
```

第二条（`48`）**不是数据 APN**，按 `0x1` 位规则会被自动跳过，选中的是前一条。同类还有 `net 1` + `net 48`（`apua_ag`）、
`internet 51` + `internet 50`（`choice_gu`）。少数画像里同名两条都带数据位（如 `atn_bm` 的 `web.c1.bm` 为 `1` 和 `49`），按文件顺序取第一条。

## 4. 目录里的顺序

生成器写出 `apns` 时会做一次**稳定排序**（`apnCatalogTailRank`），并去掉完全相同的重复条目：

1. 普通条目（数据、IMS、彩信、语音信箱、管理……）保持原来的相对顺序，排在最前；
2. 然后是热点（`type_mask == 16` 或名字含 `hotspot`）；
3. 然后是 XCAP/HOS（`type_mask == 1048576` 或名字为 `hos`/含 `xcap`）；
4. 最后是紧急（`type_mask == 262144` 或名字为 `sos`/含 `emergency`）。

排序比较的是**精确值**，所以 `48` 的热点副本不会被后置，会留在原位。结果是数据 APN 通常在最前面，但 IMS、彩信、语音信箱可能排在它前面：
1333 个组合里，3 个没有 `apns`，1273 个第一条就是数据条目，57 个要往后找，0 个找不到数据条目。

## 5. 缺失与异常值

- **缺 `type_mask` = 不是数据 APN。** 全库 19 条缺失，是 `apps.bell.ca`、`vas.wlan.three.com.hk`、`vowifiorange`、`hos`、`sos`、`ims`、
  `service` 等非数据条目，外加 1 条连 `apn` 字段都没有的。唯一的例外是手工加的 DITO `internet.dito.ph`（20404/51566），已补 `49`。
- **`type_mask: 0` = 不是数据 APN。** 8 条，多为 `vzwadmin`。
- **`tech_type_mask` 不参与判断。** 它是"按接入技术"的另一个掩码，736 条数据条目里只有 49 条带它，所以不能用它回退。
- 值不是非负整数时，当作缺失处理（不会报错，也不会让整个目录失效）。

## 6. 使用规则（VoHive Rust 的读取方式）

数据 APN 的取值顺序：**卡策略里用户自定义的 APN → 画像里第一个可用的数据 APN → 空 APN（网络默认）。** 其中"画像里的数据 APN"这样挑：

1. 取展开后的 `apns`（`common` 被 `plmn_overrides`、`selector_overrides` 整体替换后的结果，以运行时画像为准，不要自己拼）；
2. 过滤出 `type_mask & 0x1 != 0` 的条目（缺失、`0`、没有该位都排除）；
3. **取文件顺序里的第一条**；
4. 只对这一条做可用性检查：
   - 带非空的 `username`/`password`/`auth_type`（或形状无法识别）→ **不使用，回落为空 APN**。bearer 层目前不支持 APN 凭据，不能悄悄不带认证发送；全库 152/1330 个组合属于这种；
   - APN 语法非法 → 回落为空 APN（全库 0 个）。规则同 `is_valid_data_apn`：ASCII、不超过 100 字节、点分标签每段 1–63 字节、只含字母数字和 `-`、不以 `-` 开头或结尾；
   - APN 本身是空串 → 空 APN，这本来就是"网络默认"（全库 36 个）；
5. **不回退到后面的条目。** 第一条数据条目是运营商的首选，被排除后悄悄换成第二条可能换了套餐或计费；实际只有 C Spire 的 2 个组合后面还有无凭据的数据条目；
6. 不回退到 `tech_type_mask`，不按名字猜，不用"不含 IMS/紧急位"来排除。

代码位置（`vohive-rs`）：`crates/policy/src/snapshot.rs` 的 `APN_TYPE_DEFAULT_DATA`、`parse_data_apns`、`CarrierPolicyView::default_data_apn`；
语法校验 `crates/card-policy/src/model.rs` 的 `is_valid_data_apn`。`crates/policy/tests/data_apn.rs` 里有按本文例子写的用例。

## 7. 手工添加或修改 APN 条目

- **主数据 APN 写 `type_mask: 49`**（大多数运营商的值）；IMS 写 `131072`；彩信 `4`；紧急 `262144`；XCAP/HOS `1048576`。**不要省略这个字段**，否则会被当作非数据 APN。
- 画像是生成物。要改手工包，**必须同时改本地源头** `carrier-profiles/ios-carrier-bundles/Custom Bundles/<名字>.bundle/carrier.plist`，键名是连字符的
  `type-mask`（该目录被 git 忽略，只在本机），否则下次重新生成会丢。
- 验证流程（DITO 的例子）：把改过的 bundle 单独放进临时目录，`carrier-profile-gen generate-all --input-dir <空目录> --custom-input-dir <临时目录> --output-dir <临时输出>`，
  对比临时输出和已发布的 `profiles/dito_ph.yaml`，应当**只差预期的那一行**，再复制到发布仓库。重新生成全库的注意事项见 `carrier-profiles` 仓库的说明。

## 8. 已知局限

- 位的含义是推断的，不是官方定义。1333 个组合没有找到反例，但个别运营商可能不遵守；VoHive 的实机核对清单里有一项专门核对这一点。
- `0x20`、`0x8000`、`0x4000`、`0x2000`、`0x10000`、`0x400000` 含义不明，不要在任何逻辑里依赖它们。
- 统计只展开了 `common` 与 `plmn_overrides`；`selector_overrides`（25 个画像）按"针对某张 SIM 的细化"处理，VoHive 运行时会展开，本文统计不展开。

## 9. 复现

```bash
python3 docs/apn-type-mask-stats.py            # 默认读 ../profiles
python3 docs/apn-type-mask-stats.py /path/to/profiles
```

输出包括：取值分布及分解、每一位的出现数和"单独出现"的名字、名字→掩码对照、缺失 `type_mask` 的条目、各组合最终会选中哪一条及原因分布、
以及 §3.2 的相关性统计。画像更新后重跑，数字变化时更新本文（并写明对应的提交）。

## 附：常见值速查

| 值 | 十六进制 | 位 | 典型含义 | 条目数 |
| --- | --- | --- | --- | --- |
| `131072` | `0x20000` | IMS | `ims` | 393 |
| `49` | `0x31` | 数据 + 热点 | 主数据 APN | 322 |
| `4` | `0x4` | 彩信 | `mms` | 237 |
| `48` | `0x30` | 热点 | 同名数据 APN 的热点副本、`hotspot` | 195 |
| `262144` | `0x40000` | 紧急 | `sos` | 194 |
| `1048576` | `0x100000` | XCAP/HOS | `hos`、`xcap` | 186 |
| `32817` | `0x8031` | `49` + `0x8000` | 主数据 APN（VoLTE 时代） | 99 |
| `16` | `0x10` | 热点 | 单独的热点 APN | 33 |
| `53` | `0x35` | 数据 + 热点 + 彩信 | 数据兼彩信 | 28 |
| `32819` | `0x8033` | `51` + `0x8000` | 主数据 APN | 25 |
| `1081351` | `0x108007` | 数据 + 语音信箱 + 彩信 + `0x8000` + XCAP | `ereseller` | 24 |
| `1` | `0x1` | 数据 | 单独的数据 APN | 17 |
| `51` | `0x33` | 数据 + 语音信箱位 + 热点 | 数据兼语音信箱 | 16 |
| `512` | `0x200` | 管理/OTA | `vzwadmin` | 15 |
