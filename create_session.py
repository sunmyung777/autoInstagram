#!/usr/bin/env python
import json
import random
import time
from pathlib import Path
import logging
from instagrapi import Client

class InstagramSessionCreator:
    def __init__(self):
        self.logger = logging.getLogger('instagram_session')
        self._setup_logging()

    def _setup_logging(self):
        """로깅 설정"""
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def create_session(self, username: str, password: str, proxy: str = None) -> bool:
        """인스타그램 세션 생성 및 저장

        Args:
            username (str): 인스타그램 사용자명
            password (str): 인스타그램 비밀번호
            proxy (str, optional): 프록시 서버 주소. 기본값은 None.

        Returns:
            bool: 세션 생성 성공 여부
        """
        cl = Client()

        # 기본 설정
        cl.set_locale('ko_KR')
        cl.set_timezone_offset(9 * 60 * 60)  # 한국 시간대 (UTC+9)
        cl.set_country_code(82)  # 한국
        cl.set_country("KR")

        # 디바이스 설정
        cl.set_device({
            "app_version": "269.0.0.18.75",
            "android_version": 26,
            "android_release": "8.0.0",
            "dpi": "480dpi",
            "resolution": "1080x1920",
            "manufacturer": "Samsung",
            "device": "SM-G950F",
            "model": "G950F",
            "cpu": "universal8895",
            "version_code": "314665256"
        })

        # User-Agent 설정 (Android 기반)
        user_agent = "Instagram 269.0.0.18.75 Android (26/8.0.0; 480dpi; 1080x1920; Samsung; SM-G950F; dreamlte; universal8895; ko_KR; 314665256)"
        cl.set_user_agent(user_agent)

        # UUID 설정
        cl.set_settings({
            "uuids": {
                "phone_id": "".join(random.choices("abcdef0123456789", k=32)),
                "uuid": "".join(random.choices("abcdef0123456789", k=32)),
                "client_session_id": "".join(random.choices("abcdef0123456789", k=32)),
                "advertising_id": "".join(random.choices("abcdef0123456789", k=32)),
                "android_device_id": "".join(random.choices("abcdef0123456789", k=32)),
            }
        })

        # 세션 파일 경로
        sessions_dir = Path("sessions")
        sessions_dir.mkdir(exist_ok=True)
        session_path = sessions_dir / f"{username}_session.json"

        # 프록시 설정
        if proxy:
            cl.set_proxy(proxy)
            self.logger.info(f"✅ 프록시 설정 완료: {proxy}")

        try:
            self.logger.info(f"🔄 로그인 시도 중... ({username})")
            cl.login(username, password)

            # 세션 저장
            cl.dump_settings(session_path)

            # 세션 정보 저장
            session_info = {
                "user_agent": user_agent,
                "last_login": time.strftime("%Y-%m-%d %H:%M:%S"),
                "username": username
            }
            with open(session_path.with_suffix('.info'), 'w', encoding='utf-8') as f:
                json.dump(session_info, f, ensure_ascii=False, indent=2)

            self.logger.info(f"✅ 세션 생성 및 저장 완료: {username}")
            return True

        except Exception as e:
            self.logger.error(f"❌ 세션 생성 실패 ({username}): {str(e)}")
            if session_path.exists():
                session_path.unlink()
            return False

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Instagram 세션 생성 도구')
    parser.add_argument('username', help='인스타그램 사용자명')
    parser.add_argument('password', help='인스타그램 비밀번호')
    parser.add_argument('--proxy', help='프록시 서버 주소 (예: http://proxy.example.com:8080)', default=None)

    args = parser.parse_args()

    creator = InstagramSessionCreator()
    success = creator.create_session(args.username, args.password, args.proxy)

    return 0 if success else 1

if __name__ == '__main__':
    exit(main())