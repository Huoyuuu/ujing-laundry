# U净附近洗衣房

一个简单的 Python + HTML 小页面，查看东b浑南 **3、4、5、6 舍**各楼层洗衣机的空闲情况。

每 60 秒自动刷新，也可以点击按钮手动刷新。

如果机器已满，会显示最短等待时间

![4613ccc4cd564da90e866461dceffbcf.png](https://files.seeusercontent.com/2026/09/07/q2So/4613ccc4cd564da90e866461dceffbcf.png)
## 运行

需要 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。在项目目录运行：

```bash
uv sync
uv run 'u净查询附近洗衣房.py'
```

首次运行按终端提示操作：

1. 输入手机号，程序发送短信验证码。
2. 输入收到的验证码。
3. 程序在终端输出 JWT，并保存到同目录的 `ujing_config.json`。
4. 自动启动网页服务，打开 http://127.0.0.1:19000

后续运行自动读取本地 JWT，不再发送短信。

## 文件

```text
u净查询附近洗衣房.py   短信登录、FastAPI 服务与查询逻辑
index.html           页面与自动刷新
README.md            使用说明
```

运行后生成的本地文件：

- `ujing_config.json`：明文 JWT。
- `data/latest.json`：最近一次查询结果。JSON 接口为 `/api/status`。
