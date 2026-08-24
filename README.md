# ios-carrier-profiles

这是由 `carrier-profiles` 生成的 iOS 运营商运行时画像发布仓库。

运行时文件：

- `index.yaml`：Bundle 索引；
- `inventory.yaml`：全量 Bundle 扫描统计；
- `selectors/<plmn>.yaml`：SIM selector manifest；
- `profiles/<bundle-slug>.yaml`：canonical Bundle YAML。

VoHive 先下载 home PLMN 对应的 selector，再只下载命中的一个 Bundle。

## 运行时选择流程

发布仓库的根 URL 可以直接使用 GitHub Raw，例如：

```text
https://raw.githubusercontent.com/iniwex5/ios-carrier-profiles/main
```

运行时不要根据文件名猜运营商，也不要先下载全部 `profiles/`。正确流程是：

1. 从 SIM/eSIM 读取归属 PLMN（`home_mcc` + `home_mnc`）、IMSI、ICCID、GID1、GID2 和 SPN。
2. 保留真实 MNC 宽度拼接 `home_plmn`。例如 `234/10` 使用 `23410`，`310/280` 使用 `310280`，不要把所有 PLMN 强制补成六位。
3. 下载 `selectors/<home_plmn>.yaml`。例如 `310280` 对应：

   ```text
   .../selectors/310280.yaml
   ```

4. 在 selector manifest 中匹配 SIM 身份，得到唯一的 `path`，例如 `profiles/att_redpocket_us.yaml`。
5. 只下载该 Bundle YAML，校验其 `id` 和 `supported_plmns`，再交给 `vowifi-go` 展开当前 PLMN 的配置。

VoHive 的本地 `data/carrier-profiles` 选择结果优先于云端；没有本地命中时才访问云端。云端或网络不可用时，selector 和已经下载的 Bundle 使用本地缓存。网络请求只携带 PLMN 和公开文件路径，不把完整 ICCID、IMSI 或 GID 放进 URL。

### Selector manifest

每个 `selectors/<plmn>.yaml` 只描述这个 home PLMN 下可能命中的 Bundle，不包含运行时 IMS 参数。示例：

```yaml
version: 2
plmn: "310280"
profiles:
  - id: apple_att_redpocket_us
    path: profiles/att_redpocket_us.yaml
    selectors:
      - raw: 310280_GID1-42
        conditions:
          - field: gid1
            match: prefix
            value: "42"
```

支持的条件如下：

| 字段 | 支持的匹配 | 值格式 |
| --- | --- | --- |
| `gid1`、`gid2` | `prefix`、`exact` | 十六进制，匹配时不区分大小写 |
| `iccid`、`imsi` | `prefix` | 十进制数字 |
| `spn` | `exact_casefold` | 不区分大小写的字符串 |

匹配规则：

- 同一个 selector 的多个 `conditions` 是 AND，必须全部满足；
- 同一个 Bundle 的多个 selector 是 OR，任意一个满足即可；
- 先比较所有受约束 selector 的具体程度，`exact` 比 `prefix` 更具体，较长的前缀优先；
- 最高分相同的两个 Bundle 会返回歧义错误，不会随机选择；
- 受约束 selector 全部不匹配后，才允许使用唯一的 `generic: true` Bundle 或无条件 selector；
- 没有唯一匹配时，VoHive 应记录匹配失败并使用标准默认画像，不能猜测 MVNO。

例如 `23410` 的 selector 中，GID1 前缀 `508FFFFF` 会命中 `profiles/o2_giffgaff_uk.yaml`；没有命中任何受约束条件时，才可以回退到标记为 `generic` 的 O2 通用 Bundle。`310280` 中 GID1 前缀 `42` 会命中 `profiles/att_redpocket_us.yaml`，而不是同一 PLMN 下的 AT&T 主品牌画像。

GID1/GID2 不可读取时，受约束的 GID selector 视为不匹配；只有 generic selector 才能继续。这样可以避免把缺失的 SIM 身份误判成某个 MVNO。

### Bundle YAML 展开

命中后下载的 `profiles/<bundle-slug>.yaml` 是一个 Apple Bundle 的 canonical 配置：

```yaml
version: 3
kind: carrier_bundle
id: apple_o2_giffgaff_uk
bundle: O2_Giffgaff_UK.bundle
supported_plmns: ["23410"]
common:
  ims:
    apn: ims
plmn_overrides:
  "23410":
    ims:
      ip_stack: ipv6
```

运行时按以下顺序展开：

1. 读取 `common`；
2. 递归合并当前 home PLMN 的 `plmn_overrides[home_plmn]`；
3. 如果存在当前 selector 对应的 `selector_overrides`，再应用该覆盖；
4. 将最终配置交给 `vowifi/volte`。同一个 Bundle 支持多个 PLMN 时仍只保留一个 YAML，不按 PLMN 复制文件。

`index.yaml` 用于发布端列出 Bundle 与支持的 PLMN；`inventory.yaml`、`reports/` 和 `errors.yaml` 是生成与审核产物，不参与运行时 selector 匹配。

### 漫游边界

画像选择始终使用 SIM 的 **home PLMN**。当前注册到的 serving PLMN 只用于驻网、VoLTE 的 serving 网络信息和 P-CSCF 处理，不能在漫游时改用 serving PLMN 选择另一个 SIM 归属 Bundle。
