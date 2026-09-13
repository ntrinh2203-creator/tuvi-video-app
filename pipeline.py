"""
pipeline.py
Lõi xử lý: kịch bản (có SCENE) + ảnh -> video Shorts 9:16 có giọng đọc,
phụ đề karaoke (tô sáng từng chữ theo đúng nhịp giọng đọc), nhạc nền, hiệu ứng
Ken Burns (zoom nhẹ) cho từng ảnh.

Thiết kế để chạy độc lập (không cần GPU, không cần API key trả phí):
- Giọng đọc: edge-tts (miễn phí, cần Internet bình thường, không cần API key).
- Nếu không có Internet / edge-tts lỗi: tự động chuyển sang chế độ audio câm
  + ước lượng nhịp đọc, để pipeline vẫn chạy được (ảnh vẫn chuyển động đúng,
  chỉ thiếu giọng đọc thật) - hữu ích khi test offline.
"""
import asyncio
import glob
import os
import re
import shutil
import subprocess
import unicodedata

# ---------------------------------------------------------------------------
# Cấu hình chung
# ---------------------------------------------------------------------------
WIDTH, HEIGHT, FPS = 1080, 1920, 30
SCENE_PAD_SEC = 0.35          # khoảng lặng nhỏ cuối mỗi cảnh cho đỡ giật
MAX_ZOOM = 1.15                # zoom Ken Burns tối đa (1.15 = phóng to 15%)
MUSIC_VOLUME = 0.16            # âm lượng nhạc nền so với giọng đọc (0-1)

VOICES = {
    "nu_am_ap": "vi-VN-HoaiMyNeural",   # giọng nữ ấm áp
    "nam_tram": "vi-VN-NamMinhNeural",  # giọng nam trầm ấm
}


class PipelineError(Exception):
    pass


def _run(cmd, **kwargs):
    """Chạy 1 lệnh ffmpeg/ffprobe, raise kèm stderr nếu lỗi để dễ debug."""
    proc = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if proc.returncode != 0:
        raise PipelineError(
            "Lệnh lỗi: " + " ".join(cmd) + "\n--- stderr ---\n" + proc.stderr[-4000:]
        )
    return proc


def get_duration_sec(path: str) -> float:
    proc = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
    ])
    return float(proc.stdout.strip())


# ---------------------------------------------------------------------------
# 1) Tách kịch bản thành các cảnh (tương thích với các prompt SCENE 1, SCENE 2
#    đã dùng trong tài liệu kế hoạch kênh)
# ---------------------------------------------------------------------------
_SCENE_RE = re.compile(r"^(SCENE|Cảnh|CẢNH)\s*\d+\s*[:.\-]?\s*", re.IGNORECASE)


def parse_script(raw: str):
    lines = [l.strip() for l in raw.strip().splitlines()]
    has_markers = any(_SCENE_RE.match(l) for l in lines if l)
    scenes = []
    if has_markers:
        current = []
        for l in lines:
            if not l:
                continue
            m = _SCENE_RE.match(l)
            if m:
                if current:
                    scenes.append(" ".join(current).strip())
                current = [l[m.end():].strip()]
            else:
                current.append(l)
        if current:
            scenes.append(" ".join(current).strip())
    else:
        blocks = re.split(r"\n\s*\n", raw.strip())
        scenes = [b.replace("\n", " ").strip() for b in blocks if b.strip()]
    return [s for s in scenes if s]


def natural_sort_key(path):
    name = os.path.basename(path)
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


# ---------------------------------------------------------------------------
# 2) Giọng đọc (edge-tts) + timestamp từng từ để dựng phụ đề karaoke
# ---------------------------------------------------------------------------
async def _tts_async(text: str, voice: str, out_mp3: str):
    import edge_tts

    words = []
    communicate = edge_tts.Communicate(text, voice)
    with open(out_mp3, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({
                    "text": chunk["text"],
                    "offset_ms": chunk["offset"] / 10000.0,
                })
    return words


def synthesize_scene(text: str, voice: str, out_mp3: str):
    """Trả về list [{text, offset_ms}] (thời điểm bắt đầu mỗi từ, tính từ đầu
    cảnh, đơn vị mili-giây). Nếu TTS thất bại (không có mạng, v.v.) sẽ tạo
    audio câm + ước lượng nhịp đọc ~2.6 từ/giây để pipeline vẫn chạy được."""
    try:
        words = asyncio.run(_tts_async(text, voice, out_mp3))
        if not words or not os.path.exists(out_mp3) or os.path.getsize(out_mp3) < 500:
            raise PipelineError("edge-tts trả về audio rỗng")
        return words, True
    except Exception:
        tokens = text.split() or [text]
        wps = 2.6
        total_dur = max(len(tokens) / wps, 1.2)
        _run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", f"{total_dur:.3f}", "-c:a", "libmp3lame", "-b:a", "96k", out_mp3,
        ])
        per_word_ms = (total_dur * 1000) / len(tokens)
        words = [{"text": t, "offset_ms": i * per_word_ms} for i, t in enumerate(tokens)]
        return words, False


