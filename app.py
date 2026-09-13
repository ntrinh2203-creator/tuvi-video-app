"""
app.py — Web app: thả kịch bản + ảnh vào, tự động dựng video Shorts
(giọng đọc, phụ đề karaoke, nhạc nền, hiệu ứng Ken Burns).

Chạy cục bộ:
    pip install -r requirements.txt
    python app.py
Rồi mở trình duyệt: http://127.0.0.1:8000

Chạy online (Render.com, xem README): đặt biến môi trường APP_USERNAME +
APP_PASSWORD để bật khoá đăng nhập (bắt buộc khi public link ra ngoài),
Render sẽ tự cấp biến PORT.
"""
import functools
import os
import shutil
import threading
import time
import uuid

from flask import Flask, Response, jsonify, render_template, request, send_file

import pipeline

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(BASE_DIR, "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

app = Flask(__name__)
# 150MB đủ cho vài chục ảnh + 1 file nhạc; giữ thấp để an toàn RAM trên hosting free tier.
app.config["MAX_CONTENT_LENGTH"] = 150 * 1024 * 1024

APP_USERNAME = os.environ.get("APP_USERNAME")
APP_PASSWORD = os.environ.get("APP_PASSWORD")


@app.before_request
def _require_login():
    """Chỉ bật khi có đặt APP_USERNAME/APP_PASSWORD (khuyên dùng khi deploy
    online, vì link public ai có cũng vào dùng được nếu không khoá)."""
    if not (APP_USERNAME and APP_PASSWORD):
        return None
    auth = request.authorization
    if not auth or auth.username != APP_USERNAME or auth.password != APP_PASSWORD:
        return Response(
            "Cần đăng nhập để dùng công cụ này.", 401,
            {"WWW-Authenticate": 'Basic realm="Xuong Dung Video"'},
        )
    return None

# Trạng thái job lưu tạm trong RAM (đủ dùng cho công cụ nội bộ chạy 1 máy)
JOBS = {}
JOBS_LOCK = threading.Lock()


def _set_status(job_id, **kwargs):
    with JOBS_LOCK:
        JOBS[job_id].update(kwargs)


def _append_log(job_id, message):
    with JOBS_LOCK:
        JOBS[job_id]["log"].append(message)


def _worker(job_id, job_dir, scenes_text, image_paths, voice_key, music_path, title, channel_tag):
    try:
        def progress(msg):
            _append_log(job_id, msg)

        result = pipeline.render_job(
            job_dir, scenes_text, image_paths, voice_key, music_path, title, channel_tag,
            progress_cb=progress,
        )
        _set_status(
            job_id,
            state="done",
            video_path=result["video"],
            thumb_path=result["thumbnail"],
            used_real_tts=result["used_real_tts"],
            description=result["description"],
        )
    except Exception as e:
        _append_log(job_id, f"❌ Lỗi: {e}")
        _set_status(job_id, state="error", error=str(e))


@app.route("/")
def index():
    return render_template("index.html", voices=pipeline.VOICES)


@app.route("/render", methods=["POST"])
def render_endpoint():
    script_text = request.form.get("script", "").strip()
    title = request.form.get("title", "").strip() or "Lá Số Tử Vi"
    voice_key = request.form.get("voice", "nu_am_ap")
    channel_tag = request.form.get("channel_tag", "").strip()

    scenes_text = pipeline.parse_script(script_text)
    if not scenes_text:
        return jsonify({"error": "Không đọc được cảnh nào từ kịch bản. Hãy để mỗi cảnh 1 đoạn, cách nhau 1 dòng trống, hoặc đánh dấu SCENE 1, SCENE 2..."}), 400

    images = request.files.getlist("images")
    images = [f for f in images if f and f.filename]
    if not images:
        return jsonify({"error": "Cần tải lên ít nhất 1 ảnh."}), 400

    job_id = uuid.uuid4().hex[:12]
    job_dir = os.path.join(JOBS_DIR, job_id)
    input_dir = os.path.join(job_dir, "input")
    os.makedirs(input_dir, exist_ok=True)

    saved_images = []
    for f in images:
        safe_name = f"{len(saved_images):03d}_{os.path.basename(f.filename)}"
        path = os.path.join(input_dir, safe_name)
        f.save(path)
        saved_images.append(path)
    saved_images.sort(key=pipeline.natural_sort_key)

    music_path = None
    music_file = request.files.get("music")
    if music_file and music_file.filename:
        music_path = os.path.join(input_dir, "music_" + os.path.basename(music_file.filename))
        music_file.save(music_path)

    with JOBS_LOCK:
        JOBS[job_id] = {
            "state": "running",
            "log": [f"Đã nhận {len(scenes_text)} cảnh, {len(saved_images)} ảnh."],
            "created": time.time(),
        }

    thread = threading.Thread(
        target=_worker,
        args=(job_id, job_dir, scenes_text, saved_images, voice_key, music_path, title, channel_tag),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id, "scenes": len(scenes_text), "images": len(saved_images)})


@app.route("/status/<job_id>")
def status_endpoint(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"error": "job not found"}), 404
        return jsonify({
            "state": job["state"],
            "log": job["log"],
            "used_real_tts": job.get("used_real_tts"),
            "description": job.get("description"),
        })


@app.route("/download/<job_id>/video")
def download_video(job_id):
    job = JOBS.get(job_id)
    if not job or job.get("state") != "done":
        return "Video chưa sẵn sàng", 404
    return send_file(job["video_path"], as_attachment=True, download_name=f"video_{job_id}.mp4")


@app.route("/download/<job_id>/thumbnail")
def download_thumbnail(job_id):
    job = JOBS.get(job_id)
    if not job or job.get("state") != "done" or not job.get("thumb_path"):
        return "Thumbnail chưa sẵn sàng", 404
    return send_file(job["thumb_path"], as_attachment=True, download_name=f"thumbnail_{job_id}.png")


@app.route("/preview/<job_id>")
def preview_video(job_id):
    job = JOBS.get(job_id)
    if not job or job.get("state") != "done":
        return "Video chưa sẵn sàng", 404
    return send_file(job["video_path"], mimetype="video/mp4")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # 0.0.0.0 để hosting (Render...) truy cập được; chạy máy cá nhân vẫn mở
    # bằng http://127.0.0.1:<port> bình thường.
    print(f"Mở trình duyệt tại: http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
