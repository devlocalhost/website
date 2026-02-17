import os
import re
import hmac
import glob
import hashlib
import datetime
import platform
import subprocess
import urllib.parse

import requests
import pytz
import mistune
import pylistenbrainz

from dotenv import load_dotenv
from flask import Flask, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

# import status

from nsysmon.plugins import cpuinfo
from nsysmon.plugins import meminfo
from nsysmon.plugins import loadavg

load_dotenv()

app = Flask("-- website --")

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

APP_SECRET_TOKEN = os.environ["APP_SECRET_TOKEN"]
COMMIT_HASH = subprocess.check_output(
    'git log -1 --pretty=format:"%h"', shell=True, text=True
)
COMMIT_MESSAGE = subprocess.check_output(
    f"git log -1 --pretty=format:%s {COMMIT_HASH}", shell=True, text=True
)
START_TIME_TIMESTAMP_UTC = int(
    datetime.datetime.timestamp(datetime.datetime.now(pytz.UTC))
)
PLATFORM = f"{platform.uname()[1]} ({platform.uname()[2]})"

NEWLINE_CHAR = "\n"

PYLISTENBRAINZ_CLIENT = pylistenbrainz.ListenBrainz()

LASTFM_API_BASE_URL = "https://ws.audioscrobbler.com/2.0"
LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY")
WEBSITE_MODE = os.getenv("WEBSITE_MODE")


class CustomRenderer(mistune.HTMLRenderer):
    def heading(self, text, level):
        header_id = re.sub(r"\s+", "-", text.lower())
        return f'<h{level}>{text}</h{level}><div id="{header_id}"></div>'


if WEBSITE_MODE == "debug":
    print("[WEBSITE] DEBUG = True")
    app.config["DEBUG"] = True

    print("[WEBSITE] TEMPLATES_AUTO_RELOAD = True")
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


