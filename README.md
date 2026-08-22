# ios-carrier-profiles

这是由 `carrier-profiles` 生成的 iOS 运营商运行时画像发布仓库。

运行时文件：

- `index.yaml`：Bundle 索引；
- `inventory.yaml`：全量 Bundle 扫描统计；
- `selectors/<plmn>.yaml`：SIM selector manifest；
- `profiles/<bundle-slug>.yaml`：canonical Bundle YAML。

VoHive 先下载 home PLMN 对应的 selector，再只下载命中的一个 Bundle。