def pad_audio(in_path: str, out_path: str, pad_sec: float = SCENE_PAD_SEC):
    _run([
        "ffmpeg", "-y", "-i", in_path,
        "-af", f"apad=pad_dur={pad_sec}",
        "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k",
        out_path,
    ])


# ---------------------------------------------------------------------------
# 3) Hiệu ứng Ken Burns cho từng ảnh
# ---------------------------------------------------------------------------
def build_kenburns_clip(image_path: str, duration_sec: float, out_path: str, zoom_in: bool):
    frames = max(int(round(duration_sec * FPS)), 1)
    speed = (MAX_ZOOM - 1.0) / max(frames, 1)
    if zoom_in:
        zexpr = f"min(zoom+{speed:.6f}\\,{MAX_ZOOM})"
    else:
        zexpr = f"if(eq(on\\,1)\\,{MAX_ZOOM}\\,max(zoom-{speed:.6f}\\,1.0))"
    vf = (
        f"scale={WIDTH*2}:{HEIGHT*2}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH*2}:{HEIGHT*2},"
        f"zoompan=z='{zexpr}':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={WIDTH}x{HEIGHT}:fps={FPS},"
        f"format=yuv420p"
    )
    _run([
        "ffmpeg", "-y", "-loop", "1", "-i", image_path, "-t", f"{duration_sec:.3f}",
        "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        out_path,
    ])


def concat_videos(paths, out_path):
    list_file = out_path + ".txt"
    with open(list_file, "w") as f:
        for p in paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", out_path])


def concat_audios(paths, out_path):
    list_file = out_path + ".txt"
    with open(list_file, "w") as f:
        for p in paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", out_path])


# ---------------------------------------------------------------------------
# 4) Phụ đề karaoke (.ass) — mỗi chữ chuyển màu đúng lúc giọng đọc tới
# ---------------------------------------------------------------------------
def _format_ass_time(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _karaoke_tags(words, scene_duration_ms):
    tags = []
    n = len(words)
    for i, w in enumerate(words):
        start = w["offset_ms"]
        end = words[i + 1]["offset_ms"] if i + 1 < n else scene_duration_ms
        k_cs = max(int(round((end - start) / 10)), 1)
        text = w["text"].replace("{", "").replace("}", "").replace("\\", "")
        tags.append(f"{{\\k{k_cs}}}{text} ")
    return "".join(tags).strip()


ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Be Vietnam Pro,66,&H004AB8D8,&H00D9E8ED,&H00140F1F,&H00140F1F,-1,0,0,0,100,100,0,0,1,4,2,2,60,60,220,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def write_ass_file(path: str, dialogue_lines):
    with open(path, "w", encoding="utf-8") as f:
        f.write(ASS_HEADER)
        for line in dialogue_lines:
            f.write(line + "\n")


def _escape_filter_path(p: str) -> str:
    p = os.path.abspath(p).replace("\\", "/")
    p = p.replace(":", "\\:")
    return p


# ---------------------------------------------------------------------------
# 5) Ghép âm thanh (giọng đọc + nhạc nền) và gắn phụ đề vào video cuối
# ---------------------------------------------------------------------------
def mix_final(visual_path, voice_path, music_path, ass_path, out_path):
    cmd = ["ffmpeg", "-y", "-i", visual_path, "-i", voice_path]
    if music_path:
        cmd += ["-stream_loop", "-1", "-i", music_path]
        filter_complex = (
            f"[0:v]ass='{_escape_filter_path(ass_path)}'[vout];"
            f"[2:a]volume={MUSIC_VOLUME}[bg];"
            f"[1:a][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
    else:
        filter_complex = f"[0:v]ass='{_escape_filter_path(ass_path)}'[vout]"
    cmd += ["-filter_complex", filter_complex, "-map", "[vout]"]
    cmd += ["-map", "[aout]"] if music_path else ["-map", "1:a"]
    cmd += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", out_path,
    ]
    _run(cmd)


# ---------------------------------------------------------------------------
# 6) Thumbnail nhanh (Pillow) — chỉ là bản nháp, nên tinh chỉnh lại thủ công
# ---------------------------------------------------------------------------
def make_thumbnail(image_path: str, title: str, out_path: str):
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

    img = Image.open(image_path).convert("RGB")
    img = ImageOps.fit(img, (WIDTH, HEIGHT), method=Image.LANCZOS)
    img = img.filter(ImageFilter.GaussianBlur(0))

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([0, 0, WIDTH, int(HEIGHT * 0.5)], fill=(10, 8, 20, 150))

    font = None
    for candidate in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        if os.path.exists(candidate):
            font = ImageFont.truetype(candidate, 92)
            break
    if font is None:
        font = ImageFont.load_default()

    words = (title or "Lá Số Tử Vi").split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > WIDTH - 120 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)

    y = 90
    for line in lines[:4]:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (WIDTH - w) / 2
        for dx in (-4, 4):
            for dy in (-4, 4):
                draw.text((x + dx, y + dy), line, font=font, fill=(10, 8, 20, 255))
        draw.text((x, y), line, font=font, fill=(230, 190, 80, 255))
        y += 110

    out = Image.alpha_composite(img.convert("RGBA"), overlay)
    out.convert("RGB").save(out_path, quality=92)


