from __future__ import annotations

import io
import os
from typing import Any, Dict, List, Tuple

import requests
import streamlit as st

BASE_URL = "https://api.siliconflow.cn/v1"
UPLOAD_URL = f"{BASE_URL}/uploads/audio/voice"
VOICE_LIST_URL = f"{BASE_URL}/audio/voice/list"
SPEECH_URL = f"{BASE_URL}/audio/speech"
TRANSCRIBE_URL = f"{BASE_URL}/audio/transcriptions"

UPLOAD_MODELS = [
    
    "FunAudioLLM/CosyVoice2-0.5B",
    "fnlp/MOSS-TTSD-v0.5",
]

TTS_MODELS = [
    "FunAudioLLM/CosyVoice2-0.5B",
    "fnlp/MOSS-TTSD-v0.5",
]

TRANSCRIBE_MODELS = [
    "FunAudioLLM/SenseVoiceSmall",
    "TeleAI/TeleSpeechASR",
]

AUDIO_FORMATS = ["mp3", "wav", "opus", "pcm"]


def get_secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            value = st.secrets[name]
            return value.strip() if isinstance(value, str) else str(value).strip()
    except Exception:
        pass
    return os.getenv(name, default).strip()


def headers(api_key: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def upload_reference_audio(
    api_key: str,
    model: str,
    custom_name: str,
    text: str,
    file_name: str,
    file_bytes: bytes,
) -> Tuple[bool, str]:
    try:
        data = {"model": model, "customName": custom_name, "text": text}
        files = {"file": (file_name, io.BytesIO(file_bytes))}
        resp = requests.post(UPLOAD_URL, headers=headers(api_key), data=data, files=files, timeout=180)
        if resp.status_code >= 400:
            return False, f"{resp.status_code}: {resp.text}"
        payload = resp.json()
        uri = payload.get("uri", "")
        return (True, uri) if uri else (False, f"上传成功但未返回 uri：{payload}")
    except Exception as exc:
        return False, str(exc)


def transcribe_reference_audio(
    api_key: str,
    model: str,
    file_name: str,
    file_bytes: bytes,
) -> Tuple[bool, str]:
    """
    Use SiliconFlow transcription API to auto-recognize the reference audio text.
    Docs indicate multipart/form-data with file + model, and file size <= 50MB / duration <= 1 hour.
    """
    try:
        files = {"file": (file_name, io.BytesIO(file_bytes))}
        data = {"model": model}
        resp = requests.post(TRANSCRIBE_URL, headers=headers(api_key), files=files, data=data, timeout=300)
        if resp.status_code >= 400:
            return False, f"{resp.status_code}: {resp.text}"
        payload = resp.json()
        text = payload.get("text", "")
        return (True, text) if text else (False, f"转写成功但未返回 text：{payload}")
    except Exception as exc:
        return False, str(exc)


@st.cache_data(ttl=30)
def fetch_voice_list(api_key: str) -> Tuple[bool, Any]:
    try:
        resp = requests.get(VOICE_LIST_URL, headers=headers(api_key), timeout=60)
        if resp.status_code >= 400:
            return False, f"{resp.status_code}: {resp.text}"
        payload = resp.json()
        return True, payload.get("results", [])
    except Exception as exc:
        return False, str(exc)


def create_speech(
    api_key: str,
    model: str,
    input_text: str,
    voice: str,
    response_format: str,
    speed: float,
    gain: int,
) -> Tuple[bool, bytes | str]:
    try:
        payload = {
            "model": model,
            "input": input_text,
            "voice": voice,
            "response_format": response_format,
            "speed": speed,
            "gain": gain,
            "stream": False,
        }
        resp = requests.post(
            SPEECH_URL,
            headers={**headers(api_key), "Content-Type": "application/json"},
            json=payload,
            timeout=300,
        )
        if resp.status_code >= 400:
            return False, f"{resp.status_code}: {resp.text}"
        return True, resp.content
    except Exception as exc:
        return False, str(exc)


def mime_for(fmt: str) -> str:
    return {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "opus": "audio/ogg",
        "pcm": "application/octet-stream",
    }.get(fmt, "application/octet-stream")


st.set_page_config(page_title="SiliconFlow 声音克隆小应用", page_icon="🎙️", layout="wide")
st.title("SiliconFlow 声音克隆小应用")
st.caption("上传参考音频 → 自动识别文本或手动输入 → 获取音色 URI → 输入文本生成语音")

API_KEY = get_secret("SILICONFLOW_API_KEY")
APP_PASSWORD = get_secret("APP_PASSWORD")

with st.sidebar:
    st.header("访问设置")
    if APP_PASSWORD:
        typed_password = st.text_input("访问密码", type="password", placeholder="请输入共享密码")
        if typed_password != APP_PASSWORD:
            st.info("输入正确密码后才能继续使用。")
            st.stop()
    st.divider()
    st.write("API Key：", "已配置" if API_KEY else "未配置")
    st.write("上传接口：", "POST /v1/uploads/audio/voice")
    st.write("转写接口：", "POST /v1/audio/transcriptions")
    st.write("列表接口：", "GET /v1/audio/voice/list")
    st.write("生成接口：", "POST /v1/audio/speech")

if not API_KEY:
    st.error("未找到 SILICONFLOW_API_KEY。请在 Streamlit Cloud 的 Secrets 中配置。")
    st.stop()

if "voices" not in st.session_state:
    st.session_state.voices = []
if "last_uri" not in st.session_state:
    st.session_state.last_uri = ""
if "last_uploaded_model" not in st.session_state:
    st.session_state.last_uploaded_model = UPLOAD_MODELS[0]
if "reference_text" not in st.session_state:
    st.session_state.reference_text = ""

tab_upload, tab_list, tab_generate = st.tabs(["上传参考音频", "音色列表", "生成语音"])

with tab_upload:
    st.subheader("上传参考音频")
    st.write("参考音频尽量选择干净、单人声、无背景音乐的 5 到 20 秒片段。转写文件需满足官方限制：时长不超过 1 小时、大小不超过 50MB。")
    upload_model = st.selectbox("上传模型", UPLOAD_MODELS, index=0)
    transcribe_model = st.selectbox("自动识别模型", TRANSCRIBE_MODELS, index=0)
    custom_name = st.text_input("customName", placeholder="例如：zhangsan_voice")
    ref_file = st.file_uploader("参考音频文件", type=["mp3", "wav", "m4a", "flac", "ogg", "aac", "mp4"])

    auto_col, tip_col = st.columns([1, 2])
    with auto_col:
        auto_btn = st.button("自动识别参考音频文本")
    with tip_col:
        st.caption("点击后会把识别结果自动填入下面的文本框，你也可以继续手动修改。")

    if auto_btn:
        if ref_file is None:
            st.error("请先选择参考音频文件。")
        else:
            file_bytes = ref_file.getvalue()
            ok, result = transcribe_reference_audio(
                api_key=API_KEY,
                model=transcribe_model,
                file_name=ref_file.name,
                file_bytes=file_bytes,
            )
            if ok:
                st.session_state.reference_text = result
                st.success("识别成功，已自动填入文本框。")
            else:
                st.error(f"识别失败：{result}")

    reference_text = st.text_area(
        "参考音频对应文本",
        height=140,
        key="reference_text",
        placeholder="可先点击自动识别，再微调为与音频逐字一致的文本",
    )

    if st.button("上传并生成 URI", type="primary"):
        if not custom_name.strip():
            st.error("请填写 customName。")
        elif not reference_text.strip():
            st.error("请填写参考音频对应文本。")
        elif ref_file is None:
            st.error("请先选择参考音频文件。")
        else:
            ok, result = upload_reference_audio(
                api_key=API_KEY,
                model=upload_model,
                custom_name=custom_name.strip(),
                text=reference_text.strip(),
                file_name=ref_file.name,
                file_bytes=ref_file.getvalue(),
            )
            if ok:
                st.success("上传成功")
                st.code(result, language="text")
                st.session_state.last_uri = result
                st.session_state.last_uploaded_model = upload_model
                st.cache_data.clear()
            else:
                st.error(f"上传失败：{result}")

with tab_list:
    st.subheader("音色列表")
    col1, col2 = st.columns([1, 2])
    with col1:
        refresh = st.button("刷新列表", type="primary")
    with col2:
        st.caption("列表来自你的 SiliconFlow 账号下已上传的参考音频。")

    if refresh or not st.session_state.voices:
        ok, result = fetch_voice_list(API_KEY)
        if ok:
            st.session_state.voices = result
            st.success(f"已加载 {len(result)} 条音色记录")
        else:
            st.error(f"获取列表失败：{result}")

    voices = st.session_state.voices
    if not voices:
        st.info("当前没有音色记录，先去上传参考音频。")
    else:
        for idx, item in enumerate(voices, start=1):
            with st.expander(f"{idx}. {item.get('customName', 'Unnamed')} | {item.get('model', '')}"):
                st.write("customName：", item.get("customName", ""))
                st.write("model：", item.get("model", ""))
                st.write("text：", item.get("text", ""))
                st.code(item.get("uri", ""), language="text")
                if st.button("用这个音色生成", key=f"use_{idx}"):
                    st.session_state.last_uri = item.get("uri", "")
                    st.session_state.last_uploaded_model = item.get("model", UPLOAD_MODELS[0])
                    st.toast("已把该音色填入生成区")

with tab_generate:
    st.subheader("生成语音")
    st.write("选择一个音色 URI，再输入你想让它说的话。")

    voices = st.session_state.voices
    display_map: Dict[str, Dict[str, Any]] = {}
    options: List[str] = []

    for item in voices:
        label = f"{item.get('customName', 'Unnamed')} | {item.get('model', '')}"
        options.append(label)
        display_map[label] = item

    if options:
        selected_label = st.selectbox("选择已上传音色", options)
        selected_voice = display_map[selected_label]
        default_voice_uri = selected_voice.get("uri", "")
        default_tts_model = selected_voice.get("model", TTS_MODELS[0]) or TTS_MODELS[0]
    else:
        default_voice_uri = st.session_state.last_uri
        default_tts_model = st.session_state.last_uploaded_model or TTS_MODELS[0]

    manual_voice_uri = st.text_input(
        "voice URI",
        value=default_voice_uri,
        placeholder="speech:your-voice-name:xxx:xxx",
    )
    tts_model = st.selectbox(
        "TTS 模型",
        TTS_MODELS,
        index=TTS_MODELS.index(default_tts_model) if default_tts_model in TTS_MODELS else 0,
    )
    input_text = st.text_area("要合成的文本", height=160, placeholder="输入你想让声音说的话")

    c1, c2, c3 = st.columns(3)
    with c1:
        response_format = st.selectbox("输出格式", AUDIO_FORMATS, index=0)
    with c2:
        speed = st.slider("语速", 0.25, 4.0, 1.0, 0.05)
    with c3:
        gain = st.slider("音量增益", -10, 10, 0, 1)

    if st.button("生成语音", type="primary"):
        if not manual_voice_uri.strip():
            st.error("请先填写 voice URI。")
        elif not input_text.strip():
            st.error("请先输入要合成的文本。")
        else:
            ok, result = create_speech(
                api_key=API_KEY,
                model=tts_model,
                input_text=input_text.strip(),
                voice=manual_voice_uri.strip(),
                response_format=response_format,
                speed=float(speed),
                gain=int(gain),
            )
            if ok:
                audio_bytes = result
                st.success("生成成功")
                mime = mime_for(response_format)
                if response_format != "pcm":
                    st.audio(audio_bytes, format=mime)
                else:
                    st.warning("PCM 只提供下载，不适合直接预览。")
                st.download_button(
                    "下载音频",
                    data=audio_bytes,
                    file_name=f"siliconflow_voice.{response_format}",
                    mime=mime,
                )
            else:
                st.error(f"生成失败：{result}")

with st.expander("使用提示"):
    st.write("1. 先上传参考音频，必要时先点‘自动识别参考音频文本’。")
    st.write("2. 识别结果会自动填入文本框，你可以再检查一遍。")
    st.write("3. 文本尽量与音频逐字一致，这会明显影响上传后的克隆效果。")
    st.write("4. 如果识别失败，先检查音频文件是否过大，是否超过官方 50MB / 1 小时限制。")
