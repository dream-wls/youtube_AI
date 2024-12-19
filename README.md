# YouTube视频下载器

这是一个基于FastAPI和yt-dlp的YouTube视频下载器，支持普通视频和Shorts视频的下载。

## 功能特点

- 支持YouTube普通视频下载
- 支持YouTube Shorts视频下载（优化支持）
  - 自动适应Shorts视频格式
  - 优化下载参数配置
  - 限制视频最大高度以提高兼容性
- 自动转换为MP4格式
- 支持视频场景分割
- 提供Web界面操作
- 支持异步下载处理
- 详细的下载日志输出

## 环境要求

- Python 3.8+
- FFmpeg（用于视频处理）
- 稳定的网络连接（特别是下载Shorts视频时）

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行方法

1. 确保已安装所有依赖
2. 在项目根目录运行：
   ```bash
   uvicorn main:app --reload --port 8080
   ```
3. 打开浏览器访问：http://localhost:8080

## 使用说明

1. 准备工作
   - 确保已安装所有依赖
   - 确保网络连接正常

2. 在网页界面输入YouTube视频链接
   - 支持普通视频链接 (例如: https://www.youtube.com/watch?v=...)
   - 支持Shorts视频链接 (例如: https://www.youtube.com/shorts/...)
   - 注意：链接必须是有效的YouTube链接

3. 点击下载按钮开始下载
   - 对于普通视频：将下载最佳质量的MP4格式
   - 对于Shorts视频：将自动优化下载参数
   - 注意：某些视频可能需要登录才能观看，这种情况下可能无法下载

4. 等待下载完成，视频将自动保存到 static/downloads 目录

## 注意事项

- 确保有足够的磁盘空间
- 需要稳定的网络连接
- 下载的视频仅供个人学习使用
- 部分视频可能需要登录才能观看（目前不支持）
- Shorts视频可能需要更长的处理时间

## 目录结构

```
.
├── main.py            # 主程序文件
├── requirements.txt   # 依赖文件
├── static/           # 静态文件目录
│   ├── downloads/    # 下载的视频存放目录
│   ├── scenes/       # 视频场景分割后的图片
│   └── styles.css    # 样式文件
└── templates/        # 模板文件目录
    └── index.html    # 主页面模板
```

## 最新更新

- 优化了视频下载逻辑
- 改进了错误提示信息
- 优化了Shorts视频的下载支持
- 简化了视频格式选择逻辑

## 常见问题

1. 如果下载失败，请检查：
   - 视频链接是否有效
   - 网络连接是否正常
   - 视频是否需要登录（目前不支持需要登录的视频）
   - 视频是否有地区限制

## 技术栈

- FastAPI: Web框架
- yt-dlp: 视频下载工具
- FFmpeg: 视频处理
- OpenCV: 视频场景检测
- Jinja2: 模板引擎
