#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频处理模块 - 视频音频提取、语音识别、字幕生成和翻译
"""

import os
import sys
import tempfile
import subprocess
import whisper
import torch
from datetime import datetime, timedelta
from pydub import AudioSegment
from googletrans import Translator
import translators as ts
import re
import app_logger
from database import DatabaseManager

class AudioProcessor:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.db_manager.init_mongodb()
        self.translator = Translator()
        self.whisper_model = None
        self.temp_dir = tempfile.mkdtemp()
        
    def load_whisper_model(self, model_size='base'):
        """加载Whisper模型"""
        try:
            if self.whisper_model is None:
                app_logger.info(f"正在加载Whisper模型: {model_size}")
                self.whisper_model = whisper.load_model(model_size)
                app_logger.info("Whisper模型加载成功")
            return True
        except Exception as e:
            app_logger.error(f"加载Whisper模型失败: {e}")
            return False
    
    def extract_audio_from_video(self, video_path, audio_path=None):
        """从视频文件中提取音频"""
        try:
            if audio_path is None:
                audio_path = os.path.join(self.temp_dir, f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
            
            app_logger.info("开始提取音频...")
            
            # 使用ffmpeg提取音频
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vn',  # 不包含视频
                '-acodec', 'pcm_s16le',  # 音频编码
                '-ar', '16000',  # 采样率
                '-ac', '1',  # 单声道（Whisper推荐）
                '-y',  # 覆盖输出文件
                audio_path
            ]
            
            # 修复编码问题：使用errors='replace'处理无法解码的字符
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                encoding='utf-8',
                errors='replace'  # 替换无法解码的字符
            )
            
            if result.returncode == 0:
                app_logger.info(f"音频提取成功: {audio_path}")
                return audio_path
            else:
                # 清理stderr中的替换字符，避免日志混乱
                stderr_clean = result.stderr.replace('\ufffd', '[无法解码字符]')
                app_logger.error(f"音频提取失败: {stderr_clean}")
                return None
                
        except UnicodeDecodeError as e:
            app_logger.error(f"编码错误: {e}")
            # 备选方案：使用bytes模式
            try:
                result = subprocess.run(cmd, capture_output=True)
                if result.returncode == 0:
                    app_logger.info(f"音频提取成功（备选方案）: {audio_path}")
                    return audio_path
                else:
                    app_logger.error(f"音频提取失败（备选方案）: 返回码 {result.returncode}")
                    return None
            except Exception as e2:
                app_logger.error(f"备选方案也失败: {e2}")
                return None
        except Exception as e:
            app_logger.error(f"提取音频时出错: {e}")
            return None
    
    def transcribe_audio_to_text(self, audio_path, language='ja'):
        """将音频转换为文字"""
        try:
            if not self.load_whisper_model():
                return None
            
            app_logger.info(f"开始语音识别: {audio_path}")
            
            # 使用Whisper进行语音识别
            result = self.whisper_model.transcribe(
                audio_path,
                language=language,
                task='transcribe',
                verbose=True
            )
            
            # 提取文本和时间戳信息
            segments = result.get('segments', [])
            full_text = result.get('text', '')
            
            app_logger.info(f"语音识别完成，识别出 {len(segments)} 个片段")
            
            return {
                'text': full_text,
                'segments': segments
            }
            
        except Exception as e:
            app_logger.error(f"语音识别失败: {e}")
            return None
    
    def translate_text(self, text, src_lang='ja', dest_lang='zh'):
        """翻译文本"""
        try:
            # 首先尝试使用googletrans
            try:
                result = self.translator.translate(text, src=src_lang, dest=dest_lang)
                return result.text
            except Exception as e:
                app_logger.warning(f"googletrans翻译失败，尝试备用方案: {e}")
            
            # 备用翻译方案
            try:
                result = ts.translate_text(text, translator='google', from_language=src_lang, to_language=dest_lang)
                return result
            except Exception as e:
                app_logger.error(f"备用翻译也失败: {e}")
                return text  # 返回原文
                
        except Exception as e:
            app_logger.error(f"翻译失败: {e}")
            return text
    
    def format_time(self, seconds):
        """将秒数格式化为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def generate_srt_file(self, segments, output_path, translate_to_chinese=False):
        """生成SRT字幕文件"""
        try:
            srt_content = []
            
            for i, segment in enumerate(segments, 1):
                start_time = self.format_time(segment['start'])
                end_time = self.format_time(segment['end'])
                text = segment['text'].strip()
                
                if translate_to_chinese:
                    text = self.translate_text(text)
                
                srt_content.append(f"{i}")
                srt_content.append(f"{start_time} --> {end_time}")
                srt_content.append(text)
                srt_content.append("")  # 空行
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(srt_content))
            
            app_logger.info(f"SRT字幕文件生成成功: {output_path}")
            return True
            
        except Exception as e:
            app_logger.error(f"生成SRT文件失败: {e}")
            return False
    
    def process_video_to_subtitles(self, video_path, task_id=None):
        """完整的视频处理流程：提取音频 -> 语音识别 -> 生成字幕 -> 翻译"""
        try:
            if task_id:
                self.db_manager.update_audio_task_status(task_id, 'processing', progress=10)
            
            # 1. 提取音频
            app_logger.info("开始提取音频...")
            audio_path = self.extract_audio_from_video(video_path)
            if not audio_path:
                if task_id:
                    self.db_manager.update_audio_task_status(task_id, 'failed', error_message='音频提取失败')
                return None
            
            if task_id:
                self.db_manager.update_audio_task_status(task_id, 'processing', progress=30, audio_file_path=audio_path)
            
            # 2. 语音识别
            app_logger.info("开始语音识别...")
            transcription_result = self.transcribe_audio_to_text(audio_path)
            if not transcription_result:
                if task_id:
                    self.db_manager.update_audio_task_status(task_id, 'failed', error_message='语音识别失败')
                return None
            
            japanese_text = transcription_result['text']
            segments = transcription_result['segments']
            
            if task_id:
                self.db_manager.update_audio_task_status(task_id, 'processing', progress=60, japanese_text=japanese_text)
            
            # 3. 生成日文字幕文件
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            japanese_srt_path = os.path.join(self.temp_dir, f"{video_name}_japanese.srt")
            
            if not self.generate_srt_file(segments, japanese_srt_path, translate_to_chinese=False):
                if task_id:
                    self.db_manager.update_audio_task_status(task_id, 'failed', error_message='日文字幕生成失败')
                return None
            
            if task_id:
                self.db_manager.update_audio_task_status(task_id, 'processing', progress=80)
            
            # 4. 翻译并生成中文字幕文件
            app_logger.info("开始翻译为中文...")
            chinese_text = self.translate_text(japanese_text)
            chinese_srt_path = os.path.join(self.temp_dir, f"{video_name}_chinese.srt")
            
            if not self.generate_srt_file(segments, chinese_srt_path, translate_to_chinese=True):
                if task_id:
                    self.db_manager.update_audio_task_status(task_id, 'failed', error_message='中文字幕生成失败')
                return None
            
            # 5. 保存结果到数据库
            if task_id:
                self.db_manager.update_audio_task_status(
                    task_id, 'completed', progress=100,
                    chinese_text=chinese_text,
                    srt_file_path=japanese_srt_path
                )
                
                self.db_manager.save_subtitle_file(
                    task_id, japanese_srt_path, chinese_srt_path,
                    japanese_text, chinese_text
                )
            
            result = {
                'audio_path': audio_path,
                'japanese_text': japanese_text,
                'chinese_text': chinese_text,
                'japanese_srt_path': japanese_srt_path,
                'chinese_srt_path': chinese_srt_path,
                'segments': segments
            }
            
            app_logger.info("视频处理完成")
            return result
            
        except Exception as e:
            app_logger.error(f"视频处理失败: {e}")
            if task_id:
                self.db_manager.update_audio_task_status(task_id, 'failed', error_message=str(e))
            return None
    
    def cleanup_temp_files(self, file_paths):
        """清理临时文件"""
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    app_logger.info(f"临时文件已删除: {file_path}")
            except Exception as e:
                app_logger.warning(f"删除临时文件失败: {file_path}, {e}")
    
    def __del__(self):
        """清理资源"""
        try:
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
        except:
            pass