# ---------------------------------------------------------------------------
# 6b) Sinh mô tả + hashtag mẫu (theo đúng công thức đã đối chiếu thực tế
#     với kênh tham khảo: hashtag lõi cố định + 1 hashtag riêng cho chủ đề
#     video + 1 hashtag thương hiệu kênh)
# ---------------------------------------------------------------------------
CORE_HASHTAGS = "#tamlinh #tuvi #huyenhoc #phongthuy"


def slugify_vn(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text).strip().lower()
    text = re.sub(r"\s+", "", text)
    return text or "tuvi"


def build_description(title: str, channel_tag: str = "") -> str:
    topic_tag = slugify_vn(title)
    tags = f"{CORE_HASHTAGS} #{topic_tag}"
    if channel_tag.strip():
        tags += f" #{slugify_vn(channel_tag)}"
    lines = [
        (title or "").strip(),
        "",
        "🔔 Theo dõi kênh để xem giải mã lá số mỗi tuần.",
        "💬 Để lại giờ–ngày–tháng–năm sinh nếu bạn muốn được luận lá số trong video sau.",
        "⚠️ Nội dung mang tính tham khảo theo Tử Vi Đẩu Số/dân gian truyền thống — không thay thế quyết định y tế, tài chính, pháp lý.",
        "",
        tags,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7) Điều phối toàn bộ pipeline
# ---------------------------------------------------------------------------
def render_job(job_dir, scenes_text, image_paths, voice_key, music_path, title, channel_tag="", progress_cb=lambda msg: None):
    os.makedirs(job_dir, exist_ok=True)
    voice = VOICES.get(voice_key, VOICES["nu_am_ap"])
    if not image_paths:
        raise PipelineError("Cần ít nhất 1 ảnh.")

    scene_clips, audio_pieces, dialogue_lines = [], [], []
    cumulative = 0.0
    used_real_tts = True

    for i, text in enumerate(scenes_text, start=1):
        progress_cb(f"[{i}/{len(scenes_text)}] Đang tạo giọng đọc...")
        raw_mp3 = os.path.join(job_dir, f"scene_{i:02d}_raw.mp3")
        words, is_real = synthesize_scene(text, voice, raw_mp3)
        used_real_tts = used_real_tts and is_real
        speech_dur = get_duration_sec(raw_mp3)

        padded_mp3 = os.path.join(job_dir, f"scene_{i:02d}.mp3")
        pad_audio(raw_mp3, padded_mp3)
        clip_dur = speech_dur + SCENE_PAD_SEC

        img = image_paths[(i - 1) % len(image_paths)]
        clip_path = os.path.join(job_dir, f"scene_{i:02d}.mp4")
        progress_cb(f"[{i}/{len(scenes_text)}] Đang dựng chuyển động Ken Burns...")
        build_kenburns_clip(img, clip_dur, clip_path, zoom_in=(i % 2 == 1))

        scene_clips.append(clip_path)
        audio_pieces.append(padded_mp3)

        karaoke = _karaoke_tags(words, speech_dur * 1000)
        start_ts = _format_ass_time(cumulative)
        end_ts = _format_ass_time(cumulative + speech_dur)
        dialogue_lines.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{karaoke}")
        cumulative += clip_dur

    progress_cb("Đang ghép các cảnh...")
    visual_path = os.path.join(job_dir, "visual.mp4")
    voice_path = os.path.join(job_dir, "voice.mp3")
    concat_videos(scene_clips, visual_path)
    concat_audios(audio_pieces, voice_path)

    ass_path = os.path.join(job_dir, "subs.ass")
    write_ass_file(ass_path, dialogue_lines)

    progress_cb("Đang hoà âm nhạc nền, gắn phụ đề và xuất video...")
    final_path = os.path.join(job_dir, "final.mp4")
    mix_final(visual_path, voice_path, music_path, ass_path, final_path)

    progress_cb("Đang tạo thumbnail nháp...")
    thumb_path = os.path.join(job_dir, "thumbnail.png")
    try:
        make_thumbnail(image_paths[0], title, thumb_path)
    except Exception:
        thumb_path = None

    if not used_real_tts:
        progress_cb(
            "⚠️ Không gọi được dịch vụ giọng đọc (kiểm tra Internet) — "
            "video đã xuất với audio câm/ước lượng nhịp, hãy chạy lại khi có mạng."
        )

    description = build_description(title, channel_tag)

    progress_cb("Hoàn tất!")
    return {
        "video": final_path,
        "thumbnail": thumb_path,
        "used_real_tts": used_real_tts,
        "description": description,
    }
