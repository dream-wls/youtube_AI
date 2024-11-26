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
KIMI_API_KEY = 'sk-pU7yKVxX8uzIRs1dtXIhyKEA74TIaZ6FlJHeFKyefuOAul7n'
os.environ['KIMI_API_KEY'] = KIMI_API_KEY

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

# 文件变化处理器
class FileChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory:
            print(f"检测到文件变化: {event.src_path}")

# 启动文件监控
def start_file_watcher():
    event_handler = FileChangeHandler()
    observer = Observer()
    # 监控static目录
    observer.schedule(event_handler, path="static", recursive=True)
    # 监控templates目录
    observer.schedule(event_handler, path="templates", recursive=True)
    observer.start()
    print("文件监控已启动")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

# 在新线程中启动文件监控
threading.Thread(target=start_file_watcher, daemon=True).start()

# 创建必要的目录
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "static", "downloads")
SCENES_DIR = os.path.join(os.path.dirname(__file__), "static", "scenes")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(SCENES_DIR, exist_ok=True)

async def call_kimi_api(messages):
    """调用Kimi API"""
    try:
        logger.info("开始调用Kimi API")
        logger.info(f"发送消息: {messages[0]['role']}, {messages[1]['role']}")
        
        # 构建API请求消息
        formatted_messages = []
        for msg in messages:
            if isinstance(msg["content"], str):
                formatted_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            else:
                content_list = []
                for content in msg["content"]:
                    if content["type"] == "text":
                        content_list.append({
                            "type": "text",
                            "text": content["text"]
                        })
                    elif content["type"] == "image_url":
                        content_list.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{content['image_url']['url'].split(',')[1]}"
                            }
                        })
                formatted_messages.append({
                    "role": msg["role"],
                    "content": content_list
                })
        
        # 打印请求消息以便调试
        logger.info(f"发送请求到Kimi API，消息内容: {formatted_messages}")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {KIMI_API_KEY}"
        }
        
        api_url = "https://api.moonshot.cn/v1/chat/completions"
        data = {
            "model": "moonshot-v1-8k",
            "messages": formatted_messages,
            "temperature": 0.7,
            "stream": False
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=data, headers=headers) as response:
                response_text = await response.text()
                logger.info(f"API响应: {response.status} - {response_text}")
                
                if response.status == 200:
                    result = await response.json()
                    logger.info("Kimi API调用成功")
                    return result["choices"][0]["message"]["content"]
                else:
                    logger.error(f"API调用失败: {response.status} - {response_text}")
                    # 添加延迟重试
                    await asyncio.sleep(2)
                    return None
                    
    except Exception as e:
        logger.error(f"调用Kimi API时发生错误: {str(e)}")
        return None

