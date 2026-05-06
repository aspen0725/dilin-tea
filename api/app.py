#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
帝临·礼赠定制表单后端 API
接收 /api/gift-form 的 POST 请求，发送邮件通知，并保存 JSON 备份
"""

import os
import json
import smtplib
import datetime
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ── 配置 ────────────────────────────────────────────────────────────────────
SMTP_HOST = "smtp.163.com"
SMTP_PORT = 465
SMTP_USER = "aspenyoung@163.com"
SMTP_PASS = ""   # 从 credentials.json 读取
MAIL_TO   = ["aspenyoung@163.com"]

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
CRED_FILE     = os.path.join(BASE_DIR, "..", "credentials.json")

ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Flask 初始化 ────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024   # 16 MB

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("gift-api")

# ── 工具函数 ────────────────────────────────────────────────────────────────────
def send_mail(subject: str, html_body: str, attachments: list = None):
    """发送邮件通知（SSL/465）"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = ", ".join(MAIL_TO)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if attachments:
        for filepath, filename in attachments:
            with open(filepath, "rb") as f:
                part = MIMEApplication(f.read())
            part.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(part)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
    log.info("邮件已发送 -> %s", MAIL_TO)


def build_html(data: dict, files: list) -> str:
    """把表单数据渲染成 HTML 邮件正文"""
    t   = data.get("_type", "unknown")
    tag = "个人礼赠" if t == "personal" else "企业礼赠"

    rows = ""
    for k, v in data.items():
        if k.startswith("_") or not v:
            continue
        label = {
            "name": "称呼",     "gender": "称谓",       "phone": "联系方式",
            "occasion": "赠送场合", "tea_age": "对方茶龄",
            "budget": "预算范围", "quantity": "定制份数", "flavor": "香型偏好",
            "box_style": "礼盒风格", "greeting_flag": "专属寄语",
            "greeting_content": "寄语内容", "delivery_date": "期望收货日期",
            "remarks": "特殊备注",
            "company": "企业名称", "industry": "所属行业",
            "contact": "联系人", "title": "职务",
            "purpose": "礼品用途", "budget_per": "人均预算",
            "logo_type": "LOGO印制", "deadline": "期望交付日期",
            "notes": "特殊备注",
        }.get(k, k)
        rows += (
            f"<tr><td style='padding:6px 12px;background:#f5f0e8;font-weight:600;'>{label}</td>"
            f"<td style='padding:6px 12px;'>{v}</td></tr>"
        )

    file_info = ""
    if files:
        file_info = "<p><strong>上传文件：</strong>" + "、".join(f[1] for f in files) + "</p>"

    return f"""
    <div style="font-family:-apple-system,'PingFang SC',sans-serif;
                max-width:600px;margin:0 auto;background:#fff;
                border:1px solid #d4c8b8;border-radius:12px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#4a3c2e,#6b5b4a);
                  color:#f5f0e8;padding:24px 20px;text-align:center;">
        <h2 style="margin:0;font-size:18px;letter-spacing:2px;">新的礼赠定制需求</h2>
        <p style="margin:8px 0 0;opacity:0.75;font-size:13px;">{tag} · {data.get('_submitted_at','')}</p>
      </div>
      <table style="width:100%;border-collapse:collapse;font-size:14px;color:#3a3226;">
        {rows}
      </table>
      {file_info}
      <div style="padding:16px 20px;font-size:12px;color:#a09080;text-align:center;">
        本邮件由帝临礼赠定制系统自动发送
      </div>
    </div>
    """


def save_json(data: dict, files: list):
    """将提交数据保存为 JSON 备份"""
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    typ  = data.get("_type", "unknown")
    path = os.path.join(UPLOAD_FOLDER, f"{typ}_{ts}.json")
    payload = {
        "data": data,
        "files": [f[1] for f in files],
        "received_at": datetime.datetime.now().isoformat()
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log.info("JSON 备份已保存：%s", path)


# ── 路由 ────────────────────────────────────────────────────────────────────────
@app.route("/api/submit", methods=["POST"])
@app.route("/api/gift-form", methods=["POST"])
def gift_form():
    try:
        data = request.form.to_dict()
        files = []

        # 保存上传的文件
        for key in request.files:
            for f in request.files.getlist(key):
                if f and f.filename:
                    ext = os.path.splitext(f.filename)[1].lower()
                    if ext not in ALLOWED_EXT:
                        continue
                    safe_name = secure_filename(
                        f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{f.filename}"
                    )
                    save_path = os.path.join(UPLOAD_FOLDER, safe_name)
                    f.save(save_path)
                    files.append((save_path, f.filename))

        # 保存 JSON 备份
        save_json(data, files)

        # 发邮件
        tag    = "个人" if data.get("_type") == "personal" else "企业"
        subject = f"【帝临礼赠】新的{tag}定制需求"
        html    = build_html(data, files)
        send_mail(subject, html, attachments=files if files else None)

        return jsonify({"ok": True}), 200

    except Exception as e:
        log.exception("处理表单时出错：%s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


# 静态文件（开发环境；生产由 Nginx 负责）
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "../gift-dual.html")


# ── 启动 ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 读取 credentials.json
    if os.path.exists(CRED_FILE):
        with open(CRED_FILE, encoding="utf-8") as f:
            cred = json.load(f)
        SMTP_PASS = cred.get("email_auth_code", SMTP_PASS)
        log.info("已读取 credentials.json")
    else:
        log.warning("未找到 credentials.json，邮件发送可能无法工作")

    log.info("启动帝临礼赠 API，监听 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000)
