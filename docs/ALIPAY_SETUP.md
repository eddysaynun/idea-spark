# 支付宝自动支付生产配置

Idea Spark 使用支付宝开放平台电脑网站支付与手机网站支付。桌面浏览器进入电脑网站收银台，移动浏览器进入手机网站收银台。固定商家收钱码不能提供可验签的逐订单通知，不参与自动发额。

## 支付链路

1. 登录用户在账户页选择额度包。
2. 主 Worker 在 D1 创建金额与权益快照。
3. 主 Worker 通过私有 Service Binding 调用 `idea-spark-payment-gateway`。
4. 支付网关按浏览器场景生成 `alipay.trade.page.pay` 或 `alipay.trade.wap.pay` 的 RSA2 签名收银台地址。
5. 支付宝向 `/api/billing/webhooks/alipay` 发送异步通知。
6. 支付网关用支付宝公钥验签，并校验 `app_id`、`seller_id` 和交易状态。
7. 主 Worker 再校验渠道、商户订单号和金额，通过 D1 batch 幂等发放两类额度。

浏览器跳转、同步回跳参数和订单轮询都不能触发发额。同步回跳只把用户带回账户页并开始查询服务端订单状态。

## 支付宝侧准备

- 在支付宝开放平台创建网页/移动应用并取得 `AppID`。
- 为应用开通电脑网站支付与手机网站支付能力；纯线上数字服务不依赖当面付。
- 生成 RSA2 应用密钥对，把应用公钥配置到支付宝开放平台。
- 从开放平台取得支付宝公钥，不能误用应用公钥或支付宝证书文件。
- 从商家中心确认收款账号对应的 `Seller ID`。

## Cloudflare Secrets

支付网关 Worker：

- `PAYMENT_GATEWAY_TOKEN`：主 Worker 与网关之间的随机高强度共享令牌。
- `ALIPAY_APP_ID`
- `ALIPAY_PRIVATE_KEY`：PKCS#8 PEM 应用私钥。
- `ALIPAY_PUBLIC_KEY`：SPKI PEM 支付宝公钥。
- `ALIPAY_SELLER_ID`

主 Worker：

- `PAYMENT_GATEWAY_TOKEN`：必须与支付网关完全相同。

所有密钥只通过 Cloudflare Secret 配置，不进入 `wrangler.jsonc`、Git、前端变量或日志。

## 发布顺序

1. 部署 `idea-spark-payment-gateway`，并配置上述五个 Secrets。
2. 在主 Worker 的 `services` 中增加：

   ```json
   {
     "binding": "PAYMENT_GATEWAY",
     "service": "idea-spark-payment-gateway"
   }
   ```

3. 将主 Worker 非敏感变量 `ALIPAY_ENABLED` 改为 `true`。
4. 配置主 Worker 的 `PAYMENT_GATEWAY_TOKEN` Secret，再发布主 Worker。
5. 分别检查桌面端和移动端能进入对应支付宝收银台。
6. 用最低价格套餐完成真实付款，确认 D1 订单只发额一次、重复通知返回成功但不重复加额。

在步骤 1–4 任一项缺失时，前端只显示“支付宝配置中”，后端不会创建支付订单。