def get_uptime_since(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime(
        "%A, %B %d %Y, %I:%M:%S %p"
    )


def lastfm_listen(username):
    resp = requests.get(
        f"{LASTFM_API_BASE_URL}/?api_key={LASTFM_API_KEY}&method=User.getrecenttracks&user={username}&format=json&limit=1",
        timeout=15,
    )
    data = resp.json()

    nowplaying = False

    if data["recenttracks"]["track"][0].get("@attr"):
        nowplaying = True

    artist = data["recenttracks"]["track"][0]["artist"]["#text"]
    title = data["recenttracks"]["track"][0]["name"]

    return (title, artist, nowplaying, "lastfm")


def listenbrainz_listen(username):
    temp_data = PYLISTENBRAINZ_CLIENT.get_playing_now(username=username)

    if temp_data:
        data = temp_data
        nowplaying = True

    else:
        data = PYLISTENBRAINZ_CLIENT.get_listens(username=username)[0]
        nowplaying = False

    artist = data.artist_name
    title = data.track_name

    return (title, artist, nowplaying, "listenbrainz")


def custom_header_plugin(md):
    md.renderer = CustomRenderer()


markdown_parser = mistune.create_markdown(
    plugins=[custom_header_plugin, "strikethrough"]
)

app.jinja_env.globals.update(get_uptime=get_uptime, get_uptime_since=get_uptime_since)


@app.route("/autod", methods=["POST"])
def autod():
    signature = request.headers.get("X-Hub-Signature-256")
    payload = request.get_data()

    if verify_signature(APP_SECRET_TOKEN, signature, payload):
        subprocess.Popen([os.path.abspath("re-deploy.sh")])

        return "", 200

    return "", 403


@app.route("/s")
@app.route("/status")
def status():
    if request.args.get("all") == "true":
        # TODO: find a way to handle the case when a website time outs or something
        # TODO: maybe move this to a different route, like /manage?

        websites = ["laurel-updates", "pylyrical", "shl", "teleoasth", "trackard"]
        website_names = ["laurel_updates", "pylyrical_api", "shl", "teleoasth", "trackard"]
        data = []

        for index, name in enumerate(websites):
            data.append([website_names[index], requests.get(f"https://{name}.dev64.xyz/sj", timeout=5).json()])


        return render_template("status_websites.html", data=data)

    time_now_timestamp = int(
        datetime.datetime.timestamp(datetime.datetime.now(pytz.UTC))
    )
    # TIME_NOW_TIMESTAMP = datetime.datetime.now(pytz.UTC).strftime("%A, %B %d %Y - %I:%M:%S %p %Z")

    start_time = datetime.datetime.fromtimestamp(START_TIME_TIMESTAMP_UTC).strftime(
        "%A, %B %d %Y - %I:%M:%S %p"
    )
    time_now = datetime.datetime.fromtimestamp(time_now_timestamp).strftime(
        "%A, %B %d %Y - %I:%M:%S %p"
    )

    uptime = get_uptime(time_now_timestamp - START_TIME_TIMESTAMP_UTC)

    nsysmon_plugins_data = [
        cpuinfo.Cpuinfo().get_data(),
        meminfo.Meminfo().get_data(),
        loadavg.Loadavg().get_data(),
    ]

    return render_template(
        "status.html",
        data=[
            COMMIT_HASH,
            COMMIT_MESSAGE,
            PLATFORM,
            start_time,
            time_now,
            uptime,
            nsysmon_plugins_data,
            WEBSITE_MODE,
        ],
    )


@app.route("/whatismyip")
@app.route("/ip")
def whatismyip():
    remote_addr = request.headers.get("CF-Connecting-IP")

    if not remote_addr:
        remote_addr = request.headers.get("X-Forwarded-For", request.remote_addr)

    return str(remote_addr) + "\n"


# @app.route("/sj")
# def status_json():
#     return status.get_status("website")


@app.route("/")
def home():
    # the filename of the recent created/modified blog post
    blog_filename = max(glob.glob("blogs/*"), key=os.path.getctime)
    blog_title = open(blog_filename).readline().replace("# ", "").replace(NEWLINE_CHAR, "")
    timestamp = datetime.datetime.fromtimestamp(os.stat(blog_filename).st_mtime).strftime(
        "%b %d"
    )

    return render_template("index.html", blog_filename=blog_filename.split("/")[-1].replace(".md", ""), blog_title=blog_title, timestamp=timestamp)


@app.route("/testpage")
@app.route("/t")
def testpage():
    return render_template("testpage.html")


@app.route("/widlt")
@app.route("/whatisdevlisteningto")
def widlt():
    username = "dev64"

    listen_data = None
    service = None

    lastfm_data = lastfm_listen(username)
    listenbrainz_data = listenbrainz_listen(username)

    if lastfm_data[2]:
        service = "Last.fm"
        listen_data = lastfm_data

    else:
        service = "ListenBrainz"
        listen_data = listenbrainz_data

    return render_template("widlt.html", listen_data=listen_data, service=service)


@app.route("/blog")
def blog():
    blogs = {}

    for file in os.listdir("blogs"):
        if file.endswith(".md"):
            with open(f"blogs/{file}", encoding="utf-8") as blog_file:
                blogs[
                    blog_file.readline().replace("# ", "").replace(NEWLINE_CHAR, "")
                ] = file.removesuffix(".md")

    return render_template("blogs.html", blogs=blogs)


@app.route("/blog/<blog_name>")
def blog_post(blog_name):
    blog_file = os.path.join("blogs", blog_name + ".md")

    if not os.path.exists(blog_file):
        return render_template("404.html")

    with open(blog_file, encoding="utf-8") as file:
        blog_title = file.readline().removeprefix("# ").removesuffix(NEWLINE_CHAR)
        blog_data = markdown_parser(file.read())

    date_created = (
        subprocess.check_output(
            f"TZ=UTC git log --follow --format=%ad --date=format-local:'%b %d %Y - %I:%M %p %Z' {blog_file} | tail -1",
            shell=True,
            text=True,
        )
        or "Unknown"
    )
    date_last_modified = (
        subprocess.check_output(
            f"TZ=UTC git log -1 --date=format-local:'%b %d %Y - %I:%M %p %Z' --format=%ad {blog_file}",
            shell=True,
            text=True,
        )
        or "Unknown"
    )

    return render_template(
        "blog_template.html",
        blog_title=blog_title,
        blog_data=blog_data,
        blog_file=blog_file,
        date_created=date_created,
        date_last_modified=date_last_modified,
    )


@app.route("/lyrics")
def lyrics():
    search_query = request.args.get("search_query")

    if search_query:
        # bad
        data = requests.get(
            f"https://pylyrical.dev64.xyz/lyrics?q={urllib.parse.quote_plus(search_query)}"
        )

        try:
            data = data.json()

        except:
            data = data.text

        # bad

        return render_template("lyrics_result.html", data=data)

    return render_template("lyrics.html")


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html")
