import os
import hmac
import pytz
import hashlib
import datetime
import platform
import subprocess

from flask import Flask, render_template, redirect, request
from werkzeug.middleware.proxy_fix import ProxyFix

from nsysmon.plugins import cpuinfo
from nsysmon.plugins import meminfo
from nsysmon.plugins import loadavg

from dotenv import load_dotenv

load_dotenv()

app = Flask("-- website --")

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

APP_SECRET_TOKEN = os.environ["APP_SECRET_TOKEN"]
COMMIT_HASH = subprocess.check_output(
    'git log -1 --pretty=format:"%h"', shell=True, text=True
)
COMMIT_MESSAGE = subprocess.check_output(
    f'git log -1 --pretty=format:%s {COMMIT_HASH}', shell=True, text=True
)
START_TIME_TIMESTAMP_UTC = int(datetime.datetime.timestamp(datetime.datetime.now(pytz.UTC)))
PLATFORM = f"{platform.uname()[1]} ({platform.uname()[2]})"

if os.getenv("WEBSITE_MODE"):
    print("[DEBUG] Templates will auto reload")

    app.config["TEMPLATES_AUTO_RELOAD"] = True

def verify_signature(secret_token, signature_header, payload_body):
    if not signature_header:
        return False

    expected = (
        "sha256="
        + hmac.new(secret_token.encode(), payload_body, hashlib.sha256).hexdigest()
    )

    return hmac.compare_digest(expected, signature_header)

def get_uptime(seconds):
    intervals = (("week", 604800), ("day", 86400), ("hour", 3600), ("minute", 60))
    result = []
    
    original_seconds = seconds

    if seconds < 60:
        result.append(f"{seconds} seconds")

    else:
        for time_type, count in intervals:
            value = seconds // count

            if value:
                seconds -= value * count
                result.append(f"{value} {time_type if value == 1 else time_type + 's'}")

    if len(result) > 1:
        result[-1] = "and " + result[-1]

    return ", ".join(result)

@app.route("/autod", methods=["POST"])
def autod():
    signature = request.headers.get("X-Hub-Signature-256")
    payload = request.get_data()

    if verify_signature(APP_SECRET_TOKEN, signature, payload):
        subprocess.Popen([os.path.abspath("auto-deploy.sh")])

        return "", 200

    else:
        return "", 403

@app.route("/s")
def status():
    TIME_NOW_TIMESTAMP = int(datetime.datetime.timestamp(datetime.datetime.now(pytz.UTC)))
    # TIME_NOW_TIMESTAMP = datetime.datetime.now(pytz.UTC).strftime("%A, %B %d %Y - %I:%M:%S %p %Z")

    start_time = datetime.datetime.fromtimestamp(START_TIME_TIMESTAMP_UTC).strftime("%A, %B %d %Y - %I:%M:%S %p")
    time_now = datetime.datetime.fromtimestamp(TIME_NOW_TIMESTAMP).strftime("%A, %B %d %Y - %I:%M:%S %p")
    
    uptime = get_uptime(TIME_NOW_TIMESTAMP - START_TIME_TIMESTAMP_UTC)

    nsysmon_plugins_data = [cpuinfo.Cpuinfo().get_data(), meminfo.Meminfo().get_data(), loadavg.Loadavg().get_data()]
    
    return render_template("status.html", data=[COMMIT_HASH, COMMIT_MESSAGE, PLATFORM, start_time, time_now, uptime, nsysmon_plugins_data])

@app.route("/")
def home():
    return render_template("index.html")
