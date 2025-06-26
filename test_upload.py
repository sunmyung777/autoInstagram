import random
import time
import os
import json
from typing import Dict, List, Tuple
from instagrapi import Client
from pathlib import Path
import logging
from datetime import datetime
import glob
from scheduler import InstagramScheduler

class InstagramUploader:
    def __init__(self, config_path: str = "config.json"):
        """설정 파일 로드 및 초기화"""
        self.config = self._load_config(config_path)
        self.accounts = self.config["accounts"]
        self.upload_settings = self.config["upload_settings"]
        self.directory_structure = self.config["directory_structure"]
        self.scheduler = InstagramScheduler(config_path)

        # 로그 디렉토리 설정
        log_dir = self.config["directory_structure"]["logs_dir"]
        os.makedirs(log_dir, exist_ok=True)

        # 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(
                    log_dir,
                    f'instagram_upload_{datetime.now().strftime("%Y%m%d")}.log'
                )),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _load_config(self, config_path: str) -> Dict:
        """설정 파일 로드"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"설정 파일 로드 실패: {str(e)}")
            raise

    def _get_video_and_caption(self, account: Dict) -> List[Tuple[str, str]]:
        """계정별 업로드할 비디오와 캡션 목록 가져오기"""
        videos_dir = os.path.join(account["account_directory"], self.directory_structure["videos_dir"])
        captions_dir = os.path.join(account["account_directory"], self.directory_structure["captions_dir"])

        # 비디오 파일 목록 가져오기
        video_files = glob.glob(os.path.join(videos_dir, "*.mp4"))
        uploads = []

        for video_path in video_files:
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            caption_path = os.path.join(captions_dir, f"{video_name}.txt")

            # 캡션 파일이 있으면 읽고, 없으면 기본 태그로 생성
            if os.path.exists(caption_path):
                with open(caption_path, 'r', encoding='utf-8') as f:
                    caption = f.read().strip()
            else:
                tags = " ".join(account.get("default_tags", []))
                caption = f"📱 {video_name}\n\n{tags}"

            uploads.append((video_path, caption))

        return uploads

    def setup_instagrapi_session(self, username: str, password: str, proxy: str = None) -> Client:
        """인스타그램 세션 설정 및 로그인"""
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

        # 추가 헤더 설정
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
        session_path = Path("sessions") / f"{username}_session.json"

        # 프록시 설정
        if proxy:
            cl.set_proxy(proxy)
            self.logger.info(f" 프록시 설정 완료: {proxy}")

        try:
            # 기존 세션 불러오기 시도
            if session_path.exists():
                self.logger.info(f" 기존 세션 파일 발견, 로드 시도 중... ({username})")
                cl.load_settings(session_path)
                cl.login(username, password)

                # 세션 유효성 검증
                try:
                    cl.get_timeline_feed()
                    self.logger.info(f" 기존 세션으로 로그인 성공: {username}")
                except Exception:
                    self.logger.warning(f" 세션이 만료되어 재로그인 시도 중... ({username})")
                    cl.login(username, password)
                    cl.dump_settings(session_path)
                    self.logger.info(f" 재로그인 성공: {username}")
            else:
                self.logger.info(f" 새로운 세션으로 로그인 시도 중... ({username})")
                cl.login(username, password)
                cl.dump_settings(session_path)
                self.logger.info(f" 새로운 세션으로 로그인 성공: {username}")

            # 세션 정보 저장
            session_info = {
                "user_agent": user_agent,
                "last_login": time.strftime("%Y-%m-%d %H:%M:%S"),
                "username": username
            }
            with open(session_path.with_suffix('.info'), 'w', encoding='utf-8') as f:
                json.dump(session_info, f, ensure_ascii=False, indent=2)

        except Exception as e:
            self.logger.error(f" 로그인 실패 ({username}): {str(e)}")
            if session_path.exists():
                self.logger.info(f" 오류로 인해 기존 세션 파일 삭제 ({username})")
                session_path.unlink()
            raise

        return cl

    def upload_video(self, cl: Client, video_path: str, caption: str) -> None:
        """비디오 업로드 with 랜덤 딜레이"""
        try:
            # 업로드 전 랜덤 딜레이
            delay = random.uniform(
                self.upload_settings["min_delay_before_upload"],
                self.upload_settings["max_delay_before_upload"]
            )
            self.logger.info(f"⏳ 업로드 전 {delay:.1f}초 대기 중...")
            time.sleep(delay)

            # 비디오 업로드
            media = cl.clip_upload(
                video_path,
                caption,
                thumbnail=None  # 썸네일 자동 생성
            )
            self.logger.info(f" 업로드 완료! Media ID: {media.pk}")

            # 업로드된 파일 이동 또는 표시
            uploaded_mark = video_path + ".uploaded"
            Path(uploaded_mark).touch()

        except Exception as e:
            self.logger.error(f" 업로드 실패: {str(e)}")
            raise

    def process_account(self, account: Dict) -> None:
        """단일 계정 처리"""
        try:
            # 클라이언트 설정 및 로그인
            client = self.setup_instagrapi_session(
                username=account["username"],
                password=account["password"],
                proxy=account["proxy"]
            )

            # 업로드할 비디오와 캡션 목록 가져오기
            uploads = self._get_video_and_caption(account)

            if not uploads:
                self.logger.info(f" 업로드할 비디오가 없습니다. ({account['username']})")
                return

            # 각 비디오 업로드
            for video_path, caption in uploads:
                try:
                    self.logger.info(f" 비디오 업로드 시작: {os.path.basename(video_path)}")
                    self.upload_video(client, video_path, caption)
                except Exception as e:
                    self.logger.error(f" 비디오 업로드 실패 ({os.path.basename(video_path)}): {str(e)}")
                    continue

                # 비디오 간 딜레이
                if uploads.index((video_path, caption)) < len(uploads) - 1:
                    delay = random.uniform(
                        self.upload_settings["min_delay_between_uploads"],
                        self.upload_settings["max_delay_between_uploads"]
                    )
                    self.logger.info(f" 다음 비디오 업로드까지 {delay:.1f}초 대기...")
                    time.sleep(delay)

        except Exception as e:
            self.logger.error(f" 계정 처리 실패 ({account['username']}): {str(e)}")

    def process_all_accounts(self) -> None:
        """모든 계정 순차 처리"""
        for account in self.accounts:
            self.logger.info(f" 계정 처리 시작: {account['username']}")
            try:
                self.process_account(account)

                # 다음 계정 처리 전 랜덤 딜레이
                if account != self.accounts[-1]:  # 마지막 계정이 아닌 경우에만 딜레이
                    delay = random.uniform(
                        self.upload_settings["min_delay_between_uploads"],
                        self.upload_settings["max_delay_between_uploads"]
                    )
                    self.logger.info(f" 다음 계정 처리까지 {delay:.1f}초 대기...")
                    time.sleep(delay)

            except Exception as e:
                self.logger.error(f" 계정 처리 중 오류 발생: {str(e)}")
                continue  # 다음 계정으로 진행

    def process_scheduled_uploads(self) -> None:
        """예약된 업로드 처리"""
        pending_uploads = self.scheduler.get_pending_uploads()

        for schedule in pending_uploads:
            try:
                self.logger.info(f" 예약된 업로드 처리 시작 (ID: {schedule['id']})")

                # 계정 찾기
                account = next(
                    (acc for acc in self.accounts if acc["username"] == schedule["account_username"]),
                    None
                )

                if not account:
                    error_msg = f"계정을 찾을 수 없음: {schedule['account_username']}"
                    self.logger.error(f" {error_msg}")
                    self.scheduler.mark_schedule_failed(schedule["id"], error_msg)
                    continue

                # 비디오 파일 존재 확인
                if not os.path.exists(schedule["video_path"]):
                    error_msg = f"비디오 파일을 찾을 수 없음: {schedule['video_path']}"
                    self.logger.error(f" {error_msg}")
                    self.scheduler.mark_schedule_failed(schedule["id"], error_msg)
                    continue

                # 클라이언트 설정 및 로그인
                client = self.setup_instagrapi_session(
                    username=account["username"],
                    password=account["password"],
                    proxy=account.get("proxy")
                )

                # 비디오 업로드
                self.upload_video(
                    client,
                    schedule["video_path"],
                    schedule["caption"] or f"📱 {os.path.splitext(os.path.basename(schedule['video_path']))[0]}"
                )

                # 업로드 완료 처리
                self.scheduler.mark_schedule_completed(schedule["id"])

                # 다음 업로드 전 딜레이
                if schedule != pending_uploads[-1]:
                    delay = random.uniform(
                        self.upload_settings["min_delay_between_uploads"],
                        self.upload_settings["max_delay_between_uploads"]
                    )
                    self.logger.info(f" 다음 예약 업로드까지 {delay:.1f}초 대기...")
                    time.sleep(delay)

            except Exception as e:
                error_msg = str(e)
                self.logger.error(f" 예약 업로드 실패 (ID: {schedule['id']}): {error_msg}")
                self.scheduler.mark_schedule_failed(schedule["id"], error_msg)

def main():
    try:
        # 업로더 인스턴스 생성
        uploader = InstagramUploader()

        # 예약된 업로드 처리
        uploader.process_scheduled_uploads()

        # 일반 업로드 처리
        uploader.process_all_accounts()

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f" 메인 프로세스 오류: {str(e)}")

if __name__ == "__main__":
    main()
