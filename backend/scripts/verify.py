"""
Milestone 1 验证 CLI。

用法：
    # 在终端二维码扫码登录网易云，搜索一首歌并下载第一条结果
    python -m scripts.verify netease "周杰伦 晴天"

    # 同上，QQ 音乐
    python -m scripts.verify qq "周杰伦 晴天"

    # 跳过登录直接搜索（会用游客身份，部分高音质拿不到）
    python -m scripts.verify netease "周杰伦 晴天" --no-login

输出：
    1. 二维码（在终端用 ASCII 字符渲染）
    2. 搜索结果列表
    3. 下载第一条到 ./verify_output/<平台>/<歌名>.<ext>
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

import httpx
import qrcode

# 让脚本可以直接 `python -m scripts.verify`
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.platforms.base import LoginStatus, PlatformID, QualityLevel  # noqa: E402
from app.platforms.netease import NeteaseClient  # noqa: E402
from app.platforms.qq import QQClient  # noqa: E402


def _print_terminal_qr(text: str) -> None:
    """在终端用 ASCII 渲染二维码。"""
    qr = qrcode.QRCode(border=1)
    qr.add_data(text)
    qr.make()
    qr.print_ascii(invert=True)


def _print_qr_image_save(png: bytes, save_path: Path) -> None:
    save_path.write_bytes(png)
    print(f"[二维码图片已保存到] {save_path.resolve()}")


def _safe_filename(name: str) -> str:
    """替换非法文件名字符。"""
    return re.sub(r'[\\/:\*\?"<>|]', " ", name).strip()


async def _qr_login_netease(cli: NeteaseClient) -> bool:
    print("\n[网易云] 创建扫码登录...")
    qr = await cli.create_qr_login()
    print(f"二维码 URL: {qr.qr_url}")
    print("终端二维码（用网易云 APP 扫描）：")
    _print_terminal_qr(qr.qr_url)

    print("等待扫码...")
    while True:
        await asyncio.sleep(2)
        result = await cli.poll_qr_login(qr)
        if result.status is LoginStatus.PENDING:
            sys.stdout.write(".")
            sys.stdout.flush()
        elif result.status is LoginStatus.SCANNED:
            print("\n已扫码，等待手机端确认...")
        elif result.status is LoginStatus.SUCCESS:
            print(f"\n登录成功！nickname={result.nickname}, userId={result.user_id}, vip={result.vip_type}")
            return True
        elif result.status is LoginStatus.EXPIRED:
            print("\n二维码已过期，请重试")
            return False


async def _qr_login_qq(cli: QQClient) -> bool:
    print("\n[QQ 音乐] 创建扫码登录...")
    qr = await cli.create_qr_login()
    save_path = Path("verify_output") / "qq_qrcode.png"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    if qr.qr_image_png:
        _print_qr_image_save(qr.qr_image_png, save_path)
        print("请用 QQ 扫描该图片中的二维码（可双击图片查看大图）。")

    print("等待扫码...")
    while True:
        await asyncio.sleep(2)
        result = await cli.poll_qr_login(qr)
        if result.status is LoginStatus.PENDING:
            sys.stdout.write(".")
            sys.stdout.flush()
        elif result.status is LoginStatus.SCANNED:
            print("\n已扫码，等待 QQ 端确认...")
        elif result.status is LoginStatus.SUCCESS:
            print(f"\n登录成功！uin={result.user_id}")
            return True
        elif result.status is LoginStatus.EXPIRED:
            print("\n二维码已过期，请重试")
            return False


async def _download_audio(url: str, save_path: Path) -> int:
    """流式下载到本地，返回字节数。"""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as cli:
        async with cli.stream("GET", url) as r:
            r.raise_for_status()
            with save_path.open("wb") as fp:
                async for chunk in r.aiter_bytes(chunk_size=64 * 1024):
                    fp.write(chunk)
                    written += len(chunk)
    return written


async def run(platform: str, keyword: str, no_login: bool) -> int:
    pid = PlatformID(platform)
    cli: NeteaseClient | QQClient = NeteaseClient() if pid is PlatformID.NETEASE else QQClient()

    if not no_login:
        ok = await (
            _qr_login_netease(cli) if pid is PlatformID.NETEASE else _qr_login_qq(cli)  # type: ignore[arg-type]
        )
        if not ok:
            return 1

    print(f"\n搜索：{keyword}")
    songs = await cli.search_songs(keyword, limit=10)
    if not songs:
        print("无搜索结果。")
        return 1

    print("搜索结果：")
    for i, s in enumerate(songs[:5]):
        artists = " / ".join(s.artists) if s.artists else "?"
        dur = s.duration_ms // 1000
        print(f"  [{i}] {s.name} - {artists} | {s.album} | {dur}s | id={s.platform_song_id}")

    target = songs[0]
    print(f"\n下载第一条：{target.name} - {target.primary_artist}")

    result = await cli.get_download_url(target, quality=QualityLevel.LOSSLESS)
    if not result.success or not result.source:
        print(f"下载链接获取失败：{result.error}")
        return 1
    src = result.source
    print(
        f"拿到 URL：format={src.audio_format}, quality={src.quality}, "
        f"bitrate={src.bitrate}, size={src.file_size}"
    )

    out_dir = Path("verify_output") / platform
    out_path = out_dir / f"{_safe_filename(target.name)} - {_safe_filename(target.primary_artist)}.{src.audio_format}"
    print(f"开始下载到 {out_path} ...")
    n = await _download_audio(src.url, out_path)
    print(f"完成，写入 {n / 1024 / 1024:.2f} MB")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MusicHub Milestone 1 验证脚本")
    parser.add_argument("platform", choices=["netease", "qq"], help="平台")
    parser.add_argument("keyword", help="搜索关键词")
    parser.add_argument("--no-login", action="store_true", help="跳过扫码登录（游客模式）")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args.platform, args.keyword, args.no_login))
    except KeyboardInterrupt:
        print("\n用户中断")
        return 130


if __name__ == "__main__":
    sys.exit(main())
