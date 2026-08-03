#!/bin/bash
echo "=== Docker 容器内测速 ==="
docker run --rm ubuntu:22.04 bash -c '
apt-get update > /dev/null 2>&1
apt-get install -y curl > /dev/null 2>&1
echo "--- Test 清华源 ---"
time curl -s -o /dev/null -w "HTTP: %{http_code} | Speed: %{speed_download} B/s | Time: %{time_total}s\n" https://pypi.tuna.tsinghua.edu.cn/simple/matplotlib/
echo "--- Test 阿里云源 ---"
time curl -s -o /dev/null -w "HTTP: %{http_code} | Speed: %{speed_download} B/s | Time: %{time_total}s\n" https://mirrors.aliyun.com/pypi/simple/matplotlib/
echo "--- Test 下载实际 wheel ---"
time curl -L -o /tmp/test.whl "https://mirrors.aliyun.com/pypi/simple/matplotlib/" 2>&1 | tail -3
ls -lh /tmp/test.whl 2>/dev/null
'
