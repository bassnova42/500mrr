
## Cloudflare 部署

网站部署在 Cloudflare Pages：https://500mrr.rokoai.fun （备用地址 https://500mrr.pages.dev ）。改完数据后运行 `python3 scripts/build.py`，再用 cf-deploy 部署 `site/` 文件夹。

```cf-deploy
{
  "token_env": "CF_TOKEN_BA",
  "account_id": "1c29ea2a8e89fa7bb682b7019105e563",
  "worker": false,
  "pages": [{ "project": "500mrr", "dir": "site", "branch": "main" }],
  "verify": [
    { "url": "https://500mrr.rokoai.fun/", "contains": "HN 月入 $500 副业名录" },
    { "url": "https://500mrr.pages.dev/", "contains": "HN 月入 $500 副业名录" }
  ]
}
```
