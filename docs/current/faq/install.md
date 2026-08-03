# 安装 FAQ

### 问题1: sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file 

请确保您拉取了最新代码，或通过 `mkdir pilot/data` 创建目录。

### 问题2: 模型一直被 kill 掉。

您的 GPU 显存不足，请尝试更换硬件或更换其他 LLM。

### 问题3: 如何在公网上访问网站

您可以尝试使用 gradio 的 [network](https://github.com/gradio-app/gradio/blob/main/gradio/networking.py) 功能来实现。
```python
import secrets
from gradio import networking
token=secrets.token_urlsafe(32)
local_port=5670
url = networking.setup_tunnel('0.0.0.0', local_port, token)
print(f'Public url: {url}')
time.sleep(60 * 60 * 24)
```

使用浏览器打开 `url` 即可访问网站。

### 问题4: (Windows) 执行 `pip install -e .` 报错

错误日志类似如下：
``` 
× python setup.py bdist_wheel did not run successfully.
  │ exit code: 1
  ╰─> [11 lines of output]
      running bdist_wheel
      running build
      running build_py
      creating build
      creating build\lib.win-amd64-cpython-310
      creating build\lib.win-amd64-cpython-310\cchardet
      copying src\cchardet\version.py -> build\lib.win-amd64-cpython-310\cchardet
      copying src\cchardet\__init__.py -> build\lib.win-amd64-cpython-310\cchardet
      running build_ext
      building 'cchardet._cchardet' extension
      error: Microsoft Visual C++ 14.0 or greater is required. Get it with "Microsoft C++ Build Tools": https://visualstudio.microsoft.com/visual-cpp-build-tools/
      [end of output]
```

请从 [visual-cpp-build-tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) 下载并安装 `Microsoft C++ Build Tools`。

### 问题5: `Torch not compiled with CUDA enabled`

```
2023-08-19 16:24:30 | ERROR | stderr |     raise AssertionError("Torch not compiled with CUDA enabled")
2023-08-19 16:24:30 | ERROR | stderr | AssertionError: Torch not compiled with CUDA enabled
```

1. 安装 [CUDA Toolkit](https://developer.nvidia.com/cuda-toolkit-archive)
2. 从 [start-locally](https://pytorch.org/get-started/locally/#start-locally) 重新安装支持 CUDA 的 PyTorch。

### 问题6: `如何将元数据表 chat_history 和 connect_config 从 duckdb 迁移到 sqlite`
```commandline
 python docker/examples/metadata/duckdb2sqlite.py
```

### 问题7: `如何将元数据表 chat_history 和 connect_config 从 duckdb 迁移到 mysql`
```commandline
1. 在 docker/examples/metadata/duckdb2mysql.py 中更新您的 mysql 用户名和密码
2.  python docker/examples/metadata/duckdb2mysql.py
```

### 问题8: `如何管理和迁移我的数据库`

您可以使用 `dbgpt db migration` 命令来管理和迁移您的数据库。

详情请参见以下命令。
```commandline
dbgpt db migration --help
```

首先，您需要创建迁移脚本（仅需一次，除非您清理它）。
该命令会在 `pilot/meta_data` 目录下创建一个 `alembic` 目录和初始迁移脚本。
```commandline
dbgpt db migration init
```

然后您可以使用以下命令升级数据库。
```commandline
dbgpt db migration upgrade
```

每次您更改模型或从 DB-GPT 仓库拉取最新代码时，都需要创建新的迁移脚本。
```commandline

dbgpt db migration migrate -m "your message"
```

然后您可以使用以下命令升级数据库。
```commandline
dbgpt db migration upgrade
```

### 问题9: `alembic.util.exc.CommandError: Target database is not up to date.`

**解决方案 1:**

运行以下命令升级数据库。
```commandline
dbgpt db migration upgrade
```

**解决方案 2:**

运行以下命令清理迁移脚本和迁移历史。
```commandline
dbgpt db migration clean -y
```

**解决方案 3:**

如果您已经运行了上述命令，但错误仍然存在，
您可以尝试以下命令清理迁移脚本、迁移历史和数据。
警告：此命令将删除您的所有数据！！！请谨慎使用。

```commandline
dbgpt db migration clean --drop_all_tables -y --confirm_drop_all_tables
```
或
```commandline
rm -rf pilot/meta_data/alembic/versions/*
rm -rf pilot/meta_data/alembic/dbgpt.db
```