async def generate_image_prompt(image_path):
    try:
        logger.info(f"开始处理图片: {image_path}")
        
        # 读取图片并转换为base64
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
        # 打印base64图片链接的前100个字符（用于调试）
        logger.info(f"Base64图片数据前100个字符: {base64_image[:100]}")
        
        image_url = f"data:image/jpeg;base64,{base64_image}"
        logger.info(f"完整的图片URL长度: {len(image_url)}")
        
        logger.info(f"开始为图片生成prompt: {image_path}")
        
        # 添加延迟以避免频率限制
        await asyncio.sleep(1)
        
        # 发送中文请求
        chinese_messages = [
            {
                "role": "system",
                "content": "你是一个高级的图片prompt工程师，擅长为图片生成专业、详细的prompt描述。请对图片进行分析，生成详细的描述，包括主体、场景、风格、光线等要素。"
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请详细描述这张图片的内容，生成一个专业的prompt。"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }
        ]
        
        logger.info("发送中文请求到Kimi API")
        chinese_result = await call_kimi_api(chinese_messages)
        
        if chinese_result:
            logger.info("中文prompt生成成功，开始生成英文prompt")
            # 添加延迟以避免频率限制
            await asyncio.sleep(1)
            
            # 发送英文请求
            english_messages = [
                {
                    "role": "system",
                    "content": "You are an advanced image prompt engineer, skilled at generating professional and detailed prompt descriptions for images. Please analyze the image and generate a detailed description including subject, scene, style, lighting, and other elements."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please describe this image in detail and generate a professional prompt."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                }
            ]
            
            logger.info("发送英文请求到Kimi API")
            english_result = await call_kimi_api(english_messages)
            
            if english_result:
                logger.info("英文prompt生成成功")
                return {
                    "chinese": chinese_result.strip(),
                    "english": english_result.strip()
                }
            else:
                logger.error("英文prompt生成失败")
                return {
                    "chinese": chinese_result.strip(),
                    "english": "Generation failed"
                }
        else:
            logger.error("中文prompt生成失败")
            return {
                "chinese": "生成失败",
                "english": "Generation failed"
            }
    except Exception as e:
        logger.error(f"生成prompt时发生错误: {str(e)}")
        return {
            "chinese": "生成失败",
            "english": "Generation failed"
        }

def analyze_image(image_path):
    """分析图片内容"""
    try:
        # 这里可以接入图像分析API来获取更准确的描述
        # 目前返回基础描述
        return "一个视频场景截图"
    except Exception as e:
        logger.error(f"分析图片时发生错误: {str(e)}")
        return "视频场景"

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

async def download_video(url: str):
    try:
        logger.info(f"开始下载视频: {url}")
        
        # 验证URL
        if not url or not isinstance(url, str):
            raise ValueError("无效的URL")
            
        if "youtube.com" not in url and "youtu.be" not in url:
            raise ValueError("仅支持YouTube视频链接")

        # 生成唯一的文件名
        video_id = str(uuid.uuid4())
        video_filename = f'video_{video_id}.mp4'
        
        # 设置yt-dlp选项
        ydl_opts = {
            'format': 'best[ext=mp4]/best',  # 选择最佳的单一mp4格式
            'outtmpl': os.path.join(DOWNLOAD_DIR, video_filename),
            'quiet': False,  # 显示下载进度
            'no_warnings': False,  # 显示警告信息
            'extract_flat': False,
            'retries': 20,  # 增加重试次数
            'fragment_retries': 20,
            'socket_timeout': 60,  # 增加超时时间
            'http_chunk_size': 1048576,  # 减小chunk大小
            'merge_output_format': 'mp4',
        }

        max_retries = 5  # 增加最大重试次数
        retry_count = 0
        last_error = None

        while retry_count < max_retries:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info(f"尝试下载视频 (尝试 {retry_count + 1}/{max_retries})")
                    info = ydl.extract_info(url, download=True)
                    logger.info(f"视频信息获取成功: {info.get('title', 'Unknown Title')}")
                    
                    # 获取下载的视频文件路径
                    video_path = os.path.join(DOWNLOAD_DIR, video_filename)
                    if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                        logger.info(f"视频下载完成: {video_path}")
                        return video_path, video_filename
                    else:
                        raise FileNotFoundError("视频文件未找到或大小为0")
                        
            except Exception as e:
                last_error = str(e)
                logger.warning(f"下载失败 (尝试 {retry_count + 1}/{max_retries}): {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(2)  # 等待2秒后重试
                continue

        # 如果所有重试都失败
        error_msg = f"视频下载失败，已重试{max_retries}次: {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)
        
    except Exception as e:
        logger.error(f"下载视频时发生错误: {str(e)}")
        raise

async def extract_scenes(video_path: str):
    try:
        logger.info(f"开始提取场景: {video_path}")
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
            
        # 获取视频信息
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception("无法打开视频文件")
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0
        
        logger.info(f"视频信息: 总帧数={total_frames}, FPS={fps}, 时长={duration:.2f}秒")

        # 设置场景检测参数
        min_scene_len = 15  # 最小场景长度（帧数）
        threshold = 20.0  # 降低阈值，使检测更敏感
        
        detector = ContentDetector(
            threshold=threshold,
            min_scene_len=min_scene_len
        )
        
        scene_list = detect(video_path, detector)
        
        if not scene_list:
            logger.warning("未检测到场景，尝试提取关键帧...")
            # 如果没有检测到场景，至少提取几个关键帧
            scene_images = []
            intervals = 5  # 将视频分成5段
            for i in range(intervals):
                frame_num = int((total_frames / intervals) * i)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                if ret:
                    image_path = os.path.join(SCENES_DIR, f'scene_{i+1}.jpg')
                    cv2.imwrite(image_path, frame)
                    relative_path = f'/static/scenes/scene_{i+1}.jpg'
                    scene_images.append(relative_path)
                    logger.info(f"保存关键帧 {i+1}: {image_path}")
            
            if scene_images:
                return scene_images
            else:
                raise Exception("无法提取任何帧")

        logger.info(f"检测到 {len(scene_list)} 个场景")

        # 提取关键帧
        scene_images = []
        for i, scene in enumerate(scene_list):
            frame_num = scene[0].get_frames()
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            
            if ret:
                image_path = os.path.join(SCENES_DIR, f'scene_{i+1}.jpg')
                cv2.imwrite(image_path, frame)
                relative_path = f'/static/scenes/scene_{i+1}.jpg'
                scene_images.append(relative_path)
                logger.info(f"保存场景 {i+1}: {image_path}")
            else:
                logger.warning(f"无法读取场景 {i+1} 的帧")

        cap.release()
        return scene_images

    except Exception as e:
        logger.error(f"提取场景时发生错误: {str(e)}")
        raise

@app.post("/process_video")
async def process_video(url: str = Form(...)):
    try:
        logger.info(f"开始处理视频: {url}")
        
        # 下载视频
        video_path, video_filename = await download_video(url)
        if not video_path:
            raise Exception("视频下载失败")

        # 提取场景
        scene_images = await extract_scenes(video_path)
        if not scene_images:
            raise Exception("未能提取到场景")

        logger.info(f"成功处理视频，提取了 {len(scene_images)} 个场景")
        return {
            "status": "success", 
            "scene_images": scene_images,
            "video_filename": video_filename
        }

    except Exception as e:
        logger.error(f"处理视频时发生错误: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

# 文件清理函数
def cleanup_old_files():
    """清理24小时前的文件"""
    current_time = time.time()
    for filename in os.listdir(DOWNLOAD_DIR):
        file_path = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.getmtime(file_path) < (current_time - 86400):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"清理文件失败: {str(e)}")

# 定期清理文件
@app.on_event("startup")
async def startup_event():
    cleanup_old_files()

if __name__ == "__main__":
    import uvicorn
    logger.info("服务器正在启动...")
    logger.info("请访问 http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", reload=True)