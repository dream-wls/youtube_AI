from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import os
import uuid
import time
import cv2
from scenedetect import detect, ContentDetector
import logging
from openai import OpenAI
import base64
import aiohttp
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading

# 配置Kimi API
KIMI_API_KEY = os.getenv('KIMI_API_KEY', 'sk-pU7yKVxX8uzIRs1dtXIhyKEA74TIaZ6FlJHeFKyefuOAul7n')

# 初始化OpenAI客户端
client = OpenAI(
    api_key=KIMI_API_KEY,
    base_url="https://api.moonshot.cn/v1"
)

# 配置日志记录
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件和模板配置
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 创建必要的目录
DOWNLOAD_DIR = os.path.join("static", "downloads")
SCENES_DIR = os.path.join("static", "scenes")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(SCENES_DIR, exist_ok=True)

# 文件变化处理器
class FileChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory:
            logger.info(f"检测到文件变化: {event.src_path}")

# 启动文件监控
def start_file_watcher():
    event_handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path="static", recursive=True)
    observer.schedule(event_handler, path="templates", recursive=True)
    observer.start()
    logger.info("文件监控已启动")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

# 在新线程中启动文件监控
watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
watcher_thread.start()

async def download_video(url: str):
    try:
        logger.info(f"开始下载视频: {url}")
        
        # 验证URL
        if not url or not isinstance(url, str):
            raise ValueError("无效的URL")
            
        # 生成唯一的文件名
        video_id = str(uuid.uuid4())
        video_filename = f'video_{video_id}.mp4'
        
        # 设置下载选项
        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(DOWNLOAD_DIR, video_filename),
            'quiet': False,
            'verbose': True,
            'no_warnings': False,
            'extract_flat': False,
            'retries': 10,
            'fragment_retries': 10,
            'socket_timeout': 120,
            'http_chunk_size': 10485760,
            'merge_output_format': 'mp4',
            'ignoreerrors': False,
            'prefer_ffmpeg': True,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'nocheckcertificate': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'player_skip': ['webpage', 'config'],
                }
            }
        }

        # 如果是YouTube Shorts，添加特殊处理
        if "/shorts/" in url:
            ydl_opts.update({
                'format': 'best[height<=1280]',
                'merge_output_format': 'mp4',
                'concurrent_fragment_downloads': 1,
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("开始下载视频")
            info = ydl.extract_info(url, download=True)
            
            if info is None:
                raise ValueError("无法获取视频信息")
                
            logger.info(f"视频信息获取成功: {info.get('title', '未知标题')}")
            
            # 获取下载的视频文件路径
            video_path = os.path.join(DOWNLOAD_DIR, video_filename)
            if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                logger.info(f"视频下载完成: {video_path}")
                return video_path, video_filename
            else:
                raise FileNotFoundError("视频文件未找到或大小为0")
                
    except Exception as e:
        logger.error(f"下载视频时发生错误: {str(e)}")
        if "Please sign in" in str(e):
            raise Exception("此视频需要登录才能观看。请尝试下载其他视频。")
        raise

async def extract_scenes(video_path: str):
    try:
        logger.info(f"开始提取视频场景: {video_path}")
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
            
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("无法打开视频文件")
            
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        
        logger.info(f"视频信息 - FPS: {fps}, 总帧数: {frame_count}, 时长: {duration}秒")
        
        scene_list = detect(video_path, ContentDetector())
        logger.info(f"检测到 {len(scene_list)} 个场景")
        
        scene_images = []
        for i, scene in enumerate(scene_list):
            middle_frame = (scene[0].get_frames() + scene[1].get_frames()) // 2
            cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
            ret, frame = cap.read()
            
            if ret:
                image_filename = f'scene_{i}_{middle_frame}.jpg'
                image_path = os.path.join(SCENES_DIR, image_filename)
                cv2.imwrite(image_path, frame)
                scene_images.append(image_path)
                logger.info(f"保存场景图片: {image_path}")
        
        cap.release()
        return scene_images
        
    except Exception as e:
        logger.error(f"提取场景时发生错误: {str(e)}")
        raise

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/process_video")
async def process_video(url: str = Form(...)):
    try:
        # 下载视频
        video_path, video_filename = await download_video(url)
        
        # 提取场景
        scene_images = await extract_scenes(video_path)
        
        return JSONResponse({
            "status": "success",
            "message": "视频处理完成",
            "video_path": f"/static/downloads/{video_filename}",
            "scene_images": [f"/static/scenes/{os.path.basename(img)}" for img in scene_images]
        })
        
    except Exception as e:
        logger.error(f"处理视频时发生错误: {str(e)}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

def cleanup_old_files():
    """清理24小时前的文件"""
    try:
        current_time = time.time()
        for dir_path in [DOWNLOAD_DIR, SCENES_DIR]:
            for filename in os.listdir(dir_path):
                file_path = os.path.join(dir_path, filename)
                if os.path.isfile(file_path):
                    if current_time - os.path.getmtime(file_path) > 24 * 3600:
                        os.remove(file_path)
                        logger.info(f"已删除旧文件: {file_path}")
    except Exception as e:
        logger.error(f"清理文件时发生错误: {str(e)}")

@app.on_event("startup")
async def startup_event():
    cleanup_old_files()

if __name__ == "__main__":
    import uvicorn
    logger.info("服务器正在启动...")
    uvicorn.run("main:app", host="0.0.0.0", port=8088, reload=True)